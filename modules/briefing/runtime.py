from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import hashlib
import json
from typing import Any, Iterable
import re
from zoneinfo import ZoneInfo

from .direct_sources import load_direct_source_specs_from_env
from .diagnostics import ENGINE_VERSION, DIAGNOSTIC_SCHEMA, build_info
from .models import PhaseBResult, PhaseCResult, ProfileEventAnalysis, SharedEventCandidate, SourceCandidate
from .phase_b import run_phase_b
from .phase_c import run_phase_c
from .repository import BriefingRepository, BriefingRepositoryError
from .public_body import customer_body
from .market_metrics import collect_metrics
from .research import build_research


KST = ZoneInfo("Asia/Seoul")
PROFILE_LABELS = {
    "INSURANCE": "보험업계 브리핑",
    "MARKET": "경제·금융 브리핑",
    "NEWS": "종합뉴스 브리핑",
}


@dataclass(slots=True)
class GeneratedProfileResult:
    profile_code: str
    briefing_id: str
    revision_id: str
    snapshot_id: str
    publication_status: str
    validation_status: str
    coverage_status: str
    core_count: int
    light_count: int


@dataclass(slots=True)
class BriefingGenerationResult:
    generated_at: str
    profiles: list[GeneratedProfileResult]
    search_actions: int
    candidate_count: int
    event_count: int
    diagnostics: dict[str, Any] | None = None
    engine_version: str = ENGINE_VERSION
    schema_version: str = DIAGNOSTIC_SCHEMA
    status: str = "completed"


class BriefingRunError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None


def _source_payload(snapshot_id: str, row: SourceCandidate) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_code": row.source_code,
        "source_family_code": row.source_family_code,
        "endpoint_role": row.endpoint_role,
        "source_kind": row.source_kind,
        "source_tier": row.source_tier,
        "collector_provider": row.collector_provider,
        "source_name": row.source_name or row.publisher_name or "Source",
        "publisher_name": row.publisher_name,
        "publisher_domain": row.publisher_domain,
        "title": row.title,
        "url": row.url,
        "canonical_url": row.canonical_url,
        "published_at": _iso(row.published_at),
        "retrieved_at": _iso(row.retrieved_at) or datetime.now(timezone.utc).isoformat(),
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
        "access_status": "ok",
        "content_fingerprint": row.content_fingerprint,
        "untrusted_external": True,
    }


def _coverage_status(phase_b: PhaseBResult, profile_code: str, routed_event_count: int) -> str:
    dated = [c for c in phase_b.candidates if profile_code in c.routed_profiles and c.freshness_tier in {"core_window", "light_window"}]
    lanes = [row for row in phase_b.discovery_lanes if row.profile_code == profile_code]
    owned = [c for c in dated if c.metadata.get("profile_hint") == profile_code
             or profile_code in (c.metadata.get("profile_hints") or [])
             or any(c in lane.candidates for lane in lanes)]
    direct = [h for h in phase_b.source_health.values() if profile_code in h.get("profiles", [])]
    successful = any(l.search_performed for l in lanes) or any(h.get("status") in {"ok", "empty_valid"} for h in direct)
    if routed_event_count >= 1 and successful:
        return "healthy"
    return "degraded" if owned else "insufficient"


def _fast_brief(profile_code: str, rows: list[ProfileEventAnalysis]) -> dict[str, Any]:
    visible = [r for r in rows if r.selection_tier in {"core", "light_digest"}]
    visible.sort(key=lambda r: (0 if r.selection_tier == "core" else 1, -r.importance_score))
    top = visible[:5]
    categories = list(dict.fromkeys(r.category for r in visible if r.category))
    one_sentence = (
        f"오늘은 {'·'.join(categories)} 영역에서 핵심 변화 {sum(r.selection_tier == 'core' for r in visible)}건과 관련 소식 {sum(r.selection_tier == 'light_digest' for r in visible)}건을 확인합니다."
        if visible else "현재 검증 가능한 브리핑 이슈가 충분하지 않습니다."
    )
    return {
        "profile_code": profile_code,
        "core_count": sum(r.selection_tier == "core" for r in rows),
        "light_count": sum(r.selection_tier == "light_digest" for r in rows),
        "items": [{"title": r.title, "summary": r.summary, "selection_tier": r.selection_tier} for r in top],
        "remember_one_sentence": one_sentence,
    }


def _today_actions(rows: list[ProfileEventAnalysis]) -> dict[str, Any]:
    labels = {"review_now": "지금 확인", "reference_today": "오늘 참고", "watch": "지켜보기"}
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in labels}
    ordered = sorted(rows, key=lambda r: (0 if r.action_state == "review_now" else 1 if r.action_state == "reference_today" else 2, -r.importance_score))
    remaining = 3
    for row in ordered:
        if row.selection_tier == "excluded":
            continue
        if remaining == 0:
            break
        state = row.action_state if row.action_state in grouped else "watch"
        grouped[state].append({
            "event_key": row.event_key,
            "title": row.title,
            "summary": row.impact_summary or row.summary,
            "label": labels[state],
        })
        remaining -= 1
    return grouped


