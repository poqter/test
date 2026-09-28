"""Four-step claim guide using the reviewed workflow model."""
import hashlib
import uuid
from io import BytesIO
import streamlit as st
import pdfplumber
from . import claim_workflow as w
from .claim_reports import build_customer_pdf


def field(model, name, label, *, area=False):
    key='cg_ui_'+name
    st.session_state.setdefault(key,model.get(name,''))
    value=(st.text_area if area else st.text_input)(label,key=key)
    model[name]=value
    return value


def nav(case,step,label):
    if st.button(label,key='cg_nav_'+w.stable_id([step,label])):
        st.session_state['cg_pending_step']=step
        st.rerun()


def run():
    from .insurance_claim_guide import extract_pdf, render_copyable_message
    from modules.shared.upload_ui import guarded_upload
    st.title('보험금 청구 가이드')
    c=st.session_state.setdefault('cg_case',w.new_case())
    steps=['1. 청구 내용 선택','2. 안내할 서류 선택','3. 관련 담보 찾기 · 선택사항','4. 문자·PDF 전달']
    if st.session_state.get('cg_step')=='3. 문자·PDF 전달':st.session_state['cg_step']=steps[3]
    pending=st.session_state.pop('cg_pending_step',None)
    if pending:st.session_state['cg_step']=pending
    step=st.radio('작성 순서',steps,horizontal=True,key='cg_step')
    if st.button('처음부터 다시',key='cg_restart'):
        for k in list(st.session_state):
            if k.startswith('cg_'): del st.session_state[k]
        st.rerun()
    if step.startswith('1'):
        st.caption('해당하는 청구 내용을 여러 개 선택하세요. 이름과 PDF는 나중에 추가해도 됩니다.')
        for group, options in w.CLAIM_GROUPS.items():
            with st.expander(group):
                for claim in options:
                    key='cg_pick_'+claim
                    st.session_state.setdefault(key,claim in c['claims'])
                    chosen=st.checkbox(claim,key=key)
                    if chosen and claim not in c['claims']: c['claims'].append(claim)
                    if not chosen and claim in c['claims']: c['claims'].remove(claim)
        if c['claims']:
            st.write('선택한 내용: '+' · '.join(c['claims']))
        if c['claims']:nav(c,steps[1],'안내할 서류 선택으로 이동')
        return
    if not c['claims']:
        st.info('1단계에서 청구 내용을 먼저 선택해 주세요.')
        return
    docs=w.documents_for_case(c)
    if step.startswith('2'):
        questions={q for d in docs for q in d['questions']}
        labels={'prescription':'처방을 받았나요?','cast':'깁스·부목 치료를 받았나요?',
            'biomarker':'유전자·바이오마커 검사를 받았나요?','icu':'중환자실을 이용했나요?',
            'proxy':'대리 청구인가요?','nicu':'신생아중환자실을 이용했나요?','beneficiary':'보험수익자는 누구인가요?'}
        for q in sorted(questions):
            opts=['확인 중','예','아니오','해당 없음']
            if q=='beneficiary':opts=['확인 중','지정수익자','법정상속인']
            key='cg_answer_'+q
            previous=st.session_state.get(key,c['answers'].get(q,opts[0]))
            previous={'아니요':'아니오','받음':'예','받지 못함':'아니오'}.get(previous,previous)
            st.session_state[key]=previous if previous in opts else opts[0]
            c['answers'][q]=st.selectbox(labels.get(q,q),opts,key=key)
        if any(x in c['claims'] for x in ('수술','암 수술','산모 수술')):
            opts=['확인 중','질병','상해·재해','교통사고','질병과 상해 모두 확인']
            st.session_state.setdefault('cg_surgery_answer',c['answers'].get('surgery_cause',opts[0]))
            c['answers']['surgery_cause']=st.selectbox('수술 원인',opts,key='cg_surgery_answer')
        docs=w.documents_for_case(c)
        a,b=st.columns(2)
        if a.button('추천 상태로 되돌리기'):
            c['doc_edits']={}
            for k in list(st.session_state):
                if k.startswith('cg_doc_'):del st.session_state[k]
            st.rerun()
        if b.button('전체 포함 해제'):
            for d in c.get('custom_docs',[]):
                d['include']=False
                st.session_state['cg_custom_'+d['id']]=False
            for d in docs:
                c['doc_edits'].setdefault(d['id'],{})['include']=False
                st.session_state['cg_doc_include_'+d['id']]=False
            st.rerun()
        st.caption('고객에게 안내할 서류를 체크해 주세요. 검사자료는 이번 진단에 사용한 항목을 선택해 주세요.')
        for tier in ['안내할 서류','추가 요청 시']:
            with st.expander(tier,expanded=tier!='추가 요청 시'):
                for d in [x for x in docs if (x['tier']=='추가 요청 시')==(tier=='추가 요청 시')]:
                    ident=d['id'];edit=c['doc_edits'].setdefault(ident,{})
                    cols=st.columns([1,9])
                    key='cg_doc_include_'+ident
                    # Untouched conditional selections follow the latest answer.
                    if 'include' not in edit: st.session_state[key]=d['include']
                    def save_include(ident=ident,key=key):
                        c['doc_edits'].setdefault(ident,{})['include']=st.session_state[key]
                    st.session_state.setdefault(key,d['include'])
                    chosen=cols[0].checkbox('안내문 포함',key=key,label_visibility='collapsed',on_change=save_include)
                    if chosen!=d['include']: edit['include']=chosen
                    fresh=' · 새로 추가됨' if ident in c.get('new_doc_ids',[]) else ''
                    with cols[1].expander(d['name']+fresh+(' · 직접 수정' if any(k in edit for k in ('name','required_info')) else '')):
                        st.caption('관련 청구: '+' · '.join(d['reasons'])+' / 대상: '+d['target'])
                        if len(d['reasons'])>1:st.caption('목록에서는 한 번 표시하지만, 대상 질환과 발급기관에 따라 실제 서류는 여러 장일 수 있습니다.')
                        for f,label in [('name','서류명'),('required_info','확인할 내용')]:
                            key='cg_doc_'+f+'_'+ident
                            if f not in edit:st.session_state[key]=d[f]
                            st.session_state.setdefault(key,d[f])
                            def save_text(f=f,key=key,ident=ident,basis=d['default_info']):
                                e=c['doc_edits'].setdefault(ident,{})
                                e[f]=st.session_state[key]
                                if f=='required_info':e['basis_info']=basis
                            val=st.text_input(label,key=key,on_change=save_text)
                    cols[1].caption(c['doc_edits'].get(ident,{}).get('required_info',d['required_info']))
                    if d.get('additional_info'):cols[1].info('추가로 확인할 내용: '+d['additional_info'])
        st.subheader('서류 직접 추가')
        custom=c.setdefault('custom_docs',[])
        with st.form('cg_custom_form',clear_on_submit=True):
            name=st.text_input('추가할 서류명');info=st.text_input('서류에 포함할 내용')
            if st.form_submit_button('서류 추가') and name.strip():
                custom.append(dict(id=uuid.uuid4().hex,name=name,required_info=info,group='직접 준비',include=True));st.rerun()
        for d in custom:
            d['include']=st.checkbox(d['name'],value=d['include'],key='cg_custom_'+d['id'])
            if st.button('삭제',key='cg_custom_del_'+d['id']):custom.remove(d);st.rerun()
        if c.get('new_doc_ids') and st.button('추가된 서류 확인 완료'):
            c['new_doc_ids']=[];st.rerun()
        nav(c,steps[2],'관련 담보 찾기')
        nav(c,steps[3],'담보 찾기를 건너뛰고 문자·PDF 만들기')
    elif step.startswith('3'):
        st.caption('선택사항입니다. PDF 없이 담보를 직접 추가하거나 이 단계를 건너뛸 수 있습니다.')
        nav(c,steps[3],'건너뛰고 문자·PDF 만들기')
        coverage_section(c,extract_pdf,guarded_upload)
        if c.get('new_doc_ids'):nav(c,steps[1],'추가된 서류 확인')
        nav(c,steps[3],'문자·PDF 전달로 이동')
    else:
        name=field(c,'customer_name','고객 이름 · 선택사항')
        if name and c.get('source_customer') not in ('',None,'확인 필요',name):
            st.warning('입력한 고객 이름과 PDF의 고객 이름이 다릅니다. 전달 전에 확인해 주세요.')
        note=field(c,'note','추가 안내 · 선택사항',area=True)
        accident=field(c,'accident','사고경위 · 선택사항',area=True)
        docs=w.documents_for_case(c)+c.get('custom_docs',[])
        st.caption(f"청구 {len(c['claims'])}개 · 안내서류 {sum(d['include'] for d in docs)}개")
        if not any(d['include'] for d in docs):
            st.info('안내할 서류가 선택되지 않았습니다.')
            nav(c,steps[1],'안내할 서류 선택으로 이동')
        fingerprint=w.message_fingerprint(c['claims'],docs,name,note)
        if c['message'] and c['message_fingerprint']!=fingerprint:
            st.warning('선택 내용이 변경되었습니다. 기존 문자를 유지하거나 다시 생성해 주세요.')
        replace=st.checkbox('작성한 문자 내용을 새 안내문으로 교체',key='cg_replace_message') if c['message'] else True
        if st.button('문자 안내문 생성',disabled=not replace):
            c['message']=w.make_message(c['claims'],docs,name,note)
            c['message_fingerprint']=fingerprint
            st.session_state['cg_message_edit']=c['message']
        if c['message']:
            st.session_state.setdefault('cg_message_edit',c['message'])
            c['message']=st.text_area('고객에게 보낼 문자',key='cg_message_edit',height=300)
            render_copyable_message(c['message'])
        selected=list({r['id']:r for r in w.review_rows(c,c['claims'],c['answers'])}.values())
        st.session_state.setdefault('cg_pdf_coverages',c.get('include_coverages',False))
        include=st.checkbox('선택한 담보 목록을 PDF 별도 페이지에 포함',key='cg_pdf_coverages')
        c['include_coverages']=include
        st.caption('담보 목록 포함' if include else '담보 목록 미포함')
        if st.button('PDF 미리보기·생성'):
            data=build_customer_pdf(c['claims'],docs,name=name,note=note,accident=accident,coverages=selected if include else [])
            with pdfplumber.open(BytesIO(data)) as pdf: pages=len(pdf.pages)
            st.session_state['cg_pdf_result']=(w.stable_id([docs,name,note,accident,selected,include,c['claims']]),data,pages)
        token=w.stable_id([docs,name,note,accident,selected,include,c['claims']])
        saved=st.session_state.get('cg_pdf_result')
        if saved and saved[0]!=token:st.warning('입력 내용이 변경되었습니다. PDF를 다시 생성해 주세요.')
        if saved and saved[0]==token:
            if saved[2]>1:st.info(f'{saved[2]}쪽으로 작성됩니다. 그대로 다운로드할 수 있습니다.')
            st.download_button('고객용 PDF 다운로드',saved[1],file_name='화랑_보험금청구안내.pdf',mime='application/pdf')


