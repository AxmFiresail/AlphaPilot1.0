"""Institutional Forex Expert Engine.
Calculates professional technical indicators, Currency Strength Matrix (CSM),
multi-indicator consensus Buy/Sell signals, and dynamic ATR profit/loss levels.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from forex_pairs import FOREX_PAIRS, normalize_pair, get_pip_size
from forex_data import fetch_forex_history, fetch_live_forex_quote


def calculate_technical_indicators(df: pd.DataFrame, pip_size: float = 0.0001) -> pd.DataFrame:
    """Compute institutional indicators: EMA 20/50/200, RSI, MACD, Bollinger Bands, ATR."""
    data = df.copy()
    close = data["Close"]
    high = data["High"]
    low = data["Low"]

    # EMAs (Trend Hierarchy)
    data["EMA_20"] = close.ewm(span=20, adjust=False).mean()
    data["EMA_50"] = close.ewm(span=50, adjust=False).mean()
    data["EMA_200"] = close.ewm(span=min(200, len(close)), adjust=False).mean()

    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    data["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    data["MACD"] = ema12 - ema26
    data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACD_Hist"] = data["MACD"] - data["MACD_Signal"]

    # Bollinger Bands (20, 2.0 std)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    data["BB_Upper"] = bb_mid + (2.0 * bb_std)
    data["BB_Lower"] = bb_mid - (2.0 * bb_std)
    data["BB_Mid"] = bb_mid

    # ATR (14) - Average True Range in pips
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    data["ATR_Price"] = atr
    data["ATR_Pips"] = atr / pip_size

    return data


def get_current_forex_session() -> Dict[str, Any]:
    """Detect active global Forex trading session (UTC)."""
    utc_hour = datetime.now(timezone.utc).hour

    # Session hours (UTC)
    # Sydney: 21:00 - 06:00
    # Tokyo (Asian): 00:00 - 09:00
    # London (European): 07:00 - 16:00
    # New York (American): 12:00 - 21:00
    # Golden Overlap (London + NY): 12:00 - 16:00

    if 12 <= utc_hour < 16:
        name = "London / New York Overlap (Golden Hours)"
        liquidity = "PEAK (Highest Profitability & Tight Spreads)"
        color = "#10B981"
    elif 7 <= utc_hour < 16:
        name = "London Session"
        liquidity = "HIGH (Strong Trend Continuation)"
        color = "#3B82F6"
    elif 12 <= utc_hour < 21:
        name = "New York Session"
        liquidity = "HIGH (High Momentum & News Moves)"
        color = "#6366F1"
    elif 0 <= utc_hour < 9:
        name = "Tokyo / Asian Session"
        liquidity = "MODERATE (Range-bound / Consolidation)"
        color = "#F59E0B"
    else:
        name = "Pacific / Sydney Session"
        liquidity = "LOW (Quiet Markets)"
        color = "#64748B"

    return {"session": name, "liquidity": liquidity, "color": color, "utc_time": datetime.now(timezone.utc).strftime("%H:%M UTC")}


def calculate_currency_strength() -> Dict[str, float]:
    """Institutional Currency Strength Meter (CSM).
    Computes normalized relative strength (-100 to +100) for major world currencies.
    """
    pairs_to_check = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "EUR/GBP", "EUR/JPY", "GBP/JPY"]
    strength = {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "JPY": 0.0, "AUD": 0.0, "CAD": 0.0, "CHF": 0.0}

    for p in pairs_to_check:
        try:
            q = fetch_live_forex_quote(p)
            chg = q.get("change_pct", 0.0)
            base = FOREX_PAIRS[p]["base"]
            quote = FOREX_PAIRS[p]["quote"]
            if base in strength:
                strength[base] += chg
            if quote in strength:
                strength[quote] -= chg
        except Exception:
            pass

    # Normalize scores between -100 and +100
    max_val = max(abs(v) for v in strength.values()) if any(strength.values()) else 1.0
    normalized = {k: round((v / max_val) * 100.0, 1) for k, v in strength.items()}
    return normalized


def generate_buy_sell_signal(pair: str) -> Dict[str, Any]:
    """Synthesize multi-indicator consensus to generate high-probability Buy/Sell signal.
    Combines EMA Trend, RSI momentum, MACD histogram, and Bollinger Band location.
    """
    norm = normalize_pair(pair)
    pip_size = get_pip_size(norm)

    # 1. Fetch live quote & historical candles
    quote = fetch_live_forex_quote(norm)
    df = fetch_forex_history(norm, interval="1h", period="1mo", force_refresh=False)
    if len(df) < 50:
        df = fetch_forex_history(norm, interval="1h", period="2mo", force_refresh=True)

    data = calculate_technical_indicators(df, pip_size)
    last = data.iloc[-1]
    prev = data.iloc[-2]

    close = float(last["Close"])
    ema20 = float(last["EMA_20"])
    ema50 = float(last["EMA_50"])
    ema200 = float(last["EMA_200"])
    rsi = float(last["RSI"]) if not pd.isna(last["RSI"]) else 50.0
    macd_hist = float(last["MACD_Hist"]) if not pd.isna(last["MACD_Hist"]) else 0.0
    bb_upper = float(last["BB_Upper"])
    bb_lower = float(last["BB_Lower"])
    atr_pips = float(last["ATR_Pips"]) if not pd.isna(last["ATR_Pips"]) else 35.0
    atr_pips = max(atr_pips, 15.0)  # Safe floor

    # 2. Consensus Scoring System (-100 to +100)
    score = 0
    reasons = []

    # Factor A: EMA Trend Alignment (Max +/- 35 points)
    if close > ema20 > ema50:
        score += 25
        reasons.append("Bullish Trend: Price > 20-EMA > 50-EMA")
        if close > ema200:
            score += 10
            reasons.append("Above 200-EMA Institutional Baseline")
    elif close < ema20 < ema50:
        score -= 25
        reasons.append("Bearish Trend: Price < 20-EMA < 50-EMA")
        if close < ema200:
            score -= 10
            reasons.append("Below 200-EMA Institutional Baseline")

    # Factor B: RSI Momentum (Max +/- 25 points)
    if rsi < 32:
        score += 25
        reasons.append(f"Oversold Bounce: RSI is at {rsi:.1f} (<32)")
    elif rsi > 68:
        score -= 25
        reasons.append(f"Overbought Exhaustion: RSI is at {rsi:.1f} (>68)")
    elif 50 <= rsi <= 65:
        score += 10
        reasons.append(f"Bullish Momentum: RSI healthy at {rsi:.1f}")
    elif 35 <= rsi < 50:
        score -= 10
        reasons.append(f"Bearish Drift: RSI subdued at {rsi:.1f}")

    # Factor C: MACD Acceleration (Max +/- 20 points)
    if macd_hist > 0 and macd_hist > float(prev["MACD_Hist"]):
        score += 20
        reasons.append("MACD Histogram expanding upward (Bullish Surge)")
    elif macd_hist < 0 and macd_hist < float(prev["MACD_Hist"]):
        score -= 20
        reasons.append("MACD Histogram expanding downward (Bearish Pressure)")

    # Factor D: Bollinger Bands (Max +/- 20 points)
    if close <= bb_lower:
        score += 20
        reasons.append("Price piercing Lower Bollinger Band (Mean Reversion)")
    elif close >= bb_upper:
        score -= 20
        reasons.append("Price piercing Upper Bollinger Band (Resistance Cap)")

    score = max(min(score, 100), -100)

    # 3. Determine Signal Verdict
    base_curr = FOREX_PAIRS[norm]["base"]
    quote_curr = FOREX_PAIRS[norm]["quote"]

    if score >= 50:
        verdict = "STRONG BUY"
        color = "#10B981"
        direction = "BUY"
        simple_headline = f"Strong Green Light: BUY {norm}"
        simple_summary = f"The {base_curr} is surging against the {quote_curr}. Buyers are in firm control, making this a high-probability buying opportunity."
    elif score >= 20:
        verdict = "BUY"
        color = "#34D399"
        direction = "BUY"
        simple_headline = f"Green Light: BUY {norm}"
        simple_summary = f"The {base_curr} is steadily gaining value over the {quote_curr}. Upward trend is intact."
    elif score <= -50:
        verdict = "STRONG SELL"
        color = "#EF4444"
        direction = "SELL"
        simple_headline = f"Strong Red Light: SELL {norm}"
        simple_summary = f"The {base_curr} is falling sharply against the {quote_curr}. Sellers are dominating, making this a strong opportunity to profit from a price drop."
    elif score <= -20:
        verdict = "SELL"
        color = "#F87171"
        direction = "SELL"
        simple_headline = f"Red Light: SELL {norm}"
        simple_summary = f"The {base_curr} is weakening against the {quote_curr}. The market is leaning downward."
    else:
        verdict = "NEUTRAL / WAIT"
        color = "#94A3B8"
        direction = "WAIT"
        simple_headline = f"Yellow Light: WAIT & WATCH {norm}"
        simple_summary = f"Neither buyers nor sellers have an advantage right now. The smart move is to be patient and wait for a clear signal."

    # 4. Professional Dynamic Stop Loss & Take Profit Levels (ATR Based)
    sl_pips = round(atr_pips * 1.5, 1)
    tp1_pips = round(sl_pips * 1.5, 1)  # 1:1.5 Risk-Reward
    tp2_pips = round(sl_pips * 3.0, 1)  # 1:3.0 Risk-Reward

    curr_p = quote["mid_price"]
    if direction == "BUY":
        rec_sl_price = round(curr_p - (sl_pips * pip_size), 5)
        rec_tp1_price = round(curr_p + (tp1_pips * pip_size), 5)
        rec_tp2_price = round(curr_p + (tp2_pips * pip_size), 5)
    elif direction == "SELL":
        rec_sl_price = round(curr_p + (sl_pips * pip_size), 5)
        rec_tp1_price = round(curr_p - (tp1_pips * pip_size), 5)
        rec_tp2_price = round(curr_p - (tp2_pips * pip_size), 5)
    else:
        rec_sl_price = curr_p
        rec_tp1_price = curr_p
        rec_tp2_price = curr_p

    # Plain English reasons
    beginner_reasons = []
    if "Bullish Trend" in str(reasons):
        beginner_reasons.append("📈 Trend: Prices have been climbing consistently over recent hours.")
    elif "Bearish Trend" in str(reasons):
        beginner_reasons.append("📉 Trend: Prices have been dropping consistently over recent hours.")
    if "Oversold" in str(reasons):
        beginner_reasons.append("⚡ Value: Price fell too fast and is bouncing back up (bargain zone).")
    elif "Overbought" in str(reasons):
        beginner_reasons.append("🛑 Warning: Price rose too quickly and is running out of steam.")
    if "MACD" in str(reasons) and "Bullish" in str(reasons):
        beginner_reasons.append("🚀 Speed: Upward buying momentum is accelerating.")
    elif "MACD" in str(reasons) and "Bearish" in str(reasons):
        beginner_reasons.append("🔻 Pressure: Downward selling momentum is speeding up.")
    if not beginner_reasons:
        beginner_reasons.append("⚖️ Balanced: Market forces are currently equal on both sides.")

    return {
        "pair": norm,
        "base_curr": base_curr,
        "quote_curr": quote_curr,
        "price": curr_p,
        "bid": quote["bid"],
        "ask": quote["ask"],
        "spread_pips": quote["spread_pips"],
        "score": score,
        "verdict": verdict,
        "direction": direction,
        "color": color,
        "simple_headline": simple_headline,
        "simple_summary": simple_summary,
        "beginner_reasons": beginner_reasons,
        "confidence_pct": abs(score),
        "reasons": reasons,
        "atr_pips": round(atr_pips, 1),
        "recommended_sl_pips": sl_pips,
        "recommended_tp1_pips": tp1_pips,
        "recommended_tp2_pips": tp2_pips,
        "recommended_sl_price": rec_sl_price,
        "recommended_tp1_price": rec_tp1_price,
        "recommended_tp2_price": rec_tp2_price,
        "indicators": {
            "EMA_20": round(ema20, 5),
            "EMA_50": round(ema50, 5),
            "EMA_200": round(ema200, 5),
            "RSI": round(rsi, 1),
            "MACD_Hist": round(macd_hist, 6),
            "BB_Upper": round(bb_upper, 5),
            "BB_Lower": round(bb_lower, 5),
        },
        "chart_df": data.tail(60),  # Last 60 bars for live interactive charting
    }
