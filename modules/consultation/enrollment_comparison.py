"""신규 가입안 비교: 세션 초안, 검토 상태, 한 장 출력."""
from copy import deepcopy
from hashlib import sha256
import html
import io
import json
from pathlib import Path
import re
from uuid import uuid4
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas
from modules.shared.workspace_tools import workbook_bytes
from modules.shared.ui_components import page_header
from modules.shared.paths import PROJECT_ROOT

GROUPS=['암 보장','뇌·심장 보장','수술 보장','입원·간병 보장','실손의료비','사망·후유장해','운전자·배상책임']
STATES=['확인 필요','입력 완료','보장 없음']
def uid(): return uuid4().hex[:12]
def signature(v): return sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def cell(): return dict(status='확인 필요',summary='',details='',approved=None)
def product(): return dict(id=uid(),company='',name='',premium=None,term='',renewal='확인 필요')
def new_model():
    groups=[dict(id=uid(),name=n,selected=True,mode='묶음 요약') for n in GROUPS]
    return dict(title='신규 가입안 비교',basis='',note='',third=False,common=[],groups=groups,
                plans={p:dict(name=f'{p}안',products=[],cells={g['id']:cell() for g in groups}) for p in 'ABC'})
def active(m): return list('ABC' if m['third'] else 'AB')
def total(m,p):
    values=[x['premium'] for x in m['common']+m['plans'][p]['products']]
    return None if not values or any(v is None for v in values) else sum(values)
def copy_plan(m,src,dst):
    name=m['plans'][dst]['name']; m['plans'][dst]=deepcopy(m['plans'][src]); m['plans'][dst]['name']=name
    for x in m['plans'][dst]['products']: x['id']=uid()
def draft(s): return ' / '.join(x.strip() for x in s.splitlines() if x.strip())
def detail_sig(c): return signature([c['details'],c['summary']])
def issues(m):
    out=[]
    if not m['title'].strip(): out.append('기본 정보 · 자료 제목을 입력하세요.')
    selected=[g for g in m['groups'] if g['selected']]
    if not selected: out.append('보장 비교 · 출력할 묶음을 하나 이상 선택하세요.')
    labels=[g['name'].strip() for g in m['groups']]
    if any(not x for x in labels) or len(labels)!=len(set(labels)): out.append('보장 묶음 이름의 빈칸·중복을 수정하세요.')
    names=[m['plans'][p]['name'].strip() for p in active(m)]
    if any(not x for x in names) or len(names)!=len(set(names)): out.append('가입안 이름을 서로 다르게 입력하세요.')
    collections=[('공통 상품',m['common'])]+[(m['plans'][p]['name'],m['plans'][p]['products']) for p in active(m)]
    for label,products in collections:
        for i,x in enumerate(products,1):
            missing=[k for k,v in [('보험사',x['company'].strip()),('상품명',x['name'].strip()),('월 보험료',x['premium'] is not None),('납입·보장기간',x['term'].strip()),('갱신 구분',x['renewal']!='확인 필요')] if not v]
            if missing: out.append(f'{label} · 상품 {i}: '+', '.join(missing)+' 확인 필요')
    for p in active(m):
        plan=m['plans'][p]
        if not m['common'] and not plan['products']: out.append(f'{plan["name"]} · 상품을 하나 이상 등록하세요.')
        for g in selected:
            c=plan['cells'][g['id']]; label=f'{plan["name"]} · {g["name"]}'
            if c['status']=='확인 필요': out.append(label+' · 보장 상태 확인 필요')
            elif c['status']=='입력 완료':
                if not c['summary'].strip(): out.append(label+' · 묶음 요약 미입력')
                if g['mode']=='세부 비교' and not c['details'].strip(): out.append(label+' · 세부 내용 미입력')
                if c['details'].strip() and c['approved']!=detail_sig(c): out.append(label+' · 세부 내용과 요약 일치 여부 재확인')
    return out

def product_text(products):
    return '\n'.join(f'{x["company"]} · {x["name"]}\n{x["term"]} · {x["renewal"]}' for x in products)
