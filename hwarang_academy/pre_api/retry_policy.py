"""Retry policy for the future paid AI transport.

Retries reuse the same DB request/reservation and idempotency key.  A retry must
never call `reserve_*` again, otherwise temporary provider failures could double
reserve or double-charge a user.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constants import AI_RETRY_LIMIT


_RETRYABLE_HTTP_STATUS = {408, 409, 429, 500, 502, 503, 504}
_RETRYABLE_ERROR_CODES = {
    "timeout",
    "connection_error",
    "rate_limit",
    "server_error",
    "temporarily_unavailable",
}


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    attempt: int
    max_retries: int
    delay_seconds: float
    reason: str


def retry_decision(
    *,
    attempt: int,
    http_status: int | None = None,
    error_code: str | None = None,
) -> RetryDecision:
    """Return deterministic retry guidance for one failed provider attempt.

    `attempt` is zero-based and counts the request that just failed.  With the
    current limit of 2, at most three provider attempts occur: initial + 2 retry.
    """
    current = max(0, int(attempt))
    retryable = (
        (http_status is not None and int(http_status) in _RETRYABLE_HTTP_STATUS)
        or str(error_code or "").strip().lower() in _RETRYABLE_ERROR_CODES
    )
    allowed = retryable and current < AI_RETRY_LIMIT
    # Small bounded exponential backoff; provider Retry-After can override later.
    delay = min(4.0, 0.5 * (2 ** current)) if allowed else 0.0
    reason = "retryable_provider_failure" if retryable else "non_retryable_failure"
    if retryable and not allowed:
        reason = "retry_limit_reached"
    return RetryDecision(
        retry=allowed,
        attempt=current,
        max_retries=AI_RETRY_LIMIT,
        delay_seconds=delay,
        reason=reason,
    )
