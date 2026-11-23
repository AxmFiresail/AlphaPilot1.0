"""Autonomous Stock Trading Engine for Beginners.
Features Multi-Position Diversification, Institutional Breakeven Stop-Locks,
Asymmetric Profit Taking, and Automated Market Scanning.
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from stock_expert import (
    STOCK_WATCHLIST,
    generate_stock_recommendation,
    scan_entire_watchlist,
    fetch_stock_history,
)
from user_manager import get_user_dir, get_user_profile

_STOCK_TRADERS: Dict[str, "StockAutoTrader"] = {}
_STOCK_TRADER_LOCK = threading.Lock()


def get_user_stock_trader(user_id: str) -> "StockAutoTrader":
    """Factory to get or initialize an autonomous stock trader instance for a user."""
    with _STOCK_TRADER_LOCK:
        if user_id not in _STOCK_TRADERS:
            _STOCK_TRADERS[user_id] = StockAutoTrader(user_id)
        return _STOCK_TRADERS[user_id]


class StockAutoTrader:
    """Autonomous Stock Market Trader with strict risk limits for beginners."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.is_running = False
        self.polling_interval_sec = 10
        self.worker_thread: Optional[threading.Thread] = None
        self.max_positions = 5
        self.max_allocation_per_stock = 0.20  # Max 20% of cash into any single stock
        self.load_user_state()

    def get_state_path(self) -> str:
        udir = get_user_dir(self.user_id)
        return os.path.join(udir, "stock_portfolio.json")

    def load_user_state(self):
        spath = self.get_state_path()
        profile = get_user_profile(self.user_id)
        default_bal = float(profile.get("starting_balance", 10000.0))

        if os.path.exists(spath):
            try:
                with open(spath, "r") as f:
                    state = json.load(f)
                    self.cash = float(state.get("cash", default_bal))
                    self.positions = state.get("positions", {})
                    self.trade_history = state.get("trade_history", [])
                    return
            except Exception as e:
                print(f"Error reading stock portfolio for {self.user_id}: {e}")

        # Initialize clean portfolio
        self.cash = default_bal
        self.positions = {}
        self.trade_history = []
        self.save_user_state()

    def save_user_state(self):
        spath = self.get_state_path()
        state = {
            "user_id": self.user_id,
            "cash": round(self.cash, 2),
            "positions": self.positions,
            "trade_history": self.trade_history,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            with open(spath, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Failed to save stock portfolio: {e}")

    def reset_portfolio(self, starting_balance: float = 10000.0):
        """Reset the simulated paper trading account."""
        self.cash = starting_balance
        self.positions = {}
        self.trade_history = []
        self.save_user_state()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Calculates live equity, total unrealized PnL, and holdings details."""
        total_holdings_value = 0.0
        total_unrealized_pnl = 0.0

        updated_positions = {}
        for ticker, pos in list(self.positions.items()):
            rec = generate_stock_recommendation(ticker)
            current_p = rec["current_price"] if rec["current_price"] > 0 else pos["entry_price"]
            entry_p = pos["entry_price"]
            shares = pos["shares"]

            pos_value = round(shares * current_p, 2)
            pos_cost = round(shares * entry_p, 2)
            pnl_dollars = round(pos_value - pos_cost, 2)
            pnl_pct = round(((current_p - entry_p) / entry_p) * 100, 2)

            sl_p = pos.get("sl_price", entry_p * 0.97)
            tp_p = pos.get("tp_price", entry_p * 1.065)

            # Location calculation (where are we between SL and TP)
            total_range = max(0.01, tp_p - sl_p)
            progress = (current_p - sl_p) / total_range
            location_pct = max(0.0, min(100.0, progress * 100.0))

            updated_positions[ticker] = {
                **pos,
                "current_price": current_p,
                "current_value": pos_value,
                "pnl_dollars": pnl_dollars,
                "pnl_pct": pnl_pct,
                "location_pct": round(location_pct, 1),
            }

            total_holdings_value += pos_value
            total_unrealized_pnl += pnl_dollars

        self.positions = updated_positions
        total_equity = round(self.cash + total_holdings_value, 2)

        return {
            "cash": round(self.cash, 2),
            "holdings_value": round(total_holdings_value, 2),
            "total_equity": total_equity,
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "positions": self.positions,
            "open_count": len(self.positions),
            "trade_history": self.trade_history,
            "is_running": self.is_running,
        }

    def execute_buy(self, ticker: str, shares: Optional[int] = None) -> Tuple[bool, str]:
        """Executes a simulated buy order with risk-controlled sizing."""
        ticker = ticker.strip().upper()
        if ticker in self.positions:
            return False, f"You already hold {ticker}. Diversification rule: max 1 position per stock."

        if len(self.positions) >= self.max_positions:
            return False, f"Maximum positions reached ({self.max_positions}). Close a position before buying more."

        rec = generate_stock_recommendation(ticker)
        current_price = rec["current_price"]
        if current_price <= 0:
            return False, f"Could not get live market price for {ticker}."

        if shares is None:
            # Safe position sizing: Allocate max 20% of total equity
            summary = self.get_portfolio_summary()
            target_dollar_allocation = summary["total_equity"] * self.max_allocation_per_stock
            # Cannot exceed available cash
            target_dollar_allocation = min(target_dollar_allocation, self.cash)
            shares = int(target_dollar_allocation // current_price)

        if shares <= 0:
            return False, f"Not enough cash to buy 1 full share of {ticker} (${current_price:.2f})."

        total_cost = round(shares * current_price, 2)
        if total_cost > self.cash:
            return False, f"Insufficient cash (${self.cash:.2f}) for {shares} shares (${total_cost:.2f})."

        self.cash -= total_cost
        sl_price = rec["stop_loss_price"]
        tp_price = rec["take_profit_price"]

        self.positions[ticker] = {
            "ticker": ticker,
            "shares": shares,
            "entry_price": current_price,
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sl_price": sl_price,
            "tp_price": tp_price,
            "is_breakeven": False,
        }

        self.trade_history.append({
            "action": "BUY",
            "ticker": ticker,
            "shares": shares,
            "price": current_price,
            "total": total_cost,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "Signal Entry",
        })

        self.save_user_state()
        return True, f"Bought {shares} shares of {ticker} at ${current_price:.2f} (Total: ${total_cost:.2f})"

    def execute_sell(self, ticker: str, reason: str = "Manual Close") -> Tuple[bool, str]:
        """Sells an existing holding and credits proceeds back to cash balance."""
        ticker = ticker.strip().upper()
        if ticker not in self.positions:
            return False, f"No open holding found for {ticker}."

        pos = self.positions.pop(ticker)
        rec = generate_stock_recommendation(ticker)
        exit_price = rec["current_price"] if rec["current_price"] > 0 else pos["entry_price"]
        shares = pos["shares"]
        entry_price = pos["entry_price"]

        gross_revenue = round(shares * exit_price, 2)
        invested = round(shares * entry_price, 2)
        pnl = round(gross_revenue - invested, 2)
        pnl_pct = round(((exit_price - entry_price) / entry_price) * 100, 2)

        self.cash += gross_revenue

        self.trade_history.append({
            "action": "SELL",
            "ticker": ticker,
            "shares": shares,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "revenue": gross_revenue,
            "reason": reason,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.save_user_state()
        sign = "+" if pnl >= 0 else ""
        return True, f"Sold {shares} shares of {ticker} at ${exit_price:.2f} | PnL: {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%) [{reason}]"

    def tick_cycle(self) -> List[str]:
        """
        Runs one evaluation cycle:
        1. Checks active holdings for Stop Loss or Take Profit.
        2. Adjusts stops to Breakeven when trade is in profit (Profit-Lock).
        3. If Autopilot is on, scans market for high-conviction BUY setups and auto-trades.
        """
        logs = []

        # 1. Manage Open Holdings
        for ticker, pos in list(self.positions.items()):
            rec = generate_stock_recommendation(ticker)
            current_p = rec["current_price"]
            if current_p <= 0:
                continue

            entry_p = pos["entry_price"]
            sl_p = pos["sl_price"]
            tp_p = pos["tp_price"]

            # Check Stop Loss Trigger
            if current_p <= sl_p:
                msg = f"Stop Loss triggered for {ticker} at ${current_p:.2f} (Target was ${sl_p:.2f})"
                self.execute_sell(ticker, reason="Stop Loss Protected")
                logs.append(f"🛑 {msg}")
                continue

            # Check Take Profit Trigger
            if current_p >= tp_p:
                msg = f"Take Profit target achieved for {ticker} at ${current_p:.2f} (Target was ${tp_p:.2f})"
                self.execute_sell(ticker, reason="Take Profit Target Hit")
                logs.append(f"🎯 {msg}")
                continue

            # Institutional Breakeven Lock: Once position is up +2.5%, lock stop at entry!
            if current_p >= entry_p * 1.025 and not pos.get("is_breakeven", False):
                pos["sl_price"] = entry_p
                pos["is_breakeven"] = True
                self.positions[ticker] = pos
                logs.append(f"🛡️ Breakeven Stop Locked on {ticker}! Trade is now 100% Risk-Free.")
                self.save_user_state()

        # 2. Autonomous Opportunity Scanner & Entry
        if self.is_running and len(self.positions) < self.max_positions and self.cash > 200:
            scanned = scan_entire_watchlist()
            for opp in scanned:
                opp_ticker = opp["ticker"]
                if opp_ticker not in self.positions and opp["score"] >= 3:
                    success, buy_msg = self.execute_buy(opp_ticker)
                    if success:
                        logs.append(f"🤖 Autopilot Triggered: {buy_msg}")
                        break

        return logs

    def start(self):
        """Starts background monitoring loop."""
        if self.is_running:
            return
        self.is_running = True

        def _run():
            while self.is_running:
                try:
                    self.tick_cycle()
                except Exception as e:
                    print(f"Error in stock autopilot thread: {e}")
                time.sleep(self.polling_interval_sec)

        self.worker_thread = threading.Thread(target=_run, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stops background monitoring loop."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread = None
