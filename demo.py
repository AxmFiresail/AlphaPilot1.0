"""CLI Demo for Plain English Trader.
Runs the natural language parser, backtest engine, and live order evaluator directly from the terminal.
"""

import sys
from parser import parse_strategy
from engine import run_backtest
from broker import evaluate_live_signal

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Buy tech stocks when the market is up, move to bonds when it drops"
    print("\n=======================================================")
    print("📈 ALPHA PILOT: PLAIN ENGLISH TRADING BOT")
    print("=======================================================")
    print(f"\n[1] USER INPUT STRATEGY:\n    \"{prompt}\"\n")

    # 1. Parse Strategy
    spec = parse_strategy(prompt)
    print("[2] PARSED EXECUTION BLUEPRINT:")
    print(f"    Formula: {spec.human_summary}")
    print(f"    Signal Asset: {spec.signal_asset}")
    print(f"    Bull Target:  {spec.bull_assets}")
    print(f"    Bear Target:  {spec.bear_assets}\n")

    # 2. Backtest
    print("[3] RUNNING 5-YEAR HISTORICAL BACKTEST...")
    res = run_backtest(spec, years=5, initial_capital=10000.0)
    m = res.metrics
    print("    -----------------------------------------")
    print(f"    Strategy Total Return:  {m['Total Return (%)']}%  (vs SPY {m['Benchmark Return (%)']}%)")
    print(f"    Strategy CAGR:          {m['CAGR (%)']}%  (vs SPY {m['Benchmark CAGR (%)']}%)")
    print(f"    Max Drawdown:           {m['Max Drawdown (%)']}%  (vs SPY {m['Benchmark Max Drawdown (%)']}%)")
    print(f"    Sharpe Ratio:           {m['Sharpe Ratio']}")
    print(f"    Sortino Ratio:          {m['Sortino Ratio']}")
    print(f"    Alpha:                  {m['Alpha (%)']}%  (Beta: {m['Beta']})")
    print(f"    Total Rebalance Events: {m['Total Rebalances']}")
    print("    -----------------------------------------\n")

    # 3. Live Evaluation
    print("[4] EVALUATING LIVE MARKET STATUS TODAY:")
    status = evaluate_live_signal(spec, portfolio_cash=10000.0)
    print(f"    Current Time:        {status.timestamp}")
    print(f"    {status.signal_asset} Price Today:     ${status.current_price:.2f}")
    print(f"    Indicator Status:    {status.indicator_summary}")
    print(f"    Active Regime:       {'🟢 BULL' if status.is_bullish else '🔴 BEAR'}")
    print(f"    Target Allocation:   {status.target_allocation}")
    print(f"    Generated Orders:    {len(status.orders)}")
    for ord in status.orders:
        print(f"      -> {ord.action} {ord.shares} shares of {ord.symbol} @ ~${ord.estimated_price:.2f} (${ord.estimated_total:,.2f})")
    print("\n=======================================================\n")

if __name__ == "__main__":
    main()
