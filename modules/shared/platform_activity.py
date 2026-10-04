"""Best-effort operational logging for HWARANG PLATFORM.

This module is intentionally tolerant of a database that has not yet received
migration 09. Operational telemetry must never block a valid user workflow.
"""
from __future__ import annotations

import time
from typing import Any

from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService


def open_session(auth: HwarangAuthService, user_id: str, app_code: str = "workspace") -> str | None:
    try:
        data = auth._request(
            "POST",
            "/rest/v1/rpc/open_hwarang_user_session",
            admin=True,
            json={"p_user_id": user_id, "p_source_app": app_code},
        )
    except HwarangAuthError:
        return None
    if isinstance(data, str):
        return data.strip() or None
    if isinstance(data, dict):
        return str(data.get("open_hwarang_user_session") or data.get("id") or "").strip() or None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, str):
            return first.strip() or None
        if isinstance(first, dict):
            return str(first.get("open_hwarang_user_session") or first.get("id") or "").strip() or None
    return None


def heartbeat(
    auth: HwarangAuthService,
    *,
    platform_session_id: str | None,
    user_id: str,
    last_heartbeat_at: float,
    interval_seconds: int = 300,
) -> float:
    now = time.time()
    if not platform_session_id or now - float(last_heartbeat_at or 0) < interval_seconds:
        return float(last_heartbeat_at or 0)
    try:
        auth._request(
            "POST",
            "/rest/v1/rpc/heartbeat_hwarang_user_session",
            admin=True,
            json={"p_session_id": platform_session_id, "p_user_id": user_id},
        )
        return now
    except HwarangAuthError:
        return float(last_heartbeat_at or 0)


def close_session(
    auth: HwarangAuthService,
    *,
    platform_session_id: str | None,
    user_id: str,
) -> None:
    if not platform_session_id:
        return
    try:
        auth._request(
            "POST",
            "/rest/v1/rpc/close_hwarang_user_session",
            admin=True,
            json={"p_session_id": platform_session_id, "p_user_id": user_id},
        )
    except HwarangAuthError:
        pass


def log_activity(
    auth: HwarangAuthService,
    *,
    user_id: str,
    platform_session_id: str | None,
    app_code: str,
    event_code: str,
    feature_code: str | None = None,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a meaningful event without user/customer free-text."""
    safe_metadata = dict(metadata or {})
    # Explicitly remove common content-bearing keys if a caller accidentally passes them.
    for key in (
        "text", "message", "prompt", "content", "transcript", "customer_name",
        "resident_number", "phone", "email", "file_content",
    ):
        safe_metadata.pop(key, None)

    try:
        auth._request(
            "POST",
            "/rest/v1/rpc/log_hwarang_activity",
            admin=True,
            json={
                "p_user_id": user_id,
                "p_platform_session_id": platform_session_id,
                "p_app_code": app_code,
                "p_event_code": event_code,
                "p_feature_code": feature_code,
                "p_outcome": outcome,
                "p_metadata": safe_metadata,
            },
        )
    except HwarangAuthError:
        pass
