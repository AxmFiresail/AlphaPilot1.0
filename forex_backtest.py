"""Forex Backtesting Simulator.
Simulates bar-by-bar Forex trade execution with Long/Short positions, pip counting,
spread friction, stop loss (SL), and take profit (TP) triggers.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from forex_pairs import FOREX_PAIRS, normalize_pair, get_pip_size, calculate_forex_pnl
from forex_data import fetch_forex_history
from forex_parser import ForexStrategySpec


@dataclass
class ForexBacktestResult:
    spec: ForexStrategySpec
    metrics: Dict[str, Any]
    equity_curve: pd.DataFrame     # Timestamp, Balance, Equity, Pips_Cum, Drawdown_Pct
    trade_log: pd.DataFrame        # Details of every completed Forex trade
    price_df: pd.DataFrame         # Candles with indicators


def run_forex_backtest(
    spec: ForexStrategySpec,
    period: str = "1y",
    initial_balance: float = 10000.0,
    leverage: float = 30.0,
) -> ForexBacktestResult:
    """Run bar-by-bar backtest simulation for a Forex strategy."""
    pair = normalize_pair(spec.pair)
    meta = FOREX_PAIRS[pair]
    pip_size = meta["pip_size"]
    spread_pips = meta["spread_pips"]
    half_spread = (spread_pips * pip_size) / 2.0

    # 1. Fetch historical candles
    df = fetch_forex_history(pair, interval=spec.timeframe, period=period)
    if len(df) < 50:
        raise ValueError(f"Insufficient historical data for {pair} on timeframe {spec.timeframe} ({len(df)} bars)")

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]

    # 2. Compute Indicators
    if spec.condition_type == "ema_crossover":
        fast = int(spec.params.get("fast", 20))
        slow = int(spec.params.get("slow", 50))
        fast_series = closes.ewm(span=fast, adjust=False).mean()
        slow_series = closes.ewm(span=slow, adjust=False).mean()
        df["Indicator_Fast"] = fast_series
        df["Indicator_Slow"] = slow_series
        raw_signal = np.where(fast_series > slow_series, 1, -1 if spec.allow_short else 0)

    elif spec.condition_type == "sma_crossover":
        fast = int(spec.params.get("fast", 50))
        slow = int(spec.params.get("slow", 200))
        fast_series = closes.rolling(fast).mean()
        slow_series = closes.rolling(slow).mean()
        df["Indicator_Fast"] = fast_series
        df["Indicator_Slow"] = slow_series
        raw_signal = np.where(fast_series > slow_series, 1, -1 if spec.allow_short else 0)

    elif spec.condition_type == "rsi_reversal":
        period_len = int(spec.params.get("period", 14))
        oversold = float(spec.params.get("oversold", 30))
        overbought = float(spec.params.get("overbought", 70))
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(period_len).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period_len).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        df["Indicator_RSI"] = rsi
        raw_signal = np.where(rsi < oversold, 1, np.where(rsi > overbought, -1 if spec.allow_short else 0, 0))

    elif spec.condition_type == "breakout":
        window = int(spec.params.get("period", 20))
        roll_high = highs.rolling(window).max().shift(1)
        roll_low = lows.rolling(window).min().shift(1)
        df["Indicator_High"] = roll_high
        df["Indicator_Low"] = roll_low
        raw_signal = np.where(closes > roll_high, 1, np.where(closes < roll_low, -1 if spec.allow_short else 0, 0))

    else:
        # Default price above 200 SMA
        period_len = int(spec.params.get("period", 200))
        sma = closes.rolling(period_len).mean()
        df["Indicator_SMA"] = sma
        raw_signal = np.where(closes > sma, 1, -1 if spec.allow_short else 0)

    df["Signal"] = raw_signal
    # Shift signal to avoid lookahead bias (trade executes on NEXT bar)
    df["Exec_Signal"] = df["Signal"].shift(1).fillna(0).astype(int)

    # 3. Simulate Bar-by-Bar Trades with SL & TP
    balance = initial_balance
    position = None  # None or dict(direction, entry_price, entry_time, sl_price, tp_price)
    trades = []
    equity_curve = []
    cum_pips = 0.0

    sl_dist = (spec.stop_loss_pips * pip_size) if spec.stop_loss_pips else None
    tp_dist = (spec.take_profit_pips * pip_size) if spec.take_profit_pips else None

    warmup = 50
    for i in range(warmup, len(df)):
        ts = df.index[i]
        c = closes.iloc[i]
        h = highs.iloc[i]
        l = lows.iloc[i]
        o = df["Open"].iloc[i]
        target_sig = df["Exec_Signal"].iloc[i]

        # Check existing position for SL / TP hit during the bar
        if position is not None:
            p_dir = position["direction"]
            entry_p = position["entry_price"]
            exit_p = None
            exit_reason = None

            if p_dir == "BUY":
                # Check Stop Loss
                if position["sl_price"] and l <= position["sl_price"]:
                    exit_p = position["sl_price"]
                    exit_reason = "Stop Loss"
                # Check Take Profit
                elif position["tp_price"] and h >= position["tp_price"]:
                    exit_p = position["tp_price"]
                    exit_reason = "Take Profit"
                # Check signal flip
                elif target_sig == -1 or (target_sig == 0 and not spec.allow_short):
                    exit_p = o - half_spread  # exit at bar open with spread
                    exit_reason = "Signal Reverse"

            elif p_dir == "SELL":
                # Check Stop Loss
                if position["sl_price"] and h >= position["sl_price"]:
                    exit_p = position["sl_price"]
                    exit_reason = "Stop Loss"
                # Check Take Profit
                elif position["tp_price"] and l <= position["tp_price"]:
                    exit_p = position["tp_price"]
                    exit_reason = "Take Profit"
                # Check signal flip
                elif target_sig == 1:
                    exit_p = o + half_spread  # exit at bar open with spread
                    exit_reason = "Signal Reverse"

            # Execute Close if triggered
            if exit_p is not None:
                pips, dollar_pnl = calculate_forex_pnl(pair, entry_p, exit_p, p_dir, spec.lot_size)
                # Deduct spread
                pips -= spread_pips
                dollar_pnl -= (spread_pips * pip_size * (spec.lot_size * 100000.0))

                balance += dollar_pnl
                cum_pips += pips

                trades.append({
                    "Entry Time": position["entry_time"].strftime("%Y-%m-%d %H:%M"),
                    "Exit Time": ts.strftime("%Y-%m-%d %H:%M"),
                    "Pair": pair,
                    "Type": p_dir,
                    "Entry Price": round(entry_p, 5 if pip_size == 0.0001 else 3),
                    "Exit Price": round(exit_p, 5 if pip_size == 0.0001 else 3),
                    "Exit Reason": exit_reason,
                    "Pips": round(pips, 1),
                    "PnL ($)": round(dollar_pnl, 2),
                    "Balance": round(balance, 2),
                })
                position = None

        # Check for New Position Entry
        if position is None and target_sig != 0:
            new_dir = "BUY" if target_sig == 1 else "SELL"
            # Apply entry spread (Buy at Ask, Sell at Bid)
            entry_p = (o + half_spread) if new_dir == "BUY" else (o - half_spread)

            sl_p = None
            tp_p = None
            if sl_dist:
                sl_p = (entry_p - sl_dist) if new_dir == "BUY" else (entry_p + sl_dist)
            if tp_dist:
                tp_p = (entry_p + tp_dist) if new_dir == "BUY" else (entry_p - tp_dist)

            position = {
                "direction": new_dir,
                "entry_price": entry_p,
                "entry_time": ts,
                "sl_price": sl_p,
                "tp_price": tp_p,
            }

        # Track bar-end equity
        unrealized_pnl = 0.0
        if position is not None:
            _, unrealized_pnl = calculate_forex_pnl(pair, position["entry_price"], c, position["direction"], spec.lot_size)

        equity_curve.append({
            "timestamp": ts,
            "Balance": balance,
            "Equity": balance + unrealized_pnl,
            "Pips_Cumulative": cum_pips,
        })

    # 4. Generate Performance Metrics
    eq_df = pd.DataFrame(equity_curve).set_index("timestamp")
    eq_df["Peak_Equity"] = eq_df["Equity"].cummax()
    eq_df["Drawdown_Pct"] = ((eq_df["Equity"] - eq_df["Peak_Equity"]) / eq_df["Peak_Equity"]) * 100.0

    trades_df = pd.DataFrame(trades)

    total_net_pnl = balance - initial_balance
    return_pct = (total_net_pnl / initial_balance) * 100.0

    if not trades_df.empty:
        wins = trades_df[trades_df["PnL ($)"] > 0]
        losses = trades_df[trades_df["PnL ($)"] <= 0]
        win_rate = (len(wins) / len(trades_df)) * 100.0
        gross_profit = wins["PnL ($)"].sum()
        gross_loss = abs(losses["PnL ($)"].sum())
        profit_factor = round(gross_profit / (gross_loss + 1e-9), 2)
        avg_win_pips = round(wins["Pips"].mean(), 1) if not wins.empty else 0.0
        avg_loss_pips = round(losses["Pips"].mean(), 1) if not losses.empty else 0.0
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_win_pips = 0.0
        avg_loss_pips = 0.0

    max_dd_pct = round(eq_df["Drawdown_Pct"].min(), 2)

    metrics = {
        "Pair": pair,
        "Timeframe": spec.timeframe,
        "Total Return (%)": round(return_pct, 2),
        "Net Profit ($)": round(total_net_pnl, 2),
        "Total Pips": round(cum_pips, 1),
        "Win Rate (%)": round(win_rate, 1),
        "Profit Factor": profit_factor,
        "Total Trades": len(trades_df),
        "Max Drawdown (%)": max_dd_pct,
        "Avg Win (Pips)": avg_win_pips,
        "Avg Loss (Pips)": avg_loss_pips,
        "Lot Size": spec.lot_size,
        "Initial Balance ($)": initial_balance,
        "Final Balance ($)": round(balance, 2),
    }

    return ForexBacktestResult(
        spec=spec,
        metrics=metrics,
        equity_curve=eq_df,
        trade_log=trades_df,
        price_df=df,
    )
