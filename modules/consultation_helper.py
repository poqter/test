"""B1-B6: editable, rule-based consultation support."""
import streamlit as st
from .ui_components import page_header
from .workspace_tools import field, session_notice, text

LIFECYCLES={
    "사회초년": ("필수지출과 비상자금", "직장 단체보험과 개인보험의 차이", "지속 가능한 월 보험료"),
    "결혼·가족 형성": ("공동 생활비와 주거부채", "배우자 소득 공백", "중복 보장과 수익자 점검"),
    "자녀 양육": ("양육·교육비 기간", "주 소득자 부재 시 재원", "가족 의료비 부담"),
    "중장년": ("갱신보험료 부담", "은퇴 전 납입 종료 계획", "부모 돌봄과 장기 간병"),
    "은퇴 준비": ("은퇴 후 고정지출", "연금과 가용 현금", "의료·돌봄비와 부채"),
    "은퇴 이후": ("현금흐름 유지", "기존 계약 유지 가능성", "가족과 공유할 청구 절차"),
}
QUESTIONS=("이번 상담에서 가장 먼저 해결하고 싶은 문제는 무엇인가요?", "월 지출 중 조정하기 어려운 항목은 무엇인가요?", "기존 보장의 지급조건과 제외사항을 알고 계신가요?", "소득이 줄면 얼마 동안 어떤 재원으로 생활할 수 있나요?", "현재 보험료를 장기간 유지할 수 있나요?", "설명 중 다시 확인하고 싶은 부분은 무엇인가요?")
SCRIPTS={
    "첫 만남": "오늘은 가입 결정에 앞서 현재 상황과 우선순위를 확인하겠습니다. 원치 않는 정보는 말씀하지 않으셔도 됩니다. 먼저 해결하고 싶은 과제부터 알려주세요.",
    "현황 점검": "현재 계약의 보험료와 보장 조건을 확인하겠습니다. 금액이 같아도 지급 조건은 다를 수 있으므로 약관 기준으로 살펴보겠습니다.",
    "대안 비교": "현 상태 유지안과 변경안을 같은 기준으로 비교하겠습니다. 보험료뿐 아니라 보장 공백, 새 심사, 면책·감액 조건과 해지 시 불이익도 함께 확인하겠습니다.",
    "설명 확인": "제가 설명한 내용을 고객님 말씀으로 어떻게 이해하셨는지 확인해도 될까요? 이해가 어려운 항목은 다시 설명드리겠습니다.",
    "마무리": "오늘 확인한 사실과 추가 확인 사항을 정리하겠습니다. 결정은 충분히 검토한 뒤 하셔도 됩니다. 다음 만남에서 확인할 자료와 일정을 함께 정하겠습니다.",
}
MESSAGES={
    "상담 일정 안내": "안녕하세요. 약속한 상담 일정은 [날짜/시간]입니다. 이번 상담에서는 [주제]를 함께 확인할 예정입니다. 일정 변경이 필요하시면 편한 시간을 알려주세요.",
    "자료 준비 안내": "상담 준비를 위해 [필요 자료]를 확인해 주세요. 주민등록번호·계좌번호 등 불필요한 정보는 가린 자료를 준비해 주시고, 민감한 자료의 전달 방법은 별도로 안내드리겠습니다.",
    "상담 후 요약": "오늘은 [확인한 내용]을 살펴보았습니다. 추가 확인할 사항은 [미확인 항목]입니다. 자료를 확인한 뒤 다시 안내드리겠습니다. 이번 정리는 지급·가입을 확정하는 안내가 아닙니다.",
    "청구 안내": "보험금 청구 준비를 위해 해당 보험사의 공식 안내에서 [청구 유형]의 필요서류를 확인해 주세요. 보장 여부와 지급액은 약관 및 보험사 심사에 따라 결정됩니다.",
    "다음 미팅 확인": "다음 상담에서 [남은 과제]를 확인하려고 합니다. [날짜/시간]에 가능하신지 알려주세요. 궁금한 사항을 미리 남겨주시면 함께 준비하겠습니다.",
}


def build_summary(topic, facts, priorities, pending, next_action):
    return "\n\n".join(f"{label}\n{text(value)}" for label,value in (("상담 주제",topic),("확인한 사실",facts),("고객 우선순위",priorities),("추가 확인 사항",pending),("다음 행동",next_action)))

@st.dialog("고객 전달문 미리보기",width="large")
def preview_message(value):
    st.write(value)
    st.code(value,language=None)
    st.caption("코드 영역의 복사 버튼으로 복사한 뒤 수신 대상과 문구를 확인하세요.")


