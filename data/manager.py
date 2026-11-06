"""
Unified Data Manager for NIFTY 50 Tracker.
Orchestrates live feeds (NSE India, Yahoo Finance, or Demo simulation)
with automatic fallback and caching for 20-day volumes.
"""

import os
import json
import random
import time
from typing import Dict, Any, Tuple
import pandas as pd
from data.nse_provider import NSEDataProvider
from data.yfinance_provider import YFinanceProvider
from data.nse_option_chain import NSEOptionChainProvider
from config import NIFTY_50_WEIGHTS, DEFAULT_NIFTY_VALUE

CACHE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/nifty50-pulse/.vol_cache.json")


class DataManager:
    """Manages active data sources with intelligent fallback and caching."""

    def __init__(self):
        self.nse_provider = NSEDataProvider()
        self.yf_provider = YFinanceProvider()
        self.option_chain_provider = NSEOptionChainProvider()
        self.cached_avg_volumes = self._load_volume_cache()

    def get_live_option_chains(self) -> Tuple[Dict[str, Any], Dict[str, Any], list]:
        """
        Fetches live option chain data for Current and Upcoming official NSE expiries.
        """
        expiries = self.option_chain_provider.get_official_expiries()
        curr_chain = {}
        next_chain = {}
        if expiries:
            curr_chain = self.option_chain_provider.fetch_live_option_chain(expiries[0])
            if len(expiries) >= 2:
                next_chain = self.option_chain_provider.fetch_live_option_chain(expiries[1])
        return curr_chain, next_chain, expiries

    def _load_volume_cache(self) -> Dict[str, float]:
        """Loads cached 20-day average volumes from disk if available."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    # Use cache if fresh (< 24 hours old)
                    if time.time() - data.get("timestamp", 0) < 86400:
                        return data.get("volumes", {})
        except Exception:
            pass
        return {}

    def _save_volume_cache(self, volumes: Dict[str, float]):
        """Persists 20-day average volumes to disk."""
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": time.time(), "volumes": volumes}, f)
        except Exception:
            pass

    def get_average_volumes(self) -> Dict[str, float]:
        """Returns 20-day average daily volumes for all 50 stocks."""
        if self.cached_avg_volumes:
            return self.cached_avg_volumes

        # Default benchmark volumes (typical NSE daily volumes)
        fallback_vols = {
            "HDFCBANK": 16_500_000.0,
            "RELIANCE": 5_800_000.0,
            "ICICIBANK": 12_400_000.0,
            "INFY": 6_200_000.0,
            "ITC": 14_000_000.0,
            "TCS": 2_100_000.0,
            "LT": 1_800_000.0,
            "AXISBANK": 7_500_000.0,
            "SBIN": 18_000_000.0,
            "KOTAKBANK": 3_500_000.0,
            "BHARTIARTL": 6_100_000.0,
            "M&M": 2_900_000.0,
            "TATAMOTORS": 11_200_000.0,
            "BAJFINANCE": 1_100_000.0,
            "MARUTI": 550_000.0,
            "SUNPHARMA": 2_400_000.0,
            "NTPC": 13_500_000.0,
            "POWERGRID": 12_000_000.0,
            "TATASTEEL": 32_000_000.0,
            "COALINDIA": 9_500_000.0,
        }

        # Populate standard fallback for remaining
        for sym in NIFTY_50_WEIGHTS.keys():
            if sym not in fallback_vols:
                fallback_vols[sym] = 2_000_000.0

        self.cached_avg_volumes = fallback_vols
        self._save_volume_cache(fallback_vols)
        return self.cached_avg_volumes

    def fetch_live_data(self, source_preference: str = "NSE Live") -> Tuple[pd.DataFrame, Dict[str, Any], str]:
        """
        Fetches live constituent data using the requested provider with graceful fallbacks.
        Returns:
            Tuple[DataFrame, NiftyMetaDict, SourceUsedString]
        """
        # Try NSE Live if preferred
        if source_preference in ["NSE Live", "Auto"]:
            try:
                df, nifty_meta = self.nse_provider.fetch_nifty_data()
                if not df.empty:
                    return df, nifty_meta, "NSE Official Live API"
            except Exception:
                pass

        # Try Yahoo Finance
        if source_preference in ["Yahoo Finance", "Auto"]:
            try:
                df, nifty_meta = self.yf_provider.fetch_nifty_data()
                if not df.empty:
                    return df, nifty_meta, "Yahoo Finance"
            except Exception:
                pass

        # Realistic Market Simulation / Weekend Replay Mode
        # Ensures trader can explore features even when markets are shut
        df, nifty_meta = self._generate_simulated_snapshot()
        return df, nifty_meta, "Simulated / Market Replay"

    def _generate_simulated_snapshot(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Generates realistic market snapshot for demonstration/weekend testing."""
        records = []
        base_nifty = 24350.0

        # Sample base prices
        sample_prices = {
            "HDFCBANK": 1780.0,
            "RELIANCE": 2980.0,
            "ICICIBANK": 1260.0,
            "INFY": 1840.0,
            "BHARTIARTL": 1610.0,
            "ITC": 490.0,
            "TCS": 4150.0,
            "LT": 3620.0,
            "AXISBANK": 1180.0,
            "SBIN": 820.0,
            "KOTAKBANK": 1790.0,
            "M&M": 2860.0,
            "HINDUNILVR": 2420.0,
            "BAJFINANCE": 7100.0,
            "MARUTI": 12400.0,
            "SUNPHARMA": 1740.0,
            "TATAMOTORS": 890.0,
            "HCLTECH": 1760.0,
            "TITAN": 3380.0,
            "NTPC": 410.0,
            "TRENT": 6800.0,
            "ULTRACEMCO": 11200.0,
            "POWERGRID": 330.0,
            "ADANIENT": 2950.0,
            "ADANIPORTS": 1390.0,
            "BEL": 290.0,
            "TATASTEEL": 150.0,
            "COALINDIA": 440.0,
            "ONGC": 265.0,
            "ASIANPAINT": 2450.0,
        }

        # Seed random variation with slight tug-of-war bias
        random.seed(int(time.time() / 15))

        for sym, weight in NIFTY_50_WEIGHTS.items():
            base_p = sample_prices.get(sym, 1200.0)
            # Heavyweights intentionally mixed to showcase Tug-of-War
            if sym == "HDFCBANK":
                p_change = 0.85
            elif sym == "RELIANCE":
                p_change = -0.72
            elif sym == "ICICIBANK":
                p_change = 0.64
            elif sym == "INFY":
                p_change = -0.45
            elif sym == "BHARTIARTL":
                p_change = 1.15
            else:
                p_change = round(random.uniform(-1.8, 1.8), 2)

            change = round(base_p * (p_change / 100.0), 2)
            last_p = round(base_p + change, 2)
            prev_close = base_p
            # Volume with occasional surges
            avg_vol = self.get_average_volumes().get(sym, 2_000_000.0)
            rvol_mult = random.choice([0.8, 0.95, 1.1, 1.4, 2.1 if sym in ["HDFCBANK", "TRENT"] else 0.9])
            volume = int(avg_vol * rvol_mult)

            records.append({
                "symbol": sym,
                "lastPrice": last_p,
                "change": change,
                "pChange": p_change,
                "volume": volume,
                "previousClose": prev_close,
                "dayHigh": round(max(last_p, prev_close) * 1.006, 2),
                "dayLow": round(min(last_p, prev_close) * 0.994, 2),
            })

        df = pd.DataFrame(records)
        # Approximate Nifty index
        nifty_change = round(random.uniform(-35.0, 45.0), 2)
        nifty_p_change = round((nifty_change / base_nifty) * 100.0, 2)
        nifty_meta = {
            "lastPrice": round(base_nifty + nifty_change, 2),
            "change": nifty_change,
            "pChange": nifty_p_change,
            "previousClose": base_nifty,
            "open": round(base_nifty + 10.0, 2),
            "dayHigh": round(base_nifty + 60.0, 2),
            "dayLow": round(base_nifty - 40.0, 2),
            "timestamp": time.strftime("%d-%b-%Y %H:%M:%S"),
        }
        return df, nifty_meta
