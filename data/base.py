"""
Base interface for Market Data Providers.
Allows seamless switching between NSE Public Scraping, Yahoo Finance, and Broker APIs (Zerodha / Dhan).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import pandas as pd


class BaseDataProvider(ABC):
    """Abstract interface for fetching constituent stock data and historical statistics."""

    @abstractmethod
    def fetch_nifty_data(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Fetches live constituent data for NIFTY 50.
        Returns:
            Tuple[pd.DataFrame, Dict[str, Any]]:
            - DataFrame with columns: ['symbol', 'lastPrice', 'change', 'pChange', 'volume', 'previousClose']
            - Dict with NIFTY 50 index metadata: {'lastPrice', 'change', 'pChange', 'previousClose'}
        """
        pass

    @abstractmethod
    def fetch_average_volumes(self, days: int = 20) -> Dict[str, float]:
        """
        Fetches 20-day historical average volume per stock for RVOL computation.
        Returns:
            Dict[str, float]: Mapping of symbol -> average daily volume.
        """
        pass
