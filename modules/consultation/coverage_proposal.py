"""Separate current-versus-proposal comparison; no external AI calls."""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
import pandas as pd
import streamlit as st
from modules.shared.ui_components import page_header, page_footer
from modules.consultation.coverage_comparison_data import METRICS, extract_pdf, format_won, format_coverage, summarize_candidate
from modules.consultation.coverage_brief_report import comparison_pdf


def _combine(items, name):
    out={'name':name, 'notes':' / '.join(x['notes'] for x in items if x['notes'])}
    for k in ('premium',)+METRICS:
        vals=[x.get(k) for x in items]
        out[k]=sum(vals) if vals and all(v is not None for v in vals) else None
    return out



def _recommendation(current, plan):
    reasons=[]; cautions=[]
    before=current.get('premium');after=plan.get('premium')
    if before is not None and after is not None:
        difference=after-before
        if difference<0:reasons.append(f"월 보험료가 {abs(difference):,}원 줄어듭니다.")
        elif difference>0:cautions.append(f"월 보험료가 {difference:,}원 늘어납니다.")
        else:reasons.append('월 보험료가 동일합니다.')
    for metric in METRICS:
        a=current.get(metric);b=plan.get(metric)
        if a is None or b is None:continue
        if b>a:reasons.append(f'{metric} 가입금액이 {format_coverage(b-a)} 늘어납니다.')
        elif b<a:cautions.append(f'{metric} 가입금액이 {format_coverage(a-b)} 줄어듭니다.')
    if not reasons:reasons.append('고객님의 우선순위에 맞춰 보장 범위와 지급 조건을 비교해 주세요.')
    cautions.append('기존 계약 해지환급금, 새 계약의 인수·면책·감액과 지급 조건을 확인해 주세요.')
    return '\n'.join(reasons), '\n'.join(cautions)

def _read_pdf(upload, password=""):
    key='coverage_proposal_parse_'+hashlib.sha256(upload.getvalue()+password.encode()).hexdigest()
    if key not in st.session_state:
        try: st.session_state[key]=extract_pdf(upload.getvalue(), password)
        except Exception:st.session_state[key]={'rows':[],'premiums':[],'warnings':['PDF를 읽지 못했습니다. 비밀번호 또는 파일을 확인하고 보장 내용을 직접 입력해 주세요.']}
    return st.session_state[key]


def _input_file(file, group, idx):
    token=hashlib.sha256(file.getvalue()).hexdigest()[:12]+f'_{group}_{idx}'
    from pypdf import PdfReader
    from io import BytesIO
    try: encrypted=PdfReader(BytesIO(file.getvalue())).is_encrypted
    except Exception: encrypted=False
    password=st.text_input(f'{group} {idx+1} PDF 비밀번호',type='password',key=f'{token}_password') if encrypted else ''
    data=_read_pdf(file,password)
    with st.expander(f'{group} {idx+1} · {file.name}',expanded=True):
        for warning in data['warnings']:st.caption(warning)
        if data['rows']:
            st.dataframe(pd.DataFrame(data['rows'])[['항목','금액(원)','페이지','원문']],hide_index=True,use_container_width=True)
        st.caption('한 PDF에 여러 계약이 있으면 계약별 내용을 직접 확인해 입력해 주세요. 같은 담보라도 지급 조건이 다르면 단순 합산하지 마세요.')
        name=st.text_input('보험 또는 제안 이름',value=file.name.rsplit('.',1)[0],key=f'{token}_name')
        ps=data['premiums']; amount=ps[0] if len(ps)==1 else None
        if ps:st.caption('확인된 보험료 후보: '+', '.join(format_won(x) for x in ps))
        premium=st.number_input('월 보험료 (원)',min_value=0,value=amount,step=1000,key=f'{token}_premium',placeholder='확인 후 입력')
        out={'name':name,'premium':premium}
        cols=st.columns(2)
        for i,metric in enumerate(METRICS):
            vals=sorted({r['금액(원)'] for r in data['rows'] if r['항목']==metric})
            val=vals[0] if len(vals)==1 else None
            out[metric]=cols[i%2].number_input(metric+' (원)',min_value=0,value=val,step=1000000,key=f'{token}_{i}',placeholder='확인 후 입력')
        summaries=[w for w in data['warnings'] if '별도 분류' in w]
        for section in ('암 치료','뇌·심장 치료','수술','간병','기타 보장'):
            choices=[r for r in data['rows'] if r['항목']==section]
            choices.sort(key=lambda r: (not any(x in r['원문'] for x in ('주요치료','항암약물','간병인사용','간병인 사용')), r['페이지']))
            picks=choices[:2]
            for r in picks:
                summaries.append(f"{section}: {summarize_candidate(r)}")
        out['notes']=st.text_area('암·뇌심장 치료, 수술, 간병 및 기타 보장 요약',value='\n'.join(summaries),key=f'{token}_notes',height=180,placeholder='원문 확인 후 주요 금액과 지급 조건을 간략히 입력하세요.')
    return out


