"""AlphaPilot: Intelligent Stock Market & Forex Financial Assistant for Beginners.
Features Real-Time Market Scanning, Plain-English Analysis,
Automated Risk-Protected Execution (Paper Trading), and Visual Profit/Loss Location Tracking.
"""

import time
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime

# Stock Market Modules
from stock_expert import (
    STOCK_WATCHLIST,
    generate_stock_recommendation,
    scan_entire_watchlist,
)
from stock_auto_trader import get_user_stock_trader

# Forex Modules
from forex_pairs import FOREX_PAIRS, normalize_pair, get_pip_size
from forex_data import fetch_live_forex_quote
from forex_parser import parse_forex_strategy, ForexStrategySpec
from forex_expert import (
    generate_buy_sell_signal,
    calculate_currency_strength,
    get_current_forex_session,
)
from user_manager import (
    list_users,
    get_user_profile,
    save_user_profile,
    create_default_user,
    get_user_strategies,
    save_user_strategy,
    delete_user_strategy,
)
from auto_trader import get_user_trader

st.set_page_config(
    page_title="AlphaPilot - Intelligent Financial & Stock Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Clean, Modern, Beginner-Friendly Styling
st.markdown(
    """
    <style>
    .big-title {
        font-size: 2.1rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 2px;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 16px;
    }
    .decision-card {
        border-radius: 14px;
        padding: 24px;
        color: white;
        margin-bottom: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .metric-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .location-card {
        background: #FFFFFF;
        border: 2px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .progress-bar-bg {
        height: 22px;
        background: #E2E8F0;
        border-radius: 11px;
        overflow: hidden;
        margin: 12px 0 6px 0;
        position: relative;
    }
    .progress-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #EF4444 0%, #F59E0B 35%, #10B981 100%);
        border-radius: 11px;
        transition: width 0.4s ease;
    }
    .help-box {
        background: #EFF6FF;
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 10px 0;
        font-size: 0.95rem;
        color: #1E3A8A;
    }
    .secret-box {
        background: #FEF3C7;
        border-left: 4px solid #D97706;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 10px 0;
        font-size: 0.95rem;
        color: #78350F;
    }
    .badge-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------- User Management -----------------
all_users = list_users()
user_ids = [u["user_id"] for u in all_users]

if "active_user_id" not in st.session_state:
    st.session_state["active_user_id"] = user_ids[0]

# ----------------- Sidebar -----------------
with st.sidebar:
    st.markdown("### 📊 Market Selection")
    market_mode = st.radio(
        "Choose Your Asset Class:",
        ["📈 US Stock Market (Equities & ETFs)", "💱 Forex Currency Studio"],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 👤 Trader Profile")
    selected_idx = (
        user_ids.index(st.session_state["active_user_id"])
        if st.session_state["active_user_id"] in user_ids
        else 0
    )
    active_user_id = st.selectbox(
        "Active Profile",
        options=user_ids,
        index=selected_idx,
        format_func=lambda uid: next(
            (f"👤 {u['display_name']}" for u in all_users if u["user_id"] == uid), uid
        ),
    )
    st.session_state["active_user_id"] = active_user_id

    # Friendly New Trader Onboarding
    with st.expander("➕ Add New Profile"):
        new_name = st.text_input("Trader Name", placeholder="e.g. Alex Green")
        new_bal = st.number_input("Starting Capital ($)", min_value=500, max_value=100000, value=10000, step=1000)
        if st.button("Create Account", type="primary"):
            if new_name:
                uid = new_name.lower().replace(" ", "_")
                create_default_user(uid, new_name, starting_balance=float(new_bal))
                st.session_state["active_user_id"] = uid
                st.success(f"Welcome, {new_name}! Your account is ready.")
                st.rerun()

    st.markdown("---")

    if "Stock" in market_mode:
        st.markdown("### 🔍 Select Stock to Inspect")
        stock_options = list(STOCK_WATCHLIST.keys())
        selected_stock = st.selectbox(
            "Popular Stocks & ETFs",
            options=stock_options,
            format_func=lambda s: f"{s} - {STOCK_WATCHLIST[s]['name']}",
            index=0,
        )

        custom_input = st.text_input("Or Enter Any US Ticker:", placeholder="e.g. TSLA, PLTR, AMD").strip().upper()
        active_ticker = custom_input if custom_input else selected_stock

        st.markdown("---")
        st.markdown("### ⚙️ Simulator Controls")
        if st.button("🔄 Reset Portfolio to $10,000 Cash", use_container_width=True):
            s_trader = get_user_stock_trader(active_user_id)
            s_trader.reset_portfolio(10000.0)
            st.success("Paper portfolio reset to $10,000 cash!")
            st.rerun()

    else:
        st.markdown("### 💱 Currency Pair")
        pair_labels = {
            "EUR/USD": "🇪🇺 🇺🇸 Euro vs US Dollar (EUR/USD)",
            "GBP/USD": "🇬🇧 🇺🇸 British Pound vs US Dollar (GBP/USD)",
            "USD/JPY": "🇺🇸 🇯🇵 US Dollar vs Japanese Yen (USD/JPY)",
            "AUD/USD": "🇦🇺 🇺🇸 Australian Dollar vs US Dollar (AUD/USD)",
            "USD/CAD": "🇺🇸 🇨🇦 US Dollar vs Canadian Dollar (USD/CAD)",
            "USD/CHF": "🇺🇸 🇨🇭 US Dollar vs Swiss Franc (USD/CHF)",
            "EUR/JPY": "🇪🇺 🇯🇵 Euro vs Japanese Yen (EUR/JPY)",
            "GBP/JPY": "🇬🇧 🇯🇵 British Pound vs Japanese Yen (GBP/JPY)",
        }
        selected_pair = st.selectbox(
            "Select Currency Pair",
            options=list(pair_labels.keys()),
            format_func=lambda p: pair_labels.get(p, p),
            index=0,
        )

    st.markdown("---")
    chart_mode = st.radio(
        "Chart Style",
        ["Simple View (Clean & Easy for Beginners)", "Advanced View (With Technical Lines)"],
        index=0,
    )

    auto_refresh = st.checkbox("Live Refresh (every 5 sec)", value=True)

profile = get_user_profile(active_user_id)


# ======================================================================================
#                              STOCK MARKET ASSISTANT VIEW
# ======================================================================================
if "Stock" in market_mode:
    stock_trader = get_user_stock_trader(active_user_id)
    summary = stock_trader.get_portfolio_summary()
    rec = generate_stock_recommendation(active_ticker)

    # Main Header
    st.markdown('<div class="big-title">📈 AlphaPilot: Stock Market Assistant & Auto-Trader</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Trader: <strong>{profile["display_name"]}</strong> &bull; '
        f'Inspecting: <strong>{active_ticker} ({rec.get("name", active_ticker)})</strong> &bull; '
        f'<span class="badge-pill" style="background:#DCFCE7; color:#166534;">100% Risk-Free Simulation Sandbox</span></div>',
        unsafe_allow_html=True,
    )

    # ----------------- SECTION 1: WHAT TO DO RIGHT NOW -----------------
    st.markdown("## 1. What Should You Do Right Now?")

    if rec["direction"] == "BUY":
        card_bg = "linear-gradient(135deg, #059669 0%, #10B981 100%)"
        badge_icon = "🟢"
    elif rec["direction"] == "SELL":
        card_bg = "linear-gradient(135deg, #DC2626 0%, #EF4444 100%)"
        badge_icon = "🔴"
    else:
        card_bg = "linear-gradient(135deg, #475569 0%, #64748B 100%)"
        badge_icon = "🟡"

    st.markdown(
        f"""
        <div class="decision-card" style="background: {card_bg};">
            <div style="font-size:0.95rem; text-transform:uppercase; letter-spacing:1px; opacity:0.9;">
                AI Financial Advisor Signal &bull; Current Price: ${rec['current_price']:.2f} ({rec['change_pct']:+.2f}%)
            </div>
            <h1 style="margin:6px 0 10px 0; font-size:2.3rem; color:white;">{badge_icon} {rec['simple_headline']}</h1>
            <p style="font-size:1.15rem; margin:0 0 14px 0; opacity:0.95; line-height:1.5;">{rec['simple_summary']}</p>
            <div style="background:rgba(255,255,255,0.15); border-radius:8px; padding:10px 14px; font-size:0.95rem;">
                <strong>Why this recommendation?</strong> {" • ".join(rec['beginner_reasons'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Financial Secret / Educational Box
    st.markdown(
        f"""
        <div class="secret-box">
            <strong>💡 Financial Advisor Secret:</strong><br/>
            {rec['secret_note']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action Controls
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

    with c1:
        if stock_trader.is_running:
            if st.button("🔴 STOP AUTONOMOUS BOT", use_container_width=True, type="secondary"):
                stock_trader.stop()
                st.rerun()
        else:
            if st.button("🟢 START AUTOPILOT (Auto-Scan & Trade)", use_container_width=True, type="primary"):
                stock_trader.start()
                st.success("Autopilot started! Monitoring watchlist and auto-managing trades.")
                st.rerun()

    with c2:
        # Calculate safe allocation share count
        calc_shares = int((summary["total_equity"] * 0.20) // max(1.0, rec["current_price"]))
        calc_shares = max(1, calc_shares)
        if st.button(f"⚡ One-Click Buy {calc_shares}x {active_ticker}", use_container_width=True):
            success, msg = stock_trader.execute_buy(active_ticker, shares=calc_shares)
            if success:
                st.success(msg)
            else:
                st.warning(msg)
            st.rerun()

    with c3:
        if active_ticker in summary["positions"]:
            if st.button(f"🚪 Sell & Close {active_ticker}", use_container_width=True):
                success, msg = stock_trader.execute_sell(active_ticker, reason="Manual Profit Take")
                st.info(msg)
                st.rerun()
        else:
            st.button(f"Not Holding {active_ticker}", disabled=True, use_container_width=True)

    with c4:
        if st.button("🔍 Run Full Market Scan", use_container_width=True):
            st.session_state["force_scan"] = True
            st.rerun()

    st.markdown("---")

    # ----------------- SECTION 2: PORTFOLIO & MONEY LOCATION TRACKER -----------------
    st.markdown("## 2. Your Money & Live Portfolio Location")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Cash Available</div>
                <div class="metric-value" style="color:#0F172A;">${summary['cash']:,.2f}</div>
                <div style="font-size:0.8rem; color:#64748B; margin-top:4px;">Ready to Deploy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Invested in Stocks</div>
                <div class="metric-value" style="color:#2563EB;">${summary['holdings_value']:,.2f}</div>
                <div style="font-size:0.8rem; color:#64748B; margin-top:4px;">{summary['open_count']} Active Holdings</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m3:
        pnl = summary["unrealized_pnl"]
        p_color = "#10B981" if pnl >= 0 else "#EF4444"
        sign = "+" if pnl >= 0 else ""
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Unrealized Profit / Loss</div>
                <div class="metric-value" style="color:{p_color};">{sign}${pnl:,.2f}</div>
                <div style="font-size:0.85rem; font-weight:700; color:{p_color}; margin-top:4px;">Floating Return</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m4:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Total Account Equity</div>
                <div class="metric-value" style="color:#0F172A;">${summary['total_equity']:,.2f}</div>
                <div style="font-size:0.8rem; color:#64748B; margin-top:4px;">Cash + Open Stock Value</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Active Holdings Location Gauges
    if summary["positions"]:
        st.markdown("### 📍 Active Stock Holdings & Target Progress")
        for pos_ticker, pos_info in summary["positions"].items():
            pos_pnl = pos_info["pnl_dollars"]
            pos_color = "#10B981" if pos_pnl >= 0 else "#EF4444"
            pos_sign = "+" if pos_pnl >= 0 else ""
            pos_loc = pos_info["location_pct"]

            st.markdown(
                f"""
                <div class="location-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <h3 style="margin:0; font-size:1.25rem; color:#0F172A;">
                                🏢 <strong>{pos_ticker}</strong> &bull; {pos_info['shares']} Shares @ ${pos_info['entry_price']:.2f}
                            </h3>
                            <span style="font-size:0.88rem; color:#64748B;">
                                Current Price: <strong>${pos_info['current_price']:.2f}</strong> &bull; Total Value: ${pos_info['current_value']:,.2f}
                            </span>
                        </div>
                        <div style="text-align:right;">
                            <span style="font-size:1.5rem; font-weight:800; color:{pos_color};">
                                {pos_sign}${pos_pnl:,.2f} ({pos_sign}{pos_info['pnl_pct']:.2f}%)
                            </span>
                        </div>
                    </div>

                    <!-- Price Level Labels -->
                    <div style="display:flex; justify-content:space-between; margin-top:14px; font-weight:700; font-size:0.9rem;">
                        <span style="color:#EF4444;">🛑 Safety Stop: ${pos_info['sl_price']:.2f}</span>
                        <span style="color:#2563EB;">📍 Entry: ${pos_info['entry_price']:.2f}</span>
                        <span style="color:{pos_color}; font-size:1rem;">👉 YOU ARE HERE: ${pos_info['current_price']:.2f}</span>
                        <span style="color:#10B981;">🎯 Profit Target: ${pos_info['tp_price']:.2f}</span>
                    </div>

                    <!-- Progress Bar -->
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: {pos_loc}%;"></div>
                    </div>

                    <div style="display:flex; justify-content:space-between; font-size:0.82rem; color:#64748B;">
                        <span>0% (Stop Loss)</span>
                        <span style="font-weight:700; color:#0F172A;">{pos_loc:.0f}% on the way to Profit Target</span>
                        <span>100% (Target Hit)</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("💡 You currently have no open stock positions. Click **One-Click Buy** or turn on the **AUTOPILOT** bot above.")

    st.markdown("---")

    # ----------------- SECTION 3: LIVE PRICE CHART -----------------
    st.markdown(f"## 3. Live Price Chart: {active_ticker}")

    if not rec["chart_df"].empty:
        chart_df = rec["chart_df"].copy()
        base = alt.Chart(chart_df).encode(x=alt.X("Date:T", title="Date"))

        if "Simple" in chart_mode:
            # Clean beginner price line
            price_line = base.mark_line(color="#2563EB", strokeWidth=3).encode(
                y=alt.Y("Close:Q", title="Price ($)", scale=alt.Scale(zero=False)),
                tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f", title="Price")],
            )
            chart_layers = price_line

            # Show Target and Stop Loss lines
            entry_v = rec["entry_price"]
            sl_v = rec["stop_loss_price"]
            tp_v = rec["take_profit_price"]

            levels_df = pd.DataFrame([
                {"Goal": "🛑 Safety Stop", "Price": sl_v, "Color": "#EF4444"},
                {"Goal": "🎯 Profit Goal", "Price": tp_v, "Color": "#10B981"},
                {"Goal": "📍 Where You Buy", "Price": entry_v, "Color": "#2563EB"},
            ])
            rule_lines = alt.Chart(levels_df).mark_rule(strokeDash=[6, 4], strokeWidth=2).encode(
                y="Price:Q",
                color=alt.Color("Color:N", scale=None),
                tooltip=["Goal:N", alt.Tooltip("Price:Q", format=".2f")],
            )
            chart_layers = chart_layers + rule_lines
            st.altair_chart(chart_layers.properties(height=340).interactive(), use_container_width=True)
            st.caption("🔵 **Blue Line**: Stock Price &bull; 🟢 **Green Dashed**: Your Profit Goal &bull; 🔴 **Red Dashed**: Safety Net Stop Loss")

        else:
            # Advanced Technical View
            price_line = base.mark_line(color="#2563EB", strokeWidth=2.5).encode(
                y=alt.Y("Close:Q", title="Price ($)", scale=alt.Scale(zero=False)),
                tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f")],
            )
            ema20_line = base.mark_line(color="#10B981", strokeWidth=1.5, strokeDash=[4, 2]).encode(y="EMA_20:Q")
            ema50_line = base.mark_line(color="#F59E0B", strokeWidth=1.5, strokeDash=[4, 2]).encode(y="EMA_50:Q")
            bb_area = base.mark_area(opacity=0.15, color="#38BDF8").encode(y="BB_Upper:Q", y2="BB_Lower:Q")
            adv_chart = bb_area + price_line + ema20_line + ema50_line
            st.altair_chart(adv_chart.properties(height=340).interactive(), use_container_width=True)
            st.caption("🟢 **Fast Trend (20 EMA)** &bull; 🟠 **Medium Trend (50 EMA)** &bull; 🔵 **Bollinger Range**")

    st.markdown("---")

    # ----------------- SECTION 4: MARKET WATCHLIST SCANNER -----------------
    st.markdown("## 4. Market Watchlist Scanner (Ranked by Opportunity)")
    st.write("The scanner evaluates trend alignment, volume surges, and RSI momentum across the entire watchlist:")

    with st.spinner("Scanning market watchlist..."):
        scanned_list = scan_entire_watchlist()

    scan_rows = []
    for item in scanned_list:
        sig_pill = "🟢 BUY" if item["direction"] == "BUY" else ("🟡 WATCH" if item["direction"] == "WATCH" else "🔴 SELL")
        scan_rows.append({
            "Ticker": item["ticker"],
            "Company / ETF": item["name"],
            "Price": f"${item['current_price']:.2f}",
            "Today's Change": f"{item['change_pct']:+.2f}%",
            "AI Recommendation": sig_pill,
            "RSI (Momentum)": item["rsi"],
            "Score": item["score"],
        })

    scan_df = pd.DataFrame(scan_rows)
    st.dataframe(scan_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ----------------- SECTION 5: STOCK MARKET 101 FOR BEGINNERS -----------------
    with st.expander("📚 New to the Stock Market? Read the 60-Second Profit Secrets Guide"):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown(
                """
                #### 1. How Does Stock Market Profit Actually Work?
                * When you own a stock, you own a piece of a real company. You make money when the company grows in value (**Capital Gains**) or pays you cash (**Dividends**).
                * The S&P 500 (SPY) has historically compounded at roughly ~10% per year over the long term, doubling money roughly every 7 years.
                
                #### 2. The Golden Secret: Asymmetric Risk-to-Reward
                * Amateurs think you need to predict the future 90% of the time to make money. **You don't.**
                * Professional traders use a **2:1 or 3:1 Reward-to-Risk ratio**. That means if a trade goes wrong, you lose **$100**, but when it goes right, you make **$200 to $300**.
                * With a 2:1 ratio, even if you are only right **50% of the time**, you are consistently profitable!
                """
            )
        with g2:
            st.markdown(
                """
                #### 3. Why the Stop-Loss is Your Best Friend
                * The #1 reason beginners lose money is holding onto a losing stock hoping it comes back, turning a small 3% loss into a devastating 50% loss.
                * The bot's **automatic stop-loss** eliminates emotion. It cuts bad trades instantly while they are small, protecting your money so you can trade another day.
                
                #### 4. The 2% Position Risk Rule
                * Never risk more than 1% to 2% of your total account on any single trade idea.
                * By spreading your capital across 3 to 5 strong companies or ETFs, no single bad day can ever ruin your portfolio.
                """
            )

    # ----------------- SECTION 6: COMPLETED TRADE HISTORY -----------------
    if summary["trade_history"]:
        with st.expander(f"📜 View Completed Trade History ({len(summary['trade_history'])} Trades)"):
            t_df = pd.DataFrame(summary["trade_history"])
            st.dataframe(t_df, use_container_width=True, hide_index=True)


# ======================================================================================
#                              FOREX STUDIO VIEW (ORIGINAL)
# ======================================================================================
else:
    user_trader = get_user_trader(active_user_id)
    summary = user_trader.get_summary()
    sig = generate_buy_sell_signal(selected_pair)
    session_info = get_current_forex_session()

    st.markdown('<div class="big-title">⚡ AlphaForex: Autonomous Forex Studio</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Welcome back, <strong>{profile["display_name"]}</strong> &bull; '
        f'Active Market: <strong>{selected_pair}</strong> &bull; Market Status: <strong>{session_info["session"]}</strong></div>',
        unsafe_allow_html=True,
    )

    # Forex Traffic Light
    if sig["direction"] == "BUY":
        card_bg = "linear-gradient(135deg, #059669 0%, #10B981 100%)"
        badge_icon = "🟢"
    elif sig["direction"] == "SELL":
        card_bg = "linear-gradient(135deg, #DC2626 0%, #EF4444 100%)"
        badge_icon = "🔴"
    else:
        card_bg = "linear-gradient(135deg, #475569 0%, #64748B 100%)"
        badge_icon = "🟡"

    st.markdown(
        f"""
        <div class="decision-card" style="background: {card_bg};">
            <div style="font-size:0.95rem; text-transform:uppercase; letter-spacing:1px; opacity:0.9;">AI Forex Recommendation</div>
            <h1 style="margin:6px 0 10px 0; font-size:2.4rem; color:white;">{badge_icon} {sig['simple_headline']}</h1>
            <p style="font-size:1.15rem; margin:0 0 14px 0; opacity:0.95; line-height:1.5;">{sig['simple_summary']}</p>
            <div style="background:rgba(255,255,255,0.15); border-radius:8px; padding:10px 14px; font-size:0.95rem;">
                <strong>Why this trade?</strong> {" • ".join(sig['beginner_reasons'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    btn_c1, btn_c2, btn_c3 = st.columns([2, 2, 2])
    with btn_c1:
        if user_trader.is_running:
            if st.button("🔴 STOP FOREX BOT", use_container_width=True, type="secondary"):
                user_trader.stop()
                st.rerun()
        else:
            if st.button("🟢 START FOREX BOT", use_container_width=True, type="primary"):
                user_trader.set_strategy(parse_forex_strategy(f"Trade {selected_pair} with profit protection"))
                user_trader.start()
                st.rerun()

    with btn_c2:
        if st.button(f"⚡ One-Click {sig['direction']} {selected_pair}", use_container_width=True):
            user_trader.set_strategy(parse_forex_strategy(f"Trade {selected_pair} with profit protection"))
            user_trader.tick_cycle()
            st.success("Forex order executed!")
            st.rerun()

    with btn_c3:
        if summary["open_position"]:
            if st.button("🚪 Close Forex Position", use_container_width=True):
                curr_exit = summary["open_position"].get("current_price", summary["open_position"]["entry_price"])
                user_trader._close_position(curr_exit, "Manual One-Click Close")
                st.rerun()
        else:
            st.button("No Trade Open Right Now", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown(f"### Forex Account Balance: ${summary['balance']:,.2f} | Open PnL: ${summary['floating_pnl']:,.2f}")

# Auto-refresh loop
if auto_refresh:
    active_bot = (
        stock_trader.is_running if "Stock" in market_mode else user_trader.is_running
    )
    if active_bot:
        time.sleep(5)
        st.rerun()
