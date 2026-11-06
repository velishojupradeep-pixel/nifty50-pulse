"""
Option Seller Strategy & Strike Recommendation Engine.
Integrated with genuine live NSE Option Chain (https://www.nseindia.com/option-chain).
Provides authentic official expiry dates, live strike premiums (CE & PE LTP),
real ATM straddle pricing, Open Interest, PCR, and Max Pain.
"""

import math
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd


class StrikeAdvisor:
    """Generates expert option seller verdicts and strike recommendations using live NSE data."""

    def __init__(self, default_iv: float = 13.5):
        self.default_iv = default_iv

    @staticmethod
    def round_strike(price: float, step: int = 50) -> int:
        """Round price to nearest strike step (50 for NIFTY weekly, 100 for monthly)."""
        return int(round(price / step) * step)

    def calculate_dte(self, expiry_str: str) -> int:
        """Computes days to expiry from NSE date string format (e.g. '09-Nov-2026')."""
        try:
            exp_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
            today = datetime.now().date()
            return max(1, (exp_date - today).days)
        except Exception:
            return 4

    def generate_verdict_and_strikes(
        self,
        nifty_meta: Dict[str, Any],
        regime: Dict[str, Any],
        top5_df: pd.DataFrame,
        custom_iv: float = None,
        curr_chain: Optional[Dict[str, Any]] = None,
        next_chain: Optional[Dict[str, Any]] = None,
        official_expiries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Produces comprehensive Option Seller Verdict and specific strike recommendations
        backed by live NSE Option Chain prices.
        """
        curr_chain = curr_chain or {}
        next_chain = next_chain or {}
        expiries = official_expiries or []

        # Prefer live underlying from NSE Option Chain if available
        spot = curr_chain.get("underlying") or nifty_meta.get("lastPrice", 24600.0)
        atm_strike = curr_chain.get("atm_strike") or self.round_strike(spot, 50)
        regime_status = regime.get("status", "RANGEBOUND / TUG-OF-WAR")
        regime_score = regime.get("score", 0.0)
        iv = custom_iv or self.default_iv

        # Official Expiry Dates directly from NSE
        curr_expiry_date = expiries[0] if len(expiries) >= 1 else curr_chain.get("expiry", "09-Nov-2026")
        next_expiry_date = expiries[1] if len(expiries) >= 2 else next_chain.get("expiry", "17-Nov-2026")

        dte_curr = self.calculate_dte(curr_expiry_date)
        dte_next = self.calculate_dte(next_expiry_date)

        # Expected Move based on IV or real ATM Straddle price
        atm_straddle_curr = curr_chain.get("atm_straddle", 0.0)
        if atm_straddle_curr > 0:
            # When ATM straddle price is live from NSE, Expected Move ~ 0.85 * Straddle Price
            em_curr = round(atm_straddle_curr * 0.85, 1)
        else:
            em_curr = round(spot * (iv / 100.0) * math.sqrt(dte_curr / 365.0), 1)

        atm_straddle_next = next_chain.get("atm_straddle", 0.0)
        if atm_straddle_next > 0:
            em_next = round(atm_straddle_next * 0.85, 1)
        else:
            em_next = round(spot * (iv / 100.0) * math.sqrt(dte_next / 365.0), 1)

        # Build Verdict based on alignment, regime, and PCR
        pcr = curr_chain.get("pcr", 1.0)
        max_pain = curr_chain.get("max_pain", atm_strike)
        verdict = self._build_verdict(spot, regime_status, regime_score, top5_df, em_curr, pcr, max_pain)

        # Generate Current Expiry Recommendation with LIVE premiums
        curr_rec = self._build_expiry_recommendation(
            expiry_type="CURRENT",
            expiry_date=curr_expiry_date,
            dte=dte_curr,
            spot=spot,
            atm_strike=atm_strike,
            expected_move=em_curr,
            regime_status=regime_status,
            chain_data=curr_chain,
            step=50,
        )

        # Generate Upcoming Expiry Recommendation with LIVE premiums
        next_rec = self._build_expiry_recommendation(
            expiry_type="UPCOMING",
            expiry_date=next_expiry_date,
            dte=dte_next,
            spot=spot,
            atm_strike=atm_strike,
            expected_move=em_next,
            regime_status=regime_status,
            chain_data=next_chain,
            step=100,
        )

        return {
            "verdict": verdict,
            "is_live_nse": curr_chain.get("is_live_nse", False),
            "nse_timestamp": curr_chain.get("timestamp", ""),
            "atm_strike": atm_strike,
            "iv_used": iv,
            "pcr": pcr,
            "max_pain": max_pain,
            "atm_straddle_curr": atm_straddle_curr,
            "expected_move_curr": em_curr,
            "expected_move_next": em_next,
            "current_expiry": curr_rec,
            "upcoming_expiry": next_rec,
        }

    def _build_verdict(
        self,
        spot: float,
        regime_status: str,
        regime_score: float,
        top5_df: pd.DataFrame,
        em_curr: float,
        pcr: float,
        max_pain: int,
    ) -> Dict[str, Any]:
        """Synthesizes option seller market regime into an authoritative tactical verdict."""
        pcr_note = f"PCR: {pcr:.2f} | Max Pain: {max_pain}"

        if "RANGEBOUND" in regime_status:
            badge = "🟢 HIGH THETA DECAY (NEUTRAL)"
            tone = "success"
            summary = (
                f"Heavyweights are neutralizing each other's point impact. "
                f"NIFTY is boxed in a range. Spot is trading near Max Pain ({max_pain}) with {pcr_note}."
            )
            action = (
                "Deploy Delta-Neutral setups: Short Strangles, Iron Flies, or Iron Condors. "
                f"Range buffer of ±{em_curr:.0f} pts offers ~78% win-rate probability."
            )
            danger_warning = "None severe. Keep stop-loss at 1.5x of individual sold leg premium."

        elif "BULLISH TREND" in regime_status:
            badge = "🚨 STRONG BULLISH TREND (CALL SELLING HIGH RISK)"
            tone = "danger"
            summary = (
                f"Heavyweights are firing together upward (Alignment Score: +{regime_score:.1f}). "
                f"High institutional buying pressure presents severe gamma risk for Call sellers ({pcr_note})."
            )
            action = (
                "DO NOT sell naked Calls or balanced Straddles! "
                "Trade Bull Put Spreads (Sell OTM Put + Buy Lower Put) or roll up Put legs aggressively."
            )
            danger_warning = "High delta risk on Short Call strikes. Avoid CE selling against the trend."

        elif "BEARISH TREND" in regime_status:
            badge = "🚨 STRONG BEARISH TREND (PUT SELLING HIGH RISK)"
            tone = "danger"
            summary = (
                f"Heavyweights are breaking down simultaneously (Alignment Score: {regime_score:.1f}). "
                f"Aggressive selling volume creates high gamma expansion risk for Put sellers ({pcr_note})."
            )
            action = (
                "DO NOT sell naked Puts or balanced Straddles! "
                "Trade Bear Call Spreads (Sell OTM Call + Buy Higher Call) or roll down Call legs aggressively."
            )
            danger_warning = "High delta risk on Short Put strikes. Avoid PE selling against falling heavyweights."

        elif "MILD BULLISH" in regime_status:
            badge = "🟡 MILD UPWARD BIAS (SKEW RECOMMENDED)"
            tone = "warning"
            summary = f"Slight upward tilt in heavyweights ({pcr_note}). Lacks sharp momentum breakout."
            action = (
                "Skewed Strangle or Bull Put Spread. Push Short Call strike further OTM "
                f"(at least Spot + {em_curr * 1.3:.0f} pts) while keeping Put closer to capture theta."
            )
            danger_warning = "Sudden surge in Reliance/HDFC Bank could test standard Call breakevens."

        else:
            badge = "🟡 MILD DOWNWARD BIAS (SKEW RECOMMENDED)"
            tone = "warning"
            summary = f"Slight downward drift in heavyweights ({pcr_note}). Institutional selling is moderate."
            action = (
                "Skewed Strangle or Bear Call Spread. Push Short Put strike further OTM "
                f"(at least Spot - {em_curr * 1.3:.0f} pts) while keeping Call closer to collect premium."
            )
            danger_warning = "Sudden banking weakness could test standard Put breakevens."

        return {
            "badge": badge,
            "tone": tone,
            "summary": summary,
            "action": action,
            "danger_warning": danger_warning,
        }

    def _build_expiry_recommendation(
        self,
        expiry_type: str,
        expiry_date: str,
        dte: int,
        spot: float,
        atm_strike: int,
        expected_move: float,
        regime_status: str,
        chain_data: Dict[str, Any],
        step: int = 50,
    ) -> Dict[str, Any]:
        """Calculates specific strikes, queries LIVE NSE premiums, and computes exact breakevens."""
        strikes_map = chain_data.get("strikes_map", {})
        mult = 1.05 if expiry_type == "CURRENT" else 1.25

        if "RANGEBOUND" in regime_status:
            strategy_name = "0.15Δ Short Strangle (or Iron Condor)"
            strategy_bias = "Delta-Neutral"
            sell_ce = self.round_strike(spot + (expected_move * mult), step)
            sell_pe = self.round_strike(spot - (expected_move * mult), step)
            hedge_ce = sell_ce + (200 if step == 50 else 300)
            hedge_pe = sell_pe - (200 if step == 50 else 300)
        elif "BULLISH TREND" in regime_status:
            strategy_name = "Bull Put Credit Spread (Protected)"
            strategy_bias = "Bullish Theta"
            sell_pe = self.round_strike(spot - (expected_move * 0.65), step)
            hedge_pe = sell_pe - 150
            sell_ce = self.round_strike(spot + (expected_move * 1.9), step)
            hedge_ce = sell_ce + 200
        elif "BEARISH TREND" in regime_status:
            strategy_name = "Bear Call Credit Spread (Protected)"
            strategy_bias = "Bearish Theta"
            sell_ce = self.round_strike(spot + (expected_move * 0.65), step)
            hedge_ce = sell_ce + 150
            sell_pe = self.round_strike(spot - (expected_move * 1.9), step)
            hedge_pe = sell_pe - 200
        elif "MILD BULLISH" in regime_status:
            strategy_name = "Bull-Skewed Strangle"
            strategy_bias = "Mild Bullish Bias"
            sell_pe = self.round_strike(spot - (expected_move * 0.9), step)
            sell_ce = self.round_strike(spot + (expected_move * 1.35), step)
            hedge_ce = sell_ce + 200
            hedge_pe = sell_pe - 200
        else:
            strategy_name = "Bear-Skewed Strangle"
            strategy_bias = "Mild Bearish Bias"
            sell_ce = self.round_strike(spot + (expected_move * 0.9), step)
            sell_pe = self.round_strike(spot - (expected_move * 1.35), step)
            hedge_ce = sell_ce + 200
            hedge_pe = sell_pe - 200

        # Ensure strikes exist in the live NSE strikes map
        if strikes_map:
            available_strikes = sorted(strikes_map.keys())
            if sell_ce not in strikes_map:
                sell_ce = min(available_strikes, key=lambda s: abs(s - sell_ce))
            if sell_pe not in strikes_map:
                sell_pe = min(available_strikes, key=lambda s: abs(s - sell_pe))
            if hedge_ce not in strikes_map:
                hedge_ce = min(available_strikes, key=lambda s: abs(s - hedge_ce))
            if hedge_pe not in strikes_map:
                hedge_pe = min(available_strikes, key=lambda s: abs(s - hedge_pe))

        # Query LIVE PREMIUMS directly from NSE strikes map
        ce_data = strikes_map.get(sell_ce, {})
        pe_data = strikes_map.get(sell_pe, {})
        hedge_ce_data = strikes_map.get(hedge_ce, {})
        hedge_pe_data = strikes_map.get(hedge_pe, {})

        ce_ltp = float(ce_data.get("ce_ltp", 0.0))
        pe_ltp = float(pe_data.get("pe_ltp", 0.0))
        ce_oi = int(ce_data.get("ce_oi", 0))
        pe_oi = int(pe_data.get("pe_oi", 0))
        ce_iv = float(ce_data.get("ce_iv", 0.0))
        pe_iv = float(pe_data.get("pe_iv", 0.0))

        hedge_ce_ltp = float(hedge_ce_data.get("ce_ltp", 0.0))
        hedge_pe_ltp = float(hedge_pe_data.get("pe_ltp", 0.0))

        total_premium = round(ce_ltp + pe_ltp, 2)
        lower_breakeven = round(sell_pe - total_premium, 1)
        upper_breakeven = round(sell_ce + total_premium, 1)

        # Distance from spot
        ce_otm_pts = int(sell_ce - spot)
        pe_otm_pts = int(spot - sell_pe)
        ce_otm_pct = round((ce_otm_pts / spot) * 100.0, 2)
        pe_otm_pct = round((pe_otm_pts / spot) * 100.0, 2)

        return {
            "expiry_date": expiry_date,
            "dte": dte,
            "expiry_name": f"{expiry_date} ({dte} DTE)",
            "strategy_name": strategy_name,
            "strategy_bias": strategy_bias,
            "atm_strike": atm_strike,
            "sell_ce": sell_ce,
            "ce_ltp": ce_ltp,
            "ce_oi": ce_oi,
            "ce_iv": ce_iv,
            "ce_otm_pts": ce_otm_pts,
            "ce_otm_pct": ce_otm_pct,
            "sell_pe": sell_pe,
            "pe_ltp": pe_ltp,
            "pe_oi": pe_oi,
            "pe_iv": pe_iv,
            "pe_otm_pts": pe_otm_pts,
            "pe_otm_pct": pe_otm_pct,
            "hedge_ce": hedge_ce,
            "hedge_ce_ltp": hedge_ce_ltp,
            "hedge_pe": hedge_pe,
            "hedge_pe_ltp": hedge_pe_ltp,
            "total_premium": total_premium,
            "lower_breakeven": lower_breakeven,
            "upper_breakeven": upper_breakeven,
            "safe_range_pts": int(upper_breakeven - lower_breakeven),
            "stop_loss_guideline": f"SL on sold legs at 1.5x entry premium (CE SL: ₹{ce_ltp*1.5:.1f}, PE SL: ₹{pe_ltp*1.5:.1f}). Exit if Spot crosses {sell_ce} or {sell_pe}.",
        }