def _current_excel(file):
    from modules.consultation.analyzer_model import parse_source_file
    parsed=parse_source_file(file.getvalue())
    aliases={'일반암':['일반암'],'유사암':['유사암'],'뇌혈관질환':['뇌혈관'],'허혈성심장질환':['허혈성심장질환']}
    out={'name':'현재 보험', 'notes':'엑셀의 치료·수술·간병 내용은 원본 확인 필요'}
    premiums=[x.get('monthly') for x in parsed['contracts']]
    out['premium']=sum(premiums) if premiums and all(isinstance(x,(int,float)) and x>0 for x in premiums) else None
    from modules.consultation.coverage_comparison_data import _classify
    summaries=[]
    for section in ('암 치료','뇌·심장 치료','수술','간병','기타 보장'):
        rows=[r for r in parsed['coverages'] if _classify(r['label'])==section and any(isinstance(v,(int,float)) and v>0 for v in r['values'])][:2]
        for r in rows:
            vals=' / '.join(format_coverage(v) for v in r['values'] if isinstance(v,(int,float)) and v>0)
            summaries.append(f"{section}: {r.get('display') or r['label']} {vals} (지급 조건 확인)")
    if summaries:out['notes']='\n'.join(summaries)
    for key,labels in aliases.items():
        rows=[r for r in parsed['coverages'] if r['label'] in labels]
        vals=[v for r in rows for v in r['values']]
        # The existing workbook reader collapses blank cells to zero; do not assume these mean absence.
        out[key]=sum(vals) if vals and all(isinstance(v,(int,float)) and v>0 for v in vals) else None
    return out


