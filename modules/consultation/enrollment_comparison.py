"""Simplified enrollment comparisons with independent modes and explicit export selection."""
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
from pathlib import Path
import html, io, json, re
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph,Table,TableStyle,SimpleDocTemplate,Spacer
from pypdf import PdfReader
from modules.shared.paths import PROJECT_ROOT
from modules.shared.pdf_brand import draw_brand
from modules.shared.ui_components import page_header

EXAMPLES={'암 보장':'일반암 3,000만원 / 유사암 600만원\n암주요치료 포함 (10년 또는 만기 보장)','뇌·심장 보장':'뇌혈관질환 1,000만원 / 허혈성심장질환 1,000만원\n순환계주요치료 포함 (10년 또는 만기 보장)','수술 보장':'1-5종 수술 최대 1,000만원\n질병수술 30만원 / 상해수술 50만원','입원·간병 보장':'질병입원일당 2만원 / 간병인사용일당 10만원','실손의료비':'입원 5,000만원·통원 20만원 보장 / \n자기부담금과 한도 기재','사망·후유장해':'상해사망 1억원 / 상해후유장해 5,000만원','운전자·배상책임':'교통사고처리지원금 2억원 / 일상생활배상책임 1억원'}
NOTE_EXAMPLE = '각 안의 최종 월 보험료에는 공통 보험료가 포함됩니다. \n보장 범위와 지급 조건은 실제 가입설계 및 약관을 기준으로 확인하며, 면책기간·감액기간·갱신 여부에 따라 보장 내용이 달라질 수 있습니다.\n\n아래와 같은 비교 결과가 확인된 경우의 추천 예시입니다.\n최종적으로는 B안을 추천드립니다. A안은 월 보험료 부담을 줄이는 데 중점을 두었고, C안은 보장금액을 더 높인 구성입니다. \nB안은 고객님께서 중요하게 생각하신 암·뇌·심장 보장을 확보하면서, 매월 납입 가능한 예산과 장기적인 유지 가능성을 함께 고려한 절충안입니다.\n\n다만 보험료 절감이 가장 중요하시다면 A안을, 추가 보험료를 부담하더라도 보장금액을 높이고 싶으시다면 C안을 검토하실 수 있습니다. \n최종 선택은 기존 보험과의 중복 여부, 실제 보장 차이, 납입기간 및 고객님의 우선순위를 확인한 뒤 결정해 주세요.'

MODES=['가입안별 간편 입력','상품별 상세 입력']
RENEWALS=['선택','비갱신','갱신','혼합']
def uid():return uuid4().hex[:12]
def signature(x):return sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def condition():return dict(id=uid(),pay='',cover='',renewal='선택')
def product():return dict(**condition(),premium=None)
def cell():return dict(summary='',absent=False)
def new_model():
    groups=[dict(id=uid(),name=n,selected=False) for n in EXAMPLES]
    return dict(version=2,title='신규 가입안 비교',basis='',note=NOTE_EXAMPLE,third=False,mode=MODES[0],common_enabled=False,common_summary='',common=[],groups=groups,
        plans={p:dict(name=p+'안',mode=MODES[0],override=False,premium=None,conditions=[condition()],products=[],cells={g['id']:cell() for g in groups},reference=None) for p in 'ABC'})
def migrate(old):
    if old.get('version')==2:return old
    m=new_model()
    for k in ['title','basis','note','third']:m[k]=old.get(k,m[k])
    m['groups']=deepcopy(old.get('groups',m['groups']))
    def convert(x):
        y=product(); y.update(premium=x.get('premium'),pay=x.get('term',''),cover='',renewal=x.get('renewal','선택'))
        if y['renewal'] not in RENEWALS:y['renewal']='선택'
        return y
    m['common']=[convert(x) for x in old.get('common',[])];m['common_enabled']=bool(m['common'])
    for p in 'ABC':
        src=old.get('plans',{}).get(p,{}); dest=m['plans'][p]
        dest.update(name=src.get('name',p+'안'),mode=MODES[1],override=True,products=[convert(x) for x in src.get('products',[])])
        dest['cells']={g['id']:dict(summary=src.get('cells',{}).get(g['id'],{}).get('summary',''),absent=src.get('cells',{}).get(g['id'],{}).get('status')=='보장 없음') for g in m['groups']}
    return m

