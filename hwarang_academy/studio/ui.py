"""Authenticated Streamlit UI for AI training, private review and scoped sharing."""
from copy import deepcopy
from hashlib import sha256
import json
from html import escape
import streamlit as st
from .domain import (STAGES,GOALS,LIMITS,DIFFICULTIES,PERSONALITIES,CRITERIA,END_LABELS,
                     new_session,rewind,practice_from,next_stage,end_session,share_payload,disclosure_catalog)
from .provider import Config,OpenAIProvider
from .repository import Repository
from .runtime import Runtime
from . import immersion
from ..pre_api.constants import PORTFOLIO_ARCHETYPES

LEVELS={'strong':'충분히 확인됨','developing':'부분적으로 확인됨','needs_practice':'보완 연습 필요','not_observed':'평가 불가'}


def _safe_error(exc):
    known=('STUDIO_VERSION_CONFLICT','STUDIO_REQUEST_PENDING','AI_SERVICE_DISABLED','AI_TEXT_DISABLED',
           'AI_ASSESSMENT_DISABLED','AI_ASSESSMENT_PERMISSION_REQUIRED','VOICE_DISABLED','AI_VOICE_DISABLED')
    text=str(exc)
    for k in known:
        if k in text:return {'STUDIO_VERSION_CONFLICT':'다른 접속에서 기록이 변경됐습니다. 저장 상태를 다시 불러와 주세요.',
          'STUDIO_REQUEST_PENDING':'처리 중이거나 확인 대기인 요청이 있습니다. 중복 호출을 막고 있습니다.'}.get(k,'관리자 설정에서 해당 AI 기능·이용 권한을 확인해 주세요.')
    if '키' in text or '응답' in text or '크레딧' in text or '답변' in text or '음성' in text:return text[:250]
    return '요청을 완료하지 못했습니다. 저장 상태와 관리자 설정을 확인해 주세요. 중복 입력은 피해주세요.'


def _put(repo,s,op=None):
    st.session_state['_studio_state']=repo.save(s,op)
    st.rerun()


def render_report(report):
    st.subheader((report or {}).get('status','피드백 준비'))
    st.caption((report or {}).get('notice','대화 근거를 바탕으로 피드백합니다.'))
    c1,c2=st.columns(2)
    with c1:
        st.markdown('**잘한 점**')
        for x in report.get('strengths',[]):st.write('✓ '+x)
    with c2:
        st.markdown('**우선 개선점**')
        for x in report.get('improvements',[]):st.write('• '+x)
    for row in report.get('rows',[]):
        with st.expander(f"{CRITERIA.get(row['criterion'],row['criterion'])} · {LEVELS.get(row['level'],row['level'])}"):
            st.write(row['feedback'])
            for evidence in row['evidence']:st.info(f"{evidence['turn']}번째 답변 · {evidence['quote']}")
            if row.get('alternative'):st.write('대체 표현: '+row['alternative'])


def render_manager(auth,actor):
    repo=Repository(auth,actor)
    st.subheader('학습 참여와 공유받은 기록')
    st.caption('자유 연습은 횟수·완료 여부만 조회합니다. 상세 내용은 본인이 공유한 항목만 열립니다.')
    try:
        rows=repo.manager() or []
        people={}
        for r in rows:
            p=people.setdefault(r['user_id'],{'직원':r['display_name'],'연습 횟수':0,'완료':0})
            if r['mode']=='PRACTICE':p['연습 횟수']+=1;p['완료']+=int(r['finished'])
        if people:st.dataframe(list(people.values()),hide_index=True,width='stretch')
        eligible=[r for r in rows if r['shared'] or r['mode']=='ASSESSMENT']
        if not eligible:st.info('열람 가능한 상세 기록이 없습니다.');return
        selected=st.selectbox('공유·공식 평가 기록',eligible,format_func=lambda r:f"{r['display_name']} · {'공식 평가' if r['mode']=='ASSESSMENT' else '공유받은 연습'} · {r['id'][:8]}")
        # No persistent cache: revoked shares are checked again at every read.
        if st.button('권한 확인 후 열람',key='studio_manager_read'):
            st.session_state['_studio_manager_open']=selected['id']
        if st.session_state.get('_studio_manager_open')==selected['id']:
            detail=repo.manager(selected['id'])
            render_shared(detail)
            if selected['mode']=='ASSESSMENT':
                for r in repo.reviews(selected['id']):st.write(r['event'],r['note'])
                note=st.text_area('판정 확인 답변',max_chars=1000,key='studio_review_reply')
                if st.button('답변 기록',disabled=not note.strip()):repo.review(selected['id'],note,True);st.success('확인 답변을 기록했습니다.')
    except Exception as exc:st.warning(_safe_error(exc))