def coverage_section(c,extract_pdf,guarded_upload):
    st.subheader('가입한 보험에서 청구 관련 담보 찾기')
    with st.expander('보장분석 PDF 첨부 · 선택사항'):
        keep=st.checkbox('PDF 교체 시 직접 추가한 담보 유지',key='cg_keep_manual')
        def upload_changed():
            if st.session_state.get('cg_studio_upload') is None:
                st.session_state.pop('cg_upload_bytes',None)
        upload=guarded_upload('보장분석 PDF',type=['pdf'],key='cg_studio_upload',on_change=upload_changed)
        if upload: st.session_state['cg_upload_bytes']=upload.getvalue()
        data=st.session_state.get('cg_upload_bytes',b'')
        if data and st.button('첨부 PDF 제거',key='cg_remove_source'):
            st.session_state.pop('cg_upload_bytes',None)
            st.session_state.pop('cg_studio_upload',None)
            c.update(w.replace_source(c,'',[],keep_manual=keep))
            c['source_customer']=''
            c['manual']=[r for r in c['manual'] if not r.get('source_search')]
            st.rerun()
        ident=hashlib.sha256(data).hexdigest() if data else ''
        if ident!=c['file_id']:
            try: parsed=extract_pdf(data) if data else {'coverages':[]}
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("PDF parse failed: %s",type(exc).__name__)
                c.update(w.replace_source(c,'',[],keep_manual=keep))
                c['manual']=[r for r in c['manual'] if not r.get('source_search')]
                st.error('PDF를 읽지 못했습니다. 파일을 확인해 주세요.');return
            c.update(w.replace_source(c,ident,parsed['coverages'],keep_manual=keep))
            c['manual']=[r for r in c['manual'] if not r.get('source_search')]
            for k in list(st.session_state):
                if k.startswith(('cg_cov_','cg_search_')):del st.session_state[k]
            for warning in parsed.get('extraction_warnings',[]):st.warning(warning)
            c['source_customer']=parsed.get('customer','')
        if c.get('source_customer') and data:st.caption('PDF 고객: '+c['source_customer'])
    rows=w.review_rows(c,c['claims'],c['answers'])
    query=st.text_input('전체 담보 검색',key='cg_search_query')
    if query.strip():
        for r in c['rows']:
            if query.replace(' ','') in (r['company']+r['product']+r['coverage']).replace(' ',''):
                key=w.coverage_id(r)
                st.write(r['company']+' · '+r['coverage']+' · '+r['amount'])
                if st.button('검색 담보 추가',key='cg_search_add_'+key):
                    if not any(x.get('id')==key for x in c['manual']):
                        c['manual'].append({'id':key,'source_search':True,'포함':True,'보험회사':r['company'],'상품명':r['product'],'관련 담보':r['coverage'],'가입금액':r['amount'],'확인사항':'원본과 지급조건 확인','원본쪽':str(r['source_page'])})
                    st.rerun()
    rows=list({r['id']:r for r in rows}.values())
    for r in rows:
        key=r['id']
        with st.expander(r['보험회사']+' · '+r['상품명']+' / '+r['관련 담보']):
            change={}
            for f in ['포함','관련 담보','가입금액','확인사항']:
                k='cg_cov_'+f+'_'+key
                st.session_state.setdefault(k,r.get(f,''))
                value=st.checkbox('안내에 포함',key=k) if f=='포함' else st.text_input(f,key=k)
                if value!=r.get(f):change[f]=value
            if change:
                manual=next((x for x in c['manual'] if x['id']==key),None)
                if manual is not None:manual.update(change)
                else:c['coverage_edits'].setdefault(key,{}).update(change)
            st.caption('원본 페이지: '+str(r.get('원본쪽','직접 입력'))+' · '+r.get('추출상태','직접 추가'))
            if data and r.get('원본쪽'):
                pages=[int(x.strip()) for x in str(r['원본쪽']).split(',') if x.strip().isdigit()]
                if pages:
                    page=st.selectbox('원본 확인 페이지',pages,key='cg_cov_page_'+key)
                    if st.checkbox('원본 페이지 보기',key='cg_cov_preview_'+key):
                        with pdfplumber.open(BytesIO(data)) as pdf:
                            if 1<=page<=len(pdf.pages):st.image(pdf.pages[page-1].to_image(resolution=100).original)
            if st.button('수정 복원',key='cg_cov_restore_'+key):
                c['coverage_edits'].pop(key,None)
                for f in ['포함','관련 담보','가입금액','확인사항']:st.session_state.pop('cg_cov_'+f+'_'+key,None)
                st.rerun()
    with st.expander('담보 직접 추가'):
        with st.form('cg_manual_form',clear_on_submit=True):
            company=st.text_input('보험회사');product=st.text_input('상품명');coverage=st.text_input('담보명');amount=st.text_input('가입금액')
            if st.form_submit_button('담보 추가') and coverage.strip():
                c['manual'].append({'id':uuid.uuid4().hex,'포함':True,'보험회사':company,'상품명':product,'관련 담보':coverage,'가입금액':amount,'확인사항':'사용자 직접 입력'});st.rerun()
        for r in c['manual']:
            if st.button('삭제: '+r['관련 담보'],key='cg_manual_del_'+r['id']):c['manual'].remove(r);st.rerun()
    asked=set()
    for p in w.proposals(c):
        with st.container(border=True):
            st.write('추가로 확인할 청구: '+p['claim'])
            q=p['question'];key='cg_fact_'+q
            st.session_state.setdefault(key,{'아니요':'아니오'}.get(c['answers'].get(q,'확인 중'),c['answers'].get(q,'확인 중')))
            if q not in asked:
                c['answers'][q]=st.selectbox(p['claim']+' 관련 치료·이용이 실제 있었나요?',['확인 중','예','아니오','해당 없음'],key=key)
                asked.add(q)
            delta=w.proposal_delta(c,p['claim'])
            st.caption('추가할 청구: '+p['claim'])
            st.caption('새로 추가할 서류: '+(', '.join(d['name'] for d in delta['added']) or '없음'))
            if delta['updated']:st.caption('기재정보가 추가될 서류: '+', '.join(d['name'] for d in delta['updated']))
            st.caption('기존 선택과 직접 수정한 내용은 유지됩니다.')
            if st.button('청구에 추가',key='cg_proposal_'+p['claim'],disabled=c['answers'][q]!='예'):
                c.update(w.accept_proposal(c,p['claim']));st.rerun()
            if st.button('이번 상담에서는 제외',key='cg_dismiss_'+p['claim']):c['dismissed'].append(p['claim']);st.rerun()
