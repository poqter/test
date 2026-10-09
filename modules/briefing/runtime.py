from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
    publishers = {c.publisher_domain for c in owned if c.publisher_domain}
    successful = any(l.search_performed for l in lanes) or any(h.get("status") in {"ok", "empty_valid"} for h in direct)
    successful_paths = sum(l.search_performed for l in lanes) + sum(h.get("status") in {"ok", "empty_valid"} for h in direct)
    if routed_event_count >= 1 and (successful_paths >= 2 or successful and len(publishers) >= 2):
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
    event_map = _event_lookup(phase_b.events)
    return {
        "profile_code": profile_code,
        "profile_label": PROFILE_LABELS.get(profile_code, profile_code),
        "as_of": phase_b.as_of.isoformat(),
        "coverage_status": coverage_status,
        "core_count": sum(r.selection_tier == "core" for r in rows),
        "light_count": sum(r.selection_tier == "light_digest" for r in rows),
        "issues": [
            {
                "event_key": r.event_key,
                "selection_tier": r.selection_tier,
                "importance_score": r.importance_score,
                "category": r.category,
                "issue_status": r.issue_status,
                "title": r.title,
                "summary": r.summary,
                "why_important": r.why_important,
                "impact_summary": r.impact_summary,
                "action_state": r.action_state,
                "communication_state": r.communication_state,
                "audience_segments": r.audience_segments,
                "representative": r.selection_tier == "core",
                "sources": [{"title": c.title, "source_name": c.source_name, "url": c.canonical_url or c.url, "published_at": _iso(c.published_at)} for c in event_map[r.event_key].candidates if c.published_at],
            }
            for r in selected
        ],
    }


def _event_lookup(events: Iterable[SharedEventCandidate]) -> dict[str, SharedEventCandidate]:
    return {event.event_key: event for event in events}


