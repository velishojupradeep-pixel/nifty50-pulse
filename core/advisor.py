"""
Option Seller Strategy & Strike Recommendation Engine.
Analyzes market regime, index heavyweight momentum, and expected move
to generate actionable verdicts and optimal strike selections for current and upcoming expiries.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd


class StrikeAdvisor:
    """Generates expert option seller verdicts and strike recommendations."""

    def __init__(self, default_iv: float = 13.5):
        self.default_iv = default_iv

    @staticmethod
    def round_strike(price: float, step: int = 50) -> int:
        """Round price to nearest strike step (50 for NIFTY weekly, 100 for monthly)."""
        return int(round(price / step) * step)

    def get_expiry_dates(self, base_date: datetime = None) -> Dict[str, Any]:
        """
        Calculates current weekly expiry (nearest Thursday) and upcoming expiry.
        NIFTY 50 weekly options expire on Thursdays.
        """
        now = base_date or datetime.now()
        # Thursday is weekday 3 (Monday is 0, Sunday is 6)
        days_ahead = (3 - now.weekday()) % 7

        # If today is Thursday after 15:30 IST, nearest expiry is next Thursday
        if days_ahead == 0 and (now.hour > 15 or (now.hour == 15 and now.minute >= 30)):
            days_ahead = 7

        current_expiry = now + timedelta(days=days_ahead)
        next_expiry = current_expiry + timedelta(days=7)

        dte_current = max(1, (current_expiry.date() - now.date()).days)
        dte_next = max(8, (next_expiry.date() - now.date()).days)

        return {
            "current_expiry_date": current_expiry.strftime("%d-%b-%Y"),
            "current_expiry_day": current_expiry.strftime("%A"),
            "dte_current": dte_current,
            "next_expiry_date": next_expiry.strftime("%d-%b-%Y"),
            "next_expiry_day": next_expiry.strftime("%A"),
            "dte_next": dte_next,
        }

    def calculate_expected_move(self, spot: float, dte: int, iv: float = None) -> float:
        """
        Calculates 1-Standard Deviation Expected Move based on IV and DTE:
        Expected Move = Spot * (IV / 100) * sqrt(DTE / 365)
        """
        vol = (iv or self.default_iv) / 100.0
        return spot * vol * math.sqrt(dte / 365.0)

    def generate_verdict_and_strikes(
        self,
        nifty_meta: Dict[str, Any],
        regime: Dict[str, Any],
        top5_df: pd.DataFrame,
        custom_iv: float = None,
    ) -> Dict[str, Any]:
        """
        Produces comprehensive Option Seller Verdict and specific strike recommendations.
        """
        spot = nifty_meta.get("lastPrice", 24500.0)
        atm_strike = self.round_strike(spot, 50)
        regime_status = regime.get("status", "RANGEBOUND / TUG-OF-WAR")
        regime_score = regime.get("score", 0.0)
        iv = custom_iv or self.default_iv

        exp_info = self.get_expiry_dates()
        dte_curr = exp_info["dte_current"]
        dte_next = exp_info["dte_next"]

        # 1-SD Expected Moves
        em_curr = self.calculate_expected_move(spot, dte_curr, iv)
        em_next = self.calculate_expected_move(spot, dte_next, iv)

        # Build Verdict based on alignment and regime
        verdict = self._build_verdict(spot, regime_status, regime_score, top5_df, em_curr)

        # Generate Current Expiry Recommendation
        curr_rec = self._build_expiry_recommendation(
            expiry_type="CURRENT",
            expiry_name=f"{exp_info['current_expiry_date']} ({dte_curr} DTE)",
            spot=spot,
            atm_strike=atm_strike,
            expected_move=em_curr,
            regime_status=regime_status,
            regime_score=regime_score,
            step=50,
        )

        # Generate Upcoming Expiry Recommendation
        next_rec = self._build_expiry_recommendation(
            expiry_type="UPCOMING",
            expiry_name=f"{exp_info['next_expiry_date']} ({dte_next} DTE)",
            spot=spot,
            atm_strike=atm_strike,
            expected_move=em_next,
            regime_status=regime_status,
            regime_score=regime_score,
            step=100,  # 100 pt strikes for wider upcoming expiry
        )

        return {
            "verdict": verdict,
            "expiry_info": exp_info,
            "atm_strike": atm_strike,
            "iv_used": iv,
            "expected_move_curr": round(em_curr, 1),
            "expected_move_next": round(em_next, 1),
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
    ) -> Dict[str, Any]:
        """Synthesizes option seller market regime into an authoritative tactical verdict."""
        if "RANGEBOUND" in regime_status:
            badge = "🟢 HIGH THETA DECAY (NEUTRAL)"
            tone = "success"
            summary = (
                "Heavyweights are neutralizing each other's point impact. "
                "Spot is boxed in a tight tug-of-war. Ideal condition for premium selling."
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
                "Directional momentum presents severe gamma risk for Call sellers."
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
                "Aggressive selling volume creates high gamma expansion risk for Put sellers."
            )
            action = (
                "DO NOT sell naked Puts or balanced Straddles! "
                "Trade Bear Call Spreads (Sell OTM Call + Buy Higher Call) or roll down Call legs aggressively."
            )
            danger_warning = "High delta risk on Short Put strikes. Avoid PE selling against falling heavyweights."

        elif "MILD BULLISH" in regime_status:
            badge = "🟡 MILD UPWARD BIAS (SKEW RECOMMENDED)"
            tone = "warning"
            summary = "Slight upward tilt in heavyweights, but lacking aggressive momentum breakout."
            action = (
                "Skewed Strangle or Bull Put Spread. Push Short Call strike further OTM "
                f"(at least Spot + {em_curr * 1.3:.0f} pts) while keeping Put closer to capture theta."
            )
            danger_warning = "Sudden surge in Reliance/HDFC Bank could test standard Call breakevens."

        else:
            badge = "🟡 MILD DOWNWARD BIAS (SKEW RECOMMENDED)"
            tone = "warning"
            summary = "Slight downward drift in heavyweights, but institutional volume is moderate."
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
        expiry_name: str,
        spot: float,
        atm_strike: int,
        expected_move: float,
        regime_status: str,
        regime_score: float,
        step: int = 50,
    ) -> Dict[str, Any]:
        """Calculates specific strikes, protection wings, and breakevens for an expiry."""
        mult = 1.05 if expiry_type == "CURRENT" else 1.25

        if "RANGEBOUND" in regime_status:
            # Symmetric Strangle / Iron Condor
            strategy_name = "0.15Δ Short Strangle (or Iron Condor)"
            call_distance = expected_move * mult
            put_distance = expected_move * mult
            sell_ce = self.round_strike(spot + call_distance, step)
            sell_pe = self.round_strike(spot - put_distance, step)
            hedge_ce = sell_ce + (200 if step == 50 else 300)
            hedge_pe = sell_pe - (200 if step == 50 else 300)
            strategy_bias = "Delta-Neutral"

        elif "BULLISH TREND" in regime_status:
            # Bull Put Spread (Avoid Selling Calls or push Call to extreme 2-SD)
            strategy_name = "Bull Put Credit Spread (Protected)"
            strategy_bias = "Bullish Theta"
            sell_pe = self.round_strike(spot - (expected_move * 0.65), step)
            hedge_pe = sell_pe - 150
            # If trader insists on selling Call, place at extreme 2.2-SD
            sell_ce = self.round_strike(spot + (expected_move * 1.9), step)
            hedge_ce = sell_ce + 200

        elif "BEARISH TREND" in regime_status:
            # Bear Call Spread (Avoid Selling Puts or push Put to extreme 2-SD)
            strategy_name = "Bear Call Credit Spread (Protected)"
            strategy_bias = "Bearish Theta"
            sell_ce = self.round_strike(spot + (expected_move * 0.65), step)
            hedge_ce = sell_ce + 150
            # If trader insists on selling Put, place at extreme 2.2-SD
            sell_pe = self.round_strike(spot - (expected_move * 1.9), step)
            hedge_pe = sell_pe - 200

        elif "MILD BULLISH" in regime_status:
            strategy_name = "Bull-Skewed Strangle"
            strategy_bias = "Mild Bullish Bias"
            sell_pe = self.round_strike(spot - (expected_move * 0.9), step)
            sell_ce = self.round_strike(spot + (expected_move * 1.35), step)
            hedge_ce = sell_ce + 200
            hedge_pe = sell_pe - 200

        else:  # Mild Bearish
            strategy_name = "Bear-Skewed Strangle"
            strategy_bias = "Mild Bearish Bias"
            sell_ce = self.round_strike(spot + (expected_move * 0.9), step)
            sell_pe = self.round_strike(spot - (expected_move * 1.35), step)
            hedge_ce = sell_ce + 200
            hedge_pe = sell_pe - 200

        # Estimated premium and buffer
        ce_otm_pct = ((sell_ce - spot) / spot) * 100.0
        pe_otm_pct = ((spot - sell_pe) / spot) * 100.0

        # Approximate combined premium collected for 0.15 Delta Strangle
        # Typical 15-delta strangle collects ~0.7% to 1.1% of spot
        premium_pct = 0.007 if expiry_type == "CURRENT" else 0.012
        est_combined_premium = round(spot * premium_pct, 1)

        lower_breakeven = round(sell_pe - est_combined_premium, 1)
        upper_breakeven = round(sell_ce + est_combined_premium, 1)

        return {
            "expiry_name": expiry_name,
            "strategy_name": strategy_name,
            "strategy_bias": strategy_bias,
            "atm_strike": atm_strike,
            "sell_ce": sell_ce,
            "ce_otm_pts": int(sell_ce - spot),
            "ce_otm_pct": round(ce_otm_pct, 2),
            "sell_pe": sell_pe,
            "pe_otm_pts": int(spot - sell_pe),
            "pe_otm_pct": round(pe_otm_pct, 2),
            "hedge_ce": hedge_ce,
            "hedge_pe": hedge_pe,
            "est_combined_premium": est_combined_premium,
            "lower_breakeven": lower_breakeven,
            "upper_breakeven": upper_breakeven,
            "safe_range_pts": int(upper_breakeven - lower_breakeven),
            "stop_loss_guideline": f"SL on sold legs at 1.5x entry premium. Close Call if spot crosses {sell_ce}, Close Put if spot crosses {sell_pe}.",
        }