def table_data(m):
    ps=active(m); headers=['비교 항목']+[m['plans'][p]['name'] for p in ps]
    rows=[['월 보험료 합계']+[f'{total(m,p):,}원' if total(m,p) is not None else '확인 필요' for p in ps],
          ['가입 상품']+[product_text(m['plans'][p]['products']) or ('공통 상품으로 구성' if m['common'] else '상품 미입력') for p in ps]]
    for g in m['groups']:
        if not g['selected']: continue
        row=[g['name']]
        for p in ps:
            c=m['plans'][p]['cells'][g['id']]
            row.append('보장 없음' if c['status']=='보장 없음' else '확인 필요' if c['status']=='확인 필요' else c['details'] if g['mode']=='세부 비교' else c['summary'])
        rows.append(row)
    return headers,rows
class PageOverflow(ValueError): pass

def build_pdf(m):
    """Measure all content at readable fixed font sizes; never clip or shrink."""
    font='EnrollmentPretendard'
    if font not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont(font,str(PROJECT_ROOT/'assets/fonts/PretendardVariable.ttf')))
    w,h=landscape(A4); usable=w-64
    body=ParagraphStyle('body',fontName=font,fontSize=10,leading=14,wordWrap='CJK',textColor=colors.HexColor('#17233C'))
    heading=ParagraphStyle('heading',parent=body,fontSize=22,leading=29)
    white=ParagraphStyle('white',parent=body,textColor=colors.white)
    def para(s,style=body): return Paragraph(html.escape(str(s)).replace('\n','<br/>'),style)
    blocks=[para(m['title'],heading)]
    if m['basis'].strip(): blocks.append(para(m['basis']))
    if m['common']: blocks.append(para('공통 가입 상품 · 모든 안에 포함\n'+product_text(m['common'])))
    headers,rows=table_data(m)
    table=Table([[para(x,white) for x in headers]]+[[para(x) for x in row] for row in rows],colWidths=[112]+[(usable-112)/(len(headers)-1)]*(len(headers)-1))
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17233C')),('BACKGROUND',(0,1),(0,-1),colors.HexColor('#EEF2F7')),('BACKGROUND',(1,1),(-1,1),colors.HexColor('#E8F0FF')),('ROWBACKGROUNDS',(1,2),(-1,-1),[colors.white,colors.HexColor('#F8FAFC')]),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#DCE3ED')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9)]))
    blocks.append(table)
    if m['note'].strip(): blocks.append(para('설명 · '+m['note']))
    sizes=[b.wrap(usable,h) for b in blocks]; needed=sum(height for _,height in sizes)+10*(len(blocks)-1)
    if needed>h-82: raise PageOverflow(f'A4 가로 한 장 기준 약 {needed-(h-82):.0f}pt 초과. ① 공통·반복 설명 정리 → ② 세부 비교를 묶음 요약으로 변경 → ③ 덜 중요한 묶음의 PDF 선택 해제 순서로 줄여주세요.')
    output=io.BytesIO(); c=canvas.Canvas(output,pagesize=(w,h)); c.setTitle(m['title']); y=h-30
    for b,(_,height) in zip(blocks,sizes): y-=height; b.drawOn(c,32,y); y-=10
    c.setFillColor(colors.HexColor('#17233C')); c.roundRect(32,19,17,17,4,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont(font,11); c.drawString(36,22,'H')
    c.setStrokeColor(colors.HexColor('#B89555')); c.line(57,20,57,35)
    c.setFillColor(colors.HexColor('#637087')); c.setFont(font,8); c.drawString(65,24,'화랑 WORKSPACE · Planned & Built by 박병선 팀장')
    c.drawRightString(w-32,24,'입력한 가입설계 기준 | 1 / 1'); c.showPage(); c.save(); return output.getvalue()
def filename(s): return re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',s).strip().rstrip('.')[:90] or '가입안_비교'

def run():
    page_header('고객 상담','고객용 비교표 제작기','상품을 구성하고 핵심 보장을 골라, 고객에게 전달할 한 장을 완성하세요.','CB')
    st.session_state.setdefault('enroll_model',new_model()); m=st.session_state['enroll_model']; rev=st.session_state.get('enroll_revision',0)
    def widget(kind,label,obj,key,ident,**kwargs):
        wk=f'enroll_{rev}_{ident}_{key}'
        if wk not in st.session_state: st.session_state[wk]=obj[key]
        obj[key]=getattr(st,kind)(label,key=wk,**kwargs); return obj[key]
    def refresh(): st.session_state['enroll_revision']=rev+1; st.rerun()
    def edit_products(products,label):
        st.caption('월 보험료를 입력하세요. 고객용 출력에는 가입안별 합계만 표시됩니다.')
        for x in list(products):
            with st.container(border=True):
                a,b=st.columns(2)
                with a: widget('text_input','보험사',x,'company',x['id'],max_chars=40)
                with b: widget('text_input','상품명',x,'name',x['id'],max_chars=100)
                a,b,c=st.columns([1,1.5,1])
                with a: widget('number_input','월 보험료 (원)',x,'premium',x['id'],min_value=0,step=1000,value=None)
                with b: widget('text_input','납입·보장기간',x,'term',x['id'],placeholder='예: 20년납 / 100세 만기',max_chars=100)
                with c: widget('selectbox','갱신 구분',x,'renewal',x['id'],options=['확인 필요','비갱신','갱신','혼합'])
                if st.button('상품 삭제',key='del_'+x['id']): products.remove(x); refresh()
        if st.button('+ 상품 추가',key='add_'+label): products.append(product()); refresh()
    tabs=st.tabs(['① 가입안 구성','② 보장 비교','③ 미리보기·저장'])
    with tabs[0]:
        widget('text_input','자료 제목',m,'title','base',max_chars=100)
        widget('text_area','비교 기준',m,'basis','base',height=80,max_chars=600,placeholder='예: 동일 연령·직업·가입조건 기준')
        widget('checkbox','C안도 비교하기',m,'third','base')
        with st.expander('공통 가입 상품 · 선택 사항',expanded=bool(m['common'])):
            st.caption('모든 안에 동일하게 들어가는 상품만 등록하세요. 한 번 수정하면 모든 안에 반영됩니다. 없으면 비워두세요.')
            edit_products(m['common'],'common')
        for p in active(m):
            with st.expander(f'{p}안 · {m["plans"][p]["name"]}',expanded=True):
                plan=m['plans'][p]; widget('text_input','가입안 이름',plan,'name',p,max_chars=40); edit_products(plan['products'],p)
                amount=total(m,p); st.metric('월 보험료 합계 · 공통 상품 포함',f'{amount:,}원' if amount is not None else '입력 대기')
        with st.expander('가입안 복사'):
            a,b=st.columns(2); src=a.selectbox('복사할 안',active(m),key='enroll_copy_src'); dst=b.selectbox('붙여넣을 안',active(m),key='enroll_copy_dst')
            confirmed=st.checkbox('붙여넣을 안의 상품·보장 입력을 교체합니다.',key=f'enroll_copy_ok_{rev}_{src}_{dst}')
            if st.button('가입안 복사 적용',disabled=src==dst or not confirmed): copy_plan(m,src,dst); refresh()
            st.caption('복사한 안은 독립적으로 편집됩니다. 공통 상품은 계속 모든 안에 연결됩니다.')
    with tabs[1]:
        st.caption('공통 상품을 포함한 전체 보장 기준으로 작성하세요. 지급조건이 다른 보장은 구분해서 적어주세요.')
        custom=st.text_input('추가할 보장 묶음',key=f'enroll_custom_{rev}',max_chars=40)
        if st.button('+ 보장 묶음 추가',disabled=not custom.strip() or custom.strip() in [g['name'] for g in m['groups']] or len(m['groups'])>=20):
            g=dict(id=uid(),name=custom.strip(),selected=True,mode='묶음 요약'); m['groups'].append(g)
            for p in 'ABC': m['plans'][p]['cells'][g['id']]=cell()
            refresh()
        for idx,g in enumerate(list(m['groups'])):
            with st.expander(g['name']):
                a,b=st.columns([1,2])
                with a: widget('checkbox','PDF에 포함',g,'selected',g['id'])
                with b: widget('radio','표시 방식',g,'mode',g['id'],options=['묶음 요약','세부 비교'],horizontal=True)
                widget('text_input','묶음 이름',g,'name',g['id'],max_chars=40)
                for p,col in zip(active(m),st.columns(len(active(m)))):
                    with col:
                        st.markdown('**'+m['plans'][p]['name']+'**'); value=m['plans'][p]['cells'][g['id']]; ident=p+g['id']
                        widget('selectbox','입력 상태',value,'status',ident,options=STATES)
                        if value['status']=='보장 없음': st.info('“보장 없음”으로 출력됩니다.')
                        else:
                            widget('text_area','묶음 요약',value,'summary',ident,height=110,max_chars=600)
                            widget('text_area','세부 보장 · 항목별 한 줄',value,'details',ident,height=130,max_chars=2000)
                            if value['details'].strip():
                                proposed=draft(value['details']); st.caption('요약 초안: '+proposed)
                                ok=st.checkbox('현재 요약을 위 초안으로 교체',key=f'enroll_draftok_{rev}_{ident}_{signature(proposed)}')
                                if st.button('초안 적용',key='draft_'+ident,disabled=not ok): value['summary']=proposed; value['approved']=None; refresh()
                                ds=detail_sig(value)
                                checked=st.checkbox('세부 내용과 요약이 일치함을 확인',value=value['approved']==ds,key=f'enroll_detailok_{rev}_{ident}_{ds}')
                                value['approved']=ds if checked else None
                        if g['selected'] and value['status']=='확인 필요': st.warning('저장 전 확인 필요')
                a,b,c=st.columns(3)
                if a.button('위로',key='up_'+g['id'],disabled=idx==0): m['groups'][idx-1],m['groups'][idx]=m['groups'][idx],m['groups'][idx-1]; refresh()
                if b.button('아래로',key='down_'+g['id'],disabled=idx==len(m['groups'])-1): m['groups'][idx+1],m['groups'][idx]=m['groups'][idx],m['groups'][idx+1]; refresh()
                if c.button('묶음 삭제',key='remove_'+g['id']):
                    m['groups'].remove(g)
                    for p in 'ABC': m['plans'][p]['cells'].pop(g['id'],None)
                    refresh()
        widget('text_area','고객에게 전할 설명',m,'note','base',height=100,max_chars=1200)
    with tabs[2]:
        st.subheader(m['title'] or '자료 제목')
        if m['basis']: st.write(m['basis'])
        if m['common']: st.info('공통 가입 상품 · 모든 안에 포함\n\n'+product_text(m['common']))
        headers,rows=table_data(m); st.dataframe(pd.DataFrame(rows,columns=headers),hide_index=True,width='stretch')
        if m['note']: st.write(m['note'])
        problems=issues(m); pdf=None
        try: pdf=build_pdf(m)
        except PageOverflow as exc: problems.append(str(exc))
        if problems:
            st.warning(f'저장 전 확인할 항목 {len(problems)}개')
            for problem in problems: st.write('• '+problem)
        else: st.success('필수 입력 완료 · A4 가로 한 장에 들어갑니다.')
        # Do not reuse a previous review if content changes and later returns to an old value.
        sig=signature(m)
        if st.session_state.get('enroll_last_sig')!=sig:
            st.session_state['enroll_last_sig']=sig; st.session_state['enroll_reviewed']=False
        reviewed=st.checkbox('보험료·보장·조건과 PDF 포함 항목을 확인했습니다.',key='enroll_reviewed',disabled=bool(problems))
        st.caption('입력이 바뀌면 저장 전 확인이 자동으로 해제됩니다.')
        if reviewed and not problems:
            a,b=st.columns(2)
            a.download_button('한 장 PDF 저장',pdf,filename(m['title'])+'.pdf','application/pdf',width='stretch')
            notes='\n'.join(filter(None,[m['basis'],'공통 가입 상품\n'+product_text(m['common']) if m['common'] else '',m['note']]))
            b.download_button('Excel 저장',workbook_bytes(m['title'],headers,rows,notes),filename(m['title'])+'.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')
