# 📈 AlphaPilot: Stock Market Assistant & Autonomous Paper Trader

AlphaPilot is an intelligent quantitative stock market assistant designed specifically for beginners. It features real-time technical scanning, plain-English trade recommendations, institutional risk management (stop-losses and breakeven locks), and automated paper trading execution.

---

## 🌟 Key Features

1. **Market Watchlist Scanner**:
   - Analyzes high-liquidity US equities and index ETFs (`SPY`, `QQQ`, `NVDA`, `AAPL`, `MSFT`, `AMZN`, `GOOGL`, `TSLA`, `AMD`, `PLTR`, `SMH`, `JPM`).
   - Supports looking up any custom US stock symbol.
   - Evaluates multi-factor signals: 20/50/200 EMAs (trend), 14-day RSI (momentum), MACD histogram acceleration, and volume surges.

2. **Traffic-Light Recommendations**:
   - 🟢 **HIGH-CONVICTION BUY SETUP**: Trend, momentum, and volume align for buyers.
   - 🟡 **WAIT / WATCHLIST**: Neutral price action; wait for a pullback.
   - 🔴 **BEARISH / AVOID BUYING**: Downward pressure; protects against emotional buying.

3. **Autonomous Paper Trading Bot**:
   - **$10,000 Simulated Account**: Learn and test strategies with zero financial risk.
   - **Autopilot Mode**: Automatically screens the market, takes safe trades with strict 20% position limits, and manages active holdings.
   - **Breakeven Stop-Lock**: Automatically moves stop-loss to entry price once a trade is up +2.5%, locking in a 100% risk-free trade.
   - **Automated Profit Taking & Safety Stops**: Automatically exits positions when target profit or stop-loss limits are reached.

4. **Visual "Where Is My Money?" Location Tracker**:
   - Visual progress gauges showing each trade's position between the Safety Stop (0%) and Profit Target (100%).
   - Interactive charts with price, entry levels, stop loss, and target bands.

5. **Multi-User Profile Support**:
   - Switch between trader profiles with isolated portfolios and trade histories.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ installed.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/<your-username>/alphapilot-stock-trader.git
cd alphapilot-stock-trader
pip install -r requirements.txt
```

### 3. Run the Application
Start the Streamlit dashboard:
```bash
streamlit run app.py
```
Or simply double-click `run.bat` on Windows.

Open your browser to: **`http://localhost:8501`**

---

## ⚠️ Disclaimer
AlphaPilot is an educational simulation and paper-trading assistant. It does not provide certified financial advice, and paper trading involves no real capital. Never risk real money on active trading without thoroughly understanding market risks.
