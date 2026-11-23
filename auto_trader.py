"""Autonomous Forex Trading Engine with Institutional Profit Guardian.
Features Breakeven Stops, Dynamic Profit-Lock Trailing, Signal Noise Protection,
and comprehensive Margin/Equity Location tracking per user.
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from forex_pairs import FOREX_PAIRS, normalize_pair, get_pip_size, calculate_forex_pnl
from forex_data import fetch_live_forex_quote, fetch_forex_history
from forex_parser import ForexStrategySpec, parse_forex_strategy
from forex_expert import calculate_technical_indicators, generate_buy_sell_signal
from user_manager import (
    get_user_profile,
    get_user_state,
    save_user_state,
    save_user_profile,
)

_TRADERS: Dict[str, "ForexAutoTrader"] = {}
_TRADER_LOCK = threading.Lock()


def get_user_trader(user_id: str) -> "ForexAutoTrader":
    """Factory to get or initialize an autonomous trader instance for a user."""
    with _TRADER_LOCK:
        if user_id not in _TRADERS:
            _TRADERS[user_id] = ForexAutoTrader(user_id)
        return _TRADERS[user_id]


class ForexAutoTrader:
    """Autonomous trading engine with institutional Forex secrets & profit lock."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.is_running = False
        self.polling_interval_sec = 8
        self.worker_thread: Optional[threading.Thread] = None
        self.strategy: Optional[ForexStrategySpec] = None

        # Profit Guardian Controls
        self.enable_breakeven_lock = True
        self.enable_trailing_stop = True
        self.exit_only_in_profit = True  # Secret: Ignore premature chop reversals unless in profit

        self.load_user_state()

    def load_user_state(self):
        state = get_user_state(self.user_id)
        profile = get_user_profile(self.user_id)

        self.balance = float(state.get("balance", profile.get("starting_balance", 10000.0)))
        self.open_position = state.get("open_position", None)
        self.trade_history = state.get("trade_history", [])
        self.logs = state.get("logs", [])

        strat_data = state.get("strategy")
        if strat_data and isinstance(strat_data, dict):
            prompt = strat_data.get("prompt") or strat_data.get("description", "")
            if prompt:
                self.strategy = parse_forex_strategy(prompt)

        if not self.strategy:
            self.strategy = parse_forex_strategy("Buy EUR/USD when 20 EMA crosses above 50 EMA, go short when it crosses below, 30 pip stop loss, 60 pip take profit")

    def save_state(self):
        data = {
            "user_id": self.user_id,
            "balance": round(self.balance, 2),
            "open_position": self.open_position,
            "trade_history": self.trade_history[-200:],
            "logs": self.logs[-250:],
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "is_running": self.is_running,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_user_state(self.user_id, data)

    def log(self, message: str, level: str = "INFO"):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
        self.logs.append(entry)
        if len(self.logs) > 250:
            self.logs.pop(0)

    def set_strategy(self, spec: ForexStrategySpec):
        self.strategy = spec
        self.log(f"Strategy updated for user [{self.user_id}]: {spec.name} ({spec.human_summary})")
        self.save_state()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        self.log(f"🟢 Institutional Autopilot ENGAGED for [{self.user_id}]. Profit Guardian Active.")
        self.save_state()

    def stop(self):
        self.is_running = False
        self.log(f"🔴 Autopilot DISENGAGED for [{self.user_id}]. System on standby.")
        self.save_state()

    def _run_loop(self):
        while self.is_running:
            try:
                self.tick_cycle()
            except Exception as e:
                self.log(f"Scan cycle notice: {str(e)}", level="ERROR")

            for _ in range(self.polling_interval_sec):
                if not self.is_running:
                    break
                time.sleep(1)

    def tick_cycle(self):
        if not self.strategy:
            return

        profile = get_user_profile(self.user_id)
        risk_limits = profile.get("risk_limits", {})
        pair = normalize_pair(self.strategy.pair)
        pip_size = get_pip_size(pair)

        # 1. Fetch live quote
        quote = fetch_live_forex_quote(pair)
        bid = quote["bid"]
        ask = quote["ask"]
        mid = quote["mid_price"]

        # 2. Manage Active Position (Trailing Stops, Breakeven Locks, Target Hits)
        if self.open_position is not None:
            pos = self.open_position
            p_dir = pos["direction"]
            entry_p = pos["entry_price"]
            sl_p = pos.get("sl_price")
            tp_p = pos.get("tp_price")

            current_exit = bid if p_dir == "BUY" else ask
            pips, dollar_pnl = calculate_forex_pnl(pair, entry_p, current_exit, p_dir, pos["lot_size"])
            pos["floating_pips"] = pips
            pos["floating_pnl"] = dollar_pnl
            pos["current_price"] = current_exit

            # Highest Pips Peak Tracking
            if "peak_pips" not in pos:
                pos["peak_pips"] = pips
            else:
                pos["peak_pips"] = max(pos["peak_pips"], pips)

            # FOREX SECRET 1: Automatic Breakeven Lock at +15 pips
            if self.enable_breakeven_lock and pips >= 15.0 and not pos.get("is_breakeven"):
                be_price = round(entry_p + (1.5 * pip_size) if p_dir == "BUY" else entry_p - (1.5 * pip_size), 5)
                pos["sl_price"] = be_price
                pos["is_breakeven"] = True
                self.log(f"🛡️ PROFIT GUARDIAN: +{pips:.1f} pips gained! Stop Loss moved to Breakeven (+1.5 pips @ {be_price}). Risk is now ZERO!")

            # FOREX SECRET 2: Dynamic Trailing Stop as Profit Expands
            if self.enable_trailing_stop and pips >= 25.0:
                trail_distance = 18.0 * pip_size
                if p_dir == "BUY":
                    new_sl = round(current_exit - trail_distance, 5)
                    if new_sl > pos["sl_price"]:
                        pos["sl_price"] = new_sl
                        self.log(f"📈 TRAILING STOP: Trailing SL up to {new_sl} to lock in profit ({pips:.1f} pips running).")
                elif p_dir == "SELL":
                    new_sl = round(current_exit + trail_distance, 5)
                    if new_sl < pos["sl_price"]:
                        pos["sl_price"] = new_sl
                        self.log(f"📉 TRAILING STOP: Trailing SL down to {new_sl} to lock in profit ({pips:.1f} pips running).")

            # Check SL / TP
            triggered_exit = False
            exit_reason = ""
            exit_p = current_exit

            if p_dir == "BUY":
                if sl_p and bid <= sl_p:
                    triggered_exit = True
                    exit_reason = "Trailing / Breakeven Stop Hit" if pos.get("is_breakeven") else "Stop Loss Hit"
                    exit_p = sl_p
                elif tp_p and bid >= tp_p:
                    triggered_exit = True
                    exit_reason = "Take Profit Hit 🎯"
                    exit_p = tp_p
            elif p_dir == "SELL":
                if sl_p and ask >= sl_p:
                    triggered_exit = True
                    exit_reason = "Trailing / Breakeven Stop Hit" if pos.get("is_breakeven") else "Stop Loss Hit"
                    exit_p = sl_p
                elif tp_p and ask <= tp_p:
                    triggered_exit = True
                    exit_reason = "Take Profit Hit 🎯"
                    exit_p = tp_p

            if triggered_exit:
                self._close_position(exit_p, exit_reason)
                self.save_state()
                return

        # 3. Check User Circuit Breaker
        if risk_limits.get("enforce_circuit_breaker", True):
            start_bal = profile.get("starting_balance", 10000.0)
            max_dd_pct = risk_limits.get("max_daily_drawdown_pct", 5.0)
            current_loss_pct = ((start_bal - self.balance) / start_bal) * 100.0
            if current_loss_pct >= max_dd_pct:
                self.log(f"⚠️ CIRCUIT BREAKER: Account drawdown ({current_loss_pct:.1f}%) reached user limit ({max_dd_pct}%). Pausing autopilot.", level="WARN")
                self.stop()
                return

        # 4. Generate Institutional Consensus Signal
        sig = generate_buy_sell_signal(pair)
        target_signal = 1 if sig["direction"] == "BUY" else (-1 if sig["direction"] == "SELL" else 0)

        # 5. Position Management & Signal Execution
        if self.open_position is not None:
            curr_dir = self.open_position["direction"]
            curr_pips = self.open_position.get("floating_pips", 0.0)

            # FOREX SECRET 3: Don't flip or panic exit on chop unless in profit or hard stop hit!
            if (curr_dir == "BUY" and target_signal == -1) or (curr_dir == "SELL" and target_signal == 1):
                if not self.exit_only_in_profit or curr_pips >= 5.0:
                    self.log(f"⚡ Institutional Reversal Confirmed: Closing {curr_dir} in profit (+{curr_pips:.1f} pips) and opening {sig['direction']}.")
                    current_exit = bid if curr_dir == "BUY" else ask
                    self._close_position(current_exit, "Signal Reversal In Profit")
                    new_dir = "BUY" if target_signal == 1 else "SELL"
                    self._open_position(pair, new_dir, ask if new_dir == "BUY" else bid, risk_limits, sig)
                else:
                    self.log(f"🛡️ PATIENCE RULE: Counter signal detected, but holding through noise until profit or SL is reached.")
        else:
            if target_signal != 0:
                new_dir = "BUY" if target_signal == 1 else "SELL"
                self._open_position(pair, new_dir, ask if new_dir == "BUY" else bid, risk_limits, sig)
            else:
                self.log(f"Market Scan {pair} Mid: {mid:.5f} | Consensus: {sig['verdict']} ({sig['score']:+d}) | Neutral Zone")

        self.save_state()

    def _open_position(self, pair: str, direction: str, fill_price: float, risk_limits: Dict[str, Any], sig: Optional[Dict] = None):
        pip_size = get_pip_size(pair)

        requested_lots = self.strategy.lot_size
        max_lot = risk_limits.get("max_lot_size", 0.5)
        effective_lot = min(requested_lots, max_lot)

        if effective_lot < requested_lots:
            self.log(f"🛡️ Risk Rule: Requested lot size {requested_lots} capped to user max {effective_lot} lots.")

        # Use institutional dynamic ATR stop loss and take profit if available
        if sig and "recommended_sl_pips" in sig:
            sl_pips = sig["recommended_sl_pips"]
            tp_pips = sig["recommended_tp1_pips"]
        else:
            sl_pips = self.strategy.stop_loss_pips or risk_limits.get("default_sl_pips", 35.0)
            tp_pips = self.strategy.take_profit_pips or risk_limits.get("default_tp_pips", 70.0)

        sl_dist = sl_pips * pip_size
        tp_dist = tp_pips * pip_size

        sl_price = round((fill_price - sl_dist) if direction == "BUY" else (fill_price + sl_dist), 5)
        tp_price = round((fill_price + tp_dist) if direction == "BUY" else (fill_price - tp_dist), 5)

        self.open_position = {
            "pair": pair,
            "direction": direction,
            "lot_size": effective_lot,
            "entry_price": round(fill_price, 5),
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sl_price": sl_price,
            "tp_price": tp_price,
            "initial_sl_pips": sl_pips,
            "initial_tp_pips": tp_pips,
            "floating_pips": 0.0,
            "floating_pnl": 0.0,
            "current_price": round(fill_price, 5),
            "is_breakeven": False,
        }

        self.log(f"🚀 AUTO TRADE EXECUTED [{self.user_id}]: {direction} {effective_lot}L {pair} @ {fill_price:.5f} | SL: {sl_price} ({sl_pips} pips) | TP: {tp_price} ({tp_pips} pips)")

    def _close_position(self, exit_price: float, reason: str):
        if not self.open_position:
            return

        pos = self.open_position
        pair = pos["pair"]
        pips, dollar_pnl = calculate_forex_pnl(pair, pos["entry_price"], exit_price, pos["direction"], pos["lot_size"])

        self.balance += dollar_pnl
        trade_record = {
            "entry_time": pos["entry_time"],
            "exit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pair": pair,
            "direction": pos["direction"],
            "lot_size": pos["lot_size"],
            "entry_price": pos["entry_price"],
            "exit_price": round(exit_price, 5),
            "reason": reason,
            "pips": round(pips, 1),
            "pnl_usd": round(dollar_pnl, 2),
            "balance_after": round(self.balance, 2),
        }
        self.trade_history.append(trade_record)
        sign = "+" if dollar_pnl >= 0 else ""
        icon = "🎉" if dollar_pnl >= 0 else "🛑"
        self.log(f"{icon} TRADE CLOSED ({reason}): {pos['direction']} {pair} @ {exit_price:.5f} | Pips: {pips:+.1f} ({sign}${dollar_pnl:.2f}) | New Balance: ${self.balance:,.2f}")
        self.open_position = None

    def get_summary(self) -> Dict[str, Any]:
        equity = self.balance
        floating_pnl = 0.0
        floating_pips = 0.0
        margin_used = 0.0

        if self.open_position:
            floating_pnl = self.open_position.get("floating_pnl", 0.0)
            floating_pips = self.open_position.get("floating_pips", 0.0)
            equity += floating_pnl
            # 30:1 leverage margin calculation (3.33% of notional)
            units = self.open_position["lot_size"] * 100000.0
            margin_used = (units * self.open_position["entry_price"]) / 30.0

        free_margin = max(equity - margin_used, 0.0)
        margin_level = (equity / (margin_used + 1e-9)) * 100.0 if margin_used > 0 else 9999.0

        # Loss/Gain location calculation (Progress between SL and TP)
        location_pct = 50.0  # 50% = at entry
        if self.open_position and self.open_position.get("sl_price") and self.open_position.get("tp_price"):
            sl = self.open_position["sl_price"]
            tp = self.open_position["tp_price"]
            curr = self.open_position.get("current_price", self.open_position["entry_price"])
            p_dir = self.open_position["direction"]

            if p_dir == "BUY":
                total_span = (tp - sl) if tp != sl else 1.0
                curr_span = curr - sl
                location_pct = max(0.0, min(100.0, (curr_span / total_span) * 100.0))
            else:
                total_span = (sl - tp) if sl != tp else 1.0
                curr_span = sl - curr
                location_pct = max(0.0, min(100.0, (curr_span / total_span) * 100.0))

        return {
            "user_id": self.user_id,
            "is_running": self.is_running,
            "balance": round(self.balance, 2),
            "equity": round(equity, 2),
            "floating_pnl": round(floating_pnl, 2),
            "floating_pips": round(floating_pips, 1),
            "margin_used": round(margin_used, 2),
            "free_margin": round(free_margin, 2),
            "margin_level_pct": round(margin_level, 1),
            "location_pct": round(location_pct, 1),
            "open_position": self.open_position,
            "total_trades": len(self.trade_history),
            "recent_logs": self.logs[-20:],
            "recent_trades": self.trade_history[-15:],
        }
