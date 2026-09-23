"""C1-C6: independent typed comparison builder with factual exports."""
from decimal import Decimal, InvalidOperation
import re
from uuid import uuid4
import pandas as pd
import streamlit as st
from .ui_components import page_header
from .workspace_tools import downloads, field, session_notice, text
from .consultation_documents import fingerprint


def ordered_rows(records):
    if len(records)>40: raise ValueError("비교 항목은 40개 이하로 작성하세요.")
    result=[]; seen=set()
    for index,record in enumerate(records):
        row=dict(record)
        identity=str(row.get('row_id') or uuid4().hex)
        if identity in seen: identity=uuid4().hex
        seen.add(identity)
        row.update(row_id=identity,order=index)
        result.append(row)
    return result


def move_row(records,index,direction):
    rows=ordered_rows(records)
    target=index+direction
    if 0<=index<len(rows) and 0<=target<len(rows): rows[index],rows[target]=rows[target],rows[index]
    return ordered_rows(rows)


def period_months(value, unit):
    match=re.fullmatch(r'\s*([+\-]?[\d,.]+)\s*(년|개월|월)?\s*',value)
    if not match: raise ValueError('기간은 10년, 120개월 또는 숫자와 단위로 입력하세요.')
    unit=match.group(2) or unit.strip()
    if unit not in ('년','월','개월'): raise ValueError('기간 단위는 년 또는 개월로 지정하세요.')
    months=parse_number(match.group(1))*(12 if unit=='년' else 1)
    if months<0 or months!=months.to_integral_value(): raise ValueError('기간은 0 이상의 정수 개월로 환산되어야 합니다.')
    return months


def replace_rows(records):
    st.session_state['c_rows']=pd.DataFrame(ordered_rows(records))
    st.session_state['c_editor_revision']=st.session_state.get('c_editor_revision',0)+1
    st.session_state['c_reviewed']=False
    st.session_state.pop('_ws_c_reviewed',None)


def row_action(action,index=0):
    records=st.session_state['c_rows'].to_dict('records')
    if action=='add' and len(records)<40:
        records.append({'항목':'새 항목','유형':'문자','단위':'','변경 전':'','변경 후':'','확인 메모':''})
    elif action=='delete' and records: records.pop(index)
    elif action in ('up','down'): records=move_row(records,index,-1 if action=='up' else 1)
    replace_rows(records)

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
    st.session_state['c_reviewed']=False
    st.session_state.pop('_ws_c_reviewed',None)

def close_template():
    st.session_state['c_template_visible'] = False

@st.dialog("비교표 템플릿 선택", on_dismiss=close_template)
def template_dialog():
    choice=st.radio("시작 양식",["보험 조건 비교","월 지출 비교","빈 비교표"],key="c_template_choice")
    st.caption("적용하면 현재 비교항목이 교체됩니다. 필요한 자료는 먼저 내려받으세요.")
    if st.button("이 양식으로 항목 교체",key="c_template_apply",type="primary"):
        names={"보험 조건 비교":["월 보험료","진단비","보장기간","면책·감액"],"월 지출 비교":["월 고정지출","월 변동지출"],"빈 비교표":[""]}[choice]
        replace_rows([{"항목":n,"유형":"문자","단위":"","변경 전":"","변경 후":"","확인 메모":""} for n in names])
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
        elif kind=="기간":
            try: left,right=period_months(before,unit),period_months(after,unit)
            except ValueError as exc: raise ValueError(f"{index}행 {label}: {exc}")
            delta=f"{right-left:+,.0f}개월"
            sentence=f"{label}: {before} → {after}, 개월 환산 {left:,.0f} → {right:,.0f}, 차이 {delta}."
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


def install_explanation(value,signature):
    st.session_state['c_explanation']=value
    st.session_state['_ws_c_explanation']=value
    st.session_state['c_explanation_source']=signature


@st.dialog('고객 설명 초안을 교체할까요?')
def replace_explanation(value,signature):
    st.write('확인하면 현재 편집 문구를 자동 요약으로 교체합니다.')
    if st.button('교체 확인',key='c_explanation_confirm',on_click=install_explanation,args=(value,signature)): st.rerun()
    if st.button('취소',key='c_explanation_cancel'): st.rerun()