def _content_payload(profile_code: str, rows: list[ProfileEventAnalysis], phase_b: PhaseBResult, coverage_status: str) -> dict[str, Any]:
    selected = [r for r in rows if r.selection_tier != "excluded"]
    selected.sort(key=lambda r: (0 if r.selection_tier == "core" else 1, -r.importance_score))
    representative_key = next((r.event_key for r in selected if r.selection_tier == "core"), None)
    event_map = _event_lookup(phase_b.events)
    return {
        "profile_code": profile_code,
        "profile_label": PROFILE_LABELS.get(profile_code, profile_code),
        "as_of": phase_b.as_of.isoformat(),
        "coverage_status": coverage_status,
        "core_count": sum(r.selection_tier == "core" for r in rows),
        "light_count": sum(r.selection_tier == "light_digest" for r in rows),
        "editorial_version": 3,
        "source_links": [],
        "issues": [
            {
                "event_key": r.event_key,
                "selection_tier": r.selection_tier,
                "headline_sufficient": r.profile_payload.get("headline_sufficient") is True,
                "event_date": r.profile_payload.get("event_date") or "",
                "editorial_kind": r.profile_payload.get("editorial_kind"),
                "importance_score": r.importance_score,
                "category": r.category,
                "issue_status": r.issue_status,
                "title": r.title,
                "summary": r.summary,
                "why_important": r.why_important,
                "impact_summary": r.impact_summary,
                "action_state": r.action_state,
                "communication_state": r.communication_state,
                "customer_article_eligible": (
                    profile_code == 'INSURANCE' and r.validation_status == 'ok'
                    and r.communication_state == 'not_applicable'
                    and r.category in {'제도·규제','상품·보험료','보험금·보상','세제·재무','소비자·사회이슈'}
                    and r.profile_payload.get('confidence') in {'high', 'medium'}
                ),
                "audience_segments": r.audience_segments,
                "representative": r.event_key == representative_key,
                "sources": [{"title": c.title, "source_name": c.source_name, "url": c.canonical_url or c.url, "published_at": _iso(c.published_at)} for c in event_map[r.event_key].candidates if c.published_at],
            }
            for r in selected
        ],
    }


def _extra_source_links(profile_code, selected_keys, phase_b):
    """Internal original-reading links; these are never counted as AI summaries."""
    links = []
    seen = set()
    for event in sorted(phase_b.events, key=lambda e: e.last_seen_at or phase_b.as_of, reverse=True):
        if profile_code not in event.routed_profiles or event.event_key in selected_keys:
            continue
        for source in event.candidates:
            from .normalize import is_safe_url
            url = source.canonical_url or source.url
            if source.source_kind != 'news' or not source.published_at or not source.title or not is_safe_url(url) or url in seen:
                continue
            seen.add(url)
            links.append({'title': source.title, 'url': url, 'source_name': source.publisher_name or source.source_name,
                          'published_at': _iso(source.published_at), 'event_key': event.event_key})
            break
        if len(links) >= 8:
            break
    return links


def _event_lookup(events: Iterable[SharedEventCandidate]) -> dict[str, SharedEventCandidate]:
    return {event.event_key: event for event in events}


def _overall_validation(rows: list[ProfileEventAnalysis], coverage_status: str) -> str:
    if coverage_status != "healthy":
        return "required"
    visible = [r for r in rows if r.selection_tier != "excluded"]
    if any(r.validation_status != "ok" for r in visible):
        return "required"
    return "ok"


def body_quality_ready(body: dict[str, Any]) -> bool:
    """Apply the same minimum to new and previously saved publication candidates."""
    issues = body.get("issues") or []
    if not issues:
        return False
    from .normalize import is_safe_url
    if content_version := body.get('editorial_version'):
        if content_version >= 3:
            code=body.get('profile_code')
            main=[r for r in issues if r.get('selection_tier')=='core']
            if len(main) < {'MARKET':3,'NEWS':3,'INSURANCE':2}.get(code,1):return False
            if code in {'MARKET','NEWS'} and len({r.get('category') for r in main if r.get('category')})<2:return False
            if code=='INSURANCE' and not any(r.get('editorial_kind')=='development' and r.get('category') in {'제도·규제','상품·보험료','보험금·보상','영업·채널','소비자·사회이슈'} for r in main):return False
    for issue in issues:
        if not str(issue.get("title") or "").strip() or not str(issue.get("summary") or "").strip():
            return False
        if not any(source.get("published_at") and is_safe_url(str(source.get("url") or ""))
                   for source in issue.get("sources") or []):
            return False
    return True


def _display_coverage_status(profile_code: str, rows: list[ProfileEventAnalysis], phase_b: PhaseBResult, collection_status: str) -> str:
    """Search success alone cannot certify the articles that survived analysis."""
    if not any(r.selection_tier != "excluded" for r in rows):
        return "insufficient"
    if collection_status != "healthy":
        return collection_status
    body = _content_payload(profile_code, rows, phase_b, collection_status)
    return "healthy" if body_quality_ready(body) else "degraded"


def _revision_type(revision_no: int) -> str:
    return "initial" if revision_no == 1 else "regeneration"


def _job_key(profile_code: str, date_text: str, briefing_type: str) -> str:
    return f"{date_text}:{profile_code}:{briefing_type}"


