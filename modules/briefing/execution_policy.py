"""Bounded execution policy. No credentials, calls, or automatic lock release."""
import hashlib
import json
import math
import os
from dataclasses import asdict

PURPOSES = {"operation", "validation", "recovery"}

def execution_purpose(trigger, actor=None):
    if trigger == "retry": return "recovery"
    return "validation" if actor or trigger == "manual" else "operation"

def retry_guidance(details):
    status = details.get("http_status")
    if status in {400, 401, 403, 404, 422}:
        return {"retryable": False, "action": "인증·권한·모델·요청 설정을 수정한 뒤 재검증하세요."}
    if status == 429 or isinstance(status, int) and status >= 500:
        return {"retryable": True, "action": "일시 제한·공급자 장애입니다. 요청 상태를 확인한 뒤 허용된 복구를 사용하세요."}
    return {"retryable": None, "action": "요청·응답 상태를 확인하세요. 응답 불명확 잠금을 자동 해제하지 않습니다."}

def checkpoint_identity(as_of, profiles):
    # Version the collection/analysis contract independently from presentation fixes.
    config = {k: os.getenv(k, "") for k in ("BRIEFING_DISCOVERY_MODEL", "BRIEFING_ROUTINE_MODEL",
        "BRIEFING_DIRECT_SOURCES_JSON", "BRIEFING_DEFAULT_NEWS_FEEDS", "BRIEFING_ENABLE_RESEARCH")}
    from pathlib import Path
    root = Path(__file__).parent
    contracts = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
        'phase_b.py', 'phase_c.py', 'gates.py', 'profile_rules.py', 'openai_analysis.py', 'openai_discovery.py', 'direct_sources.py', 'feed_catalog.py')}
    return digest({"contract": "briefing-input-v1", "code": contracts, "as_of": as_of.isoformat(),
                   "profiles": sorted(profiles), "config": config})

def digest(value):
    from .checkpoints import json_value
    return hashlib.sha256(json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

def analysis_identity(profile, events, model, prompt, schema):
    return digest({"profile": profile, "events": [asdict(e) for e in events],
                   "model": model, "prompt": prompt, "schema": schema})

def request_plan(group):
    # Initial primary lanes; recovery reserves remain subject to the shared DB cap.
    web = 4 if group == "DAILY" else 2
    research = group == "MARKET" and os.getenv("BRIEFING_ENABLE_RESEARCH", "false").lower() == "true"
    analysis = (2 if group == "DAILY" else 1) + int(research)
    return {"web_requests_max": web, "analysis_requests_max": analysis,
            "output_tokens_max": web * 2000 + analysis * ANALYSIS_OUTPUT_TOKENS,
            "note": "직접 피드·저장 결과로 실제 요청은 줄어듭니다. 입력 토큰과 실제 검색 결과는 실행 전 확정할 수 없어 총비용 상한은 아닙니다."}

def budget_notice(summary, period):
    raw = os.getenv("BRIEFING_" + period.upper() + "_BUDGET_USD", "").strip()
    if not raw: return {"state": "unset", "message": "금액 예산 미설정 · 기존 요청 상한 유지"}
    try: limit = float(raw)
    except ValueError: return {"state": "invalid", "message": "금액 예산 설정을 확인하세요."}
    if not math.isfinite(limit) or limit <= 0: return {"state": "invalid", "message": "금액 예산은 양의 유한값이어야 합니다."}
    known = summary.get("accounted_known_usd", 0)
    ratio = known / limit
    state = "exceeded" if ratio >= 1 else "near" if ratio >= .8 else "normal"
    return {"state": state, "ratio": ratio, "limit_usd": limit,
            "message": "알림용 예산 · 확정 청구와 미확인 요청을 함께 확인하세요. 호출 차단은 기존 상한을 따릅니다."}


# Approved operational ceilings: normal output and one token-exhaustion recovery.
ANALYSIS_OUTPUT_TOKENS = 24000
ANALYSIS_RECOVERY_OUTPUT_TOKENS = 48000


def token_exhausted_response(record):
    if not isinstance(record, dict): return False
    if (record.get('provider_status') != 'incomplete' or not record.get('usage_logged')
            or not record.get('usage_available') or record.get('charge_uncertain')):return False
    reason=(record.get('incomplete_details') or {}).get('reason')
    if reason:return reason == 'max_output_tokens'
    # Legacy checkpoints did not save incomplete_details; require exact ceiling evidence.
    limit=record.get('requested_max_output_tokens')
    used=(record.get('usage') or {}).get('output_tokens')
    return isinstance(limit,int) and limit>0 and isinstance(used,int) and used>=limit


def bounded_analysis_recovery(saved, code, cached, *, allowed):
    if not token_exhausted_response(cached):return None
    if not allowed:raise RuntimeError('출력 한도 복구에는 허용된 API 요청이 필요합니다.')
    if code in saved.get('token_recovery_started',[]):
        raise RuntimeError('출력 한도 확대 복구는 한 번만 허용됩니다.')
    saved.setdefault('token_recovery_started',[]).append(code)
    saved.setdefault('incomplete_analysis_archive',{})[code]=cached
    saved.setdefault('analysis_responses',{}).pop(code,None)
    return ANALYSIS_RECOVERY_OUTPUT_TOKENS