def run():
    page_header("리모델링·비교","범용 비교표 제작","보험료·보장·조건을 같은 기준으로 직접 비교하고 설명자료로 내보냅니다.","CB")
    session_notice("c_")
    if st.button("시작 양식 선택",key="c_template_open"):
        st.session_state['c_template_visible']=True
    if st.session_state.get('c_template_visible'):
        template_dialog()
    title=field("text_input","자료 제목","c_title","변경 전후 비교",max_chars=100)
    context=field("text_area","비교 기준과 가정","c_context","동일한 납입주기·보장조건인지 확인하세요. 입력값을 바탕으로 한 상담 참고자료입니다.",max_chars=2000)
    st.caption("숫자와 0은 미입력과 구분합니다. 기간은 10년·120개월처럼 입력할 수 있습니다. 비율 차이는 %p입니다. 빈 항목명은 제외하며 최대 40행입니다. 기본값은 가상 예시입니다.")
    st.session_state.setdefault("c_rows",pd.DataFrame(ordered_rows(DEFAULT_ROWS)))
    records=st.session_state['c_rows'].fillna('').to_dict('records')
    st.button('항목 추가',key='c_add_row',disabled=len(records)>=40,on_click=row_action,args=('add',))
    if records:
        selected=st.selectbox('순서를 바꿀 항목',list(range(len(records))),format_func=lambda i:f"{i+1}. {records[i].get('항목','')}",key='c_selected_row')
        cols=st.columns(3)
        cols[0].button('위로',key='c_move_up',disabled=selected==0,on_click=row_action,args=('up',selected))
        cols[1].button('아래로',key='c_move_down',disabled=selected==len(records)-1,on_click=row_action,args=('down',selected))
        cols[2].button('선택 항목 삭제',key='c_delete_row',on_click=row_action,args=('delete',selected))
    editor_key=f'c_editor_{st.session_state.get("c_editor_revision",0)}'
    if editor_key not in st.session_state:
        st.session_state["c_base"]=st.session_state["c_rows"].copy()
    edited=st.data_editor(st.session_state["c_base"],num_rows="fixed",hide_index=True,use_container_width=True,key=editor_key,on_change=commit_editor,args=(editor_key,),column_config={
        'row_id':None,'order':None,
        "항목":st.column_config.TextColumn(max_chars=100),
        "유형":st.column_config.SelectboxColumn(options=["금액","숫자","비율(%)","기간","문자"],required=True),
        "단위":st.column_config.TextColumn(max_chars=20),
        "변경 전":st.column_config.TextColumn(max_chars=500),
        "변경 후":st.column_config.TextColumn(max_chars=500),
        "확인 메모":st.column_config.TextColumn(max_chars=500),
    })
    # Widget deletion on navigation must not remove the durable, session-local draft.
    try: rows,summary=compare_rows(edited.fillna("").to_dict("records"))
    except ValueError as exc:
        st.warning(str(exc)); return
    if not rows: st.info("항목명을 입력해 비교표를 시작하세요."); return
    headers=["항목","유형","단위","변경 전","변경 후","차이","확인 메모"]
    st.subheader("변경 전후 미리보기")
    st.dataframe(pd.DataFrame(rows,columns=headers),hide_index=True,use_container_width=True)
    st.subheader("입력값 자동 요약")
    st.text("\n".join(summary))
    st.caption("금액 증감과 문자 변경만 설명합니다. 보장 확대·축소, 상품 우열이나 가입 적합성을 자동 판정하지 않습니다.")
    source=fingerprint([rows,context])
    if st.button("자동 요약을 고객 설명 초안으로 가져오기",key="c_make_explanation"):
        explanation="\n".join(summary)+"\n\n실제 지급조건, 면책·감액, 갱신, 해지 시 불이익은 약관과 공식 설명서를 함께 확인해야 합니다."
        if st.session_state.get('c_explanation','').strip(): replace_explanation(explanation,source)
        else: install_explanation(explanation,source)
    explanation=field("text_area","고객 설명 문구 편집","c_explanation","",height=180,max_chars=6000)
    stale=bool(explanation and st.session_state.get('c_explanation_source') and st.session_state['c_explanation_source']!=source)
    if stale:
        st.warning('비교 조건이 변경되었습니다. 설명문을 수정·확인하거나 자동 요약을 다시 가져오세요.')
        if st.button('설명문을 현재 조건에 맞게 확인했습니다',key='c_explanation_recheck'):
            st.session_state['c_explanation_source']=source
            stale=False
    signature=fingerprint([title,context,rows,explanation])
    if st.session_state.get('c_last_signature')!=signature:
        st.session_state['c_reviewed']=False
        st.session_state.pop('_ws_c_reviewed',None)
        st.session_state['c_last_signature']=signature
    checked=field("checkbox","입력 단위와 사실관계를 확인했습니다","c_reviewed",False)
    if checked and not stale:
        downloads("comparison",title,headers,rows,context+"\n\n"+explanation)
    else: st.info("단위·조건을 확인하고 체크하면 Excel·PDF 다운로드가 표시됩니다.")
