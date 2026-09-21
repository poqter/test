"""E28–E34. Local editorial learning content; no customer records."""
import streamlit as st
from .ui_components import page_header
from .workspace_tools import field, session_notice, source_notes

TERMS = {
    "보험계약자": "보험회사와 계약을 체결하고 보험료 납입 등 계약상 의무를 부담하는 사람입니다.",
    "피보험자": "보험사고 판단의 대상이 되는 사람입니다. 계약자·수익자와 다를 수 있습니다.",
    "보험수익자": "보험사고 발생 시 약관에 따라 보험금을 청구하여 받을 수 있는 사람입니다.",
    "보험나이": "일반적으로 계약일의 만 나이에서 6개월 미만은 버리고 6개월 이상은 1년으로 계산합니다. 개별 약관의 나이 기준을 확인합니다.",
    "상령일": "신규 가입 시 적용 보험나이가 한 살 증가하는 시점을 일컫는 표현입니다. 기존 계약의 계약해당일과 구분합니다.",
    "면책기간": "약관에서 정한 특정 보장을 하지 않는 기간입니다. 모든 담보에 동일하게 적용되는 것은 아닙니다.",
    "감액기간": "약관상 정해진 기간에 사고가 발생하면 보험금의 일부만 지급하는 조건입니다.",
    "갱신형": "일정 주기마다 계약을 갱신하며 보험료 등이 변경될 수 있는 구조입니다. 갱신 가능 나이와 조건을 확인합니다.",
    "비갱신형": "정해진 납입기간 동안 보험료가 유지되는 구조를 말합니다. 보장기간과 납입기간은 서로 다를 수 있습니다.",
    "해지환급금": "계약을 해지할 때 약관과 경과기간에 따라 지급되는 금액입니다. 납입보험료보다 적거나 없을 수 있습니다.",
    "자기부담금": "보장 대상 손해 중 가입자가 부담하는 부분입니다. 정액·비율·최소금액 등 약관 조건을 확인합니다.",
    "비례보상": "실제 손해를 보상하는 담보가 중복된 경우 각 계약의 책임에 따라 나누어 보상하는 방식입니다.",
    "정액보상": "약관상 지급사유를 충족하면 약정한 금액을 지급하는 방식입니다. 실제 지출과 반드시 같지는 않습니다.",
    "납입면제": "약관의 특정 사유를 충족하면 대상 보험료의 납입을 면제하는 제도입니다. 면제 대상 특약과 기간을 확인합니다.",
    "고지의무": "청약 시 보험회사가 질문한 중요한 사항을 사실대로 알리는 의무입니다. 설계사에게 말한 것만으로 충분한지 확인해야 합니다.",
    "부담보": "특정 부위·질병 등에 관한 보장을 일정 기간 또는 전 기간 제한하는 인수 조건입니다.",
}
CHECKS = {
    "불완전판매 예방": ("상담 목적과 월 보험료 부담 가능성을 확인했다", "고객이 원한 보장과 제안한 보장의 차이를 설명했다", "고지 질문을 고객이 직접 확인하도록 안내했다", "기존 계약 변경 시 손실·새 심사·보장 공백을 비교했다", "불확실한 환급금·수익·보험금을 확정적으로 말하지 않았다", "고객의 자발적 선택과 추가 질문을 확인했다"),
    "설명의무 확인": ("주계약·특약의 주요 지급사유를 설명했다", "보험료·납입기간·보장기간·갱신 조건을 설명했다", "면책·감액·자기부담·주요 지급제한을 설명했다", "해지환급금과 중도해지 불이익을 설명했다", "청약철회·해지 관련 권리와 절차를 공식 자료로 확인했다", "고객의 이해 여부를 확인하고 회사의 필수 절차를 이행했다"),
}
GUIDES = {
    "기존 보장 점검": ("보장 분석 도우미", "analyzer", "원본을 확인하고 주요 보장과 지급조건을 검토합니다."),
    "보험료 부담 조정": ("보험 리모델링", "remodeling", "유지안과 변경안의 비용·보장 공백을 함께 비교합니다."),
    "보험금 청구 준비": ("보험금 청구 가이드", "insurance_claim_guide", "사고 유형과 회사별 공식 서류를 확인합니다."),
    "생활비 공백 점검": ("간편 계산기", "quick_calculators", "공백 기간과 가용자금을 가정하여 부족액을 계산합니다."),
    "설명자료 만들기": ("고객용 비교표 제작기", "comparison_builder", "동일 조건으로 구성한 비교표를 검토한 뒤 출력합니다."),
    "첫 상담 준비": ("상담 지원 도구", "consultation_helper", "핵심 질문과 생애주기별 주제를 정리합니다."),
}
SCENARIOS = (
    ("보험료가 부담돼서 기존 보험을 모두 해지하고 싶다고 합니다.", ["즉시 해지를 권유한다", "유지 가능 예산과 기존 보장·환급금·새 심사를 먼저 비교한다", "새 보험료만 보여준다"], 1, "유지·감액·변경안의 장단점을 함께 검토하고 보장 공백과 새 심사 조건을 먼저 확인합니다."),
    ("고객이 약 복용 이력을 말했지만 청약서에는 쓰지 않아도 되냐고 묻습니다.", ["말로 들었으니 괜찮다고 한다", "가입부터 진행한다", "청약 질문을 함께 확인하고 사실대로 답변하도록 안내한다"], 2, "질문 내용과 기간을 확인하고 고객이 사실대로 작성하게 안내합니다. 고지 누락을 유도하지 않습니다."),
    ("고객이 내용을 이해하지 못했지만 서명을 하겠다고 합니다.", ["서명을 먼저 받는다", "쉬운 말로 다시 설명하고 이해한 내용을 확인한다", "요약 문자로 대신한다"], 1, "중요 조건을 다시 설명하고 이해 여부를 확인합니다. 서명만으로 설명 과정이 대체되지는 않습니다."),
)
QUIZZES = (
    ("실손보험이 두 개면 실제 의료비의 두 배를 항상 받나요?", ["항상 두 배", "실제 보상대상 손해 범위에서 계약별 비례보상을 확인", "가입 순서가 빠른 보험만 지급"], 1, "실손형은 실제 손해 보상 원칙에 따라 중복 가입 시 비례보상 여부를 확인합니다."),
    ("진단서가 있으면 모든 진단비가 확정되나요?", ["확정된다", "진단명만 같으면 된다", "약관의 진단 정의·확정 방법·제한 조건을 확인해야 한다"], 2, "진단서 자체만으로 지급을 확정하지 않습니다. 계약별 지급사유와 필요한 근거서류를 확인합니다."),
    ("청구서류를 안내할 때 가장 적절한 행동은?", ["모든 회사에 같은 서류를 확정 안내", "회사·담보·사고 유형의 공식 안내를 확인", "진료비 영수증만 요청"], 1, "기본서류와 추가서류는 계약·사고·회사별로 달라질 수 있습니다."),
)
FAQ = {
    "이 체크리스트만 완료하면 법적 의무가 모두 충족되나요?": "아닙니다. 일반적인 상담 준비용 점검표입니다. 실제 상품·거래 상황과 회사 필수 절차에 맞는 공식 자료를 함께 확인해야 합니다.",
    "연습 결과는 저장되나요?": "이 페이지는 현재 세션에서만 연습 결과를 사용합니다. 고객정보를 입력하지 않고 가상 사례로 연습하세요.",
    "고객 자료 없이 상담 연습이 가능한가요?": "가능합니다. 제공된 가상 시나리오와 질문·해설을 사용합니다.",
    "진단비와 치료비는 같은 보장인가요?": "지급사유가 다를 수 있습니다. 진단 확정에 지급하는 담보와 특정 치료 시행을 요건으로 하는 담보를 구분하여 약관을 확인합니다.",
    "실손 전환은 보험료가 저렴하면 유리한가요?": "보험료뿐 아니라 자기부담·보장 제외·향후 조건과 현재 계약을 함께 비교해야 합니다.",
}

