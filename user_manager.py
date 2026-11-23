"""User Account and Profile Manager.
Provides isolated multi-tenant storage for custom user profiles, risk parameters,
personal strategy libraries, broker credentials, and live account states.
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from forex_parser import ForexStrategySpec, parse_forex_strategy

USERS_DIR = os.path.join(os.path.dirname(__file__), "users")
os.makedirs(USERS_DIR, exist_ok=True)


def sanitize_user_id(name: str) -> str:
    """Convert name to safe directory name."""
    s = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip().lower())
    return s if s else "trader_default"


def get_user_dir(user_id: str) -> str:
    path = os.path.join(USERS_DIR, sanitize_user_id(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def list_users() -> List[Dict[str, Any]]:
    """List all registered users."""
    users = []
    if not os.path.exists(USERS_DIR):
        return [create_default_user("default_trader", "Default Trader")]

    for entry in os.scandir(USERS_DIR):
        if entry.is_dir():
            prof_file = os.path.join(entry.path, "profile.json")
            if os.path.exists(prof_file):
                try:
                    with open(prof_file, "r") as f:
                        data = json.load(f)
                        users.append(data)
                except Exception:
                    pass

    if not users:
        users.append(create_default_user("default_trader", "Default Trader"))

    return users


def create_default_user(user_id: str, display_name: str, starting_balance: float = 10000.0) -> Dict[str, Any]:
    """Create a new user with default custom settings and sample strategy."""
    uid = sanitize_user_id(user_id)
    udir = get_user_dir(uid)

    profile = {
        "user_id": uid,
        "display_name": display_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account_currency": "USD",
        "starting_balance": starting_balance,
        "risk_limits": {
            "max_lot_size": 0.5,
            "default_lot_size": 0.1,
            "max_daily_drawdown_pct": 5.0,
            "default_sl_pips": 35.0,
            "default_tp_pips": 70.0,
            "enforce_circuit_breaker": True,
        },
        "broker": {
            "mode": "simulated",  # 'simulated' or 'oanda'
            "oanda_token": "",
            "oanda_account_id": "",
            "oanda_env": "practice",
        },
    }

    # Save profile.json
    with open(os.path.join(udir, "profile.json"), "w") as f:
        json.dump(profile, f, indent=2)

    # Initial sample strategies
    sample_strategies = [
        {
            "id": "strat_1",
            "name": "EUR/USD Trend Crossover",
            "prompt": "Buy EUR/USD when 20 EMA crosses above 50 EMA, go short when it crosses below, with 30 pip stop loss and 60 pip take profit",
            "pair": "EUR/USD",
            "lot_size": 0.1,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": "Core trend-following setup on 1-hour candles.",
        },
        {
            "id": "strat_2",
            "name": "GBP/USD RSI Reversal",
            "prompt": "Go long GBP/USD when RSI 14 drops below 30, go short when RSI is above 70, with 40 pip stop loss and 80 pip take profit",
            "pair": "GBP/USD",
            "lot_size": 0.1,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": "Mean-reversion scalp on oversold/overbought extremes.",
        },
    ]

    with open(os.path.join(udir, "strategies.json"), "w") as f:
        json.dump(sample_strategies, f, indent=2)

    # Initial state
    state = {
        "user_id": uid,
        "balance": starting_balance,
        "open_position": None,
        "trade_history": [],
        "logs": [],
        "strategy": sample_strategies[0],
        "is_running": False,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(udir, "autopilot_state.json"), "w") as f:
        json.dump(state, f, indent=2)

    return profile


def get_user_profile(user_id: str) -> Dict[str, Any]:
    uid = sanitize_user_id(user_id)
    prof_file = os.path.join(get_user_dir(uid), "profile.json")
    if os.path.exists(prof_file):
        try:
            with open(prof_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return create_default_user(uid, uid.replace("_", " ").title())


def save_user_profile(user_id: str, profile_data: Dict[str, Any]):
    uid = sanitize_user_id(user_id)
    prof_file = os.path.join(get_user_dir(uid), "profile.json")
    with open(prof_file, "w") as f:
        json.dump(profile_data, f, indent=2)


def get_user_strategies(user_id: str) -> List[Dict[str, Any]]:
    uid = sanitize_user_id(user_id)
    strat_file = os.path.join(get_user_dir(uid), "strategies.json")
    if os.path.exists(strat_file):
        try:
            with open(strat_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_user_strategy(user_id: str, name: str, prompt: str, notes: str = "") -> Dict[str, Any]:
    uid = sanitize_user_id(user_id)
    strategies = get_user_strategies(uid)
    strat_id = f"strat_{int(datetime.now().timestamp())}"
    spec = parse_forex_strategy(prompt)

    new_strat = {
        "id": strat_id,
        "name": name.strip() or spec.name,
        "prompt": prompt.strip(),
        "pair": spec.pair,
        "lot_size": spec.lot_size,
        "timeframe": spec.timeframe,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": notes.strip(),
    }
    strategies.append(new_strat)

    strat_file = os.path.join(get_user_dir(uid), "strategies.json")
    with open(strat_file, "w") as f:
        json.dump(strategies, f, indent=2)

    return new_strat


def delete_user_strategy(user_id: str, strategy_id: str) -> bool:
    uid = sanitize_user_id(user_id)
    strategies = get_user_strategies(uid)
    filtered = [s for s in strategies if s["id"] != strategy_id]
    if len(filtered) != len(strategies):
        strat_file = os.path.join(get_user_dir(uid), "strategies.json")
        with open(strat_file, "w") as f:
            json.dump(filtered, f, indent=2)
        return True
    return False


def get_user_state(user_id: str) -> Dict[str, Any]:
    uid = sanitize_user_id(user_id)
    state_file = os.path.join(get_user_dir(uid), "autopilot_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Create default state
    prof = get_user_profile(uid)
    return {
        "user_id": uid,
        "balance": prof.get("starting_balance", 10000.0),
        "open_position": None,
        "trade_history": [],
        "logs": [],
        "is_running": False,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_user_state(user_id: str, state_data: Dict[str, Any]):
    uid = sanitize_user_id(user_id)
    state_file = os.path.join(get_user_dir(uid), "autopilot_state.json")
    with open(state_file, "w") as f:
        json.dump(state_data, f, indent=2)
