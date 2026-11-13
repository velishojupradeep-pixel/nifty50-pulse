"""
Institutional Large-Quantity Option Seller Module.
Designed specifically for heavy lot-size traders (50 to 1,000+ lots / ₹50L to ₹10Cr+ capital).
Provides order slicing, liquidity grading, margin efficiency optimization, and dynamic adjustment protocols.
"""

from typing import Dict, Any, List


class InstitutionalAdvisor:
    """Specialized analytics and execution rules for high-quantity option sellers."""

    # NSE Freeze Limit for NIFTY Index Options is typically 1,800 units (~36-72 lots depending on lot size)
    FREEZE_LIMIT_UNITS = 1800
    LOT_SIZE = 65  # Standard NIFTY lot size

    @classmethod
    def get_max_lots_per_order(cls) -> int:
        return cls.FREEZE_LIMIT_UNITS // cls.LOT_SIZE  # e.g., 72 lots

    @classmethod
    def evaluate_strike_liquidity(cls, oi: int, volume: int = 0) -> Dict[str, Any]:
        """
        Grades strike execution capacity based on Open Interest and depth.
        Crucial for large accounts to avoid catastrophic bid-ask slippage.
        """
        if oi >= 150_000:
            return {
                "grade": "EXCELLENT",
                "badge": "🟢 Institutional Grade (High Depth)",
                "color": "#00c853",
                "max_safe_lots_single_order": 50,
                "slippage_risk": "Low (< 0.20 pts)",
                "comment": "Safe for large batch execution and automated market-making.",
            }
        elif oi >= 75_000:
            return {
                "grade": "MODERATE",
                "badge": "🟡 Moderate Liquidity",
                "color": "#ffb300",
                "max_safe_lots_single_order": 25,
                "slippage_risk": "Moderate (0.30 - 0.60 pts)",
                "comment": "Execute with limit order slicing; avoid dumping large market orders.",
            }
        else:
            return {
                "grade": "THIN",
                "badge": "🚨 Thin Liquidity (Slippage Danger)",
                "color": "#ff3344",
                "max_safe_lots_single_order": 10,
                "slippage_risk": "High (> 1.0 pt)",
                "comment": "Emergency exits will face heavy spread penalty. Avoid large naked size.",
            }

    @classmethod
    def calculate_order_slicing(cls, total_lots: int) -> Dict[str, Any]:
        """Calculates order slices to stay below exchange freeze limits and minimize market impact."""
        max_slice = cls.get_max_lots_per_order()
        slice_size = min(total_lots, max_slice)
        num_slices = (total_lots + slice_size - 1) // slice_size if total_lots > 0 else 1

        return {
            "total_lots": total_lots,
            "total_quantity": total_lots * cls.LOT_SIZE,
            "freeze_limit_per_order": cls.FREEZE_LIMIT_UNITS,
            "num_slices": num_slices,
            "slice_size_lots": slice_size,
            "slice_size_qty": slice_size * cls.LOT_SIZE,
            "execution_tip": f"Split {total_lots} lots into {num_slices} limit orders of ~{slice_size} lots with a 500ms delay to absorb queue depth smoothly.",
        }

    @classmethod
    def calculate_capital_and_margin(cls, capital_inr: float, current_spot: float) -> Dict[str, Any]:
        """
        Compares Naked Strangle vs Hedged Institutional Iron Condor margin requirements.
        Demonstrates the 3.2x capital efficiency and overnight safety of long wings.
        """
        # Benchmark exchange margin
        naked_margin_per_lot = 125_000.0   # ~₹1.25 Lakhs per naked strangle
        hedged_margin_per_lot = 38_000.0    # ~₹38k per hedged iron condor with 200pt wings

        # Max safe capacity (utilizing 75% capital to maintain peak margin buffer)
        safe_deploy_capital = capital_inr * 0.75

        naked_lots = int(safe_deploy_capital // naked_margin_per_lot)
        hedged_lots = int(safe_deploy_capital // hedged_margin_per_lot)

        margin_saved_pct = round(((naked_margin_per_lot - hedged_margin_per_lot) / naked_margin_per_lot) * 100, 1)

        return {
            "capital_inr": capital_inr,
            "safe_deploy_capital": safe_deploy_capital,
            "naked_margin_per_lot": naked_margin_per_lot,
            "hedged_margin_per_lot": hedged_margin_per_lot,
            "margin_saved_pct": margin_saved_pct,
            "naked_max_lots": max(1, naked_lots),
            "hedged_max_lots": max(1, hedged_lots),
            "capacity_multiplier": round(hedged_lots / max(naked_lots, 1), 1),
        }

    @classmethod
    def get_institutional_adjustment_playbook(cls, spot: float, sell_ce: int, sell_pe: int, ce_ltp: float, pe_ltp: float) -> List[Dict[str, Any]]:
        """
        Provides the 3-Step Systematic Adjustment Protocol used by institutional desks
        when NIFTY experiences strong intraday directional drift.
        """
        return [
            {
                "step": "Phase 1: Untested Leg Roll-up / Roll-down (100-Point Rule)",
                "trigger": f"If Spot moves ±75 to 100 points towards either sold strike (Spot > {spot + 80:.0f} or Spot < {spot - 80:.0f}).",
                "action": (
                    f"Roll the untested side closer to spot. For example, if NIFTY rallies, your Put premium has decayed by > 50%. "
                    f"Square off current {sell_pe} PE and sell {sell_pe + 100} PE to collect an additional ₹25-35 premium and recenter portfolio delta."
                ),
                "goal": "Locks in profit on winning leg, raises breakeven cushion on losing leg without adding risk.",
            },
            {
                "step": "Phase 2: Inversion / Straddle Conversion (Strong Momentum Defense)",
                "trigger": f"If Spot breaches 50% distance to short strike (Spot > {sell_ce - 50} or Spot < {sell_pe + 50}).",
                "action": (
                    f"Roll untested side completely into the ATM strike or tested strike, converting the Strangle into an Iron Fly. "
                    f"If Call is threatened, roll Put to ATM to double the total credit collected."
                ),
                "goal": "Maximizes collected premium to withstand large continuation moves.",
            },
            {
                "step": "Phase 3: Hard Stop-Loss & Wing Shield (Emergency Protocol)",
                "trigger": f"Individual sold leg premium reaches 1.5x of entry (CE SL: ₹{ce_ltp * 1.5:.1f} | PE SL: ₹{pe_ltp * 1.5:.1f}).",
                "action": (
                    "Strictly exit the tested sold leg. DO NOT hope for reversal against heavy institutional volume. "
                    "Your long hedge wings strictly cap overnight tail-risk against gap openings."
                ),
                "goal": "Preserves capital and eliminates emotional holding during breakout days.",
            },
        ]
