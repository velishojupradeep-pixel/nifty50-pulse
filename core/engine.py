"""
Calculation and Analytics Engine tailored for NIFTY 50 Option Traders.
Handles Market Regime detection, Heavyweight Tug-of-War, Volume/RVOL surges, and Top Gainers/Losers.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from config import (
    TOP_5_HEAVYWEIGHTS,
    TOP_10_HEAVYWEIGHTS,
    REGIME_THRESHOLDS,
    VOLUME_THRESHOLDS,
    DEFAULT_NIFTY_VALUE,
)
from core.weights import WeightEngine
from core.sectors import SectorAnalyzer
from core.advisor import StrikeAdvisor


class AnalyticsEngine:
    """Core analytics engine computing option seller signals and constituent metrics."""

    def __init__(self, default_iv: float = 13.5):
        self.weight_engine = WeightEngine()
        self.sector_analyzer = SectorAnalyzer()
        self.advisor = StrikeAdvisor(default_iv=default_iv)

    def process_market_data(
        self,
        df: pd.DataFrame,
        nifty_meta: Dict[str, Any],
        avg_volumes: Dict[str, float] = None,
        custom_iv: float = None,
        curr_chain: Dict[str, Any] = None,
        next_chain: Dict[str, Any] = None,
        official_expiries: list = None,
    ) -> Dict[str, Any]:
        """
        Takes raw constituent data and computes complete analytics:
        - Enriched dataframe with weights, points, RVOL
        - Option seller regime & heavyweight alignment
        - Top gainers/losers by % and by Nifty point impact
        - Volume surges
        - Sector breakdown
        """
        if df.empty:
            return {}

        nifty_prev_close = nifty_meta.get("previousClose", DEFAULT_NIFTY_VALUE)
        nifty_ltp = nifty_meta.get("lastPrice", nifty_prev_close)
        nifty_p_change = nifty_meta.get("pChange", 0.0)
        nifty_change = nifty_meta.get("change", 0.0)

        # 1. Enrich with weights & points
        df = self.weight_engine.enrich_dataframe_with_points(
            df, nifty_prev_close=nifty_prev_close
        )

        # 2. Enrich with Sector
        df["sector"] = df["symbol_clean"].apply(self.sector_analyzer.get_sector)

        # 3. Calculate RVOL (Relative Volume)
        avg_vols = avg_volumes or {}
        df["avg_volume_20d"] = df["symbol_clean"].map(avg_vols).fillna(df["volume"])
        df["rvol"] = np.where(
            df["avg_volume_20d"] > 0,
            (df["volume"] / df["avg_volume_20d"]).round(2),
            1.0,
        )

        # 4. Volume Surge Tagging
        def get_volume_tag(row):
            rvol = row["rvol"]
            p_change = row["pChange"]
            if rvol >= VOLUME_THRESHOLDS["RVOL_EXTREME"]:
                return "🔥 Extreme Surge" if p_change >= 0 else "🚨 Heavy Selloff"
            elif rvol >= VOLUME_THRESHOLDS["RVOL_HIGH"]:
                return "⚡ High Volume" if p_change >= 0 else "⚠️ High Volume Sell"
            elif rvol >= VOLUME_THRESHOLDS["RVOL_MODERATE"]:
                return "Active"
            elif rvol <= 0.6:
                return "Dull / Low Vol"
            return "Normal"

        df["volume_status"] = df.apply(get_volume_tag, axis=1)

        # 5. Heavyweight Tug-of-War & Market Regime Calculation
        top5_df = df[df["symbol_clean"].isin(TOP_5_HEAVYWEIGHTS)].copy()
        top10_df = df[df["symbol_clean"].isin(TOP_10_HEAVYWEIGHTS)].copy()

        regime_analysis = self._calculate_option_regime(df, top5_df, top10_df)

        # 5b. Generate Option Seller Strike Verdict and Recommendations
        advisor_data = self.advisor.generate_verdict_and_strikes(
            nifty_meta=nifty_meta,
            regime=regime_analysis,
            top5_df=top5_df,
            custom_iv=custom_iv,
            curr_chain=curr_chain,
            next_chain=next_chain,
            official_expiries=official_expiries,
        )

        # 6. Gainers & Losers
        by_pct_gainers = df.sort_values(by="pChange", ascending=False).head(5)
        by_pct_losers = df.sort_values(by="pChange", ascending=True).head(5)

        by_points_gainers = df.sort_values(
            by="points_contribution", ascending=False
        ).head(5)
        by_points_losers = df.sort_values(
            by="points_contribution", ascending=True
        ).head(5)

        # 7. Volume Surges
        volume_surges = (
            df[df["rvol"] >= VOLUME_THRESHOLDS["RVOL_MODERATE"]]
            .sort_values(by="rvol", ascending=False)
            .head(10)
        )

        # 8. Sector Breakdown
        sector_summary = self.sector_analyzer.analyze_sectors(df)

        # 9. Breadth
        advances = int((df["pChange"] > 0).sum())
        declines = int((df["pChange"] < 0).sum())
        unchanged = int((df["pChange"] == 0).sum())

        bullish_weight = float(df[df["pChange"] > 0]["weight"].sum())
        bearish_weight = float(df[df["pChange"] < 0]["weight"].sum())

        return {
            "df": df,
            "nifty_meta": {
                "lastPrice": nifty_ltp,
                "change": nifty_change,
                "pChange": nifty_p_change,
                "previousClose": nifty_prev_close,
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "bullish_weight": round(bullish_weight, 1),
                "bearish_weight": round(bearish_weight, 1),
            },
            "regime": regime_analysis,
            "advisor": advisor_data,
            "top5_heavyweights": top5_df.sort_values(by="weight", ascending=False),
            "top10_heavyweights": top10_df.sort_values(by="weight", ascending=False),
            "by_pct_gainers": by_pct_gainers,
            "by_pct_losers": by_pct_losers,
            "by_points_gainers": by_points_gainers,
            "by_points_draggers": by_points_losers,
            "volume_surges": volume_surges,
            "sector_summary": sector_summary,
        }

    def _calculate_option_regime(
        self, df: pd.DataFrame, top5_df: pd.DataFrame, top10_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyzes directional coherence among the heavyweights.
        When heavyweights pull in opposing directions, Nifty stays sideways (Tug-of-War).
        When heavyweights pull together, a trending move is in play.
        """
        if top5_df.empty:
            return {
                "status": "UNKNOWN",
                "score": 0.0,
                "badge": "Neutral",
                "description": "Insufficient data",
                "seller_strategy": "Maintain standard risk rules",
            }

        top5_points = top5_df["points_contribution"].sum()
        top10_points = top10_df["points_contribution"].sum()
        total_points = df["points_contribution"].sum()

        # Weighted alignment metric (-100 to +100)
        # Sum of (weight * sign(pChange) * min(abs(pChange)/1.0, 1.0)) normalized by top10 weight
        total_top10_weight = top10_df["weight"].sum()
        if total_top10_weight > 0:
            weighted_directional_score = sum(
                row["weight"] * np.clip(row["pChange"] / 1.5, -1.0, 1.0)
                for _, row in top10_df.iterrows()
            )
            normalized_score = (weighted_directional_score / total_top10_weight) * 100.0
        else:
            normalized_score = 0.0

        # Check divergence in Top 5 (e.g. some up, some down)
        top5_greens = (top5_df["pChange"] > 0.1).sum()
        top5_reds = (top5_df["pChange"] < -0.1).sum()

        if (
            REGIME_THRESHOLDS["RANGEBOUND_MIN"]
            <= normalized_score
            <= REGIME_THRESHOLDS["RANGEBOUND_MAX"]
            or (top5_greens >= 2 and top5_reds >= 2)
        ):
            status = "RANGEBOUND / TUG-OF-WAR"
            badge = "🟢 High Theta Decay Friendly"
            badge_color = "green"
            description = (
                f"Heavyweights are neutralizing each other ({top5_greens} UP vs {top5_reds} DOWN). "
                "Index is rangebound; low delta momentum risk."
            )
            seller_strategy = (
                "Ideal for Short Straddles, Iron Flies, and Rangebound Iron Condors. "
                "Look for steady premium decay."
            )
        elif normalized_score > REGIME_THRESHOLDS["BULLISH_TREND"]:
            status = "STRONG BULLISH TREND"
            badge = "🚨 Delta Risk for Call Sellers"
            badge_color = "red"
            description = (
                f"Heavyweights are aligned upward (Top 10 score: +{normalized_score:.1f}). "
                f"Top 5 contributed +{top5_points:.1f} pts."
            )
            seller_strategy = (
                "Avoid naked Call selling. Favor Bull Put Spreads or trailing OTM Put sales. "
                "Hedge short delta immediately."
            )
        elif normalized_score < REGIME_THRESHOLDS["BEARISH_TREND"]:
            status = "STRONG BEARISH TREND"
            badge = "🚨 Delta Risk for Put Sellers"
            badge_color = "red"
            description = (
                f"Heavyweights are breaking down together (Top 10 score: {normalized_score:.1f}). "
                f"Top 5 dragged {top5_points:.1f} pts."
            )
            seller_strategy = (
                "Avoid naked Put selling. Favor Bear Call Spreads or trailing OTM Call sales. "
                "Hedge short delta immediately."
            )
        elif normalized_score > 0:
            status = "MILD BULLISH BIAS"
            badge = "🟡 Moderate Delta"
            badge_color = "orange"
            description = "Slight upward tilt in heavyweights, but lacks strong institutional momentum."
            seller_strategy = "Wider Iron Condors or staggered Put Credit Spreads."
        else:
            status = "MILD BEARISH BIAS"
            badge = "🟡 Moderate Delta"
            badge_color = "orange"
            description = "Slight downward tilt in heavyweights, but lacks heavy selling volume."
            seller_strategy = "Wider Iron Condors or staggered Call Credit Spreads."

        return {
            "status": status,
            "score": round(normalized_score, 1),
            "badge": badge,
            "badge_color": badge_color,
            "description": description,
            "seller_strategy": seller_strategy,
            "top5_points": round(top5_points, 1),
            "top10_points": round(top10_points, 1),
            "total_points": round(total_points, 1),
            "top5_greens": int(top5_greens),
            "top5_reds": int(top5_reds),
        }
