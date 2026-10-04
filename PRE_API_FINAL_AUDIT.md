# HWARANG ACADEMY · PRE-API FINAL V1

## Finalized

### AI roles
- Customer AI: provider-agnostic structured contract; actual text model ID is bound at API connection time.
- Coach AI: provider-agnostic structured contract; GUIDE/COACH only.
- Formal Evaluator: commercial report contract with 18 competencies.
- Voice V1: **GPT-Live-1**.
- Python Case Engine remains source of truth for facts and persistent state.

### Billing / user allowance
- TEXT Customer + Coach + Formal Evaluator → **Training Credit**
- Voice → **separate Voice allowance**
- Users see percentage/status only, not API cost.
- Super admin sees raw usage and estimated API cost.
- Low/exhausted allowance shows the configured “박병선 팀장에게 이용량 추가 문의” route.

### Guardrails
- No normal-use requests-per-minute limit.
- Max advisor input: 2,400 characters.
- Max session turns: 40 (matches DEEP mode).
- Customer output: 800 tokens max.
- Coach output: 1,200 tokens max.
- Evaluator output: 6,000 tokens max.
- Voice session: warning at 25 minutes, hard cap at 30 minutes.
- One active AI simulator session per user.
- Request idempotency prevents Streamlit rerun/double-click duplicate billing.
- Training Credit and Voice allowance are atomically reserved before external calls.
- AI global Kill Switch remains fail-closed.
- AI session lock has a heartbeat for long text/voice sessions.

### Prompt / state safety
- Advisor text is passed as untrusted conversation input, not interpolated into system prompts.
- Customer/Coach/Evaluator output is JSON-schema validated.
- AI may propose conversational deltas, but Python validates/applies them.
- Ground-truth customer/insurance facts are never directly mutated by model output.
- Customer disclosures are checked against ground truth/customer beliefs before becoming state.
- Evaluator must provide all 18 competency results.
- Assessment snapshot hash enables evaluator-result reuse when the transcript is unchanged.
- GPT-Live receives backend-approved directives and is treated as the voice/interaction surface, not the fact source.

### PRE-API mock
- Deterministic MockAIAdapter is included.
- Customer → Python validator → evidence pipeline tested without network/API cost.
- Coach structured output tested.
- Evaluator 18-competency output tested.
- GPT-Live-1 session specification tested.

## Supabase migration
Run after existing 09:
- `10_Pre_API_Finalization.sql`

Do not rerun 01~09 merely to apply this change.

## Remaining only at actual API connection
1. Create/store `OPENAI_API_KEY`.
2. Verify current OpenAI API model availability/pricing.
3. Bind provider model IDs for CUSTOMER / COACH / EVALUATOR.
4. Calibrate real token cost → Training Credit conversion using initial observed usage.
5. Add the real OpenAI Responses adapter.
6. Add GPT-Live transport (WebRTC/WebSocket as selected at implementation time).
7. Turn AI runtime ON only after smoke tests.

No paid OpenAI request is made by this PRE-API package.
