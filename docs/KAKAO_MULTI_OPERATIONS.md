# Multi-owner daily briefing operations

## Schedule semantics
Each connected owner chooses a minute of day and weekdays, in Asia/Seoul. Distinct minutes share one dispatch and one database-only backstop per minute. Twenty different times produce 40 cron jobs, not 40 Edge invocations. Identical times share a slot. The date of a 23:55 delivery remains the scheduled date if processing crosses midnight. Owner/date batch uniqueness prevents replay after changing the delivery time on the same day.

Weekdays are supported. Public holidays, substitute holidays and personal holiday exceptions are not automatically excluded.

## Capacity is not a delivery guarantee
Normal briefings split without content truncation into messages of at most 200 UTF-16 units. Twenty owners do not necessarily mean twenty messages. A one-part daily briefing for 20 owners is 620 messages over 31 days; distinct daily times need roughly 1,240 internal work units before extra parts/continuations. These internal units are not Supabase's billed invocation count.

The worker prepares up to 25 owners and processes up to 25 parts per tick, with bounded elapsed-time checks and continuation. Delivery has a ten-minute deadline. Slow provider or database responses can cause partial or missed delivery. The system does not silently retry uncertain provider outcomes. One owner's uncertain part stops that owner's remaining parts, without intentionally stopping others.

Local mocked load regression covers twenty owners with five parts each. A fast model completed 100 parts in four ticks; a slow 9.5-second provider model reached the deadline after 57 attempted parts. These are deterministic model results, not measured production performance or promises.

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
