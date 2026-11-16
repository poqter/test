# Explicit self-tests, independent of regular delivery

Test requests do not alter the daily subscription, its jobs/batches, or cron. Existing test history is retained. There is no lifetime two-test limit.

## Authorization and bounds
- The signed-in owner requests a test with `kakao_request_test(request_id)`; current auth session, active workspace permission, connection, consent, selected weather region and cost gate are checked server-side. Arbitrary-owner request is service-only.
- A request UUID is idempotent. Reusing it returns its prior state without another network request. The UI retains it when an HTTP response is uncertain.
- No fixed daily test-count limit or mandatory delay after a completed request. A pending or uncertain send blocks new requests; no automatic resend.
- Each request can send at most one 200 UTF-16 message. Content and button are identical to the regular briefing, with no test header. Longer content fails before sending, rather than truncating.
- Function work is counted in the existing bounded budget. Tests leave two function units for the normal tick/send path and never consume normal daily batches. The function allocation is a shared free-capacity safeguard, not a Kakao per-user limit.
- Weather uses the normal validated cache. A test may fetch only when at least one source attempt remains reserved afterward for normal delivery. No paid/provider fallback.

## Delivery safety
- Requests are inserted and queued atomically. A random 256-bit ticket is stored only as a hash and expires within three minutes. The HTTP queue contains the temporary ticket, never a persistent account credential.
- Service-only claim changes queued to processing once. Concurrent callers cannot reuse it.
- Live ownership, consent, generation and schedule snapshot are rechecked immediately before sending. Tests never rotate shared credentials; an expiring token fails before transmission.
- Original fixed-slot records are retained as history, not reset or retried. Expired processing is shown as uncertain and remains blocked pending investigation.
- accepted means Kakao API acceptance, not device delivery or read. Lost responses and recording failures are uncertain and are never retried automatically.

## UI
In Kakao briefing settings, expand `시험 발송`. `시험 메시지 보내기` requests delivery, and `시험 상태 새로고침` refreshes the private result. This does not change the normal delivery time.

## Verification
Node mock-worker tests check identical regular content, cap, authorization, timeout/no-retry and cache behavior. Python Streamlit tests cover authenticated request IDs, pending/uncertain disablement and settings isolation. Local PostgreSQL integration verifies authenticated ownership, idempotency/shared-budget boundaries, ACL, independent history, weather reservation and normal state invariance.