@st.dialog("학습 해설")
def answer_dialog(correct, explanation):
    (st.success if correct else st.info)("맞게 이해하셨습니다." if correct else "판단 근거를 다시 살펴보세요.")
    st.write(explanation)
    st.caption("일반 교육용 가상 사례이며 특정 보험금 지급이나 가입을 확정하지 않습니다.")

def run():
    page_header("교육·체크리스트", "교육·체크리스트 센터", "공통 용어와 상담 절차를 점검하고 가상 사례로 연습합니다.", "ED")
    session_notice("e_")
    mode=st.selectbox("학습할 내용",["보험용어 검색",*CHECKS,"상담유형별 권장 도구","신입 FP 상담 시뮬레이션","보험금 청구 사례 퀴즈","자주 묻는 질문"],key="e_mode")
    if mode=="보험용어 검색":
        query=st.text_input("용어 또는 설명 검색",key="e_query").strip()
        matches=[(k,v) for k,v in TERMS.items() if query in k or query in v]
        if not matches: st.info("일치하는 용어가 없습니다. 더 짧은 검색어를 입력하세요.")
        for name,definition in matches:
            with st.expander(name,expanded=bool(query)): st.write(definition)
    elif mode in CHECKS:
        items=CHECKS[mode]; done=[]
        st.info("상담 준비용 일반 체크리스트입니다. 완료 표시가 법적 의무 충족을 보증하지 않습니다.")
        for i,item in enumerate(items):
            done.append(field("checkbox",item,f"e_{mode}_{i}",False))
        st.progress(sum(done)/len(done),text=f"확인 {sum(done)} / {len(done)}")
        output=mode+"\n"+"\n".join(("[확인] " if value else "[미확인] ")+item for item,value in zip(items,done))
        st.download_button("점검 내용 내려받기",output.encode("utf-8-sig"),"consultation_checklist.txt",key="e_check_download")
    elif mode=="상담유형별 권장 도구":
        subject=st.selectbox("상담 유형",list(GUIDES),key="e_type")
        name,app_id,desc=GUIDES[subject]; st.subheader(name); st.write(desc)
        from modules.workbench import save_page_draft
        # Page rights are supplied by the app router, never bypassed here.
        if app_id in st.session_state.get('ws_allowed_ids', []):
            if st.button('추천 도구 열기',key='e_recommended_go',type='primary'):
                save_page_draft('education_center')
                st.session_state['active_app']=app_id
                st.rerun()
        else:
            st.caption('이 도구의 사용 권한은 계정 설정을 따릅니다.')
    elif mode in ("신입 FP 상담 시뮬레이션","보험금 청구 사례 퀴즈"):
        data=SCENARIOS if mode.startswith("신입") else QUIZZES
        prefix="sim" if mode.startswith("신입") else "quiz"
        choice=st.selectbox("연습 사례",range(len(data)),format_func=lambda i:f"사례 {i+1} · {data[i][0]}",key=f"e_{prefix}_case")
        question,options,answer,explanation=data[choice]
        st.subheader(question)
        selected=st.radio("가장 적절한 답변",options,index=None,key=f"e_{prefix}_{choice}_answer")
        if st.button("답변 확인과 해설",disabled=selected is None,key=f"e_{prefix}_submit",type="primary"):
            answer_dialog(selected==options[answer],explanation)
    else:
        query=st.text_input("질문 검색",key="e_faq_search").strip()
        matches=[(q,a) for q,a in FAQ.items() if query in q or query in a]
        for q,a in matches:
            with st.expander(q,expanded=bool(query)): st.write(a)
        if not matches: st.info("검색 결과가 없습니다.")
    source_notes(["보험나이","생명보험협회","손해보험협회"])
