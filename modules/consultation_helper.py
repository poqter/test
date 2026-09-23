"""Session-only consultation studio. No customer persistence or paid APIs."""
from datetime import date

import streamlit as st

from .content_repository import load_content
from .consultation_documents import (
    NOTE, build_summary, build_proposal, document_pdf, fingerprint, message_draft, unresolved,
)
from .ui_components import page_header
from .workspace_tools import field, session_notice

MODES = ("생애주기 주제", "핵심 질문", "단계별 스크립트", "상황별 메시지", "상담 요약", "다음 미팅", "제안서·PDF")


def profile():
    return {"goal": st.session_state.get("b_goal", "보장 점검"),
            "visit": st.session_state.get("b_visit", "첫 상담"),
            "lifecycle": st.session_state.get("b_lifecycle", "사회초년")}


def summary_source():
    return [st.session_state.get("b_summary_" + key, "")
            for key in ("topic", "facts", "priorities", "pending", "next")]


def proposal_source():
    return [profile(), summary_source(), st.session_state.get("b_summary_edit", ""),
            *[st.session_state.get("b_proposal_" + key, "") for key in ("direction", "cautions", "next")]]


def current(kind, source):
    return st.session_state.get("b_" + kind + "_source") == fingerprint(source)


def install_draft(kind, value, source):
    key = "b_" + kind + "_edit"
    st.session_state[key] = value
    st.session_state["_ws_" + key] = value
    st.session_state["b_" + kind + "_source"] = fingerprint(source)
    st.session_state.pop("b_" + kind + "_review", None)


@st.dialog("현재 초안을 바꿀까요?")
def replace_draft(kind, value, source):
    st.write("직접 수정한 내용을 포함해 현재 초안을 새 입력 내용으로 교체합니다. 취소하거나 창을 닫으면 현재 내용이 유지됩니다.")
    if st.button("새 초안으로 교체", key="b_replace_confirm", on_click=install_draft, args=(kind, value, source)):
        st.rerun()
    if st.button("취소", key="b_replace_cancel"):
        st.rerun()


def generate(kind, value, source):
    if st.session_state.get("b_" + kind + "_edit", "").strip():
        replace_draft(kind, value, source)
    else:
        install_draft(kind, value, source)


@st.dialog("고객 전달문 미리보기", width="large")
def preview_message(value):
    st.text(value)
    st.code(value, language=None)
    st.caption("복사 버튼으로 복사한 뒤 전달 대상을 직접 확인하세요. 자동 발송하지 않습니다.")


def export_document(kind, title, body, *, valid=True, pdf=True):
    """Review tokens bind the exact text, source validity and export options."""
    include_alias = field("checkbox", "상담 구분명을 결과물에 포함", "b_" + kind + "_include_alias", False)
    alias = st.session_state.get("b_alias", "") if include_alias else ""
    prepared = date.today().isoformat()
    token = fingerprint([kind, body, valid, alias, prepared])
    ready = valid and bool(body.strip()) and not unresolved(body)
    if unresolved(body):
        st.info("대괄호의 임시 항목을 실제 전달 문구로 바꾼 뒤 검토해 주세요.")
    if st.button("내용 확인 · 전달 준비 완료", key="b_" + kind + "_approve", disabled=not ready):
        st.session_state["b_" + kind + "_review"] = token
    reviewed = ready and st.session_state.get("b_" + kind + "_review") == token
    if not reviewed:
        st.caption("문구와 포함 정보를 확인하면 내려받기가 활성화됩니다. 수정 시 다시 확인해야 합니다.")
    content = title + "\n작성일 " + prepared + ("\n상담 구분명: " + alias if alias else "") + "\n\n" + body + "\n\n" + NOTE
    st.download_button("TXT 내려받기", content.encode("utf-8-sig") if reviewed else b"",
                       "consultation_" + kind + ".txt", disabled=not reviewed, key="b_" + kind + "_download")
    if pdf and reviewed:
        try:
            payload = document_pdf(title, body, prepared_on=prepared, customer_label=alias)
        except Exception:
            st.warning("PDF를 만들지 못했습니다. 본문 길이와 설치된 글꼴을 확인하거나 TXT를 이용해 주세요.")
        else:
            st.download_button("PDF 내려받기", payload, "consultation_" + kind + ".pdf",
                               "application/pdf", key="b_" + kind + "_pdf")


def checklist(items, prefix):
    completed = [item for i, item in enumerate(items) if field("checkbox", item, f"b_{prefix}_{i}", False)]
    st.progress(len(completed) / len(items), text=f"확인 {len(completed)}/{len(items)}")
    return completed


