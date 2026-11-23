"""Forex Pairs and Pip Calculation Utilities.
Supports major, minor, and cross currency pairs with accurate pip sizes, spreads, and margin calculations.
"""

from typing import Dict, Any, Tuple

# Supported Forex Pairs and Metadata
FOREX_PAIRS: Dict[str, Dict[str, Any]] = {
    "EUR/USD": {
        "symbol": "EURUSD=X",
        "base": "EUR",
        "quote": "USD",
        "pip_size": 0.0001,
        "spread_pips": 1.2,
        "description": "Euro vs US Dollar",
    },
    "GBP/USD": {
        "symbol": "GBPUSD=X",
        "base": "GBP",
        "quote": "USD",
        "pip_size": 0.0001,
        "spread_pips": 1.5,
        "description": "British Pound vs US Dollar",
    },
    "USD/JPY": {
        "symbol": "USDJPY=X",
        "base": "USD",
        "quote": "JPY",
        "pip_size": 0.01,
        "spread_pips": 1.3,
        "description": "US Dollar vs Japanese Yen",
    },
    "USD/CHF": {
        "symbol": "USDCHF=X",
        "base": "USD",
        "quote": "CHF",
        "pip_size": 0.0001,
        "spread_pips": 1.6,
        "description": "US Dollar vs Swiss Franc",
    },
    "AUD/USD": {
        "symbol": "AUDUSD=X",
        "base": "AUD",
        "quote": "USD",
        "pip_size": 0.0001,
        "spread_pips": 1.4,
        "description": "Australian Dollar vs US Dollar",
    },
    "USD/CAD": {
        "symbol": "USDCAD=X",
        "base": "USD",
        "quote": "CAD",
        "pip_size": 0.0001,
        "spread_pips": 1.8,
        "description": "US Dollar vs Canadian Dollar",
    },
    "NZD/USD": {
        "symbol": "NZDUSD=X",
        "base": "NZD",
        "quote": "USD",
        "pip_size": 0.0001,
        "spread_pips": 2.0,
        "description": "New Zealand Dollar vs US Dollar",
    },
    "EUR/GBP": {
        "symbol": "EURGBP=X",
        "base": "EUR",
        "quote": "GBP",
        "pip_size": 0.0001,
        "spread_pips": 1.8,
        "description": "Euro vs British Pound",
    },
    "EUR/JPY": {
        "symbol": "EURJPY=X",
        "base": "EUR",
        "quote": "JPY",
        "pip_size": 0.01,
        "spread_pips": 1.8,
        "description": "Euro vs Japanese Yen",
    },
    "GBP/JPY": {
        "symbol": "GBPJPY=X",
        "base": "GBP",
        "quote": "JPY",
        "pip_size": 0.01,
        "spread_pips": 2.4,
        "description": "British Pound vs Japanese Yen",
    },
}

# Aliases for natural language mapping
FOREX_ALIASES = {
    "eurusd": "EUR/USD",
    "eur/usd": "EUR/USD",
    "euro": "EUR/USD",
    "gbpusd": "GBP/USD",
    "gbp/usd": "GBP/USD",
    "cable": "GBP/USD",
    "pound": "GBP/USD",
    "usdjpy": "USD/JPY",
    "usd/jpy": "USD/JPY",
    "yen": "USD/JPY",
    "ninja": "USD/JPY",
    "usdchf": "USD/CHF",
    "usd/chf": "USD/CHF",
    "swissie": "USD/CHF",
    "audusd": "AUD/USD",
    "aud/usd": "AUD/USD",
    "aussie": "AUD/USD",
    "usdcad": "USD/CAD",
    "usd/cad": "USD/CAD",
    "loonie": "USD/CAD",
    "nzdusd": "NZD/USD",
    "nzd/usd": "NZD/USD",
    "kiwi": "NZD/USD",
    "eurgbp": "EUR/GBP",
    "eur/gbp": "EUR/GBP",
    "eurjpy": "EUR/JPY",
    "eur/jpy": "EUR/JPY",
    "gbpjpy": "GBP/JPY",
    "gbp/jpy": "GBP/JPY",
    "geppy": "GBP/JPY",
}


def normalize_pair(text: str) -> str:
    """Resolve plain text pair name to standard format (e.g. 'eur/usd' -> 'EUR/USD')."""
    cleaned = text.strip().lower().replace(" ", "").replace("-", "")
    if cleaned in FOREX_ALIASES:
        return FOREX_ALIASES[cleaned]
    # Check uppercase slash format
    upper = text.strip().upper()
    if upper in FOREX_PAIRS:
        return upper
    return "EUR/USD"  # default standard pair


def get_pair_symbol(pair: str) -> str:
    norm = normalize_pair(pair)
    return FOREX_PAIRS.get(norm, FOREX_PAIRS["EUR/USD"])["symbol"]


def get_pip_size(pair: str) -> float:
    norm = normalize_pair(pair)
    return FOREX_PAIRS.get(norm, FOREX_PAIRS["EUR/USD"])["pip_size"]


def calculate_pips(pair: str, entry_price: float, exit_price: float, direction: str) -> float:
    """Calculate pips gained or lost based on direction ('BUY'/'LONG' vs 'SELL'/'SHORT')."""
    pip_size = get_pip_size(pair)
    diff = (exit_price - entry_price) if direction.upper() in ["BUY", "LONG"] else (entry_price - exit_price)
    return round(diff / pip_size, 1)


def calculate_forex_pnl(
    pair: str,
    entry_price: float,
    exit_price: float,
    direction: str,
    lot_size: float = 0.1,  # 0.1 = Mini Lot = 10,000 units
) -> Tuple[float, float]:
    """Calculate PnL in both Pips and USD dollars.
    Returns: (pips, dollar_pnl)
    """
    pip_size = get_pip_size(pair)
    pips = calculate_pips(pair, entry_price, exit_price, direction)
    units = lot_size * 100000.0  # 1 standard lot = 100,000 base units

    norm = normalize_pair(pair)
    meta = FOREX_PAIRS[norm]

    # If quote currency is USD (EUR/USD, GBP/USD, etc.):
    # 1 pip = pip_size * units = 0.0001 * 10,000 = $1.00 for 0.1 lot
    if meta["quote"] == "USD":
        dollar_pnl = pips * (pip_size * units)
    elif meta["quote"] == "JPY":
        # USD/JPY: pip value = (0.01 / exit_price) * units
        pip_val_usd = (0.01 / (exit_price + 1e-9)) * units
        dollar_pnl = pips * pip_val_usd
    else:
        # Approximate for other quotes
        dollar_pnl = pips * (pip_size * units)

    return round(pips, 1), round(dollar_pnl, 2)
