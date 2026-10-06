from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import html
import hashlib
import json
from dataclasses import asdict
from typing import Any, Callable

import streamlit as st

from .repository import BriefingRepository, BriefingRepositoryError
from .runtime import PROFILE_LABELS, BriefingRunError, generate_and_store_briefings
from .normalize import is_safe_url
from .preflight import run_runtime_preflight, preflight_ready
from .direct_sources import load_direct_source_specs_from_env, probe_direct_sources
from .diagnostics import ENGINE_VERSION, DIAGNOSTIC_SCHEMA, build_info, failure_diagnostic
from .config import SHARED_DISCOVERY_HARD_LIMIT
from .discovery_budget import DISCOVERY_REQUEST_HARD_LIMIT


PROFILE_ORDER = ("MARKET", "INSURANCE", "NEWS")
PROFILE_SHORT = {"MARKET": "MARKET", "INSURANCE": "INSURANCE", "NEWS": "NEWS"}
ACTION_LABELS = {"review_now": "지금 확인", "reference_today": "오늘 참고", "watch": "지켜보기"}
COMM_LABELS = {
    "customer_ready": "바로 설명 가능",
    "consultation_reference": "상담 참고",
    "internal_check": "내부 확인",
    "do_not_mention": "고객 언급 금지",
    "not_applicable": "해당 없음",
}
SELECTION_LABELS = {"core": "핵심", "light_digest": "참고", "excluded": "제외"}

PROFILE_META = {
    "MARKET": {
        "eyebrow": "MARKET",
        "title": "경제·주식",
        "description": "금리·환율·증시와 주요 시장 변수를 압축합니다.",
        "tone": "market",
    },
    "INSURANCE": {
        "eyebrow": "INSURANCE",
        "title": "보험업계",
        "description": "FP 업무와 고객 상담에 영향을 주는 변화만 정리합니다.",
        "tone": "insurance",
    },
    "NEWS": {
        "eyebrow": "NEWS",
        "title": "국내 주요 뉴스",
        "description": "오늘 알아야 할 정책·사회·생활 변화를 선별합니다.",
        "tone": "news",
    },
}
KST = ZoneInfo("Asia/Seoul")


