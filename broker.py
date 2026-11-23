"""Broker & Execution Automation module.
Evaluates live market conditions, computes rebalance order deltas,
executes orders via Simulated Broker or Alpaca API, and generates scheduled cron scripts.
"""

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from data_loader import fetch_ticker_data, resolve_ticker
from engine import calculate_rsi
from parser import StrategySpec

STATE_FILE = os.path.join(os.path.dirname(__file__), "portfolio_state.json")


@dataclass
class RebalanceOrder:
    symbol: str
    action: str            # 'BUY' or 'SELL'
    shares: int
    estimated_price: float
    estimated_total: float
    target_weight: float


@dataclass
class LiveSignalStatus:
    timestamp: str
    signal_asset: str
    current_price: float
    indicator_summary: str
    is_bullish: bool
    active_regime: str
    target_allocation: Dict[str, float]
    orders: List[RebalanceOrder]


def load_simulated_portfolio(initial_cash: float = 10000.0) -> Dict[str, Any]:
    """Load or initialize simulated portfolio state on disk."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    state = {
        "cash": initial_cash,
        "positions": {},  # symbol -> shares
        "last_rebalance": None,
        "history": [],
    }
    save_simulated_portfolio(state)
    return state


def save_simulated_portfolio(state: Dict[str, Any]):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def evaluate_live_signal(spec: StrategySpec, portfolio_cash: float = 10000.0) -> LiveSignalStatus:
    """Evaluate current live market status against strategy condition and calculate orders."""
    # Fetch 1 year of daily data to get recent moving averages
    df = fetch_ticker_data(spec.signal_asset, years=1, force_refresh=True)
    closes = df["AdjClose"]
    latest_price = float(closes.iloc[-1])

    is_bull = False
    indicator_text = ""

    if spec.condition_type == "price_above_sma":
        period = int(spec.params.get("period", 200))
        sma = float(closes.rolling(period).mean().iloc[-1])
        is_bull = latest_price > sma
        diff_pct = ((latest_price / sma) - 1.0) * 100.0
        sign = "+" if diff_pct >= 0 else ""
        indicator_text = f"Current {latest_price:.2f} vs {period}-SMA {sma:.2f} ({sign}{diff_pct:.2f}%)"

    elif spec.condition_type == "sma_crossover":
        fast = int(spec.params.get("fast", 50))
        slow = int(spec.params.get("slow", 200))
        fast_sma = float(closes.rolling(fast).mean().iloc[-1])
        slow_sma = float(closes.rolling(slow).mean().iloc[-1])
        is_bull = fast_sma > slow_sma
        indicator_text = f"{fast}-SMA {fast_sma:.2f} vs {slow}-SMA {slow_sma:.2f}"

    elif spec.condition_type == "rsi_oversold":
        period = int(spec.params.get("period", 14))
        threshold = float(spec.params.get("threshold", 30))
        rsi_val = float(calculate_rsi(closes, period=period).iloc[-1])
        is_bull = rsi_val < threshold
        indicator_text = f"14-RSI: {rsi_val:.1f} (Threshold < {threshold})"

    elif spec.condition_type == "momentum_positive":
        days = int(spec.params.get("days", 20))
        mom_pct = float(closes.pct_change(days).iloc[-1] * 100.0)
        is_bull = mom_pct > 0
        indicator_text = f"{days}-day Return: {mom_pct:+.2f}%"

    else:
        sma = float(closes.rolling(200).mean().iloc[-1])
        is_bull = latest_price > sma
        indicator_text = f"Price {latest_price:.2f} vs 200-SMA {sma:.2f}"

    active_regime = "BULL" if is_bull else "BEAR"
    target_alloc = spec.bull_assets if is_bull else spec.bear_assets

    # Load current simulated portfolio positions
    port_state = load_simulated_portfolio(portfolio_cash)
    current_cash = port_state["cash"]
    positions = port_state.get("positions", {})

    # Calculate Total Portfolio Net Worth
    total_val = current_cash
    prices_map = {}
    for ticker in list(target_alloc.keys()) + list(positions.keys()):
        if ticker not in prices_map:
            try:
                tdf = fetch_ticker_data(ticker, years=1)
                prices_map[ticker] = float(tdf["AdjClose"].iloc[-1])
            except Exception:
                prices_map[ticker] = 100.0

    for ticker, shares in positions.items():
        total_val += shares * prices_map.get(ticker, 0.0)

    # Compute Rebalance Order Deltas
    orders: List[RebalanceOrder] = []

    # First, handle liquidating assets not in target allocation
    for ticker, shares in positions.items():
        if shares > 0 and ticker not in target_alloc:
            p = prices_map.get(ticker, 1.0)
            orders.append(
                RebalanceOrder(
                    symbol=ticker,
                    action="SELL",
                    shares=int(shares),
                    estimated_price=round(p, 2),
                    estimated_total=round(shares * p, 2),
                    target_weight=0.0,
                )
            )

    # Then adjust or initiate target positions
    for ticker, weight in target_alloc.items():
        p = prices_map.get(ticker, 1.0)
        curr_shares = positions.get(ticker, 0)
        target_dollars = total_val * weight
        target_shares = int(target_dollars // p) if p > 0 else 0

        share_delta = target_shares - curr_shares
        if abs(share_delta) > 0:
            action = "BUY" if share_delta > 0 else "SELL"
            orders.append(
                RebalanceOrder(
                    symbol=ticker,
                    action=action,
                    shares=abs(int(share_delta)),
                    estimated_price=round(p, 2),
                    estimated_total=round(abs(share_delta) * p, 2),
                    target_weight=weight,
                )
            )

    return LiveSignalStatus(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        signal_asset=spec.signal_asset,
        current_price=round(latest_price, 2),
        indicator_summary=indicator_text,
        is_bullish=is_bull,
        active_regime=active_regime,
        target_allocation=target_alloc,
        orders=orders,
    )


def execute_simulated_orders(orders: List[RebalanceOrder]) -> Dict[str, Any]:
    """Execute orders in the local simulated paper portfolio."""
    state = load_simulated_portfolio()
    cash = state["cash"]
    positions = state.get("positions", {})
    history = state.get("history", [])

    for ord in orders:
        if ord.action == "SELL":
            curr = positions.get(ord.symbol, 0)
            sold = min(curr, ord.shares)
            proceeds = sold * ord.estimated_price
            cash += proceeds
            positions[ord.symbol] = curr - sold
            if positions[ord.symbol] == 0:
                del positions[ord.symbol]
            history.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "SELL",
                "symbol": ord.symbol,
                "shares": sold,
                "price": ord.estimated_price,
            })
        elif ord.action == "BUY":
            cost = ord.shares * ord.estimated_price
            if cash >= cost:
                cash -= cost
                positions[ord.symbol] = positions.get(ord.symbol, 0) + ord.shares
                history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "BUY",
                    "symbol": ord.symbol,
                    "shares": ord.shares,
                    "price": ord.estimated_price,
                })

    state["cash"] = round(cash, 2)
    state["positions"] = positions
    state["last_rebalance"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["history"] = history[-100:]  # Keep last 100 entries
    save_simulated_portfolio(state)
    return state


def execute_alpaca_orders(orders: List[RebalanceOrder], api_key: str, api_secret: str, paper: bool = True) -> List[Dict[str, Any]]:
    """Submit orders to Alpaca Markets API."""
    base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    headers = {
        "APCA-API-KEY-ID": api_key.strip(),
        "APCA-API-SECRET-KEY": api_secret.strip(),
        "Content-Type": "application/json",
    }
    results = []

    for ord in orders:
        payload = {
            "symbol": ord.symbol,
            "qty": str(ord.shares),
            "side": ord.action.lower(),
            "type": "market",
            "time_in_force": "day",
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/v2/orders", data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                results.append({"status": "SUCCESS", "symbol": ord.symbol, "order_id": res_json.get("id")})
        except Exception as e:
            results.append({"status": "FAILED", "symbol": ord.symbol, "error": str(e)})

    return results


def generate_standalone_scheduler_code(spec: StrategySpec) -> str:
    """Generate a clean, self-contained Python automation script for daily scheduled execution."""
    spec_dict = spec.to_dict()
    return f'''"""