def active(m):return list('ABC' if m['third'] else 'AB')
def summed(xs):return None if any(x['premium'] is None for x in xs) else sum(x['premium'] for x in xs)
def common_total(m):return summed(m['common']) if m['common_enabled'] else 0
def own_total(plan):return plan['premium'] if plan['mode']==MODES[0] else summed(plan['products'])
def total(m,p):
    a,b=common_total(m),own_total(m['plans'][p]);return None if a is None or b is None else a+b
def plan_conditions(p):return p['conditions'] if p['mode']==MODES[0] else p['products']
def switch_mode(p,mode):
    if p['mode']==mode:return
    if mode==MODES[0]:
        p['premium']=summed(p['products']);p['conditions']=[{k:v for k,v in x.items() if k!='premium'} for x in p['products']] or [condition()]
    else:p['reference']=p['premium']
    p['mode']=mode

def copy_plan(m,src,dst):
    name=m['plans'][dst]['name'];m['plans'][dst]=deepcopy(m['plans'][src]);m['plans'][dst]['name']=name
    for x in m['plans'][dst]['products']+m['plans'][dst]['conditions']:x['id']=uid()
def condition_text(xs):return '\n'.join(f'{x["pay"]}납 / {x["cover"]} 보장 / {x["renewal"]}' for x in xs)
def issues(m):
    out=[]
    if not m['title'].strip():out.append('자료 제목을 입력하세요.')
    groups=[g for g in m['groups'] if g['selected']]
    if not groups:out.append('PDF에 넣을 보장 묶음을 선택하세요.')
    names=[m['plans'][p]['name'].strip() for p in active(m)]
    if any(not x for x in names) or len(names)!=len(set(names)):out.append('가입안 이름의 빈칸·중복을 수정하세요.')
    labels=[g['name'].strip() for g in groups]
    if any(not x for x in labels) or len(labels)!=len(set(labels)):out.append('선택한 묶음 이름의 빈칸·중복을 수정하세요.')
    sets=[]
    if m['common_enabled']:
        if not m['common']:out.append('공통 가입 조건을 하나 이상 추가하세요.')
        if not m['common_summary'].strip():out.append('공통 보장 요약을 입력하세요.')
        if common_total(m) is None:out.append('공통 월 보험료를 입력하세요.')
        sets.append(('공통',m['common']))
    for p in active(m):
        plan=m['plans'][p];label=plan['name'];xs=plan_conditions(plan)
        if own_total(plan) is None:out.append(label+' · 월 보험료 미입력')
        if not xs and not m['common_enabled']:out.append(label+' · 가입 조건을 입력하세요.')
        if plan['mode']==MODES[1] and plan['reference'] is not None and own_total(plan)!=plan['reference']:out.append(label+' · 상세 합계와 이전 간편 총액이 다릅니다. 합계를 확인한 뒤 참고 총액 확인을 눌러주세요.')
        sets.append((label,xs))
        for g in groups:
            c=plan['cells'][g['id']]
            if not c['summary'].strip() and not c['absent']:out.append(label+' · '+g['name']+' 작성 또는 보장 없음 선택')
    for label,xs in sets:
        for i,x in enumerate(xs,1):
            if not x['pay'].strip() or not x['cover'].strip() or x['renewal']=='선택':out.append(f'{label} · 조건 {i} 납입기간·보장기간·갱신 구분 확인')
    return out

def table_data(m):
    ps=active(m);headers=['비교 항목']+[m['plans'][p]['name'] for p in ps];rows=[]
    if m['common_enabled']:
        amount=common_total(m);s=('월 '+f'{amount:,}원' if amount is not None else '보험료 미입력')+' · 모든 안에 포함\n'+condition_text(m['common'])+'\n'+m['common_summary']
        rows.append(['공통 가입 내용',s]+['']*(len(ps)-1))
    rows.append(['최종 월 보험료']+[f'{total(m,p):,}원' if total(m,p) is not None else '미입력' for p in ps])
    rows.append(['납입·보장 조건']+[condition_text(plan_conditions(m['plans'][p])) or '공통 조건과 동일' for p in ps])
    for g in m['groups']:
        if g['selected']:rows.append([g['name']]+['보장 없음' if m['plans'][p]['cells'][g['id']]['absent'] else m['plans'][p]['cells'][g['id']]['summary'] for p in ps])
    return headers,rows
class PageOverflow(ValueError):pass

