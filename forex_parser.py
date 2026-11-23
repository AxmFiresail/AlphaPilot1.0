"""Forex Natural Language Strategy Parser.
Converts freeform trading ideas into a formal ForexStrategySpec with pair, conditions, and pip risk limits.
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from forex_pairs import normalize_pair, FOREX_ALIASES


@dataclass
class ForexStrategySpec:
    name: str
    description: str
    pair: str                       # e.g. "EUR/USD"
    timeframe: str                  # "1h", "15m", "1d"
    condition_type: str             # "ema_crossover", "sma_crossover", "rsi_reversal", "price_above_ma", "breakout"
    params: Dict[str, Any]          # e.g. {"fast": 20, "slow": 50}
    stop_loss_pips: Optional[float] # e.g. 40.0
    take_profit_pips: Optional[float]# e.g. 80.0
    lot_size: float = 0.1           # Default 0.1 = Mini Lot (10,000 units)
    allow_short: bool = True        # True = Bidirectional (Long/Short), False = Long/Flat

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def human_summary(self) -> str:
        sl_str = f" [SL: {self.stop_loss_pips} pips]" if self.stop_loss_pips else ""
        tp_str = f" [TP: {self.take_profit_pips} pips]" if self.take_profit_pips else ""
        
        if self.condition_type == "ema_crossover":
            cond = f"Fast {self.params.get('fast', 20)}-EMA crosses Slow {self.params.get('slow', 50)}-EMA"
        elif self.condition_type == "sma_crossover":
            cond = f"Fast {self.params.get('fast', 50)}-SMA crosses Slow {self.params.get('slow', 200)}-SMA"
        elif self.condition_type == "rsi_reversal":
            cond = f"RSI({self.params.get('period', 14)}) < {self.params.get('oversold', 30)} (Long) / > {self.params.get('overbought', 70)} (Short)"
        elif self.condition_type == "price_above_ma":
            cond = f"Price > {self.params.get('period', 200)}-SMA"
        elif self.condition_type == "breakout":
            cond = f"Price breaks {self.params.get('period', 20)}-period High/Low"
        else:
            cond = f"Custom Indicator Condition"

        action = "LONG / SHORT" if self.allow_short else "LONG / FLAT"
        return f"PAIR: {self.pair} ({self.timeframe}) | RULE: {cond} -> {action}{sl_str}{tp_str} | SIZE: {self.lot_size} lots"


def rule_based_forex_parse(prompt: str) -> ForexStrategySpec:
    """Specialized Forex rule parser for currency pairs, pips, and FX signals."""
    lower = prompt.lower()

    # 1. Detect Currency Pair
    detected_pair = "EUR/USD"
    for alias, standard in FOREX_ALIASES.items():
        if alias in lower:
            detected_pair = standard
            break

    # 2. Timeframe detection (15m, 1h, 1d)
    timeframe = "1h"  # default 1-hour candles for Forex
    if "15m" in lower or "15 min" in lower or "minute" in lower:
        timeframe = "15m"
    elif "4h" in lower or "4 hour" in lower:
        timeframe = "1h"
    elif "daily" in lower or "1d" in lower or "day" in lower:
        timeframe = "1d"

    # 3. Detect Stop Loss & Take Profit in Pips
    stop_loss = 40.0
    take_profit = 80.0

    sl_m = re.search(r'(\d+)\s*(pip|pips)?\s*(stop|sl|stop loss)', lower) or re.search(r'(stop|sl|stop loss)\s*(\d+)', lower)
    if sl_m:
        stop_loss = float(sl_m.group(1) if sl_m.group(1).isdigit() else sl_m.group(2))

    tp_m = re.search(r'(\d+)\s*(pip|pips)?\s*(target|tp|take profit)', lower) or re.search(r'(take profit|tp|target)\s*(\d+)', lower)
    if tp_m:
        take_profit = float(tp_m.group(1) if tp_m.group(1).isdigit() else tp_m.group(2))

    # 4. Lot sizing
    lot_size = 0.1
    lot_m = re.search(r'(\d+(\.\d+)?)\s*(lot|lots)', lower)
    if lot_m:
        lot_size = float(lot_m.group(1))

    # 5. Condition Type and Indicators
    condition_type = "ema_crossover"
    params = {"fast": 20, "slow": 50}

    # EMA crossover
    if "ema" in lower or "exponential" in lower:
        condition_type = "ema_crossover"
        periods = [int(p[0]) for p in re.findall(r'(\d+)\s*[- ]*(ema|period)', lower)]
        if len(periods) >= 2:
            params = {"fast": min(periods[0], periods[1]), "slow": max(periods[0], periods[1])}
        elif len(periods) == 1:
            params = {"fast": periods[0], "slow": periods[0] * 2}
        else:
            params = {"fast": 20, "slow": 50}

    # RSI
    elif "rsi" in lower:
        condition_type = "rsi_reversal"
        params = {"period": 14, "oversold": 30, "overbought": 70}
        thresh = re.findall(r'\b(20|25|30|35|65|70|75|80)\b', lower)
        if len(thresh) >= 2:
            params["oversold"] = int(min(thresh))
            params["overbought"] = int(max(thresh))

    # Breakout
    elif "breakout" in lower or "break" in lower or "high" in lower:
        condition_type = "breakout"
        params = {"period": 20}
        pm = re.search(r'(\d+)\s*[- ]*(bar|period|day|hour)', lower)
        if pm:
            params["period"] = int(pm.group(1))

    # Simple Moving Average / Trend
    elif "sma" in lower or "moving average" in lower or "above" in lower or "market is up" in lower or "trend" in lower:
        if "cross" in lower:
            condition_type = "sma_crossover"
            params = {"fast": 50, "slow": 200}
        else:
            condition_type = "price_above_ma"
            params = {"period": 200}
            period_m = re.search(r'(\d+)\s*[- ]*(sma|ma|moving average)', lower)
            if period_m:
                params["period"] = int(period_m.group(1))

    name = f"{detected_pair} {condition_type.replace('_', ' ').title()}"

    return ForexStrategySpec(
        name=name,
        description=prompt,
        pair=detected_pair,
        timeframe=timeframe,
        condition_type=condition_type,
        params=params,
        stop_loss_pips=stop_loss,
        take_profit_pips=take_profit,
        lot_size=lot_size,
        allow_short=True,
    )


def parse_forex_strategy(prompt: str, api_key: Optional[str] = None, provider: str = "gemini") -> ForexStrategySpec:
    """Parse natural language into ForexStrategySpec. Uses LLM if key given, else rule parser."""
    if api_key and api_key.strip():
        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            prompt_instruction = f"""
            You are a quantitative Forex trading engineer. Convert the user prompt into this JSON schema:
            {{
              "name": "Strategy Name",
              "pair": "EUR/USD" | "GBP/USD" | "USD/JPY" | "AUD/USD" | "USD/CAD" | "USD/CHF" | "EUR/GBP" | "EUR/JPY" | "GBPJPY",
              "timeframe": "1h" | "15m" | "1d",
              "condition_type": "ema_crossover" | "sma_crossover" | "rsi_reversal" | "price_above_ma" | "breakout",
              "params": {{"fast": 20, "slow": 50}} or relevant indicators,
              "stop_loss_pips": 40.0,
              "take_profit_pips": 80.0,
              "lot_size": 0.1,
              "allow_short": true
            }}
            Prompt: {prompt}
            Only output valid JSON.
            """
            res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_instruction)
            text = res.text.strip()
            if text.startswith("```"):
                text = "\n".join(text.splitlines()[1:-1])
            data = json.loads(text)
            return ForexStrategySpec(
                name=data.get("name", "Custom Forex Strategy"),
                description=prompt,
                pair=normalize_pair(data.get("pair", "EUR/USD")),
                timeframe=data.get("timeframe", "1h"),
                condition_type=data.get("condition_type", "ema_crossover"),
                params=data.get("params", {"fast": 20, "slow": 50}),
                stop_loss_pips=float(data.get("stop_loss_pips", 40.0)) if data.get("stop_loss_pips") else None,
                take_profit_pips=float(data.get("take_profit_pips", 80.0)) if data.get("take_profit_pips") else None,
                lot_size=float(data.get("lot_size", 0.1)),
                allow_short=bool(data.get("allow_short", True)),
            )
        except Exception:
            pass

    return rule_based_forex_parse(prompt)
