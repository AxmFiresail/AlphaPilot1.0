[README.md](https://github.com/user-attachments/files/35321353/README.md)
# ⚡ AlphaForex: Autonomous Plain English Forex Studio

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.62+-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Market: Forex](https://img.shields.io/badge/Market-Forex%20%28FX%29-10B981.svg)]()
[![Status: Autonomous 24/5](https://img.shields.io/badge/Execution-24%2F5%20Autopilot-indigo.svg)]()

> **Describe any Forex strategy in everyday plain English, backtest how it would have performed historically in pips, monitor live currency strength, and let an institutional 24/5 autonomous bot execute and manage trades with zero-risk profit locks.**

---

## 🌟 Why AlphaForex?

Most quantitative trading systems require writing complex code in MQL4/MQL5, PineScript, or Python. **AlphaForex bridges the gap for beginners and quantitative traders alike**:

1. **Natural Language Strategy Compiler**: Write rules in everyday English like *"Buy EUR/USD when 20 EMA crosses above 50 EMA, go short when it crosses below, with a 30 pip stop loss and 60 pip take profit"*.
2. **Beginner-Friendly Traffic-Light Signals**: No confusing mathematical clutter. The system gives you clear **Green Light (BUY)**, **Red Light (SELL)**, or **Yellow Light (WAIT)** recommendations with plain-English reasoning.
3. **Real-Time Visual Loss / Gain Location Tracker**: Always know where your money is with a live progress gauge showing your exact position between your safety net (Stop Loss) and profit target (Take Profit).
4. **Institutional "Profit Guardian" Engine**: Employs real institutional risk secrets:
   - 🛡️ **Automatic Breakeven Lock (+15 pips)**: Moves stop loss to entry $+1.5$ pips once in profit. Trade becomes **100% risk-free**.
   - 📈 **Dynamic ATR Trailing Stop (+25 pips)**: Automatically trails profits behind price to lock in green pips during runners.
   - 🛑 **Anti-Chop Rule**: Holds through market noise without panic-selling at a loss.
5. **Live Multi-Currency Radar & Currency Strength Meter (CSM)**: Tracks 8 major and cross currency pairs in real time and highlights the highest-momentum "Power Pair".
6. **Multi-User Isolation**: Each user has an isolated workspace with custom risk tolerances, lot-size caps, private strategy libraries, and personal broker credentials.
7. **24/5 Autopilot Daemon**: Can run interactively via web dashboard or as a lightweight, headless terminal daemon on a VPS/cloud server.

---

## 📸 Core Features Overview

### 1. 🚦 "What Should You Do Right Now?" Decision Card
Clear visual signal cards powered by multi-indicator technical consensus (EMA Hierarchy, RSI Momentum, MACD Acceleration, and Bollinger Bands):
* 🟢 **BUY (Long)**: Base currency is surging; buyers dominate.
* 🔴 **SELL (Short)**: Base currency is falling; sellers dominate.
* 🟡 **WAIT (Neutral)**: Choppy or consolidating market; wait for a clear setup.

### 2. 📍 Live Loss / Gain Location Gauge
```
🛑 Safety Net Stop Loss     📍 Where You Entered     👉 YOU ARE HERE     🎯 Profit Goal Target
      [1.09450]                 [1.09650]               [1.09790]              [1.10150]
────────────────────────────────────────────────────────────────────────────────────────────
[████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]
                       70% of the way to your Profit Target!
```

### 3. 📈 Interactive Line Chart (Simple vs Advanced View)
* **Simple View**: Clean, uncluttered price line with green target zones and red safety stops.
* **Advanced View**: Live overlays of 20-EMA (Fast), 50-EMA (Medium), 200-EMA (Macro Baseline), and Bollinger Band volatility channels.

### 4. 🌍 Multi-Currency Radar & Power Pair Detection
* Live Bid/Ask quotes, spreads (in pips), and 24h change for `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, `USD/CAD`, `USD/CHF`, `EUR/JPY`, and `GBP/JPY`.
* **Currency Strength Meter**: Ranks USD, EUR, GBP, JPY, AUD, CAD, and CHF on a $-100$ to $+100$ scale to automatically pair the strongest vs. weakest currency.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              User Input (Everyday English)              │
│  "Buy EUR/USD when 20 EMA > 50 EMA, 30 pip stop loss"   │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│        Forex NLP Parser (`forex_parser.py`)             │
│   Extracts pair, timeframe, rules, SL/TP pips, lot size │
└──────────────┬───────────────────────────┬──────────────┘
               │                           │
               ▼                           ▼
┌─────────────────────────────┐ ┌─────────────────────────┐
│ Historical Backtesting      │ │ Autonomous Autopilot    │
│ Engine (`forex_backtest.py`)│ │ Engine (`auto_trader.py`)
│ - Bar-by-bar pip simulation │ │ - 24/5 Live tick loop   │
│ - Spread friction deduction │ │ - Breakeven Lock (+15p) │
│ - Profit factor, win-rate   │ │ - Trailing Stop (+25p)  │
│ - Max drawdown analysis     │ │ - OANDA & Paper broker  │
└─────────────────────────────┘ └─────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher installed.

### 2. Clone & Install
```bash
git clone https://github.com/<your-username>/alphaforex-studio.git
cd alphaforex-studio
pip install -r requirements.txt
```

*(Or simply install required packages directly: `pip install streamlit pandas numpy altair requests`)*

### 3. Launch the Interactive Dashboard
```bash
python -m streamlit run plain_english_trader/app.py
```
Or double-click `start-forex-trader.bat` on Windows.

Open your browser to: **`http://localhost:8501`**

### 4. Launch Headless 24/5 Daemon (Server / VPS)
Run in the background without needing a web browser open:
```bash
python plain_english_trader/auto_forex_daemon.py --user alex --interval 10
```

---

## 💬 Plain English Strategy Examples

You can type any of the following directly into the prompt box:

| Strategy Type | Everyday Language Input |
|---|---|
| **Trend Following** | *"Buy EUR/USD when 20 EMA crosses above 50 EMA, go short when it crosses below, with 30 pip stop loss and 60 pip take profit"* |
| **RSI Reversal** | *"Go long GBP/USD when RSI 14 drops below 30, go short when RSI is above 70, with 40 pip stop loss and 80 pip take profit"* |
| **Macro Trend** | *"Trend follow USD/JPY above 200 SMA, short below 200 SMA, 50 pip stop loss, 0.2 lots"* |
| **Breakout Scalp** | *"Buy EUR/USD when price breaks 20-period high, go short when it breaks 20-period low, 25 pip stop loss"* |

---

## 📁 Repository Structure

```
plain_english_trader/
├── app.py                  # Streamlit visual dashboard (Traffic lights, charts, gauge)
├── auto_trader.py          # Multi-user autonomous execution engine (Profit Guardian)
├── auto_forex_daemon.py    # Headless 24/5 background terminal runner
├── forex_expert.py         # Indicator suite (EMA, RSI, MACD, BB, ATR) & Currency Strength
├── forex_parser.py         # Plain English natural language strategy compiler
├── forex_data.py           # Real-time Bid/Ask quote poller & candle data fetcher
├── forex_pairs.py          # Forex pip math, spreads, and lot conversion utilities
├── forex_backtest.py       # Bar-by-bar historical pip & PnL backtesting simulator
├── user_manager.py         # Multi-tenant profile manager & risk rule enforcer
└── users/                  # Isolated per-user directories (profiles, strategies, states)
```

---

## 🛡️ Risk Management & Safety Guardrails

AlphaForex incorporates multi-layered risk controls:
* **Per-User Lot Size Caps**: Hard ceiling on position size to prevent over-leveraging.
* **Emergency Circuit Breaker**: Auto-pauses trading if daily drawdown reaches user limit (e.g. 5%).
* **Guaranteed Breakeven Shift**: Removes trade risk once in +15 pips of profit.
* **Paper Sandbox Mode**: All trades run risk-free in simulated accounts by default before connecting live broker keys.

---

## ⚠️ Disclaimer
AlphaForex is designed for educational, research, and algorithmic trading simulation. Foreign exchange trading carries a high level of risk and may not be suitable for all investors. Never trade with money you cannot afford to lose. Always thoroughly backtest and paper-trade strategies before deploying live capital.

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