def build_pdf(m):
    font='EnrollmentPretendard'
    if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(font,str(PROJECT_ROOT/'assets/fonts/PretendardVariable.ttf')))
    w,h=landscape(A4);usable=w-64
    body=ParagraphStyle('body',fontName=font,fontSize=10,leading=14,wordWrap='CJK',textColor=colors.HexColor('#112B49'))
    title=ParagraphStyle('title',parent=body,fontSize=21,leading=28)
    table_body=ParagraphStyle('table_body',parent=body,alignment=1)
    white=ParagraphStyle('white',parent=table_body,textColor=colors.white)
    def para(s,style=body):return Paragraph(html.escape(str(s)).replace('\n','<br/>'),style)
    blocks=[para(m['title'],title)]
    if m['basis'].strip():blocks.append(para(m['basis']))
    headers,rows=table_data(m)
    t=Table([[para(x,white) for x in headers]]+[[para(x,table_body) for x in row] for row in rows],colWidths=[112]+[(usable-112)/(len(headers)-1)]*(len(headers)-1),repeatRows=1,splitByRow=1,splitInRow=1)
    styles=[('BACKGROUND',(0,0),(-1,0),colors.HexColor('#112B49')),('BACKGROUND',(0,1),(0,-1),colors.HexColor('#EEF3F8')),('ROWBACKGROUNDS',(1,1),(-1,-1),[colors.white,colors.HexColor('#F7FAFD')]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#DCE5EF')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9)]
    if m['common_enabled']:styles += [('SPAN',(1,1),(-1,1)),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#EAF5F4'))]
    premium_row=2 if m['common_enabled'] else 1
    styles.append(('BACKGROUND',(1,premium_row),(-1,premium_row),colors.HexColor('#E8F0FF')))
    t.setStyle(TableStyle(styles));blocks.append(t)
    if m['note'].strip():
        note_table=Table([[para('고객님께 드리는 안내',white)],[para(m['note'],table_body)]],colWidths=[usable],repeatRows=1,splitByRow=1,splitInRow=1)
        note_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#112B49')),
            ('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#F7FAFD')),
            ('BOX',(0,0),(-1,-1),.5,colors.HexColor('#DCE5EF')),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),
            ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),
        ]))
        blocks.append(note_table)
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=(w,h),leftMargin=26,rightMargin=26,
                          topMargin=54,bottomMargin=46,title=m['title'],author='화랑 WORKSPACE')
    story=[]
    for block in blocks:
        if story:story.append(Spacer(1,10))
        story.append(block)
    def marks(c,d):draw_brand(c,d.page)
    doc.build(story,onFirstPage=marks,onLaterPages=marks)
    return out.getvalue()

def filename(s):return re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',s).strip().rstrip('.')[:90] or '가입안_비교'

