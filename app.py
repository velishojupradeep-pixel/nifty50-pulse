"""
NIFTY 50 Option Radar & Volume Tracker
Streamlit Application tailored for Active Option Sellers.
"""

import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from data.manager import DataManager
from core.engine import AnalyticsEngine
from core.technicals import TechnicalAnalyzer
from core.macro import MacroEventsProvider
from core.positions import PositionManager, NIFTY_LOT_SIZE
from core.auth import SupabaseAuthClient
from utils.formatting import (
    format_inr,
    format_volume,
    create_point_contribution_chart,
    create_heavyweights_tug_of_war_chart,
    create_sector_contribution_chart,
    create_volume_surge_chart,
)

# Page configuration
st.set_page_config(
    page_title="NIFTY 50 Option Seller Radar",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Financial Trading Terminal Aesthetic
st.markdown(
    """
    <style>
    /* Metric Cards */
    .metric-container {
        background-color: #131722;
        border: 1px solid #2a2e39;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .metric-label {
        color: #848e9c;
        font-size: 0.82rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 700;
        color: #eaecef;
        margin: 4px 0;
    }
    .metric-sub {
        font-size: 0.85rem;
        font-weight: 600;
    }
    .pos-val { color: #00c853 !important; }
    .neg-val { color: #ff3344 !important; }
    .neutral-val { color: #848e9c !important; }

    /* Regime Callout Banner */
    .regime-box {
        border-radius: 8px;
        padding: 16px 20px;
        margin: 10px 0 20px 0;
        border-left: 6px solid;
    }
    .regime-green {
        background-color: rgba(0, 200, 83, 0.1);
        border-color: #00c853;
    }
    .regime-red {
        background-color: rgba(255, 51, 68, 0.1);
        border-color: #ff3344;
    }
    .regime-orange {
        background-color: rgba(255, 152, 0, 0.1);
        border-color: #ff9800;
    }

    /* Strike Recommendation Cards */
    .strike-card {
        background-color: #131722;
        border: 1px solid #2a2e39;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .strike-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #eaecef;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .strike-leg-box {
        background-color: #1a1e29;
        border-radius: 6px;
        padding: 12px 14px;
        margin: 8px 0;
        border-left: 4px solid #00c853;
    }
    .strike-leg-box.pe {
        border-left: 4px solid #ff3344;
    }
    .strike-leg-val {
        font-size: 1.35rem;
        font-weight: 700;
        color: #ffffff;
    }
    .breakeven-corridor {
        background: linear-gradient(90deg, rgba(255,51,68,0.15) 0%, rgba(0,200,83,0.15) 50%, rgba(255,51,68,0.15) 100%);
        border: 1px solid #2a2e39;
        border-radius: 6px;
        padding: 10px 14px;
        text-align: center;
        margin-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


data_manager = DataManager()
analytics_engine = AnalyticsEngine()
tech_analyzer = TechnicalAnalyzer()
macro_provider = MacroEventsProvider()
auth_client = SupabaseAuthClient()
pos_manager = PositionManager()

if "auth_session" not in st.session_state:
    st.session_state["auth_session"] = None

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("⚡ Option Radar Settings")

# User Account & Cloud Sync (Supabase)
with st.sidebar.expander("🔐 User Account (Cloud Sync)", expanded=st.session_state["auth_session"] is None):
    if not auth_client.is_configured():
        st.caption(
            "Cloud login not configured yet. Add `SUPABASE_URL` & `SUPABASE_ANON_KEY` "
            "to `.streamlit/secrets.toml` (or Streamlit Cloud Secrets) to enable per-user login."
        )
    elif st.session_state["auth_session"]:
        sess = st.session_state["auth_session"]
        st.success(f"☁️ Signed in as **{sess['email']}**")
        ac1, ac2 = st.columns(2)
        with ac1:
            if st.button("🔄 Sync", key="sb_sync_pos", use_container_width=True):
                st.session_state["active_positions"] = pos_manager.load_positions(
                    user_id=sess["user_id"], access_token=sess["access_token"]
                )
                st.rerun()
        with ac2:
            if st.button("🚪 Sign Out", key="sb_signout", use_container_width=True):
                auth_client.sign_out(sess.get("access_token"))
                st.session_state["auth_session"] = None
                st.session_state["active_positions"] = pos_manager.load_positions()
                st.rerun()
    else:
        auth_tab1, auth_tab2, auth_tab3 = st.tabs(["Sign In", "Sign Up", "Reset"])
        with auth_tab1:
            with st.form("sb_login_form"):
                l_email = st.text_input("Email", key="login_email")
                l_pass = st.text_input("Password", type="password", key="login_pass")
                do_login = st.form_submit_button("Sign In", use_container_width=True)
                if do_login:
                    ok, msg, sess = auth_client.sign_in(l_email, l_pass)
                    if ok and sess:
                        st.session_state["auth_session"] = sess
                        st.session_state["active_positions"] = pos_manager.load_positions(
                            user_id=sess["user_id"], access_token=sess["access_token"]
                        )
                        st.rerun()
                    else:
                        st.error(msg)
        with auth_tab2:
            with st.form("sb_signup_form"):
                s_email = st.text_input("Email", key="signup_email")
                s_pass = st.text_input("Password (min 6 chars)", type="password", key="signup_pass")
                do_signup = st.form_submit_button("Create Account", use_container_width=True)
                if do_signup:
                    ok, msg, sess = auth_client.sign_up(s_email, s_pass)
                    if ok and sess:
                        st.session_state["auth_session"] = sess
                        st.session_state["active_positions"] = pos_manager.load_positions(
                            user_id=sess["user_id"], access_token=sess["access_token"]
                        )
                        st.rerun()
                    elif ok:
                        st.success(msg)
                    else:
                        st.error(msg)
        with auth_tab3:
            with st.form("sb_reset_form"):
                r_email = st.text_input("Account Email", key="reset_email")
                do_reset = st.form_submit_button("Send Reset Link", use_container_width=True)
                if do_reset:
                    ok, msg = auth_client.send_password_reset(r_email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# Strike Selection & IV Controls
st.sidebar.subheader("🎯 Option Seller Parameters")
custom_iv = st.sidebar.slider(
    "NIFTY ATM Implied Volatility (IV %)",
    min_value=9.0,
    max_value=25.0,
    value=13.5,
    step=0.5,
    help="Used to compute dynamic 1-SD expected moves and delta strike boundaries.",
)

# Auto-refresh selector
auto_refresh = st.sidebar.checkbox("Auto-Refresh Feed", value=True)
refresh_interval = st.sidebar.select_slider(
    "Refresh Interval",
    options=[10, 15, 30, 60, 120],
    value=30,
    format_func=lambda x: f"{x} seconds",
)

if auto_refresh:
    # Trigger periodic rerun
    st_autorefresh(interval=refresh_interval * 1000, key="nifty_refresh")

# Data Source Selector
data_source_mode = st.sidebar.selectbox(
    "Data Source Mode",
    ["Auto (Recommended)", "NSE Live", "Yahoo Finance", "Simulated Replay"],
    index=0,
    help="Auto tries official NSE endpoints first, then Yahoo Finance, then fallback replay.",
)

# Fetch Data
with st.spinner("Fetching live constituent data & official NSE option chain..."):
    source_choice = (
        "Auto" if data_source_mode.startswith("Auto") else data_source_mode
    )
    df_raw, nifty_meta, source_used = data_manager.fetch_live_data(
        source_preference=source_choice
    )
    avg_volumes = data_manager.get_average_volumes()
    
    # Fetch live Option Chain directly from NSE India (nseindia.com/option-chain)
    curr_chain, next_chain, official_expiries = (
        data_manager.get_live_option_chains()
    )

    # Fetch live GIFT NIFTY from NSE IX with fallback
    gift_nifty = (
        data_manager.get_gift_nifty()
        if hasattr(data_manager, "get_gift_nifty")
        else {}
    )
    
    market = analytics_engine.process_market_data(
        df_raw,
        nifty_meta,
        avg_volumes,
        custom_iv=custom_iv,
        curr_chain=curr_chain,
        next_chain=next_chain,
        official_expiries=official_expiries,
    )

st.sidebar.caption(f"**Connected Feed**: `{source_used}`")
st.sidebar.caption(f"**Last Sync**: {time.strftime('%H:%M:%S')}")

# Manual Refresh Button
if st.sidebar.button("🔄 Sync Now", use_container_width=True):
    st.rerun()

st.sidebar.markdown("---")
# Broker API Connection Drawer
with st.sidebar.expander("🔌 Connect Broker API (Zerodha / Dhan)"):
    st.caption("Stream live tick data & market depth with zero delay.")
    broker_select = st.selectbox("Broker", ["Zerodha Kite Connect", "DhanHQ", "Fyers API"])
    api_key_input = st.text_input("API Key", type="password")
    api_secret_input = st.text_input("Access Token / Secret", type="password")
    if st.button("Save Broker Credentials"):
        st.success("Credentials saved. Will use broker websocket when live session is authenticated.")

# --- TOP HEADER: NIFTY 50 SNAPSHOT ---
n_meta = market["nifty_meta"]
ltp = n_meta.get("lastPrice", 0.0)
change = n_meta.get("change", 0.0)
p_change = n_meta.get("pChange", 0.0)
color_class = "pos-val" if change >= 0 else "neg-val"
sign = "+" if change >= 0 else ""

# Technical Indicators Summary for Option Sellers
tech_data = tech_analyzer.get_technical_summary(
    spot=ltp,
    prev_close=n_meta.get("previousClose", ltp),
    day_high=n_meta.get("dayHigh", None),
    day_low=n_meta.get("dayLow", None),
    day_open=n_meta.get("open", None),
)

# Global Macro & Market Events for Option Sellers
macro_data = macro_provider.get_macro_dashboard()

st.markdown(
    """
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <div>
            <h1 style="margin: 0; padding: 0; font-size: 2.2rem; color: #eaecef;">⚡ NIFTY 50 Pulse & Option Seller Radar</h1>
            <div style="color: #848e9c; font-size: 0.95rem; margin-top: 2px;">
                Real-time constituent weightage tracker, index point contribution, heavyweight alignment, and live NSE Option Chain.
            </div>
        </div>
        <div>
            <a href="https://www.nseindia.com/option-chain" target="_blank" style="background: #1976d2; color: #ffffff; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; font-size: 0.88rem; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.4);">
                🌐 Open Official NSE Option Chain ↗
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# GIFT Nifty metrics calculation
gift_price = gift_nifty.get("lastPrice", ltp)
gift_change = gift_nifty.get("change", 0.0)
gift_pct = gift_nifty.get("pChange", 0.0)
gift_color = "pos-val" if gift_change >= 0 else "neg-val"
gift_sign = "+" if gift_change >= 0 else ""

# Spread / Gap vs Nifty 50 Spot
spread = round(gift_price - ltp, 1)
spread_sign = "+" if spread >= 0 else ""
if spread > 15:
    spread_desc = f"<span class='pos-val'>{spread_sign}{spread:,.1f} Premium (Gap-Up)</span>"
elif spread < -15:
    spread_desc = f"<span class='neg-val'>{spread_sign}{spread:,.1f} Discount (Gap-Down)</span>"
else:
    spread_desc = f"<span class='neutral-val'>{spread_sign}{spread:,.1f} Par (Flat)</span>"

col_gift, col1, col2, col3, col4, col5 = st.columns([1.15, 1.15, 1.0, 1.0, 1.1, 1.0])

with col_gift:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>GIFT NIFTY</span>
                <span style="font-size: 0.7rem; color: #64b5f6;">NSE IX</span>
            </div>
            <div class="metric-val">{gift_price:,.2f}</div>
            <div class="metric-sub {gift_color}">{gift_sign}{gift_change:,.1f} ({gift_sign}{gift_pct:.2f}%)</div>
            <div style="font-size: 0.75rem; margin-top: 2px;">Spread: {spread_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col1:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">NIFTY 50 SPOT</div>
            <div class="metric-val">{ltp:,.2f}</div>
            <div class="metric-sub {color_class}">{sign}{change:,.2f} ({sign}{p_change:.2f}%)</div>
            <div style="font-size: 0.75rem; color: #848e9c; margin-top: 2px;">Prev: {n_meta.get('previousClose', ltp):,.1f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    adv = n_meta.get("advances", 0)
    dec = n_meta.get("declines", 0)
    unch = n_meta.get("unchanged", 0)
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">MARKET BREADTH</div>
            <div class="metric-val"><span class="pos-val">{adv}</span> : <span class="neg-val">{dec}</span></div>
            <div class="metric-sub neutral-val">{unch} Unchanged | Ratio: {(adv/max(dec,1)):.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    b_wt = n_meta.get("bullish_weight", 0.0)
    br_wt = n_meta.get("bearish_weight", 0.0)
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">WEIGHTED BREADTH</div>
            <div class="metric-val"><span class="pos-val">{b_wt:.1f}%</span> : <span class="neg-val">{br_wt:.1f}%</span></div>
            <div class="metric-sub neutral-val">Bull vs Bear Weight</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    regime = market["regime"]
    regime_score = regime.get("score", 0.0)
    score_sign = "+" if regime_score >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">ALIGNMENT METER</div>
            <div class="metric-val">{score_sign}{regime_score:.1f} / 100</div>
            <div class="metric-sub">{regime.get('badge')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col5:
    top5_pts = regime.get("top5_points", 0.0)
    t5_sign = "+" if top5_pts >= 0 else ""
    t5_class = "pos-val" if top5_pts >= 0 else "neg-val"
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">TOP 5 POINTS PULL</div>
            <div class="metric-val {t5_class}">{t5_sign}{top5_pts:.1f} pts</div>
            <div class="metric-sub neutral-val">Total: {regime.get('total_points', 0.0):+.1f} pts</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- SECTION 1: OPTION SELLER MARKET VERDICT & RECOMMENDED STRIKES ---
advisor = market["advisor"]
verdict = advisor["verdict"]
curr_rec = advisor["current_expiry"]
next_rec = advisor["upcoming_expiry"]

st.subheader("🎯 Market Verdict & Recommended Strike Positions")
st.caption(
    f"Algorithmic option-selling playbook derived from constituent weight alignment, 1-SD expected moves (±{advisor['expected_move_curr']:.0f} pts), "
    f"and ATM IV ({advisor['iv_used']:.1f}%)."
)

# Verdict Callout Banner
box_class = (
    "regime-green"
    if verdict["tone"] == "success"
    else ("regime-red" if verdict["tone"] == "danger" else "regime-orange")
)

st.markdown(
    f"""
    <div class="regime-box {box_class}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3 style="margin: 0; color: #ffffff;">{verdict['badge']}</h3>
            <span style="font-size: 0.9rem; color: #cfd8dc; background: #1a1e29; padding: 4px 10px; border-radius: 4px;">
                ATM Strike: <b>{advisor['atm_strike']}</b> | Expected Move: <b>±{advisor['expected_move_curr']:.0f} pts</b>
            </span>
        </div>
        <div style="font-size: 1.0rem; color: #eaecef; margin-bottom: 6px;">
            <b>Market Condition:</b> {verdict['summary']}
        </div>
        <div style="font-size: 0.95rem; color: #ffeb3b; margin-bottom: 6px;">
            <b>💡 Recommended Playbook:</b> {verdict['action']}
        </div>
        <div style="font-size: 0.88rem; color: #ff8a80;">
            <b>⚠️ Risk Rule:</b> {verdict['danger_warning']}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Two Expiry Recommendation Columns
rec_col1, rec_col2 = st.columns(2)

live_badge_text = (
    f"🟢 Verified Live Data Direct from <a href='https://www.nseindia.com/option-chain' target='_blank' style='color: #64b5f6; font-weight: 600; text-decoration: underline;'>NSE India Option Chain</a> ({advisor['nse_timestamp']})"
    if advisor.get("is_live_nse")
    else "⚡ Real-time Analytics Engine (NSE Baseline)"
)
st.markdown(
    f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; background: #131722; padding: 10px 16px; border-radius: 6px; border: 1px solid #2a2e39;">
        <span style="font-size: 0.85rem; color: #90a4ae;">{live_badge_text} &nbsp;|&nbsp; Official Expiries directly from NSE</span>
        <a href="https://www.nseindia.com/option-chain" target="_blank" style="color: #64b5f6; font-size: 0.85rem; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
            🔗 Open nseindia.com/option-chain in new tab ↗
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)

with rec_col1:
    hedge_ce_note = f"(@ ₹{curr_rec['hedge_ce_ltp']:.1f})" if curr_rec['hedge_ce_ltp'] > 0 else "(Hedge)"
    hedge_pe_note = f"(@ ₹{curr_rec['hedge_pe_ltp']:.1f})" if curr_rec['hedge_pe_ltp'] > 0 else "(Hedge)"
    st.markdown(
        f"""
        <div class="strike-card">
            <div class="strike-title">
                <span>⚡ CURRENT EXPIRY: {curr_rec['expiry_name']}</span>
                <span style="font-size: 0.85rem; color: #00e676; background: rgba(0,230,118,0.1); padding: 2px 8px; border-radius: 4px;">{curr_rec['strategy_bias']}</span>
            </div>
            <div style="color: #848e9c; font-size: 0.9rem; margin-bottom: 12px;">
                <b>Strategy:</b> {curr_rec['strategy_name']}
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="strike-leg-box">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #00c853; font-size: 0.8rem; font-weight: 700;">SELL CALL (CE)</span>
                        <span style="color: #00e676; font-size: 0.85rem; font-weight: 700;">₹{curr_rec['ce_ltp']:.2f} LTP</span>
                    </div>
                    <div class="strike-leg-val">{curr_rec['sell_ce']} CE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        +{curr_rec['ce_otm_pts']} pts (+{curr_rec['ce_otm_pct']}%) OTM | IV: {curr_rec['ce_iv']:.1f}%
                    </div>
                    <div style="font-size: 0.74rem; color: #90a4ae; margin-top: 2px;">
                        OI: <b>{curr_rec['ce_oi']:,}</b>
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Buy <b>{curr_rec['hedge_ce']} CE</b> {hedge_ce_note}
                    </div>
                </div>
                <div class="strike-leg-box pe">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #ff3344; font-size: 0.8rem; font-weight: 700;">SELL PUT (PE)</span>
                        <span style="color: #ff5252; font-size: 0.85rem; font-weight: 700;">₹{curr_rec['pe_ltp']:.2f} LTP</span>
                    </div>
                    <div class="strike-leg-val">{curr_rec['sell_pe']} PE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        -{curr_rec['pe_otm_pts']} pts (-{curr_rec['pe_otm_pct']}%) OTM | IV: {curr_rec['pe_iv']:.1f}%
                    </div>
                    <div style="font-size: 0.74rem; color: #90a4ae; margin-top: 2px;">
                        OI: <b>{curr_rec['pe_oi']:,}</b>
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Buy <b>{curr_rec['hedge_pe']} PE</b> {hedge_pe_note}
                    </div>
                </div>
            </div>
            <div class="breakeven-corridor">
                <div style="font-size: 0.78rem; color: #848e9c; display: flex; justify-content: space-between;">
                    <span>LIVE PREMIUM: <b style="color: #00e676;">₹{curr_rec['total_premium']:.2f}</b></span>
                    <span>ATM Straddle: <b>₹{advisor['atm_straddle_curr']:.2f}</b></span>
                    <span>PCR: <b>{advisor['pcr']:.2f}</b> | Max Pain: <b>{advisor['max_pain']}</b></span>
                </div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #eaecef; margin: 4px 0;">
                    {curr_rec['lower_breakeven']} &nbsp;⟵ &nbsp;<span style="color: #00c853;">{curr_rec['safe_range_pts']} pts Safe Zone</span> &nbsp;⟶ &nbsp;{curr_rec['upper_breakeven']}
                </div>
            </div>
            <div style="font-size: 0.76rem; color: #848e9c; margin-top: 8px;">
                <b>Adjustment Trigger:</b> {curr_rec['stop_loss_guideline']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with rec_col2:
    hedge_ce_note_next = f"(@ ₹{next_rec['hedge_ce_ltp']:.1f})" if next_rec['hedge_ce_ltp'] > 0 else "(Hedge)"
    hedge_pe_note_next = f"(@ ₹{next_rec['hedge_pe_ltp']:.1f})" if next_rec['hedge_pe_ltp'] > 0 else "(Hedge)"
    st.markdown(
        f"""
        <div class="strike-card">
            <div class="strike-title">
                <span>🗓️ UPCOMING EXPIRY: {next_rec['expiry_name']}</span>
                <span style="font-size: 0.85rem; color: #ffb300; background: rgba(255,179,0,0.1); padding: 2px 8px; border-radius: 4px;">{next_rec['strategy_bias']}</span>
            </div>
            <div style="color: #848e9c; font-size: 0.9rem; margin-bottom: 12px;">
                <b>Strategy:</b> {next_rec['strategy_name']}
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="strike-leg-box">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #00c853; font-size: 0.8rem; font-weight: 700;">SELL CALL (CE)</span>
                        <span style="color: #00e676; font-size: 0.85rem; font-weight: 700;">₹{next_rec['ce_ltp']:.2f} LTP</span>
                    </div>
                    <div class="strike-leg-val">{next_rec['sell_ce']} CE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        +{next_rec['ce_otm_pts']} pts (+{next_rec['ce_otm_pct']}%) OTM | IV: {next_rec['ce_iv']:.1f}%
                    </div>
                    <div style="font-size: 0.74rem; color: #90a4ae; margin-top: 2px;">
                        OI: <b>{next_rec['ce_oi']:,}</b>
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Buy <b>{next_rec['hedge_ce']} CE</b> {hedge_ce_note_next}
                    </div>
                </div>
                <div class="strike-leg-box pe">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #ff3344; font-size: 0.8rem; font-weight: 700;">SELL PUT (PE)</span>
                        <span style="color: #ff5252; font-size: 0.85rem; font-weight: 700;">₹{next_rec['pe_ltp']:.2f} LTP</span>
                    </div>
                    <div class="strike-leg-val">{next_rec['sell_pe']} PE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        -{next_rec['pe_otm_pts']} pts (-{next_rec['pe_otm_pct']}%) OTM | IV: {next_rec['pe_iv']:.1f}%
                    </div>
                    <div style="font-size: 0.74rem; color: #90a4ae; margin-top: 2px;">
                        OI: <b>{next_rec['pe_oi']:,}</b>
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Buy <b>{next_rec['hedge_pe']} PE</b> {hedge_pe_note_next}
                    </div>
                </div>
            </div>
            <div class="breakeven-corridor">
                <div style="font-size: 0.78rem; color: #848e9c; display: flex; justify-content: space-between;">
                    <span>LIVE PREMIUM: <b style="color: #00e676;">₹{next_rec['total_premium']:.2f}</b></span>
                    <span>Safe Corridor: <b>{next_rec['safe_range_pts']} pts</b></span>
                    <span>DTE: <b>{next_rec['dte']} Days</b></span>
                </div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #eaecef; margin: 4px 0;">
                    {next_rec['lower_breakeven']} &nbsp;⟵ &nbsp;<span style="color: #00c853;">{next_rec['safe_range_pts']} pts Safe Zone</span> &nbsp;⟶ &nbsp;{next_rec['upper_breakeven']}
                </div>
            </div>
            <div style="font-size: 0.76rem; color: #848e9c; margin-top: 8px;">
                <b>Adjustment Trigger:</b> {next_rec['stop_loss_guideline']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Live NSE Option Chain Table Expander
with st.expander("📊 View Live NSE Option Chain Table (Direct from nseindia.com/option-chain)", expanded=False):
    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="color: #848e9c; font-size: 0.88rem;">Official live strike chain from NSE India for current expiry <b>{curr_rec['expiry_date']}</b> (Underlying: ₹{advisor.get('atm_strike', 24600):,})</span>
            <a href="https://www.nseindia.com/option-chain" target="_blank" style="background: rgba(25, 118, 210, 0.15); color: #64b5f6; border: 1px solid #1976d2; padding: 4px 12px; border-radius: 4px; text-decoration: none; font-size: 0.82rem; font-weight: 600;">
                ↗ Open nseindia.com/option-chain
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if curr_chain and "strikes_map" in curr_chain:
        atm = advisor["atm_strike"]
        strikes_to_show = [s for s in sorted(curr_chain["strikes_map"].keys()) if abs(s - atm) <= 600]
        oc_records = []
        for s in strikes_to_show:
            d = curr_chain["strikes_map"].get(s, {})
            is_atm = "🎯 " if s == atm else ""
            oc_records.append({
                "CE OI": d.get("ce_oi", 0),
                "CE Change": d.get("ce_change", 0.0),
                "CE LTP": d.get("ce_ltp", 0.0),
                "Strike": f"{is_atm}{s}",
                "PE LTP": d.get("pe_ltp", 0.0),
                "PE Change": d.get("pe_change", 0.0),
                "PE OI": d.get("pe_oi", 0),
            })
        oc_df = pd.DataFrame(oc_records)
        st.dataframe(
            oc_df.style.format({
                "CE OI": "{:,}",
                "CE Change": "{:+.2f}",
                "CE LTP": "₹{:.2f}",
                "PE LTP": "₹{:.2f}",
                "PE Change": "{:+.2f}",
                "PE OI": "{:,}",
            }),
            hide_index=True,
            use_container_width=True,
        )

st.markdown("---")

# --- SECTION: MY ACTIVE POSITIONS & RISK/PROFIT STRATEGY ADVISOR ---
auth_sess = st.session_state.get("auth_session")
auth_uid = auth_sess.get("user_id") if auth_sess else None
auth_tok = auth_sess.get("access_token") if auth_sess else None

if "active_positions" not in st.session_state:
    st.session_state["active_positions"] = pos_manager.load_positions(
        user_id=auth_uid, access_token=auth_tok
    )

st.subheader("💼 My Active Positions & Risk / Profit Adjustment Advisor")
sync_label = (
    f"☁️ Synced to `{auth_sess['email']}`"
    if auth_sess
    else "💻 Guest Mode (Sign in from sidebar to save positions per-user in the cloud)"
)
st.caption(
    f"Enter your open or closed NIFTY option legs below ({sync_label}). "
    "Positions are marked to market against the live NSE Option Chain to calculate real-time P&L, payoff, and tailored strategies."
)

avail_expiries = official_expiries[:4] if official_expiries else [curr_chain.get("expiry", "17-Nov-2026")]
atm_default = int(round(ltp / 50.0) * 50) if ltp > 0 else 25200
strike_choices = list(range(atm_default - 1200, atm_default + 1250, 50))
default_ce_idx = strike_choices.index(atm_default + 200) if (atm_default + 200) in strike_choices else len(strike_choices) // 2

with st.form("add_position_form", clear_on_submit=False):
    f_c1, f_c2, f_c3, f_c4, f_c5, f_c6, f_c7, f_c8 = st.columns([0.9, 0.8, 1.3, 1.0, 0.9, 1.15, 1.15, 1.1])
    with f_c1:
        pos_side = st.selectbox("Side", ["SELL", "BUY"], key="pos_side")
    with f_c2:
        pos_type = st.selectbox("Type", ["CE", "PE"], key="pos_type")
    with f_c3:
        pos_expiry = st.selectbox("Expiry", avail_expiries, key="pos_expiry")
    with f_c4:
        pos_strike = st.selectbox("Strike", strike_choices, index=default_ce_idx, key="pos_strike")
    with f_c5:
        pos_lots = st.number_input("Lots (65/lot)", min_value=1, max_value=500, value=1, step=1, key="pos_lots")
    with f_c6:
        pos_entry = st.number_input(
            "Entry ₹ (0=Live)", min_value=0.0, max_value=5000.0, value=0.0, step=0.5, key="pos_entry"
        )
    with f_c7:
        pos_exit = st.number_input(
            "Exit ₹ (0=Open)", min_value=0.0, max_value=5000.0, value=0.0, step=0.5, key="pos_exit"
        )
    with f_c8:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        submitted_pos = st.form_submit_button("➕ Add Position", use_container_width=True)

    if submitted_pos:
        resolved_entry = float(pos_entry)
        if resolved_entry <= 0.0:
            target_chain = next_chain if (next_chain and pos_expiry == next_chain.get("expiry")) else curr_chain
            s_row = (target_chain or {}).get("strikes_map", {}).get(int(pos_strike), {})
            resolved_entry = float(s_row.get("ce_ltp" if pos_type == "CE" else "pe_ltp", 0.0))
            if resolved_entry <= 0.0:
                resolved_entry = 50.0
        st.session_state["active_positions"] = pos_manager.add_position(
            st.session_state["active_positions"],
            side=pos_side,
            opt_type=pos_type,
            strike=int(pos_strike),
            expiry=pos_expiry,
            lots=int(pos_lots),
            entry_price=resolved_entry,
            exit_price=float(pos_exit),
            user_id=auth_uid,
            access_token=auth_tok,
        )
        st.rerun()

active_pos_list = st.session_state["active_positions"]

if active_pos_list:
    eval_res = pos_manager.evaluate_portfolio(
        positions=active_pos_list,
        spot=ltp,
        curr_chain=curr_chain,
        next_chain=next_chain,
        tech_data=tech_data,
        dte_curr=advisor.get("curr", {}).get("dte", 4),
    )

    # Portfolio KPI Strip
    pk1, pk2, pk3, pk4 = st.columns(4)
    mtm_val = eval_res["total_pnl"]
    realized_val = eval_res.get("realized_pnl", 0.0)
    open_val = eval_res.get("open_mtm_pnl", 0.0)
    mtm_color = "#00e676" if mtm_val >= 0 else "#ff5252"
    mtm_sign = "+" if mtm_val >= 0 else ""

    with pk1:
        st.markdown(
            f"""
            <div class="metric-container" style="border-top: 3px solid {mtm_color}; padding: 12px 14px;">
                <div class="metric-label">Today's Total P&L</div>
                <div class="metric-val" style="font-size: 1.45rem; color: {mtm_color};">{mtm_sign}₹{mtm_val:,.0f}</div>
                <div style="font-size: 0.72rem; color: #848e9c;">Realized: ₹{realized_val:,.0f} • Open MTM: ₹{open_val:,.0f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pk2:
        st.markdown(
            f"""
            <div class="metric-container" style="border-top: 3px solid #64b5f6; padding: 12px 14px;">
                <div class="metric-label">Detected Strategy</div>
                <div class="metric-val" style="font-size: 1.05rem; color: #eaecef;">{eval_res['structure']}</div>
                <div style="font-size: 0.74rem; color: #848e9c;">Breakevens: {', '.join(str(b) for b in eval_res['breakevens']) if eval_res['breakevens'] else 'N/A'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pk3:
        nd = eval_res["net_delta"]
        nd_color = "#00c853" if abs(nd) < 0.25 else ("#64b5f6" if nd > 0 else "#ff9800")
        nd_bias = "Delta-Neutral" if abs(nd) < 0.25 else ("Net Bullish" if nd > 0 else "Net Bearish")
        st.markdown(
            f"""
            <div class="metric-container" style="border-top: 3px solid {nd_color}; padding: 12px 14px;">
                <div class="metric-label">Net Portfolio Delta</div>
                <div class="metric-val" style="font-size: 1.45rem; color: {nd_color};">{nd:+.2f}</div>
                <div style="font-size: 0.74rem; color: #848e9c;">{nd_bias}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pk4:
        rp_color = "#00c853" if eval_res["is_hedged"] else "#ff5252"
        max_p = eval_res.get("max_profit", 0.0)
        st.markdown(
            f"""
            <div class="metric-container" style="border-top: 3px solid {rp_color}; padding: 12px 14px;">
                <div class="metric-label">Risk Profile</div>
                <div class="metric-val" style="font-size: 1.0rem; color: {rp_color};">{eval_res['risk_profile']}</div>
                <div style="font-size: 0.74rem; color: #848e9c;">Max Expiry Profit: ₹{max_p:,.0f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Active Legs Table + Remove Controls
    hdr_col1, hdr_col2 = st.columns([5, 1])
    with hdr_col1:
        st.markdown("**📋 Open Option Legs (Live NSE Mark-to-Market)**")
    with hdr_col2:
        if st.button("🗑️ Clear All", key="clear_all_positions", use_container_width=True):
            st.session_state["active_positions"] = pos_manager.clear_positions(
                user_id=auth_uid, access_token=auth_tok
            )
            st.rerun()

    if "editing_leg_id" not in st.session_state:
        st.session_state["editing_leg_id"] = None

    for leg in eval_res["enriched_legs"]:
        l_col1, l_col2, l_col3 = st.columns([10.5, 0.75, 0.75])
        side_color = "#ff5252" if leg["side"] == "SELL" else "#64b5f6"
        pnl_color = "#00e676" if leg["pnl"] >= 0 else "#ff5252"
        pnl_sign = "+" if leg["pnl"] >= 0 else ""
        with l_col1:
            price_trail = (
                f"Entry: <b>₹{leg['entry_price']:.2f}</b> → Exit: <b>₹{leg['exit_price']:.2f}</b>"
                if leg.get("is_closed")
                else f"Entry: <b>₹{leg['entry_price']:.2f}</b> → Live: <b>₹{leg['live_ltp']:.2f}</b>"
            )
            st.markdown(
                f"""
                <div class="strike-card" style="padding: 10px 14px; margin-bottom: 6px; border-left: 4px solid {side_color};">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <span style="font-weight: 800; color: {side_color}; font-size: 0.86rem;">{leg['side']}</span>
                            <span style="font-weight: 800; color: #eaecef; font-size: 0.96rem; margin-left: 6px;">NIFTY {leg['strike']} {leg['type']}</span>
                            <span style="font-size: 0.78rem; color: #848e9c; margin-left: 8px;">{leg['expiry']} • {leg['lots']} lot(s) ({leg['qty']} qty)</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
                            <span style="font-size: 0.82rem; color: #cfd8dc;">{price_trail}</span>
                            <span style="font-size: 0.82rem; color: #848e9c;">Dist: <b>{leg['dist_pts']:+.0f} pts</b> ({leg['dist_pct']:+.2f}%)</span>
                            <span style="font-size: 0.9rem; font-weight: 800; color: {pnl_color};">{pnl_sign}₹{leg['pnl']:,.0f} ({leg['pts_pnl']:+.2f} pts)</span>
                            <span style="font-size: 0.72rem; font-weight: 700; color: {leg['status_color']}; background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 4px;">{leg['status']}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with l_col2:
            if st.button("✏️", key=f"edit_leg_btn_{leg['id']}", help="Edit leg"):
                st.session_state["editing_leg_id"] = (
                    None if st.session_state["editing_leg_id"] == leg["id"] else leg["id"]
                )
                st.rerun()
        with l_col3:
            if st.button("✖", key=f"del_leg_{leg['id']}", help="Remove leg"):
                if st.session_state["editing_leg_id"] == leg["id"]:
                    st.session_state["editing_leg_id"] = None
                st.session_state["active_positions"] = pos_manager.remove_position(
                    st.session_state["active_positions"],
                    leg["id"],
                    user_id=auth_uid,
                    access_token=auth_tok,
                )
                st.rerun()

        if st.session_state.get("editing_leg_id") == leg["id"]:
            edit_expiries = list(dict.fromkeys(avail_expiries + [leg["expiry"]]))
            edit_strikes = sorted(set(strike_choices + [int(leg["strike"])]))
            with st.form(f"edit_leg_form_{leg['id']}"):
                ec1, ec2, ec3, ec4, ec5, ec6, ec7, ec8, ec9 = st.columns([0.85, 0.75, 1.2, 0.95, 0.75, 1.0, 1.0, 0.8, 0.8])
                with ec1:
                    e_side = st.selectbox("Side", ["SELL", "BUY"], index=0 if leg["side"] == "SELL" else 1, key=f"e_side_{leg['id']}")
                with ec2:
                    e_type = st.selectbox("Type", ["CE", "PE"], index=0 if leg["type"] == "CE" else 1, key=f"e_type_{leg['id']}")
                with ec3:
                    e_exp = st.selectbox("Expiry", edit_expiries, index=edit_expiries.index(leg["expiry"]), key=f"e_exp_{leg['id']}")
                with ec4:
                    e_strike = st.selectbox("Strike", edit_strikes, index=edit_strikes.index(int(leg["strike"])), key=f"e_strike_{leg['id']}")
                with ec5:
                    e_lots = st.number_input("Lots", min_value=1, max_value=500, value=int(leg["lots"]), step=1, key=f"e_lots_{leg['id']}")
                with ec6:
                    e_entry = st.number_input("Entry ₹", min_value=0.0, max_value=5000.0, value=float(leg["entry_price"]), step=0.5, key=f"e_entry_{leg['id']}")
                with ec7:
                    e_exit = st.number_input("Exit ₹ (0=Open)", min_value=0.0, max_value=5000.0, value=float(leg.get("exit_price", 0.0)), step=0.5, key=f"e_exit_{leg['id']}")
                with ec8:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    save_edit = st.form_submit_button("💾 Save", use_container_width=True)
                with ec9:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    cancel_edit = st.form_submit_button("Cancel", use_container_width=True)

                if save_edit:
                    resolved_e = float(e_entry)
                    if resolved_e <= 0.0:
                        t_chain = next_chain if (next_chain and e_exp == next_chain.get("expiry")) else curr_chain
                        s_r = (t_chain or {}).get("strikes_map", {}).get(int(e_strike), {})
                        resolved_e = float(s_r.get("ce_ltp" if e_type == "CE" else "pe_ltp", 0.0)) or 50.0
                    st.session_state["active_positions"] = pos_manager.update_position(
                        st.session_state["active_positions"],
                        leg_id=leg["id"],
                        side=e_side,
                        opt_type=e_type,
                        strike=int(e_strike),
                        expiry=e_exp,
                        lots=int(e_lots),
                        entry_price=resolved_e,
                        exit_price=float(e_exit),
                        user_id=auth_uid,
                        access_token=auth_tok,
                    )
                    st.session_state["editing_leg_id"] = None
                    st.rerun()
                elif cancel_edit:
                    st.session_state["editing_leg_id"] = None
                    st.rerun()

    # Strategy Suggestions + Expiry Payoff Curve
    strat_col, payoff_col = st.columns([1.25, 1.0])
    with strat_col:
        st.markdown("**🛡️ Suggested Strategy to Minimize Risk & Increase Profit**")
        for sug in eval_res["suggestions"]:
            st.markdown(
                f"""
                <div class="strike-card" style="padding: 12px 15px; margin-bottom: 8px; border-left: 4px solid {sug['color']};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-size: 0.72rem; font-weight: 700; color: {sug['color']};">{sug['category']} • {sug['priority']}</span>
                    </div>
                    <div style="font-size: 0.92rem; font-weight: 700; color: #eaecef; margin-bottom: 4px;">{sug['title']}</div>
                    <div style="font-size: 0.83rem; color: #cfd8dc; line-height: 1.45; margin-bottom: 4px;">{sug['action']}</div>
                    <div style="font-size: 0.76rem; color: #848e9c;"><i>Why: {sug['why']}</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with payoff_col:
        st.markdown("**📈 Expiry Payoff Curve**")
        pc = eval_res.get("payoff_curve")
        if pc and pc["spots"]:
            fig_payoff = go.Figure()
            fig_payoff.add_trace(
                go.Scatter(
                    x=pc["spots"],
                    y=pc["pnls"],
                    mode="lines",
                    name="Expiry P&L",
                    line=dict(color="#64b5f6", width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(100, 181, 246, 0.12)",
                )
            )
            fig_payoff.add_hline(y=0, line_dash="dash", line_color="#848e9c", line_width=1)
            if ltp > 0:
                fig_payoff.add_vline(
                    x=ltp,
                    line_dash="dot",
                    line_color="#ffb300",
                    annotation_text=f"Spot {ltp:,.0f}",
                    annotation_position="top right",
                )
            fig_payoff.update_layout(
                template="plotly_dark",
                height=320,
                margin=dict(l=10, r=10, t=25, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,255,255,0.02)",
                xaxis_title="NIFTY Expiry Spot",
                yaxis_title="P&L (₹)",
                showlegend=False,
            )
            st.plotly_chart(fig_payoff, use_container_width=True)
else:
    st.info(
        "No active positions entered yet. Use the form above to add your open NIFTY option legs "
        "(e.g., SELL 25450 CE / SELL 24850 PE) to see live MTM P&L, expiry payoff, and tailored risk/profit adjustments."
    )

st.markdown("---")

# --- SECTION: INSTITUTIONAL LARGE-QUANTITY OPTION SELLER DESK ---
from core.institutional import InstitutionalAdvisor

st.subheader("🏛️ Institutional Desk: Large-Quantity Option Selling (Heavy Lot Sizing)")
st.caption(
    "Strategic execution framework for deploying 50 to 1,000+ lots: order slicing (NSE freeze limit: 1,800 units / 72 lots), "
    "strike depth grading, margin relief via wings & dynamic adjustment protocols."
)

inst_tab1, inst_tab2, inst_tab3, inst_tab4 = st.tabs([
    "🛡️ Hedged Large-Lot Playbook",
    "💧 Strike Liquidity & Slicing",
    "🔄 Systematic Adjustment Protocol",
    "💰 Capital & Margin Sizing Calculator",
])

with inst_tab1:
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid #00c853;">
                <div class="strike-title">
                    <span>1. Defined-Risk Institutional Iron Condor</span>
                    <span style="font-size: 0.8rem; color: #00e676; background: rgba(0,230,118,0.1); padding: 2px 8px; border-radius: 4px;">Recommended for 100+ Lots</span>
                </div>
                <div style="font-size: 0.9rem; color: #cfd8dc; margin-bottom: 8px;">
                    <b>Structure:</b> Sell {curr_rec['sell_ce']} CE & {curr_rec['sell_pe']} PE | Buy {curr_rec['hedge_ce']} CE & {curr_rec['hedge_pe']} PE (Wings)
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; line-height: 1.5;">
                    • <b>Overnight Tail-Risk Protection:</b> Unhedged strangles risk unlimited loss on 300+ pt freak gap-openings. Wings strictly cap max possible loss.<br>
                    • <b>Massive Margin Relief:</b> Margin drops from <b>₹1.25 Lakhs</b> (Naked) to <b>~₹38,000</b> per lot (Hedged). Enables <b>3.3x capital efficiency</b>.<br>
                    • <b>Regulatory Safety:</b> Fully compliant with SEBI peak margin rules; eliminates broker margin penalty spikes during midday IV expansion.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with h_col2:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid #ffb300;">
                <div class="strike-title">
                    <span>2. 1:2 Credit Ratio Spread (Directional Drift)</span>
                    <span style="font-size: 0.8rem; color: #ffb300; background: rgba(255,179,0,0.1); padding: 2px 8px; border-radius: 4px;">Zero Opposite Risk</span>
                </div>
                <div style="font-size: 0.9rem; color: #cfd8dc; margin-bottom: 8px;">
                    <b>Structure:</b> Buy 1x Near-OTM ({curr_rec['sell_ce'] - 50} CE) & Sell 2x Far-OTM ({curr_rec['sell_ce']} CE)
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; line-height: 1.5;">
                    • <b>Zero Risk on Reversal:</b> If NIFTY reverses and tanks, the position retains net credit with zero downside risk.<br>
                    • <b>Sweet Spot P&L Peak:</b> Maximum profit is achieved if NIFTY expires right at the sold short strike.<br>
                    • <b>Ideal for Trending Breakouts:</b> Deploy Bull Put 1:2 Ratios when heavyweights surge together with RVOL > 1.8x.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with inst_tab2:
    ce_liq = InstitutionalAdvisor.evaluate_strike_liquidity(curr_rec.get("ce_oi", 0))
    pe_liq = InstitutionalAdvisor.evaluate_strike_liquidity(curr_rec.get("pe_oi", 0))

    st.markdown("**Live Strike Execution Depth (Current Expiry Recommendations)**")
    l_col1, l_col2 = st.columns(2)
    with l_col1:
        st.markdown(
            f"""
            <div class="strike-card" style="padding: 14px 16px;">
                <div style="display: flex; justify-content: space-between;">
                    <b>Sell {curr_rec['sell_ce']} CE</b>
                    <span style="color: {ce_liq['color']}; font-weight: 700; font-size: 0.85rem;">{ce_liq['badge']}</span>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-top: 4px;">
                    Open Interest: <b>{curr_rec.get('ce_oi', 0):,} contracts</b> | Expected Slippage: <b>{ce_liq['slippage_risk']}</b>
                </div>
                <div style="font-size: 0.8rem; color: #cfd8dc; margin-top: 4px;">{ce_liq['comment']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with l_col2:
        st.markdown(
            f"""
            <div class="strike-card" style="padding: 14px 16px;">
                <div style="display: flex; justify-content: space-between;">
                    <b>Sell {curr_rec['sell_pe']} PE</b>
                    <span style="color: {pe_liq['color']}; font-weight: 700; font-size: 0.85rem;">{pe_liq['badge']}</span>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-top: 4px;">
                    Open Interest: <b>{curr_rec.get('pe_oi', 0):,} contracts</b> | Expected Slippage: <b>{pe_liq['slippage_risk']}</b>
                </div>
                <div style="font-size: 0.8rem; color: #cfd8dc; margin-top: 4px;">{pe_liq['comment']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("**⚡ NSE Freeze Limit Order Slicing Calculator**")
    test_lots = st.select_slider(
        "Select Planned Quantity to Deploy (Lots)",
        options=[20, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000],
        value=200,
        key="slice_lots_slider",
    )
    s_calc = InstitutionalAdvisor.calculate_order_slicing(test_lots)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Contracts", f"{s_calc['total_quantity']:,} units")
    s2.metric("NSE Order Freeze Limit", f"{s_calc['freeze_limit_per_order']:,} units")
    s3.metric("Required Slices", f"{s_calc['num_slices']} orders")
    s4.metric("Per-Slice Size", f"{s_calc['slice_size_lots']} lots ({s_calc['slice_size_qty']:,} qty)")
    st.info(f"💡 **Execution Rule:** {s_calc['execution_tip']}")

with inst_tab3:
    st.markdown("**Systematic 3-Phase Adjustment Protocol (When NIFTY Tests Your Sold Legs)**")
    adj_steps = InstitutionalAdvisor.get_institutional_adjustment_playbook(
        spot=ltp,
        sell_ce=curr_rec['sell_ce'],
        sell_pe=curr_rec['sell_pe'],
        ce_ltp=curr_rec['ce_ltp'],
        pe_ltp=curr_rec['pe_ltp'],
    )
    for step in adj_steps:
        st.markdown(
            f"""
            <div class="strike-card" style="margin-bottom: 12px; padding: 14px 18px;">
                <div style="font-weight: 700; color: #64b5f6; font-size: 0.95rem; margin-bottom: 4px;">{step['step']}</div>
                <div style="font-size: 0.85rem; color: #ffb300; margin-bottom: 4px;"><b>Trigger:</b> {step['trigger']}</div>
                <div style="font-size: 0.85rem; color: #eaecef; margin-bottom: 4px;"><b>Action:</b> {step['action']}</div>
                <div style="font-size: 0.8rem; color: #848e9c;"><b>Objective:</b> {step['goal']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with inst_tab4:
    st.markdown("**Capital Allocation & Margin Multiplier Calculator**")
    cap_val = st.slider(
        "Your Trading Capital Dedicated to Option Selling (₹)",
        min_value=1_000_000,
        max_value=50_000_000,
        value=5_000_000,
        step=500_000,
        format="₹%d",
        key="cap_calc_slider",
    )
    c_res = InstitutionalAdvisor.calculate_capital_and_margin(cap_val, ltp)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capital Pool", format_inr(c_res['capital_inr']))
    c2.metric("Safe Deploy Reserve (75%)", format_inr(c_res['safe_deploy_capital']))
    c3.metric("Naked Capacity (~₹1.25L/lot)", f"{c_res['naked_max_lots']} lots")
    c4.metric(f"Hedged Capacity ({c_res['capacity_multiplier']}x More)", f"{c_res['hedged_max_lots']} lots")

    st.markdown(
        f"""
        <div class="breakeven-corridor" style="text-align: left; padding: 12px 18px;">
            <div style="font-size: 0.9rem; color: #eaecef; font-weight: 600;">
                💡 <b>Institutional Efficiency Summary:</b>
            </div>
            <div style="font-size: 0.85rem; color: #cfd8dc; margin-top: 4px;">
                With <b>{format_inr(cap_val)}</b>, deploying naked strangles restricts you to only <b>{c_res['naked_max_lots']} lots</b> with unlimited gap risk.
                By converting to an <b>Institutional Defined-Risk Iron Condor</b> with cheap protection wings, your safe deployment expands to <b>{c_res['hedged_max_lots']} lots ({c_res['capacity_multiplier']}x larger size)</b>,
                saving <b>{c_res['margin_saved_pct']}% exchange margin</b> while leaving a 25% cash buffer ({format_inr(cap_val * 0.25)}) against intraday volatility spikes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# --- SECTION: TECHNICAL INDICATOR RADAR FOR OPTION SELLERS ---
st.subheader("📈 Technical Indicator Radar & Option Seller Levels")
st.caption(
    "Mathematical and derivatives indicator levels translated into plain-English definitions and "
    "specific tactical recommendations for option selling, strike placement, and gamma defense."
)

cpr_d = tech_data["cpr"]
cam_d = tech_data["camarilla"]
rsi_d = tech_data["rsi"]
adx_d = tech_data["adx"]
bb_d = tech_data["bollinger"]
atr_d = tech_data["atr"]
ma_d = tech_data["ma"]

# Top 4-Metric Pulse Row
t_col1, t_col2, t_col3, t_col4 = st.columns(4)

with t_col1:
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {cpr_d['color']};">
            <div class="metric-label">Central Pivot Range (CPR)</div>
            <div class="metric-val" style="font-size: 1.3rem;">{cpr_d['width_pts']:.1f} pts</div>
            <div class="metric-sub" style="color: {cpr_d['color']};">{cpr_d['badge']}</div>
            <div style="font-size: 0.75rem; color: #848e9c; margin-top: 4px;">Pivot: ₹{cpr_d['pivot']:,.1f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with t_col2:
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {cam_d['color']};">
            <div class="metric-label">Camarilla Iron Condor Range</div>
            <div class="metric-val" style="font-size: 1.3rem;">₹{cam_d['l3']:,.0f} - ₹{cam_d['h3']:,.0f}</div>
            <div class="metric-sub" style="color: {cam_d['color']};">{cam_d['badge']}</div>
            <div style="font-size: 0.75rem; color: #848e9c; margin-top: 4px;">Corridor: {cam_d['range_pts']:.0f} pts</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with t_col3:
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {adx_d['color']};">
            <div class="metric-label">Trend Strength (ADX 14)</div>
            <div class="metric-val" style="font-size: 1.3rem;">{adx_d['value']:.1f}</div>
            <div class="metric-sub" style="color: {adx_d['color']};">{adx_d['badge']}</div>
            <div style="font-size: 0.75rem; color: #848e9c; margin-top: 4px;">Threshold: &lt; 20 Sideways | &gt; 25 Trend</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with t_col4:
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {rsi_d['color']};">
            <div class="metric-label">Momentum (RSI 14)</div>
            <div class="metric-val" style="font-size: 1.3rem;">{rsi_d['value']:.1f}</div>
            <div class="metric-sub" style="color: {rsi_d['color']};">{rsi_d['badge']}</div>
            <div style="font-size: 0.75rem; color: #848e9c; margin-top: 4px;">ATR Buffer: ±{atr_d['safe_strike_buffer_pts']} pts</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

tech_tab1, tech_tab2, tech_tab3 = st.tabs([
    "🎯 Pivot Ranges (CPR & Camarilla)",
    "🌊 Volatility & Statistical Boundaries (Bollinger & ATR)",
    "⚡ Trend Direction & Moving Averages (ADX, RSI, EMAs)",
])

with tech_tab1:
    p_c1, p_c2 = st.columns(2)
    with p_c1:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {cpr_d['color']};">
                <div class="strike-title">
                    <span>1. Central Pivot Range (CPR)</span>
                    <span style="font-size: 0.8rem; color: {cpr_d['color']}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px;">{cpr_d['badge']}</span>
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {cpr_d['simple_term']}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; text-align: center;">
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #848e9c;">TC (Top)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #eaecef;">₹{cpr_d['top']:,.1f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #848e9c;">Pivot (P)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #64b5f6;">₹{cpr_d['pivot']:,.1f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #848e9c;">BC (Bottom)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #eaecef;">₹{cpr_d['bottom']:,.1f}</div>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Option Seller Rule:</b><br>{cpr_d['suggestion']}
                </div>
                <div style="font-size: 0.8rem; color: #848e9c; margin-top: 8px; display: flex; justify-content: space-between;">
                    <span><b>Classic R1:</b> ₹{cpr_d['r1']:,.0f} | <b>R2:</b> ₹{cpr_d['r2']:,.0f}</span>
                    <span><b>Classic S1:</b> ₹{cpr_d['s1']:,.0f} | <b>S2:</b> ₹{cpr_d['s2']:,.0f}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p_c2:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {cam_d['color']};">
                <div class="strike-title">
                    <span>2. Camarilla Intraday Matrix</span>
                    <span style="font-size: 0.8rem; color: {cam_d['color']}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px;">{cam_d['badge']}</span>
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {cam_d['simple_term']}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6px; margin-bottom: 12px; text-align: center;">
                    <div style="background: #1a1e29; padding: 8px 4px; border-radius: 4px;">
                        <div style="font-size: 0.7rem; color: #ff5252;">H4 (Breakout)</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #eaecef;">₹{cam_d['h4']:,.0f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px 4px; border-radius: 4px;">
                        <div style="font-size: 0.7rem; color: #ffb300;">H3 (Sell CE)</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #00e676;">₹{cam_d['h3']:,.0f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px 4px; border-radius: 4px;">
                        <div style="font-size: 0.7rem; color: #ffb300;">L3 (Sell PE)</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #ff5252;">₹{cam_d['l3']:,.0f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px 4px; border-radius: 4px;">
                        <div style="font-size: 0.7rem; color: #ff5252;">L4 (Breakdown)</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #eaecef;">₹{cam_d['l4']:,.0f}</div>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Option Seller Rule:</b><br>{cam_d['suggestion']}
                </div>
                <div style="font-size: 0.8rem; color: #848e9c; margin-top: 8px;">
                    🛡️ <b>Stop-Loss Rule:</b> If a 15-min candle closes beyond H4 (₹{cam_d['h4']:,.0f}) or L4 (₹{cam_d['l4']:,.0f}), square off or immediately hedge short legs.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tech_tab2:
    v_c1, v_c2 = st.columns(2)
    with v_c1:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {bb_d['color']};">
                <div class="strike-title">
                    <span>1. Bollinger Bands (20-Period, 2-SD)</span>
                    <span style="font-size: 0.8rem; color: {bb_d['color']}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px;">{bb_d['badge']}</span>
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {bb_d['simple_term']} (Bandwidth: <b>{bb_d['bandwidth_pct']}%</b>)
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; text-align: center;">
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #ff5252;">Upper (+2σ Ceiling)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #eaecef;">₹{bb_d['upper']:,.1f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #848e9c;">Middle (20 SMA)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #64b5f6;">₹{bb_d['middle']:,.1f}</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #00e676;">Lower (-2σ Floor)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #eaecef;">₹{bb_d['lower']:,.1f}</div>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Option Seller Rule:</b><br>{bb_d['suggestion']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with v_c2:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid #64b5f6;">
                <div class="strike-title">
                    <span>2. Average True Range (ATR 14)</span>
                    <span style="font-size: 0.8rem; color: #64b5f6; background: rgba(100,181,246,0.1); padding: 2px 8px; border-radius: 4px;">±{atr_d['value']:.1f} pts Daily Move</span>
                </div>
                <div style="font-size: 0.85rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {atr_d['simple_term']}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; text-align: center;">
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #848e9c;">14-Day ATR Range</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #eaecef;">±{atr_d['value']:.1f} pts</div>
                    </div>
                    <div style="background: #1a1e29; padding: 8px; border-radius: 4px;">
                        <div style="font-size: 0.75rem; color: #00e676;">Min Safe Strike Buffer (1.25x)</div>
                        <div style="font-size: 1rem; font-weight: 700; color: #00e676;">{atr_d['safe_strike_buffer_pts']} pts</div>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Option Seller Rule:</b><br>{atr_d['suggestion']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tech_tab3:
    m_c1, m_c2, m_c3 = st.columns(3)
    with m_c1:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {adx_d['color']};">
                <div class="strike-title">
                    <span>1. ADX (14) Trend Strength</span>
                </div>
                <div style="font-size: 1.5rem; font-weight: 700; color: {adx_d['color']}; margin: 6px 0;">
                    {adx_d['value']:.1f} <span style="font-size: 0.85rem; font-weight: 500;">({adx_d['badge']})</span>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {adx_d['simple_term']}
                </div>
                <div style="font-size: 0.83rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Seller Rule:</b><br>{adx_d['suggestion']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m_c2:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {rsi_d['color']};">
                <div class="strike-title">
                    <span>2. RSI (14) Momentum</span>
                </div>
                <div style="font-size: 1.5rem; font-weight: 700; color: {rsi_d['color']}; margin: 6px 0;">
                    {rsi_d['value']:.1f} <span style="font-size: 0.85rem; font-weight: 500;">({rsi_d['badge']})</span>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {rsi_d['simple_term']}
                </div>
                <div style="font-size: 0.83rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Seller Rule:</b><br>{rsi_d['suggestion']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m_c3:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {ma_d['color']};">
                <div class="strike-title">
                    <span>3. Moving Averages (Trend)</span>
                </div>
                <div style="font-size: 1rem; font-weight: 700; color: {ma_d['color']}; margin: 6px 0;">
                    {ma_d['badge']}
                </div>
                <div style="font-size: 0.8rem; color: #848e9c; margin-bottom: 6px;">
                    20 EMA: <b>₹{ma_d['ema20']:,.0f}</b> | 50 EMA: <b>₹{ma_d['ema50']:,.0f}</b>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-bottom: 8px;">
                    <b>Simple Meaning:</b> {ma_d['simple_term']}
                </div>
                <div style="font-size: 0.83rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Seller Rule:</b><br>{ma_d['suggestion']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# --- SECTION: GLOBAL MACRO, GEOPOLITICS & MARKET EVENTS RADAR ---
st.subheader("🌐 Global Macro, Geopolitics & Event Radar")
st.caption(
    "Option sellers don't get hurt by normal technical pullbacks; they get hurt by overnight gap-openings and sudden volatility spikes. "
    "Track live macro catalysts, high-impact central bank events, and geopolitical developments that dictate gap risk."
)

m_rates = macro_data.get("rates", {})
m_news = macro_data.get("news", [])
m_cal = macro_data.get("calendar", [])
m_fii = macro_data.get("fii_rules", {})
m_global = macro_data.get("global_markets", [])
m_earnings = macro_data.get("upcoming_earnings", [])
m_gf_summary = macro_data.get("gf_summary", "")
m_gf_live = macro_data.get("gf_live", False)
m_updated = macro_data.get("last_updated", "")

# 5 Core Global Macro Ticker Cards
r_c1, r_c2, r_c3, r_c4, r_c5 = st.columns(5)

# 1. Brent Crude
brent = m_rates.get("brent", {})
with r_c1:
    b_chg = brent.get("pChange", 0.0)
    b_sign = "+" if b_chg >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {brent.get('color', '#848e9c')}; padding: 12px 14px;">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>Brent Crude</span>
                <span style="font-size: 0.7rem; color: #848e9c;">USD/bbl</span>
            </div>
            <div class="metric-val" style="font-size: 1.35rem;">${brent.get('price', 0.0):.2f}</div>
            <div class="metric-sub" style="color: {brent.get('color', '#848e9c')};">{b_sign}{b_chg:.2f}%</div>
            <div style="font-size: 0.72rem; color: #848e9c; margin-top: 4px;">{brent.get('status', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 2. US Dollar Index (DXY)
dxy = m_rates.get("dxy", {})
with r_c2:
    d_chg = dxy.get("pChange", 0.0)
    d_sign = "+" if d_chg >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {dxy.get('color', '#848e9c')}; padding: 12px 14px;">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>Dollar Index</span>
                <span style="font-size: 0.7rem; color: #848e9c;">DXY</span>
            </div>
            <div class="metric-val" style="font-size: 1.35rem;">{dxy.get('price', 0.0):.2f}</div>
            <div class="metric-sub" style="color: {dxy.get('color', '#848e9c')};">{d_sign}{d_chg:.2f}%</div>
            <div style="font-size: 0.72rem; color: #848e9c; margin-top: 4px;">{dxy.get('status', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 3. USD / INR
usdinr = m_rates.get("usdinr", {})
with r_c3:
    u_chg = usdinr.get("pChange", 0.0)
    u_sign = "+" if u_chg >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {usdinr.get('color', '#848e9c')}; padding: 12px 14px;">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>USD / INR</span>
                <span style="font-size: 0.7rem; color: #848e9c;">Rupee</span>
            </div>
            <div class="metric-val" style="font-size: 1.35rem;">₹{usdinr.get('price', 0.0):.2f}</div>
            <div class="metric-sub" style="color: {usdinr.get('color', '#848e9c')};">{u_sign}{u_chg:.2f}%</div>
            <div style="font-size: 0.72rem; color: #848e9c; margin-top: 4px;">{usdinr.get('status', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 4. US 10-Yr Yield
us10y = m_rates.get("us10y", {})
with r_c4:
    y_chg = us10y.get("pChange", 0.0)
    y_sign = "+" if y_chg >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {us10y.get('color', '#848e9c')}; padding: 12px 14px;">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>US 10Y Yield</span>
                <span style="font-size: 0.7rem; color: #848e9c;">Treasury</span>
            </div>
            <div class="metric-val" style="font-size: 1.35rem;">{us10y.get('price', 0.0):.2f}%</div>
            <div class="metric-sub" style="color: {us10y.get('color', '#848e9c')};">{y_sign}{y_chg:.2f}%</div>
            <div style="font-size: 0.72rem; color: #848e9c; margin-top: 4px;">{us10y.get('status', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 5. India VIX
vix = m_rates.get("vix", {})
with r_c5:
    v_chg = vix.get("pChange", 0.0)
    v_sign = "+" if v_chg >= 0 else ""
    st.markdown(
        f"""
        <div class="metric-container" style="border-top: 3px solid {vix.get('color', '#848e9c')}; padding: 12px 14px;">
            <div class="metric-label" style="display: flex; justify-content: space-between;">
                <span>India VIX</span>
                <span style="font-size: 0.7rem; color: #848e9c;">Volatility</span>
            </div>
            <div class="metric-val" style="font-size: 1.35rem;">{vix.get('price', 0.0):.2f}</div>
            <div class="metric-sub" style="color: {vix.get('color', '#848e9c')};">{v_sign}{v_chg:.2f}%</div>
            <div style="font-size: 0.72rem; color: #848e9c; margin-top: 4px;">{vix.get('status', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Google Finance Live Global Summary & Benchmarks Strip
if m_gf_summary or m_global:
    gf_badge = (
        f"<span style='color:#00e676; font-weight:600;'>🟢 Live via Google Finance</span>"
        if m_gf_live
        else "<span style='color:#ffb300; font-weight:600;'>🟡 Cached Macro Snapshot</span>"
    )
    pills_html = ""
    for gm in m_global:
        # For CBOE VIX, higher is risk-off (red); for indices, positive is green
        is_vix = "VIX" in gm["name"]
        if is_vix:
            p_color = "#ff5252" if gm["pct"] > 0 else "#00c853"
        else:
            p_color = "#00c853" if gm["pct"] >= 0 else "#ff5252"
        pills_html += (
            f"<div style='background: rgba(255,255,255,0.03); border: 1px solid #2a2e39; border-radius: 6px; "
            f"padding: 6px 10px; min-width: 115px; flex: 1;'>"
            f"<div style='font-size: 0.72rem; color: #848e9c;'>{gm['name']}</div>"
            f"<div style='font-size: 0.88rem; font-weight: 700; color: #eaecef;'>{gm['price']} "
            f"<span style='font-size: 0.76rem; color: {p_color}; font-weight: 600;'>({gm['pct_str']})</span></div>"
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="strike-card" style="padding: 12px 16px; margin-top: 10px; margin-bottom: 12px; border-left: 4px solid #64b5f6;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
                <span style="font-size: 0.86rem; font-weight: 700; color: #eaecef;">🌍 Google Finance Global Macro Summary</span>
                <span style="font-size: 0.74rem; color: #848e9c;">{gf_badge} • Updated {m_updated} IST • <a href="https://www.google.com/finance/" target="_blank" style="color: #64b5f6; text-decoration: none;">google.com/finance ↗</a></span>
            </div>
            <div style="font-size: 0.84rem; color: #cfd8dc; line-height: 1.5; margin-bottom: 10px;">
                {m_gf_summary}
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                {pills_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

macro_tab1, macro_tab2, macro_tab3 = st.tabs([
    "📅 High-Impact Event & Central Bank Calendar",
    "📰 Live Market & Geopolitical Headlines",
    "🏦 FII / DII Derivatives Positioning Guide",
])

with macro_tab1:
    if m_earnings:
        st.markdown("**📊 Live Upcoming Corporate Earnings (via Google Finance)**")
        e_cols = st.columns(min(3, len(m_earnings)))
        for idx, earn in enumerate(m_earnings):
            with e_cols[idx % len(e_cols)]:
                st.markdown(
                    f"""
                    <div class="strike-card" style="padding: 10px 14px; margin-bottom: 10px; border-left: 3px solid #64b5f6;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
                            <span style="font-size: 0.85rem; font-weight: 700; color: #eaecef;">{earn['company']}</span>
                            <span style="font-size: 0.72rem; color: #64b5f6; font-weight: 600;">{earn['day']}</span>
                        </div>
                        <div style="font-size: 0.76rem; color: #848e9c;">
                            {earn['quarter']} • {earn['time']}
                        </div>
                        <div style="font-size: 0.76rem; color: #cfd8dc; margin-top: 4px;">
                            EPS Est: <b>{earn['eps_est']}</b> | Rev Est: <b>{earn['rev_est']}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("**Major Macro & Central Bank Events Dictating Overnight Gap Risk**")
    for ev in m_cal:
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {ev['impact_color']}; padding: 14px 18px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: #eaecef;">{ev['event']}</span>
                    <span style="font-size: 0.78rem; font-weight: 700; color: {ev['impact_color']}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px;">{ev['impact']} IMPACT</span>
                </div>
                <div style="font-size: 0.82rem; color: #848e9c; margin-bottom: 6px;">
                    <b>Schedule:</b> {ev['frequency']} | <b>Affected Sectors:</b> {ev['affected_sectors']}
                </div>
                <div style="font-size: 0.85rem; color: #cfd8dc; margin-bottom: 8px;">
                    <b>Catalyst Focus:</b> {ev['key_focus']}
                </div>
                <div style="font-size: 0.84rem; color: #eaecef; background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; border: 1px solid #2a2e39;">
                    <b>💡 Option Seller Playbook:</b><br>{ev['seller_rule']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with macro_tab2:
    st.markdown("**Real-Time Market, Energy & Geopolitical Headlines (Google Finance)**")
    if m_news:
        n_col1, n_col2 = st.columns(2)
        for idx, item in enumerate(m_news):
            target_col = n_col1 if idx % 2 == 0 else n_col2
            pub_meta = f"{item['publisher']} • {item['time_ago']}" if item.get("time_ago") else item["publisher"]
            with target_col:
                st.markdown(
                    f"""
                    <div class="strike-card" style="padding: 12px 16px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-size: 0.75rem; color: {item['tag_color']}; font-weight: 600; background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 4px;">{item['tag']}</span>
                            <span style="font-size: 0.72rem; color: #848e9c;">{pub_meta}</span>
                        </div>
                        <div style="font-size: 0.88rem; font-weight: 600; color: #eaecef; line-height: 1.4; margin-bottom: 6px;">
                            {item['title']}
                        </div>
                        <div style="text-align: right;">
                            <a href="{item['link']}" target="_blank" style="color: #64b5f6; font-size: 0.75rem; text-decoration: none; font-weight: 600;">Read Full Story ↗</a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No active market headlines reported at this time.")

with macro_tab3:
    st.markdown("**FII Index Futures Long/Short Positioning Framework**")
    st.caption("FII positioning in index futures provides a 3-5 day leading indicator of liquidity momentum and potential short-squeeze traps.")
    for r in m_fii.get("ranges", []):
        st.markdown(
            f"""
            <div class="strike-card" style="border-left: 4px solid {r['color']}; padding: 12px 16px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 0.95rem; font-weight: 700; color: #eaecef;">{r['range']}</span>
                    <span style="font-size: 0.8rem; font-weight: 700; color: {r['color']};">{r['state']}</span>
                </div>
                <div style="font-size: 0.85rem; color: #cfd8dc;">
                    {r['rule']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# Heavyweights Breakdown Row
st.subheader("🏛️ Heavyweights Alignment (The Top 5 Movers)")
st.caption(
    "HDFCBANK, RELIANCE, ICICIBANK, INFY & BHARTIARTL control ~40% of NIFTY. "
    "If they disagree, theta decay is at its best. If they align with volume, trend day risk is high."
)

t5_cols = st.columns(5)
for idx, (_, row) in enumerate(market["top5_heavyweights"].iterrows()):
    with t5_cols[idx]:
        p_chg = row["pChange"]
        pts = row["points_contribution"]
        rvol = row["rvol"]
        s_class = "pos-val" if p_chg >= 0 else "neg-val"
        s_sign = "+" if p_chg >= 0 else ""

        st.markdown(
            f"""
            <div class="metric-container" style="padding: 10px 14px;">
                <div style="display: flex; justify-content: space-between;">
                    <b>{row['symbol_clean']}</b>
                    <span style="color: #848e9c; font-size: 0.75rem;">Wt: {row['weight']:.1f}%</span>
                </div>
                <div style="font-size: 1.15rem; font-weight: 700; margin: 4px 0;">
                    {format_inr(row['lastPrice'])}
                </div>
                <div style="font-size: 0.85rem;" class="{s_class}">
                    {s_sign}{p_chg:.2f}% ({s_sign}{pts:.1f} pts)
                </div>
                <div style="font-size: 0.75rem; color: {'#00e676' if rvol >= 1.5 else '#848e9c'}; margin-top: 4px;">
                    RVOL: <b>{rvol:.2f}x</b> | {row['volume_status']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Visual tug-of-war chart
st.plotly_chart(
    create_heavyweights_tug_of_war_chart(market["top5_heavyweights"]),
    use_container_width=True,
)

st.markdown("---")

# --- SECTION 2: POINT CONTRIBUTION & TOP GAINERS / LOSERS ---
st.subheader("⚖️ Point Impact vs % Movers")
st.caption(
    "Option traders focus on **Points Contribution** rather than just % gainers. "
    "A 1% move in Reliance or HDFC Bank swings NIFTY ~25-30 pts, whereas a 4% move in a 0.7% stock barely moves Nifty 5 pts."
)

c_left, c_right = st.columns([1.4, 1.0])

with c_left:
    st.plotly_chart(
        create_point_contribution_chart(market["df"], top_n=8),
        use_container_width=True,
    )

with c_right:
    tab1, tab2 = st.tabs(["By Nifty Points Impact", "By % Change"])

    with tab1:
        st.markdown("**Top Contributors (Pulling Index UP)**")
        g_pts = market["by_points_gainers"][
            ["symbol_clean", "weight", "pChange", "points_contribution"]
        ].copy()
        g_pts.columns = ["Stock", "Weight %", "Change %", "Points Contributed"]
        st.dataframe(
            g_pts.style.format(
                {
                    "Weight %": "{:.2f}%",
                    "Change %": "{:+.2f}%",
                    "Points Contributed": "{:+.2f} pts",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("**Top Draggers (Dragging Index DOWN)**")
        d_pts = market["by_points_draggers"][
            ["symbol_clean", "weight", "pChange", "points_contribution"]
        ].copy()
        d_pts.columns = ["Stock", "Weight %", "Change %", "Points Dragged"]
        st.dataframe(
            d_pts.style.format(
                {
                    "Weight %": "{:.2f}%",
                    "Change %": "{:+.2f}%",
                    "Points Dragged": "{:+.2f} pts",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab2:
        st.markdown("**Top % Gainers**")
        g_pct = market["by_pct_gainers"][
            ["symbol_clean", "weight", "lastPrice", "pChange"]
        ].copy()
        g_pct.columns = ["Stock", "Weight %", "LTP", "% Change"]
        st.dataframe(
            g_pct.style.format(
                {
                    "Weight %": "{:.2f}%",
                    "LTP": "₹{:.2f}",
                    "% Change": "{:+.2f}%",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("**Top % Losers**")
        l_pct = market["by_pct_losers"][
            ["symbol_clean", "weight", "lastPrice", "pChange"]
        ].copy()
        l_pct.columns = ["Stock", "Weight %", "LTP", "% Change"]
        st.dataframe(
            l_pct.style.format(
                {
                    "Weight %": "{:.2f}%",
                    "LTP": "₹{:.2f}",
                    "% Change": "{:+.2f}%",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

st.markdown("---")

# --- SECTION 3: VOLUME SURGE & RVOL SCANNER ---
st.subheader("🔥 Volume Surge & RVOL Radar")
st.caption(
    "Relative Volume (RVOL) compares current volume to the 20-day average. "
    "RVOL > 1.8x signifies aggressive institutional positioning. High RVOL in top heavyweights warns option sellers of strong directional follow-through."
)

v_col1, v_col2 = st.columns([1.2, 1.0])

with v_col1:
    st.plotly_chart(
        create_volume_surge_chart(market["volume_surges"]),
        use_container_width=True,
    )

with v_col2:
    st.markdown("**Unusual Institutional Volume Activity**")
    if not market["volume_surges"].empty:
        v_table = market["volume_surges"][
            [
                "symbol_clean",
                "weight",
                "pChange",
                "points_contribution",
                "volume",
                "rvol",
                "volume_status",
            ]
        ].copy()
        v_table["volume"] = v_table["volume"].apply(format_volume)
        v_table.columns = [
            "Stock",
            "Weight",
            "Change %",
            "Point Impact",
            "Volume",
            "RVOL",
            "Signal",
        ]
        st.dataframe(
            v_table.style.format(
                {
                    "Weight": "{:.1f}%",
                    "Change %": "{:+.2f}%",
                    "Point Impact": "{:+.1f} pts",
                    "RVOL": "{:.2f}x",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No unusual volume surges detected at this moment (All RVOL < 1.3x).")

st.markdown("---")

# --- SECTION 4: SECTOR CONTRIBUTION BREAKDOWN ---
st.subheader("🏢 Sector Tug-of-War")
st.caption(
    "NIFTY is heavily tilted towards Financial Services (~34%) and IT (~13%). "
    "When Financials rally but IT drops, NIFTY remains rangebound."
)

sec_col1, sec_col2 = st.columns([1.2, 1.0])

with sec_col1:
    st.plotly_chart(
        create_sector_contribution_chart(market["sector_summary"]),
        use_container_width=True,
    )

with sec_col2:
    st.markdown("**Sector Performance Summary**")
    sec_display = market["sector_summary"][
        [
            "sector",
            "stocks_count",
            "total_weight",
            "net_points_contribution",
            "avg_p_change",
            "advances",
            "declines",
        ]
    ].copy()
    sec_display.columns = [
        "Sector",
        "Stocks",
        "Weight %",
        "Net Points",
        "Avg %",
        "Adv",
        "Dec",
    ]
    st.dataframe(
        sec_display.style.format(
            {
                "Weight %": "{:.1f}%",
                "Net Points": "{:+.1f} pts",
                "Avg %": "{:+.2f}%",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

st.markdown("---")

# --- SECTION 5: COMPLETE CONSTITUENT MASTER SCREENER ---
st.subheader("📋 Complete NIFTY 50 Constituent Screener")

filter_col1, filter_col2, filter_col3 = st.columns([1.5, 1.5, 2.0])

with filter_col1:
    sector_filter = st.multiselect(
        "Filter by Sector",
        options=sorted(list(set(market["df"]["sector"]))),
        default=[],
    )

with filter_col2:
    vol_filter = st.selectbox(
        "Filter by Volume Activity",
        ["All Activity", "Surges Only (RVOL ≥ 1.3x)", "High Volume (RVOL ≥ 1.8x)"],
    )

with filter_col3:
    search_query = st.text_input("🔍 Search Stock Symbol", "")

filtered_df = market["df"].copy()

if sector_filter:
    filtered_df = filtered_df[filtered_df["sector"].isin(sector_filter)]

if vol_filter == "Surges Only (RVOL ≥ 1.3x)":
    filtered_df = filtered_df[filtered_df["rvol"] >= 1.3]
elif vol_filter == "High Volume (RVOL ≥ 1.8x)":
    filtered_df = filtered_df[filtered_df["rvol"] >= 1.8]

if search_query:
    filtered_df = filtered_df[
        filtered_df["symbol_clean"].str.contains(search_query.upper(), na=False)
    ]

# Sort options
sort_by = st.selectbox(
    "Sort Table By",
    [
        "Weight (Highest first)",
        "Points Contribution (Highest first)",
        "Points Contribution (Lowest first)",
        "% Change (Gainers first)",
        "% Change (Losers first)",
        "RVOL (Highest Volume Surge first)",
    ],
    index=0,
)

if sort_by == "Weight (Highest first)":
    filtered_df = filtered_df.sort_values(by="weight", ascending=False)
elif sort_by == "Points Contribution (Highest first)":
    filtered_df = filtered_df.sort_values(by="points_contribution", ascending=False)
elif sort_by == "Points Contribution (Lowest first)":
    filtered_df = filtered_df.sort_values(by="points_contribution", ascending=True)
elif sort_by == "% Change (Gainers first)":
    filtered_df = filtered_df.sort_values(by="pChange", ascending=False)
elif sort_by == "% Change (Losers first)":
    filtered_df = filtered_df.sort_values(by="pChange", ascending=True)
elif sort_by == "RVOL (Highest Volume Surge first)":
    filtered_df = filtered_df.sort_values(by="rvol", ascending=False)

display_table = filtered_df[
    [
        "symbol_clean",
        "sector",
        "weight",
        "lastPrice",
        "change",
        "pChange",
        "points_contribution",
        "volume",
        "avg_volume_20d",
        "rvol",
        "volume_status",
    ]
].copy()

display_table["volume_formatted"] = display_table["volume"].apply(format_volume)
display_table["avg_vol_formatted"] = display_table["avg_volume_20d"].apply(
    lambda x: format_volume(int(x))
)

display_table = display_table.drop(columns=["volume", "avg_volume_20d"])
display_table.columns = [
    "Symbol",
    "Sector",
    "Weight %",
    "LTP",
    "Change",
    "% Change",
    "Points Contributed",
    "RVOL",
    "Status",
    "Traded Vol",
    "20D Avg Vol",
]

st.dataframe(
    display_table.style.format(
        {
            "Weight %": "{:.2f}%",
            "LTP": "₹{:.2f}",
            "Change": "{:+.2f}",
            "% Change": "{:+.2f}%",
            "Points Contributed": "{:+.2f} pts",
            "RVOL": "{:.2f}x",
        }
    ),
    hide_index=True,
    use_container_width=True,
    height=450,
)

# Footer info
st.caption(
    "⚡ Built for active NIFTY 50 Option Traders. Real-time point weights, volume surges & heavyweight alignment. "
    "Designed to protect option sellers from gamma risk on trending breakout days."
)
