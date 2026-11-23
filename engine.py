"""Backtesting Engine for Natural Language Trading Strategies.
Simulates daily portfolio returns, rebalances, transaction slippage, and performance metrics.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from data_loader import get_multi_asset_close, resolve_ticker
from parser import StrategySpec


@dataclass
class BacktestResult:
    spec: StrategySpec
    metrics: Dict[str, Any]
    equity_curve: pd.DataFrame     # Contains: Strategy, Benchmark, Drawdown, Regime
    trade_log: pd.DataFrame        # Log of allocation switches
    asset_prices: pd.DataFrame     # Historical adjusted closes
    signals: pd.Series             # Boolean series of bullish (True) vs bearish (False)


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Standard Relative Strength Index calculation."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def run_backtest(
    spec: StrategySpec,
    years: int = 5,
    initial_capital: float = 10000.0,
    slippage_pct: float = 0.0005,  # 5 bps (0.05%) slippage per rebalance
) -> BacktestResult:
    """Execute historical simulation for a given StrategySpec."""

    # 1. Gather all required assets
    all_assets = set()
    all_assets.add(spec.benchmark)
    all_assets.add(spec.signal_asset)
    for a in spec.bull_assets.keys():
        all_assets.add(resolve_ticker(a))
    for a in spec.bear_assets.keys():
        all_assets.add(resolve_ticker(a))

    prices = get_multi_asset_close(list(all_assets), years=years)

    # 2. Compute the Signal Condition
    sig_series = prices[spec.signal_asset]

    if spec.condition_type == "price_above_sma":
        period = int(spec.params.get("period", 200))
        sma = sig_series.rolling(period).mean()
        raw_signal = sig_series > sma

    elif spec.condition_type == "sma_crossover":
        fast = int(spec.params.get("fast", 50))
        slow = int(spec.params.get("slow", 200))
        fast_sma = sig_series.rolling(fast).mean()
        slow_sma = sig_series.rolling(slow).mean()
        raw_signal = fast_sma > slow_sma

    elif spec.condition_type == "rsi_oversold":
        period = int(spec.params.get("period", 14))
        threshold = float(spec.params.get("threshold", 30))
        rsi = calculate_rsi(sig_series, period=period)
        raw_signal = rsi < threshold

    elif spec.condition_type == "momentum_positive":
        days = int(spec.params.get("days", 20))
        mom = sig_series.pct_change(days)
        raw_signal = mom > 0

    else:
        # Default fallback
        sma = sig_series.rolling(200).mean()
        raw_signal = sig_series > sma

    # 3. Clean up warmup period NaNs
    valid_idx = raw_signal.dropna().index
    if len(valid_idx) < 30:
        raise ValueError(f"Insufficient historical data after indicator warmup ({len(valid_idx)} days). Try increasing years.")

    prices = prices.loc[valid_idx]
    raw_signal = raw_signal.loc[valid_idx]

    # Shift signal by 1 day to execute at next day's open/close (No Lookahead Bias)
    execution_signal = raw_signal.shift(1).fillna(False)

    # 4. Simulate Daily Portfolio Performance
    daily_returns = prices.pct_change().fillna(0.0)
    benchmark_returns = daily_returns[spec.benchmark]

    n_days = len(prices)
    strat_equity = np.zeros(n_days)
    bench_equity = np.zeros(n_days)
    strat_equity[0] = initial_capital
    bench_equity[0] = initial_capital

    regimes = []
    trades = []
    prev_state = None

    for i in range(1, n_days):
        date = prices.index[i]
        is_bull = bool(execution_signal.iloc[i])
        current_state = "BULL" if is_bull else "BEAR"
        regimes.append(current_state)

        # Check for allocation switch
        rebalanced = (prev_state is not None and prev_state != current_state)
        prev_state = current_state

        target_weights = spec.bull_assets if is_bull else spec.bear_assets

        # Compute day's weighted return
        day_ret = 0.0
        for asset, weight in target_weights.items():
            r = daily_returns[asset].iloc[i]
            day_ret += weight * r

        # Deduct transaction cost / friction on rebalance days
        friction = slippage_pct if rebalanced else 0.0
        net_ret = day_ret - friction

        strat_equity[i] = strat_equity[i - 1] * (1.0 + net_ret)
        bench_equity[i] = bench_equity[i - 1] * (1.0 + benchmark_returns.iloc[i])

        if rebalanced:
            target_str = ", ".join([f"{int(w*100)}% {a}" for a, w in target_weights.items()])
            trades.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Regime": current_state,
                "Trigger": f"{spec.signal_asset} {'UP' if is_bull else 'DOWN'} ({spec.condition_type})",
                "New Allocation": target_str,
                "Signal Price": round(float(sig_series.loc[date]), 2),
                "Portfolio Value": round(float(strat_equity[i]), 2),
            })

    # Regimes list adjustment for initial day
    regimes.insert(0, regimes[0] if regimes else "NEUTRAL")

    # 5. Build Curves and Drawdowns
    equity_df = pd.DataFrame(
        {
            "Strategy": strat_equity,
            "Benchmark": bench_equity,
            "Regime": regimes,
        },
        index=prices.index,
    )

    # Rolling peak and drawdowns
    strat_peak = equity_df["Strategy"].cummax()
    strat_dd = (equity_df["Strategy"] - strat_peak) / strat_peak
    bench_peak = equity_df["Benchmark"].cummax()
    bench_dd = (equity_df["Benchmark"] - bench_peak) / bench_peak

    equity_df["Strategy_Drawdown"] = strat_dd * 100.0
    equity_df["Benchmark_Drawdown"] = bench_dd * 100.0

    # 6. Calculate Quantitative Metrics
    strat_daily_ret = equity_df["Strategy"].pct_change().dropna()
    bench_daily_ret = equity_df["Benchmark"].pct_change().dropna()

    days_total = len(equity_df)
    years_fraction = max(days_total / 252.0, 0.1)

    total_return = (strat_equity[-1] / strat_equity[0]) - 1.0
    bench_total_return = (bench_equity[-1] / bench_equity[0]) - 1.0

    cagr = ((strat_equity[-1] / strat_equity[0]) ** (1.0 / years_fraction)) - 1.0
    bench_cagr = ((bench_equity[-1] / bench_equity[0]) ** (1.0 / years_fraction)) - 1.0

    risk_free_rate = 0.03  # 3% annual cash rate
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0
    excess_ret = strat_daily_ret - daily_rf

    # Sharpe Ratio
    std_dev = strat_daily_ret.std()
    sharpe = float((excess_ret.mean() / (std_dev + 1e-9)) * np.sqrt(252)) if std_dev > 0 else 0.0

    # Sortino Ratio (downside deviation only)
    downside_ret = strat_daily_ret[strat_daily_ret < 0]
    downside_std = downside_ret.std()
    sortino = float((excess_ret.mean() / (downside_std + 1e-9)) * np.sqrt(252)) if downside_std > 0 else 0.0

    # Max Drawdown
    max_dd = float(strat_dd.min()) * 100.0
    bench_max_dd = float(bench_dd.min()) * 100.0

    # Calmar Ratio
    calmar = float(cagr / (abs(max_dd / 100.0) + 1e-9))

    # Beta and Alpha vs Benchmark
    cov = np.cov(strat_daily_ret, bench_daily_ret)[0][1]
    bench_var = np.var(bench_daily_ret)
    beta = float(cov / (bench_var + 1e-9))
    alpha = float((cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))) * 100.0)

    # Win Rate (% of positive trading days)
    win_rate = float((strat_daily_ret > 0).mean() * 100.0)

    trade_log = pd.DataFrame(trades)

    metrics = {
        "Total Return (%)": round(total_return * 100.0, 2),
        "CAGR (%)": round(cagr * 100.0, 2),
        "Benchmark Return (%)": round(bench_total_return * 100.0, 2),
        "Benchmark CAGR (%)": round(bench_cagr * 100.0, 2),
        "Sharpe Ratio": round(sharpe, 2),
        "Sortino Ratio": round(sortino, 2),
        "Max Drawdown (%)": round(max_dd, 2),
        "Benchmark Max Drawdown (%)": round(bench_max_dd, 2),
        "Calmar Ratio": round(calmar, 2),
        "Beta": round(beta, 2),
        "Alpha (%)": round(alpha, 2),
        "Win Rate (%)": round(win_rate, 1),
        "Total Rebalances": len(trades),
        "Days Simulated": days_total,
        "Initial Capital ($)": initial_capital,
        "Final Strategy Value ($)": round(strat_equity[-1], 2),
        "Final Benchmark Value ($)": round(bench_equity[-1], 2),
    }

    return BacktestResult(
        spec=spec,
        metrics=metrics,
        equity_curve=equity_df,
        trade_log=trade_log,
        asset_prices=prices,
        signals=raw_signal,
    )