def run():
    topics = load_content("consultation_topics")
    scripts = load_content("consultation_scripts")
    messages = load_content("message_templates")
    checks = load_content("checklists")
    page_header("상담·제안서", "상담·제안서 스튜디오", "준비 → 상담 → 요약 → 제안서. 직접 검토한 내용으로 전달자료를 만드세요.", "CH")
    session_notice("b_")
    with st.expander("이번 상담 설정"):
        field("selectbox", "상담 구분", "b_visit", "첫 상담", options=topics["visits"])
        field("selectbox", "상담 목표", "b_goal", "보장 점검", options=topics["goals"])
        field("text_input", "상담 구분명 (선택 · 예: 상담 A)", "b_alias", "", max_chars=40)
        st.caption("구분명은 기본적으로 출력하지 않습니다. 본문에 직접 입력한 정보는 출력에 포함됩니다.")
    mode = st.radio("준비할 내용", MODES, horizontal=True, key="b_mode")
    if mode == "생애주기 주제":
        stage = field("selectbox", "생애주기", "b_lifecycle", "사회초년", options=list(topics["lifecycles"]))
        st.subheader("함께 점검할 주제")
        for item in topics["lifecycles"][stage]:
            st.write("• " + item)
        st.caption("실제 상황과 고객의 선택을 먼저 확인하세요. 생애주기만으로 상품을 추천하지 않습니다.")
        st.subheader("상담 전 준비")
        checklist(checks["preparation"], "preparation")
    elif mode == "핵심 질문":
        picked = field("multiselect", "이번 상담에 사용할 질문", "b_questions", topics["questions"][:3], options=topics["questions"])
        extra = field("text_area", "추가 질문", "b_extra", "", max_chars=1500)
        output = "\n".join(f"{i}. {q}" for i, q in enumerate(picked, 1)) + ("\n" + extra if extra else "")
        st.text(output or "질문을 선택하세요.")
        st.download_button("질문 목록 내려받기", output.encode("utf-8-sig"), "consultation_questions.txt", disabled=not output.strip(), key="b_questions_download")
    elif mode == "단계별 스크립트":
        stage = field("selectbox", "상담 단계", "b_stage", "첫 만남", options=list(scripts["scripts"]))
        value = field("text_area", "수정 가능한 진행 문구", "b_script_" + stage, scripts["scripts"][stage], height=200, max_chars=4000)
        st.code(value, language=None)
        reaction = field("selectbox", "고객 반응에 이어갈 질문", "b_reaction", next(iter(scripts["reactions"])), options=list(scripts["reactions"]))
        st.info(scripts["reactions"][reaction])
        with st.expander("설명 후 확인 체크리스트"):
            checklist(checks["explanation"], "explanation")
            st.caption(checks["source"])
    elif mode == "상황별 메시지":
        customer = field("selectbox", "고객 유형", "b_customer_type", "첫 상담 고객", options=list(messages["intros"]))
        kind = field("selectbox", "메시지 유형", "b_message_type", "상담 일정 안내", options=list(messages["messages"]))
        channel = field("radio", "전달 형식", "b_channel", "문자", options=["문자", "이메일"], horizontal=True)
        key = "b_message_" + customer + kind + ("_email" if channel == "이메일" else "")
        value = field("text_area", "메시지 편집", key, message_draft(messages["intros"][customer], messages["messages"][kind], channel, kind), height=240, max_chars=4000)
        if st.button("문구 미리보기 · 복사", key="b_preview"):
            preview_message(value)
        export_document("message", "고객 전달문", value, pdf=False)
    elif mode == "상담 요약":
        values = [field("text_area", label, "b_summary_" + key, "", max_chars=1500) for key, label in
                  (("topic", "주제"), ("facts", "확인한 사실"), ("priorities", "우선순위"), ("pending", "미확인 사항"), ("next", "다음 행동"))]
        ready = all(values[i].strip() for i in (0, 1, 4))
        if not ready:
            st.info("주제·확인한 사실·다음 행동을 입력하면 요약 초안을 만들 수 있습니다.")
        if st.button("입력 내용으로 요약 초안 만들기", key="b_build_summary", disabled=not ready):
            generate("summary", build_summary(*values), values)
        summary = field("text_area", "최종 요약 직접 편집", "b_summary_edit", "", height=320, max_chars=10000)
        valid = ready and current("summary", values)
        if summary and not valid:
            st.warning("원본 입력이 바뀌었습니다. 요약 초안을 다시 만든 뒤 확인해 주세요. 현재 편집 내용은 유지됩니다.")
        export_document("summary", "상담 요약", summary, valid=valid)
    elif mode == "다음 미팅":
        items = checks["next_meeting"]
        completed = checklist(items, "meeting")
        note = field("text_area", "다음 미팅 메모", "b_meeting_note", "", max_chars=2000)
        output = "\n".join(("완료: " if item in completed else "미완료: ") + item for item in items) + "\n\n" + note
        st.download_button("미팅 체크리스트 내려받기", output.encode("utf-8-sig"), "next_meeting.txt", key="b_meeting_download")
    else:
        summary = st.session_state.get("b_summary_edit", "")
        summary_ok = bool(summary.strip()) and current("summary", summary_source())
        st.subheader("검토 방향을 고객용 자료로 정리")
        if not summary_ok:
            st.info("먼저 상담 요약에서 현재 입력에 맞는 요약을 만들어 주세요.")
        with st.expander("사용할 상담 요약", expanded=bool(summary)):
            st.text(summary or "작성된 요약이 없습니다.")
        direction = field("text_area", "함께 검토할 방향", "b_proposal_direction", "", max_chars=2000)
        cautions = field("text_area", "주의사항·확인할 조건", "b_proposal_cautions", "", max_chars=2000)
        next_action = field("text_area", "다음 상담 준비", "b_proposal_next", "", max_chars=1500)
        source = proposal_source()
        ready = summary_ok and bool(direction.strip()) and bool(next_action.strip())
        if st.button("제안서 초안 만들기", key="b_build_proposal", disabled=not ready):
            generate("proposal", build_proposal(profile(), summary, direction, cautions, next_action), source)
        value = field("text_area", "최종 제안서 직접 편집", "b_proposal_edit", "", height=420, max_chars=18000)
        valid = ready and current("proposal", source)
        if value and not valid:
            st.warning("요약이나 검토 조건이 바뀌었습니다. 제안서 초안을 다시 만든 뒤 확인해 주세요.")
        st.caption("상품 자동 추천이 아닌 상담 정리 자료입니다. 입력 사실·가정·주의사항을 직접 검토하세요.")
        export_document("proposal", "상담 제안서", value, valid=valid)
    with st.expander("기본 문구 안내"):
        st.caption(f"자체 작성 기본 문구 · 편집일 {topics['edited_at']} · 회사 승인 문구나 최신 약관의 대체 자료가 아닙니다.")
