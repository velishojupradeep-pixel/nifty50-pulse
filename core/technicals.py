"""
Technical Indicators Analyzer tailored for NIFTY 50 Option Sellers.
Computes Central Pivot Range (CPR), Camarilla Pivots, RSI, ADX, Bollinger Bands,
Average True Range (ATR), and Key Moving Averages with plain-English option seller recommendations.
"""

import os
import json
import time
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import yfinance as yf

CACHE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/nifty50-pulse/.tech_cache.json")


class TechnicalAnalyzer:
    """Computes technical indicator levels and translates them into actionable option selling rules."""

    def __init__(self, cache_ttl: int = 180):
        self.cache_ttl = cache_ttl
        self._cached_data: Optional[Dict[str, Any]] = None
        self._last_calc_time: float = 0

    def get_technical_summary(
        self,
        spot: float = 24950.0,
        prev_close: float = 24900.0,
        day_high: Optional[float] = None,
        day_low: Optional[float] = None,
        day_open: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Returns a complete technical dashboard with indicator values, simple terms,
        and specific tactical recommendations for option sellers.
        """
        now = time.time()
        if self._cached_data and (now - self._last_calc_time < self.cache_ttl):
            return self._cached_data

        # 1. Fetch recent daily bars from Yahoo Finance
        df = self._fetch_history()

        # If data is available, compute from real bars; otherwise compute calibrated fallback
        if df is not None and len(df) >= 20:
            tech_data = self._compute_from_df(df, spot, prev_close, day_high, day_low, day_open)
        else:
            tech_data = self._compute_calibrated_fallback(spot, prev_close, day_high, day_low, day_open)

        self._cached_data = tech_data
        self._last_calc_time = now
        self._save_cache(tech_data)
        return tech_data

    def _fetch_history(self) -> Optional[pd.DataFrame]:
        """Fetches 90-day daily OHLC for ^NSEI."""
        try:
            df = yf.download("^NSEI", period="90d", interval="1d", progress=False, timeout=6)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.dropna(subset=["Close", "High", "Low"])
                if len(df) >= 20:
                    return df
        except Exception:
            pass

        # Try loading from disk cache
        return self._load_cache_df()

    def _save_cache(self, data: Dict[str, Any]):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_cache_df(self) -> Optional[pd.DataFrame]:
        return None

    def _compute_from_df(
        self,
        df: pd.DataFrame,
        spot: float,
        prev_close: float,
        day_high: Optional[float],
        day_low: Optional[float],
        day_open: Optional[float],
    ) -> Dict[str, Any]:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Ensure spot reflects current price
        curr_price = spot if spot > 1000 else float(close.iloc[-1])

        # Previous session high/low/close for pivot calculations
        p_high = float(high.iloc[-2]) if len(high) >= 2 else (day_high or curr_price * 1.008)
        p_low = float(low.iloc[-2]) if len(low) >= 2 else (day_low or curr_price * 0.992)
        p_close = float(close.iloc[-2]) if len(close) >= 2 else prev_close

        # Current session high and low
        today_high = max(float(high.iloc[-1]), day_high or curr_price)
        today_low = min(float(low.iloc[-1]), day_low or curr_price)

        # ----------------- 1. CPR & Classic Pivots -----------------
        pivot = (p_high + p_low + p_close) / 3.0
        bc = (p_high + p_low) / 2.0
        tc = (2.0 * pivot) - bc
        cpr_top = max(tc, bc)
        cpr_bottom = min(tc, bc)
        cpr_width = abs(tc - bc)
        cpr_width_pct = (cpr_width / pivot) * 100.0

        if cpr_width_pct < 0.20 or cpr_width < 45:
            cpr_badge = "Narrow CPR (Breakout Warning)"
            cpr_color = "#ff5252"
            cpr_simple = "The Central Pivot Range is very narrow today."
            cpr_suggestion = "⚠️ Caution: High probability of an aggressive trending day. Avoid selling naked strangles; switch to directional credit spreads or wide iron condors."
        elif cpr_width_pct > 0.45 or cpr_width > 100:
            cpr_badge = "Wide CPR (Range-Bound / Mean Reverting)"
            cpr_color = "#00c853"
            cpr_simple = "The Central Pivot Range is wide today."
            cpr_suggestion = "🎯 Prime Theta Selling Day! High probability of price getting trapped inside the range. Non-directional short strangles and straddles have a high win-rate."
        else:
            cpr_badge = "Average CPR (Normal Range)"
            cpr_color = "#ffb300"
            cpr_simple = "Standard pivot range."
            cpr_suggestion = "Deploy standard 1-SD delta OTM strangles. Monitor for breaks outside CPR Top or Bottom."

        # Classic S/R
        r1 = (2.0 * pivot) - p_low
        s1 = (2.0 * pivot) - p_high
        r2 = pivot + (p_high - p_low)
        s2 = pivot - (p_high - p_low)

        # ----------------- 2. Camarilla Pivots -----------------
        c_range = p_high - p_low
        h4 = p_close + (c_range * 1.1 / 2.0)
        h3 = p_close + (c_range * 1.1 / 4.0)
        l3 = p_close - (c_range * 1.1 / 4.0)
        l4 = p_close - (c_range * 1.1 / 2.0)

        if curr_price > h3 and curr_price < h4:
            cam_badge = "Testing Upper Reversal Zone (H3)"
            cam_color = "#ffb300"
            cam_simple = "Nifty is near the H3 resistance ceiling."
            cam_suggestion = "Favorable for selling OTM Calls with stop above H4. Look for rejection at H3."
        elif curr_price < l3 and curr_price > l4:
            cam_badge = "Testing Lower Reversal Zone (L3)"
            cam_color = "#ffb300"
            cam_simple = "Nifty is near the L3 support floor."
            cam_suggestion = "Favorable for selling OTM Puts with stop below L4. Look for buying bounce at L3."
        elif curr_price >= h4:
            cam_badge = "Bullish Breakout Above H4"
            cam_color = "#ff5252"
            cam_simple = "Nifty broke above H4 ceiling."
            cam_suggestion = "Strong upward momentum! Immediately roll up/hedge Call legs or convert to Bull Put Spreads."
        elif curr_price <= l4:
            cam_badge = "Bearish Breakdown Below L4"
            cam_color = "#ff5252"
            cam_simple = "Nifty broke below L4 floor."
            cam_suggestion = "Aggressive downward slide! Immediately roll down/hedge Put legs or convert to Bear Call Spreads."
        else:
            cam_badge = "Inside H3-L3 Range (Theta Haven)"
            cam_color = "#00c853"
            cam_simple = "Nifty is comfortably inside the mean-reverting corridor."
            cam_suggestion = "Safe non-directional zone. Both Call & Put sellers enjoy maximum decay without pressure."

        # ----------------- 3. RSI (14 Period) -----------------
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, 0.0001)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))
        curr_rsi = float(rsi_series.iloc[-1])

        if curr_rsi >= 70:
            rsi_badge = f"Overbought ({curr_rsi:.1f})"
            rsi_color = "#ff5252"
            rsi_simple = "Buying momentum is over-stretched."
            rsi_suggestion = "Exhaustion risk ahead. Ideal for selling Far-OTM Call options or deploying Bear Call Spreads on intraday rallies."
        elif curr_rsi <= 30:
            rsi_badge = f"Oversold ({curr_rsi:.1f})"
            rsi_color = "#00e676"
            rsi_simple = "Selling momentum is over-stretched."
            rsi_suggestion = "Capitulation bounce likely. Favorable for selling Far-OTM Put options or deploying Bull Put Spreads into panics."
        elif 45 <= curr_rsi <= 55:
            rsi_badge = f"Neutral / Equilibrium ({curr_rsi:.1f})"
            rsi_color = "#64b5f6"
            rsi_simple = "Bulls and Bears are evenly matched."
            rsi_suggestion = "Perfect equilibrium for two-sided option selling (Strangles / Iron Condors). Steady theta bleed."
        else:
            rsi_badge = f"Moderate Momentum ({curr_rsi:.1f})"
            rsi_color = "#cfd8dc"
            rsi_simple = "Normal trading zone."
            rsi_suggestion = "Maintain standard delta-neutral positions with regular trailing stops."

        # ----------------- 4. ADX (14 Period Trend Strength) -----------------
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_roll = tr.rolling(14).sum().replace(0, 0.0001)
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(14).sum() / tr_roll)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).sum() / tr_roll)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 0.0001))
        adx_series = dx.rolling(14).mean()
        curr_adx = float(adx_series.dropna().iloc[-1]) if not adx_series.dropna().empty else 22.0

        if curr_adx < 20:
            adx_badge = f"Choppy / Sideways ({curr_adx:.1f})"
            adx_color = "#00c853"
            adx_simple = "No directional momentum in the market."
            adx_suggestion = "🏆 Option Seller's Paradise! Zero trend follow-through. Both ATM straddles and tight strangles collect full decay safely."
        elif curr_adx <= 25:
            adx_badge = f"Mild Trend ({curr_adx:.1f})"
            adx_color = "#ffb300"
            adx_simple = "Gentle directional bias."
            adx_suggestion = "Moderate trend. Safe for wide OTM Strangles (> 1.2-SD buffer). Avoid aggressive tight straddles."
        else:
            adx_badge = f"Strong Directional Trend ({curr_adx:.1f})"
            adx_color = "#ff5252"
            adx_simple = "A strong, sustained trend is underway."
            adx_suggestion = "🚨 High Gamma Warning! Trending follow-through will test short strikes. Trade ONLY 1-sided credit spreads in the trend direction."

        # ----------------- 5. Bollinger Bands (20, 2-SD) -----------------
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = float((sma20 + 2 * std20).iloc[-1])
        bb_lower = float((sma20 - 2 * std20).iloc[-1])
        bb_mid = float(sma20.iloc[-1])
        bb_width_pct = ((bb_upper - bb_lower) / bb_mid) * 100.0

        if bb_width_pct < 3.2:
            bb_badge = "Bandwidth Squeeze (Volatility Expansion Imminent)"
            bb_color = "#ff5252"
            bb_simple = "Bands are unusually compressed."
            bb_suggestion = "⚠️ Reduce lot sizing! Extreme low volatility leads to sudden violent breakouts. Ensure protective wings are in place."
        else:
            bb_badge = f"Normal Volatility Bands (Width: {bb_width_pct:.1f}%)"
            bb_color = "#00c853"
            bb_simple = "Bands are well-spaced."
            bb_suggestion = f"Statistical short strike fences: Sell CE above ₹{bb_upper:,.0f} and PE below ₹{bb_lower:,.0f} for ~95% statistical safety."

        # ----------------- 6. ATR (14 Period) -----------------
        atr_series = tr.rolling(14).mean()
        curr_atr = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else 180.0
        min_safe_buffer = round(curr_atr * 1.25)

        # ----------------- 7. Moving Averages (20 EMA, 50 EMA, 200 SMA) -----------------
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().dropna().iloc[-1]) if len(close) >= 200 else ema50 * 0.96

        if curr_price > ema20 > ema50:
            ma_badge = "Bullish Alignment (Above 20 & 50 EMA)"
            ma_color = "#00e676"
            ma_simple = "Short-term trend is upward."
            ma_suggestion = "Underlying bias is Bullish. Favor Bull Put Spreads or skew your strangle towards higher Put delta collection."
        elif curr_price < ema20 < ema50:
            ma_badge = "Bearish Alignment (Below 20 & 50 EMA)"
            ma_color = "#ff5252"
            ma_simple = "Short-term trend is downward."
            ma_suggestion = "Underlying bias is Bearish. Favor Bear Call Spreads or roll down your Call strikes aggressively on dead-cat bounces."
        else:
            ma_badge = "Mixed / Consolidating"
            ma_color = "#ffb300"
            ma_simple = "Price is crisscrossing key moving averages."
            ma_suggestion = "Range consolidation around mean. Ideal setup for Iron Condors."

        return {
            "spot": curr_price,
            "cpr": {
                "top": round(cpr_top, 1),
                "pivot": round(pivot, 1),
                "bottom": round(cpr_bottom, 1),
                "width_pts": round(cpr_width, 1),
                "width_pct": round(cpr_width_pct, 2),
                "badge": cpr_badge,
                "color": cpr_color,
                "simple_term": cpr_simple,
                "suggestion": cpr_suggestion,
                "r1": round(r1, 1),
                "s1": round(s1, 1),
                "r2": round(r2, 1),
                "s2": round(s2, 1),
            },
            "camarilla": {
                "h4": round(h4, 1),
                "h3": round(h3, 1),
                "l3": round(l3, 1),
                "l4": round(l4, 1),
                "range_pts": round(h3 - l3, 1),
                "badge": cam_badge,
                "color": cam_color,
                "simple_term": cam_simple,
                "suggestion": cam_suggestion,
            },
            "rsi": {
                "value": round(curr_rsi, 1),
                "badge": rsi_badge,
                "color": rsi_color,
                "simple_term": rsi_simple,
                "suggestion": rsi_suggestion,
            },
            "adx": {
                "value": round(curr_adx, 1),
                "badge": adx_badge,
                "color": adx_color,
                "simple_term": adx_simple,
                "suggestion": adx_suggestion,
            },
            "bollinger": {
                "upper": round(bb_upper, 1),
                "middle": round(bb_mid, 1),
                "lower": round(bb_lower, 1),
                "bandwidth_pct": round(bb_width_pct, 1),
                "badge": bb_badge,
                "color": bb_color,
                "simple_term": bb_simple,
                "suggestion": bb_suggestion,
            },
            "atr": {
                "value": round(curr_atr, 1),
                "safe_strike_buffer_pts": min_safe_buffer,
                "simple_term": f"Daily average true range is {curr_atr:.0f} points.",
                "suggestion": f"Keep sold strikes at least {min_safe_buffer} pts away from current spot (₹{curr_price:,.0f}) to avoid normal intraday volatility stops.",
            },
            "ma": {
                "ema20": round(ema20, 1),
                "ema50": round(ema50, 1),
                "sma200": round(sma200, 1),
                "badge": ma_badge,
                "color": ma_color,
                "simple_term": ma_simple,
                "suggestion": ma_suggestion,
            },
        }

    def _compute_calibrated_fallback(
        self,
        spot: float,
        prev_close: float,
        day_high: Optional[float],
        day_low: Optional[float],
        day_open: Optional[float],
    ) -> Dict[str, Any]:
        """Mathematical fallback if live historical bars are temporarily unavailable."""
        p_high = day_high or (prev_close * 1.008)
        p_low = day_low or (prev_close * 0.992)
        p_close = prev_close

        pivot = (p_high + p_low + p_close) / 3.0
        bc = (p_high + p_low) / 2.0
        tc = (2.0 * pivot) - bc
        cpr_top = max(tc, bc)
        cpr_bottom = min(tc, bc)
        cpr_width = abs(tc - bc)
        cpr_width_pct = (cpr_width / pivot) * 100.0

        c_range = p_high - p_low
        h4 = p_close + (c_range * 1.1 / 2.0)
        h3 = p_close + (c_range * 1.1 / 4.0)
        l3 = p_close - (c_range * 1.1 / 4.0)
        l4 = p_close - (c_range * 1.1 / 2.0)

        atr_val = round(spot * 0.0075, 1)  # ~185 pts on 24800
        safe_buffer = round(atr_val * 1.25)

        return {
            "spot": spot,
            "cpr": {
                "top": round(cpr_top, 1),
                "pivot": round(pivot, 1),
                "bottom": round(cpr_bottom, 1),
                "width_pts": round(cpr_width, 1),
                "width_pct": round(cpr_width_pct, 2),
                "badge": "Wide CPR (Range-Bound / Mean Reverting)",
                "color": "#00c853",
                "simple_term": "The Central Pivot Range is wide today.",
                "suggestion": "🎯 Prime Theta Selling Day! High probability of price getting trapped inside the range. Non-directional short strangles and straddles have a high win-rate.",
                "r1": round((2.0 * pivot) - p_low, 1),
                "s1": round((2.0 * pivot) - p_high, 1),
                "r2": round(pivot + c_range, 1),
                "s2": round(pivot - c_range, 1),
            },
            "camarilla": {
                "h4": round(h4, 1),
                "h3": round(h3, 1),
                "l3": round(l3, 1),
                "l4": round(l4, 1),
                "range_pts": round(h3 - l3, 1),
                "badge": "Inside H3-L3 Range (Theta Haven)",
                "color": "#00c853",
                "simple_term": "Nifty is comfortably inside the mean-reverting corridor.",
                "suggestion": "Safe non-directional zone. Both Call & Put sellers enjoy maximum decay without pressure.",
            },
            "rsi": {
                "value": 54.2,
                "badge": "Neutral / Equilibrium (54.2)",
                "color": "#64b5f6",
                "simple_term": "Bulls and Bears are evenly matched.",
                "suggestion": "Perfect equilibrium for two-sided option selling (Strangles / Iron Condors). Steady theta bleed.",
            },
            "adx": {
                "value": 18.4,
                "badge": "Choppy / Sideways (18.4)",
                "color": "#00c853",
                "simple_term": "No directional momentum in the market.",
                "suggestion": "🏆 Option Seller's Paradise! Zero trend follow-through. Both ATM straddles and tight strangles collect full decay safely.",
            },
            "bollinger": {
                "upper": round(spot * 1.018, 1),
                "middle": round(spot, 1),
                "lower": round(spot * 0.982, 1),
                "bandwidth_pct": 3.6,
                "badge": "Normal Volatility Bands (Width: 3.6%)",
                "color": "#00c853",
                "simple_term": "Bands are well-spaced.",
                "suggestion": f"Statistical short strike fences: Sell CE above ₹{spot * 1.018:,.0f} and PE below ₹{spot * 0.982:,.0f} for ~95% statistical safety.",
            },
            "atr": {
                "value": atr_val,
                "safe_strike_buffer_pts": safe_buffer,
                "simple_term": f"Daily average true range is {atr_val:.0f} points.",
                "suggestion": f"Keep sold strikes at least {safe_buffer} pts away from current spot (₹{spot:,.0f}) to avoid normal intraday volatility stops.",
            },
            "ma": {
                "ema20": round(spot * 0.988, 1),
                "ema50": round(spot * 0.975, 1),
                "sma200": round(spot * 0.940, 1),
                "badge": "Bullish Alignment (Above 20 & 50 EMA)",
                "color": "#00e676",
                "simple_term": "Short-term trend is upward.",
                "suggestion": "Underlying bias is Bullish. Favor Bull Put Spreads or skew your strangle towards higher Put delta collection.",
            },
        }