def _persist_profile(
    repo: BriefingRepository,
    *,
    profile_code: str,
    phase_b: PhaseBResult,
    phase_c: PhaseCResult,
    actor_user_id: str | None,
    job_id: str,
    run_mode: str,
    briefing_type: str = "MORNING",
    market_context: dict | None = None,
) -> GeneratedProfileResult:
    now = datetime.now(timezone.utc)
    kst_date = phase_b.as_of.astimezone(KST).date()
    rows = phase_c.profile_rows(profile_code)
    from .editorial import remove_unchanged_repeats
    from datetime import timedelta
    previous = repo.bundle_for_date(profile_code, kst_date-timedelta(days=1))
    if isinstance(previous,dict):
        remove_unchanged_repeats(rows, (previous['snapshot'].get('content_payload') or {}).get('issues', []))
        from .phase_c import _apply_caps
        _apply_caps(rows, profile_code)
    routed_events = [event for event in phase_b.events if profile_code in event.routed_profiles]
    coverage_status = _coverage_status(phase_b, profile_code, len(routed_events))
    coverage_status = _display_coverage_status(profile_code, rows, phase_b, coverage_status)
    validation_status = _overall_validation(rows, coverage_status)

    briefing = repo.get_or_create_briefing(profile_code, kst_date, briefing_type)
    revision_no = repo.next_revision_no(str(briefing["id"]))
    revision = repo.create_revision({
        "briefing_id": briefing["id"],
        "revision_no": revision_no,
        "revision_type": _revision_type(revision_no),
        "publication_status": "draft",
        "validation_status": validation_status,
        "coverage_status": coverage_status,
        "external_share_allowed": False,
        "external_qa_passed": False,
        "data_as_of": phase_b.as_of.isoformat(),
        "generated_at": now.isoformat(),
        "created_by": actor_user_id,
        "change_summary": "일일 브리핑·증권사 공개 리서치·동일 고객 본문",
        "version_trace": {
            "engine_version": ENGINE_VERSION,
            "profile_config_version": ENGINE_VERSION,
            "prompt_version": "phase_c_v2",
            "source_config_version": "phase_b_v4",
            "run_mode": run_mode,
        },
    })

    fast_brief = _fast_brief(profile_code, rows)
    today_action = _today_actions(rows)
    content = _content_payload(profile_code, rows, phase_b, coverage_status)
    if profile_code == "MARKET": content.update(market_context or {})
    from .editorial import verified_extras
    content.update(verified_extras(rows, phase_b, profile_code))
    external = customer_body(content)
    public_ready = body_quality_ready(external)
    if profile_code != "INSURANCE": public_ready = public_ready and len(external["issues"]) == len(content["issues"])
    internal_ready = body_quality_ready(content)
    if profile_code == "MARKET":
        public_ready = public_ready and bool(content.get('market_flow'))
        internal_ready = internal_ready and bool(content.get('market_flow'))
    if not internal_ready: validation_status = "required"
    if validation_status != revision.get("validation_status"):
        repo.update_revision(str(revision["id"]), {"validation_status": validation_status})
    # Persist the eligible analysis pool BEFORE display caps for the later customer edition.
    content["eligible_analysis_pool"] = [asdict(r) for r in phase_c.eligible_analyses if r.profile_code == profile_code]
    content_hash = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    snapshot = repo.create_snapshot({
        "revision_id": revision["id"],
        "content_hash": content_hash,
        "content_payload": content,
        "external_content_payload": external,
        "fast_brief_payload": fast_brief,
        "today_action_payload": today_action,
        "qa_payload": {
            "validation_status": validation_status,
            "public_body_ready": public_ready,
            "internal_body_ready": internal_ready,
            "coverage_status": coverage_status,
            "excluded_counts": phase_b.excluded_counts,
            "collection_diagnostics": phase_b.diagnostics,
            "source_health": phase_b.source_health,
            "editorial_audit": [{"event_key":r.event_key,"title":r.title,"tier":r.selection_tier,
                "score":r.importance_score,"validation":r.validation_status,**r.profile_payload} for r in rows],
            "selection_diagnostics": {
                "routed_events": len(routed_events),
                "analyzed_events": sum(not r.profile_payload.get('analysis_missing') for r in rows),
                "analysis_missing": sum(bool(r.profile_payload.get('analysis_missing')) for r in rows),
                "eligible_events": sum(r.profile_code == profile_code for r in phase_c.eligible_analyses),
                "displayed_events": len(content['issues']),
                "original_links": len(content.get('source_links') or []),
            },
        },
    })
    repo.checkpoint(job_id, "snapshot_created", {"snapshot_id": snapshot["id"]})

    event_map = _event_lookup(routed_events)
    db_events: dict[str, dict[str, Any]] = {}
    for event in routed_events:
        matching = [r for r in rows if r.event_key == event.event_key]
        primary_category = matching[0].category if matching else None
        event_row = repo.upsert_event({
            "event_key": event.event_key,
            "canonical_title": event.canonical_title,
            "primary_category": primary_category,
            "event_status": "active",
            "first_seen_at": _iso(event.first_seen_at) or phase_b.as_of.isoformat(),
            "last_seen_at": _iso(event.last_seen_at) or phase_b.as_of.isoformat(),
            "metadata": {"routed_profiles": sorted(event.routed_profiles)},
        })
        db_events[event.event_key] = event_row
        # Timeline updates are append-only but regeneration alone must not create
        # a fake development.  Derive the key from the observed source state so
        # an unchanged Event is naturally de-duplicated by (event_id, update_key).
        update_basis = "|".join(sorted(
            (candidate.content_fingerprint or candidate.canonical_url or candidate.url)
            for candidate in event.candidates
            if (candidate.content_fingerprint or candidate.canonical_url or candidate.url)
        )) or event.event_key
        update_key = hashlib.sha256(update_basis.encode("utf-8")).hexdigest()[:40]
        repo.ensure_event_update({
            "event_id": event_row["id"],
            "revision_id": revision["id"],
            "update_key": update_key,
            "update_type": "initial" if revision_no == 1 else "development",
            "evidence_status": matching[0].evidence_status if matching else "reported",
            "title": matching[0].title if matching else event.canonical_title,
            "change_summary": (matching[0].summary if matching else event.canonical_title)[:2000],
            "observed_at": phase_b.as_of.isoformat(),
            "details": {"profile_code": profile_code},
        })

    # Snapshot Sources are immutable. Keep one row per URL and later relate each
    # issue only to the sources that belonged to its Shared Event.
    candidate_by_url: dict[str, SourceCandidate] = {}
    event_urls: dict[str, set[str]] = {}
    for event in routed_events:
        urls: set[str] = set()
        for candidate in event.candidates:
            url = candidate.url
            if url:
                candidate_by_url.setdefault(url, candidate)
                urls.add(url)
        event_urls[event.event_key] = urls
    source_rows = repo.insert_sources([_source_payload(str(snapshot["id"]), row) for row in candidate_by_url.values()])
    source_id_by_url = {str(row.get("url")): str(row.get("id")) for row in source_rows if row.get("url") and row.get("id")}

    ordered_rows = sorted(rows, key=lambda r: (0 if r.selection_tier == "core" else 1 if r.selection_tier == "light_digest" else 2, -r.importance_score))
    issue_payloads: list[dict[str, Any]] = []
    for sort_order, row in enumerate(ordered_rows, start=1):
        event_row = db_events.get(row.event_key)
        issue_payloads.append({
            "snapshot_id": snapshot["id"],
            "event_id": event_row.get("id") if event_row else None,
            "issue_key": f"{profile_code}:{row.event_key}",
            "sort_order": sort_order,
            "category": row.category,
            "tags": [],
            "importance_score": row.importance_score,
            "importance_label": None,
            "issue_status": row.issue_status,
            "selection_tier": row.selection_tier,
            "evidence_status": row.evidence_status,
            "title": row.title,
            "summary": row.summary,
            "fact_payload": {"why_important": row.why_important},
            "analysis_payload": {"impact_summary": row.impact_summary},
            "profile_payload": row.profile_payload,
        })
    db_issues = repo.insert_issues(issue_payloads)
    issue_by_key = {str(row.get("issue_key")): row for row in db_issues}

    action_payloads: list[dict[str, Any]] = []
    issue_source_links: list[dict[str, Any]] = []
    for sort_order, row in enumerate(ordered_rows, start=1):
        issue = issue_by_key.get(f"{profile_code}:{row.event_key}")
        if not issue:
            continue
        for url in event_urls.get(row.event_key, set()):
            source_id = source_id_by_url.get(url)
            if source_id:
                issue_source_links.append({"issue_id": issue["id"], "source_id": source_id, "relation_type": "supporting"})
        if row.selection_tier == "excluded":
            continue
        event_row = db_events.get(row.event_key)
        action_payloads.append({
            "snapshot_id": snapshot["id"],
            "issue_id": issue["id"],
            "event_id": event_row.get("id") if event_row else None,
            "action_key": f"{profile_code}:{row.event_key}:primary",
            "action_scope": "issue",
            "action_state": row.action_state,
            "communication_state": row.communication_state,
            "title": row.title,
            "summary": row.impact_summary or row.summary or "확인 필요",
            "audience_segments": row.audience_segments,
            "conversation_payload": row.conversation_payload,
            "workspace_actions": row.workspace_actions,
            "academy_practice_hint": {},
            "sort_order": sort_order,
        })
    repo.link_issue_sources(issue_source_links)
    repo.insert_actions(action_payloads)

    # Shadow/manual modes never auto-publish. Auto mode is allowed only after
    # validation and coverage gates pass. Initial deployment remains shadow.
    publication_status = "draft"
    if run_mode == "auto" and validation_status == "ok" and coverage_status == "healthy" and repo.operating_policy().get('automatic_publication_enabled'):
        repo.publish_revision(str(briefing["id"]), str(revision["id"]), actor_user_id=None)
        publication_status = "published"
        repo.checkpoint(job_id, "published", {"revision_id": revision["id"]})

    return GeneratedProfileResult(
        profile_code=profile_code,
        briefing_id=str(briefing["id"]),
        revision_id=str(revision["id"]),
        snapshot_id=str(snapshot["id"]),
        publication_status=publication_status,
        validation_status=validation_status,
        coverage_status=coverage_status,
        core_count=sum(r.selection_tier == "core" for r in rows),
        light_count=sum(r.selection_tier == "light_digest" for r in rows),
    )