def run():
    page_header("상담 준비", "상담 도우미", "생애주기·질문·문구·요약을 준비하고 직접 다듬습니다.", "CH")
    session_notice("b_")
    mode=st.radio("준비할 내용",("생애주기 주제","핵심 질문","단계별 스크립트","상황별 메시지","상담 요약","다음 미팅"),horizontal=True,key="b_mode")
    if mode == "생애주기 주제":
        stage=field("selectbox","생애주기","b_lifecycle","사회초년",options=list(LIFECYCLES))
        st.subheader("함께 점검할 주제")
        for item in LIFECYCLES[stage]: st.write("• "+item)
        st.caption("연령이나 가족 형태만으로 상품을 추천하지 않습니다. 실제 상황과 고객의 선택을 먼저 확인하세요.")
    elif mode == "핵심 질문":
        picked=field("multiselect","이번 상담에 사용할 질문","b_questions",list(QUESTIONS[:3]),options=list(QUESTIONS))
        additional=field("text_area","추가 질문","b_extra","",max_chars=1500)
        output="\n".join(f"{i}. {q}" for i,q in enumerate(picked,1)) + ("\n"+additional if additional else "")
        st.text(output or "질문을 선택하세요.")
        st.download_button("질문 목록 내려받기",output.encode("utf-8-sig"),"consultation_questions.txt",key="b_questions_download")
    elif mode == "단계별 스크립트":
        stage=field("selectbox","상담 단계","b_stage","첫 만남",options=list(SCRIPTS))
        value=field("text_area","수정 가능한 진행 문구","b_script_"+stage,SCRIPTS[stage],height=200,max_chars=4000)
        st.code(value,language=None)
        st.caption("기본 문구를 상황에 맞게 수정한 뒤 사용하세요. 자동 발송하지 않습니다.")
    elif mode == "상황별 메시지":
        customer=field("selectbox","고객 유형","b_customer_type","첫 상담 고객",options=["첫 상담 고객","기존 고객","검토 중인 고객","청구 진행 고객"])
        kind=field("selectbox","메시지 유형","b_message_type","상담 일정 안내",options=list(MESSAGES))
        intros={"첫 상담 고객":"처음 인사드립니다. 편하게 궁금한 점을 말씀해 주세요.","기존 고객":"기존 상담 내용을 바탕으로 필요한 사항을 함께 점검하겠습니다.","검토 중인 고객":"검토 중 궁금하신 점이 있으면 알려주세요. 충분히 비교한 뒤 결정하셔도 됩니다.","청구 진행 고객":"청구 준비 과정에서 추가로 확인할 사항을 정리해 안내드립니다."}
        value=field("text_area","메시지 편집","b_message_"+customer+kind,intros[customer]+"\n\n"+MESSAGES[kind],height=200,max_chars=4000)
        if st.button("문구 미리보기 · 복사",key="b_preview"): preview_message(value)
        if "[" in value: st.info("대괄호 안의 항목을 바꾸고 수신 대상·내용을 직접 확인한 뒤 사용하세요.")
        st.download_button("메시지 텍스트 내려받기",value.encode("utf-8-sig"),"consultation_message.txt",key="b_message_download")
    elif mode == "상담 요약":
        values=[]
        for key,label in (("topic","주제"),("facts","확인한 사실"),("priorities","우선순위"),("pending","미확인 사항"),("next","다음 행동")):
            values.append(field("text_area",label,"b_summary_"+key,"",max_chars=1500))
        if st.button("입력 내용으로 요약 초안 만들기",key="b_build_summary"):
            generated=build_summary(*values)
            st.session_state["b_summary_edit"]=generated
            st.session_state["_ws_b_summary_edit"]=generated
        summary=field("text_area","최종 요약 직접 편집","b_summary_edit","",height=300,max_chars=10000)
        st.download_button("최종 요약 내려받기",summary.encode("utf-8-sig"),"consultation_summary.txt",disabled=not summary.strip(),key="b_summary_download")
    else:
        items=("미확인 약관·지급조건 정리","고객이 원한 추가 질문 확인","개인정보를 가린 자료 준비","비교안의 가정과 단위 확인","다음 일정과 준비사항 합의")
        completed=[]
        for i,item in enumerate(items):
            if field("checkbox",item,f"b_meeting_{i}",False): completed.append(item)
        action=field("text_area","다음 미팅 메모 (개인정보 제외)","b_meeting_note","",max_chars=2000)
        st.progress(len(completed)/len(items),text=f"준비 {len(completed)}/{len(items)}")
        output="\n".join(("[완료] " if item in completed else "[미완료] ")+item for item in items)+"\n\n"+action
        st.download_button("미팅 체크리스트 내려받기",output.encode("utf-8-sig"),"next_meeting.txt",key="b_meeting_download")
