"""Data Loader module for Plain English Trader.
Fetches daily historical OHLCV data from financial sources with local caching.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Common ETF/Stock aliases mapped to ticker symbols
ASSET_ALIASES = {
    "tech": "QQQ",
    "tech stocks": "QQQ",
    "technology": "XLK",
    "market": "SPY",
    "s&p 500": "SPY",
    "sp500": "SPY",
    "bonds": "BND",
    "treasury bonds": "TLT",
    "treasuries": "TLT",
    "cash": "BIL",
    "t-bills": "BIL",
    "gold": "GLD",
    "crypto": "BTC-USD",
    "bitcoin": "BTC-USD",
    "semiconductors": "SMH",
    "energy": "XLE",
    "financials": "XLF",
    "healthcare": "XLV",
    "utilities": "XLU",
    "small cap": "IWM",
    "small caps": "IWM",
    "emerging markets": "EEM",
    "real estate": "VNQ",
    "dividend": "SCHD",
}


def resolve_ticker(name: str) -> str:
    """Resolve an asset nickname or symbol to a clean uppercase ticker."""
    cleaned = name.strip().lower()
    if cleaned in ASSET_ALIASES:
        return ASSET_ALIASES[cleaned]
    return name.strip().upper()


def fetch_ticker_data(ticker: str, years: int = 5, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch daily OHLCV data for a ticker with local disk caching."""
    ticker = resolve_ticker(ticker)
    cache_file = os.path.join(CACHE_DIR, f"{ticker}_{years}y.csv")

    # Use cache if file exists and is less than 12 hours old
    if not force_refresh and os.path.exists(cache_file):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - mtime < timedelta(hours=12):
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                if not df.empty:
                    return df
        except Exception:
            pass

    # Fetch from Yahoo Finance chart API
    range_str = f"{years}y" if years <= 10 else "max"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        res = data.get("chart", {}).get("result")
        if not res or len(res) == 0:
            raise ValueError(f"No chart data found for ticker {ticker}")

        item = res[0]
        timestamps = item.get("timestamp", [])
        if not timestamps:
            raise ValueError(f"No price timestamps for {ticker}")

        quote = item.get("indicators", {}).get("quote", [{}])[0]
        adjclose_list = item.get("indicators", {}).get("adjclose", [{}])
        adj_close = adjclose_list[0].get("adjclose") if adjclose_list else None

        df = pd.DataFrame(
            {
                "Open": quote.get("open", []),
                "High": quote.get("high", []),
                "Low": quote.get("low", []),
                "Close": quote.get("close", []),
                "Volume": quote.get("volume", []),
            },
            index=pd.to_datetime(timestamps, unit="s"),
        )

        if adj_close and len(adj_close) == len(df):
            df["AdjClose"] = adj_close
        else:
            df["AdjClose"] = df["Close"]

        # Clean index timezone and drop NaNs
        df.index = df.index.tz_localize(None).floor("D")
        df = df[~df.index.duplicated(keep="first")]
        df = df.dropna(subset=["Close"])

        # Cache to disk
        df.to_csv(cache_file)
        return df

    except Exception as e:
        # If network fails, try stale cache if available
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file, index_col=0, parse_dates=True)
        raise RuntimeError(f"Failed to fetch data for {ticker}: {str(e)}")


def get_multi_asset_close(tickers: List[str], years: int = 5) -> pd.DataFrame:
    """Fetch adjusted close series for multiple assets aligned by date."""
    resolved = [resolve_ticker(t) for t in tickers]
    data = {}
    for t in resolved:
        try:
            df = fetch_ticker_data(t, years=years)
            data[t] = df["AdjClose"]
        except Exception as e:
            print(f"Warning: could not load {t}: {e}")

    if not data:
        raise ValueError("Could not load data for any requested tickers.")

    combined = pd.DataFrame(data).dropna()
    return combined
