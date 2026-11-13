"""
Active Positions & Live Risk/Profit Adjustment Advisor for NIFTY 50 Option Sellers.
Persists user-entered positions, marks them to market against live NSE option chains,
computes portfolio Greeks/payoff/breakevens, and generates strike-specific strategies
to minimize tail risk and maximize theta profit.
"""

import os
import json
import math
import uuid
from typing import Dict, Any, List, Optional, Tuple
import requests

from core.auth import get_supabase_credentials

POSITIONS_FILE = os.path.expanduser(
    "~/.gemini/antigravity/scratch/nifty50-pulse/.active_positions.json"
)
NIFTY_LOT_SIZE = 65


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def estimate_option_delta(
    spot: float, strike: float, opt_type: str, iv_pct: float = 15.0, dte_days: int = 4
) -> float:
    """Estimates Black-Scholes option delta for a single NIFTY option contract."""
    if spot <= 0 or strike <= 0:
        return 0.5 if opt_type == "CE" else -0.5
    t = max(dte_days, 0.5) / 365.0
    sigma = max(iv_pct, 8.0) / 100.0
    r = 0.065
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (
            sigma * math.sqrt(t)
        )
        call_delta = _norm_cdf(d1)
        return round(call_delta if opt_type == "CE" else call_delta - 1.0, 2)
    except Exception:
        return 0.5 if opt_type == "CE" else -0.5


