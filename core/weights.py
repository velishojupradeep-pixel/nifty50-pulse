"""
NIFTY 50 Weightage and Point Contribution Engine.
Computes real-time index point impact per constituent stock.
"""

from typing import Dict, List, Optional
import pandas as pd
from config import NIFTY_50_WEIGHTS, DEFAULT_NIFTY_VALUE


class WeightEngine:
    """Calculates weighted point impact of each constituent on NIFTY 50."""

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        self.weights = custom_weights or NIFTY_50_WEIGHTS.copy()
        self._normalize_weights()

    def _normalize_weights(self):
        """Ensure constituent weights sum to 100%."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: (v / total) * 100.0 for k, v in self.weights.items()}

    def get_weight(self, symbol: str) -> float:
        """Get percentage weight of a symbol in NIFTY 50."""
        return self.weights.get(symbol.upper(), 0.0)

    def calculate_points_contribution(
        self,
        symbol: str,
        p_change: float,
        nifty_prev_close: float = DEFAULT_NIFTY_VALUE,
    ) -> float:
        """
        Calculates the exact point contribution of an individual stock to NIFTY.

        Formula:
        Points Contribution = (Weight % / 100) * (Stock % Change / 100) * Nifty Prev Close
                            = (Weight * Stock % Change * Nifty Prev Close) / 10,000

        Example:
        HDFCBANK (weight ~11.5%) up +2.0% with Nifty at 24,000:
        Contribution = (11.5 * 2.0 * 24000) / 10,000 = +55.20 points.
        """
        weight = self.get_weight(symbol)
        if weight <= 0:
            return 0.0
        return (weight * p_change * nifty_prev_close) / 10000.0

    def enrich_dataframe_with_points(
        self, df: pd.DataFrame, nifty_prev_close: float = DEFAULT_NIFTY_VALUE
    ) -> pd.DataFrame:
        """
        Takes a DataFrame containing 'symbol' and 'pChange' and appends:
        - 'weight': Percentage weight in Nifty 50
        - 'points_contribution': Points moved by the stock in Nifty
        - 'weighted_impact': Absolute contribution magnitude
        """
        if df.empty:
            return df

        df = df.copy()
        df["symbol_clean"] = df["symbol"].str.upper().str.replace(".NS", "", regex=False)
        df["weight"] = df["symbol_clean"].apply(self.get_weight)
        
        # Calculate point contribution
        df["points_contribution"] = (
            df["weight"] * df["pChange"] * nifty_prev_close
        ) / 10000.0

        # Weighted impact magnitude
        df["abs_points_contribution"] = df["points_contribution"].abs()

        return df
