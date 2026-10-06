from __future__ import annotations

from datetime import date, datetime
import html
from typing import Any, Callable

import streamlit as st

from .repository import BriefingRepository, BriefingRepositoryError
from .runtime import PROFILE_LABELS, BriefingRunError, generate_and_store_briefings


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
        return dt.astimezone().strftime("%m.%d %H:%M")
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
    label = PROFILE_LABELS[code]
    with st.container(key=f"hw_briefing_card_{code.lower()}"):
        st.caption(PROFILE_SHORT[code])
        st.subheader(label.replace(" 브리핑", ""))
        if not bundle:
            if code == "MARKET":
                st.write("시장 데이터 Source가 연결되면 이곳에서 확인할 수 있습니다.")
            else:
                st.write("아직 확인 가능한 브리핑이 없습니다.")
            st.caption("상태 · 준비 중")
        else:
            revision = bundle.get("revision") or {}
            snapshot = bundle.get("snapshot") or {}
            fast = snapshot.get("fast_brief_payload") or {}
            core, light = _counts(bundle)
            state = "공개" if revision.get("publication_status") == "published" else "관리자 미리보기"
            st.write(str(fast.get("remember_one_sentence") or "오늘의 주요 변화를 확인하세요."))
            st.caption(f"{state} · 핵심 {core} · 참고 {light} · {_fmt_dt(revision.get('generated_at'))}")
        return st.button("브리핑 보기 →", key=f"hw_briefing_open_{code}", use_container_width=True, disabled=not bool(bundle))


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
        if url:
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


def _render_issue(repo: BriefingRepository, issue: dict[str, Any], action: dict[str, Any] | None, bundle: dict[str, Any]) -> None:
    tier = str(issue.get("selection_tier") or "")
    title = str(issue.get("title") or "이슈")
    prefix = "핵심" if tier == "core" else "참고"
    with st.expander(f"[{prefix}] {title}", expanded=False):
        cols = st.columns(3)
        cols[0].metric("카테고리", str(issue.get("category") or "-"))
        cols[1].metric("상태", str(issue.get("issue_status") or "-"))
        cols[2].metric("근거", str(issue.get("evidence_status") or "-"))
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


def _render_profile_detail(repo: BriefingRepository, code: str, bundle: dict[str, Any], *, can_manage: bool) -> None:
    briefing = bundle.get("briefing") or {}
    revision = bundle.get("revision") or {}
    snapshot = bundle.get("snapshot") or {}
    fast = snapshot.get("fast_brief_payload") or {}
    today = snapshot.get("today_action_payload") or {}
    issues = bundle.get("issues") or []
    actions = {str(row.get("issue_id")): row for row in bundle.get("actions") or [] if row.get("issue_id")}

    st.divider()
    h1, h2 = st.columns([4, 1], vertical_alignment="center")
    with h1:
        st.subheader(PROFILE_LABELS[code])
        status = "공개" if revision.get("publication_status") == "published" else "관리자 미리보기"
        st.caption(f"{briefing.get('briefing_date')} · {status} · 생성 {_fmt_dt(revision.get('generated_at'))} · Coverage {revision.get('coverage_status')}")
    with h2:
        if can_manage and revision.get("publication_status") != "published":
            can_publish = revision.get("validation_status") == "ok" and revision.get("coverage_status") != "insufficient"
            if st.button("공개하기", key=f"hw_briefing_publish_{revision.get('id')}", type="primary", use_container_width=True, disabled=not can_publish):
                try:
                    actor = str((st.session_state.get("login_profile") or {}).get("id") or "") or None
                    repo.publish_revision(str(briefing["id"]), str(revision["id"]), actor_user_id=actor)
                    st.success("브리핑을 공개했습니다.")
                    st.rerun()
                except BriefingRepositoryError as exc:
                    st.error(str(exc))

    st.markdown("### 오늘 5분 FAST BRIEF")
    st.info(str(fast.get("remember_one_sentence") or "오늘의 핵심 변화를 확인하세요."))
    for item in (fast.get("items") or [])[:5]:
        st.write("• " + str(item.get("title") or ""))

    st.markdown("### TODAY ACTION")
    action_cols = st.columns(3)
    for col, key in zip(action_cols, ("review_now", "reference_today", "watch")):
        with col:
            st.markdown(f"**{ACTION_LABELS[key]}**")
            rows = today.get(key) or []
            if not rows:
                st.caption("해당 항목 없음")
            for row in rows[:4]:
                st.write("• " + str(row.get("title") or ""))

    core = [row for row in issues if row.get("selection_tier") == "core"]
    light = [row for row in issues if row.get("selection_tier") == "light_digest"]
    st.markdown("### 핵심 이슈")
    if not core:
        st.caption("현재 검증된 핵심 이슈가 없습니다.")
    for issue in core:
        _render_issue(repo, issue, actions.get(str(issue.get("id"))), bundle)

    if light:
        st.markdown("### 참고할 소식")
        for issue in light:
            _render_issue(repo, issue, actions.get(str(issue.get("id"))), bundle)


def _render_generate_panel(repo: BriefingRepository) -> None:
    if not _can_manage():
        return
    with st.expander("콘텐츠 관리", expanded=False):
        st.caption("현재 초기 운영모드는 shadow입니다. 생성 결과는 관리자 미리보기로 저장되며 자동 공개되지 않습니다.")
        st.caption("INSURANCE·NEWS는 한 번의 Shared Discovery에서 함께 생성되어 불필요한 검색 호출을 반복하지 않습니다.")
        if st.button("오늘 브리핑 생성", key="hw_briefing_generate_today", type="primary", use_container_width=True):
            actor = str((st.session_state.get("login_profile") or {}).get("id") or "") or None
            with st.spinner("오늘의 이슈를 수집·검증·분석하고 있습니다…"):
                try:
                    result = generate_and_store_briefings(actor_user_id=actor, repository=repo)
                    summary = ", ".join(
                        f"{row.profile_code} 핵심 {row.core_count} / 참고 {row.light_count}"
                        for row in result.profiles
                    )
                    st.success(f"생성이 완료되었습니다. {summary}")
                    st.caption(f"Shared Search Actions {result.search_actions} · 후보 {result.candidate_count} · Event {result.event_count}")
                    st.session_state.pop("hw_briefing_selected_profile", None)
                    st.rerun()
                except (BriefingRunError, BriefingRepositoryError, ValueError) as exc:
                    st.error("브리핑 생성에 실패했습니다.")
                    st.caption(str(exc))


def _render_today(repo: BriefingRepository, can_manage: bool) -> None:
    _render_generate_panel(repo)
    bundles = {code: repo.latest_bundle(code, include_draft=can_manage) for code in PROFILE_ORDER}
    st.markdown("### 오늘의 브리핑")
    st.caption("세 영역을 한 번에 훑고, 필요한 브리핑만 상세하게 확인하세요.")
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
    st.markdown("# 브리핑 센터")
    st.caption("오늘의 중요한 변화를 검증하고, 업무에 필요한 다음 행동까지 연결합니다.")
    can_manage = _can_manage()
    try:
        repo = _repo()
        mode = st.radio("브리핑 보기", ["오늘 브리핑", "과거 브리핑"], horizontal=True, label_visibility="collapsed")
        if mode == "오늘 브리핑":
            _render_today(repo, can_manage)
        else:
            _render_history(repo, can_manage)
    except BriefingRepositoryError as exc:
        st.error("브리핑 데이터를 불러올 수 없습니다.")
        if can_manage:
            st.caption(str(exc))
