"""Natural Language Strategy Parser.
Converts plain English prompts into a deterministic, structured StrategySpec.
Includes both a zero-dependency rule-based semantic parser and an optional LLM parser.
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from data_loader import resolve_ticker


@dataclass
class StrategySpec:
    name: str
    description: str
    signal_asset: str               # Asset evaluated for the condition (e.g. SPY)
    condition_type: str             # 'price_above_sma', 'sma_crossover', 'rsi_oversold', 'momentum_positive'
    params: Dict[str, Any]          # e.g. {'period': 200}
    bull_assets: Dict[str, float]   # Asset -> portfolio weight when condition is TRUE
    bear_assets: Dict[str, float]   # Asset -> portfolio weight when condition is FALSE
    benchmark: str = "SPY"
    rebalance_freq: str = "daily"   # 'daily', 'weekly', 'monthly'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def human_summary(self) -> str:
        bull_str = ", ".join([f"{int(w*100)}% {a}" for a, w in self.bull_assets.items()])
        bear_str = ", ".join([f"{int(w*100)}% {a}" for a, w in self.bear_assets.items()])
        
        if self.condition_type == "price_above_sma":
            cond = f"{self.signal_asset} Price > {self.params.get('period', 200)}-day SMA"
        elif self.condition_type == "sma_crossover":
            cond = f"{self.signal_asset} {self.params.get('fast', 50)}-SMA > {self.params.get('slow', 200)}-SMA"
        elif self.condition_type == "rsi_oversold":
            cond = f"{self.signal_asset} RSI({self.params.get('period', 14)}) < {self.params.get('threshold', 30)}"
        elif self.condition_type == "momentum_positive":
            cond = f"{self.signal_asset} {self.params.get('days', 20)}-day Momentum > 0%"
        else:
            cond = f"{self.signal_asset} condition active"

        return f"IF [{cond}] THEN allocate [{bull_str}] ELSE allocate [{bear_str}]"


def rule_based_parse(prompt: str) -> StrategySpec:
    """Parse strategy description using pattern matching and financial entity recognition."""
    text = prompt.strip()
    lower = text.lower()

    # 1. Detect Signal Asset (Default to SPY / Market)
    signal_asset = "SPY"
    if "qqq" in lower and ("when qqq" in lower or "qqq is" in lower):
        signal_asset = "QQQ"
    elif "tech" in lower and "when tech" in lower:
        signal_asset = "QQQ"
    elif "bitcoin" in lower or "btc" in lower:
        signal_asset = "BTC-USD"

    # 2. Detect Target Bull Assets
    # Check for tech, qqq, xlk, spy, individual tickers
    bull_asset = "QQQ"  # Default tech
    if "xlk" in lower:
        bull_asset = "XLK"
    elif "smh" in lower or "semiconductor" in lower:
        bull_asset = "SMH"
    elif "nvda" in lower or "nvidia" in lower:
        bull_asset = "NVDA"
    elif "aapl" in lower or "apple" in lower:
        bull_asset = "AAPL"
    elif "crypto" in lower or "btc" in lower:
        bull_asset = "BTC-USD"
    elif "s&p" in lower or "spy" in lower:
        bull_asset = "SPY"

    # 3. Detect Target Bear Assets (defensive)
    bear_asset = "BND"  # Default bonds
    if "cash" in lower or "bil" in lower or "t-bills" in lower:
        bear_asset = "BIL"
    elif "tlt" in lower or "long treasury" in lower or "treasuries" in lower:
        bear_asset = "TLT"
    elif "gold" in lower or "gld" in lower:
        bear_asset = "GLD"
    elif "spy" in lower and ("move to spy" in lower or "else spy" in lower):
        bear_asset = "SPY"

    # 4. Detect Condition Type & Parameters
    condition_type = "price_above_sma"
    params = {"period": 200}

    # Moving Average Period extraction
    ma_match = re.search(r'(\d+)\s*[- ]*(day|d)?\s*(sma|moving average|ma)', lower)
    if ma_match:
        params["period"] = int(ma_match.group(1))

    # Crossover detection
    if "cross" in lower or "golden cross" in lower or ("50" in lower and "200" in lower):
        condition_type = "sma_crossover"
        params = {"fast": 50, "slow": 200}
        fast_m = re.search(r'(\d+)\s*(day)?\s*(sma)?\s*(above|cross|over|>)\s*(\d+)', lower)
        if fast_m:
            params["fast"] = int(fast_m.group(1))
            params["slow"] = int(fast_m.group(5))

    # RSI detection
    elif "rsi" in lower:
        condition_type = "rsi_oversold"
        params = {"period": 14, "threshold": 30}
        rsi_thresh = re.search(r'rsi\s*(<|below|under)?\s*(\d+)', lower)
        if rsi_thresh:
            params["threshold"] = int(rsi_thresh.group(2))

    # Momentum / Return detection
    elif "momentum" in lower or "trend" in lower or "market is up" in lower or "drops" in lower:
        if "200" in lower or "sma" in lower or "average" in lower or "market is up" in lower:
            condition_type = "price_above_sma"
            if "50" in lower:
                params["period"] = 50
            elif "20" in lower:
                params["period"] = 20
            else:
                params["period"] = 200
        else:
            condition_type = "momentum_positive"
            params = {"days": 20}

    # Frequency detection
    freq = "daily"
    if "week" in lower:
        freq = "weekly"
    elif "month" in lower:
        freq = "monthly"

    name = f"{resolve_ticker(bull_asset)} vs {resolve_ticker(bear_asset)} ({condition_type.replace('_', ' ').title()})"

    return StrategySpec(
        name=name,
        description=prompt,
        signal_asset=resolve_ticker(signal_asset),
        condition_type=condition_type,
        params=params,
        bull_assets={resolve_ticker(bull_asset): 1.0},
        bear_assets={resolve_ticker(bear_asset): 1.0},
        benchmark="SPY",
        rebalance_freq=freq,
    )


def llm_parse(prompt: str, api_key: str, provider: str = "gemini") -> StrategySpec:
    """Use an LLM (Gemini or Groq) to parse unstructured trading strategies into StrategySpec."""
    system_instruction = """
    You are an expert quantitative trading engineer. Convert the user's natural language trading strategy description into a structured JSON object matching this schema:
    {
      "name": "Short strategy title",
      "signal_asset": "Ticker symbol used to determine signal (e.g. SPY, QQQ, BTC-USD)",
      "condition_type": "price_above_sma" | "sma_crossover" | "rsi_oversold" | "momentum_positive",
      "params": {
         "period": 200 (if price_above_sma),
         "fast": 50, "slow": 200 (if sma_crossover),
         "period": 14, "threshold": 30 (if rsi_oversold),
         "days": 20 (if momentum_positive)
      },
      "bull_assets": {"TICKER": 1.0},
      "bear_assets": {"TICKER": 1.0},
      "benchmark": "SPY",
      "rebalance_freq": "daily" | "weekly" | "monthly"
    }
    Only output valid JSON with no markdown wrapping.
    """

    if provider.lower() == "gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_instruction}\nUser Prompt: {prompt}",
        )
        content = response.text.strip()
    elif provider.lower() == "groq":
        from groq import Groq
        client = Groq(api_key=api_key)
        chat = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        content = chat.choices[0].message.content.strip()
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # Clean potential markdown backticks
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1])

    data = json.loads(content)
    return StrategySpec(
        name=data.get("name", "Custom Natural Strategy"),
        description=prompt,
        signal_asset=resolve_ticker(data.get("signal_asset", "SPY")),
        condition_type=data.get("condition_type", "price_above_sma"),
        params=data.get("params", {"period": 200}),
        bull_assets={resolve_ticker(k): float(v) for k, v in data.get("bull_assets", {"QQQ": 1.0}).items()},
        bear_assets={resolve_ticker(k): float(v) for k, v in data.get("bear_assets", {"BND": 1.0}).items()},
        benchmark=resolve_ticker(data.get("benchmark", "SPY")),
        rebalance_freq=data.get("rebalance_freq", "daily"),
    )


def parse_strategy(prompt: str, api_key: Optional[str] = None, provider: str = "gemini") -> StrategySpec:
    """Main entry point: uses LLM if key is supplied, otherwise falls back gracefully to rule parser."""
    if api_key and api_key.strip():
        try:
            return llm_parse(prompt, api_key.strip(), provider=provider)
        except Exception as e:
            print(f"LLM parsing failed ({e}), falling back to robust rule-based parser.")
            return rule_based_parse(prompt)
    return rule_based_parse(prompt)
