'use strict';
(() => {
  const root=document.getElementById('app'), status=document.getElementById('connection-status');
  const params=new URLSearchParams(location.search), frag=new URLSearchParams(location.hash.slice(1));
  const embedded=window.parent!==window;
  let model=null,busy=false,lastEvent=null,timeoutId=null,parentOrigin=null;
  let mode=params.get('mode')||'GUIDE',selected=params.get('scenario')||'C07-S01',sessionLength=params.get('length')||'STANDARD';
  let mapGroup='ALL',reportTab='summary',typing='',customerThinking=false,pendingAdvisorText='',guideInserted=false;
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
  function frameHeight(){if(embedded)post('streamlit:setFrameHeight',{height:Math.ceil(Math.max(document.body.scrollHeight,920))})}
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
      model=next;clearTimeout(timeoutId);busy=false;customerThinking=false;pendingAdvisorText='';status.textContent='';
      if(model.phase==='session'||model.phase==='result'){mode=model.session.mode;selected=model.session.scenario_id;sessionLength=model.session.session_length;rememberProfile(model.session)}
      else{mode=model.mode||mode;selected=model.selection||selected;sessionLength=model.session_length||sessionLength}
      if(!model.error&&['send','commit','start','retry','retry_new','retry_harder','setup'].includes(lastEvent?.kind))typing='';
      render();
    };
    if(producing){customerThinking=true;status.textContent='';render();setTimeout(apply,next.session?.reply_delay_ms||900)}else apply();
  }
  function header(){return `<header class="topbar"><div class="brand-wrap">${brand()}<div class="tagline">Learn Today, Grow Together<small>배움을 넘어, 더 나은 내일의 전문가로</small></div></div><span class="right-label">교육 · 실습 · 성장</span></header>`}
  function home(){
    const all=model.scenarios,first=all.find(x=>x.id==='C07-S01')||all[0];
    return `${header()}<div class="academy-layout"><nav class="academy-nav" aria-label="아카데미 메뉴">${button('⌂ <span>홈</span>','home','nav-item current')}${button('◈ <span>PRACTICE LAB</span>','scroll-cases','nav-item')}${button('▤ <span>전체 상담 지도</span>','scroll-map','nav-item')}<button class="nav-item" disabled>온보딩 <small>자료 준비</small></button><button class="nav-item" disabled>교육 과정 <small>자료 준비</small></button><div class="nav-foot">Planned &amp; Built by<br>박병선 팀장<br><br>대화 엔진 V3 스트레스 검증 시험판</div></nav><main class="academy-main"><div class="intro-row"><h3>오늘의 한 번이, 내일의 실력이 됩니다.</h3><p>학습을 실제 상담으로 연결합니다.</p></div><div class="hero-grid"><section class="hero learning-hero"><span class="eyebrow">HWARANG ACADEMY</span><h1>오늘도,<br>더 나은 내일의<br>전문가를 만듭니다.</h1><p>정답 문장을 외우는 대신 고객의 맥락을 읽고 상담을 이어갑니다.</p><a class="action" href="${esc(simulatorUrl(first.id))}" target="_blank" rel="noopener noreferrer">가이드 훈련 시작하기 ↗</a></section><section class="hero lab-hero"><div class="intro-row"><span class="eyebrow">PRACTICE LAB</span>${badge('AI 확장 예정','dark')}</div><h2>실전이 실력을 만듭니다.</h2><p>고객 성향·상황·이벤트가 달라지는 반복 훈련.<br>GUIDE부터 ASSESSMENT까지 단계적으로 도전하세요.</p><div class="hero-stats"><span>◎ 가상 고객</span><span>▧ 4가지 훈련 모드</span><span>↻ 반복 변형</span></div><a class="action light" href="${esc(simulatorUrl())}" target="_blank" rel="noopener noreferrer">상담 시뮬레이터 시작하기 ↗</a></section></div><div class="section-head" id="cases-anchor"><h2>지금 시작하는 상담 훈련</h2>${badge('대표 6개 실행 시험')}</div><div class="cases">${all.map(s=>`<article class="case-card"><div class="eyebrow">${esc(s.id)} · ${esc(s.label)}</div><h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><a class="action secondary" href="${esc(simulatorUrl(s.id))}" target="_blank" rel="noopener noreferrer">훈련 열기 ↗</a></article>`).join('')}</div><section class="map-panel" id="map-anchor"><div class="intro-row"><h2>전체 상담 유형 지도</h2>${badge('97개 유형 · 194개 제작 슬롯')}</div><p class="muted">전체 지도는 유지하고, 현재는 대표 6개에서 대화 엔진 V3를 먼저 검증합니다.</p><div class="map-filters">${button('전체','filter-map','chip '+(mapGroup==='ALL'?'active':''),'data-id="ALL"')}${model.categories.map(c=>button(esc(c.name),'filter-map','chip '+(mapGroup===c.id?'active':''),`data-id="${esc(c.id)}"`)).join('')}</div><div class="map-list">${model.catalog.filter(x=>mapGroup==='ALL'||x.category===mapGroup).map(x=>`<div class="map-row"><span><small>${esc(x.id)}</small> ${esc(x.name)}</span>${x.ready_scenario?`<a class="badge" href="${esc(simulatorUrl(x.ready_scenario))}" target="_blank" rel="noopener noreferrer">시험 가능 ↗</a>`:'<small>대사 준비</small>'}</div>`).join('')}</div></section></main></div>`;
  }
  function simHeader(){return `<div class="sim-top">${brand('ACADEMY / PRACTICE LAB')}<span class="tagline">연습이, 실력을 만듭니다.</span>${badge('AI 확장 예정','dark')}</div>`}
  function selectedScenario(){return model.scenarios.find(s=>s.id===selected)||model.scenarios[0]}
  function setup(){
    const sc=selectedScenario(),obj=sc.objectives[mode],points=mode==='GUIDE'?sc.guide_points:[];
    return `<main class="sim-wrap">${simHeader()}<section class="glass setup"><div class="setup-lead"><div><span class="eyebrow">COUNSELING SIMULATOR · V3</span><h1>상담 시뮬레이터</h1><p>이번 상담의 목적을 확인한 뒤 실제 상담하듯 자유롭게 입력하세요.</p></div>${badge('규칙 기반 · 맥락형 대화','dark')}</div><div class="step-label"><span>01</span>훈련 방식을 선택하세요</div><div class="modes">${model.modes.map((m,i)=>`<button type="button" class="mode-card ${mode===m.id?'selected':''}" data-action="mode" data-id="${esc(m.id)}"><span class="mode-check">${mode===m.id?'✓ 선택됨':'0'+(i+1)}</span><strong>${esc(m.id)}</strong><b>${esc(m.name)}</b><p>${esc(m.purpose)}</p></button>`).join('')}</div><div class="step-label"><span>02</span>훈련 길이를 선택하세요</div><div class="lengths">${model.lengths.map(l=>`<button type="button" class="length-card ${sessionLength===l.id?'selected':''}" data-action="length" data-id="${l.id}"><strong>${esc(l.name)}</strong><span>${esc(l.minutes)}</span><p>${esc(l.description)}</p></button>`).join('')}</div><div class="step-label"><span>03</span>오늘의 상담 상황을 선택하세요 ${button('🎲 다른 과제','random','action ghost small')}</div><div class="scene-choices">${model.scenarios.map(s=>`<button class="scene-choice ${s.id===selected?'selected':''}" data-action="scene" data-id="${esc(s.id)}"><strong>${esc(s.name)}</strong><small>${esc(s.id)} · ${esc(s.label)}</small></button>`).join('')}</div><section class="mission-preview"><div class="eyebrow">MISSION · 이번 상담의 최종 목적</div><h2>${esc(sc.name)}</h2><p>${esc(obj)}</p>${points.length?`<div class="guide-points">${points.map(x=>`<span>✓ ${esc(x)}</span>`).join('')}</div>`:''}<small>${mode==='ASSESSMENT'?'평가 모드에서는 세부 정답 경로를 공개하지 않습니다.':'목표는 알려주되 숨은 고객 정보와 실제 대화 경로는 공개하지 않습니다.'}</small></section><div class="setup-footer"><p>같은 과제를 다시 선택해도 고객 프로필·표현·허용된 이벤트가 달라질 수 있습니다.<br>GUIDE·COACH에서도 낮은 강도의 상황 변화가 발생합니다.</p>${button('상담 시작하기 →','start','action light')}</div></section></main>`;
  }
  function customerPanel(s){
    let meters='';if(s.states)meters=`<div class="states"><strong>고객 상태 · 연출용</strong>${[['trust','신뢰'],['resistance','경계'],['patience','인내']].map(([k,v])=>`<div class="meter-line"><span>${v}</span><div class="meter"><i style="width:${s.states[k]}%"></i></div><b>${s.states[k]}</b></div>`).join('')}<p>실제 심리 측정값이나 학습 점수가 아닙니다.</p></div>`;
    const hasProgress=Number.isFinite(s.completion?.done)&&Number.isFinite(s.completion?.total);
    const progress=hasProgress?Math.round((s.completion.done/Math.max(1,s.completion.total))*100):null;
    return `<aside class="glass customer-panel"><div class="customer-title"><span class="avatar">◎</span><div><strong>오늘의 가상 고객</strong><small>${esc(s.scenario_id)} · 공개된 정보</small></div></div><div class="mission-mini"><small>MISSION · ${esc(s.stage)}</small><p>${esc(s.mission)}</p>${progress===null?'':`<div class="mini-progress"><div class="meter"><i style="width:${progress}%"></i></div><span>${progress}%</span></div>`}</div><div class="public-heading">대화에서 확인한 내용</div><div class="public-record">${s.public_facts.map(f=>`<div class="fact"><small>${esc(f.label)}${f.turn?' · '+f.turn+'번째 응답':''}</small><div>${esc(f.value)}</div></div>`).join('')}</div>${meters}</aside>`;
  }
  function guidePanel(){
    const g=model.guide_panel;if(!g)return '';
    return `<aside class="guide-panel glass"><div class="guide-head"><div><span class="eyebrow">GUIDE ASSIST</span><strong>실시간 코칭</strong></div>${badge('항상 표시','dark')}</div><div class="guide-core"><span class="eyebrow">지금의 핵심</span><p>${esc(g.hint)}</p></div><div class="guide-card good"><strong>✓ 권장 답변</strong><p>${esc(g.recommended)}</p><button type="button" class="action light small" data-action="insert-guide" data-text="${esc(g.recommended)}">답변에 넣기</button></div><div class="guide-card okay"><strong>△ 무난한 답변</strong><p>${esc(g.adequate)}</p><button type="button" class="action secondary small" data-action="insert-guide" data-text="${esc(g.adequate)}">답변에 넣기</button></div><div class="guide-card caution"><strong>! 주의할 답변</strong><p>${esc(g.avoid)}</p><details><summary>왜 주의해야 하나?</summary><p>${esc(g.reason||'고객 상황을 충분히 확인하기 전에 결론·권고를 앞서 내리거나 선택권을 좁힐 수 있습니다.')}</p></details></div><p class="guide-foot">예시는 정답 문장 암기용이 아닙니다. 가져온 뒤 자신의 말투로 바꿔도 됩니다.</p></aside>`;
  }
  function chat(s){
    const c=model.coaching,g=model.examples;let msgs=[...s.messages];
    if(customerThinking&&pendingAdvisorText)msgs.push({role:'advisor',text:pendingAdvisorText,turn:s.next_turn});
    return `<section class="conversation" aria-label="밝은 상담 채팅창"><div class="chat-title"><h3>상담 대화</h3><small>${esc(s.session_length)} · 상담사 답변 ${s.next_turn-1}개</small></div>${s.dialogue_notice?`<div class="dialogue-notice" role="status">${esc(s.dialogue_notice)}</div>`:''}<div class="messages" id="messages" role="log" aria-live="polite">${msgs.map(m=>`<div class="msg ${m.role}">${m.role==='customer'?'<span class="msg-avatar">◎</span>':''}<div class="msg-body"><div class="meta">${m.role==='customer'?'고객':'나 · 상담사'} ${m.turn?'· '+m.turn:''}</div><div class="bubble">${esc(m.text)}</div></div></div>`).join('')}${customerThinking?`<div class="msg customer thinking"><span class="msg-avatar">◎</span><div class="msg-body"><div class="meta">고객</div><div class="bubble typing-bubble"><i></i><i></i><i></i><span>답변을 생각하고 있습니다</span></div></div></div>`:''}</div><div class="composer"><form id="compose"><div class="compose-box"><textarea id="message-input" placeholder="고객에게 할 말을 입력하세요." maxlength="1200" rows="2" ${customerThinking?'disabled':''}>${esc(typing)}</textarea><button type="submit" class="send" ${busy||customerThinking?'disabled':''}>${s.mode==='COACH'?'코칭 확인':'전송'} ↑</button></div><div class="compose-foot"><span>Enter 전송 · Shift + Enter 줄바꿈</span><span id="char-count">${typing.length} / 1200</span></div></form></div>${c?`<div class="coaching"><div class="eyebrow">COACH REVIEW · ${c.revision}번째 작성</div><h3>${esc(c.title)}</h3><p>${esc(c.note)}</p><div class="draft">${esc(c.text)}</div><div class="intent-pills">${c.observed.map(x=>`<span>${esc(x)}</span>`).join('')}</div><div class="action-row">${button('이 답변으로 진행 →','commit','action small')}${button('다시 답해보기','edit','action secondary small')}${button(g?'예시 접기':'예시 보기','examples','action ghost small')}</div>${g?`<div class="examples"><div class="example"><strong>권장 방향</strong>${esc(g.recommended)}</div><div class="example average"><strong>보완 가능한 답변</strong>${esc(g.adequate)}</div></div>`:''}</div>`:''}</section>`;
  }
  function sessionView(){const s=model.session;return `<main class="sim-wrap">${simHeader()}<section class="glass stagebar"><div class="stage-copy"><div class="stage-code">${esc(s.scenario_id.split('-')[0])}</div><div><span class="eyebrow">${esc(s.stage)} · ${esc(s.session_length)}</span><h2>${esc(s.title)}</h2><p>${esc(s.mission)}</p></div></div><div class="stage-actions">${badge(s.mode+' · '+model.modes.find(x=>x.id===s.mode).name,'dark')}${button('상담 종료','finish','action light small')}</div></section><div class="session-layout ${s.mode==='GUIDE'?'with-guide':''}">${customerPanel(s)}${chat(s)}${s.mode==='GUIDE'?guidePanel():''}</div><p class="session-note">대화가 자연스럽게 빨리 끝날 수 있지만, 턴 수를 채우기 위해 억지로 늘리지는 않습니다. 미해석은 자동 오답 처리하지 않습니다.</p></main>`}
  const states={full:'충분한 증거',partial:'부분 증거',not_observed:'미수행',unresolved:'판정 유보',not_applicable:'해당 없음'};
  function rubricRows(){return model.report.rows.map(r=>`<div class="rubric-row"><div class="rubric-head"><h3>${esc(r.name)}</h3>${badge(states[r.state],r.state==='unresolved'?'warm':'')}</div><p>${esc(r.gate)}</p><p>${esc(r.reason)}</p>${r.evidence.slice(-2).map(e=>`<blockquote>${e.turn}번째 상담사 답변<br>${esc(e.text)}</blockquote>`).join('')}</div>`).join('')}
  function reviewRows(){return model.review.map(r=>`<div class="review-row"><h3>${r.turn}번째 대화 ${r.risks.length?badge('위험 후보 · 검수 필요','warm'):''}</h3><p>${esc(r.text)}</p><p class="customer-reply">고객 · ${esc(r.customer)}</p><div class="intent-pills">${r.intents.map(x=>`<span>${esc(x)}</span>`).join('')}</div></div>`).join('')||'<p>아직 제출한 대화가 없습니다.</p>'}
  function resultView(){const r=model.report,s=model.session,value=r.lower===null?'—':r.lower===r.upper?String(r.lower):`${r.lower}–${r.upper}`;return `<main class="sim-wrap">${simHeader()}<section class="glass result"><div class="result-top"><span class="eyebrow">SESSION COMPLETE</span><h1>${s.end_reason==='customer_exit'?'고객이 상담을 종료했습니다.':'오늘의 연습을, 다음 상담의 자신감으로.'}</h1><p>${esc(s.title)} · ${esc(s.mode)} · ${esc(s.session_length)}</p></div><div class="result-overview"><div class="score-ring"><strong>${esc(value)}</strong><span>규칙 기반 잠정 평가</span></div><div>${r.axes.map(a=>`<div class="axis"><span>${esc(a.name)}</span><div class="meter"><i style="width:${a.lower}%"></i></div><b>${a.lower===a.upper?a.lower:a.lower+'–'+a.upper}</b></div>`).join('')}</div></div><div class="report-note">${esc(r.notice)}</div><div class="report-tabs">${button('평가 근거','report-summary','action ghost '+(reportTab==='summary'?'active':''))}${button('대화 복기','report-review','action ghost '+(reportTab==='review'?'active':''))}${button('복기 저장','download','action ghost')}</div><div class="report-content">${reportTab==='summary'?rubricRows():reviewRows()}</div><div class="report-actions">${button('같은 고객 다시 도전','retry','action light')}${button('같은 과제 · 새로운 고객','retry-new','action secondary')}${button('더 어려운 상황','retry-harder','action secondary')}${button('다른 훈련 선택','setup','action ghost')}</div></section></main>`}
  function render(){
    if(!model)return;document.body.classList.toggle('simulator',model.independent||['session','result','setup'].includes(model.phase));
    root.innerHTML=(model.error?`<div class="error" role="alert">${esc(model.error)}</div>`:'')+(model.phase==='home'?home():model.phase==='setup'?setup():model.phase==='session'?sessionView():resultView());bind();frameHeight();
    const messages=document.getElementById('messages');if(messages)requestAnimationFrame(()=>messages.scrollTop=messages.scrollHeight);
    const input=document.getElementById('message-input');if(input&&!customerThinking&&model.phase==='session'&&!model.coaching)requestAnimationFrame(()=>{input.focus();input.setSelectionRange(input.value.length,input.value.length)});
  }
  function bind(){
    root.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{
      const k=b.dataset.action;
      if(k==='mode'){mode=b.dataset.id;render()} else if(k==='length'){sessionLength=b.dataset.id;render()} else if(k==='scene'){selected=b.dataset.id;render()}
      else if(k==='random'){const pool=model.scenarios.filter(s=>s.id!==selected);const a=new Uint32Array(1);crypto.getRandomValues(a);selected=pool[a[0]%pool.length].id;render()}
      else if(k==='start')action('start',{scenario_id:selected,mode,session_length:sessionLength,avoid_profiles:recentProfiles(selected)})
      else if(k==='insert-guide'){typing=b.dataset.text||'';guideInserted=true;render()}
      else if(k==='commit'){pendingAdvisorText=model.coaching?.text||'';customerThinking=true;render();action('commit',{expected_turn:model.session.next_turn,draft_revision:model.coaching.revision})}
      else if(k==='edit'){typing=model.coaching.text;render()}
      else if(k==='examples')action('examples')
      else if(k==='finish'){if(confirm('이 상담을 종료하고 복기할까요?'))action('finish')}
      else if(k==='retry')action('retry')
      else if(k==='retry-new')action('retry_new',{avoid_profiles:recentProfiles(model.session.scenario_id)})
      else if(k==='retry-harder')action('retry_harder',{avoid_profiles:recentProfiles(model.session.scenario_id)})
      else if(k==='setup')action('setup')
      else if(k==='filter-map'){mapGroup=b.dataset.id;render();document.getElementById('map-anchor')?.scrollIntoView({block:'start'})}
      else if(k==='scroll-cases')document.getElementById('cases-anchor')?.scrollIntoView({behavior:'smooth'})
      else if(k==='scroll-map')document.getElementById('map-anchor')?.scrollIntoView({behavior:'smooth'})
      else if(k==='report-summary'){reportTab='summary';render()}
      else if(k==='report-review'){reportTab='review';render()}
      else if(k==='download'){download()}
      else if(k==='home'){window.scrollTo({top:0,behavior:'smooth'})}
    }));
    const input=document.getElementById('message-input'),form=document.getElementById('compose');if(input&&form){let composing=false;input.addEventListener('compositionstart',()=>composing=true);input.addEventListener('compositionend',()=>composing=false);input.addEventListener('input',()=>{typing=input.value;const c=document.getElementById('char-count');if(c)c.textContent=typing.length+' / 1200'});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&!composing&&e.keyCode!==229){e.preventDefault();form.requestSubmit()}});form.addEventListener('submit',e=>{e.preventDefault();const text=input.value;if(!text.trim()||busy||customerThinking)return;typing='';if(mode!=='COACH'){pendingAdvisorText=text;customerThinking=true}render();action('send',{text,expected_turn:model.session.next_turn,assist_used:guideInserted});guideInserted=false})}
  }
  function download(){const html=`<!doctype html><html lang="ko"><meta charset="utf-8"><title>화랑 상담 훈련 복기</title><style>body{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#183750;line-height:1.7}.rubric-row,.review-row{padding:15px 0;border-bottom:1px solid #d6e0e9}blockquote{background:#f5f8fc;padding:12px}</style><h1>화랑 상담 시뮬레이터 · 훈련 복기</h1><p>${esc(model.session.title)} / ${esc(model.session.mode)} / ${esc(model.session.session_length)}</p>${rubricRows()}<h2>대화 복기</h2>${reviewRows()}</html>`;const u=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'})),a=document.createElement('a');a.href=u;a.download='화랑_상담복기_'+model.session.scenario_id+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
  if(embedded){window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='streamlit:render')return;parentOrigin=e.origin;receive(e.data.args?.model)});post('streamlit:componentReady',{apiVersion:1});frameHeight()}else{if(!token){root.innerHTML='<div class="loading">run_academy_local.py를 실행하면 브라우저가 자동으로 열립니다.</div>';return}action('bootstrap')}
  new ResizeObserver(()=>frameHeight()).observe(root);
})();
