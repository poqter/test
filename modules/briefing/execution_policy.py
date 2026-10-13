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
    web = 2 if group == "MARKET" else 4
    research = group == "MARKET" and os.getenv("BRIEFING_ENABLE_RESEARCH", "false").lower() == "true"
    analysis = (1 if group == "MARKET" else 2) + int(research)
    return {"web_requests_max": web, "analysis_requests_max": analysis,
            "output_tokens_max": web * 2000 + analysis * 12000,
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