class PositionManager:
    """Manages active user positions (Supabase cloud per-user or local fallback) and generates live risk/profit strategies."""

    def _sb_headers(self, access_token: str) -> Dict[str, str]:
        _, anon_key = get_supabase_credentials()
        return {
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _use_supabase(self, user_id: Optional[str], access_token: Optional[str]) -> bool:
        url, key = get_supabase_credentials()
        return bool(url and key and user_id and access_token)

    def load_positions(
        self, user_id: Optional[str] = None, access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self._use_supabase(user_id, access_token):
            url, _ = get_supabase_credentials()
            try:
                resp = requests.get(
                    f"{url}/rest/v1/positions",
                    headers=self._sb_headers(access_token),
                    params={"user_id": f"eq.{user_id}", "order": "created_at.asc"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    rows = resp.json()
                    return [
                        {
                            "id": str(r["id"]),
                            "side": r["side"],
                            "type": r["type"],
                            "strike": int(r["strike"]),
                            "expiry": r["expiry"],
                            "lots": int(r["lots"]),
                            "qty": int(r["lots"]) * NIFTY_LOT_SIZE,
                            "entry_price": float(r["entry_price"]),
                            "exit_price": float(r.get("exit_price", 0.0) or 0.0),
                        }
                        for r in rows
                    ]
            except Exception:
                pass
            return []

        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def save_positions(self, positions: List[Dict[str, Any]]) -> None:
        try:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(positions, f, indent=2)
        except Exception:
            pass

    def add_position(
        self,
        positions: List[Dict[str, Any]],
        side: str,
        opt_type: str,
        strike: int,
        expiry: str,
        lots: int,
        entry_price: float,
        exit_price: float = 0.0,
        user_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        new_leg = {
            "id": str(uuid.uuid4())[:8],
            "side": side.upper(),
            "type": opt_type.upper(),
            "strike": int(strike),
            "expiry": expiry,
            "lots": int(lots),
            "qty": int(lots) * NIFTY_LOT_SIZE,
            "entry_price": round(float(entry_price), 2),
            "exit_price": round(float(exit_price), 2),
        }
        if self._use_supabase(user_id, access_token):
            url, _ = get_supabase_credentials()
            try:
                payload = {**new_leg, "user_id": user_id}
                resp = requests.post(
                    f"{url}/rest/v1/positions",
                    headers=self._sb_headers(access_token),
                    json=payload,
                    timeout=8,
                )
                if resp.status_code in (200, 201):
                    return list(positions) + [new_leg]
            except Exception:
                pass
            return list(positions)

        updated = list(positions) + [new_leg]
        self.save_positions(updated)
        return updated

    def update_position(
        self,
        positions: List[Dict[str, Any]],
        leg_id: str,
        side: str,
        opt_type: str,
        strike: int,
        expiry: str,
        lots: int,
        entry_price: float,
        exit_price: float = 0.0,
        user_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        fields = {
            "side": side.upper(),
            "type": opt_type.upper(),
            "strike": int(strike),
            "expiry": expiry,
            "lots": int(lots),
            "qty": int(lots) * NIFTY_LOT_SIZE,
            "entry_price": round(float(entry_price), 2),
            "exit_price": round(float(exit_price), 2),
        }
        if self._use_supabase(user_id, access_token):
            url, _ = get_supabase_credentials()
            try:
                requests.patch(
                    f"{url}/rest/v1/positions",
                    headers=self._sb_headers(access_token),
                    params={"id": f"eq.{leg_id}", "user_id": f"eq.{user_id}"},
                    json=fields,
                    timeout=8,
                )
            except Exception:
                pass

        updated = []
        for p in positions:
            if p.get("id") == leg_id:
                updated.append({"id": leg_id, **fields})
            else:
                updated.append(p)
        if not self._use_supabase(user_id, access_token):
            self.save_positions(updated)
        return updated

    def remove_position(
        self,
        positions: List[Dict[str, Any]],
        leg_id: str,
        user_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._use_supabase(user_id, access_token):
            url, _ = get_supabase_credentials()
            try:
                requests.delete(
                    f"{url}/rest/v1/positions",
                    headers=self._sb_headers(access_token),
                    params={"id": f"eq.{leg_id}", "user_id": f"eq.{user_id}"},
                    timeout=8,
                )
            except Exception:
                pass
            return [p for p in positions if p.get("id") != leg_id]

        updated = [p for p in positions if p.get("id") != leg_id]
        self.save_positions(updated)
        return updated

    def clear_positions(
        self, user_id: Optional[str] = None, access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self._use_supabase(user_id, access_token):
            url, _ = get_supabase_credentials()
            try:
                requests.delete(
                    f"{url}/rest/v1/positions",
                    headers=self._sb_headers(access_token),
                    params={"user_id": f"eq.{user_id}"},
                    timeout=8,
                )
            except Exception:
                pass
            return []

        self.save_positions([])
        return []

    def evaluate_portfolio(
        self,
        positions: List[Dict[str, Any]],
        spot: float,
        curr_chain: Dict[str, Any],
        next_chain: Dict[str, Any],
        tech_data: Dict[str, Any],
        dte_curr: int = 4,
    ) -> Dict[str, Any]:
        """
        Marks all positions to live NSE option chain prices and generates
        actionable risk-minimization and profit-maximization strategies.
        """
        if not positions:
            return {
                "enriched_legs": [],
                "total_pnl": 0.0,
                "realized_pnl": 0.0,
                "open_mtm_pnl": 0.0,
                "open_count": 0,
                "closed_count": 0,
                "net_delta": 0.0,
                "structure": "No Active Positions",
                "risk_profile": "Neutral",
                "is_hedged": True,
                "breakevens": [],
                "suggestions": [],
                "payoff_curve": None,
            }

        # Map available chains by expiry
        chains_by_exp = {}
        if curr_chain and curr_chain.get("expiry"):
            chains_by_exp[curr_chain["expiry"]] = curr_chain
        if next_chain and next_chain.get("expiry"):
            chains_by_exp[next_chain["expiry"]] = next_chain

        enriched_legs = []
        total_pnl = 0.0
        realized_pnl = 0.0
        open_mtm_pnl = 0.0
        open_count = 0
        closed_count = 0
        net_delta = 0.0

        short_ces = []
        buy_ces = []
        short_pes = []
        buy_pes = []

        for leg in positions:
            side = leg["side"]
            otype = leg["type"]
            strike = int(leg["strike"])
            lots = int(leg.get("lots", 1))
            qty = lots * NIFTY_LOT_SIZE
            entry = float(leg["entry_price"])
            exit_p = float(leg.get("exit_price", 0.0) or 0.0)
            is_closed = exit_p > 0.0
            expiry = leg.get("expiry", curr_chain.get("expiry", ""))

            chain = chains_by_exp.get(expiry) or curr_chain or {}
            strikes_map = chain.get("strikes_map", {})
            s_data = strikes_map.get(strike) or strikes_map.get(str(strike)) or {}

            if otype == "CE":
                live_ltp = float(s_data.get("ce_ltp", 0.0))
                iv = float(s_data.get("ce_iv", 15.0)) or 15.0
                oi = int(s_data.get("ce_oi", 0))
            else:
                live_ltp = float(s_data.get("pe_ltp", 0.0))
                iv = float(s_data.get("pe_iv", 15.0)) or 15.0
                oi = int(s_data.get("pe_oi", 0))

            # Fallback if strike missing in chain
            if live_ltp <= 0:
                intrinsic = (
                    max(0.0, spot - strike)
                    if otype == "CE"
                    else max(0.0, strike - spot)
                )
                live_ltp = round(intrinsic if intrinsic > 0 else entry, 2)

            mark_price = exit_p if is_closed else live_ltp

            if side == "SELL":
                pts_pnl = entry - mark_price
                pnl = pts_pnl * qty
            else:
                pts_pnl = mark_price - entry
                pnl = pts_pnl * qty

            total_pnl += pnl
            if is_closed:
                realized_pnl += pnl
                closed_count += 1
            else:
                open_mtm_pnl += pnl
                open_count += 1

            # Distance from spot (positive = OTM for option seller)
            if otype == "CE":
                dist_pts = strike - spot
            else:
                dist_pts = spot - strike
            dist_pct = (dist_pts / spot * 100.0) if spot > 0 else 0.0

            if is_closed:
                signed_delta = 0.0
                status = "CLOSED"
                status_color = "#848e9c"
            else:
                unit_delta = estimate_option_delta(spot, strike, otype, iv, dte_curr)
                signed_delta = (-unit_delta if side == "SELL" else unit_delta) * (
                    qty / NIFTY_LOT_SIZE
                )
                net_delta += signed_delta

                # Risk status badge
                if side == "BUY":
                    status = "Hedge / Long"
                    status_color = "#64b5f6"
                elif dist_pts < 0:
                    status = "ITM Danger"
                    status_color = "#ff5252"
                elif dist_pts <= 120:
                    status = "Tested (Near Spot)"
                    status_color = "#ffb300"
                else:
                    status = "Safe OTM"
                    status_color = "#00c853"

            enriched = {
                **leg,
                "qty": qty,
                "exit_price": round(exit_p, 2),
                "is_closed": is_closed,
                "live_ltp": round(live_ltp, 2),
                "iv": round(iv, 1),
                "oi": oi,
                "pts_pnl": round(pts_pnl, 2),
                "pnl": round(pnl, 2),
                "dist_pts": round(dist_pts, 1),
                "dist_pct": round(dist_pct, 2),
                "delta": round(signed_delta, 2),
                "status": status,
                "status_color": status_color,
            }
            enriched_legs.append(enriched)

            if not is_closed:
                if side == "SELL" and otype == "CE":
                    short_ces.append(enriched)
                elif side == "BUY" and otype == "CE":
                    buy_ces.append(enriched)
                elif side == "SELL" and otype == "PE":
                    short_pes.append(enriched)
                elif side == "BUY" and otype == "PE":
                    buy_pes.append(enriched)

        # Determine structure & hedge completeness
        short_ce_qty = sum(l["qty"] for l in short_ces)
        buy_ce_qty = sum(l["qty"] for l in buy_ces)
        short_pe_qty = sum(l["qty"] for l in short_pes)
        buy_pe_qty = sum(l["qty"] for l in buy_pes)

        unhedged_ce = max(0, short_ce_qty - buy_ce_qty)
        unhedged_pe = max(0, short_pe_qty - buy_pe_qty)
        is_hedged = (unhedged_ce == 0) and (unhedged_pe == 0)

        if open_count == 0 and closed_count > 0:
            structure = "All Positions Closed Today"
            risk_profile = "Flat (No Open Risk)"
        elif short_ces and short_pes and buy_ces and buy_pes:
            structure = "Iron Condor / Iron Fly (Hedged)"
        elif short_ces and short_pes:
            structure = "Short Strangle / Straddle (Naked)"
        elif short_ces and buy_ces and not short_pes:
            structure = "Bear Call Credit Spread"
        elif short_pes and buy_pes and not short_ces:
            structure = "Bull Put Credit Spread"
        elif short_ces and not short_pes:
            structure = "Naked Short Call (Bearish)"
        elif short_pes and not short_ces:
            structure = "Naked Short Put (Bullish)"
        else:
            structure = "Custom / Directional Option Book"

        if open_count > 0:
            risk_profile = (
                "Defined / Capped Risk"
                if is_hedged
                else "Unlimited Tail Risk (Unhedged Short)"
            )

        # Compute expiry payoff curve across spot -600 to +600
        payoff_curve = self._compute_payoff_curve(enriched_legs, spot)
        breakevens = self._find_breakevens(payoff_curve)

        # Generate Risk Minimization & Profit Maximization Strategies
        if open_count == 0 and closed_count > 0:
            suggestions = [{
                "category": "TODAY'S P&L SUMMARY",
                "priority": "DONE",
                "color": "#00e676" if realized_pnl >= 0 else "#ff5252",
                "title": f"All {closed_count} Leg(s) Closed Today — Net Realized P&L: {'+' if realized_pnl >= 0 else ''}₹{realized_pnl:,.0f}",
                "action": "Zero open intraday or overnight risk remaining.",
                "why": "Capital is free for your next high-probability setup.",
            }]
        else:
            suggestions = self._generate_strategy_suggestions(
                enriched_legs=enriched_legs,
                short_ces=short_ces,
                buy_ces=buy_ces,
                short_pes=short_pes,
                buy_pes=buy_pes,
                unhedged_ce=unhedged_ce,
                unhedged_pe=unhedged_pe,
                net_delta=net_delta,
                spot=spot,
                curr_chain=curr_chain,
                tech_data=tech_data,
            )

        return {
            "enriched_legs": enriched_legs,
            "total_pnl": round(total_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "open_mtm_pnl": round(open_mtm_pnl, 2),
            "open_count": open_count,
            "closed_count": closed_count,
            "net_delta": round(net_delta, 2),
            "structure": structure,
            "risk_profile": risk_profile,
            "is_hedged": is_hedged,
            "breakevens": breakevens,
            "suggestions": suggestions,
            "payoff_curve": payoff_curve,
            "max_profit": payoff_curve["max_profit"] if payoff_curve else 0.0,
            "max_loss": payoff_curve["max_loss"] if payoff_curve else 0.0,
        }

    def _compute_payoff_curve(
        self, legs: List[Dict[str, Any]], spot: float
    ) -> Dict[str, Any]:
        center = int(round(spot / 50.0) * 50) if spot > 0 else 25000
        spot_grid = list(range(center - 700, center + 750, 25))
        pnls = []
        for s in spot_grid:
            total = 0.0
            for l in legs:
                if l.get("is_closed"):
                    total += l["pnl"]
                    continue
                k = l["strike"]
                entry = l["entry_price"]
                qty = l["qty"]
                intrinsic = (
                    max(0.0, s - k) if l["type"] == "CE" else max(0.0, k - s)
                )
                if l["side"] == "SELL":
                    total += (entry - intrinsic) * qty
                else:
                    total += (intrinsic - entry) * qty
            pnls.append(round(total, 2))
        return {
            "spots": spot_grid,
            "pnls": pnls,
            "max_profit": max(pnls) if pnls else 0.0,
            "max_loss": min(pnls) if pnls else 0.0,
        }

    def _find_breakevens(self, payoff_curve: Dict[str, Any]) -> List[int]:
        spots = payoff_curve.get("spots", [])
        pnls = payoff_curve.get("pnls", [])
        bes = []
        for i in range(1, len(spots)):
            if (pnls[i - 1] < 0 <= pnls[i]) or (pnls[i - 1] > 0 >= pnls[i]):
                bes.append(spots[i])
        return bes

    def _pick_live_strike(
        self,
        strikes_map: Dict[Any, Any],
        target_strike: int,
        opt_type: str,
        min_ltp: float = 10.0,
    ) -> Tuple[int, float]:
        """Finds closest valid strike in live NSE option chain."""
        best_k = target_strike
        best_ltp = 0.0
        for offset in (0, 50, -50, 100, -100, 150, -150):
            k = target_strike + offset
            row = strikes_map.get(k) or strikes_map.get(str(k))
            if row:
                ltp = float(row.get("ce_ltp" if opt_type == "CE" else "pe_ltp", 0.0))
                if ltp >= min_ltp:
                    return k, round(ltp, 2)
                if ltp > best_ltp:
                    best_k, best_ltp = k, round(ltp, 2)
        return best_k, best_ltp

    def _generate_strategy_suggestions(
        self,
        enriched_legs: List[Dict[str, Any]],
        short_ces: List[Dict[str, Any]],
        buy_ces: List[Dict[str, Any]],
        short_pes: List[Dict[str, Any]],
        buy_pes: List[Dict[str, Any]],
        unhedged_ce: int,
        unhedged_pe: int,
        net_delta: float,
        spot: float,
        curr_chain: Dict[str, Any],
        tech_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []
        strikes_map = (curr_chain or {}).get("strikes_map", {})
        atm = int(round(spot / 50.0) * 50) if spot > 0 else 25200

        # 1. CRITICAL RISK MINIMIZATION: Tested / ITM Short Legs
        for leg in short_ces + short_pes:
            if leg["dist_pts"] < 0:
                safe_target = (
                    atm + 250 if leg["type"] == "CE" else atm - 250
                )
                roll_k, roll_ltp = self._pick_live_strike(
                    strikes_map, safe_target, leg["type"], min_ltp=25.0
                )
                untested_note = ""
                if leg["type"] == "CE" and short_pes:
                    pe_leg = short_pes[0]
                    untested_note = (
                        f" Simultaneously, consider rolling your safe {pe_leg['strike']} PE up closer to "
                        f"{atm - 150} PE to collect extra credit and offset the roll cost."
                    )
                elif leg["type"] == "PE" and short_ces:
                    ce_leg = short_ces[0]
                    untested_note = (
                        f" Simultaneously, consider rolling your safe {ce_leg['strike']} CE down closer to "
                        f"{atm + 150} CE to collect extra credit and offset the roll cost."
                    )
                suggestions.append({
                    "category": "RISK MINIMIZATION",
                    "priority": "CRITICAL",
                    "color": "#ff5252",
                    "title": f"Defend ITM {leg['strike']} {leg['type']} (Spot is {abs(leg['dist_pts']):.0f} pts ITM)",
                    "action": (
                        f"Square off {leg['strike']} {leg['type']} (Live ₹{leg['live_ltp']:.2f}) and roll out/away to "
                        f"**{roll_k} {leg['type']}** (Live ₹{roll_ltp:.2f}).{untested_note}"
                    ),
                    "why": "ITM short options carry accelerating gamma risk and lose time-value protection.",
                })
            elif leg["dist_pts"] <= 120:
                roll_target = leg["strike"] + 150 if leg["type"] == "CE" else leg["strike"] - 150
                roll_k, roll_ltp = self._pick_live_strike(
                    strikes_map, roll_target, leg["type"], min_ltp=20.0
                )
                suggestions.append({
                    "category": "RISK MINIMIZATION",
                    "priority": "HIGH",
                    "color": "#ffb300",
                    "title": f"{leg['strike']} {leg['type']} Under Pressure ({leg['dist_pts']:.0f} pts from Spot)",
                    "action": (
                        f"Keep strict stop-loss at ₹{leg['entry_price'] * 1.5:.1f} (1.5x entry) or pre-emptively roll to "
                        f"**{roll_k} {leg['type']}** (@ ₹{roll_ltp:.2f}) if spot closes beyond {leg['strike']}."
                    ),
                    "why": "Within 120 pts of spot, a single 15-min momentum candle can push this leg ITM.",
                })

        # 2. HIGH RISK MINIMIZATION: Unhedged / Naked Short Tail-Risk
        if unhedged_ce > 0:
            highest_short_ce = max(l["strike"] for l in short_ces)
            hedge_k, hedge_ltp = self._pick_live_strike(
                strikes_map, highest_short_ce + 200, "CE", min_ltp=8.0
            )
            lots_needed = max(1, unhedged_ce // NIFTY_LOT_SIZE)
            suggestions.append({
                "category": "RISK MINIMIZATION",
                "priority": "HIGH",
                "color": "#ff9800",
                "title": f"Cap Unlimited Upside Gap Risk on {unhedged_ce} Qty Short CE",
                "action": (
                    f"**Buy {lots_needed} lot(s) {hedge_k} CE @ ₹{hedge_ltp:.2f}** "
                    f"(Cost: ₹{hedge_ltp * unhedged_ce:,.0f}) to convert naked call into a defined-risk Bear Call Spread."
                ),
                "why": "Eliminates overnight gap-up tail risk and typically reduces SPAN+Exposure margin by 45–60%.",
            })

        if unhedged_pe > 0:
            lowest_short_pe = min(l["strike"] for l in short_pes)
            hedge_k, hedge_ltp = self._pick_live_strike(
                strikes_map, lowest_short_pe - 200, "PE", min_ltp=8.0
            )
            lots_needed = max(1, unhedged_pe // NIFTY_LOT_SIZE)
            suggestions.append({
                "category": "RISK MINIMIZATION",
                "priority": "HIGH",
                "color": "#ff9800",
                "title": f"Cap Unlimited Downside Gap Risk on {unhedged_pe} Qty Short PE",
                "action": (
                    f"**Buy {lots_needed} lot(s) {hedge_k} PE @ ₹{hedge_ltp:.2f}** "
                    f"(Cost: ₹{hedge_ltp * unhedged_pe:,.0f}) to convert naked put into a defined-risk Bull Put Spread."
                ),
                "why": "Protects against sudden macro/geopolitical gap-downs and frees up pledged margin.",
            })

        # 3. PROFIT MAXIMIZATION: Unbalanced / Single-Sided Income Opportunity
        adx_val = float((tech_data or {}).get("adx", {}).get("value", 20.0))
        if short_ces and not short_pes and adx_val < 28:
            pe_target = atm - 300
            pe_k, pe_ltp = self._pick_live_strike(strikes_map, pe_target, "PE", min_ltp=25.0)
            suggestions.append({
                "category": "PROFIT MAXIMIZATION",
                "priority": "OPPORTUNITY",
                "color": "#00c853",
                "title": "Add Opposite Put Leg for Zero-Extra-Margin Theta Boost",
                "action": (
                    f"Since you only hold Short Calls and ADX ({adx_val:.1f}) shows no runaway trend, "
                    f"consider **Selling {pe_k} PE @ ₹{pe_ltp:.2f}** (paired with a cheap {pe_k - 200} PE hedge)."
                ),
                "why": "Balances net delta closer to zero and nearly doubles daily theta decay without extra margin.",
            })
        elif short_pes and not short_ces and adx_val < 28:
            ce_target = atm + 300
            ce_k, ce_ltp = self._pick_live_strike(strikes_map, ce_target, "CE", min_ltp=25.0)
            suggestions.append({
                "category": "PROFIT MAXIMIZATION",
                "priority": "OPPORTUNITY",
                "color": "#00c853",
                "title": "Add Opposite Call Leg for Zero-Extra-Margin Theta Boost",
                "action": (
                    f"Since you only hold Short Puts and ADX ({adx_val:.1f}) is controlled, "
                    f"consider **Selling {ce_k} CE @ ₹{ce_ltp:.2f}** (paired with a cheap {ce_k + 200} CE hedge)."
                ),
                "why": "Collects additional call-side premium while keeping your net delta balanced.",
            })

        # 4. PROFIT MAXIMIZATION: Decayed Winner Harvesting
        for leg in short_ces + short_pes:
            if leg["entry_price"] > 0 and leg["live_ltp"] <= leg["entry_price"] * 0.45:
                captured_pct = (
                    (leg["entry_price"] - leg["live_ltp"]) / leg["entry_price"]
                ) * 100.0
                closer_target = (
                    max(atm + 150, leg["strike"] - 100)
                    if leg["type"] == "CE"
                    else min(atm - 150, leg["strike"] + 100)
                )
                new_k, new_ltp = self._pick_live_strike(
                    strikes_map, closer_target, leg["type"], min_ltp=30.0
                )
                suggestions.append({
                    "category": "PROFIT MAXIMIZATION",
                    "priority": "OPTIMIZE",
                    "color": "#00e676",
                    "title": f"Harvest {captured_pct:.0f}% Decay on {leg['strike']} {leg['type']} (₹{leg['live_ltp']:.2f} left)",
                    "action": (
                        f"Book profits on {leg['strike']} {leg['type']} (+₹{leg['pnl']:,.0f}) or roll closer to "
                        f"**{new_k} {leg['type']}** (@ ₹{new_ltp:.2f}) to reload theta decay."
                    ),
                    "why": "Once 55%+ of an option's premium is captured, remaining reward-to-risk is unfavorable.",
                })

        # 5. DIRECTIONAL ALIGNMENT CHECK (Delta vs Technicals)
        st_trend = (tech_data or {}).get("supertrend", {}).get("signal", "Neutral")
        if abs(net_delta) >= 0.35:
            bias = "Bullish" if net_delta > 0 else "Bearish"
            if (bias == "Bearish" and "Bullish" in st_trend) or (
                bias == "Bullish" and "Bearish" in st_trend
            ):
                suggestions.append({
                    "category": "RISK MINIMIZATION",
                    "priority": "MEDIUM",
                    "color": "#ffb300",
                    "title": f"Delta Conflict: Book is {bias} (Net Δ {net_delta:+.2f}) vs {st_trend} Technicals",
                    "action": (
                        f"Your net exposure ({bias}) opposes the live SuperTrend ({st_trend}). "
                        "Trim directional size or add an opposing credit leg to neutralize delta."
                    ),
                    "why": "Fighting the dominant intraday trend increases MTM drawdown risk.",
                })

        if not suggestions:
            suggestions.append({
                "category": "PROFIT MAXIMIZATION",
                "priority": "HOLD",
                "color": "#00c853",
                "title": "Position Well-Balanced — Hold & Collect Theta",
                "action": (
                    "All short legs are safely OTM and hedged. Maintain trailing stop-loss at 1.5x entry premium "
                    "and let time decay work."
                ),
                "why": "No immediate adjustment needed; unnecessary churning erodes brokerage and slippage.",
            })

        return suggestions
