"""Configuration helpers for separately deployed HWARANG applications."""
from __future__ import annotations

import os

import streamlit as st


def external_app_url(key: str) -> str:
    """Return a validated external-app URL from Secrets or environment.

    Streamlit Community Cloud deployments should define::

        [external_apps]
        calculator_url = "https://...streamlit.app"
        ACADEMY_URL = "https://...streamlit.app"

    Secret keys are matched case-insensitively, so ``academy_url`` and
    ``ACADEMY_URL`` are equivalent. Environment fallbacks use ``HW_<KEY>``.
    """
    value = ""
    try:
        section = dict(st.secrets.get("external_apps", {}))
        normalized = {str(name).lower(): item for name, item in section.items()}
        value = str(normalized.get(key.lower(), "") or "").strip()
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


def academy_url() -> str:
    return external_app_url("academy_url")


def workspace_url() -> str:
    return external_app_url("workspace_url")
