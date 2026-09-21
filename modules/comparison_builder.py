"""C1-C6: independent typed comparison builder with factual exports."""
from decimal import Decimal, InvalidOperation
import pandas as pd
import streamlit as st
from .ui_components import page_header
from .workspace_tools import downloads, field, session_notice, text

DEFAULT_ROWS=[
    {"항목":"월 보험료", "유형":"금액", "단위":"원", "변경 전":"100000", "변경 후":"90000", "확인 메모":"동일 납입 주기인지 확인"},
    {"항목":"보장기간", "유형":"문자", "단위":"", "변경 전":"", "변경 후":"", "확인 메모":"약관 기준 직접 입력"},
]

def commit_editor(widget_key):
    """Apply Streamlit's delta against an immutable base, once per callback."""
    base=st.session_state["c_base"].copy()
    patch=st.session_state.get(widget_key,{})
    for index,values in patch.get("edited_rows",{}).items():
        for column,value in values.items(): base.at[int(index),column]=value
    base=base.drop(index=patch.get("deleted_rows",[]),errors="ignore")
    if patch.get("added_rows"):
        base=pd.concat([base,pd.DataFrame(patch["added_rows"])],ignore_index=True)
    st.session_state["c_rows"]=base.fillna("").reset_index(drop=True)

def close_template():
    st.session_state['c_template_visible'] = False

@st.dialog("비교표 템플릿 선택", on_dismiss=close_template)
def template_dialog():
    choice=st.radio("시작 양식",["보험 조건 비교","월 지출 비교","빈 비교표"],key="c_template_choice")
    st.caption("적용하면 현재 비교항목이 교체됩니다. 필요한 자료는 먼저 내려받으세요.")
    if st.button("이 양식으로 항목 교체",key="c_template_apply",type="primary"):
        names={"보험 조건 비교":["월 보험료","진단비","보장기간","면책·감액"],"월 지출 비교":["월 고정지출","월 변동지출"],"빈 비교표":[""]}[choice]
        st.session_state["c_rows"]=pd.DataFrame([{"항목":n,"유형":"문자","단위":"","변경 전":"","변경 후":"","확인 메모":""} for n in names])
        st.session_state["c_editor_revision"]=st.session_state.get("c_editor_revision",0)+1
        st.session_state['c_template_visible']=False
        st.session_state["c_reviewed"]=False
        st.session_state.pop("_ws_c_reviewed",None)
        st.rerun()


def parse_number(value):
    cleaned=text(value,100).replace(",","").strip()
    try: result=Decimal(cleaned)
    except InvalidOperation: raise ValueError("숫자 유형에는 숫자만 입력하세요. 쉼표는 사용할 수 있습니다.")
    if not result.is_finite() or abs(result)>Decimal("1e15"):
        raise ValueError("유한한 숫자를 ±1,000조 범위 안에서 입력하세요.")
    return result


def compare_rows(records):
    if len(records)>40: raise ValueError("비교 항목은 40개 이하로 작성하세요.")
    rows=[]; summary=[]
    for index,record in enumerate(records,1):
        label=text(record.get("항목"),100).strip()
        if not label: continue
        kind=text(record.get("유형")); unit=text(record.get("단위"),20)
        before=text(record.get("변경 전"),500).strip(); after=text(record.get("변경 후"),500).strip()
        note=text(record.get("확인 메모"),500)
        if not before or not after: delta="미입력"; sentence=f"{label}: 양쪽 값을 확인해야 합니다."
        elif kind=="문자":
            delta="동일" if before==after else "내용 변경"
            sentence=f"{label}: {delta}."
        elif kind in ("금액","숫자","비율(%)"):
            try: left,right=parse_number(before),parse_number(after)
            except ValueError as exc: raise ValueError(f"{index}행 {label}: {exc}")
            diff=right-left
            suffix="%p" if kind=="비율(%)" else unit
            delta=f"{diff:+,.2f}{suffix}"
            sentence=f"{label}: {left:,.2f} → {right:,.2f}, 차이 {delta}."
        else: raise ValueError(f"{index}행의 유형을 선택하세요.")
        rows.append([label,kind,unit,before,after,delta,note]); summary.append(sentence)
    return rows,summary


def run():
    page_header("리모델링·비교","범용 비교표 제작","보험료·보장·조건을 같은 기준으로 직접 비교하고 설명자료로 내보냅니다.","CB")
    session_notice("c_")
    if st.button("시작 양식 선택",key="c_template_open"):
        st.session_state['c_template_visible']=True
    if st.session_state.get('c_template_visible'):
        template_dialog()
    title=field("text_input","자료 제목","c_title","변경 전후 비교",max_chars=100)
    context=field("text_area","비교 기준과 가정 (개인정보 제외)","c_context","동일한 납입주기·보장조건인지 확인하세요. 입력값을 바탕으로 한 상담 참고자료입니다.",max_chars=2000)
    st.caption("금액/숫자/비율은 숫자만 입력하고 단위는 별도 칸에 적습니다. 비율 차이는 %p로 표시합니다. 빈 항목명은 제외됩니다. 행은 최대 40개입니다.")
    st.session_state.setdefault("c_rows",pd.DataFrame(DEFAULT_ROWS))
    editor_key=f'c_editor_{st.session_state.get("c_editor_revision",0)}'
    if editor_key not in st.session_state:
        st.session_state["c_base"]=st.session_state["c_rows"].copy()
    edited=st.data_editor(st.session_state["c_base"],num_rows="dynamic",hide_index=True,use_container_width=True,key=editor_key,on_change=commit_editor,args=(editor_key,),column_config={
        "항목":st.column_config.TextColumn(max_chars=100),
        "유형":st.column_config.SelectboxColumn(options=["금액","숫자","비율(%)","문자"],required=True),
        "단위":st.column_config.TextColumn(max_chars=20),
        "변경 전":st.column_config.TextColumn(max_chars=500),
        "변경 후":st.column_config.TextColumn(max_chars=500),
        "확인 메모":st.column_config.TextColumn(max_chars=500),
    })
    # Widget deletion on navigation must not remove the durable, session-local draft.
    try: rows,summary=compare_rows(edited.fillna("").to_dict("records"))
    except ValueError as exc:
        st.error(str(exc)); return
    if not rows: st.info("항목명을 입력해 비교표를 시작하세요."); return
    headers=["항목","유형","단위","변경 전","변경 후","차이","확인 메모"]
    st.subheader("변경 전후 미리보기")
    st.dataframe(pd.DataFrame(rows,columns=headers),hide_index=True,use_container_width=True)
    st.subheader("입력값 자동 요약")
    st.text("\n".join(summary))
    st.caption("금액 증감과 문자 변경만 설명합니다. 보장 확대·축소, 상품 우열이나 가입 적합성을 자동 판정하지 않습니다.")
    if st.button("자동 요약을 고객 설명 초안으로 가져오기",key="c_make_explanation"):
        explanation="\n".join(summary)+"\n\n실제 지급조건, 면책·감액, 갱신, 해지 시 불이익은 약관과 공식 설명서를 함께 확인해야 합니다."
        st.session_state["c_explanation"]=explanation; st.session_state["_ws_c_explanation"]=explanation
    explanation=field("text_area","고객 설명 문구 편집","c_explanation","",height=180,max_chars=6000)
    checked=field("checkbox","입력 단위와 사실관계를 확인했습니다","c_reviewed",False)
    if checked:
        downloads("comparison",title,headers,rows,context+"\n\n"+explanation)
    else: st.info("단위·조건을 확인하고 체크하면 Excel·PDF 다운로드가 표시됩니다.")
