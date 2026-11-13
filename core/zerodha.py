"""
Zerodha Kite Connect & Kite Web CSV Sync Helper for NIFTY 50 Option Seller Radar.
Fetches live NFO NIFTY option positions via Kite Connect REST API v3 (or parses
Kite Web CSV export) and normalizes them into Active Positions format.
"""

import re
import csv
import io
import hashlib
from typing import Dict, Any, List, Optional, Tuple
import requests

from core.positions import NIFTY_LOT_SIZE

KITE_API_BASE = "https://api.kite.trade"

MONTH_MAP = {
    "1": "Jan", "2": "Feb", "3": "Mar", "4": "Apr", "5": "May", "6": "Jun",
    "7": "Jul", "8": "Aug", "9": "Sep", "O": "Oct", "N": "Nov", "D": "Dec",
    "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr", "MAY": "May", "JUN": "Jun",
    "JUL": "Jul", "AUG": "Aug", "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DEC": "Dec",
}


def parse_kite_tradingsymbol(
    symbol: str, official_expiries: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Parses Zerodha NIFTY option tradingsymbols such as:
      - Monthly: NIFTY26NOV25350CE -> strike=25350, type=CE, expiry matching Nov-2026
      - Weekly:  NIFTY26N1725350CE -> strike=25350, type=CE, expiry matching 17-Nov-2026
    """
    sym = str(symbol or "").strip().upper()
    if not sym.startswith("NIFTY") or sym.startswith("NIFTYNXT") or sym.startswith("NIFTYIT"):
        return None
    if not (sym.endswith("CE") or sym.endswith("PE")):
        return None

    opt_type = sym[-2:]
    body = sym[5:-2]  # Strip 'NIFTY' and 'CE'/'PE'
    expiries = official_expiries or []

    # 1. Monthly format: YYMMMSTRIKE (e.g. 26NOV25350)
    m_mon = re.match(r"^(\d{2})([A-Z]{3})(\d+)$", body)
    if m_mon:
        yy, mon_str, strike_str = m_mon.groups()
        mon = MONTH_MAP.get(mon_str, mon_str.title())
        year = f"20{yy}"
        matched_exp = next(
            (e for e in reversed(expiries) if f"-{mon}-{year}" in e),
            expiries[0] if expiries else f"{mon}-{year}",
        )
        return {"strike": int(strike_str), "type": opt_type, "expiry": matched_exp}

    # 2. Weekly format: YYMDSTRIKE where M is 1-9/O/N/D and DD is 2 digits (e.g. 26N1725350)
    m_wk = re.match(r"^(\d{2})([1-9OND])(\d{2})(\d+)$", body)
    if m_wk:
        yy, m_code, dd, strike_str = m_wk.groups()
        mon = MONTH_MAP.get(m_code, "Nov")
        year = f"20{yy}"
        target = f"{dd}-{mon}-{year}"
        matched_exp = next(
            (e for e in expiries if e == target),
            expiries[0] if expiries else target,
        )
        return {"strike": int(strike_str), "type": opt_type, "expiry": matched_exp}

    # 3. Fallback: extract trailing 5-digit strike
    m_fb = re.search(r"(\d{4,5})$", body)
    if m_fb:
        return {
            "strike": int(m_fb.group(1)),
            "type": opt_type,
            "expiry": expiries[0] if expiries else "",
        }
    return None


def exchange_request_token(
    api_key: str, api_secret: str, request_token: str
) -> Tuple[bool, str, Optional[str]]:
    """Exchanges Kite Connect request_token for an access_token."""
    api_key = api_key.strip()
    api_secret = api_secret.strip()
    request_token = request_token.strip()
    if not (api_key and api_secret and request_token):
        return False, "API Key, API Secret, and Request Token are all required.", None

    checksum = hashlib.sha256(
        f"{api_key}{request_token}{api_secret}".encode("utf-8")
    ).hexdigest()
    try:
        resp = requests.post(
            f"{KITE_API_BASE}/session/token",
            headers={"X-Kite-Version": "3"},
            data={
                "api_key": api_key,
                "request_token": request_token,
                "checksum": checksum,
            },
            timeout=10,
        )
        payload = resp.json() if resp.content else {}
        if resp.status_code == 200 and payload.get("status") == "success":
            token = payload.get("data", {}).get("access_token")
            if token:
                return True, "Kite access token generated!", token
        return False, str(payload.get("message") or "Failed to exchange request token."), None
    except Exception as exc:
        return False, f"Kite connection error: {exc}", None


def fetch_kite_positions(
    api_key: str,
    access_token: str,
    official_expiries: Optional[List[str]] = None,
    include_closed_today: bool = True,
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """Fetches NIFTY option positions from Zerodha Kite Connect /portfolio/positions."""
    api_key = api_key.strip()
    access_token = access_token.strip()
    if not (api_key and access_token):
        return False, "Please provide both Zerodha API Key and Access Token.", []

    try:
        resp = requests.get(
            f"{KITE_API_BASE}/portfolio/positions",
            headers={
                "X-Kite-Version": "3",
                "Authorization": f"token {api_key}:{access_token}",
            },
            timeout=10,
        )
        payload = resp.json() if resp.content else {}
        if resp.status_code != 200 or payload.get("status") != "success":
            err = payload.get("message") or f"HTTP {resp.status_code} from Kite API."
            return False, str(err), []

        net_list = payload.get("data", {}).get("net", [])
        parsed_legs: List[Dict[str, Any]] = []

        for p in net_list:
            if p.get("exchange") not in ("NFO", "NSE"):
                continue
            parsed = parse_kite_tradingsymbol(p.get("tradingsymbol", ""), official_expiries)
            if not parsed:
                continue

            qty = int(p.get("quantity", 0) or 0)
            buy_qty = int(p.get("buy_quantity", 0) or 0)
            sell_qty = int(p.get("sell_quantity", 0) or 0)
            buy_price = float(p.get("buy_price", 0.0) or 0.0)
            sell_price = float(p.get("sell_price", 0.0) or 0.0)
            avg_price = float(p.get("average_price", 0.0) or 0.0)

            if qty != 0:
                side = "SELL" if qty < 0 else "BUY"
                lots = max(1, round(abs(qty) / NIFTY_LOT_SIZE))
                entry_p = (
                    (sell_price if sell_price > 0 else avg_price)
                    if side == "SELL"
                    else (buy_price if buy_price > 0 else avg_price)
                )
                parsed_legs.append({
                    "side": side,
                    "type": parsed["type"],
                    "strike": parsed["strike"],
                    "expiry": parsed["expiry"],
                    "lots": lots,
                    "entry_price": round(entry_p, 2),
                    "exit_price": 0.0,
                })
            elif include_closed_today and buy_qty > 0 and sell_qty > 0:
                lots = max(1, round(min(buy_qty, sell_qty) / NIFTY_LOT_SIZE))
                parsed_legs.append({
                    "side": "SELL",
                    "type": parsed["type"],
                    "strike": parsed["strike"],
                    "expiry": parsed["expiry"],
                    "lots": lots,
                    "entry_price": round(sell_price, 2),
                    "exit_price": round(buy_price, 2),
                })

        if not parsed_legs:
            return True, "Connected to Zerodha, but no NIFTY option positions were found.", []
        return True, f"Fetched {len(parsed_legs)} NIFTY option leg(s) from Zerodha Kite.", parsed_legs
    except Exception as exc:
        return False, f"Error connecting to Zerodha Kite: {exc}", []


def parse_kite_csv(
    csv_text: str, official_expiries: Optional[List[str]] = None
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Parses CSV exported from Kite Web (kite.zerodha.com/positions).
    Expected columns typically include: Instrument, Qty., Avg., LTP, P&L.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            return False, "Empty or invalid CSV file.", []

        legs: List[Dict[str, Any]] = []
        for row in reader:
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            inst = norm.get("instrument") or norm.get("tradingsymbol") or norm.get("symbol") or ""
            parsed = parse_kite_tradingsymbol(inst, official_expiries)
            if not parsed:
                continue

            qty_raw = norm.get("qty.") or norm.get("qty") or norm.get("quantity") or "0"
            avg_raw = norm.get("avg.") or norm.get("avg") or norm.get("average_price") or "0"
            try:
                qty = int(float(qty_raw.replace(",", "")))
                avg_p = abs(float(avg_raw.replace(",", "").replace("₹", "")))
            except ValueError:
                continue

            if qty == 0:
                continue
            side = "SELL" if qty < 0 else "BUY"
            lots = max(1, round(abs(qty) / NIFTY_LOT_SIZE))
            legs.append({
                "side": side,
                "type": parsed["type"],
                "strike": parsed["strike"],
                "expiry": parsed["expiry"],
                "lots": lots,
                "entry_price": round(avg_p, 2),
                "exit_price": 0.0,
            })

        if not legs:
            return False, "No open NIFTY option legs found in the uploaded CSV.", []
        return True, f"Parsed {len(legs)} NIFTY option leg(s) from Kite CSV.", legs
    except Exception as exc:
        return False, f"Failed to parse Kite CSV: {exc}", []