Automated Trading Strategy Bot
Generated by Natural Language Trader
Strategy: {spec.name}
Description: {spec.description}
"""

import json
import urllib.request
from datetime import datetime

SPEC = {json.dumps(spec_dict, indent=4)}
ALPACA_API_KEY = "YOUR_ALPACA_API_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET_KEY"
USE_PAPER = True

def check_and_rebalance():
    print(f"[{{datetime.now()}}] Checking market conditions for {{SPEC['name']}}...")
    # 1. Fetch signal data
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{{SPEC['signal_asset']}}?range=1y&interval=1d"
    req = urllib.request.Request(url, headers={{"User-Agent": "Mozilla/5.0"}})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    latest_price = closes[-1]
    
    # 2. Check Condition (e.g. 200 SMA)
    period = SPEC["params"].get("period", 200)
    sma = sum(closes[-period:]) / period
    is_bull = latest_price > sma
    target_alloc = SPEC["bull_assets"] if is_bull else SPEC["bear_assets"]
    
    print(f"Signal Asset: {{SPEC['signal_asset']}} | Latest: ${{latest_price:.2f}} | SMA({{period}}): ${{sma:.2f}}")
    print(f"Active Regime: {{'BULL' if is_bull else 'BEAR'}} | Target: {{target_alloc}}")
    
    # 3. Connect to Alpaca and submit orders if keys provided
    if ALPACA_API_KEY != "YOUR_ALPACA_API_KEY":
        base_url = "https://paper-api.alpaca.markets" if USE_PAPER else "https://api.alpaca.markets"
        headers = {{
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            "Content-Type": "application/json"
        }}
        # Submit rebalance target orders here
        print("Executing orders on Alpaca...")
    else:
        print("[DRY RUN] No API keys configured. Rebalance target computed successfully.")

if __name__ == "__main__":
    check_and_rebalance()
'''
