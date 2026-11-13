"""
Direct NSE India Live Option Chain Provider.
Fetches official expiry dates, live strike premiums (CE & PE LTP), Implied Volatility,
Open Interest (OI), PCR, and Max Pain directly from https://www.nseindia.com/option-chain.
Includes resilient disk persistence so real market prices are NEVER replaced by synthetic estimates.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from curl_cffi import requests

CACHE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/nifty50-pulse/.nse_chain_cache.json")


class NSEOptionChainProvider:
    """Connects to NSE India official v3 Option Chain API with session impersonation."""

    BASE_URL = "https://www.nseindia.com/option-chain"
    CONTRACT_INFO_URL = "https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY"
    CHAIN_API_URL = "https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY"

    def __init__(self, cache_ttl: int = 15):
        self.cache_ttl = cache_ttl
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            "Referer": self.BASE_URL,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_session_time = 0
        self.disk_cache = self._load_disk_cache()

    def _load_disk_cache(self) -> Dict[str, Any]:
        """Loads cached NSE option chain snapshot from disk or bundled seed."""
        # 1. Try runtime cache
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    if data:
                        return data
        except Exception:
            pass

        # 2. Try bundled repository seed (vital for Streamlit Cloud / AWS datacenter instances)
        seed_path = os.path.join(os.path.dirname(__file__), "nse_chain_seed.json")
        try:
            if os.path.exists(seed_path):
                with open(seed_path, "r") as f:
                    data = json.load(f)
                    if data:
                        return data
        except Exception:
            pass

        return {}

    def _save_disk_cache(self):
        """Saves current option chain data to disk for instant recovery."""
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.disk_cache, f)
        except Exception:
            pass

    def _ensure_session(self):
        """Initializes cookies from option-chain page if expired."""
        now = time.time()
        if now - self.last_session_time > 180 or not self.session.cookies:
            try:
                self.session.get(self.BASE_URL, timeout=8)
                self.last_session_time = now
            except Exception:
                pass

    @staticmethod
    def filter_active_expiries(expiries: List[str]) -> List[str]:
        """Filters out any expiry dates in the past based on today's calendar date."""
        today = datetime.now().date()
        valid = []
        for exp in expiries:
            try:
                exp_clean = exp.strip()
                dt = datetime.strptime(exp_clean, "%d-%b-%Y").date()
                if dt >= today:
                    valid.append(exp_clean)
            except Exception:
                pass
        return valid

    @staticmethod
    def generate_fallback_expiries() -> List[str]:
        """Dynamically computes the next 4 upcoming Tuesday expiries if network fails."""
        today = datetime.now().date()
        days_ahead = (1 - today.weekday()) % 7
        if days_ahead == 0 and datetime.now().hour >= 16:
            days_ahead = 7
        next_tuesday = today + timedelta(days=days_ahead)
        return [(next_tuesday + timedelta(weeks=i)).strftime("%d-%b-%Y") for i in range(4)]

    def get_official_expiries(self) -> List[str]:
        """Fetches the official list of live expiry dates directly from NSE India."""
        self._ensure_session()
        try:
            resp = self.session.get(self.CONTRACT_INFO_URL, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                raw_expiries = data.get("expiryDates", [])
                active_expiries = self.filter_active_expiries(raw_expiries)
                if active_expiries:
                    self.disk_cache["expiries"] = active_expiries
                    self._save_disk_cache()
                    return active_expiries
        except Exception:
            pass

        # Return disk cached official expiries strictly filtered for active non-expired dates
        cached = self.filter_active_expiries(self.disk_cache.get("expiries", []))
        if cached:
            return cached

        # Dynamic calendar fallback
        return self.generate_fallback_expiries()

    def fetch_live_option_chain(self, expiry: str) -> Dict[str, Any]:
        """
        Fetches live option chain for a specific official NSE expiry date.
        Returns authentic live premiums (LTP) directly from nseindia.com/option-chain.
        """
        self._ensure_session()
        url = f"{self.CHAIN_API_URL}&expiry={expiry}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get("records", {})
                underlying = float(records.get("underlyingValue", 0.0))
                timestamp = records.get("timestamp", time.strftime("%d-%b-%Y %H:%M:%S"))
                raw_strikes = records.get("data", [])

                if raw_strikes:
                    strikes_map = {}
                    total_ce_oi = 0
                    total_pe_oi = 0

                    for item in raw_strikes:
                        strike = int(item.get("strikePrice", 0))
                        ce = item.get("CE", {})
                        pe = item.get("PE", {})

                        ce_price = float(ce.get("lastPrice", 0.0))
                        pe_price = float(pe.get("lastPrice", 0.0))
                        ce_iv = float(ce.get("impliedVolatility", 0.0))
                        pe_iv = float(pe.get("impliedVolatility", 0.0))
                        ce_oi = int(ce.get("openInterest", 0))
                        pe_oi = int(pe.get("openInterest", 0))

                        total_ce_oi += ce_oi
                        total_pe_oi += pe_oi

                        strikes_map[strike] = {
                            "strike": strike,
                            "ce_ltp": ce_price,
                            "ce_iv": ce_iv,
                            "ce_oi": ce_oi,
                            "ce_change": float(ce.get("change", 0.0)),
                            "pe_ltp": pe_price,
                            "pe_iv": pe_iv,
                            "pe_oi": pe_oi,
                            "pe_change": float(pe.get("change", 0.0)),
                        }

                    # Put-Call Ratio
                    pcr = round(total_pe_oi / max(total_ce_oi, 1), 2)

                    # ATM Strike & Straddle Price
                    atm_strike = int(round(underlying / 50.0) * 50)
                    atm_data = strikes_map.get(atm_strike, {})
                    atm_straddle = round(
                        atm_data.get("ce_ltp", 0.0) + atm_data.get("pe_ltp", 0.0), 2
                    )

                    # Calculate Max Pain
                    max_pain = self._calculate_max_pain(strikes_map)

                    # Convert int keys to str for JSON serialization
                    serializable_strikes = {str(k): v for k, v in strikes_map.items()}

                    result = {
                        "is_live_nse": True,
                        "expiry": expiry,
                        "timestamp": timestamp,
                        "underlying": underlying,
                        "atm_strike": atm_strike,
                        "atm_straddle": atm_straddle,
                        "pcr": pcr,
                        "max_pain": max_pain,
                        "strikes_map": strikes_map,
                        "total_ce_oi": total_ce_oi,
                        "total_pe_oi": total_pe_oi,
                    }

                    # Cache to disk
                    self.disk_cache[f"chain_{expiry}"] = {
                        **result,
                        "strikes_map": serializable_strikes,
                    }
                    self._save_disk_cache()
                    return result

        except Exception:
            pass

        # If live fetch timed out or blocked by cloud hosting IP, return last saved authentic NSE snapshot or seed
        cached_chain = self.disk_cache.get(f"chain_{expiry}")
        if not cached_chain:
            # Check any available non-expired chain in cache/seed
            active_list = self.get_official_expiries()
            for k, v in self.disk_cache.items():
                if k.startswith("chain_") and isinstance(v, dict) and "strikes_map" in v:
                    c_exp = v.get("expiry", "")
                    if c_exp in active_list:
                        cached_chain = v
                        break

        if cached_chain:
            # Restore integer keys and mark explicitly as cached fallback (not live-fetched)
            s_map = {int(k): v for k, v in cached_chain.get("strikes_map", {}).items()}
            return {
                **cached_chain,
                "is_live_nse": False,
                "strikes_map": s_map,
            }

        return {}

    def _calculate_max_pain(self, strikes_map: Dict[int, Dict[str, Any]]) -> int:
        """Finds strike where total option buyer loss is maximized (Option Seller Max Pain)."""
        if not strikes_map:
            return 24600

        all_strikes = sorted(strikes_map.keys())
        min_loss = float("inf")
        max_pain_strike = all_strikes[len(all_strikes) // 2]

        mid = all_strikes[len(all_strikes) // 2]
        eval_strikes = [s for s in all_strikes if abs(s - mid) <= 1500]

        for spot_candidate in eval_strikes:
            total_loss = 0
            for strike, data in strikes_map.items():
                if abs(strike - spot_candidate) > 2000:
                    continue
                ce_loss = max(0, spot_candidate - strike) * data["ce_oi"]
                pe_loss = max(0, strike - spot_candidate) * data["pe_oi"]
                total_loss += ce_loss + pe_loss

            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = spot_candidate

        return max_pain_strike
