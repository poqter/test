'use strict';
(() => {
  const root=document.getElementById('app'), status=document.getElementById('connection-status');
  const params=new URLSearchParams(location.search), frag=new URLSearchParams(location.hash.slice(1));
  const embedded=window.parent!==window;
  let model=null,busy=false,lastEvent=null,timeoutId=null,parentOrigin=null;
  let mode=params.get('mode')||'GUIDE',selected=params.get('scenario')||'C07-S01',sessionLength=params.get('length')||'STANDARD';
  let mapGroup='ALL',reportTab='summary',typing='',customerThinking=false,pendingAdvisorText='',guideInserted=false,missionModalOpen=false,completionFlash=false;
  const chatScroll={top:0,nearBottom:true,unread:false,forceBottom:true,restoring:false};let lastMessageCount=0;
  const token=frag.get('access')||'';
  const localSid=(()=>{if(crypto.randomUUID)return crypto.randomUUID();const a=new Uint8Array(16);crypto.getRandomValues(a);return [...a].map(x=>x.toString(16).padStart(2,'0')).join('')})();
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const badge=(text,cls='')=>`<span class="badge ${cls}">${esc(text)}</span>`;
  const button=(text,action,cls='action',attrs='')=>`<button type="button" class="${cls}" data-action="${action}" ${attrs}>${text}</button>`;
  const brand=(subtitle='ACADEMY')=>`<div class="brand"><span class="mark">H</span><div><strong>HWARANG</strong><small>${subtitle}</small></div></div>`;
  const historyKey=id=>'hwarang-academy-profile-history:'+id;
  function recentProfiles(id){try{return JSON.parse(localStorage.getItem(historyKey(id))||'[]').slice(-3)}catch{return []}}
  function rememberProfile(s){if(!s?.profile_id)return;try{let a=recentProfiles(s.scenario_id).filter(x=>x!==s.profile_id);a.push(s.profile_id);localStorage.setItem(historyKey(s.scenario_id),JSON.stringify(a.slice(-3)))}catch{}}
  function simulatorUrl(id='C07-S01',m='GUIDE',len='STANDARD'){
    const base=model?.base_url||location.origin+location.pathname,u=new URL(base,location.href);u.search='';u.searchParams.set('view','simulator');u.searchParams.set('scenario',id);u.searchParams.set('mode',m);u.searchParams.set('length',len);if(!embedded)u.hash='access='+encodeURIComponent(token);return u.href;
  }
  function frameHeight(){if(!embedded)return;const phase=model?.phase;const fixed=phase==='session'?1040:phase==='setup'?1120:null;post('streamlit:setFrameHeight',{height:fixed||Math.ceil(Math.max(document.body.scrollHeight,920))})}
  function captureChatState(){const el=document.getElementById('messages');if(!el||chatScroll.restoring)return;chatScroll.top=el.scrollTop;chatScroll.nearBottom=(el.scrollHeight-el.scrollTop-el.clientHeight)<90;if(chatScroll.nearBottom)chatScroll.unread=false}
  function restoreChatState(){const el=document.getElementById('messages');if(!el)return;const toBottom=chatScroll.forceBottom||chatScroll.nearBottom;const apply=()=>{if(toBottom){el.scrollTop=el.scrollHeight;chatScroll.unread=false}else{el.scrollTop=Math.min(chatScroll.top,Math.max(0,el.scrollHeight-el.clientHeight))}};chatScroll.restoring=true;apply();requestAnimationFrame(()=>{apply();chatScroll.forceBottom=false;chatScroll.restoring=false})}
  function currentMessageCount(next=model){return next?.session?.messages?.length||0}
  function post(type,data){window.parent.postMessage({isStreamlitMessage:true,type,...data},parentOrigin&&parentOrigin!=='null'?parentOrigin:'*')}
  function willCreateCustomerReply(kind){return kind==='commit'||(kind==='send'&&mode!=='COACH')}
  async function action(kind,data={},reuse=false){
    if(busy&&!reuse)return;
    const a=reuse?lastEvent:{kind,event_id:crypto.randomUUID?crypto.randomUUID():localSid+Date.now(),...data};if(!a)return;
    lastEvent=a;busy=true;status.textContent='처리 중…';
    clearTimeout(timeoutId);timeoutId=setTimeout(()=>{busy=false;customerThinking=false;status.textContent='응답이 지연되고 있습니다. 같은 입력을 다시 보내지 말고 연결 상태를 확인해 주세요.';render()},12000);
    if(embedded){post('streamlit:setComponentValue',{value:a,dataType:'json'});return}
    try{
      const response=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Hwarang-Local':token},body:JSON.stringify({session:localSid,view:params.get('view'),scenario:params.get('scenario'),mode:params.get('mode'),action:a})});
      if(!response.ok)throw new Error('HTTP '+response.status);const next=await response.json();receive(next);
    }catch(e){clearTimeout(timeoutId);busy=false;customerThinking=false;status.textContent='연결을 확인해 주세요. 입력 내용은 화면에 남아 있습니다.';render()}
  }
  function receive(next){
    if(!next)return;
    const producing=willCreateCustomerReply(lastEvent?.kind||'') && next.session && !next.error;
    const apply=()=>{
      captureChatState();const beforeCount=lastMessageCount;const wasNear=chatScroll.nearBottom;const previousPhase=model?.phase;
      model=next;clearTimeout(timeoutId);busy=false;customerThinking=false;pendingAdvisorText='';status.textContent='';
      if(previousPhase==='session'&&next.phase==='result'&&next.session?.end_reason==='mission_complete'){
        completionFlash=true;setTimeout(()=>{completionFlash=false;render()},950);
      }
      const afterCount=currentMessageCount(next);if(afterCount>beforeCount&&!wasNear)chatScroll.unread=true;chatScroll.forceBottom=wasNear;lastMessageCount=afterCount;
      if(model.phase==='session'||model.phase==='result'){mode=model.session.mode;selected=model.session.scenario_id;sessionLength=model.session.session_length;rememberProfile(model.session)}
      else{mode=model.mode||mode;selected=model.selection||selected;sessionLength=model.session_length||sessionLength}
      if(!model.error&&['send','commit','start','retry','retry_new','retry_harder','setup'].includes(lastEvent?.kind))typing='';
      render();
    };
    if(producing){customerThinking=true;status.textContent='';render();setTimeout(apply,next.session?.reply_delay_ms||900)}else apply();
  }
  function viewerBlock(dark=false){
    const v=model?.viewer||{},name=v.display_name||v.login_id||'사용자';
    const meta=[v.organization_name,v.position_name].filter(Boolean).join(' · ');
    return `<div class="viewer ${dark?'dark':''}"><div class="viewer-avatar">${esc(String(name).slice(0,1))}</div><div><strong>${esc(name)}</strong><small>${esc(meta||'HWARANG ACADEMY')}</small></div></div>`;
  }
  function header(){return `<header class="topbar"><div class="brand-wrap">${brand()}<div class="tagline">Learn Today, Grow Together<small>배움을 넘어, 더 나은 내일의 전문가로</small></div></div>${viewerBlock(false)}</header>`}
  const hasPerm=code=>(model?.feature_permissions||[]).includes(code);
  function moduleCard(icon,title,copy,ready=false,actionName='',scenarioId=''){
    const state=ready?'<span class="module-status ready">사용 가능</span>':'<span class="module-status">준비 중</span>';
    const resume=Boolean(model?.simulator_status?.has_session);
    const action=ready?`<button type="button" class="module-action module-action-button" data-action="${esc(actionName)}" data-id="${esc(scenarioId)}">${resume?'이어하기':'시작하기'} →</button>`:'<span class="module-action disabled">준비 중</span>';
    return `<article class="module-card ${ready?'featured':''}"><div class="module-top"><span class="module-icon">${icon}</span>${state}</div><h3>${title}</h3><p>${copy}</p>${action}</article>`;
  }
  function home(){
    const first=model.scenarios.find(x=>x.id==='C07-S01')||model.scenarios[0],v=model.viewer||{},sim=model.simulator_status||{},canSim=hasPerm('academy.simulator');
    const simLead=!canSim
      ? `<b>현재 계정에는 이용 권한이 없습니다.</b><p>최고관리자에게 AI 상담 시뮬레이터 권한을 요청해 주세요.</p>`
      : sim.has_session
      ? `<b>${sim.ended?'최근 상담 결과를 다시 확인할 수 있습니다.':'진행 중인 상담이 있습니다.'}</b><p>${esc(sim.title||'AI 상담 시뮬레이터')} · ${esc(sim.mode||'')}</p><button type="button" class="text-link text-link-button" data-action="open-simulator" data-id="${esc(sim.scenario_id||first.id)}">${sim.ended?'결과 이어보기':'상담 이어하기'} →</button>`
      : `<b>AI 상담 시뮬레이터</b><p>실제 고객과 상담하듯 훈련하고 상담 과정과 역량을 확인해보세요.</p><button type="button" class="text-link text-link-button" data-action="open-simulator" data-id="${esc(first.id)}">시뮬레이터 시작 →</button>`;
    return `${header()}<div class="academy-layout"><nav class="academy-nav" aria-label="아카데미 메뉴">${button('⌂ <span>홈</span>','home','nav-item current')}${canSim?button('◉ <span>AI 상담 시뮬레이터</span>','open-simulator','nav-item nav-link',`data-id="${esc(sim.scenario_id||first.id)}"`):'<button class="nav-item" disabled>◉ <span>AI 상담 시뮬레이터</span><small>권한 없음</small></button>'}<button class="nav-item" disabled>♧ <span>신입교육</span><small>준비 중</small></button><button class="nav-item" disabled>▦ <span>상담교육</span><small>준비 중</small></button><button class="nav-item" disabled>▤ <span>보험실무</span><small>준비 중</small></button><button class="nav-item" disabled>✓ <span>시험 · 평가</span><small>준비 중</small></button><button class="nav-item" disabled>▣ <span>교육자료실</span><small>준비 중</small></button><button class="nav-item" disabled>♙ <span>나의학습</span><small>준비 중</small></button><div class="nav-foot"><span>Better Advisor<br>A Brighter Tomorrow</span><br><br>Planned &amp; Built by<br>박병선 팀장</div></nav><main class="academy-main academy-dashboard"><section class="academy-home-hero"><div><span class="eyebrow">HWARANG ACADEMY</span><h1>배움이 만드는<br>더 큰 가능성</h1><p>상담 역량부터 보험 실무까지.<br>FP의 성장을 위한 통합 교육 플랫폼</p></div><div class="hero-quote">Grow Today<br><b>Lead Tomorrow</b><small>“오늘의 배움이 내일의 더 큰 가능성을 만듭니다.”</small></div></section><div class="section-head academy-module-head"><h2>교육 프로그램</h2><span class="muted">필요한 교육과 실습을 선택해 시작하세요.</span></div><section class="academy-modules">${moduleCard('◉','AI 상담 시뮬레이터','실제 고객과 상담하듯 훈련하고 상담 과정과 역량을 전문적으로 평가합니다.',canSim,'open-simulator',sim.scenario_id||first.id)}${moduleCard('♧','신입교육','30일 · 60일 · 90일 단계별 온보딩 교육과정을 제공합니다.')}${moduleCard('▦','상담교육','TA부터 1차·2차 미팅, 니즈 파악과 클로징까지 단계별로 학습합니다.')}${moduleCard('▤','보험실무','보장분석, 계약, 청구 등 실무에 필요한 핵심 지식을 학습합니다.')}${moduleCard('✓','시험 · 평가','지식 평가부터 상담 실기까지 나의 역량을 점검합니다.')}${moduleCard('▣','교육자료실','스크립트, 체크리스트, 교안 등 교육 자료를 한곳에서 확인합니다.')}${moduleCard('♙','나의학습','학습 진도, 평가 결과와 성장 기록을 한눈에 확인합니다.')}</section><section class="academy-home-lower"><article class="academy-summary-card"><div class="intro-row"><h3>나의 학습 요약</h3><span class="muted">${esc(v.display_name||v.login_id||'사용자')}</span></div><div class="summary-placeholder"><b>아직 누적된 학습 기록이 없습니다.</b><p>상담 이력과 평가가 저장되면 진행 중 과정, 완료 교육과 성장 현황을 이곳에서 확인할 수 있습니다.</p></div></article><article class="academy-summary-card"><div class="intro-row"><h3>AI 상담 시뮬레이터</h3><span class="muted">PRACTICE</span></div><div class="summary-placeholder">${simLead}</div></article><article class="academy-summary-card"><div class="intro-row"><h3>공지사항</h3><span class="muted">ACADEMY</span></div><div class="summary-placeholder"><b>HWARANG 계정으로 학습 기록이 연결됩니다.</b><p>상담 훈련과 평가, 성장 기록을 개인별로 이어서 확인할 수 있도록 확장됩니다.</p></div></article></section></main></div>`;
  }
  function simHeader(){return `<div class="sim-top"><div class="sim-brand-group">${button('← ACADEMY 홈','academy-home','sim-home-button')}${brand('ACADEMY / AI 상담 시뮬레이터')}</div><span class="tagline">연습이, 실력을 만듭니다.</span>${viewerBlock(true)}</div>`}
  function selectedScenario(){return model.scenarios.find(s=>s.id===selected)||model.scenarios[0]}
  function missionModal(sc,brief){
    if(!missionModalOpen)return '';
    const modeInfo=model.modes.find(x=>x.id===mode),lengthInfo=model.lengths.find(x=>x.id===sessionLength);
    brief=brief||{};
    const situation=brief.situation?`<div class="mission-block"><small>상황</small><p>${esc(brief.situation)}</p></div>`:'';
    const finalGoal=brief.final_goal||brief.text||sc.objectives?.[mode]||'';
    const detail=mode==='GUIDE' && (brief.guide_points||[]).length
      ? `<div class="mission-block"><small>이번 상담에서 확인할 것</small><div class="mission-points">${brief.guide_points.map(x=>`<span>✓ ${esc(x)}</span>`).join('')}</div></div>`
      : mode==='ASSESSMENT'?'<p class="mission-privacy">평가 모드에서는 세부 체크포인트는 숨기고 최종 목표만 제시합니다.</p>':'';
    const boundary=brief.boundary?`<div class="mission-block boundary"><small>이번 미션의 경계</small><p>${esc(brief.boundary)}</p></div>`:'';
    const endings=(brief.valid_endings||[]).length?`<div class="mission-block"><small>정상 종료로 인정되는 방식</small><div class="mission-points">${brief.valid_endings.map(x=>`<span>✓ ${esc(x)}</span>`).join('')}</div></div>`:'';
    const guideRule=mode==='GUIDE'&&brief.guide_completion_rule?`<div class="mission-block guide-rule"><small>GUIDE 운영 원칙</small><p>${esc(brief.guide_completion_rule)}</p></div>`:'';
    return `<div class="mission-modal-backdrop" data-action="mission-close" role="presentation"><section class="mission-modal glass" role="dialog" aria-modal="true" aria-labelledby="mission-title" onclick="event.stopPropagation()"><div class="mission-modal-top"><div><span class="eyebrow">MISSION BRIEFING</span><small>${esc(sc.id)} · ${esc(mode)} · ${esc(sessionLength)}</small></div>${button('×','mission-close','mission-close-btn','aria-label="미션 창 닫기"')}</div><div class="mission-code">${esc(sc.id.split('-')[0])}</div><h2 id="mission-title">${esc(sc.name)}</h2>${situation}<div class="mission-block final"><small>최종 목표 · 이 상태가 되면 상담 종료</small><p>${esc(finalGoal)}</p></div>${endings}${detail}${guideRule}${boundary}<div class="mission-role"><strong>당신의 역할</strong><p>최종 목표까지 가는 방법은 하나가 아닙니다. 중간 확인을 일부 놓쳐도 최종 목표가 달성되면 상담은 종료되고, 빠진 부분은 결과에서 평가합니다.</p></div><div class="mission-meta"><span>${esc(modeInfo?.name||mode)}</span><span>${esc(lengthInfo?.name||sessionLength)} · ${esc(lengthInfo?.minutes||'')}</span></div><div class="mission-modal-actions">${button('돌아가기','mission-close','action ghost')}${button('미션 확인 · 상담 시작 →','start-confirm','action light')}</div></section></div>`;
  }
  function setup(){
    const sc=selectedScenario(),brief=sc.mission_briefings?.[mode]||{text:sc.objectives[mode],guide_points:mode==='GUIDE'?sc.guide_points:[]};
    return `<main class="sim-wrap">${simHeader()}<section class="glass setup"><div class="setup-lead"><div><span class="eyebrow">COUNSELING SIMULATOR · V5 CORE</span><h1>상담 시뮬레이터</h1><p>훈련 방식을 선택한 뒤 시작 직전에 이번 상담의 미션을 확인합니다.</p></div>${badge('규칙 기반 · 맥락형 대화','dark')}</div><div class="step-label"><span>01</span>훈련 방식을 선택하세요</div><div class="modes">${model.modes.map((m,i)=>`<button type="button" class="mode-card ${mode===m.id?'selected':''}" data-action="mode" data-id="${esc(m.id)}"><span class="mode-check">${mode===m.id?'✓ 선택됨':'0'+(i+1)}</span><strong>${esc(m.id)}</strong><b>${esc(m.name)}</b><p>${esc(m.purpose)}</p></button>`).join('')}</div><div class="step-label"><span>02</span>훈련 길이를 선택하세요</div><div class="lengths">${model.lengths.map(l=>`<button type="button" class="length-card ${sessionLength===l.id?'selected':''}" data-action="length" data-id="${l.id}"><strong>${esc(l.name)}</strong><span>${esc(l.minutes)}</span><p>${esc(l.description)}</p></button>`).join('')}</div><div class="step-label"><span>03</span>오늘의 상담 상황을 선택하세요 ${button('🎲 다른 과제','random','action ghost small')}</div><div class="scene-choices">${model.scenarios.map(s=>`<button class="scene-choice ${s.id===selected?'selected':''}" data-action="scene" data-id="${esc(s.id)}"><strong>${esc(s.name)}</strong><small>${esc(s.id)} · ${esc(s.label)}</small></button>`).join('')}</div><div class="setup-footer"><div><p>미션은 상담 시작 직전에 별도 창으로 표시됩니다.</p><small>같은 과제를 다시 선택해도 고객 프로필·표현·허용된 이벤트가 달라질 수 있습니다.</small></div>${button('미션 확인 후 시작 →','mission-open','action light')}</div></section>${missionModal(sc,brief)}</main>`;
  }
  function customerPanel(s){
    let meters='';if(s.states)meters=`<div class="states"><strong>고객 상태 · 연출용</strong>${[['trust','신뢰'],['resistance','경계'],['patience','인내']].map(([k,v])=>`<div class="meter-line"><span>${v}</span><div class="meter"><i style="width:${s.states[k]}%"></i></div><b>${s.states[k]}</b></div>`).join('')}<p>실제 심리 측정값이나 학습 점수가 아닙니다.</p></div>`;
    const hasProgress=Number.isFinite(s.completion?.done)&&Number.isFinite(s.completion?.total);
    const progress=hasProgress?Math.round((s.completion.done/Math.max(1,s.completion.total))*100):null;
    const miniGoal=s.mission_briefing?.final_goal||s.mission;
    return `<aside class="glass customer-panel"><div class="customer-title"><span class="avatar">◎</span><div><strong>오늘의 가상 고객</strong><small>${esc(s.scenario_id)} · 공개된 정보</small></div></div><div class="mission-mini"><small>MISSION · ${esc(s.stage)}</small><p>${esc(miniGoal)}</p>${progress===null?'':`<div class="mini-progress"><div class="meter"><i style="width:${progress}%"></i></div><span>${progress}%</span></div>`}</div><div class="public-heading">대화에서 확인한 내용</div><div class="public-record">${s.public_facts.map(f=>`<div class="fact"><small>${esc(f.label)}${f.turn?' · '+f.turn+'번째 응답':''}</small><div>${esc(f.value)}</div></div>`).join('')}</div>${meters}</aside>`;
  }
  function guidePanel(){
    const g=model.guide_panel;if(!g)return '';
    const alt=(g.alternatives||[]).length?`<div class="guide-alternatives"><strong>현재 가능한 다른 경로</strong>${g.alternatives.map(a=>`<div class="guide-alt"><span>${esc(a.label)}</span><p>${esc(a.text)}</p><button type="button" class="action ghost small" data-action="insert-guide" data-text="${esc(a.text)}">이 경로 사용</button></div>`).join('')}</div>`:'';
    const route=g.route_action?`<div class="guide-route-meta"><span>${g.rescue?'RECOVERY ROUTE':'TRAINING ROUTE'}</span><b>${esc(g.training_route_name||g.route_action)}</b>${g.target_minutes?`<small>권장 학습 길이 ${esc(g.target_minutes)}</small>`:''}</div>`:'';
    const purpose=g.purpose?`<div class="guide-purpose"><strong>왜 지금 이 질문인가?</strong><p>${esc(g.purpose)}</p></div>`:'';
    const loops=(g.open_loops||[]).length?`<div class="guide-open-loops"><strong>아직 열려 있는 상담 과제</strong>${g.open_loops.slice(0,3).map(x=>`<p>• ${esc(x.label)}</p>`).join('')}</div>`:'';
    return `<aside class="guide-panel glass"><div class="guide-head"><div><span class="eyebrow">GUIDE ASSIST</span><strong>실시간 코칭</strong></div>${badge(g.rescue?'복구 경로':'항상 표시','dark')}</div>${route}<div class="guide-core"><span class="eyebrow">지금의 핵심</span><p>${esc(g.hint)}</p></div><div class="guide-card good"><strong>✓ 권장 답변</strong><p>${esc(g.recommended)}</p><button type="button" class="action light small" data-action="insert-guide" data-text="${esc(g.recommended)}">답변에 넣기</button>${purpose}</div>${alt}${loops}<div class="guide-card okay"><strong>△ 무난한 답변</strong><p>${esc(g.adequate)}</p><button type="button" class="action secondary small" data-action="insert-guide" data-text="${esc(g.adequate)}">답변에 넣기</button></div><div class="guide-card caution"><strong>! 주의할 답변</strong><p>${esc(g.avoid)}</p><details><summary>왜 주의해야 하나?</summary><p>고객 상황을 충분히 확인하기 전에 결론·권고를 앞서 내리거나 선택권을 좁히는 표현은 피하세요.</p></details></div><p class="guide-foot">권장 답변은 가장 짧은 완주 경로가 아니라 충분한 학습 단계를 거치는 훈련 경로를 사용합니다. 사용자가 직접 더 빠르게 최종 목표에 도달하면 그대로 종료하고 상담 완성도는 별도로 평가합니다.</p></aside>`;
  }
  function chat(s){
    const c=model.coaching,g=model.examples;let msgs=[...s.messages];
    if(customerThinking&&pendingAdvisorText)msgs.push({role:'advisor',text:pendingAdvisorText,turn:s.next_turn});
    return `<section class="conversation" aria-label="밝은 상담 채팅창"><div class="chat-title"><h3>상담 대화</h3><small>${esc(s.session_length)} · 상담사 답변 ${s.next_turn-1}개</small></div>${s.dialogue_notice?`<div class="dialogue-notice" role="status">${esc(s.dialogue_notice)}</div>`:''}<div class="messages" id="messages" role="log" aria-live="polite">${msgs.map(m=>`<div class="msg ${m.role}${m.variant==='event'?' event':''}">${m.role==='customer'?'<span class="msg-avatar">◎</span>':''}<div class="msg-body"><div class="meta">${m.role==='customer'?(m.variant==='event'?'고객 · 추가 상황':'고객'):'나 · 상담사'} ${m.turn?'· '+m.turn:''}</div><div class="bubble">${esc(m.text)}</div></div></div>`).join('')}${customerThinking?`<div class="msg customer thinking"><span class="msg-avatar">◎</span><div class="msg-body"><div class="meta">고객</div><div class="bubble typing-bubble"><i></i><i></i><i></i><span>답변을 생각하고 있습니다</span></div></div></div>`:''}</div>${chatScroll.unread?`<button type="button" class="new-message-btn" data-action="jump-latest">새 메시지 ↓</button>`:''}<div class="composer"><form id="compose"><div class="compose-box"><textarea id="message-input" placeholder="고객에게 할 말을 입력하세요." maxlength="2400" rows="2" ${customerThinking?'disabled':''}>${esc(typing)}</textarea><button type="submit" class="send" ${busy||customerThinking?'disabled':''}>${s.mode==='COACH'?'코칭 확인':'전송'} ↑</button></div><div class="compose-foot"><span>Enter 전송 · Shift + Enter 줄바꿈</span><span id="char-count">${typing.length} / 2400</span></div></form></div>${c?`<div class="coaching"><div class="eyebrow">COACH REVIEW · ${c.revision}번째 작성</div><h3>${esc(c.title)}</h3><p>${esc(c.note)}</p><div class="draft">${esc(c.text)}</div><div class="intent-pills">${c.observed.map(x=>`<span>${esc(x)}</span>`).join('')}</div><div class="action-row">${button('이 답변으로 진행 →','commit','action small')}${button('다시 답해보기','edit','action secondary small')}${button(g?'예시 접기':'예시 보기','examples','action ghost small')}</div>${g?`<div class="examples"><div class="example"><strong>권장 방향</strong>${esc(g.recommended)}</div><div class="example average"><strong>보완 가능한 답변</strong>${esc(g.adequate)}</div></div>`:''}</div>`:''}</section>`;
  }
  function sessionView(){const s=model.session;return `<main class="sim-wrap">${simHeader()}<section class="glass stagebar"><div class="stage-copy"><div class="stage-code">${esc(s.scenario_id.split('-')[0])}</div><div><span class="eyebrow">${esc(s.stage)} · ${esc(s.session_length)} · ${esc(s.scenario_seed||'')}</span><h2>${esc(s.title)}</h2><p>${esc(s.mission_briefing?.final_goal||s.mission)}</p></div></div><div class="stage-actions">${badge(s.mode+' · '+model.modes.find(x=>x.id===s.mode).name,'dark')}${button('상담 종료','finish','action light small')}</div></section><div class="session-layout ${s.mode==='GUIDE'?'with-guide':''}">${customerPanel(s)}${chat(s)}${s.mode==='GUIDE'?guidePanel():''}</div><p class="session-note">GUIDE는 충분한 학습 단계를 거치는 경로를 추천합니다. 사용자가 직접 최종 목표를 빠르게 달성하면 즉시 종료할 수 있으며, 상담 완성도는 결과에서 별도로 평가합니다. 미해석은 자동 오답 처리하지 않습니다.</p></main>`}
  const states={full:'충분한 증거',partial:'부분 증거',not_observed:'미수행',unresolved:'판정 유보',not_applicable:'해당 없음'};
  function rubricRows(){return model.report.rows.map(r=>`<div class="rubric-row"><div class="rubric-head"><h3>${esc(r.name)}</h3>${badge(states[r.state],r.state==='unresolved'?'warm':'')}</div><p>${esc(r.gate)}</p><p>${esc(r.reason)}</p>${r.evidence.slice(-2).map(e=>`<blockquote>${e.turn}번째 상담사 답변<br>${esc(e.text)}</blockquote>`).join('')}</div>`).join('')}
  function reviewRows(){return model.review.map(r=>`<div class="review-row"><h3>${r.turn}번째 대화 ${r.risks.length?badge('위험 후보 · 검수 필요','warm'):''}</h3><p>${esc(r.text)}</p><p class="customer-reply">고객 · ${esc(r.customer)}</p><div class="intent-pills">${r.intents.map(x=>`<span>${esc(x)}</span>`).join('')}</div></div>`).join('')||'<p>아직 제출한 대화가 없습니다.</p>'}
  function criticalMoments(){const ms=model.report.critical_moments||[];if(!ms.length)return '';return `<section class="critical-moments"><div class="eyebrow">CRITICAL MOMENTS</div><h2>결정적인 순간</h2>${ms.map(m=>`<article class="moment ${m.tone==='caution'?'caution':''}"><div><strong>TURN ${m.turn} · ${esc(m.title)}</strong><p>${esc(m.reason)}</p></div><blockquote>나 · ${esc(m.advisor)}<br><span>고객 · ${esc(m.customer)}</span></blockquote></article>`).join('')}</section>`}
  function v5Flow(){const f=model.report.v5_flow||{},good=f.strengths||[],watch=f.watch||[],p=model.report.session_pacing;const pace=p?`<div class="pacing-summary"><strong>상담 속도</strong><p>${esc(p.note)}</p><small>${esc(p.target_minutes)} 설계 · 의미 있는 단계 ${esc(p.meaningful_steps)}개 · 상담사 발화 ${esc(p.turns)}회</small></div>`:'';if(!good.length&&!watch.length&&!pace)return '';return `<section class="flow-analysis"><div class="eyebrow">V5.5 FLOW ANALYSIS</div><h2>상담 흐름 분석</h2>${pace}<div class="flow-grid"><div><strong>잘 이어간 흐름</strong>${good.map(x=>`<p>✓ ${esc(x)}</p>`).join('')||'<p class="muted">확인된 항목이 없습니다.</p>'}</div><div><strong>복기할 흐름</strong>${watch.map(x=>`<p>• ${esc(x)}</p>`).join('')||'<p class="muted">특별한 복구 이슈가 감지되지 않았습니다.</p>'}</div></div></section>`}

  function learningInsights(){const r=model.report||{},miss=r.missed_signals||[],rep=r.unnecessary_repetition||[],un=r.unresolved_items||[];if(!miss.length&&!rep.length&&!un.length)return '';return `<section class="learning-insights"><div class="eyebrow">LEARNING REVIEW</div><h2>놓친 신호와 미해결 항목</h2><div class="insight-grid"><div><strong>놓친 신호</strong>${miss.map(x=>`<p>• TURN ${x.turn} · ${esc(x.signal)}<br><small>${esc(x.note)}</small></p>`).join('')||'<p class="muted">뚜렷한 놓친 신호가 감지되지 않았습니다.</p>'}</div><div><strong>반복·미해결</strong>${rep.map(x=>`<p>• TURN ${x.turn} · ${esc(x.note)}</p>`).join('')}${un.map(x=>`<p>• ${esc(x)}</p>`).join('')||(!rep.length?'<p class="muted">미해결 항목이 없습니다.</p>':'')}</div></div></section>`}
  function missionOutcome(){const m=model.report?.mission_outcome;if(!m)return '';const rows=(m.intermediate||[]).map(x=>`<div class="mission-check ${x.done?'done':'miss'}"><span>${x.done?'✓':'○'}</span><b>${esc(x.label)}</b></div>`).join('');return `<section class="mission-result"><div class="eyebrow">MISSION RESULT</div><h2>${m.final_complete?'최종 목표를 달성했습니다.':'최종 목표를 완료하지 못했습니다.'}</h2><p class="mission-result-goal">${esc(m.final_goal)}</p>${m.followup_schedule?`<p><strong>확정된 후속 일정</strong> · ${esc(m.followup_schedule)}</p>`:''}${m.completion_path?`<p><strong>완료 경로</strong> · ${esc(m.completion_path)}</p>`:''}${rows?`<div class="mission-checks">${rows}</div>`:''}<small>${esc(m.note||'')}</small></section>`}
  function resultView(){const r=model.report,s=model.session,value=r.lower===null?'—':r.lower===r.upper?String(r.lower):`${r.lower}–${r.upper}`;const flash=completionFlash?`<div class="mission-complete-flash"><div><span>MISSION COMPLETE</span><strong>최종 목표를 달성했습니다.</strong><small>${esc(r.mission_outcome?.followup_schedule||'다음 상담 경로가 확정되었습니다.')}</small></div></div>`:'';return `${flash}<main class="sim-wrap">${simHeader()}<section class="glass result"><div class="result-top"><span class="eyebrow">SESSION COMPLETE</span><h1>${s.end_reason==='customer_exit'?'고객이 상담을 종료했습니다.':'오늘의 연습을, 다음 상담의 자신감으로.'}</h1><p>${esc(s.title)} · ${esc(s.mode)} · ${esc(s.session_length)}</p></div><div class="result-overview"><div class="score-ring"><strong>${esc(value)}</strong><span>규칙 기반 잠정 평가</span></div><div>${r.axes.map(a=>`<div class="axis"><span>${esc(a.name)}</span><div class="meter"><i style="width:${a.lower}%"></i></div><b>${a.lower===a.upper?a.lower:a.lower+'–'+a.upper}</b></div>`).join('')}</div></div><div class="report-note">${esc(r.notice)}</div>${missionOutcome()}${v5Flow()}${learningInsights()}${criticalMoments()}<div class="report-tabs">${button('평가 근거','report-summary','action ghost '+(reportTab==='summary'?'active':''))}${button('대화 복기','report-review','action ghost '+(reportTab==='review'?'active':''))}${button('복기 저장','download','action ghost')}</div><div class="report-content">${reportTab==='summary'?rubricRows():reviewRows()}</div><div class="report-actions">${button('같은 고객 다시 도전','retry','action light')}${button('같은 과제 · 새로운 고객','retry-new','action secondary')}${button('더 어려운 상황','retry-harder','action secondary')}${button('다른 훈련 선택','setup','action ghost')}</div></section></main>`}
  function render(){
    if(!model)return;captureChatState();document.body.classList.toggle('simulator',model.independent||['session','result','setup'].includes(model.phase));document.body.classList.toggle('mission-open',missionModalOpen);
    root.innerHTML=(model.error?`<div class="error" role="alert">${esc(model.error)}</div>`:'')+(model.phase==='home'?home():model.phase==='setup'?setup():model.phase==='session'?sessionView():resultView());bind();frameHeight();restoreChatState();
    const input=document.getElementById('message-input');if(input&&!customerThinking&&model.phase==='session'&&!model.coaching)requestAnimationFrame(()=>requestAnimationFrame(()=>{try{input.focus({preventScroll:true})}catch{input.focus()}input.setSelectionRange(input.value.length,input.value.length)}));
  }
  function bind(){
    root.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{
      const k=b.dataset.action;
      if(k==='open-simulator')action('open_simulator',{scenario_id:b.dataset.id||selected})
      else if(k==='academy-home')action('academy_home')
      else if(k==='mode'){missionModalOpen=false;mode=b.dataset.id;render();action('configure',{scenario_id:selected,mode,session_length:sessionLength})}
      else if(k==='length'){missionModalOpen=false;sessionLength=b.dataset.id;render();action('configure',{scenario_id:selected,mode,session_length:sessionLength})}
      else if(k==='scene'){missionModalOpen=false;selected=b.dataset.id;render();action('configure',{scenario_id:selected,mode,session_length:sessionLength})}
      else if(k==='random'){missionModalOpen=false;const pool=model.scenarios.filter(s=>s.id!==selected);const a=new Uint32Array(1);crypto.getRandomValues(a);selected=pool[a[0]%pool.length].id;render();action('configure',{scenario_id:selected,mode,session_length:sessionLength})}
      else if(k==='mission-open'){missionModalOpen=true;render()}
      else if(k==='mission-close'){missionModalOpen=false;render()}
      else if(k==='start-confirm'){missionModalOpen=false;action('start',{scenario_id:selected,mode,session_length:sessionLength,avoid_profiles:recentProfiles(selected)})}
      else if(k==='insert-guide'){typing=b.dataset.text||'';guideInserted=true;render()}
      else if(k==='commit'){pendingAdvisorText=model.coaching?.text||'';customerThinking=true;render();action('commit',{expected_turn:model.session.next_turn,draft_revision:model.coaching.revision})}
      else if(k==='edit'){typing=model.coaching.text;render()}
      else if(k==='examples')action('examples')
      else if(k==='finish'){if(confirm('이 상담을 종료하고 복기할까요?'))action('finish')}
      else if(k==='retry')action('retry')
      else if(k==='retry-new')action('retry_new',{avoid_profiles:recentProfiles(model.session.scenario_id)})
      else if(k==='retry-harder')action('retry_harder',{avoid_profiles:recentProfiles(model.session.scenario_id)})
      else if(k==='setup')action('setup')
      else if(k==='jump-latest'){const m=document.getElementById('messages');if(m){m.scrollTop=m.scrollHeight;chatScroll.top=m.scrollTop;chatScroll.nearBottom=true;chatScroll.unread=false;render()}}
      else if(k==='filter-map'){mapGroup=b.dataset.id;render();document.getElementById('map-anchor')?.scrollIntoView({block:'start'})}
      else if(k==='scroll-cases')document.getElementById('cases-anchor')?.scrollIntoView({behavior:'smooth'})
      else if(k==='scroll-map')document.getElementById('map-anchor')?.scrollIntoView({behavior:'smooth'})
      else if(k==='report-summary'){reportTab='summary';render()}
      else if(k==='report-review'){reportTab='review';render()}
      else if(k==='download'){download()}
      else if(k==='home'){window.scrollTo({top:0,behavior:'smooth'})}
    }));
    if(missionModalOpen){const modal=document.querySelector('.mission-modal');requestAnimationFrame(()=>modal?.querySelector('[data-action=\"start-confirm\"]')?.focus());}
    const msgBox=document.getElementById('messages');if(msgBox){msgBox.addEventListener('scroll',()=>{chatScroll.top=msgBox.scrollTop;chatScroll.nearBottom=(msgBox.scrollHeight-msgBox.scrollTop-msgBox.clientHeight)<90;if(chatScroll.nearBottom&&chatScroll.unread){chatScroll.unread=false;const b=document.querySelector('.new-message-btn');if(b)b.remove()}})}
    const input=document.getElementById('message-input'),form=document.getElementById('compose');if(input&&form){let composing=false;input.addEventListener('compositionstart',()=>composing=true);input.addEventListener('compositionend',()=>composing=false);input.addEventListener('input',()=>{typing=input.value;const c=document.getElementById('char-count');if(c)c.textContent=typing.length+' / 2400'});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&!composing&&e.keyCode!==229){e.preventDefault();form.requestSubmit()}});form.addEventListener('submit',e=>{e.preventDefault();const text=input.value;if(!text.trim()||busy||customerThinking)return;captureChatState();chatScroll.forceBottom=chatScroll.nearBottom;typing='';if(mode!=='COACH'){pendingAdvisorText=text;customerThinking=true}render();action('send',{text,expected_turn:model.session.next_turn,assist_used:guideInserted});guideInserted=false})}
  }
  function download(){const html=`<!doctype html><html lang="ko"><meta charset="utf-8"><title>화랑 상담 훈련 복기</title><style>body{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#183750;line-height:1.7}.rubric-row,.review-row{padding:15px 0;border-bottom:1px solid #d6e0e9}blockquote{background:#f5f8fc;padding:12px}</style><h1>화랑 상담 시뮬레이터 · 훈련 복기</h1><p>${esc(model.session.title)} / ${esc(model.session.mode)} / ${esc(model.session.session_length)}</p>${rubricRows()}<h2>대화 복기</h2>${reviewRows()}</html>`;const u=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'})),a=document.createElement('a');a.href=u;a.download='화랑_상담복기_'+model.session.scenario_id+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&missionModalOpen){missionModalOpen=false;render()}});
  if(embedded){window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='streamlit:render')return;parentOrigin=e.origin;receive(e.data.args?.model)});post('streamlit:componentReady',{apiVersion:1});frameHeight()}else{if(!token){root.innerHTML='<div class="loading">화랑 ACADEMY 연결을 확인해 주세요.</div>';return}action('bootstrap')}
  new ResizeObserver(()=>frameHeight()).observe(root);
})();