def _inject_briefing_styles() -> None:
    st.markdown(
        """
        <style>
        .st-key-hw_briefing_hero{
            margin:2px 0 18px;
            padding:22px 24px;
            border:1px solid #dbe4ef;
            border-radius:18px;
            background:linear-gradient(135deg,#ffffff 0%,#f7faff 100%);
            box-shadow:0 10px 30px rgba(27,55,90,.055);
        }
        .hw-briefing-eyebrow{
            font-size:11px;font-weight:800;letter-spacing:.12em;color:#66809f;margin-bottom:8px;
        }
        .hw-briefing-title{
            margin:0;color:#102b4e;font-size:30px;line-height:1.2;font-weight:800;letter-spacing:-.035em;
        }
        .hw-briefing-subtitle{
            margin:9px 0 0;color:#687b91;font-size:14px;line-height:1.65;
        }
        .hw-briefing-mode{
            display:inline-flex;align-items:center;gap:7px;padding:7px 10px;
            border:1px solid #dbe4ef;border-radius:999px;background:#fff;
            color:#5b6f86;font-size:11px;font-weight:800;letter-spacing:.04em;
        }
        .hw-briefing-mode-dot{width:7px;height:7px;border-radius:999px;background:#e29b32;display:inline-block}
        .st-key-hw_briefing_tabs [role="radiogroup"]{gap:8px!important}
        .st-key-hw_briefing_tabs label[data-baseweb="radio"]{
            min-height:40px;padding:7px 15px!important;border-radius:10px;
            border:1px solid #dbe4ef;background:#fff;
        }
        .st-key-hw_briefing_tabs label:has(input:checked){
            border-color:#7fa9e6;background:#edf4ff!important;color:#174f9a;
        }
        .st-key-hw_briefing_card_market,
        .st-key-hw_briefing_card_insurance,
        .st-key-hw_briefing_card_news{
            min-height:258px;padding:19px 20px 16px!important;border-radius:16px;
            border:1px solid #dbe4ef;background:#fff;
            box-shadow:0 6px 20px rgba(31,55,82,.045);
        }
        .st-key-hw_briefing_card_market{border-top:3px solid #476f9f}
        .st-key-hw_briefing_card_insurance{border-top:3px solid #2b7a78}
        .st-key-hw_briefing_card_news{border-top:3px solid #6a67a5}
        .hw-profile-eyebrow{font-size:10px;font-weight:800;letter-spacing:.11em;color:#8091a6;margin-bottom:6px}
        .hw-profile-title{font-size:21px;font-weight:800;color:#112d4f;letter-spacing:-.025em;margin-bottom:6px}
        .hw-profile-desc{font-size:12.5px;line-height:1.55;color:#7a899b;min-height:40px;margin-bottom:12px}
        .hw-profile-summary{font-size:14px;line-height:1.55;color:#253b55;min-height:44px;margin:4px 0 10px}
        .hw-profile-state{display:flex;align-items:center;gap:7px;margin:5px 0 10px}
        .hw-state-pill{
            display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;
            font-size:10.5px;font-weight:800;border:1px solid #dce4ed;background:#f8fafc;color:#61758b;
        }
        .hw-state-pill.is-ready{background:#eef8f3;border-color:#cfe7da;color:#267052}
        .hw-state-pill.is-preview{background:#fff7e8;border-color:#f1dfb7;color:#8a631c}
        .hw-state-pill.is-waiting{background:#f6f8fb;border-color:#e1e6ed;color:#7d8b9b}
        .hw-count-row{display:flex;gap:8px;flex-wrap:wrap;margin:7px 0 12px}
        .hw-count-chip{
            display:inline-flex;align-items:baseline;gap:5px;padding:6px 9px;border-radius:9px;
            background:#f5f8fc;border:1px solid #e3e9f1;color:#6a7c91;font-size:11px;
        }
        .hw-count-chip strong{font-size:14px;color:#19395f}
        .st-key-hw_briefing_admin_panel{
            padding:12px 14px!important;border:1px solid #e2e8f0;border-radius:13px;background:#fbfcfe;
        }
        .hw-section-head{display:flex;align-items:flex-end;justify-content:space-between;margin:25px 0 11px}
        .hw-section-head h3{margin:0;font-size:20px;color:#173352;letter-spacing:-.025em}
        .hw-section-head span{font-size:12px;color:#8795a5}
        .st-key-hw_fast_brief{
            padding:17px 18px!important;border-radius:14px;border:1px solid #dce6f1;background:#f8fbff;
        }
        .hw-fast-sentence{font-size:16px;font-weight:750;color:#17395f;line-height:1.55;margin-bottom:10px}
        .hw-fast-item{font-size:13.5px;color:#425a73;line-height:1.55;padding:4px 0}
        .st-key-hw_action_review_now,
        .st-key-hw_action_reference_today,
        .st-key-hw_action_watch{
            min-height:150px;padding:15px 16px!important;border-radius:14px;border:1px solid #e1e7ee;background:#fff;
        }
        .st-key-hw_action_review_now{border-top:3px solid #c7705f}
        .st-key-hw_action_reference_today{border-top:3px solid #4f7eaa}
        .st-key-hw_action_watch{border-top:3px solid #9a8652}
        .hw-action-title{font-size:13px;font-weight:800;color:#243c58;margin-bottom:8px}
        .hw-action-item{font-size:12.5px;line-height:1.5;color:#5a6d83;padding:3px 0}
        .hw-issue-meta{display:flex;gap:7px;flex-wrap:wrap;margin:3px 0 14px}
        .hw-issue-chip{
            display:inline-flex;padding:5px 8px;border-radius:8px;background:#f6f8fb;
            border:1px solid #e3e8ef;font-size:11px;color:#64768b;
        }
        [class*="st-key-hw_briefing_history_"]{
            padding:11px 14px!important;border:1px solid #e3e8ef;border-radius:12px;background:#fff;margin-bottom:8px;
        }
        @media(max-width:768px){
            .st-key-hw_briefing_hero{padding:17px 16px}
            .hw-briefing-title{font-size:25px}
            .st-key-hw_briefing_card_market,
            .st-key-hw_briefing_card_insurance,
            .st-key-hw_briefing_card_news{min-height:auto}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_section_head(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="hw-section-head"><h3>{html.escape(title)}</h3>'
        f'<span>{html.escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def _status_html(state: str) -> str:
    css = "is-ready" if state == "공개" else "is-preview" if state == "관리자 미리보기" else "is-waiting"
    return f'<span class="hw-state-pill {css}">{html.escape(state)}</span>'


def _can_manage() -> bool:
    profile = st.session_state.get("login_profile") or {}
    permissions = set(st.session_state.get("hw_feature_permissions") or ())
    return profile.get("role") == "super_admin" or "workspace.briefing_manage" in permissions


def _repo() -> BriefingRepository:
    return BriefingRepository()


def _fmt_dt(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return "-"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%m.%d %H:%M")
    except ValueError:
        return raw[:16]


def _counts(bundle: dict[str, Any] | None) -> tuple[int, int]:
    if not bundle:
        return 0, 0
    snapshot = bundle.get("snapshot") or {}
    fast = snapshot.get("fast_brief_payload") or {}
    try:
        return int(fast.get("core_count") or 0), int(fast.get("light_count") or 0)
    except (TypeError, ValueError):
        return 0, 0


def _latest_bundles(include_draft: bool) -> dict[str, dict[str, Any] | None]:
    repo = _repo()
    return {code: repo.latest_bundle(code, include_draft=include_draft) for code in PROFILE_ORDER}


def render_home_summary(navigate: Callable[..., object]) -> None:
    """Compact, low-density home signal.  Fail closed if the briefing DB is unavailable."""
    try:
        bundles = _latest_bundles(include_draft=False)
    except Exception:
        return
    available = [bundle for bundle in bundles.values() if bundle]
    if not available:
        return
    with st.container(key="hw_home_briefing_summary"):
        title_col, button_col = st.columns([4, 1], vertical_alignment="center")
        with title_col:
            st.markdown("#### 오늘의 브리핑")
            pieces: list[str] = []
            for code in PROFILE_ORDER:
                bundle = bundles.get(code)
                if not bundle:
                    pieces.append(f"{PROFILE_SHORT[code]} 준비 중")
                    continue
                core, light = _counts(bundle)
                pieces.append(f"{PROFILE_SHORT[code]} 핵심 {core} · 참고 {light}")
            st.caption("  ·  ".join(pieces))
        with button_col:
            if st.button("브리핑 센터 →", key="hw_home_briefing_open", use_container_width=True):
                navigate("briefing")


def _render_profile_card(code: str, bundle: dict[str, Any] | None, *, include_draft: bool) -> bool:
    meta = PROFILE_META[code]
    with st.container(key=f"hw_briefing_card_{code.lower()}"):
        st.markdown(
            f'<div class="hw-profile-eyebrow">{html.escape(meta["eyebrow"])}</div>'
            f'<div class="hw-profile-title">{html.escape(meta["title"])}</div>'
            f'<div class="hw-profile-desc">{html.escape(meta["description"])}</div>',
            unsafe_allow_html=True,
        )
        if not bundle:
            waiting_text = (
                "시장 데이터 Source 연결 후 자동 생성할 수 있습니다."
                if code == "MARKET"
                else "첫 브리핑 생성 후 오늘의 핵심 변화가 표시됩니다."
            )
            st.markdown(
                '<div class="hw-profile-state">' + _status_html("준비 중") + '</div>'
                f'<div class="hw-profile-summary">{html.escape(waiting_text)}</div>'
                '<div class="hw-count-row">'
                '<span class="hw-count-chip">핵심 <strong>–</strong></span>'
                '<span class="hw-count-chip">참고 <strong>–</strong></span>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            revision = bundle.get("revision") or {}
            snapshot = bundle.get("snapshot") or {}
            fast = snapshot.get("fast_brief_payload") or {}
            core, light = _counts(bundle)
            state = "공개" if revision.get("publication_status") == "published" else "관리자 미리보기"
            sentence = str(fast.get("remember_one_sentence") or "오늘의 주요 변화를 확인하세요.")
            st.markdown(
                '<div class="hw-profile-state">' + _status_html(state)
                + f'<span style="font-size:11px;color:#8897a7">{html.escape(_fmt_dt(revision.get("generated_at")))}</span></div>'
                f'<div class="hw-profile-summary">{html.escape(sentence)}</div>'
                '<div class="hw-count-row">'
                f'<span class="hw-count-chip">핵심 <strong>{core}</strong></span>'
                f'<span class="hw-count-chip">참고 <strong>{light}</strong></span>'
                '</div>',
                unsafe_allow_html=True,
            )
        return st.button(
            "브리핑 보기 →",
            key=f"hw_briefing_open_{code}",
            use_container_width=True,
            disabled=not bool(bundle),
        )


def _source_map(bundle: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    sources = {str(row.get("id")): row for row in bundle.get("sources") or [] if row.get("id")}
    by_issue: dict[str, list[str]] = {}
    for rel in bundle.get("issue_sources") or []:
        issue_id = str(rel.get("issue_id") or "")
        source_id = str(rel.get("source_id") or "")
        if issue_id and source_id:
            by_issue.setdefault(issue_id, []).append(source_id)
    return sources, by_issue


def _render_sources(issue: dict[str, Any], bundle: dict[str, Any]) -> None:
    sources, by_issue = _source_map(bundle)
    ids = by_issue.get(str(issue.get("id") or ""), [])
    if not ids:
        st.caption("연결된 출처가 없습니다.")
        return
    st.markdown("**주요 출처**")
    for source_id in ids[:5]:
        source = sources.get(source_id) or {}
        title = str(source.get("title") or source.get("publisher_name") or source.get("source_name") or "출처")
        url = str(source.get("canonical_url") or source.get("url") or "")
        meta = " · ".join(x for x in [str(source.get("publisher_name") or source.get("source_name") or ""), _fmt_dt(source.get("published_at"))] if x and x != "-")
        if is_safe_url(url):
            st.link_button(title[:80] + ("…" if len(title) > 80 else ""), url, use_container_width=True)
            if meta:
                st.caption(meta)


def _render_timeline(repo: BriefingRepository, event_id: str | None) -> None:
    if not event_id:
        return
    updates = repo.event_updates(str(event_id), limit=6)
    if not updates:
        return
    st.markdown("**Event Timeline**")
    for row in reversed(updates):
        st.caption(f"{_fmt_dt(row.get('observed_at'))} · {str(row.get('change_summary') or row.get('title') or '')}")


def _issue_anchor(issue: dict[str, Any]) -> str:
    return "hw-issue-" + hashlib.sha256(str(issue.get("id") or issue.get("issue_key") or "").encode()).hexdigest()[:16]


def _render_issue(repo: BriefingRepository, issue: dict[str, Any], action: dict[str, Any] | None, bundle: dict[str, Any], *, expanded: bool = False) -> None:
    tier = str(issue.get("selection_tier") or "")
    title = str(issue.get("title") or "이슈")
    prefix = "핵심" if tier == "core" else "참고"
    st.markdown(f'<div id="{_issue_anchor(issue)}"></div>', unsafe_allow_html=True)
    with st.expander(f"[{prefix}] {title}", expanded=expanded):
        st.markdown(
            '<div class="hw-issue-meta">'
            f'<span class="hw-issue-chip">카테고리 · {html.escape(str(issue.get("category") or "-"))}</span>'
            f'<span class="hw-issue-chip">상태 · {html.escape(str(issue.get("issue_status") or "-"))}</span>'
            f'<span class="hw-issue-chip">근거 · {html.escape(str(issue.get("evidence_status") or "-"))}</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        if issue.get("summary"):
            st.write(str(issue["summary"]))
        fact = issue.get("fact_payload") or {}
        analysis = issue.get("analysis_payload") or {}
        if fact.get("why_important"):
            st.markdown("**왜 중요한가**")
            st.write(str(fact.get("why_important")))
        if analysis.get("impact_summary"):
            st.markdown("**영향**")
            st.write(str(analysis.get("impact_summary")))
        if action:
            st.markdown("**TODAY ACTION**")
            st.write(f"{ACTION_LABELS.get(str(action.get('action_state')), '지켜보기')} · {str(action.get('summary') or '')}")
            communication = str(action.get("communication_state") or "not_applicable")
            if communication != "not_applicable":
                st.caption("고객 대화 · " + COMM_LABELS.get(communication, communication))
            audiences = action.get("audience_segments") or []
            if audiences:
                st.caption("관련 대상 · " + " / ".join(str(x) for x in audiences[:5]))
            conversation = action.get("conversation_payload") or {}
            if conversation.get("recommended_expression"):
                st.markdown("**권장 표현**")
                st.write(str(conversation.get("recommended_expression")))
            if conversation.get("check_first"):
                st.caption("먼저 확인 · " + str(conversation.get("check_first")))
            if conversation.get("avoid_expression"):
                st.caption("주의 표현 · " + str(conversation.get("avoid_expression")))
        _render_sources(issue, bundle)
        _render_timeline(repo, str(issue.get("event_id") or "") or None)


def _render_related_issue(issue: dict[str, Any], bundle: dict[str, Any]) -> None:
    st.markdown(f'<div id="{_issue_anchor(issue)}"></div>', unsafe_allow_html=True)
    st.write(str(issue.get("title") or "관련 뉴스"))
    if issue.get("summary"):
        st.write(str(issue["summary"]))
    st.caption(str(issue.get("category") or ""))
    _render_sources(issue, bundle)


def _render_profile_detail(repo: BriefingRepository, code: str, bundle: dict[str, Any], *, can_manage: bool) -> None:
    briefing = bundle.get("briefing") or {}
    revision = bundle.get("revision") or {}
    snapshot = bundle.get("snapshot") or {}
    fast = snapshot.get("fast_brief_payload") or {}
    today = snapshot.get("today_action_payload") or {}
    issues = bundle.get("issues") or []
    actions = {str(row.get("issue_id")): row for row in bundle.get("actions") or [] if row.get("issue_id")}
    if revision.get("coverage_status") == "insufficient":
        st.warning("수집·게시일 확인이 충분하지 않아 공개를 보류합니다. ‘오늘 중요한 뉴스가 없음’을 뜻하지 않습니다.")
    elif revision.get("coverage_status") == "degraded":
        st.warning("일부 출처만 확보된 브리핑입니다. 여러 분야의 뉴스가 충분히 수집됐는지 검토해 주세요.")

    st.divider()
    h1, h2 = st.columns([4, 1], vertical_alignment="center")
    with h1:
        st.subheader(PROFILE_LABELS[code])
        status = "공개" if revision.get("publication_status") == "published" else "관리자 미리보기"
        st.caption(f"{briefing.get('briefing_date')} · {status} · 생성 {_fmt_dt(revision.get('generated_at'))} · Coverage {revision.get('coverage_status')}")
    with h2:
        if can_manage and revision.get("publication_status") != "published":
            can_publish = (revision.get("validation_status") == "ok"
                           and revision.get("coverage_status") != "insufficient"
                           and (revision.get("coverage_status") == "healthy" or bool(bundle.get("issues"))))
            if st.button("공개하기", key=f"hw_briefing_publish_{revision.get('id')}", type="primary", use_container_width=True, disabled=not can_publish):
                try:
                    actor = str((st.session_state.get("login_profile") or {}).get("id") or "") or None
                    repo.publish_revision(str(briefing["id"]), str(revision["id"]), actor_user_id=actor)
                    st.success("브리핑을 공개했습니다.")
                    st.rerun()
                except BriefingRepositoryError as exc:
                    st.error(str(exc))

    _render_section_head("오늘 5분 FAST BRIEF", "3~5분 안에 오늘의 흐름을 파악합니다.")
    with st.container(key="hw_fast_brief"):
        st.markdown(
            f'<div class="hw-fast-sentence">{html.escape(str(fast.get("remember_one_sentence") or "오늘의 핵심 변화를 확인하세요."))}</div>',
            unsafe_allow_html=True,
        )
        items = (fast.get("items") or [])[:5]
        if not items:
            st.caption("표시할 핵심 흐름이 없습니다.")
        for item in items:
            st.markdown(
                f'<div class="hw-fast-item">• {html.escape(str(item.get("title") or ""))}</div>',
                unsafe_allow_html=True,
            )

    _render_section_head("TODAY ACTION", "지금 확인할 일과 지켜볼 일을 분리합니다.")
    action_cols = st.columns(3, gap="medium")
    for col, key in zip(action_cols, ("review_now", "reference_today", "watch")):
        with col, st.container(key=f"hw_action_{key}"):
            st.markdown(f'<div class="hw-action-title">{ACTION_LABELS[key]}</div>', unsafe_allow_html=True)
            rows = today.get(key) or []
            if not rows:
                st.markdown('<div class="hw-action-item">해당 항목 없음</div>', unsafe_allow_html=True)
            for row in rows[:4]:
                linked_issue = next((i for i in issues if str(i.get("issue_key") or "") == f"{code}:{row.get('event_key')}"), None)
                label = html.escape(str(row.get("title") or ""))
                if linked_issue:
                    label = f'<a href="#{_issue_anchor(linked_issue)}">{label}</a>'
                st.markdown(
                    f'<div class="hw-action-item">• {label}</div>',
                    unsafe_allow_html=True,
                )

    core = [row for row in issues if row.get("selection_tier") == "core"]
    light = [row for row in issues if row.get("selection_tier") == "light_digest"]
    _render_section_head("핵심 이슈", "오늘 반드시 알아야 할 변화입니다.")
    if not core:
        st.caption("현재 검증된 핵심 이슈가 없습니다.")
    for index, issue in enumerate(core):
        _render_issue(repo, issue, actions.get(str(issue.get("id"))), bundle, expanded=index == 0)

    if light:
        _render_section_head("참고할 소식", "오늘의 흐름을 이해하는 데 도움이 되는 정보입니다.")
        for issue in light[:5]:
            _render_related_issue(issue, bundle)
        if len(light) > 5:
            with st.expander(f"관련 뉴스 {min(len(light), 7)-5}개 더 보기"):
                for issue in light[5:7]:
                    _render_related_issue(issue, bundle)
    if can_manage:
        with st.expander("생성 진단 결과"):
            qa = snapshot.get("qa_payload") or {}
            st.json(qa)
            st.download_button("진단 JSON 다운로드", json.dumps({"schema_version": DIAGNOSTIC_SCHEMA, **build_info(), "profile_code": code, "briefing_date": briefing.get("briefing_date"), "revision_status": {k: revision.get(k) for k in ("publication_status", "validation_status", "coverage_status")}, "qa": qa}, ensure_ascii=False, indent=2), file_name=f"briefing_{code}_stage1_diagnostics.json", mime="application/json", key=f"hw_diag_{snapshot.get('id')}")


def _render_generate_panel(repo: BriefingRepository) -> None:
    if not _can_manage():
        return
    with st.container(key="hw_briefing_admin_panel"):
        with st.popover("콘텐츠 관리", use_container_width=True):
            st.markdown("**운영 모드 · SHADOW**")
            st.caption(f"개발 검증 버전 · {ENGINE_VERSION}")
            st.caption("생성 결과는 관리자 미리보기로 저장되며, 검증 후 공개할 수 있습니다.")
            st.caption("INSURANCE·NEWS는 Shared Discovery를 함께 사용해 중복 검색을 줄입니다.")
            checks = run_runtime_preflight(require_direct_sources=False)
            has_market_source = False
            if preflight_ready(checks):
                has_market_source = any("MARKET" in s.profile_hints for s in load_direct_source_specs_from_env())
            requested_profiles = ("INSURANCE", "MARKET", "NEWS") if has_market_source else ("INSURANCE", "NEWS")
            if not has_market_source:
                st.caption("MARKET 직접 출처 연결 전에는 보험·국내 뉴스만 생성합니다.")
            for check in checks:
                if not check.ok:
                    (st.error if check.required else st.caption)(check.message)
            st.download_button("배포 진단 다운로드 · API 호출 없음", json.dumps({
                "schema_version": DIAGNOSTIC_SCHEMA, **build_info(), "status": "preflight",
                "requested_profiles": requested_profiles,
                "settings": [{"code": c.code, "ok": c.ok, "required": c.required} for c in checks],
                "limits": {"search_actions": SHARED_DISCOVERY_HARD_LIMIT, "discovery_requests": DISCOVERY_REQUEST_HARD_LIMIT},
            }, ensure_ascii=False, indent=2), file_name="briefing_stage1_deployment_diagnostics.json",
                mime="application/json", key="hw_briefing_deployment_diagnostic_download")
            paid_ack = st.checkbox("이번 1회 유료 API 실행을 확인했습니다.", key="hw_briefing_paid_ack")
            if st.button(
                "오늘 브리핑 생성",
                key="hw_briefing_generate_today",
                type="primary",
                use_container_width=True,
                disabled=not paid_ack or not preflight_ready(checks),
            ):
                actor = str((st.session_state.get("login_profile") or {}).get("id") or "") or None
                st.session_state.pop("hw_briefing_last_diagnostic", None)
                with st.spinner("오늘의 이슈를 수집·검증·분석하고 있습니다…"):
                    try:
                        result = generate_and_store_briefings(actor_user_id=actor, repository=repo, profile_codes=requested_profiles, force_shadow=True)
                        st.session_state["hw_briefing_last_diagnostic"] = asdict(result)
                        summary = " · ".join(
                            f"{row.profile_code} 핵심 {row.core_count} / 참고 {row.light_count}"
                            for row in result.profiles
                        )
                        st.session_state["hw_briefing_flash"] = (
                            f"생성 완료 · {summary} · 검색 기록 {result.search_actions} · "
                            f"후보 {result.candidate_count} · Event {result.event_count}"
                        )
                        st.session_state.pop("hw_briefing_selected_profile", None)
                        st.rerun()
                    except (BriefingRunError, BriefingRepositoryError, ValueError) as exc:
                        st.session_state["hw_briefing_last_diagnostic"] = failure_diagnostic(exc)
                        st.error("브리핑 생성에 실패했습니다.")
                        st.caption(str(exc))
            if st.session_state.get("hw_briefing_last_diagnostic"):
                st.download_button("이번 실행 전체 진단 다운로드", json.dumps(st.session_state["hw_briefing_last_diagnostic"], ensure_ascii=False, indent=2), file_name="briefing_stage1_run_diagnostics.json", mime="application/json", key="hw_briefing_run_diagnostic_download")
            st.divider()
            st.caption("직접 출처 점검은 공개 RSS/Atom에 접속합니다. OpenAI 호출과 DB 쓰기 없이 서버 연결 상태만 확인합니다.")
            if st.button("직접 출처 점검 · 유료 API 없음", key="hw_briefing_probe_sources", use_container_width=True):
                with st.spinner("직접 출처 연결과 게시일을 확인하고 있습니다…"):
                    try:
                        packet = probe_direct_sources(load_direct_source_specs_from_env())
                    except (ValueError, KeyError, TypeError):
                        packet = {"status": "direct_source_config_invalid", "project_openai_api_calls": 0, "db_writes": 0}
                    st.session_state["hw_briefing_source_probe"] = {"schema_version": DIAGNOSTIC_SCHEMA, **build_info(), **packet}
            if st.session_state.get("hw_briefing_source_probe"):
                packet = st.session_state["hw_briefing_source_probe"]
                if packet.get("status") == "direct_source_config_invalid":
                    st.error("직접 출처 설정을 읽지 못했습니다. 아래 점검 JSON을 전달해 주세요.")
                failed = sum(row.get("status") == "failed" for row in (packet.get("direct_sources") or {}).values())
                st.caption(f"직접 출처 {packet.get('configured_source_count', 0)}개 · 실패 {failed}개 · OpenAI 호출 0회")
                st.download_button("직접 출처 점검 JSON 다운로드", json.dumps(packet, ensure_ascii=False, indent=2),
                                   file_name="briefing_direct_source_diagnostics.json", mime="application/json",
                                   key="hw_briefing_source_probe_download")


def _render_today(repo: BriefingRepository, can_manage: bool) -> None:
    bundles = {code: repo.latest_bundle(code, include_draft=can_manage) for code in PROFILE_ORDER}
    _render_section_head("오늘의 브리핑", "세 영역을 한 번에 훑고 필요한 내용만 상세히 확인하세요.")
    clicked: str | None = None
    for col, code in zip(st.columns(3, gap="medium"), PROFILE_ORDER):
        with col:
            if _render_profile_card(code, bundles.get(code), include_draft=can_manage):
                clicked = code
    if clicked:
        st.session_state["hw_briefing_selected_profile"] = clicked
        st.rerun()
    selected = str(st.session_state.get("hw_briefing_selected_profile") or "")
    if selected not in PROFILE_ORDER or not bundles.get(selected):
        selected = next((code for code in PROFILE_ORDER if bundles.get(code)), "")
    if selected and bundles.get(selected):
        _render_profile_detail(repo, selected, bundles[selected], can_manage=can_manage)


def _render_history(repo: BriefingRepository, can_manage: bool) -> None:
    st.markdown("### 과거 브리핑")
    c1, c2 = st.columns([1, 2])
    with c1:
        profile_code = st.selectbox("Profile", options=list(PROFILE_ORDER), format_func=lambda x: PROFILE_LABELS[x])
    with c2:
        keyword = st.text_input("키워드", placeholder="제목이나 이슈 키워드")
    rows = repo.history(profile_code, limit=60, include_draft=can_manage)
    if not rows:
        st.info("저장된 브리핑이 없습니다.")
        return
    keyword_cf = keyword.strip().casefold()
    shown = 0
    for item in rows:
        briefing = item["briefing"]
        revision = item["revision"]
        bundle = repo.bundle_for_date(profile_code, str(briefing.get("briefing_date")), include_draft=can_manage)
        if not bundle:
            continue
        snapshot = bundle.get("snapshot") or {}
        fast = snapshot.get("fast_brief_payload") or {}
        blob = " ".join(str(x.get("title") or "") for x in fast.get("items") or []).casefold()
        if keyword_cf and keyword_cf not in blob:
            continue
        core, light = _counts(bundle)
        status = "공개" if revision.get("publication_status") == "published" else "미리보기"
        with st.container(key=f"hw_briefing_history_{briefing.get('id')}"):
            cols = st.columns([2, 4, 1])
            cols[0].write(str(briefing.get("briefing_date") or ""))
            cols[1].write(str(fast.get("remember_one_sentence") or PROFILE_LABELS[profile_code]))
            cols[2].caption(f"{status} · {core}/{light}")
            if st.button("보기", key=f"hw_briefing_history_open_{briefing.get('id')}"):
                st.session_state["hw_briefing_history_open"] = str(briefing.get("briefing_date"))
                st.rerun()
        shown += 1
    if shown == 0:
        st.info("조건에 맞는 과거 브리핑이 없습니다.")
    open_date = str(st.session_state.get("hw_briefing_history_open") or "")
    if open_date:
        bundle = repo.bundle_for_date(profile_code, open_date, include_draft=can_manage)
        if bundle:
            _render_profile_detail(repo, profile_code, bundle, can_manage=can_manage)


def run() -> None:
    _inject_briefing_styles()
    can_manage = _can_manage()
    try:
        repo = _repo()
        with st.container(key="hw_briefing_hero"):
            left, right = st.columns([5, 1.25], vertical_alignment="center")
            with left:
                st.markdown(
                    '<div class="hw-briefing-eyebrow">HWARANG DAILY INTELLIGENCE</div>'
                    '<h1 class="hw-briefing-title">브리핑 센터</h1>'
                    '<p class="hw-briefing-subtitle">오늘의 중요한 변화를 검증하고, '
                    '업무에 필요한 다음 행동까지 연결합니다.</p>',
                    unsafe_allow_html=True,
                )
            with right:
                if can_manage:
                    st.markdown(
                        '<div style="text-align:right"><span class="hw-briefing-mode">'
                        '<span class="hw-briefing-mode-dot"></span> SHADOW</span></div>',
                        unsafe_allow_html=True,
                    )
                    _render_generate_panel(repo)

        flash = str(st.session_state.pop("hw_briefing_flash", "") or "")
        if flash:
            st.success(flash)

        with st.container(key="hw_briefing_tabs"):
            mode = st.radio(
                "브리핑 보기",
                ["오늘 브리핑", "과거 브리핑"],
                horizontal=True,
                label_visibility="collapsed",
            )
        if mode == "오늘 브리핑":
            _render_today(repo, can_manage)
        else:
            _render_history(repo, can_manage)
    except BriefingRepositoryError as exc:
        st.error("브리핑 데이터를 불러올 수 없습니다.")
        if can_manage:
            st.caption(str(exc))