def _sharing(repo,s):
    if s['mode']!='PRACTICE':return
    with st.expander('관리자에게 선택 공유'):
        st.caption('기본은 비공개입니다. 원본 음성은 저장·공유하지 않습니다.')
        recipients=repo.recipients()
        if not recipients:st.info('현재 조직 권한에서 공유할 관리자가 없습니다.');return
        target=st.selectbox('공유 대상',recipients,format_func=lambda x:x['name'],key='studio_share_target')
        fields=st.multiselect('공유 항목', ['summary','feedback','transcript'],default=[],
            format_func=lambda x:{'summary':'평가 요약·항목별 결과','feedback':'상세 피드백·원문 발췌','transcript':'전체 대화'}[x],key='studio_share_fields')
        if fields:
            preview=share_payload(s,fields)
            st.markdown('**전달될 내용 미리보기**');render_shared(preview)
            if st.button('이 내용으로 공유',key='studio_share_commit'):
                repo.share(s['id'],target['id'],fields);st.success('선택한 기록과 항목을 공유했습니다.')
        if st.button('이 관리자에게 공유 철회',key='studio_share_revoke'):
            repo.share(s['id'],target['id'],[],False);st.success('이후 열람을 차단했습니다. 이미 별도로 보관한 내용은 회수되지 않습니다.')


def _setup(repo,config,permissions):
    st.markdown('<div class="studio-kicker">PRACTICE ROOM</div>',unsafe_allow_html=True)
    st.title('오늘은 어떤 상담을 해볼까요?')
    st.write('장면을 고르면 한 명의 고객과 대화가 시작됩니다.')
    stage=st.radio('훈련 장면',list(STAGES),format_func=STAGES.get,horizontal=True,key='studio_stage_pick')
    st.markdown(f'<div class="studio-mission"><span>오늘의 연습</span><h3>{escape(STAGES[stage])}</h3><p>{escape(GOALS[stage])}</p></div>',unsafe_allow_html=True)
    if not config.api_key:st.warning('관리자에게 상담 서비스 연결을 요청해 주세요. API 키는 대화창에 입력하지 마세요.')
    with st.form('studio_start'):
        a,b=st.columns(2)
        with a:
            mode=st.radio('연습 방식',['PRACTICE','ASSESSMENT'],format_func=lambda x:'자유 연습' if x=='PRACTICE' else '공식 평가',horizontal=True)
            difficulty=st.select_slider('고객 난이도',list(DIFFICULTIES),value='standard',format_func=DIFFICULTIES.get)
        with b:
            interaction=st.radio('대화 방식',['텍스트','음성','혼합'],horizontal=True)
            personality=st.selectbox('만날 고객',list(PERSONALITIES),format_func=PERSONALITIES.get)
        with st.expander('상담 범위와 고객 상황'):
            journey=st.radio('연습 범위',['집중 연습','전체 상담'],horizontal=True)=='전체 상담'
            archetype=st.selectbox('가상 보험 상황',['random',*PORTFOLIO_ARCHETYPES],format_func=lambda x:{'random':'랜덤','BALANCED':'균형형','UNDERINSURED':'보장 부족','OVERINSURED':'보험료 과다','DUPLICATED':'중복 가입','OUTDATED':'오래된 보장','RENEWAL_HEAVY':'갱신 중심','GAP_SPECIFIC':'특정 보장 공백','MIXED':'혼합형'}[x])
        st.caption('자유 연습은 힌트·되돌리기와 비공개 복기를 제공합니다. 공식 평가는 도움 없이 진행하고 담당 관리자가 결과를 확인합니다.')
        st.caption(f'답변 {config.customer_credits} · 힌트/연습 피드백 {config.coach_credits} · 공식 평가 {config.evaluator_credits} 크레딧 / 음성 별도')
        go=st.form_submit_button('고객 만나기 →',type='primary',use_container_width=True,disabled=not config.api_key)
    if go:
        if mode=='ASSESSMENT' and 'academy.formal_ai_assessment' not in permissions:
            st.error('공식 AI 평가 이용 권한이 필요합니다.');return
        if interaction!='텍스트' and 'academy.voice_simulator' not in permissions:
            st.error('음성 시뮬레이터 이용 권한이 필요합니다. 텍스트로 시작할 수 있습니다.');return
        state=new_session(repo.owner,stage=stage,mode=mode,difficulty=difficulty,journey=journey,
                          personality=personality,archetype=None if archetype=='random' else archetype)
        st.session_state['_studio_interaction']=interaction
        st.session_state['_studio_preview']=state;st.rerun()


