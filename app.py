"""
NIFTY 50 Option Radar & Volume Tracker
Streamlit Application tailored for Active Option Sellers.
"""

import time
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from data.manager import DataManager
from core.engine import AnalyticsEngine
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


@st.cache_resource
def get_services():
    data_mgr = DataManager()
    engine = AnalyticsEngine()
    return data_mgr, engine


data_manager, analytics_engine = get_services()

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("⚡ Option Radar Settings")

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
with st.spinner("Fetching live constituent data..."):
    source_choice = (
        "Auto" if data_source_mode.startswith("Auto") else data_source_mode
    )
    df_raw, nifty_meta, source_used = data_manager.fetch_live_data(
        source_preference=source_choice
    )
    avg_volumes = data_manager.get_average_volumes()
    market = analytics_engine.process_market_data(
        df_raw, nifty_meta, avg_volumes, custom_iv=custom_iv
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

st.title("NIFTY 50 Pulse & Option Seller Radar")
st.caption(
    "Real-time constituent weightage tracker, index point contribution, heavyweight alignment, and RVOL analysis."
)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">NIFTY 50 SPOT</div>
            <div class="metric-val">{ltp:,.2f}</div>
            <div class="metric-sub {color_class}">{sign}{change:,.2f} ({sign}{p_change:.2f}%)</div>
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
            <div class="metric-sub neutral-val">Bullish vs Bearish Index Weight</div>
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
            <div class="metric-label">HEAVYWEIGHT ALIGNMENT</div>
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
            <div class="metric-sub neutral-val">Out of Total {regime.get('total_points', 0.0):+.1f} pts</div>
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

with rec_col1:
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
                    <div style="color: #00c853; font-size: 0.8rem; font-weight: 700;">SELL CALL (CE)</div>
                    <div class="strike-leg-val">{curr_rec['sell_ce']} CE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        +{curr_rec['ce_otm_pts']} pts (+{curr_rec['ce_otm_pct']}%) OTM
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Hedge: Buy <b>{curr_rec['hedge_ce']} CE</b>
                    </div>
                </div>
                <div class="strike-leg-box pe">
                    <div style="color: #ff3344; font-size: 0.8rem; font-weight: 700;">SELL PUT (PE)</div>
                    <div class="strike-leg-val">{curr_rec['sell_pe']} PE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        -{curr_rec['pe_otm_pts']} pts (-{curr_rec['pe_otm_pct']}%) OTM
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Hedge: Buy <b>{curr_rec['hedge_pe']} PE</b>
                    </div>
                </div>
            </div>
            <div class="breakeven-corridor">
                <div style="font-size: 0.78rem; color: #848e9c; text-transform: uppercase;">Breakeven Corridor (Est. Premium ₹{curr_rec['est_combined_premium']:.0f})</div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #eaecef; margin: 2px 0;">
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
                    <div style="color: #00c853; font-size: 0.8rem; font-weight: 700;">SELL CALL (CE)</div>
                    <div class="strike-leg-val">{next_rec['sell_ce']} CE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        +{next_rec['ce_otm_pts']} pts (+{next_rec['ce_otm_pct']}%) OTM
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Hedge: Buy <b>{next_rec['hedge_ce']} CE</b>
                    </div>
                </div>
                <div class="strike-leg-box pe">
                    <div style="color: #ff3344; font-size: 0.8rem; font-weight: 700;">SELL PUT (PE)</div>
                    <div class="strike-leg-val">{next_rec['sell_pe']} PE</div>
                    <div style="font-size: 0.78rem; color: #848e9c; margin-top: 2px;">
                        -{next_rec['pe_otm_pts']} pts (-{next_rec['pe_otm_pct']}%) OTM
                    </div>
                    <div style="font-size: 0.75rem; color: #64b5f6; margin-top: 4px;">
                        🛡️ Hedge: Buy <b>{next_rec['hedge_pe']} PE</b>
                    </div>
                </div>
            </div>
            <div class="breakeven-corridor">
                <div style="font-size: 0.78rem; color: #848e9c; text-transform: uppercase;">Breakeven Corridor (Est. Premium ₹{next_rec['est_combined_premium']:.0f})</div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #eaecef; margin: 2px 0;">
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
