# Independent owner-requested self-test

This operator-only path is separate from the daily subscription worker. It does not insert daily batches/jobs, alter preferences, change cron, or refresh shared credentials.

- Two individually approved request slots per owner, database uniqueness enforced; no reset or retry on uncertainty. Slot 2 requires fresh cached weather and never consumes another weather request.
- One 200 UTF-16 message maximum, clearly labelled as a test. Longer manifests fail before sending.
- A random 256-bit ticket, stored only as its hash, expires within five minutes. Claim changes queued to processing atomically; concurrent callers cannot reuse it.
- Live active-owner, consent, generation, current region/schedule snapshot and free-cost gate are checked before claim and immediately before send.
- Only service_role can access the test ledger and RPCs. The Edge function authenticates the single-use ticket, not platform JWT. No credential is returned to callers or logged.
- Test invocation consumes one existing internal function-budget unit. Weather uses the existing bounded shared cache. Preserve at least one source attempt and adequate function budget for the scheduled morning delivery.
- Test message cap is independently one per request (two individually approved slots per owner); it is not counted in the normal monthly_message_budget. With a normal cap of 10 and one authorized owner, total potential messages are at most 12.
- No automatic trigger, scheduler or request is installed by the migration. An explicitly authorized operator enqueues one ticket to hwarang-kakao-test using pg_net; only request ID/status should be returned, never the ticket.
- accepted means Kakao API accepted, not device delivery/read. A lost response or recording error is uncertain and must not be resent.

Validation: Node mocked-worker suite, PostgreSQL17 live synthetic checks for tickets/claims/terminal state/ACL and normal state invariance, plus parallel claim race (exactly one winner). All production users and credentials are excluded from fixtures.
