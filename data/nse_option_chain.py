"""
Direct NSE India Live Option Chain Provider.
Fetches official expiry dates, live strike premiums (CE & PE LTP), Implied Volatility,
Open Interest (OI), PCR, and Max Pain directly from https://www.nseindia.com/option-chain.
"""

import time
from typing import Dict, Any, List, Optional
from curl_cffi import requests


class NSEOptionChainProvider:
    """Connects to NSE India official v3 Option Chain API with session impersonation."""

    BASE_URL = "https://www.nseindia.com/option-chain"
    CONTRACT_INFO_URL = "https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY"
    CHAIN_API_URL = "https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY"

    def __init__(self, cache_ttl: int = 20):
        self.cache_ttl = cache_ttl
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            "Referer": self.BASE_URL,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_fetch_time = 0
        self.cached_contract_info: Dict[str, Any] = {}
        self.cached_chain_data: Dict[str, Any] = {}

    def _ensure_session(self):
        """Initializes cookies from option-chain page if expired."""
        now = time.time()
        if now - self.last_fetch_time > 300 or not self.session.cookies:
            try:
                self.session.get(self.BASE_URL, timeout=8)
                self.last_fetch_time = now
            except Exception:
                pass

    def get_official_expiries(self) -> List[str]:
        """Fetches the official list of live expiry dates directly from NSE India."""
        now = time.time()
        if self.cached_contract_info and (now - self.cached_contract_info.get("timestamp", 0) < 120):
            return self.cached_contract_info.get("expiries", [])

        self._ensure_session()
        try:
            resp = self.session.get(self.CONTRACT_INFO_URL, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                expiries = data.get("expiryDates", [])
                if expiries:
                    self.cached_contract_info = {"timestamp": now, "expiries": expiries}
                    return expiries
        except Exception:
            pass

        # Fallback to cached or empty
        return self.cached_contract_info.get("expiries", [])

    def fetch_live_option_chain(self, expiry: str) -> Dict[str, Any]:
        """
        Fetches live option chain for a specific official NSE expiry date.
        Returns:
            - underlyingValue: Current spot price
            - timestamp: NSE live timestamp
            - strikes: Dict mapping strikePrice -> {'CE': {...}, 'PE': {...}}
            - atm_straddle: Real combined ATM premium
            - pcr: Put-Call Ratio
            - max_pain: Max Pain strike
        """
        cache_key = f"chain_{expiry}"
        now = time.time()
        if cache_key in self.cached_chain_data:
            cached = self.cached_chain_data[cache_key]
            if now - cached.get("_cached_at", 0) < self.cache_ttl:
                return cached

        self._ensure_session()
        url = f"{self.CHAIN_API_URL}&expiry={expiry}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get("records", {})
                underlying = float(records.get("underlyingValue", 0.0))
                timestamp = records.get("timestamp", "")
                raw_strikes = records.get("data", [])

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

                result = {
                    "_cached_at": now,
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
                self.cached_chain_data[cache_key] = result
                return result

        except Exception as e:
            pass

        return {}

    def _calculate_max_pain(self, strikes_map: Dict[int, Dict[str, Any]]) -> int:
        """Finds strike where total option buyer loss is maximized (Option Seller Max Pain)."""
        if not strikes_map:
            return 24500

        all_strikes = sorted(strikes_map.keys())
        min_loss = float("inf")
        max_pain_strike = all_strikes[len(all_strikes) // 2]

        # Evaluate loss across reasonable range (±1000 pts around midpoint)
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
