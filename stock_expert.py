"""Stock Market Expert & Technical Scanner Module.
Provides quantitative scanning, technical indicator analysis, 
asymmetric risk/reward calculation, and plain-English beginner guidance.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf

# Curated watchlist of high-liquidity US Equities & ETFs for beginners
STOCK_WATCHLIST = {
    "SPY": {
        "name": "SPDR S&P 500 ETF Trust",
        "category": "Broad US Market Index",
        "description": "Represents the 500 largest US companies. The gold standard for steady, diversified wealth building.",
    },
    "QQQ": {
        "name": "Invesco QQQ Trust (Nasdaq 100)",
        "category": "Tech & Innovation Index",
        "description": "Tracks the top 100 non-financial tech giants (Apple, Microsoft, Nvidia, Amazon, etc.). High growth.",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "category": "AI & Semiconductors",
        "description": "World leader in graphics processing units (GPUs) powering the global Artificial Intelligence revolution.",
    },
    "AAPL": {
        "name": "Apple Inc.",
        "category": "Consumer Tech & Ecosystem",
        "description": "Global powerhouse known for iPhone, Mac, services, and massive recurring cash flow.",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "category": "Cloud & Enterprise Software",
        "description": "Dominant in enterprise software, Azure Cloud infrastructure, and frontier AI investments.",
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "category": "E-Commerce & AWS Cloud",
        "description": "Undisputed leader in cloud computing (AWS) and global e-commerce logistics.",
    },
    "GOOGL": {
        "name": "Alphabet Inc. (Google)",
        "category": "Digital Advertising & AI",
        "description": "Owns Google Search, YouTube, Android, and DeepMind; leading digital ad infrastructure.",
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "category": "EVs, Energy & Robotics",
        "description": "Pioneer in electric vehicles, autonomous driving software, energy storage, and robotics.",
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "category": "Semiconductors & Data Centers",
        "description": "Top designer of high-performance CPUs and AI accelerator chips for cloud data centers.",
    },
    "PLTR": {
        "name": "Palantir Technologies",
        "category": "Enterprise AI & Defense",
        "description": "Big data analytics and AI operating systems for defense intelligence and Fortune 500 enterprises.",
    },
    "SMH": {
        "name": "VanEck Semiconductor ETF",
        "category": "Semiconductor Sector",
        "description": "Basket of the world's most critical chipmakers and chip equipment manufacturers.",
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "category": "Banking & Financials",
        "description": "America's largest and most fortress-like commercial and investment bank.",
    },
}

_STOCK_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 60  # Cache quotes for 60 seconds to prevent rate limits


def fetch_stock_history(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV stock history from yfinance with caching."""
    ticker = ticker.strip().upper()
    now = time.time()

    cache_key = f"{ticker}_{period}_{interval}"
    if cache_key in _STOCK_CACHE:
        cached_time, cached_df = _STOCK_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_df.copy()

    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df is None or len(df) < 20:
            return None

        # Flatten multi-index columns if present (common in recent yfinance)
        if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
            df.columns = df.columns.get_level_values(0)

        df = df.dropna().copy()
        _STOCK_CACHE[cache_key] = (now, df)
        return df.copy()
    except Exception as e:
        print(f"Error fetching stock data for {ticker}: {e}")
        return None