def generate_and_store_briefings(
    *,
    actor_user_id: str | None = None,
    profile_codes: tuple[str, ...] = ("INSURANCE", "MARKET", "NEWS"),
    repository: BriefingRepository | None = None,
    force_shadow: bool = False,
    as_of: datetime | None = None,
    checkpoint: dict | None = None,
    save_checkpoint=None,
    before_request=None,
    trigger_type: str = "manual",
    allow_partial_market: bool = False,
    saved_material_only: bool = False,
) -> BriefingGenerationResult:
    """Run one shared Phase B discovery, one Phase C batch per routed profile,
    then persist immutable V1.6 snapshots for the requested profiles.

    The initial DB seed is run_mode=shadow, so this function normally creates
    manager-visible drafts.  Publication remains a separate explicit action.
    """
    repo = repository or BriefingRepository()
    profiles = {str(row.get("profile_code")): row for row in repo.profiles()}
    if not repo.ai_generation_enabled():
        raise BriefingRunError('플랫폼 AI 서비스가 꺼져 있습니다. 유료 생성은 시작하지 않았습니다.')
    requested = tuple(code for code in profile_codes if code in profiles and bool(profiles[code].get("is_enabled", True)))
    if not requested:
        raise BriefingRunError("활성화된 브리핑 Profile이 없습니다")

    as_of = as_of or datetime.now(timezone.utc)
    saved = checkpoint if checkpoint is not None else {}
    from .checkpoints import encode, phase_b as restore_b, phase_c as restore_c
    from .openai_discovery import OpenAIWebDiscoveryClient
    from .openai_analysis import OpenAIAnalysisClient
    def save():
        if save_checkpoint: save_checkpoint(saved)
    from .execution_policy import checkpoint_identity, execution_purpose
    identity = checkpoint_identity(as_of, requested)
    if saved.get('input_identity') and saved['input_identity'] != identity:
        raise BriefingRunError('저장본의 수집 마감·영역·모델·설정이 달라 재사용할 수 없습니다. 기존 저장본을 보존했습니다.')
    if saved.get('phase_b') and saved['phase_b'].get('as_of') != as_of.isoformat():
        raise BriefingRunError('저장된 수집 결과의 마감 시각이 다릅니다. 추가 호출 없이 중단했습니다.')
    saved['input_identity'] = identity
    purpose = execution_purpose(trigger_type, actor_user_id)
    saved['execution_purpose'] = purpose
    date_text = as_of.astimezone(KST).date().isoformat()
    jobs: dict[str, dict[str, Any]] = {}
    progress: dict[str, Any] = {"stage": "creating_jobs", "requested_profiles": list(requested),
                                "discovery_requests": [], "analysis_requests": [],
                                "reused_analysis_profiles": [], "build": build_info()}

    def record_usage(record: dict[str, Any], *, discovery: bool) -> None:
        collection = "discovery_requests" if discovery else "analysis_requests"
        from .execution_policy import retry_guidance
        if record.get('status') == 'request_failed':
            record['recovery_guidance'] = retry_guidance(record)
        progress[collection].append(record)
        code = record["profile_code"]
        owner = code if code in jobs else next(iter(jobs))
        usage = record.get("usage") or {}
        search_status = record.get("search_status_counts") or {}
        uncertain_search = discovery and any(search_status.get(state, 0) for state in ("nonfinal", "unknown"))
        record["usage_logged"] = False
        degraded = bool(discovery and record.get('direct_feed_fallback') and record.get('status') == 'completed'
                        and record.get('usage_available'))
        record["charge_uncertain"] = not bool(record.get("usage_available")) or uncertain_search
        repo.log_api_usage({
            "job_id": jobs[owner]["id"], "profile_code": owner, "provider": "openai",
            "operation": f"web_discovery:{record['lane_code']}" if discovery else record.get("operation") or "phase_c_analysis",
            **{field: usage.get(field) for field in ("model_name", "service_tier")},
            **{field: int(usage.get(field) or 0) for field in ("input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "web_tool_calls", "search_actions", "search_retry_count", "verification_search_actions")},
            "metadata": {"engine_version": ENGINE_VERSION, "execution_purpose": purpose, "request_no": record.get("request_no"),
                         "response_id": record.get("response_id"), "response_status": record.get("status"),
                         "request_failure": {k:record.get(k) for k in ('failure_message','http_status','error_class','provider_error_code','provider_error_type')},
                         "retry_used": bool(record.get("retry")), "lane_profile_code": code,
                         "usage_available": bool(record.get("usage_available")),
                         "charge_uncertain": not bool(record.get("usage_available")) or uncertain_search,
                         "search_status_counts": search_status if discovery else None,
                         "search_billing_uncertain": uncertain_search,
                         "requested_max_tool_calls": record.get("requested_max_tool_calls"),
                         "recovery_guidance": record.get("recovery_guidance")},
        })
        if discovery and before_request:
            repo._request("POST", "/rest/v1/rpc/hwarang_observe_briefing_search", json={"p_date":date_text,"p_actions":int(usage.get("search_actions") or 0)})
        record["usage_logged"] = True
        if record['charge_uncertain'] and not degraded:
            saved['charge_uncertain']=True
            saved['last_request_failure']={k:record.get(k) for k in ('profile_code','status','failure_message','http_status','error_class','provider_error_code','provider_error_type','response_id')}
            save()
            repo.update_job(str(jobs[owner]['id']), {'metadata': {
                'engine_version': ENGINE_VERSION, 'shared_run': True, 'partial_diagnostics': progress}})
            message = record.get('failure_message') or 'API 사용량 또는 검색 완료 상태가 확인되지 않았습니다.'
            raise BriefingRunError(message + ' 추가 유료 호출을 중단했습니다.', {'request_failure': saved['last_request_failure']})
        if degraded:
            saved['search_degraded_to_direct'] = True
        if record.get("usage_available") and (not record["charge_uncertain"] or degraded):
            if not discovery and record.get("output_text_sample"):
                saved.setdefault("analysis_responses", {})[code] = dict(record)
            saved.pop("pending_request", None); save()
        repo.update_job(str(jobs[owner]["id"]), {"metadata": {
            "engine_version": ENGINE_VERSION, "shared_run": True, "partial_diagnostics": progress}})
    try:
        if not progress["build"]["code_matches_release"]:
            raise BriefingRunError("배포 파일이 수정 패키지와 일치하지 않습니다. 유료 API 실행을 중단했습니다.")
        for code in requested:
            key = _job_key(code, date_text, "MORNING")
            attempt = repo.next_attempt_no(key)
            jobs[code] = repo.create_job({
                "profile_code": code,
                "briefing_date": date_text,
                "briefing_type": "MORNING",
                "job_key": key,
                "attempt_no": attempt,
                "trigger_type": trigger_type,
                "job_status": "collecting",
                "started_at": as_of.isoformat(),
                "metadata": {"engine_version": ENGINE_VERSION, "shared_run": True},
            })
        progress["stage"] = "web_discovery"
        if saved.get("phase_b"):
            phase_b = restore_b(saved["phase_b"])
        else:
            discovery_client = OpenAIWebDiscoveryClient() if before_request else None
            if discovery_client: discovery_client.before_request = before_request
            previous = restore_b(saved["partial_b"]).discovery_lanes if saved.get("partial_b") else []
            def lane_done(lanes):
                saved["partial_b"] = encode(PhaseBResult(as_of, [], [], lanes, {})); save()
            phase_b = run_phase_b(as_of=as_of, direct_sources=load_direct_source_specs_from_env(),
                discovery_client=discovery_client, profile_codes=requested,
                previous_lanes=previous, on_lane_complete=lane_done if save_checkpoint else None,
                retry_missing_search=False, supplement_only=True,
                include_research=os.getenv("BRIEFING_ENABLE_RESEARCH", "false").lower()=="true",
                on_discovery_response=lambda record: record_usage(record, discovery=True),
                direct_checkpoint=saved, on_direct_complete=save,
                saved_material_only=saved_material_only, seed_candidates=saved.get("seed_candidates"))
            saved["phase_b"] = encode(phase_b); save()
        progress["phase_b"] = {"collection": phase_b.diagnostics, "source_health": phase_b.source_health,
                               "excluded_counts": phase_b.excluded_counts,
                               "candidate_count": len(phase_b.candidates), "event_count": len(phase_b.events)}
        for code, job in jobs.items():
            repo.checkpoint(str(job["id"]), "direct_collection_complete", {"candidate_count": len(phase_b.candidates)})
            repo.checkpoint(str(job["id"]), "web_discovery_complete", {
                "search_actions": sum(l.usage.search_actions for l in phase_b.discovery_lanes if l.profile_code == code),
            })
            repo.update_job(str(job["id"]), {"job_status": "analyzing"})

        # Record Discovery usage against the lane's owning profile only; this
        # prevents the shared four Search Actions from being double-counted.
        for lane in (() if progress["discovery_requests"] or save_checkpoint else phase_b.discovery_lanes):
            job = jobs.get(lane.profile_code)
            if not job:
                continue
            usage = lane.usage
            repo.log_api_usage({
                "job_id": job["id"],
                "profile_code": lane.profile_code,
                "provider": "openai",
                "operation": f"web_discovery:{lane.lane_code}",
                "model_name": usage.model_name,
                "service_tier": usage.service_tier,
                "input_tokens": usage.input_tokens,
                "cached_input_tokens": usage.cached_input_tokens,
                "output_tokens": usage.output_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "web_tool_calls": usage.web_tool_calls,
                "search_actions": usage.search_actions,
                "search_retry_count": usage.search_retry_count,
                "verification_search_actions": usage.verification_search_actions,
                "metadata": {"execution_purpose": purpose, "retry_used": lane.retry_used, "response_id": lane.raw_response_id},
            })

        progress["stage"] = "analysis"
        completed_c = saved.setdefault("phase_c_by_profile", {})
        for code in requested:
            if code not in completed_c:
                client = OpenAIAnalysisClient(on_response=lambda record: record_usage(record, discovery=False))
                client.before_request = before_request
                from datetime import timedelta
                if code not in saved.setdefault('previous_news',{}):
                    previous=repo.bundle_for_date(code,as_of.astimezone(KST).date()-timedelta(days=1))
                    saved['previous_news'][code]=[{k:r.get(k) for k in ('title','summary','event_key')}
                        for r in (previous['snapshot'].get('content_payload') or {}).get('issues',[])] if isinstance(previous,dict) else []
                    save()
                client.previous_news=saved['previous_news'][code]
                cached = saved.get("analysis_responses", {}).get(code)
                if cached is None and checkpoint is not None:
                    # Older releases retained the paid output in failed-job
                    # diagnostics rather than in the daily checkpoint.
                    cached = repo.analysis_recovery_response(date_text, code)
                    if not isinstance(cached, dict): cached = None
                from .execution_policy import bounded_analysis_recovery
                recovery_limit = bounded_analysis_recovery(saved, code, cached,
                    allowed=before_request is not None and not saved_material_only)
                if recovery_limit:
                    client.max_output_tokens = recovery_limit
                    cached = None
                    save()
                if cached is not None:
                    client.cached_response = cached
                    progress["reused_analysis_profiles"].append(code)
                if code=='MARKET':
                    if 'observations' not in saved:
                        saved['observations'] = collect_metrics(as_of) if not saved_material_only else {'items': [], 'collection_status':'deadline_skipped'}
                        save()
                    # Public synthesis uses only externally permitted observations.
                    client.market_metrics=[r for r in saved['observations']['items'] if r.get('value') is not None and r.get('external_allowed')]
                completed_c[code] = encode(run_phase_c(phase_b, profile_codes=(code,), analyzer=client))
                if code=='MARKET':saved['market_flow']=client.market_flow
                save()
        # Optional single bounded supplement; durable marker prevents replay if
        # the worker dies after a paid response. The shared reserve still wins.
        from datetime import time as clock_time
        from .phase_c import _apply_caps
        for code in requested:
            initial = restore_c(completed_c[code])
            visible = [r for r in initial.analyses if r.selection_tier == 'core']
            target = {'MARKET':4, 'NEWS':8, 'INSURANCE':5}[code]
            local_now = datetime.now(KST)
            if (len(visible) >= target or trigger_type == 'retry' or saved_material_only
                    or local_now.date() != as_of.astimezone(KST).date() or local_now.time() >= clock_time(8,30)
                    or code in saved.get('supplement_started', []) or before_request is None):
                continue
            used = {r.event_key for r in initial.analyses}
            candidates = [e for e in phase_b.events if e.event_key not in used and code in e.routed_profiles
                          and any(len(c.description.strip()) > 80 for c in e.candidates)]
            if not candidates:continue
            from .costs import estimate_cost
            from .execution_policy import budget_notice
            cost=repo.cost_status()
            estimate=estimate_cost({'model_name':os.getenv('BRIEFING_ROUTINE_MODEL',''), 'input_tokens':100000, 'output_tokens':24000})
            limits=[budget_notice(cost.get('today' if period=='day' else period,{}),period) for period in ('day','month')]
            # Extra calls require known prices, complete accounting and configured
            # monetary headroom; the original daily atomic request cap also applies.
            if (estimate is None or any(x.get('limit_usd') is None for x in limits)
                    or cost.get('row_limit_reached')
                    or any(cost.get(p,{}).get('unknown_cost_requests',0) for p in ('today','month'))
                    or any(cost.get(p,{}).get('accounted_known_usd',0)+estimate > limit['limit_usd']
                           for p,limit in zip(('today','month'),limits))):
                saved.setdefault('supplement_result',{})[code]={'status':'budget_hold'};save();continue
            saved.setdefault('supplement_started', []).append(code); save()
            client = OpenAIAnalysisClient(on_response=lambda record: record_usage(record, discovery=False))
            client.before_request = before_request
            client.previous_news = saved.get('previous_news', {}).get(code, [])
            supplement_b = PhaseBResult(phase_b.as_of, phase_b.candidates, candidates, [], {})
            try:
                extra = run_phase_c(supplement_b, profile_codes=(code,), analyzer=client, max_events_per_profile=10)
                merged = initial.analyses + extra.analyses
                # Reconsider capacity-only exclusions without bypassing quality.
                for row in merged:
                    if row.profile_payload.get('selection_decision') == 'capacity':row.selection_tier='light_digest'
                _apply_caps(merged, code)
                initial.analyses = merged
                initial.eligible_analyses += extra.eligible_analyses
                completed_c[code] = encode(initial); save()
            except Exception as exc:
                if saved.get('pending_request') or saved.get('charge_uncertain'):raise
                saved.setdefault('supplement_result', {})[code] = {'status':'stopped','reason':type(exc).__name__}
                save()
        pieces = [restore_c(completed_c[code]) for code in requested]
        phase_c = PhaseCResult([r for p in pieces for r in p.analyses],
            {k:v for p in pieces for k,v in p.usage_by_profile.items()},
            {k:v for p in pieces for k,v in p.omitted_by_profile.items()}, [r for p in pieces for r in p.eligible_analyses])
        market_context = saved.get("market_context", {})
        if "MARKET" in requested and not market_context:
            client = None
            if os.getenv("BRIEFING_ENABLE_RESEARCH", "false").lower()=="true" and any(c.metadata.get("lane_code") == "broker_research" for c in phase_b.candidates):
                client = OpenAIAnalysisClient(); client.before_request = before_request
            research, _ = build_research(phase_b.candidates if client else [], client=client,
                on_response=lambda record: record_usage(record, discovery=False))
            market_rows = sorted([r for r in phase_c.profile_rows("MARKET") if r.selection_tier != "excluded"], key=lambda r:-r.importance_score)
            market_context = {"market_metrics": saved.get("observations", {"items": []}), "research": research,
                "market_news_only": False, "market_mode": "article_briefing",
                "market_flow": [r['text'] for r in saved.get('market_flow',[])], "market_flow_facts":saved.get('market_flow',[])}
            saved["market_context"] = market_context; save()
        if "MARKET" in requested:
            market_context["market_metrics"] = saved.get("observations", {"items": []})
            market_context["market_news_only"] = False
            market_context["market_mode"] = "article_briefing"
            visible_market = [r for r in phase_c.profile_rows("MARKET")
                              if r.selection_tier != "excluded" and r.validation_status == "ok"]
            allowed_refs = {"event:" + r.event_key for r in visible_market} | {"metric:"+r["code"] for r in market_context["market_metrics"].get("items",[]) if r.get("value") is not None and r.get("external_allowed")}
            flow_facts = [r for r in market_context.get("market_flow_facts", [])
                          if r.get("fact_refs") and set(r["fact_refs"]) <= allowed_refs]
            market_context["market_flow_facts"] = flow_facts
            market_context["market_flow"] = [r["text"] for r in flow_facts]
            # Missing/old metric-backed synthesis must not demand another paid call.
            # Only already-validated article summaries may supply a factual fallback.
            if not market_context["market_flow"]:
                market_context["market_flow"] = [r.summary for r in sorted(visible_market,
                    key=lambda row: -row.importance_score)[:3] if r.summary.strip()]
                market_context["market_flow_mode"] = "verified_article_summaries"
            else:
                market_context["market_flow_mode"] = "event_synthesis"
            saved["market_context"] = market_context
        for code, usage in ({} if progress["analysis_requests"] or save_checkpoint else phase_c.usage_by_profile).items():
            if code in progress["reused_analysis_profiles"]: continue
            job = jobs.get(code)
            if not job:
                continue
            repo.log_api_usage({
                "job_id": job["id"],
                "profile_code": code,
                "provider": "openai",
                "operation": "phase_c_analysis",
                "model_name": usage.model_name,
                "service_tier": usage.service_tier,
                "input_tokens": usage.input_tokens,
                "cached_input_tokens": usage.cached_input_tokens,
                "output_tokens": usage.output_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "web_tool_calls": 0,
                "search_actions": 0,
                "search_retry_count": 0,
                "verification_search_actions": 0,
                "metadata": {"execution_purpose": purpose},
            })

        results: list[GeneratedProfileResult] = []
        progress["stage"] = "persistence"
        for code in requested:
            job = jobs[code]
            if code in saved.get("stored_profiles", {}):
                results.append(GeneratedProfileResult(**saved["stored_profiles"][code]))
                repo.update_job(str(job["id"]), {"job_status": "completed", "finished_at": datetime.now(timezone.utc).isoformat()})
                continue
            repo.update_job(str(job["id"]), {"job_status": "generating"})
            result = _persist_profile(
                repo,
                profile_code=code,
                phase_b=phase_b,
                phase_c=phase_c,
                actor_user_id=actor_user_id,
                job_id=str(job["id"]),
                run_mode="shadow" if force_shadow else str(profiles[code].get("run_mode") or "shadow"),
                market_context=market_context,
            )
            results.append(result)
            saved.setdefault("stored_profiles", {})[code] = asdict(result); save()
            progress["stored_profiles"] = [asdict(r) for r in results]
            repo.update_job(str(job["id"]), {"job_status": "completed", "finished_at": datetime.now(timezone.utc).isoformat()})

        progress["stage"] = "completed"
        return BriefingGenerationResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
            profiles=results,
            search_actions=sum(lane.usage.search_actions for lane in phase_b.discovery_lanes),
            candidate_count=len(phase_b.candidates),
            event_count=len(phase_b.events),
            diagnostics={"build": build_info(), "phase_b": phase_b.diagnostics, "source_health": phase_b.source_health, "excluded_counts": phase_b.excluded_counts,
                         "request_progress": progress,
                         "analysis_omitted": phase_c.omitted_by_profile, "analysis_usage": {k: asdict(v) for k,v in phase_c.usage_by_profile.items()},
                         "discovery_usage": [{"lane_code": l.lane_code, "profile_code": l.profile_code, "usage": asdict(l.usage)} for l in phase_b.discovery_lanes]},
        )
    except Exception as exc:
        details = {**progress, "failure_details": getattr(exc, "diagnostics", {})}
        paid = details["failure_details"].get("analysis_response") or {}
        if (paid.get("usage_logged") and paid.get("usage_available") and not paid.get("charge_uncertain")
                and paid.get("output_text_sample")):
            saved.setdefault("analysis_responses", {})[paid["profile_code"]] = dict(paid)
        cleanup_failures = []
        for code, job in jobs.items():
            if code in saved.get("stored_profiles", {}): continue
            try:
                repo.update_job(str(job["id"]), {
                    "job_status": "failed",
                    "failure_code": "GENERATION_FAILURE",
                    "failure_message": str(exc)[:500],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"engine_version": ENGINE_VERSION, "shared_run": True, "failure_diagnostics": details},
                })
            except Exception:
                cleanup_failures.append(str(job["id"]))
        details["job_cleanup_failures"] = cleanup_failures
        saved["charge_uncertain"] = bool(saved.get("pending_request")) or any(r.get("charge_uncertain") and not r.get("direct_feed_fallback") for group in (progress["discovery_requests"], progress["analysis_requests"]) for r in group)
        if save_checkpoint: save_checkpoint(saved)
        raise BriefingRunError(str(exc), details) from exc