def _introduction(repo,s):
    p=s['case']['public_state']
    st.markdown('<div class="studio-kicker">MEET YOUR CUSTOMER</div>',unsafe_allow_html=True)
    st.title('오늘 만날 고객입니다')
    st.markdown(f'<div class="studio-mission"><span>{escape(STAGES[s["stage"]])} · 첫 만남</span><div class="studio-profile-name">{escape(p.get("customer_alias","고객"))} 고객</div><p>{escape(str(p.get("age","")))}세 · {escape(p.get("occupation",""))}<br>{escape(p.get("relationship","소개 고객"))}</p></div>',unsafe_allow_html=True)
    st.write(p.get('known_note','보험 점검을 위해 만나는 가상 고객입니다.'))
    st.caption('처음 알려진 정보입니다. 고민과 판단 기준은 대화를 나누며 알아가세요.')
    st.markdown('**이번 만남의 목표**');st.write(GOALS[s['stage']])
    st.caption('자유 연습 · 상세 기록은 나만 확인' if s['mode']=='PRACTICE' else '공식 평가 · 도움 없이 진행 / 담당 관리자 열람')
    a,b=st.columns([2,1])
    with a:
        if st.button('대화 시작',type='primary',use_container_width=True):
            st.session_state['_studio_state']=repo.save(s)
            st.session_state.pop('_studio_preview',None);st.rerun()
    with b:
        if st.button('훈련 설정으로',use_container_width=True):
            st.session_state.pop('_studio_preview',None);st.rerun()


@st.dialog('고객이 공유한 보험 자료',width='large')
def _document_dialog(s):
    st.caption('가상 훈련용 자료입니다. 창을 닫으면 대화로 돌아갑니다.')
    _materials(s)


def _attachment(s,key):
    # Data access is checked independently from the presence of a UI card.
    if not (s.get('documents_shared') or s['stage'] in ('COVERAGE','PROPOSAL') or s['ended']):return
    count=len(s['case']['insurance_state'].get('contracts',[]))
    st.caption('고객이 보험 자료를 공유했습니다 · 가상 훈련용')
    if st.button(f'보험 증권 {count}건 열기',key=key):_document_dialog(s)


def _comparison(s):
    view=immersion.comparison(s)
    if not view:return
    with st.expander('이전 답변과 이번 답변 비교',expanded=len(s['turns'])==view['before']['turn']):
        a,b=st.columns(2)
        with a:
            st.markdown('**이전 시도**');st.write('나 · '+view['before']['advisor']);st.write('고객 · '+view['before']['customer'])
        with b:
            st.markdown('**이번 시도**');st.write('나 · '+view['after']['advisor']);st.write('고객 · '+view['after']['customer'])
        st.caption(view['notice'])


def _moments(repo,s):
    items=immersion.moments(s)
    if not items:return
    st.subheader('다시 답해볼 순간')
    st.caption('같은 고객과 같은 상황에서, 다른 표현을 시도해 보세요.')
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{item['turn']}번째 대화 · {item['label']}**")
            st.write('나 · '+item['advisor']);st.write('고객 · '+item['customer'])
            if st.button('이 장면 다시 연습',key='studio_moment_'+str(item['turn'])):_put(repo,practice_from(s,item['turn']))


def _customer_card(s):
    public=s['case']['public_state'];name=public.get('customer_alias','고객')
    st.markdown(f'<div class="studio-customer"><div class="studio-avatar">{escape(name[:1])}</div><div><strong>{escape(name)} 고객</strong><small>{escape(str(public.get("age","")))}세 · {escape(public.get("occupation",""))}</small></div><span class="studio-live">'+('상담 종료' if s['ended'] else '대화 중')+'</span></div>',unsafe_allow_html=True)


def _materials(s):
    public=s['case']['public_state']
    st.caption(public.get('relationship','소개 고객')+' · '+public.get('known_note',''))
    if s['stage'] in ('COVERAGE','PROPOSAL') or s.get('documents_shared') or s['ended']:
        from ..coverage_master import COVERAGE_MASTER
        for contract in s['case']['insurance_state'].get('contracts',[]):
            st.markdown(f"**{contract['product_name']} · 월 {contract['premium_won']:,}원**")
            st.caption(f"{contract['insurer']} · {contract['start_date']} 가입")
            st.table([{'보장':COVERAGE_MASTER.get(x['coverage_code'],{}).get('name',x['coverage_code']),'금액(만원)':f"{x['amount_manwon']:,}"} for x in contract['coverages']])
    else:st.caption('지금은 처음 알려진 정보만 보입니다. 필요한 내용은 고객에게 질문해 보세요.')


