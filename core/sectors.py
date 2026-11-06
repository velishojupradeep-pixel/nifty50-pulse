"""
Sector analysis module for NIFTY 50.
Aggregates points contribution, breadth, and performance across industry sectors.
"""

from typing import Dict, Optional
import pandas as pd
from config import STOCK_SECTORS


class SectorAnalyzer:
    """Aggregates and analyzes constituent stock performance by industry sector."""

    def __init__(self, sector_mapping: Optional[Dict[str, str]] = None):
        self.sector_mapping = sector_mapping or STOCK_SECTORS

    def get_sector(self, symbol: str) -> str:
        clean_symbol = symbol.upper().replace(".NS", "")
        return self.sector_mapping.get(clean_symbol, "Other")

    def analyze_sectors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enriches and aggregates the DataFrame into sector summaries:
        - Points contributed by sector to NIFTY
        - Advances / Declines per sector
        - Average % change
        - Sector weight in NIFTY
        """
        if df.empty or "points_contribution" not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        if "sector" not in df.columns:
            df["sector"] = df["symbol_clean"].apply(self.get_sector)

        sector_summary = (
            df.groupby("sector")
            .agg(
                stocks_count=("symbol", "count"),
                total_weight=("weight", "sum"),
                net_points_contribution=("points_contribution", "sum"),
                avg_p_change=("pChange", "mean"),
                advances=("pChange", lambda x: (x > 0).sum()),
                declines=("pChange", lambda x: (x < 0).sum()),
                unchanged=("pChange", lambda x: (x == 0).sum()),
                total_volume=("volume", "sum") if "volume" in df.columns else ("symbol", "count"),
            )
            .reset_index()
        )

        # Sort by absolute points contribution impact
        sector_summary = sector_summary.sort_values(
            by="net_points_contribution", ascending=False
        )

        return sector_summary