def run():
    page_header('고객 상담','고객용 비교표 제작기','보험료와 필요한 보장만 입력해 비교 자료를 만드세요.','CB')
    st.session_state.setdefault('enroll_model',new_model());m=migrate(st.session_state['enroll_model']);st.session_state['enroll_model']=m
    rev=st.session_state.get('enroll_revision',0)
    def refresh():st.session_state['enroll_revision']=rev+1;st.rerun()
    def widget(kind,label,obj,key,ident,**kw):
        wk=f'enroll_v2_{rev}_{ident}_{key}'
        if wk not in st.session_state:st.session_state[wk]=obj[key]
        obj[key]=getattr(st,kind)(label,key=wk,**kw);return obj[key]
    def conditions(xs,label,priced=False):
        for i,x in enumerate(list(xs),1):
            with st.container(border=True):
                st.caption(('상품 ' if priced else '조건 ')+str(i))
                if priced:widget('number_input','월 보험료 (원)',x,'premium',x['id'],min_value=0,step=1000,value=None)
                a,b,c=st.columns(3)
                with a:widget('text_input','납입기간',x,'pay',x['id'],placeholder='예: 20년',max_chars=60)
                with b:widget('text_input','보장기간',x,'cover',x['id'],placeholder='예: 100세',max_chars=60)
                with c:widget('selectbox','갱신 구분',x,'renewal',x['id'],options=RENEWALS)
                if st.button('삭제',key='remove_'+label+x['id']):xs.remove(x);refresh()
        if st.button('+ 상품 추가' if priced else '+ 조건 추가',key='add_'+label):xs.append(product() if priced else condition());refresh()
    tabs=st.tabs(['① 기본·가입 조건','② 보장 묶음','③ 미리보기·저장'])
    with tabs[0]:
        widget('text_input','자료 제목',m,'title','base',max_chars=100)
        widget('checkbox','C안 추가',m,'third','base')
        chosen=st.radio('기본 입력 방식',MODES,index=MODES.index(m['mode']),key=f'enroll_globalmode_{rev}',horizontal=True)
        if chosen!=m['mode']:
            m['mode']=chosen
            for p in 'ABC':
                if not m['plans'][p]['override']:switch_mode(m['plans'][p],chosen)
            refresh()
        with st.expander('비교 기준 · 선택 사항'):widget('text_area','비교 기준',m,'basis','base',max_chars=500)
        widget('checkbox','모든 안에 공통으로 포함되는 내용이 있어요',m,'common_enabled','base')
        if m['common_enabled']:
            with st.expander('공통 가입 내용',expanded=True):
                conditions(m['common'],'common',True)
                widget('text_area','공통 보장 요약',m,'common_summary','base',placeholder='예: 실손의료비는 모든 안에 동일하게 포함',max_chars=800)
        for p in active(m):
            plan=m['plans'][p]
            with st.expander(plan['name']+' · 보험료와 조건',expanded=True):
                widget('text_input','가입안 이름',plan,'name',p,max_chars=40)
                override=widget('checkbox','이 안만 입력 방식 별도 선택',plan,'override',p)
                mode=st.radio('입력 방식',MODES,index=MODES.index(plan['mode']),key=f'enroll_mode_{rev}_{p}',horizontal=True) if override else m['mode']
                if mode!=plan['mode']:switch_mode(plan,mode);refresh()
                if plan['mode']==MODES[0]:
                    widget('number_input','공통 제외 월 보험료 (원)' if m['common_enabled'] else '월 보험료 합계 (원)',plan,'premium',p,min_value=0,step=1000,value=None)
                    conditions(plan['conditions'],p)
                else:
                    st.caption('공통 가입 내용의 보험료는 여기에 중복 입력하지 마세요.' if m['common_enabled'] else '상품별 보험료를 자동 합산합니다.')
                    conditions(plan['products'],p,True)
                    if plan['reference'] is not None:
                        st.info(f'이전 간편 입력 총액: {plan["reference"]:,}원 · 현재 상세 합계: {own_total(plan)}원')
                        if st.button('현재 상세 합계를 확인했습니다',key='ref_'+p):plan['reference']=None;refresh()
                amount=total(m,p);st.metric('최종 월 보험료 · 공통 포함' if m['common_enabled'] else '최종 월 보험료',f'{amount:,}원' if amount is not None else '입력 대기')
        with st.expander('반복 입력 줄이기 · 조건 적용 / 가입안 복사'):
            src=st.selectbox('기준 가입안',active(m),key='enroll_tools_src')
            dst=st.multiselect('적용할 가입안',[p for p in active(m) if p!=src],key='enroll_tools_dst')
            action=st.radio('적용할 내용',['납입·보장·갱신 조건','가입안 전체'],horizontal=True,key='enroll_tools_action')
            ok=st.checkbox('선택한 안의 해당 입력을 교체합니다.',key=f'enroll_tools_ok_{rev}_{src}_{signature(dst)}_{action}')
            if st.button('선택한 안에 적용',disabled=not dst or not ok):
                for target in dst:
                    if action=='가입안 전체':copy_plan(m,src,target)
                    else:
                        template=plan_conditions(m['plans'][src])
                        target_plan=m['plans'][target]
                        if target_plan['mode']==MODES[0]:target_plan['conditions']=[dict(id=uid(),pay=x['pay'],cover=x['cover'],renewal=x['renewal']) for x in template]
                        else:
                            for i,x in enumerate(target_plan['products']):
                                if template:
                                    base=template[min(i,len(template)-1)]
                                    for k in ['pay','cover','renewal']:x[k]=base[k]
                refresh()
    with tabs[1]:
        st.caption('왼쪽 체크로 PDF 포함을 선택하세요. 예시는 안내용이며 출력되지 않습니다.')
        only=st.toggle('선택한 묶음만 보기',key='enroll_only_selected')
        custom=st.text_input('추가할 묶음 이름',key=f'enroll_newgroup_{rev}',max_chars=40)
        if st.button('+ 묶음 추가',disabled=not custom.strip() or custom.strip() in [g['name'] for g in m['groups']] or len(m['groups'])>=20):
            g=dict(id=uid(),name=custom.strip(),selected=False);m['groups'].append(g)
            for p in 'ABC':m['plans'][p]['cells'][g['id']]=cell()
            refresh()
        for idx,g in enumerate(m['groups']):
            if only and not g['selected']:continue
            left,right=st.columns([.07,.93],gap='small')
            with left:
                old=g['selected'];widget('checkbox',g['name']+' PDF 포함',g,'selected',g['id'],label_visibility='collapsed')
                if old!=g['selected']:
                    st.session_state['enroll_expand_'+g['id']]=st.session_state.get('enroll_expand_'+g['id'],0)+1
                    st.rerun()
            count=sum(bool(m['plans'][p]['cells'][g['id']]['summary'].strip()) or m['plans'][p]['cells'][g['id']]['absent'] for p in active(m))
            with right:
                with st.container(key=f'enroll_group_{g["id"]}_{st.session_state.get("enroll_expand_"+g["id"],0)}'):
                    with st.expander(f'{g["name"]} · {count}/{len(active(m))}안 작성',expanded=g['selected']):
                        for p,col in zip(active(m),st.columns(len(active(m)))):
                            with col:
                                c=m['plans'][p]['cells'][g['id']];st.markdown('**'+m['plans'][p]['name']+'**')
                                widget('text_area','묶음 요약',c,'summary',p+g['id'],placeholder='예: '+EXAMPLES.get(g['name'],'핵심 보장과 금액·조건을 작성하세요.'),height=110,max_chars=1200,disabled=c['absent'])
                                if not c['summary'].strip() or c['absent']:widget('checkbox','보장 없음',c,'absent',p+g['id'])
                        source=st.selectbox('요약을 복사할 안',active(m),key='enroll_group_src_'+g['id'])
                        targets=st.multiselect('요약을 받을 안',[p for p in active(m) if p!=source],key='enroll_group_dst_'+g['id'])
                        overwrite=any(m['plans'][p]['cells'][g['id']]['summary'] or m['plans'][p]['cells'][g['id']]['absent'] for p in targets)
                        ok=st.checkbox('기존 요약 교체',key=f'enroll_group_ok_{rev}_{g["id"]}_{source}_{signature(targets)}') if overwrite else True
                        if st.button('요약 복사',key='copy_'+g['id'],disabled=not targets or not ok):
                            for p in targets:m['plans'][p]['cells'][g['id']]=deepcopy(m['plans'][source]['cells'][g['id']])
                            refresh()
                        with st.expander('묶음 이름·순서 편집'):
                            widget('text_input','묶음 이름',g,'name',g['id'],max_chars=40)
                            a,b,c=st.columns(3)
                            if a.button('위로',key='up_'+g['id'],disabled=idx==0):m['groups'][idx-1],m['groups'][idx]=m['groups'][idx],m['groups'][idx-1];refresh()
                            if b.button('아래로',key='down_'+g['id'],disabled=idx==len(m['groups'])-1):m['groups'][idx+1],m['groups'][idx]=m['groups'][idx],m['groups'][idx+1];refresh()
                            if c.button('삭제',key='del_'+g['id']):m['groups'].pop(idx);refresh()
    with tabs[2]:
        widget('text_area','고객에게 전할 설명 · 선택 사항',m,'note','base',max_chars=1500,height=260,placeholder=NOTE_EXAMPLE)
        st.caption('기본 설명이 입력되어 있습니다. 추천안과 이유를 실제 비교 결과에 맞게 수정하세요. 모두 지우면 PDF에서 안내 표가 생략됩니다.')
        headers,rows=table_data(m);st.dataframe(pd.DataFrame(rows,columns=headers),hide_index=True,width='stretch')
        errors=issues(m);pdf=None
        pdf=build_pdf(m)
        pages=len(PdfReader(io.BytesIO(pdf)).pages)
        if pages==1:st.success('A4 가로 한 장 출력 가능')
        else:
            st.warning(f'한 장 분량을 초과하여 총 {pages}페이지로 출력됩니다. 그대로 PDF를 저장할 수 있습니다.')
            st.caption('한 장으로 줄이려면 ① 공통·반복 설명 정리 → ② 긴 요약 줄이기 → ③ 중요도가 낮은 묶음 체크 해제 순서로 조정하세요.')
        if errors:
            with st.expander(f'저장 전 확인 {len(errors)}개',expanded=True):
                for e in errors:st.write('• '+e)
        sig=signature(m)
        if st.session_state.get('enroll_last_sig')!=sig:st.session_state['enroll_last_sig']=sig;st.session_state['enroll_reviewed']=False
        reviewed=st.checkbox('현재 보험료·조건·보장 내용을 확인했습니다.',key='enroll_reviewed',disabled=bool(errors))
        if reviewed and not errors:
            st.download_button('PDF 저장',pdf,filename(m['title'])+'.pdf','application/pdf',width='stretch')