def calculate_stock_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate key technical indicators for stock scanning."""
    df = df.copy()

    # Moving Averages
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["SMA_200"] = df["Close"].rolling(window=min(200, len(df))).mean()

    # RSI (14-period)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # Bollinger Bands (20-day, 2 std dev)
    rolling_mean = df["Close"].rolling(window=20).mean()
    rolling_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = rolling_mean + (rolling_std * 2)
    df["BB_Lower"] = rolling_mean - (rolling_std * 2)
    df["BB_Mid"] = rolling_mean

    # Volume Analysis
    df["Vol_SMA20"] = df["Volume"].rolling(window=20).mean()
    df["Vol_Surge"] = df["Volume"] / (df["Vol_SMA20"] + 1e-9)

    return df


def generate_stock_recommendation(ticker: str) -> Dict[str, Any]:
    """
    Scans a stock, computes multi-factor technical rating, 
    and returns a beginner-friendly recommendation with exact entry/exit targets.
    """
    ticker = ticker.strip().upper()
    df = fetch_stock_history(ticker, period="6mo", interval="1d")

    meta = STOCK_WATCHLIST.get(ticker, {
        "name": ticker,
        "category": "US Equity",
        "description": f"Publicly traded stock ({ticker}) listed on US exchanges.",
    })

    if df is None or len(df) < 25:
        return {
            "ticker": ticker,
            "name": meta["name"],
            "category": meta["category"],
            "description": meta["description"],
            "current_price": 0.0,
            "change_pct": 0.0,
            "direction": "WAIT",
            "score": 0,
            "simple_headline": "Data Unavailable",
            "simple_summary": f"Could not retrieve recent price data for {ticker}.",
            "beginner_reasons": ["Market data provider timed out or symbol is unrecognized."],
            "secret_note": "Always ensure you are querying valid, liquid tickers.",
            "entry_price": 0.0,
            "stop_loss_price": 0.0,
            "take_profit_price": 0.0,
            "risk_reward_ratio": 2.0,
            "chart_df": pd.DataFrame(),
        }

    df = calculate_stock_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    current_price = float(latest["Close"])
    prev_close = float(prev["Close"])
    change_pct = ((current_price - prev_close) / prev_close) * 100

    ema_20 = float(latest["EMA_20"])
    ema_50 = float(latest["EMA_50"])
    sma_200 = float(latest["SMA_200"])
    rsi = float(latest["RSI"])
    macd_hist = float(latest["MACD_Hist"])
    prev_macd_hist = float(prev["MACD_Hist"])
    vol_surge = float(latest["Vol_Surge"])

    # Multi-Factor Quantitative Scoring
    score = 0
    reasons = []

    # Factor 1: Trend Alignment
    if current_price > ema_50:
        score += 1
        reasons.append("Price is trading above its 50-day average (Medium-Term Trend is Up)")
    else:
        score -= 1
        reasons.append("Price is below its 50-day average (Downtrend pressure)")

    if ema_20 > ema_50:
        score += 1
        reasons.append("Fast 20-day trend is above the 50-day trend (Bullish momentum)")

    if current_price > sma_200:
        score += 1
        reasons.append("Above 200-day moving average (Institutional Macro Bull Market)")
    else:
        score -= 1

    # Factor 2: Momentum (RSI)
    if 45 <= rsi <= 68:
        score += 1
        reasons.append(f"RSI momentum is healthy at {rsi:.1f} (Steady buying without being overbought)")
    elif rsi > 70:
        score -= 1
        reasons.append(f"RSI is elevated at {rsi:.1f} (Overbought — risk of short-term pullback)")
    elif rsi < 32 and current_price > prev_close:
        score += 1
        reasons.append(f"RSI was oversold at {rsi:.1f} and is bouncing back upward")

    # Factor 3: MACD Histogram Acceleration
    if macd_hist > 0 and macd_hist > prev_macd_hist:
        score += 1
        reasons.append("MACD momentum bars are expanding green (Buyers gaining strength)")
    elif macd_hist < 0 and macd_hist < prev_macd_hist:
        score -= 1
        reasons.append("MACD momentum bars are declining red (Sellers in control)")

    # Factor 4: Volume Confirmation
    if vol_surge > 1.2 and change_pct > 0:
        score += 1
        reasons.append(f"Trading volume is {vol_surge:.1f}x higher than usual (Big institutions buying)")

    # Final Direction & Plain-English Headline
    if score >= 3:
        direction = "BUY"
        headline = "🟢 HIGH-CONVICTION BUY SETUP"
        summary = (
            f"{ticker} has strong institutional backing right now. The trend, momentum, "
            f"and trading volume are all aligned in favor of buyers."
        )
        # Asymmetric Targets: Stop Loss 3.0% below, Take Profit 6.5% above (Reward:Risk ~ 2.2:1)
        stop_loss = round(current_price * 0.97, 2)
        take_profit = round(current_price * 1.065, 2)
        secret_note = (
            "Wall Street Secret #1 (Asymmetric Risk): A good trade never risks more than 1 unit to make 2 units. "
            f"If {ticker} drops to ${stop_loss:.2f}, the bot cuts the loss automatically. If it rises to ${take_profit:.2f}, "
            f"you lock in a solid profit. You don't need a 90% win rate to be profitable — you just need your winners to be bigger than your losers."
        )
    elif score in [1, 2]:
        direction = "WATCH"
        headline = "🟡 NEUTRAL / WAIT FOR PULLBACK"
        summary = (
            f"{ticker} is in a decent position, but hasn't formed a clean breakout entry yet. "
            f"Patience is a trader's greatest superpower."
        )
        stop_loss = round(current_price * 0.96, 2)
        take_profit = round(current_price * 1.05, 2)
        secret_note = (
            "Wall Street Secret #2 (Patience): Amateurs lose money by feeling the urge to trade every single minute. "
            "Professional traders wait like snipers for high-probability setups before deploying capital."
        )
    else:
        direction = "SELL"
        headline = "🔴 BEARISH PRESSURE / AVOID BUYING"
        summary = (
            f"{ticker} is experiencing selling pressure or breaking below key support levels. "
            f"Do not buy declining stocks hoping they will bounce — wait for buyers to return first."
        )
        stop_loss = round(current_price * 0.95, 2)
        take_profit = round(current_price * 1.04, 2)
        secret_note = (
            "Wall Street Secret #3 (Trend is Your Friend): Never fight the market trend. It is far easier to make "
            "money swimming with the current than swimming against a waterfall."
        )

    rr_ratio = round((take_profit - current_price) / max(0.01, (current_price - stop_loss)), 2)

    # Format chart dataframe
    chart_df = df.tail(60).copy()
    chart_df["Date"] = chart_df.index
    chart_df = chart_df.reset_index(drop=True)

    return {
        "ticker": ticker,
        "name": meta["name"],
        "category": meta["category"],
        "description": meta["description"],
        "current_price": round(current_price, 2),
        "change_pct": round(change_pct, 2),
        "direction": direction,
        "score": score,
        "simple_headline": headline,
        "simple_summary": summary,
        "beginner_reasons": reasons,
        "secret_note": secret_note,
        "entry_price": round(current_price, 2),
        "stop_loss_price": stop_loss,
        "take_profit_price": take_profit,
        "risk_reward_ratio": rr_ratio,
        "rsi": round(rsi, 1),
        "chart_df": chart_df,
    }


def scan_entire_watchlist() -> List[Dict[str, Any]]:
    """Scan all stocks in the watchlist and return ranked by opportunity score."""
    results = []
    for ticker in STOCK_WATCHLIST.keys():
        rec = generate_stock_recommendation(ticker)
        if rec["current_price"] > 0:
            results.append(rec)

    # Sort descending by quantitative score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