def render(auth,owner,permissions,credit_status=None):
    st.markdown('''<style>
    [data-testid="stMainBlockContainer"]{max-width:1000px!important;padding:22px 28px 36px!important}
    .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f3f5f9!important;color:#192d45}
    [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important}
    .studio-flow{display:flex;gap:8px;margin:8px 0 18px}.studio-flow span{font-size:11px;padding:6px 10px;border-radius:99px;color:#91a0af;background:#e9edf3}.studio-flow .active{background:#203e60;color:#fff}.studio-flow .done{background:#e6f0ed;color:#427564}
    .studio-kicker{font-size:11px;font-weight:800;letter-spacing:.16em;color:#617c99;margin:20px 0 8px}
    h1{font-size:30px!important;letter-spacing:-1.1px!important}h3{letter-spacing:-.5px}
    .studio-mission{border-radius:22px;background:#142d49;color:#fff;padding:24px 28px;margin:12px 0 24px}
    .studio-profile-name{font-size:28px;font-weight:800;letter-spacing:-.7px;color:white;margin:12px 0}
    .studio-mission span{font-size:12px;color:#a9c5e6}.studio-mission h3{color:#fff;margin:6px 0;font-size:22px}.studio-mission p{color:#d5e1ef;margin:0;font-size:14px}
    .studio-customer{display:flex;gap:12px;align-items:center;padding:16px 20px;background:#fff;border:1px solid #dfe6f0;border-radius:18px;margin:10px 0}
    .studio-avatar{height:44px;width:44px;display:grid;place-items:center;background:#e2edfa;color:#275f9b;border-radius:16px;font-size:20px;font-weight:800}
    .studio-customer strong{font-size:16px}.studio-customer small{display:block;color:#789;font-size:12px;margin-top:3px}
    .studio-live{margin-left:auto;font-size:12px;color:#237465;background:#eaf6f2;border-radius:99px;padding:5px 10px}
    [data-testid="stChatMessage"]{background:transparent;border:0;padding:12px 8px;gap:10px}
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"]{background:#fff;border:1px solid #e0e6ee;border-radius:4px 18px 18px 18px;padding:12px 16px;box-shadow:0 2px 6px #122b4510}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){flex-direction:row-reverse;margin-left:8%;width:92%}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"]{background:#203e60;color:#fff;border-color:#203e60;border-radius:18px 4px 18px 18px}
    [data-testid="stChatMessageAvatarUser"]{background:#42678e!important}
    [data-testid="stChatInput"]{border:1px solid #afbed0;border-radius:18px;background:white}
    [data-testid="stBottom"]{background:#f3f5f9!important}
    [data-testid="stForm"]{border:1px solid #dfe6f0;background:#fff;border-radius:20px}
    .st-key-studio_toolbar [data-testid="stHorizontalBlock"],.st-key-studio_controls [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important}
    .st-key-studio_toolbar [data-testid="stColumn"],.st-key-studio_controls [data-testid="stColumn"]{min-width:0!important}
    @media(max-width:640px){.st-key-studio_toolbar [data-testid="stColumn"]:first-child{display:none}.st-key-studio_toolbar [data-testid="stColumn"]{flex:1!important;width:50%!important}.st-key-studio_controls [data-testid="stColumn"]{flex:1!important;width:33%!important}.st-key-studio_controls button p{font-size:12px!important}[data-testid="stMainBlockContainer"]{padding:12px 12px 24px!important}h1{font-size:24px!important}.studio-mission{padding:18px}}
    </style>''',unsafe_allow_html=True)
    repo=Repository(auth,owner)
    if st.session_state.get('_studio_owner')!=owner:
        for k in list(st.session_state):
            if k.startswith('_studio_'):del st.session_state[k]
        st.session_state['_studio_owner']=owner
    config=Config.from_mapping(st.secrets)
    try:
        for k,v in (repo.rpc('settings') or {}).items():setattr(config,k,v)
    except Exception:
        st.error('AI 상담 설정을 읽지 못했습니다. Migration 23과 계정 권한을 확인해 주세요.');return
    runtime=Runtime(repo,OpenAIProvider(config))
    with st.container(key='studio_toolbar'):
        top=st.columns([3,1,1])
        with top[0]:st.caption('HWARANG ACADEMY · AI 상담 Studio')
        with top[1]:
            with st.popover('이용량'):
                if credit_status:
                    st.metric('남은 크레딧',f'{credit_status.available_credits:,}')
                    st.caption(f'음성 {credit_status.voice_available_seconds//60}분 {credit_status.voice_available_seconds%60}초 남음')
                else:st.caption('이용량을 불러오지 못했습니다.')
        with top[2]:
            if st.button('ACADEMY 홈',key='studio_back'):
                st.session_state['_studio_open']=False
                if 'view' in st.query_params:del st.query_params['view']
                st.rerun()
    if st.session_state.get('_studio_manager'):
        render_manager(auth,owner);return
    try:
        rows=repo.rows()
    except Exception:
        st.error('AI 상담 저장소를 연결하지 못했습니다. Migration 23 적용 및 ACADEMY 접근 설정을 확인해 주세요. 기존 규칙 기반 훈련은 유지됩니다.');return
    with st.expander('나의 AI 상담 기록 · 최근 50회',expanded=st.session_state.get('_studio_history_open',False)):
        if rows:
            chosen=st.selectbox('저장된 상담',rows,format_func=lambda r:f"{STAGES.get(r['stage'],r['stage'])} · {'자유 연습' if r['mode']=='PRACTICE' else '공식 평가'} · {r['updated_at'][:16]}")
            if st.button('선택 기록 열기'):
                st.session_state['_studio_state']=repo.load(chosen['id']);st.rerun()
        else:st.caption('첫 상담을 시작해 보세요.')
    if st.session_state.get('_studio_notice'):st.warning(st.session_state.pop('_studio_notice'))
    s=st.session_state.get('_studio_state')
    try:
        phase=0 if not s else 2 if s['ended'] else 1
        steps=''.join(f'<span class="'+('active' if i==phase else 'done' if i<phase else '')+f'">{i+1:02} {label}</span>' for i,label in enumerate(['상담 준비','고객과 대화','복기와 재훈련']))
        st.markdown('<div class="studio-flow">'+steps+'</div>',unsafe_allow_html=True)
        if not s:
            preview=st.session_state.get('_studio_preview')
            if preview:_introduction(repo,preview)
            else:_setup(repo,config,permissions)
            return
        st.caption(('자유 연습' if s['mode']=='PRACTICE' else '공식 평가')+' / '+STAGES[s['stage']]+' / '+DIFFICULTIES[s['difficulty']])
        _customer_card(s)
        if s['journey']:
            labels=[('✓ ' if k in s['completed_stages'] else '● ' if k==s['stage'] else '')+v for k,v in STAGES.items()]
            st.caption(' → '.join(labels))
        if not s['ended']:
            with st.container(key='studio_controls'):
                a,b,c=st.columns([2,1,1])
                with a:
                    with st.popover('고객 · 목표'):
                        st.write(GOALS[s['stage']]);_materials(s)
                with b:
                    with st.popover('이용 내역'):
                        st.caption(f"이번 상담 {sum(x.get('credits',0) for x in s['usage'])} 크레딧 · 음성 {sum(x.get('seconds',0) for x in s['usage'])}초")
                        if st.button('저장 상태 다시 불러오기',key='studio_reload'):
                            st.session_state['_studio_state']=repo.load(s['id']);st.rerun()
                with c:
                    if st.button('상담 마치기',key='studio_finish'):
                        out=deepcopy(s);end_session(out,'user');_put(repo,out)
        if s['ended']:
            last=next((m['text'] for m in reversed(s['messages']) if m['role']=='customer'),'')
            voice=st.session_state.get('studio_voice_'+s['id'],'alloy')
            audio_key=sha256((s['id']+last+voice).encode()).hexdigest()
            audio=st.session_state.get('_studio_audio_cache',{}).get(audio_key)
            if audio:st.audio(audio,format='audio/wav',autoplay=st.session_state.get('_studio_autoplay_key')==audio_key)
            st.markdown('<div class="studio-kicker">SESSION COMPLETE</div>',unsafe_allow_html=True)
            finish=immersion.ending(s)
            st.title(finish['title']);st.info(finish['action'])
            with st.chat_message('assistant',avatar=':material/person:'):st.write(finish['last_reply'])
            if finish['decision_quote'] and finish['decision_quote']!=finish['last_reply']:st.caption('고객의 결정 · '+finish['decision_quote'])
            st.caption('상담의 결과와 과정의 완성도는 별개입니다. 놓친 질문은 복기에서 확인하세요.')
            _comparison(s)
            if not s.get('report'):
                role='EVALUATOR' if s['mode']=='ASSESSMENT' else 'COACH'
                if st.button(f'근거 기반 피드백 생성 · {config.credits(role)} Credit',type='primary'):
                    with st.spinner('대화 근거를 확인하고 있습니다…'):st.session_state['_studio_state']=runtime.evaluate(s)
                    st.rerun()
            else:render_report(s['report'])
            _moments(repo,s)
            with st.expander('전체 대화 복기'):
                for m in s['messages']:st.write(('나' if m['role']=='advisor' else '고객')+' · '+m['text'])
            with st.expander('고객 자료 · 연습 내역'):
                _materials(s)
                st.caption(f"힌트 {len(s['hints'])}회 · 되돌리기 {len(s['attempts'])}회")
            _sharing(repo,s)
            if s['mode']=='ASSESSMENT':
                with st.expander('판정 확인 요청'):
                    note=st.text_area('확인이 필요한 이유',max_chars=1000,key='studio_review_note')
                    if st.button('확인 요청 기록',disabled=not note.strip()):
                        repo.review(s['id'],note);st.success('판정 확인 요청을 기록했습니다.')
                    for r in repo.reviews(s['id']):st.write(r['event'],r['note'])
            st.download_button('내 대화와 피드백 저장',json.dumps({'messages':s['messages'],'report':s['report']},ensure_ascii=False,indent=2),
                               file_name='화랑_AI상담_복기.json',mime='application/json')
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button('같은 고객 다시 연습'):
                    fresh=new_session(owner,stage=s['initial_stage'],difficulty=s['difficulty'],journey=s['journey'],personality=s['personality'],seed=s['case']['seed'])
                    fresh['case']=deepcopy(s['case']);st.session_state['_studio_state']=repo.save(fresh);st.rerun()
            with c2:
                if st.button('같은 목표 · 새로운 고객'):
                    st.session_state['_studio_state']=repo.save(new_session(owner,stage=s['initial_stage'],difficulty=s['difficulty'],journey=s['journey']));st.rerun()
            with c3:
                if st.button('다른 훈련 선택'):
                    st.session_state.pop('_studio_state',None);st.session_state.pop('_studio_preview',None);st.rerun()
            if any('before' in t for t in s['turns']):
                n=st.selectbox('취약 장면 재연습', [t['number'] for t in s['turns'] if 'before' in t],format_func=lambda n:f'{n}번째 답변 직전')
                if st.button('이 장면에서 다시 답하기'):
                    out=practice_from(s,n);_put(repo,out)
            return
        if s['warning']:st.warning('상담 맥락과 관련 없는 응답이 연속 확인되었습니다. 한 번 더 반복되면 이번 평가는 종료됩니다.')
        count=sum(t['stage']==s['stage'] for t in s['turns']);remain=LIMITS[s['stage']]-count
        if remain<=3:st.caption(f'이번 장면의 답변 기회가 {remain}회 남았습니다. 마무리하거나 종료 후 다시 연습할 수 있습니다.')
        show_signals=False
        if s['mode']=='PRACTICE':
            show_signals=st.toggle('대화 변화 안내 보기',value=False,key='studio_signals_'+s['id'],help='대사에서 확인된 변화만 표시합니다. 신뢰 점수나 숨은 고객 설정은 표시하지 않습니다.')
        signals=immersion.visible_signals(s,show_signals)
        with st.container(height=440,border=False,key='studio_chat_log'):
            for index,m in enumerate(s['messages']):
                with st.chat_message('user' if m['role']=='advisor' else 'assistant',avatar=None if m['role']=='advisor' else ':material/person:'):
                    st.write(m['text'])
                    if m.get('attachment')=='insurance':_attachment(s,'studio_document_'+str(index))
                if m['role']=='customer':
                    for signal in signals:
                        if signal['turn']==m.get('turn'):st.caption('관찰 · '+signal['label']+' / “'+signal['quote']+'”')
        _comparison(s)
        if s['stage_complete']:
            if s.get('appointment'):st.success('다음 상담 약속 · '+s['appointment']['label'])
            else:st.success('이번 상담 장면을 마쳤습니다.')
            st.caption('다음 장면은 같은 고객의 이후 상담입니다. 지금까지 나눈 대화를 기억합니다.')
            if st.button('다음 상담 단계로',type='primary'):
                out=deepcopy(s);next_stage(out);_put(repo,out)
        if s['mode']=='PRACTICE':
            with st.expander('막힐 때 도움받기'):
                key=f"{s['branch']}:{len(s['turns'])}:{s['stage']}"
                hint=s['hint_cache'].get(key)
                if not hint:
                    if st.button(f'힌트 준비 · {config.coach_credits} Credit'):
                        with st.spinner('현재 대화에 맞는 힌트를 준비합니다…'):st.session_state['_studio_state']=runtime.hint(s)
                        st.rerun()
                else:
                    st.write('방향: '+hint['direction'])
                    with st.expander('질문의 의도 보기'):st.write(hint['intention'])
                    with st.expander('예시 문장 보기'):st.write(hint['example'])
                if any('before' in t for t in s['turns']):
                    n=st.selectbox('되돌릴 답변',[t['number'] for t in s['turns'] if 'before' in t],format_func=lambda n:f'{n}번째 답변 직전')
                    st.caption('고객 상태도 복원합니다. 이미 처리된 Credit·Voice 사용량은 되돌리지 않습니다.')
                    if st.button('선택 장면으로 돌아가기'):
                        out=deepcopy(s);rewind(out,n);_put(repo,out)
        if not s['stage_complete']:_conversation(repo,runtime,s,config,permissions)
    except Exception as exc:st.error(_safe_error(exc))


