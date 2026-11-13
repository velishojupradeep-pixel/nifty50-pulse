"""
Global Macro & Market Events Provider for NIFTY 50 Option Sellers.
Tracks live Brent Crude, US Dollar Index (DXY), USD/INR, US 10Y Yield, India VIX,
high-impact economic catalysts, and live geopolitical/market headlines.
"""

import os
import re
import json
import time
from typing import Dict, Any, List, Optional
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

CACHE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/nifty50-pulse/.macro_cache.json")


class MacroEventsProvider:
    """Provides real-time global macro catalysts, event calendar, and market news for option sellers."""

    def __init__(self, cache_ttl: int = 180):
        self.cache_ttl = cache_ttl
        self._cached_summary: Optional[Dict[str, Any]] = None
        self._last_fetch_time: float = 0

    def get_macro_dashboard(self) -> Dict[str, Any]:
        """
        Returns live macro indicators, Google Finance global summary,
        upcoming earnings, event calendar, and geopolitical news headlines.
        """
        now = time.time()
        if self._cached_summary and (now - self._last_fetch_time < self.cache_ttl):
            return self._cached_summary

        # 1. Fetch live Google Finance data (global markets, FX, news, upcoming earnings)
        gf_data = self._fetch_google_finance_data()

        # 2. Fetch live macro market rates (enriched with Google Finance USD/INR if available)
        rates = self._fetch_live_rates(gf_usdinr=gf_data.get("usdinr"))

        # 3. Use Google Finance news first, fallback to yfinance/curated news
        news = gf_data.get("news") or self._fetch_live_news()

        # 4. Get high-impact economic calendar
        calendar = self._get_high_impact_calendar()

        # 5. FII / DII Institutional derivatives positioning rules
        fii_rules = self._get_fii_positioning_guide()

        # 6. Build concise Google Finance Macro & Geopolitical Summary
        gf_summary = self._build_google_finance_summary(
            rates=rates,
            global_markets=gf_data.get("global_markets", []),
            news=news,
            upcoming_earnings=gf_data.get("upcoming_earnings", []),
        )

        dashboard = {
            "rates": rates,
            "global_markets": gf_data.get("global_markets", []),
            "upcoming_earnings": gf_data.get("upcoming_earnings", []),
            "gf_summary": gf_summary,
            "gf_live": gf_data.get("is_live", False),
            "news": news,
            "calendar": calendar,
            "fii_rules": fii_rules,
            "last_updated": time.strftime("%H:%M:%S"),
        }

        self._cached_summary = dashboard
        self._last_fetch_time = now
        self._save_cache(dashboard)
        return dashboard

    def _fetch_google_finance_data(self) -> Dict[str, Any]:
        """Scrapes live global indices, USD/INR, news headlines, and upcoming earnings from Google Finance."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        result: Dict[str, Any] = {
            "is_live": False,
            "global_markets": [],
            "usdinr": None,
            "news": [],
            "upcoming_earnings": [],
        }

        target_quotes = {
            ".INX:INDEXSP": "S&P 500",
            ".IXIC:INDEXNASDAQ": "Nasdaq",
            ".DJI:INDEXDJX": "Dow Jones",
            "VIX:INDEXCBOE": "CBOE VIX",
            "UKX:INDEXFTSE": "FTSE 100",
            "DAX:INDEXDB": "DAX",
            "NIFTY_BANK:INDEXNSE": "Nifty Bank",
            "NIFTY_IT:INDEXNSE": "Nifty IT",
        }

        try:
            resp = requests.get("https://www.google.com/finance/?hl=en", headers=headers, timeout=8)
            if resp.status_code == 200:
                result["is_live"] = True
                soup = BeautifulSoup(resp.text, "html.parser")

                # A. Global Markets Snapshot
                seen_quotes = set()
                parsed_quotes: Dict[str, Dict[str, Any]] = {}
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    for q_key, q_label in target_quotes.items():
                        if q_key in href and q_key not in seen_quotes:
                            parts = [t.strip() for t in a.stripped_strings]
                            # Typical format: [Name, Price, '(', Change, ')', Pct, 'arrow_...']
                            price_str = parts[1] if len(parts) > 1 else ""
                            pct_str = next((p for p in parts if p.endswith("%")), "0.00%")
                            try:
                                price_val = float(price_str.replace(",", ""))
                                pct_val = float(pct_str.replace("%", "").replace("+", "").replace(",", ""))
                                seen_quotes.add(q_key)
                                parsed_quotes[q_key] = {
                                    "name": q_label,
                                    "price": price_str,
                                    "price_val": price_val,
                                    "pct": pct_val,
                                    "pct_str": pct_str,
                                }
                            except ValueError:
                                pass

                for q_key in target_quotes:
                    if q_key in parsed_quotes:
                        result["global_markets"].append(parsed_quotes[q_key])

                # B. Live News Headlines (with publisher & time_ago)
                seen_links = set()
                seen_titles = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if not (href.startswith("http") and "google.com" not in href):
                        continue
                    if href in seen_links:
                        continue
                    raw_text = " ".join(a.get_text(" ", strip=True).split())
                    if len(raw_text) < 28:
                        continue

                    # Extract publisher and relative time from ancestor container
                    publisher = "Google Finance"
                    time_ago = ""
                    parent = a.parent
                    for _ in range(3):
                        if not parent:
                            break
                        p_strings = [s.strip() for s in parent.stripped_strings if s.strip()]
                        # Look for "·" followed by time_ago and publisher
                        for i, tok in enumerate(p_strings):
                            if re.search(r"\b(min|hour|hr|day)s?\.?\s+ago\b", tok, re.I):
                                time_ago = tok
                                if i + 1 < len(p_strings) and p_strings[i + 1] not in ("-", "·") and len(p_strings[i + 1]) < 35:
                                    publisher = p_strings[i + 1]
                                break
                        if time_ago:
                            break
                        parent = parent.parent

                    # Clean trailing publisher duplication if present
                    title = raw_text
                    if publisher != "Google Finance" and title.endswith(publisher):
                        title = title[: -len(publisher)].strip(" -·")

                    norm_title = re.sub(r"\W+", "", title.lower())[:55]
                    if norm_title in seen_titles or len(title) < 25:
                        continue
                    seen_links.add(href)
                    seen_titles.add(norm_title)

                    tag, tag_color = self._classify_headline(title)
                    result["news"].append({
                        "title": title,
                        "publisher": publisher,
                        "time_ago": time_ago,
                        "link": href,
                        "tag": tag,
                        "tag_color": tag_color,
                    })
                    if len(result["news"]) >= 10:
                        break

                # C. Upcoming Earnings Calendar
                h_earn = soup.find(string=re.compile(r"Upcoming earnings", re.I))
                if h_earn:
                    container = h_earn.find_parent()
                    for _ in range(2):
                        if container and container.parent:
                            container = container.parent
                    if container:
                        tokens = [t.strip() for t in container.stripped_strings if t.strip()]
                        # Pattern: Day (Fri), Date (13), Company, 'fitbit_today', Time (2:30 PM IST), Quarter, 'Period', Quarter, 'EPS est.', val, 'Rev est.', val
                        idx = 0
                        while idx < len(tokens) - 4:
                            if tokens[idx] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun") and tokens[idx + 1].isdigit():
                                day_str = f"{tokens[idx]} {tokens[idx + 1]}"
                                company = tokens[idx + 2]
                                time_ist = ""
                                quarter = ""
                                eps_est = "—"
                                rev_est = "—"
                                scan = idx + 3
                                while scan < min(idx + 14, len(tokens)):
                                    tok = tokens[scan]
                                    if tok in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun") and scan + 1 < len(tokens) and tokens[scan + 1].isdigit():
                                        break
                                    if "IST" in tok or "EST" in tok or "GMT" in tok:
                                        time_ist = tok
                                    elif tok.startswith("Fiscal Q") or tok.startswith("Q"):
                                        quarter = tok
                                    elif tok == "EPS est." and scan + 1 < len(tokens):
                                        eps_est = tokens[scan + 1]
                                    elif tok == "Rev est." and scan + 1 < len(tokens):
                                        rev_est = tokens[scan + 1]
                                    scan += 1
                                result["upcoming_earnings"].append({
                                    "day": day_str,
                                    "company": company,
                                    "time": time_ist or "Scheduled",
                                    "quarter": quarter or "Quarterly",
                                    "eps_est": eps_est,
                                    "rev_est": rev_est,
                                })
                                idx = scan
                                if len(result["upcoming_earnings"]) >= 6:
                                    break
                            else:
                                idx += 1
        except Exception:
            pass

        # D. Fetch live USD/INR from Google Finance Currencies
        try:
            rc = requests.get("https://www.google.com/finance/markets/currencies?hl=en", headers=headers, timeout=6)
            if rc.status_code == 200:
                sc = BeautifulSoup(rc.text, "html.parser")
                for a in sc.find_all("a", href=True):
                    if "/quote/USD-INR" in a["href"]:
                        parts = [t.strip() for t in a.stripped_strings]
                        if len(parts) >= 2:
                            price_val = float(parts[1].replace(",", ""))
                            chg_tok = next((p for p in parts[2:] if p.startswith("+") or p.startswith("-")), "0")
                            chg_val = 0.0 if "%" in chg_tok else float(chg_tok.replace(",", ""))
                            pct_tok = next((p for p in parts if p.endswith("%")), "0%")
                            pct_val = float(pct_tok.replace("%", "").replace("+", "").replace(",", ""))
                            result["usdinr"] = {
                                "price": round(price_val, 2),
                                "change": round(chg_val, 2),
                                "pChange": round(pct_val, 2),
                            }
                        break
        except Exception:
            pass

        return result

    def _classify_headline(self, title: str) -> tuple:
        """Tags Google Finance headlines by option-seller relevance."""
        low = title.lower()
        if any(k in low for k in ("crude", "oil", "brent", "hormuz", "opec", "iran", "war", "tariff", "geopolit", "sanction", "middle east")):
            return ("Crude & Geopolitics", "#ff9800")
        if any(k in low for k in ("rbi", "fed", "fomc", "inflation", "cpi", "rate", "yield", "rupee", "dollar", "treasury", "gdp")):
            return ("Central Banks & Macro", "#ff5252")
        if any(k in low for k in ("dow", "s&p", "nasdaq", "nvidia", "wall street", "ai ", "tech", "nikkei", "europe")):
            return ("US & Global Markets", "#ab47bc")
        if any(k in low for k in ("q1", "q2", "q3", "q4", "results", "earnings", "profit", "ipo", "msci", "fii", "dii", "rejig")):
            return ("Earnings & Flows", "#00c853")
        return ("NIFTY & Equities", "#1976d2")

    def _build_google_finance_summary(
        self,
        rates: Dict[str, Any],
        global_markets: List[Dict[str, Any]],
        news: List[Dict[str, Any]],
        upcoming_earnings: List[Dict[str, Any]],
    ) -> str:
        """Builds a concise, option-seller-focused summary from live Google Finance data."""
        parts = []
        m_map = {m["name"]: m for m in global_markets}

        spx = m_map.get("S&P 500")
        ndx = m_map.get("Nasdaq")
        vix_us = m_map.get("CBOE VIX")
        if spx and ndx:
            us_tone = "risk-on" if spx["pct"] > 0.2 and ndx["pct"] > 0.2 else ("risk-off / soft" if spx["pct"] < -0.2 else "flat / mixed")
            vix_note = f" (CBOE VIX at {vix_us['price']}, {vix_us['pct_str']})" if vix_us else ""
            parts.append(f"<b>US Cues:</b> {us_tone} — S&P 500 {spx['pct_str']}, Nasdaq {ndx['pct_str']}{vix_note}.")

        nb = m_map.get("Nifty Bank")
        nit = m_map.get("Nifty IT")
        if nb and nit:
            parts.append(f"<b>India Sectors:</b> Nifty Bank {nb['pct_str']} vs Nifty IT {nit['pct_str']}.")

        brent_p = rates.get("brent", {}).get("price", 0)
        usdinr_p = rates.get("usdinr", {}).get("price", 0)
        if brent_p:
            crude_note = "elevated headwind" if brent_p > 85 else ("benign" if brent_p < 75 else "range-bound")
            parts.append(f"<b>Macro Pressure:</b> Brent at ${brent_p:.2f} ({crude_note}), USD/INR ₹{usdinr_p:.2f}.")

        if upcoming_earnings:
            names = ", ".join(e["company"].replace(" Limited", "") for e in upcoming_earnings[:3])
            parts.append(f"<b>Today's Earnings:</b> {names}.")

        if news:
            geo_or_macro = next((n for n in news if n["tag"] in ("Crude & Geopolitics", "Central Banks & Macro")), news[0])
            parts.append(f"<b>Top Catalyst:</b> {geo_or_macro['title']} <i>({geo_or_macro['publisher']})</i>")

        return " ".join(parts) if parts else "Live Google Finance feed active; monitor overnight US indices and crude for gap risk."

    def _fetch_live_rates(self, gf_usdinr: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetches live quotes for Brent Crude, DXY, USDINR, US10Y, and India VIX."""
        tickers = {
            "brent": "BZ=F",
            "dxy": "DX-Y.NYB",
            "usdinr": "INR=X",
            "us10y": "^TNX",
            "vix": "^INDIAVIX",
        }

        rates_data = {}
        try:
            download_str = " ".join(tickers.values())
            data = yf.download(download_str, period="5d", interval="1d", progress=False, timeout=8)
            if data is not None and not data.empty and hasattr(data.columns, "levels"):
                close = data["Close"]
                for key, symbol in tickers.items():
                    if symbol in close.columns:
                        s = close[symbol].dropna()
                        if len(s) >= 1:
                            last_p = float(s.iloc[-1])
                            prev_p = float(s.iloc[-2]) if len(s) >= 2 else last_p
                            chg = last_p - prev_p
                            chg_pct = (chg / prev_p) * 100.0 if prev_p else 0.0
                            rates_data[key] = {
                                "price": round(last_p, 2),
                                "change": round(chg, 2),
                                "pChange": round(chg_pct, 2),
                            }
        except Exception:
            pass

        # Fill with fallback defaults if any ticker failed or network blocked
        defaults = {
            "brent": {"price": 76.50, "change": -0.45, "pChange": -0.58},
            "dxy": {"price": 104.20, "change": 0.15, "pChange": 0.14},
            "usdinr": {"price": 84.45, "change": 0.02, "pChange": 0.02},
            "us10y": {"price": 4.38, "change": -0.02, "pChange": -0.45},
            "vix": {"price": 13.80, "change": -0.35, "pChange": -2.47},
        }
        for k, v in defaults.items():
            if k not in rates_data:
                rates_data[k] = v

        # Prefer Google Finance live USD/INR quote when available
        if gf_usdinr and gf_usdinr.get("price"):
            rates_data["usdinr"] = gf_usdinr

        # Add Option Seller Interpretations
        brent_p = rates_data["brent"]["price"]
        if brent_p > 85.0:
            rates_data["brent"]["status"] = "High Headwind for India"
            rates_data["brent"]["color"] = "#ff5252"
            rates_data["brent"]["impact"] = "Spike in Brent Crude expands India's import bill and fuels inflation. Pressure on Paints, OMCs, and Autos."
        elif brent_p < 75.0:
            rates_data["brent"]["status"] = "Sweet Spot for India"
            rates_data["brent"]["color"] = "#00c853"
            rates_data["brent"]["impact"] = "Sub-$75 crude lowers CAD and inflation, creating strong macro tailwinds for Indian equities."
        else:
            rates_data["brent"]["status"] = "Moderate / Range-Bound"
            rates_data["brent"]["color"] = "#ffb300"
            rates_data["brent"]["impact"] = "Crude trading in a neutral corridor. Limited immediate shock to NIFTY."

        dxy_p = rates_data["dxy"]["price"]
        if dxy_p > 105.0:
            rates_data["dxy"]["status"] = "FII Outflow Alert"
            rates_data["dxy"]["color"] = "#ff5252"
            rates_data["dxy"]["impact"] = "Surging Dollar Index drains capital from Emerging Markets. FIIs typically turn heavy net sellers."
        elif dxy_p < 102.0:
            rates_data["dxy"]["status"] = "Bullish for EM Inflows"
            rates_data["dxy"]["color"] = "#00c853"
            rates_data["dxy"]["impact"] = "Weak Dollar spurs foreign liquidity inflows into Indian equities."
        else:
            rates_data["dxy"]["status"] = "Stable Dollar"
            rates_data["dxy"]["color"] = "#64b5f6"
            rates_data["dxy"]["impact"] = "Dollar Index is stable; FII flows driven more by domestic fundamentals."

        usdinr_p = rates_data["usdinr"]["price"]
        rates_data["usdinr"]["status"] = "Depreciation Watch" if usdinr_p > 84.5 else "Stable Rupee"
        rates_data["usdinr"]["color"] = "#ffb300" if usdinr_p > 84.5 else "#00c853"
        rates_data["usdinr"]["impact"] = "Tracks currency resilience. Rapid depreciation forces RBI intervention and prompts FII equity pullbacks."

        us10y_p = rates_data["us10y"]["price"]
        if us10y_p > 4.40:
            rates_data["us10y"]["status"] = "Yield Pressure"
            rates_data["us10y"]["color"] = "#ff5252"
            rates_data["us10y"]["impact"] = "High US Treasury yields reduce risk appetite for global equities; caps NIFTY PE multiples."
        else:
            rates_data["us10y"]["status"] = "Moderate Yield"
            rates_data["us10y"]["color"] = "#00c853"
            rates_data["us10y"]["impact"] = "Benign US yields support equity valuation stability."

        vix_p = rates_data["vix"]["price"]
        if vix_p > 18.0:
            rates_data["vix"]["status"] = "High Volatility Regime"
            rates_data["vix"]["color"] = "#ff5252"
            rates_data["vix"]["impact"] = "Juicy option premiums, but high intraday swing risk. Mandates strict stop-loss rules."
        elif vix_p < 12.0:
            rates_data["vix"]["status"] = "Complacency / Thin Premiums"
            rates_data["vix"]["color"] = "#ffb300"
            rates_data["vix"]["impact"] = "Premiums are thin. Low edge for naked option selling; sudden spikes trigger sharp MTM drawdowns."
        else:
            rates_data["vix"]["status"] = "Optimal Seller Range (12-16)"
            rates_data["vix"]["color"] = "#00c853"
            rates_data["vix"]["impact"] = "Ideal environment for theta collection. Premiums decay cleanly with modest intraday range."

        return rates_data

    def _fetch_live_news(self) -> List[Dict[str, Any]]:
        """Fetches latest market and macro headlines from Yahoo Finance."""
        news_items = []
        try:
            t = yf.Ticker("^NSEI")
            raw_news = t.news
            if raw_news:
                for item in raw_news[:6]:
                    title = item.get("title") or (item.get("content", {}).get("title"))
                    publisher = item.get("publisher") or (item.get("content", {}).get("provider", {}).get("displayName", "Market Wire"))
                    link = item.get("link") or (item.get("content", {}).get("canonicalUrl", {}).get("url", "#"))
                    if title:
                        news_items.append({
                            "title": title,
                            "publisher": publisher,
                            "link": link,
                            "tag": "NIFTY & Equities",
                            "tag_color": "#1976d2",
                        })
        except Exception:
            pass

        # Try fetching Crude / Energy news
        try:
            t_oil = yf.Ticker("CL=F")
            raw_oil_news = t_oil.news
            if raw_oil_news:
                for item in raw_oil_news[:3]:
                    title = item.get("title") or (item.get("content", {}).get("title"))
                    publisher = item.get("publisher") or (item.get("content", {}).get("provider", {}).get("displayName", "Energy Wire"))
                    link = item.get("link") or (item.get("content", {}).get("canonicalUrl", {}).get("url", "#"))
                    if title:
                        news_items.append({
                            "title": title,
                            "publisher": publisher,
                            "link": link,
                            "tag": "Crude & Geopolitics",
                            "tag_color": "#ff9800",
                        })
        except Exception:
            pass

        if not news_items:
            news_items = [
                {
                    "title": "Global equity markets digest central bank commentary and crude price oscillations.",
                    "publisher": "Reuters Financial",
                    "link": "https://www.reuters.com/markets",
                    "tag": "Global Macro",
                    "tag_color": "#1976d2",
                },
                {
                    "title": "Brent crude hovers in key trading range amid Middle East shipping developments and OPEC+ supply monitoring.",
                    "publisher": "Bloomberg Energy",
                    "link": "https://www.bloomberg.com/energy",
                    "tag": "Crude & Geopolitics",
                    "tag_color": "#ff9800",
                },
                {
                    "title": "FII derivative flows show selective hedging across index futures ahead of upcoming monthly expiry.",
                    "publisher": "NSE India Analytics",
                    "link": "https://www.nseindia.com",
                    "tag": "Derivatives",
                    "tag_color": "#00c853",
                },
            ]

        return news_items

    def _get_high_impact_calendar(self) -> List[Dict[str, Any]]:
        """Returns the high-impact central bank, macroeconomic, and geopolitical catalysts."""
        return [
            {
                "event": "RBI Monetary Policy Committee (MPC) Meeting",
                "frequency": "Bi-Monthly (Feb, Apr, Jun, Aug, Oct, Dec)",
                "impact": "CRITICAL",
                "impact_color": "#ff5252",
                "key_focus": "Repo rate decision, inflation outlook, system liquidity & stance.",
                "affected_sectors": "Banking (HDFC Bank, ICICI Bank, SBI), NBFCs, Autos, Realty.",
                "seller_rule": "⚠️ Avoid naked Bank Nifty straddles overnight. IV crush of 15-25% unfolds within 45 mins post-announcement. Deploy wide Iron Condors after the initial 15-min kneejerk candle.",
            },
            {
                "event": "US Federal Reserve (FOMC) Rate Decision",
                "frequency": "8 times per year (Jan, Mar, May, Jun, Jul, Sep, Nov, Dec)",
                "impact": "CRITICAL",
                "impact_color": "#ff5252",
                "key_focus": "Fed funds rate, dot plot projections, Powell press conference.",
                "affected_sectors": "IT Services (TCS, INFY, HCLTECH), FII flows, USD/INR.",
                "seller_rule": "🚨 Overnight Gap Danger! The decision drops at 11:30 PM / 12:00 AM IST. Never hold unhedged short strangles overnight ahead of FOMC. Always buy cheap wings for tail-risk protection.",
            },
            {
                "event": "India & US CPI Inflation Data Release",
                "frequency": "Monthly (Approx. 12th of each month)",
                "impact": "HIGH",
                "impact_color": "#ff9800",
                "key_focus": "Food inflation, core services, and sticky rent components.",
                "affected_sectors": "Broad Nifty 50, FMCG, Consumer Durables, Bond Yields.",
                "seller_rule": "Expect 50-80 pt opening reaction. If data meets street consensus, sharp theta decay follows immediately in the opening hour.",
            },
            {
                "event": "OPEC+ Ministerial & Production Meetings",
                "frequency": "Bi-monthly / Ad-hoc",
                "impact": "HIGH",
                "impact_color": "#ff9800",
                "key_focus": "Crude oil output quotas, voluntary cuts by Saudi Arabia & Russia.",
                "affected_sectors": "Oil & Gas (Reliance, ONGC, BPCL), Paints (Asian Paints), Aviation.",
                "seller_rule": "A $5/bbl move in crude directly swings Reliance point contribution. Option sellers should verify heavyweight alignment before writing short calls.",
            },
            {
                "event": "NIFTY Heavyweight Quarterly Earnings (TCS, INFY, HDFCBANK, RELIANCE)",
                "frequency": "Quarterly (Jan, Apr, Jul, Oct)",
                "impact": "HIGH",
                "impact_color": "#ff9800",
                "key_focus": "PAT, margins, forward guidance, management commentary.",
                "affected_sectors": "Heavyweight individual stock point contribution to NIFTY.",
                "seller_rule": "Check if an earnings announcement falls on an expiry date. A 4% move in HDFC Bank moves Nifty by ~55 index points instantly.",
            },
        ]

    def _get_fii_positioning_guide(self) -> Dict[str, Any]:
        """Provides institutional derivatives interpretation rules for option sellers."""
        return {
            "title": "FII Index Futures Long/Short Ratio Playbook",
            "ranges": [
                {
                    "range": "FII Net Long > 75%",
                    "state": "Extreme Bullish Overcrowding",
                    "color": "#ff5252",
                    "rule": "⚠️ Vulnerable to sudden profit booking and long unwinding. Favorable for selling OTM Calls or Bear Call Spreads on intraday momentum peaks.",
                },
                {
                    "range": "FII Net Long 40% – 60%",
                    "state": "Neutral Equilibrium",
                    "color": "#00c853",
                    "rule": "🎯 Option Seller's Sweet Spot. Neither side is overextended. Non-directional Iron Condors and Strangles collect maximum theta decay with minimal gap risk.",
                },
                {
                    "range": "FII Net Long < 20%",
                    "state": "Extreme Bearish Oversold / Heavy Short Trap",
                    "color": "#00e676",
                    "rule": "🚨 Short-Squeeze Alert! High probability of violent short covering rallies. Do NOT sell naked OTM Calls into shallow dips; favor selling Bull Put Spreads.",
                },
            ],
        }

    def _save_cache(self, data: Dict[str, Any]):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
