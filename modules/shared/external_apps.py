"""Configuration helpers for separately deployed HWARANG applications."""
from __future__ import annotations

import os

import streamlit as st


def external_app_url(key: str) -> str:
    """Return a validated external-app URL from Secrets or environment.

    Streamlit Community Cloud deployments should define::

        [external_apps]
        calculator_url = "https://...streamlit.app"

    Local development may instead set ``HW_CALCULATOR_URL``.
    """
    value = ""
    try:
        section = st.secrets.get("external_apps", {})
        value = str(section.get(key, "") or "").strip()
    except (FileNotFoundError, KeyError, TypeError, ValueError, AttributeError):
        value = ""
    if not value:
        env_key = "HW_" + key.upper()
        value = os.getenv(env_key, "").strip()
    if value and not value.lower().startswith(("https://", "http://")):
        return ""
    return value.rstrip("/")


def calculator_url() -> str:
    return external_app_url("calculator_url")