def _overall_validation(rows: list[ProfileEventAnalysis], coverage_status: str) -> str:
    if coverage_status == "insufficient":
        return "required"
    visible = [r for r in rows if r.selection_tier != "excluded"]
    if any(r.validation_status != "ok" for r in visible):
        return "required"
    return "ok"


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
    routed_events = [event for event in phase_b.events if profile_code in event.routed_profiles]
    coverage_status = _coverage_status(phase_b, profile_code, len(routed_events))
    validation_status = _overall_validation(rows, coverage_status)
    if profile_code == "MARKET" and not (market_context or {}).get("market_metrics", {}).get("complete"):
        validation_status = "required"

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
    external = customer_body(content)
    public_ready = bool(external["issues"]) and len(external["issues"]) == len(content["issues"])
    if profile_code == "MARKET":
        public_ready = public_ready and len(external["market_metrics"]) == 6
    if not public_ready: validation_status = "required"
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
            "coverage_status": coverage_status,
            "excluded_counts": phase_b.excluded_counts,
            "collection_diagnostics": phase_b.diagnostics,
            "source_health": phase_b.source_health,
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
    if run_mode == "auto" and validation_status == "ok" and coverage_status != "insufficient":
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
) -> BriefingGenerationResult:
    """Run one shared Phase B discovery, one Phase C batch per routed profile,
    then persist immutable V1.6 snapshots for the requested profiles.

    The initial DB seed is run_mode=shadow, so this function normally creates
    manager-visible drafts.  Publication remains a separate explicit action.
    """
    repo = repository or BriefingRepository()
    profiles = {str(row.get("profile_code")): row for row in repo.profiles()}
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
    date_text = as_of.astimezone(KST).date().isoformat()
    jobs: dict[str, dict[str, Any]] = {}
    progress: dict[str, Any] = {"stage": "creating_jobs", "requested_profiles": list(requested),
                                "discovery_requests": [], "analysis_requests": [], "build": build_info()}

    def record_usage(record: dict[str, Any], *, discovery: bool) -> None:
        collection = "discovery_requests" if discovery else "analysis_requests"
        progress[collection].append(record)
        code = record["profile_code"]
        owner = code if code in jobs else next(iter(jobs))
        usage = record.get("usage") or {}
        search_status = record.get("search_status_counts") or {}
        uncertain_search = discovery and any(search_status.get(state, 0) for state in ("nonfinal", "unknown"))
        record["usage_logged"] = False
        record["charge_uncertain"] = not bool(record.get("usage_available")) or uncertain_search
        repo.log_api_usage({
            "job_id": jobs[owner]["id"], "profile_code": owner, "provider": "openai",
            "operation": f"web_discovery:{record['lane_code']}" if discovery else record.get("operation") or "phase_c_analysis",
            **{field: usage.get(field) for field in ("model_name", "service_tier")},
            **{field: int(usage.get(field) or 0) for field in ("input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "web_tool_calls", "search_actions", "search_retry_count", "verification_search_actions")},
            "metadata": {"engine_version": ENGINE_VERSION, "request_no": record.get("request_no"),
                         "response_id": record.get("response_id"), "response_status": record.get("status"),
                         "retry_used": bool(record.get("retry")), "lane_profile_code": code,
                         "usage_available": bool(record.get("usage_available")),
                         "charge_uncertain": not bool(record.get("usage_available")) or uncertain_search,
                         "search_status_counts": search_status if discovery else None,
                         "search_billing_uncertain": uncertain_search,
                         "requested_max_tool_calls": record.get("requested_max_tool_calls")},
        })
        if discovery and before_request:
            repo._request("POST", "/rest/v1/rpc/hwarang_observe_briefing_search", json={"p_date":date_text,"p_actions":int(usage.get("search_actions") or 0)})
        record["usage_logged"] = True
        if record.get("usage_available") and not record["charge_uncertain"]:
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
                retry_missing_search=trigger_type == "manual" and before_request is None,
                on_discovery_response=lambda record: record_usage(record, discovery=True))
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
                "metadata": {"retry_used": lane.retry_used, "response_id": lane.raw_response_id},
            })

        progress["stage"] = "analysis"
        if save_checkpoint:
            completed_c = saved.setdefault("phase_c_by_profile", {})
            for code in requested:
                if code not in completed_c:
                    client = OpenAIAnalysisClient(on_response=lambda record: record_usage(record, discovery=False))
                    client.before_request = before_request
                    completed_c[code] = encode(run_phase_c(phase_b, profile_codes=(code,), analyzer=client))
                    save()
            pieces = [restore_c(completed_c[code]) for code in requested]
            phase_c = PhaseCResult([r for p in pieces for r in p.analyses],
                {k:v for p in pieces for k,v in p.usage_by_profile.items()},
                {k:v for p in pieces for k,v in p.omitted_by_profile.items()}, [r for p in pieces for r in p.eligible_analyses])
        else:
            phase_c = run_phase_c(phase_b, profile_codes=requested,
                                 on_analysis_response=lambda record: record_usage(record, discovery=False))
        market_context = saved.get("market_context", {})
        if "MARKET" in requested and not market_context:
            client = None
            if any(c.metadata.get("lane_code") == "broker_research" for c in phase_b.candidates):
                client = OpenAIAnalysisClient(); client.before_request = before_request
            research, _ = build_research(phase_b.candidates, client=client,
                on_response=lambda record: record_usage(record, discovery=False))
            market_rows = sorted([r for r in phase_c.profile_rows("MARKET") if r.selection_tier != "excluded"], key=lambda r:-r.importance_score)
            market_context = {"market_metrics": collect_metrics(as_of), "research": research,
                "market_flow": [re.split(r"(?<=[.!?。])\s+|\n", r.impact_summary or r.summary)[0] for r in market_rows[:5] if r.impact_summary or r.summary]}
            saved["market_context"] = market_context; save()
        for code, usage in ({} if progress["analysis_requests"] or save_checkpoint else phase_c.usage_by_profile).items():
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
                "metadata": {},
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
        saved["charge_uncertain"] = bool(saved.get("pending_request")) or any(r.get("charge_uncertain") for group in (progress["discovery_requests"], progress["analysis_requests"]) for r in group)
        if save_checkpoint: save_checkpoint(saved)
        raise BriefingRunError(str(exc), details) from exc
