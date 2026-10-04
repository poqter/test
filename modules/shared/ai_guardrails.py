"""Pre-API guardrail adapter for HWARANG ACADEMY.

No OpenAI dependency is used here. The functions are database-backed primitives
for Training Credit, idempotency, active-session locks and fail-closed AI
runtime switches. They can be tested with mock usage before an API key exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService


@dataclass(frozen=True)
class TrainingCreditStatus:
    allocation_credits: int = 0
    balance_credits: int = 0
    reserved_credits: int = 0
    available_credits: int = 0
    remaining_percent: float = 0.0
    service_enabled: bool = False
    text_enabled: bool = False
    voice_enabled: bool = False
    assessment_enabled: bool = False
    soft_limit_percent: int = 80
    contact_label: str = "박병선 팀장에게 이용량 추가 문의"
    contact_url: str = ""

    @property
    def is_configured(self) -> bool:
        return self.allocation_credits > 0 or self.service_enabled


def credit_display_state(percent: float, *, allocation_credits: int = 0) -> tuple[str, str]:
    """Return a stable user-facing label and severity token."""
    if allocation_credits <= 0:
        return ("이용량 미지급", "empty")
    p = max(0.0, min(float(percent or 0), 100.0))
    if p >= 76:
        return ("매우 여유", "good")
    if p >= 51:
        return ("여유", "good")
    if p >= 26:
        return ("보통", "normal")
    if p >= 11:
        return ("얼마 남지 않음", "warning")
    if p > 0:
        return ("이용량 추가 필요", "critical")
    return ("이용 한도 도달", "blocked")


def get_training_credit_status(
    auth: HwarangAuthService,
    user_id: str,
) -> TrainingCreditStatus | None:
    """Best-effort status read. Returns None until migration 09 exists."""
    try:
        rows = auth._request(
            "POST",
            "/rest/v1/rpc/get_hwarang_training_credit_status",
            admin=True,
            json={"p_user_id": user_id},
        )
    except HwarangAuthError:
        return None

    row: dict[str, Any] | None = None
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        row = rows[0]
    elif isinstance(rows, dict):
        row = rows
    if not row:
        return None

    return TrainingCreditStatus(
        allocation_credits=int(row.get("allocation_credits") or 0),
        balance_credits=int(row.get("balance_credits") or 0),
        reserved_credits=int(row.get("reserved_credits") or 0),
        available_credits=int(row.get("available_credits") or 0),
        remaining_percent=float(row.get("remaining_percent") or 0),
        service_enabled=bool(row.get("service_enabled")),
        text_enabled=bool(row.get("text_enabled")),
        voice_enabled=bool(row.get("voice_enabled")),
        assessment_enabled=bool(row.get("assessment_enabled")),
        soft_limit_percent=int(row.get("soft_limit_percent") or 80),
        contact_label=str(row.get("contact_label") or "박병선 팀장에게 이용량 추가 문의"),
        contact_url=str(row.get("contact_url") or ""),
    )


def make_idempotency_key(
    *,
    user_id: str,
    academy_session_id: str,
    turn_no: int,
    purpose: str,
    payload_fingerprint: str = "",
) -> str:
    raw = "|".join([
        user_id.strip(),
        academy_session_id.strip(),
        str(int(turn_no)),
        purpose.strip().upper(),
        payload_fingerprint.strip(),
    ])
    return sha256(raw.encode("utf-8")).hexdigest()


def acquire_ai_session(auth: HwarangAuthService, *, user_id: str, academy_session_id: str) -> None:
    auth._request(
        "POST",
        "/rest/v1/rpc/acquire_hwarang_ai_session",
        admin=True,
        json={"p_user_id": user_id, "p_academy_session_id": academy_session_id},
    )


def release_ai_session(auth: HwarangAuthService, *, user_id: str, academy_session_id: str) -> None:
    try:
        auth._request(
            "POST",
            "/rest/v1/rpc/release_hwarang_ai_session",
            admin=True,
            json={"p_user_id": user_id, "p_academy_session_id": academy_session_id},
        )
    except HwarangAuthError:
        pass


def reserve_ai_request(
    auth: HwarangAuthService,
    *,
    user_id: str,
    academy_session_id: str,
    turn_no: int,
    purpose: str,
    interaction_mode: str,
    idempotency_key: str,
    estimated_credits: int,
) -> dict[str, Any]:
    rows = auth._request(
        "POST",
        "/rest/v1/rpc/reserve_hwarang_ai_request",
        admin=True,
        json={
            "p_user_id": user_id,
            "p_academy_session_id": academy_session_id,
            "p_turn_no": int(turn_no),
            "p_purpose": purpose.upper(),
            "p_interaction_mode": interaction_mode.upper(),
            "p_idempotency_key": idempotency_key,
            "p_estimated_credits": int(estimated_credits),
        },
    )
    if isinstance(rows, list) and rows:
        return dict(rows[0])
    if isinstance(rows, dict):
        return dict(rows)
    raise HwarangAuthError("AI 이용량 예약 결과를 확인하지 못했습니다.")


def finalize_ai_request(
    auth: HwarangAuthService,
    *,
    request_id: str,
    result_status: str,
    actual_credits: int,
) -> dict[str, Any]:
    rows = auth._request(
        "POST",
        "/rest/v1/rpc/finalize_hwarang_ai_request",
        admin=True,
        json={
            "p_request_id": request_id,
            "p_result_status": result_status,
            "p_actual_credits": int(actual_credits),
        },
    )
    if isinstance(rows, list) and rows:
        return dict(rows[0])
    if isinstance(rows, dict):
        return dict(rows)
    return {}


def record_ai_usage(
    auth: HwarangAuthService,
    *,
    request_id: str,
    user_id: str,
    academy_session_id: str | None,
    ai_role: str,
    model: str,
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    audio_input_units: int = 0,
    audio_output_units: int = 0,
    unit_price_snapshot: dict[str, Any] | None = None,
    calculated_cost_usd: float = 0.0,
    credits_charged: int = 0,
    status: str = "completed",
    latency_ms: int | None = None,
    prompt_version: str | None = None,
    model_version: str | None = None,
) -> None:
    """Called only after a future external AI request has been finalized."""
    auth._request(
        "POST",
        "/rest/v1/hwarang_ai_usage_log",
        admin=True,
        json={
            "request_id": request_id,
            "user_id": user_id,
            "academy_session_id": academy_session_id,
            "ai_role": ai_role.upper(),
            "model": model,
            "input_tokens": int(input_tokens),
            "cached_tokens": int(cached_tokens),
            "output_tokens": int(output_tokens),
            "audio_input_units": int(audio_input_units),
            "audio_output_units": int(audio_output_units),
            "unit_price_snapshot": unit_price_snapshot or {},
            "calculated_cost_usd": float(calculated_cost_usd),
            "credits_charged": int(credits_charged),
            "status": status,
            "latency_ms": latency_ms,
            "prompt_version": prompt_version,
            "model_version": model_version,
        },
        prefer="return=minimal",
    )
