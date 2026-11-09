"""
Official NSE IX GIFT Nifty Data Provider.
Fetches real-time GIFT NIFTY (formerly SGX Nifty) quotes, changes, and spreads directly from NSE IX (GIFT City).
URL: https://www.nseix.com/api/nifty-market-rate
"""

import time
from typing import Dict, Any, Optional
from curl_cffi import requests


class GiftNiftyProvider:
    """Fetches real-time GIFT NIFTY index data from NSE IX."""

    API_URL = "https://www.nseix.com/api/nifty-market-rate"
    REFERER = "https://www.nseix.com"

    def __init__(self, cache_ttl: int = 15):
        self.cache_ttl = cache_ttl
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            "Referer": self.REFERER,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_fetch_time = 0
        self.cached_data: Dict[str, Any] = {}

    def fetch_gift_nifty(self) -> Dict[str, Any]:
        """
        Fetches live GIFT NIFTY quote.
        Returns:
            Dict containing: lastPrice, change, pChange, timestamp, open, close, is_live
        """
        now = time.time()
        if self.cached_data and (now - self.last_fetch_time < self.cache_ttl):
            return self.cached_data

        try:
            resp = self.session.get(self.API_URL, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list):
                    item = data[0]
                    curr_val_str = str(item.get("CURRVALUE", "0")).replace(",", "")
                    last_price = float(curr_val_str)
                    change = float(item.get("CHANGE", 0.0))
                    p_change = float(item.get("PERCHANGE", 0.0))
                    timestamp = item.get("FULLTIMESTAMP", item.get("TIMESTAMP", ""))
                    open_val = float(item.get("OI_OPEN_INDEX_VAL", last_price))
                    prev_close = float(item.get("OI_CLOSE_INDEX_VAL", last_price))

                    result = {
                        "is_live": True,
                        "name": "GIFT NIFTY",
                        "lastPrice": last_price,
                        "change": change,
                        "pChange": p_change,
                        "open": open_val,
                        "previousClose": prev_close,
                        "timestamp": timestamp,
                    }
                    self.cached_data = result
                    self.last_fetch_time = now
                    return result
        except Exception:
            pass

        # Return cached or default benchmark if temporary network timeout
        if self.cached_data:
            return self.cached_data

        return {
            "is_live": False,
            "name": "GIFT NIFTY",
            "lastPrice": 24925.0,
            "change": -50.0,
            "pChange": -0.20,
            "open": 24980.0,
            "previousClose": 24975.0,
            "timestamp": time.strftime("%d-%b-%Y %H:%M"),
        }