def _conversation(repo,runtime,s,config,permissions):
    options=['텍스트','음성','혼합'] if 'academy.voice_simulator' in permissions else ['텍스트']
    preferred=st.session_state.get('_studio_interaction','텍스트')
    interaction=st.radio('대화 방식',options,index=options.index(preferred) if preferred in options else 0,horizontal=True,key='studio_interaction_control')
    st.session_state['_studio_interaction']=interaction
    widget=f"{s['id']}:{s['branch']}:{len(s['turns'])}"
    text_key='studio_input_'+widget
    auto_speak=False;voice='alloy'
    if interaction!='텍스트':
        profile=s['case']['customer_state']
        default_voice='sage' if profile.get('age',0)>=60 else ('nova' if profile.get('gender') in ('female','F','여성','여') else 'onyx')
        voice=st.selectbox('고객 목소리',['alloy','nova','onyx','coral','sage'],index=['alloy','nova','onyx','coral','sage'].index(default_voice),key='studio_voice_'+s['id'])
        auto_speak=st.checkbox('답변 후 고객 음성 자동 생성·재생 · Voice 사용',value=interaction=='음성',key='studio_auto_speak')
        st.caption('합성 고객 목소리입니다. 음성은 처리에 필요한 동안만 메모리에 유지하며 학습 기록에는 저장하지 않습니다.')
        c1,c2=st.columns(2)
        with c1:
            recorded=st.audio_input('눌러 녹음하고 종료',key='studio_audio_'+widget)
            if recorded and st.button('음성을 글로 변환 · Voice 사용',key='studio_transcribe_'+widget):
                audio=recorded.getvalue()
                cache=st.session_state.setdefault('_studio_transcript_cache',{})
                cache_key=sha256((s['id']+widget).encode()+audio).hexdigest()
                if cache_key in cache:
                    st.session_state[text_key]=cache[cache_key];st.rerun()
                with st.spinner('음성을 인식하고 있습니다…'):updated,text=runtime.transcribe(s,audio)
                cache[cache_key]=text
                st.session_state['_studio_state']=updated;st.session_state[text_key]=text;st.rerun()
        with c2:
            last=next((m['text'] for m in reversed(s['messages']) if m['role']=='customer'),'')
            audio_key=sha256((s['id']+last+voice).encode()).hexdigest()
            cache=st.session_state.setdefault('_studio_audio_cache',{})
            if audio_key in cache:st.audio(cache[audio_key],format='audio/wav',autoplay=st.session_state.get('_studio_autoplay_key')==audio_key)
            else:
                if st.button(('고객 목소리 미리듣기' if not s['turns'] else '고객 답변 듣기')+' · Voice 사용',key='studio_speech_'+widget):
                    with st.spinner('고객 음성을 준비하고 있습니다…'):updated,data=runtime.speak(s,last,voice)
                    st.session_state['_studio_state']=updated
                    if data:cache[audio_key]=data
                    # Bound in-memory audio retention.
                    while len(cache)>6:cache.pop(next(iter(cache)))
                    st.rerun()
            st.caption('생성 전 최대 180초를 예약하고 실제 생성 길이만 차감합니다. 같은 음성의 재생·일시정지는 추가 호출하지 않습니다.')
        st.caption('인식된 문장을 확인·수정한 뒤 제출하세요. 음성 인식 오류는 상담 답변으로 자동 제출되지 않습니다.')
    draft=st.session_state.get(text_key,'')
    if draft:
        with st.expander('인식한 문장 확인',expanded=True):
            edited=st.text_area('보낼 문장',value=draft,max_chars=2400,key='studio_review_'+widget)
            voice_submit=st.button('확인한 문장 보내기',type='primary')
    else:edited='';voice_submit=False
    text=st.chat_input('고객에게 메시지 보내기…',max_chars=2400,key='studio_chat_'+widget)
    submit=bool(text) or voice_submit
    if voice_submit:text=edited
    if submit:
        with st.chat_message('user'):st.write(text)
        with st.spinner('고객이 답변하고 있습니다…'):st.session_state['_studio_state']=runtime.send(s,text)
        if auto_speak and not st.session_state['_studio_state']['ended']:
            updated=st.session_state['_studio_state']
            last=next((m['text'] for m in reversed(updated['messages']) if m['role']=='customer'),'')
            try:
                with st.spinner('고객 음성을 준비하고 있습니다…'):updated,audio=runtime.speak(updated,last,voice)
                st.session_state['_studio_state']=updated
                key=sha256((updated['id']+last+voice).encode()).hexdigest()
                if audio:
                    cache=st.session_state.setdefault('_studio_audio_cache',{});cache[key]=audio
                    while len(cache)>6:cache.pop(next(iter(cache)))
                    st.session_state['_studio_autoplay_key']=key
            except Exception as exc:st.session_state['_studio_notice']='대화 답변은 저장했습니다. 음성 처리: '+_safe_error(exc)
        st.rerun()