def run():
    page_header('고객 상담','보험 보장비교 제안 보고서','현재 보험과 제안 보험을 비교하고 추천 이유를 정리합니다.','▤')
    st.caption('고객 자료는 현재 작업에서만 사용합니다. 추출된 금액과 지급 조건은 원본과 비교해 확인해 주세요.')
    a,b=st.columns(2)
    current_files=a.file_uploader('현재 유지 보험 자료',type=['pdf','xlsx'],accept_multiple_files=True,key='coverage_current_files')
    proposed_files=b.file_uploader('제안 보험 PDF',type=['pdf'],accept_multiple_files=True,key='coverage_proposed_files')
    if not current_files or not proposed_files:
        st.info('현재 보험 자료와 제안 보험 PDF를 각각 첨부해 주세요.');return
    from modules.shared.validators import validate_upload, ValidationError
    total_bytes=0
    for file in current_files+proposed_files:
        try:
            validate_upload(file.name,file.getvalue(),session_total=total_bytes,allow_encrypted_pdf=True)
            total_bytes+=file.size
        except ValidationError as exc:
            st.error('파일 확인: '+str(exc)); return
    identities=[hashlib.sha256(f.getvalue()).hexdigest() for f in current_files+proposed_files]
    if len(identities)!=len(set(identities)):
        st.error('동일한 파일이 여러 번 첨부되었습니다. 중복 파일을 제외해 주세요.');return
    mode=st.radio('제안 보험 비교 방식',['각각 비교','모두 합쳐 비교'],horizontal=True) if len(proposed_files)>1 else '각각 비교'
    st.markdown('### 1. 보험료와 보장금액 확인')
    current=[]
    for i,file in enumerate(current_files):
        if file.name.lower().endswith('.xlsx'):
            try:
                preset=_current_excel(file)
                # Reuse the same review interface for every source; no silent zero defaults.
                with st.expander(f'현재 보험 엑셀 · {file.name}',expanded=True):
                    st.caption('엑셀 원본의 계약과 금액을 반드시 확인해 주세요. 자료에 기재되지 않은 항목은 확인 필요로 둡니다.')
                    token='xlsx_'+hashlib.sha256(file.getvalue()).hexdigest()[:12]+str(i)
                    preset['premium']=st.number_input('현재 월 보험료 합계 (원)',min_value=0,value=preset['premium'],step=1000,key=token+'p',placeholder='확인 후 입력')
                    cc=st.columns(2)
                    for j,k in enumerate(METRICS):preset[k]=cc[j%2].number_input('현재 '+k+' (원)',min_value=0,value=preset[k],step=1000000,key=token+str(j),placeholder='확인 후 입력')
                    preset['notes']=st.text_area('현재 암·뇌심장 치료, 수술, 간병 및 기타 보장 요약',value=preset['notes'],key=token+'n')
                current.append(preset)
            except Exception:st.error('현재 엑셀을 읽지 못했습니다. 보장분석 도우미에 사용하는 원본 엑셀을 확인해 주세요.')
        else:current.append(_input_file(file,'현재',i))
    proposed=[_input_file(file,'제안',i) for i,file in enumerate(proposed_files)]
    if not current or len(current)!=len(current_files):return
    c=_combine(current,'현재 보험')
    plans=[_combine(proposed,'통합 제안')] if mode=='모두 합쳐 비교' else proposed
    names=[p['name'].strip() for p in plans]
    if any(not n for n in names) or len(set(names))!=len(names):st.error('제안 이름을 서로 다르게 입력해 주세요.');return
    st.markdown('### 2. 추천안과 전달할 내용')
    recommended=st.selectbox('추천안', ['선택하지 않음']+names)
    selected=next((p for p in plans if p['name']==recommended),None)
    auto_reason,auto_caution=_recommendation(c,selected) if selected else ('','')
    note_hash=hashlib.sha256(json.dumps([c,plans,recommended],ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:16]
    reason=st.text_area('추천 이유',value=auto_reason,key='coverage_reason_'+note_hash,placeholder='예: 보장기간 확대와 간병 대비를 고려한 구성입니다.')
    caution=st.text_area('변경 시 함께 확인할 내용',value=auto_caution,key='coverage_caution_'+note_hash,placeholder='예: 기존 대비 줄어드는 진단금과 면책·감액 기간을 확인합니다.')
    st.markdown('### 3. 비교 결과')
    rows=[]
    for metric in ('premium',)+METRICS:
        rows.append({'항목':'월 보험료' if metric=='premium' else metric,'현재':format_won(c.get(metric)) if metric=='premium' else format_coverage(c.get(metric)),**{p['name']:(format_won(p.get(metric)) if metric=='premium' else format_coverage(p.get(metric))) for p in plans}})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    premiums={p['name']:p['premium'] for p in [c]+plans if p.get('premium') is not None}
    if premiums:st.bar_chart(pd.DataFrame({'월 보험료':premiums}))
    st.caption('금액 미기재는 보장 없음이 아닙니다. 통합금액은 동일한 범위와 지급 조건의 합산 여부를 확인하세요.')
    signature=hashlib.sha256(json.dumps([c,plans,recommended,reason,caution],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if st.session_state.get('coverage_review_signature') != signature:
        st.session_state['coverage_verified']=False
        st.session_state['coverage_review_signature']=signature
    verified=st.checkbox('고객, 보험료, 보장금액과 지급 조건을 원본과 대조했습니다.',key='coverage_verified')
    if verified:
        pdf=comparison_pdf(c,plans,'' if recommended=='선택하지 않음' else recommended,reason,caution)
        st.download_button('비교 제안 보고서 PDF 다운로드',pdf,file_name='보험_보장비교_제안보고서.pdf',mime='application/pdf',type='primary',use_container_width=True)
    page_footer('보험 보장비교 제안 보고서','1.0')
