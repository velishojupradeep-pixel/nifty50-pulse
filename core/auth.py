"""
Supabase Authentication Helper for NIFTY 50 Option Seller Radar.
Uses Supabase GoTrue HTTPS REST API with st.secrets / environment variables.
"""

import os
from typing import Dict, Any, Optional, Tuple
import requests


def get_supabase_credentials() -> Tuple[str, str]:
    """Reads SUPABASE_URL and SUPABASE_ANON_KEY from st.secrets or environment."""
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()

    try:
        import streamlit as st

        if not url and "SUPABASE_URL" in st.secrets:
            url = str(st.secrets["SUPABASE_URL"]).strip().rstrip("/")
        if not key and "SUPABASE_ANON_KEY" in st.secrets:
            key = str(st.secrets["SUPABASE_ANON_KEY"]).strip()
    except Exception:
        pass

    return url, key


class SupabaseAuthClient:
    """Lightweight, zero-SDK-bloat Supabase Auth client over HTTPS."""

    def __init__(self):
        self.url, self.anon_key = get_supabase_credentials()

    def is_configured(self) -> bool:
        return bool(self.url and self.anon_key)

    def _headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def sign_up(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Registers a new user via Supabase Auth."""
        if not self.is_configured():
            return False, "Supabase credentials are not configured.", None
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/signup",
                headers=self._headers(),
                json={"email": email.strip(), "password": password},
                timeout=10,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code in (200, 201):
                user = data.get("user") or {}
                access_token = data.get("access_token")
                if access_token and user.get("id"):
                    session = {
                        "user_id": user["id"],
                        "email": user.get("email", email.strip()),
                        "access_token": access_token,
                        "refresh_token": data.get("refresh_token", ""),
                    }
                    return True, "Account created and signed in!", session
                return (
                    True,
                    "Account created! Please check your email to confirm, then sign in.",
                    None,
                )
            err = data.get("msg") or data.get("error_description") or data.get("message") or "Sign up failed."
            return False, str(err), None
        except Exception as exc:
            return False, f"Connection error: {exc}", None

    def sign_in(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Authenticates user with email & password and returns JWT session."""
        if not self.is_configured():
            return False, "Supabase credentials are not configured.", None
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/token?grant_type=password",
                headers=self._headers(),
                json={"email": email.strip(), "password": password},
                timeout=10,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get("access_token"):
                user = data.get("user") or {}
                session = {
                    "user_id": user.get("id", ""),
                    "email": user.get("email", email.strip()),
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", ""),
                }
                return True, f"Signed in as {session['email']}", session
            err = data.get("error_description") or data.get("msg") or data.get("message") or "Invalid email or password."
            return False, str(err), None
        except Exception as exc:
            return False, f"Connection error: {exc}", None

    def get_user(self, access_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validates an existing access_token via Supabase /auth/v1/user without rotating refresh_token."""
        if not self.is_configured() or not access_token:
            return False, None
        try:
            resp = requests.get(
                f"{self.url}/auth/v1/user",
                headers=self._headers(access_token.strip()),
                timeout=8,
            )
            if resp.status_code == 200:
                user = resp.json() if resp.content else {}
                if user.get("id"):
                    return True, {
                        "user_id": user["id"],
                        "email": user.get("email", ""),
                        "access_token": access_token.strip(),
                    }
            return False, None
        except Exception:
            return False, None

    def refresh_session(self, refresh_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Restores/refreshes a Supabase session using a stored refresh_token."""
        if not self.is_configured() or not refresh_token:
            return False, None
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/token?grant_type=refresh_token",
                headers=self._headers(),
                json={"refresh_token": refresh_token.strip()},
                timeout=10,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get("access_token"):
                user = data.get("user") or {}
                session = {
                    "user_id": user.get("id", ""),
                    "email": user.get("email", ""),
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", refresh_token),
                }
                return True, session
            return False, None
        except Exception:
            return False, None

    def send_password_reset(self, email: str) -> Tuple[bool, str]:
        """Sends a password reset email via Supabase."""
        if not self.is_configured():
            return False, "Supabase credentials are not configured."
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/recover",
                headers=self._headers(),
                json={"email": email.strip()},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return True, "Password reset email sent (check your inbox)."
            data = resp.json() if resp.content else {}
            return False, str(data.get("msg") or "Could not send reset email.")
        except Exception as exc:
            return False, f"Connection error: {exc}"

    def sign_out(self, access_token: Optional[str]) -> None:
        """Revokes the current Supabase session token."""
        if not self.is_configured() or not access_token:
            return
        try:
            requests.post(
                f"{self.url}/auth/v1/logout",
                headers=self._headers(access_token),
                timeout=5,
            )
        except Exception:
            pass