def render_operations(auth,actor):
    with st.expander('AI 상담 모델·차감 설정'):
        try:
            repo=Repository(auth,actor);config=Config.from_mapping(st.secrets)
            for k,v in (repo.rpc('settings') or {}).items():setattr(config,k,v)
            with st.form('studio_model_settings'):
                changes={}
                for key,label in [('customer_model','고객 역할'),('coach_model','코칭·자유 연습 피드백'),('evaluator_model','공식 평가'),('transcription_model','음성 인식'),('speech_model','고객 목소리')]:
                    changes[key]=st.text_input(label,getattr(config,key),max_chars=100)
                for key,label in [('customer_credits','고객 답변 Credit'),('coach_credits','코칭·자유 피드백 Credit'),('evaluator_credits','공식 평가 Credit')]:
                    changes[key]=st.number_input(label,min_value=1,max_value=10000,value=getattr(config,key),step=1)
                st.caption('기존 월 지급·구매 잔액·Voice 원장 정책은 변경하지 않습니다. API 키는 서버 Secrets에서 관리합니다.')
                if st.form_submit_button('모델·차감 단위 저장'):
                    repo.rpc('configure',p_settings=changes);st.success('설정을 저장했습니다. 다음 요청부터 화면에 표시된 단위가 적용됩니다.')
        except Exception as exc:st.warning(_safe_error(exc))
    st.caption('학습 AI 비용은 확인된 금액만 집계합니다. API 비용 미확인 요청이 있으면 실제 총비용은 더 클 수 있습니다.')
    with st.expander('AI 상담 요청 확인 · 비용 미확인'):
        st.caption('API 비용 미확인 요청은 0원이 아닙니다. 아래 기존 비용 합계에는 미확인 비용이 포함되지 않습니다.')
        try:
            repo=Repository(auth,actor)
            pending=repo.rpc('pending') or []
            st.dataframe(pending,hide_index=True,width='stretch')
            if not pending:return
            chosen=st.selectbox('확인할 요청',pending,format_func=lambda r:r['purpose']+' · '+r['created_at']+' · '+r['op_key'][:10])
            st.warning('공급자 처리 기록과 원장을 먼저 대조하세요. 처리 중인 요청은 조정할 수 없습니다. 음성 처리 완료·이미 만료된 원장은 별도 정산 확인이 필요합니다.')
            delivered=st.radio('확인 결과',['외부 처리되지 않음 확인','외부 처리 완료·응답 유실 확인'],key='studio_resolve_result')
            note=st.text_area('확인 근거와 처리 사유',max_chars=1000,key='studio_resolve_note')
            verified=st.checkbox('공급자 기록과 해당 요청 식별자를 대조했습니다.',key='studio_resolve_verified')
            if st.button('원장 정산 후 요청 보류 해제',disabled=not verified or len(note.strip())<10):
                repo.rpc('resolve',p_op=chosen['op_key'],p_delivered=delivered.startswith('외부 처리 완료'),p_note=note)
                st.success('정산·처리 이력을 기록했습니다. 사용자 화면에서 저장 상태를 다시 불러와 주세요.')
        except Exception as exc:st.warning(_safe_error(exc))


def render_shared(payload):
    if payload.get('summary'):
        summary=payload['summary']
        st.write(summary.get('status') or '요약 결과 없음')
        for row in summary.get('levels',[]):st.write(CRITERIA.get(row['criterion'],row['criterion'])+' · '+LEVELS.get(row['level'],row['level']))
    if payload.get('feedback'):render_report(payload['feedback'])
    if payload.get('transcript'):
        for m in payload['transcript']:
            with st.chat_message('user' if m['role']=='advisor' else 'assistant'):st.write(m['text'])
