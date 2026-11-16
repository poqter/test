# First connected-account briefing

## User flow
OAuth alone does not send a message. The signed-in owner must finish the connection confirmation, save a valid weather region and enable the recurring briefing. The settings screen explains that this sends today's briefing once, followed by the chosen weekdays/time starting the following day. Leaving recurring delivery off sends nothing.

The first briefing uses the same content and format as normal delivery, including multipart content rather than silent truncation. A no-event day still has an explicit first-day summary; subsequent empty-day behavior follows the saved preference.

## Safety requirements
- First-delivery eligibility is once per workspace owner, not once per OAuth connection. Reconnecting must not reset it.
- Existing connection, batch and test owners are explicitly excluded during migration. Existing calendar members who have never connected Kakao remain eligible.
- Read-only settings views never enqueue messages. Only authenticated confirmation/settings writes can complete readiness.
- First-day reservation and normal owner/date uniqueness are coordinated atomically. Existing normal delivery prevents an additional first briefing; a reserved first day cannot later produce a normal duplicate.
- Waiting-for-setup can follow a replacement connection; once queued, a generation change invalidates rather than retries the request.
- Each delivery ticket is random, short-lived and usable once. Each part is claimed once and validated immediately before provider transmission.
- Continuation handles only never-attempted reserved parts. Sending/uncertain parts are never automatically retried. The deadline is bounded and must not send yesterday's queued briefing after midnight.
- Partial acceptance and unknown outcomes are not reported as complete success. The UI does not offer an automatic first-delivery retry.
- First delivery consumes normal work, normal message and normal weather allocation, not the independent test allocation. It cannot evade the shared free-capacity safeguards.

Deployment must preserve current users' preferences and scheduled jobs, and must not itself enqueue a message. Any live verification needs separate recipient-specific sending authorization.
