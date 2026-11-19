# Multi-owner daily briefing operations

## Schedule semantics
Each connected owner chooses a minute of day and weekdays, in Asia/Seoul. Distinct minutes share one dispatch and one database-only backstop per minute. Twenty different times produce 40 cron jobs, not 40 Edge invocations. Identical times share a slot. The date of a 23:55 delivery remains the scheduled date if processing crosses midnight. Owner/date batch uniqueness prevents replay after changing the delivery time on the same day.

Weekdays are supported. Public holidays, substitute holidays and personal holiday exceptions are not automatically excluded.

## Capacity is not a delivery guarantee
Normal briefings split without content truncation into messages of at most 200 UTF-16 units. Twenty owners do not necessarily mean twenty messages. A one-part daily briefing for 20 owners is 620 messages over 31 days; distinct daily times need roughly 1,240 internal work units before extra parts/continuations. These internal units are not Supabase's billed invocation count.

The worker prepares up to 25 owners and processes up to 25 parts per tick, with bounded elapsed-time checks and continuation. Within each Edge invocation, up to three different owners can deliver concurrently; each owner remains strictly sequential even across overlapping invocations. This is not a global three-owner semaphore. The pending list rotates between owners while preserving each owner’s database batch chronology. A failed or uncertain part closes that owner’s stale local queue. Delivery has a ten-minute deadline. Slow provider or database responses can cause partial or missed delivery. The system does not silently retry uncertain provider outcomes. One owner's uncertain part stops that owner's remaining parts, without intentionally stopping others.

Local mocked load regression covers twenty owners with five parts each, bounded cross-owner concurrency, duplicate ticks, token rotation conflicts and uncertain responses. Older serial baseline models reached a ten-minute deadline under slow provider responses; parallelism reduces cross-owner waiting but does not remove that deadline or guarantee completion. Model results are not measured production performance or promises.

## Free service accounting
Kakao memo-to-self uses the app's overall monthly free API quota, not the friend-message per-user daily limit. Supabase Free has an organization-wide invocation allowance and does not automatically charge overages, but availability can be restricted. Other projects/API routes share provider usage. Internal counters omit unauthorized or otherwise rejected Edge invocations and must never be presented as the provider usage meter.

Do not enable paid APIs, upgrade plans or automatically buy capacity. Confirm provider dashboards and account for other use before configuring operational allocations. Configuration values are local protective allocations, not provider prices or quotas. Refresh cost verification before its expiry and report a renewal failure rather than silently claiming ongoing readiness.

## Verification and reporting
Use the SQL twenty-schedule regression and the worker load regression without external delivery. Preserve each user's authorization, generation and consent checks, request idempotency, uncertain no-retry behavior and all historical rows. Report accepted/total parts, uncertain and missed results separately. API acceptance is not confirmation of device receipt.

## 2026-11-17 reviewed allocation
Dashboard evidence: Kakao app 17/3,000,000 monthly requests (hourly refresh), paid APIs disabled; Supabase organization-wide Edge 35/500,000, Free with no automatic overage billing. Dashboard values can lag real requests.

Reviewed local monthly allocations: 10,000 normal messages, 10,000 normal work units, 10,000 test work units, 20,000 shared work units. Reviewed external weather-fetch allocations per Korean day: 100 normal, 100 test, 200 shared. These are separate protection pools, not provider limits or delivery guarantees. Cache hits do not use fetch allocations. Old weather attempts without provenance remain conservatively charged to normal history.

The operational cost verification expires at 2026-12-01 09:00 Asia/Seoul. Renewal requires checking the free plan, paid-feature status and shared usage again. No payment, paid quota purchase or subscription change is authorized by this document.

Sources: https://developers.kakao.com/docs/ko/getting-started/quota ; https://devtalk.kakao.com/t/api/145613 ; https://supabase.com/docs/guides/platform/cost-control ; https://supabase.com/docs/guides/platform/manage-your-usage/edge-function-invocations

## Scheduling and dispatch efficiency
The reconciler still runs under the existing serialized safety triggers but compares desired schedules with the actual cron jobs. Unchanged slots retain their job IDs and are not re-registered. It only creates, repairs or removes changed jobs. Disabled or drifted jobs are repaired only to the same configured schedule/gate state.

A service-only atomic begin-job RPC combines internal-budget entry and claim in one database transaction, retaining the existing budget, owner, generation, deadline, snapshot and per-owner sending checks. The worker uses it only when advertised by the pending response; old responses retain the original two-RPC path and missing owner metadata falls back to fully serial delivery. Every lane is awaited before the worker returns. Actual Kakao sends and uncertain outcomes are never automatically retried.

## Branch manager briefing (2026-11-20)
Actual `branch_manager` position receives the branch staff summary before the personal schedule and existing weather. System admin status alone does not enable branch summaries. The receiver and other branch managers are excluded from staff totals. Staff counts use active, same-unit people and undeleted, non-common schedules (including companion attendance); cancelled/postponed events do not count. Full-day leave, explicit `sales_empty_days`, and missing status are separate. Existing senior-position missing exclusions remain.

No total-event count, registered-person count, or activity-kind totals are added. Names are paired per line. Each body remains at most 200 UTF-16 units; overflow is split losslessly, all branch parts before personal parts. The same composition applies to first-connection briefings. Independent one-message connection tests retain their existing sample semantics.

Deploy `KAKAO_BRANCH_BRIEFING_PATCH.sql` as a new migration, then deploy both `hwarang-kakao` and `hwarang-kakao-welcome` with their shared dependencies. The patch adds persisted batch part metadata and service-only reservation wrappers; it does not enqueue messages or change connection preferences. Calendar links use `briefing=branch|personal` to select the appropriate view after normal login and authorization. Adding an explicit-empty choice to the event editor remains a proposal, not part of this change.

Validation: Node worker/message regressions; local PostgreSQL-compatible synthetic scope, status, order, deduplication, welcome and RPC-permission checks; Python calendar/settings regressions. Provider acceptance and device receipt must be reported separately from these tests.
