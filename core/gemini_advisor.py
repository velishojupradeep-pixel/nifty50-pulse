"""
Gemini AI Position Strategist for NIFTY 50 Option Sellers.
Uses Gemini REST API (gemini-3.8-flash) with live NSE option chain, active positions,
technical indicators, and Google Finance macro context injected into every prompt.
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
import requests

GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def get_gemini_api_key(session_key: Optional[str] = None) -> str:
    """Resolves Gemini API key from session input, st.secrets, or environment."""
    if session_key and session_key.strip():
        return session_key.strip()
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return ""


def build_market_context(
    spot: float,
    advisor: Dict[str, Any],
    eval_res: Optional[Dict[str, Any]],
    tech_data: Dict[str, Any],
    macro_data: Dict[str, Any],
) -> str:
    """Builds a compact, factual snapshot of market & portfolio state for Gemini."""
    curr = (advisor or {}).get("curr", {})
    rates = (macro_data or {}).get("rates", {})

    lines = [
        "=== LIVE NIFTY 50 MARKET SNAPSHOT ===",
        f"Spot Price: {spot:,.2f}",
        f"Verdict: {(advisor or {}).get('verdict', 'N/A')} | Bias: {(advisor or {}).get('bias', 'N/A')}",
        f"Current Expiry: {curr.get('expiry', 'N/A')} ({curr.get('dte', 'N/A')} DTE) | ATM Straddle: ₹{curr.get('atm_straddle', 0)} | PCR: {curr.get('pcr', 0)} | Max Pain: {curr.get('max_pain', 0)}",
        f"India VIX: {rates.get('vix', {}).get('price', 'N/A')} ({rates.get('vix', {}).get('status', '')})",
        "",
        "=== TECHNICAL INDICATORS ===",
        f"RSI(14): {tech_data.get('rsi', {}).get('value', 'N/A')} ({tech_data.get('rsi', {}).get('signal', '')})",
        f"ADX(14): {tech_data.get('adx', {}).get('value', 'N/A')} ({tech_data.get('adx', {}).get('signal', '')})",
        f"SuperTrend: {tech_data.get('supertrend', {}).get('signal', 'N/A')} | VWAP: {tech_data.get('vwap', {}).get('value', 'N/A')}",
        f"Bollinger Bands: Lower {tech_data.get('bollinger', {}).get('lower', 'N/A')} | Upper {tech_data.get('bollinger', {}).get('upper', 'N/A')}",
        "",
        "=== GLOBAL MACRO & GEOPOLITICS ===",
        f"Brent Crude: ${rates.get('brent', {}).get('price', 'N/A')} | USD/INR: ₹{rates.get('usdinr', {}).get('price', 'N/A')} | DXY: {rates.get('dxy', {}).get('price', 'N/A')} | US10Y: {rates.get('us10y', {}).get('price', 'N/A')}%",
    ]

    if macro_data.get("gf_summary"):
        # Strip simple HTML tags for clean LLM context
        clean_sum = (
            macro_data["gf_summary"]
            .replace("<b>", "")
            .replace("</b>", "")
            .replace("<i>", "")
            .replace("</i>", "")
        )
        lines.append(f"Google Finance Brief: {clean_sum}")

    lines.append("")
    lines.append("=== USER'S ACTIVE & CLOSED POSITIONS (1 Lot = 65 Qty) ===")
    if eval_res and eval_res.get("enriched_legs"):
        lines.append(
            f"Structure: {eval_res.get('structure')} | Risk Profile: {eval_res.get('risk_profile')} | "
            f"Today's Total P&L: ₹{eval_res.get('total_pnl', 0):,.0f} "
            f"(Realized: ₹{eval_res.get('realized_pnl', 0):,.0f}, Open MTM: ₹{eval_res.get('open_mtm_pnl', 0):,.0f}) | "
            f"Net Delta: {eval_res.get('net_delta', 0):+.2f} | Breakevens: {eval_res.get('breakevens', [])}"
        )
        for leg in eval_res["enriched_legs"]:
            state = f"CLOSED @ ₹{leg['exit_price']}" if leg.get("is_closed") else f"OPEN (Live ₹{leg['live_ltp']}, Dist {leg['dist_pts']:+.0f} pts)"
            lines.append(
                f" - {leg['side']} {leg['strike']} {leg['type']} ({leg['expiry']}) | {leg['lots']} lot(s) ({leg['qty']} qty) | "
                f"Entry ₹{leg['entry_price']} | {state} | P&L: ₹{leg['pnl']:,.0f}"
            )
    else:
        lines.append("No active positions entered yet.")

    return "\n".join(lines)


def ask_gemini_strategist(
    api_key: str,
    user_prompt: str,
    context_text: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[bool, str]:
    """Queries Gemini 2.5 Flash with system instructions + live market/portfolio context."""
    if not api_key:
        return False, "Missing Gemini API Key. Add `GEMINI_API_KEY` in Secrets or enter it above."

    system_instruction = (
        "You are an institutional NIFTY 50 Options Trading & Risk Management Strategist. "
        "Analyze the user's exact open/closed NIFTY option legs (65 qty/lot), live NSE metrics, "
        "technicals, and global macro cues provided in the context. "
        "Be specific with strike prices, stop-loss levels, hedge wings, and roll adjustments. "
        "Keep responses structured, concise, and actionable. "
        "Include a brief 1-line educational/risk disclaimer at the end (not financial advice)."
    )

    contents = []
    # Inject live market & position context into the first turn
    contents.append({
        "role": "user",
        "parts": [{"text": f"Here is my live market & portfolio snapshot:\n\n{context_text}"}],
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "Understood. I have your live NIFTY 50 market snapshot, technicals, macro cues, and exact positions. What would you like to analyze?"}],
    })

    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    contents.append({"role": "user", "parts": [{"text": user_prompt}]})

    try:
        resp = requests.post(
            GEMINI_ENDPOINT,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system_instruction}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1200},
            },
            timeout=25,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200:
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return True, text
            return False, "Gemini returned an empty response."
        err = data.get("error", {}).get("message") or f"HTTP {resp.status_code}"
        return False, f"Gemini API error: {err}"
    except Exception as exc:
        return False, f"Connection error calling Gemini: {exc}"
