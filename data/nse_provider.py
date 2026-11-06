"""
NSE India Official Public Data Provider.
Fetches real-time NIFTY 50 constituent quotes, index value, and volume data.
"""

import time
import requests
from typing import Dict, Any, Tuple
import pandas as pd
from data.base import BaseDataProvider
from config import DEFAULT_NIFTY_VALUE


class NSEDataProvider(BaseDataProvider):
    """Fetches live quotes directly from NSE India API with session handling."""

    BASE_URL = "https://www.nseindia.com"
    API_URL = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/market-data/live-equity-market",
    }

    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.last_cookie_time = 0
        self.cookie_ttl = 300  # Refresh cookies every 5 minutes

    def _refresh_session(self):
        """Fetches fresh session cookies from NSE homepage."""
        try:
            now = time.time()
            if now - self.last_cookie_time > self.cookie_ttl:
                self.session.get(self.BASE_URL, timeout=self.timeout)
                self.last_cookie_time = now
        except Exception:
            pass

    def fetch_nifty_data(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Fetches live NIFTY 50 constituent table and index metadata.
        """
        self._refresh_session()

        try:
            resp = self.session.get(self.API_URL, timeout=self.timeout)
            if resp.status_code == 401 or resp.status_code == 403:
                # Re-initialize session cookies if unauthorized
                self.session = requests.Session()
                self.session.headers.update(self.HEADERS)
                self.session.get(self.BASE_URL, timeout=self.timeout)
                resp = self.session.get(self.API_URL, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                raw_data = data.get("data", [])
                if not raw_data:
                    raise ValueError("Empty data returned from NSE API")

                # The first entry in 'data' is the NIFTY 50 index summary itself
                nifty_meta = {}
                records = []

                for item in raw_data:
                    symbol = item.get("symbol", "")
                    if symbol == "NIFTY 50":
                        nifty_meta = {
                            "lastPrice": float(item.get("lastPrice", DEFAULT_NIFTY_VALUE)),
                            "change": float(item.get("change", 0.0)),
                            "pChange": float(item.get("pChange", 0.0)),
                            "previousClose": float(
                                item.get("previousClose", DEFAULT_NIFTY_VALUE)
                            ),
                            "open": float(item.get("open", DEFAULT_NIFTY_VALUE)),
                            "dayHigh": float(item.get("dayHigh", DEFAULT_NIFTY_VALUE)),
                            "dayLow": float(item.get("dayLow", DEFAULT_NIFTY_VALUE)),
                            "timestamp": data.get("timestamp", ""),
                        }
                    else:
                        records.append(
                            {
                                "symbol": symbol,
                                "lastPrice": float(item.get("lastPrice", 0.0)),
                                "change": float(item.get("change", 0.0)),
                                "pChange": float(item.get("pChange", 0.0)),
                                "volume": int(item.get("totalTradedVolume", 0)),
                                "totalTradedValue": float(
                                    item.get("totalTradedValue", 0.0)
                                ),
                                "previousClose": float(item.get("previousClose", 0.0)),
                                "dayHigh": float(item.get("dayHigh", 0.0)),
                                "dayLow": float(item.get("dayLow", 0.0)),
                            }
                        )

                df = pd.DataFrame(records)
                return df, nifty_meta

        except Exception as e:
            # Propagate error so caller can fallback to yfinance or demo mode
            raise ConnectionError(f"NSE API fetch failed: {e}")

    def fetch_average_volumes(self, days: int = 20) -> Dict[str, float]:
        """
        NSE public endpoint doesn't provide 20-day historical SMA in this single call.
        Historical volume is provided via Yahoo Finance provider.
        """
        return {}
