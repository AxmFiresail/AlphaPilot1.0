"""Forex Data Fetcher and Live Tick Poller.
Fetches real-time quotes, intraday bars, and multi-year historical candles for Forex currency pairs.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from forex_pairs import normalize_pair, get_pair_symbol, FOREX_PAIRS

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache_forex")
os.makedirs(CACHE_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_forex_history(pair: str, interval: str = "1d", period: str = "2y", force_refresh: bool = False) -> pd.DataFrame:
    """Fetch OHLCV candlestick data for a Forex pair.
    interval: '15m', '1h', '1d'
    period: '5d', '1mo', '6mo', '1y', '2y', '5y'
    """
    norm = normalize_pair(pair)
    sym = get_pair_symbol(norm)
    cache_file = os.path.join(CACHE_DIR, f"{sym.replace('=', '_')}_{interval}_{period}.csv")

    if not force_refresh and os.path.exists(cache_file):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            # Cache for 1 hour for daily, 10 mins for intraday
            max_age = timedelta(hours=1) if interval == "1d" else timedelta(minutes=10)
            if datetime.now() - mtime < max_age:
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                if not df.empty:
                    return df
        except Exception:
            pass

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={period}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        res = data.get("chart", {}).get("result")
        if not res or len(res) == 0:
            raise ValueError(f"No chart data found for currency pair {pair} ({sym})")

        item = res[0]
        timestamps = item.get("timestamp", [])
        quote = item.get("indicators", {}).get("quote", [{}])[0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [0] * len(timestamps))

        # Filter out trailing None values common in live chart streams
        valid_records = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            o = opens[i] if i < len(opens) else None
            h = highs[i] if i < len(highs) else None
            l = lows[i] if i < len(lows) else None
            if c is not None and o is not None:
                valid_records.append({
                    "timestamp": datetime.fromtimestamp(ts),
                    "Open": float(o),
                    "High": float(h if h is not None else c),
                    "Low": float(l if l is not None else c),
                    "Close": float(c),
                    "Volume": float(volumes[i] if i < len(volumes) and volumes[i] is not None else 0),
                })

        if not valid_records:
            raise ValueError(f"No valid price ticks found for {pair}")

        df = pd.DataFrame(valid_records).set_index("timestamp")
        df = df[~df.index.duplicated(keep="last")]
        df.sort_index(inplace=True)

        # Cache on disk
        df.to_csv(cache_file)
        return df

    except Exception as e:
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file, index_col=0, parse_dates=True)
        raise RuntimeError(f"Failed to fetch Forex data for {pair}: {str(e)}")


def fetch_live_forex_quote(pair: str) -> Dict[str, Any]:
    """Fetch current real-time Bid/Ask rates and daily stats for a Forex pair."""
    norm = normalize_pair(pair)
    sym = get_pair_symbol(norm)
    meta = FOREX_PAIRS[norm]
    spread_pips = meta["spread_pips"]
    pip_size = meta["pip_size"]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1m"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        res = data["chart"]["result"][0]
        meta_info = res.get("meta", {})
        quote = res["indicators"]["quote"][0]
        valid_closes = [c for c in quote["close"] if c is not None]

        latest_price = float(valid_closes[-1]) if valid_closes else float(meta_info.get("regularMarketPrice", 1.0))
        prev_close = float(meta_info.get("chartPreviousClose", latest_price))

        half_spread = (spread_pips * pip_size) / 2.0
        bid = round(latest_price - half_spread, 5 if pip_size == 0.0001 else 3)
        ask = round(latest_price + half_spread, 5 if pip_size == 0.0001 else 3)
        change_pct = ((latest_price / prev_close) - 1.0) * 100.0 if prev_close else 0.0

        return {
            "pair": norm,
            "symbol": sym,
            "mid_price": latest_price,
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips,
            "pip_size": pip_size,
            "change_pct": round(change_pct, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        # Fallback approximation
        return {
            "pair": norm,
            "symbol": sym,
            "mid_price": 1.0850,
            "bid": 1.0849,
            "ask": 1.0851,
            "spread_pips": spread_pips,
            "pip_size": pip_size,
            "change_pct": 0.0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e),
        }
