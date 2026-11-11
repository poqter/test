// Explicit entrance: run after the synchronous form build, without delaying focus.
function showCalendarDialog(panel){
 panel.showModal();
 queueMicrotask(()=>{
  if(!panel.isConnected||!panel.open||matchMedia('(prefers-reduced-motion: reduce)').matches||typeof panel.animate!=='function')return;
  const style=getComputedStyle(panel),duration=parseFloat(style.getPropertyValue('--calendar-enter'))||180;
  const shift=style.getPropertyValue('--calendar-shift').trim()||'0px';
  const animation=panel.animate([{opacity:0,transform:`translateY(${shift})`},{opacity:1,transform:'translateY(0)'}],{duration,easing:style.getPropertyValue('--calendar-ease').trim()||'ease'});
  panel.addEventListener('close',()=>animation.cancel(),{once:true});
 });
}
// Let native dialog close release focus immediately while its exit transition finishes.
function retireDialog(node){
 node.inert=true;node.setAttribute('aria-hidden','true');node.style.pointerEvents='none';
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){node.remove();return}
 const exitMs=parseFloat(getComputedStyle(node).getPropertyValue('--calendar-exit'))||0;
 setTimeout(()=>{if(!node.open)node.remove()},exitMs+40);
}
/* One mounted calendar. Navigation and form lifetime belong to the browser.
 * Commands are serialized; only server-acknowledged saves are shown as saved.
 * Data never enters localStorage; existing preference keys remain unchanged.
 */
let calendarLayoutReady=false,calendarBoot=null,calendarLoading=false,calendarLoadError=false,calendarQueue=[],calendarFlight=null,calendarSeq=0,calendarVisible=true,calendarPanel=null,calendarDraft=null,calendarDrafts=new Map(),calendarChange=null,calendarEpoch=0,calendarMemory=null;
const calendarCache=new Map();
function rpc(op,args={}){return new Promise((resolve,reject)=>{if(op==='load'){const obsolete=calendarQueue.filter(q=>q.op==='load');calendarQueue=calendarQueue.filter(q=>q.op!=='load');obsolete.forEach(q=>q.reject(Error('조회 기간이 변경됐습니다.')))}calendarQueue.push({nonce:crypto.randomUUID(),op,args,resolve,reject});sendNext()})}
function sendNext(){
 if(calendarFlight||!calendarQueue.length)return;
 const q=calendarFlight=calendarQueue.shift();
 post('streamlit:setComponentValue',{value:{action:'rpc',value:{op:q.op,args:q.args},nonce:q.nonce},dataType:'json'});
 q.timer=setTimeout(()=>{
  calendarStatus('응답을 기다리는 중입니다. 현재 화면과 입력은 유지됩니다.');
  const notice=el('div','','draft-notice');notice.dataset.request=q.nonce;notice.append(el('p','연결이 지연되고 있습니다. 입력은 유지됩니다.'),button('연결 다시 확인',()=>{q.attempt=(q.attempt||0)+1;post('streamlit:setComponentValue',{value:{action:'rpc',value:{op:q.op,args:q.args},nonce:q.nonce,attempt:q.attempt},dataType:'json'})}));
  (calendarPanel?.querySelector('.panel-content')||document.getElementById('agenda')).prepend(notice);
 },15000);
}
function calendarStatus(text){document.getElementById('refreshing').textContent=text||''}
function receiveCalendar(a){
 document.body.dataset.shellFirst=a.shellFirst?"true":"false";
 const hostEntering=typeof receiveHost==='function'?receiveHost(a):false;
 if(a.hosted&&!a.hostActive)return;
 if(!a.boot)return;
 fitCalendar();
 if(calendarBoot&&(calendarBoot.uid!==a.boot.uid||calendarBoot.access!==a.boot.access)){calendarEpoch++;calendarSeq++;stopRealtime();calendarCache.clear();calendarDrafts.clear();if(calendarPanel)calendarPanel.close();calendarBoot=null;context=null;lastRender=null;}
 if(!calendarBoot){
  calendarBoot=a.boot;
  try{parent.__hwarangCalendarMemory??={};calendarMemory=parent.__hwarangCalendarMemory[calendarBoot.uid]??={drafts:new Map()};calendarDrafts=calendarMemory.drafts; if(calendarMemory.access!==a.boot.access){calendarMemory.cache=new Map();calendarMemory.view=null;calendarMemory.access=a.boot.access;}for(const [k,v] of calendarMemory.cache||[])calendarCache.set(k,v);}catch{}
  const shellView=a.hosted&&latest?{day:latest.day,mode:latest.mode}:{};
  latest={...a.boot,...shellView,hideMobileApp:a.hideMobileApp,mobileSession:a.mobileSession};
  const remembered=calendarMemory?.view;if(remembered){calendarBoot.team=remembered.team;calendarBoot.member=calendarBoot.members[remembered.member]?remembered.member:null;latest={...latest,day:remembered.day,mode:remembered.mode};selected=remembered.selected;context=latest.mode+latest.day}
  const [first,last]=desiredRange();
  const fresh=a.boot.ready!==false&&a.bootFresh&&!remembered&&first===a.boot.rangeStart&&last===a.boot.rangeEnd;
  calendarLoading=!fresh;
  if(fresh)calendarCache.set(rangeKey(first,last),a.boot);
  render(latest);if(!fresh)reloadCalendar();setTimeout(()=>{frameViewport='';fitCalendar();calendarLayoutReady=true},150);
 }else{latest.mobileSession=a.mobileSession;latest.hideMobileApp=a.hideMobileApp;syncConfig=latest;configureRealtime(latest);if(hostEntering){calendarLoading=true;reloadCalendar();}}
 const r=a.reply,q=calendarFlight;
 if(r&&q&&r.nonce===q.nonce){clearTimeout(q.timer);document.querySelectorAll('[data-request]').forEach(n=>{if(n.dataset.request===q.nonce)n.remove()});calendarFlight=null;r.ok?q.resolve(r.result):q.reject(Error(r.error||'요청을 완료하지 못했습니다.'));sendNext()}
 if(a.changeNonce&&calendarChange!==a.changeNonce){calendarChange=a.changeNonce;reloadCalendar(true)}
}
function rangeKey(first,last){return [first,last,calendarBoot.team,calendarBoot.member||''].join('|')}
function desiredRange(){const d=date(latest.day);let first;
 if(latest.mode==='월간'){first=date(latest.day.slice(0,7)+'-01');first=add(first,-((first.getUTCDay()+6)%7));return [iso(first),iso(add(first,41))]}
 first=add(d,-((d.getUTCDay()+6)%7));return [iso(add(first,-7)),iso(add(first,13))];}
async function reloadCalendar(force=false){
 const seq=++calendarSeq,[first,last]=desiredRange(),key=rangeKey(first,last),epoch=calendarEpoch;
 if(force){calendarCache.clear();if(calendarMemory)calendarMemory.cache=new Map();}
 const cached=calendarCache.get(key);
 if(cached&&!force){calendarLoading=false;render({...latest,...cached,day:latest.day,mode:latest.mode});calendarStatus('최신 일정 확인 중…');}
 calendarLoading=!cached;calendarLoadError=false;if(!cached)calendarStatus('일정을 불러오는 중…');render(latest);
 try{
  if(cached&&!force&&calendarBoot.fast){
   const session=latest.mobileSession,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
   try{
    const response=await fetch(session.url+'/rest/v1/rpc/sales_calendar_stamp',{method:'POST',headers:{apikey:session.key,Authorization:'Bearer '+session.token,'Content-Type':'application/json','X-Hwarang-View-Scope':session.viewScope||'daily'},body:JSON.stringify({first_day:first,last_day:last,p_unit:cached.syncUnit}),signal:controller.signal});
    if(response.ok&&await response.json()===cached.syncStamp){if(seq===calendarSeq&&epoch===calendarEpoch){calendarLoading=false;calendarStatus('');configureSync(latest)}return;}
   }finally{clearTimeout(timer)}
  }
  const data=calendarBoot.fast?await loadPayload(first,last,calendarBoot.team,calendarBoot.member):await rpc('load',{first,last,team:calendarBoot.team,member:calendarBoot.member});
  if(epoch!==calendarEpoch)return;
  calendarCache.set(key,data);while(calendarCache.size>8)calendarCache.delete(calendarCache.keys().next().value);
  if(calendarMemory)calendarMemory.cache=new Map(calendarCache);
  if(seq!==calendarSeq)return;
  calendarLoading=false;calendarLoadError=false;render({...latest,...data});calendarStatus('');if(signalPending)checkSync();
 }catch(e){if(seq===calendarSeq){calendarLoading=false;calendarLoadError=true;calendarStatus(e.message);render(latest)}}
}
async function loadPayload(first,last,team,member){
 const session=latest.mobileSession,controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
 try{
  const response=await fetch(session.url+'/rest/v1/rpc/sales_calendar_payload',{method:'POST',headers:{apikey:session.key,Authorization:'Bearer '+session.token,'Content-Type':'application/json','X-Hwarang-View-Scope':session.viewScope||'daily'},body:JSON.stringify({first_day:first,last_day:last,p_member:member||null,p_team:!!team}),signal:controller.signal});
  if(!response.ok){if(response.status===401)calendarAction('reauth');if(response.status===403){calendarCache.clear();if(calendarMemory)calendarMemory.cache=new Map();latest={...latest,events:[],roster:{}};}throw Error('일정을 불러오지 못했습니다. 다시 확인해 주세요.');}
  const data=await response.json(),details=new Map(data.rows.map(r=>[r.id,r])),branch=Object.fromEntries(data.branch.map(r=>[r.member,r.label]));
  const rows=member?data.rows:data.summary.map(r=>details.get(r.id)||r);
  const now=new Date(),kst=new Date(now.getTime()+9*3600000).toISOString(),today=kst.slice(0,10),clock=kst.slice(11,19);
  const events=rows.sort((a,b)=>(a.day+(a.start_time||'')+a.id).localeCompare(b.day+(b.start_time||'')+b.id)).map(r=>{
   const owner=branch[r.owner]||calendarBoot.members[r.owner]||'지점 공통',stamp=(r.start_time||(r.time_pending?'시간 미정':'종일')).slice(0,5);
   const overdue=r.status==='예정'&&(r.day<today||r.day===today&&r.start_time&&r.start_time<clock);
   let label=r.kind==='휴무'?owner+' · 휴무':stamp+' · '+r.kind+' · '+owner+' · '+(overdue?'결과 미입력':r.status);
   if(r.companion)label+=' · 동행 '+(branch[r.companion]||'');if(r.help)label+=' · 지원 요청';
   const seconds=r.start_time?(new Date(r.day+'T'+r.start_time+'+09:00')-now)/1000:-1;
   return {start:r.start_time,timePending:!!r.time_pending,place:r.place||'',status:r.status,revision:r.revision,id:r.id,day:r.day,kind:r.kind,member:r.owner,allDay:!r.start_time,short:r.kind==='휴무'?(team?owner+' · 휴무':'휴무'):(r.title||r.kind)+(team?' · '+owner:''),label,done:r.kind!=='휴무'&&r.status==='완료',soon:r.day===today&&r.status==='예정'&&seconds>=0&&seconds<=1800,readable:details.has(r.id)};
  });
  return {events,rangeStart:first,rangeEnd:last,syncUnit:data.unit,syncStamp:data.stamp,scopeLabel:member?calendarBoot.members[member]:team?(calendarBoot.viewLabel||'지점 일정'):'내 일정',roster:team||member?Object.fromEntries(Object.entries(branch).filter(([u])=>!member||u===member)):{}};
 }finally{clearTimeout(timeout)}
}
function calendarAction(action,value){
 if(!calendarBoot){
  if(latest&&(action==='mode'||action==='date')){latest={...latest,[action==='mode'?'mode':'day']:value};context=null;render(latest);}
  return;
 }
 if(typeof workspaceHost!=='undefined'&&workspaceHost&&(workspaceHost.pending()||!parentVisible)&&action!=='reauth')return;
 if(action==='mode'||action==='date'){
  selectedByUser=null;
  if(action==='mode'){latest={...latest,mode:value,day:selected||latest.day};}
  else latest={...latest,day:value};
  selected=latest.day;context=null;calendarLoading=true;render(latest);reloadCalendar();return;
 }
 if(action==='weekends'){render(latest);return}
 if(action==='new'){openEditor(null,'new',value||selected);return}
 if(action==='event'){dayListReturn=null;openDetail(value);return}
 if(action==='scope'){document.querySelector('.member-search input')?.focus();return}
 if(action==='refresh'){reloadCalendar(true);return}
 if(action==='reauth'){if(calendarFlight){setTimeout(()=>calendarAction('reauth'),1000);return}post('streamlit:setComponentValue',{value:{action:'reauth',nonce:crypto.randomUUID()},dataType:'json'});return}
}
function createPanel(title, spacious=false){
 dismissCloseConfirm();
 document.querySelectorAll('dialog.calendar-panel:not([open]),dialog.calendar-close-confirm:not([open])').forEach(node=>node.remove());
 if(calendarPanel){calendarPanel.remove();calendarPanel=null;}
 const returnFocus=document.activeElement;
 try{const fab=parent.document.querySelector('.mobile-new-event');if(fab)fab.style.visibility='hidden'}catch{}
 const panel=calendarPanel=el('dialog','','calendar-panel');panel.setAttribute('aria-label',title);
 if(spacious&&document.body.dataset.shellFirst==='true')panel.classList.add('calendar-spacious');
 const head=el('div','','panel-head'),body=el('div','','panel-content');head.append(el('h3',title),button('×',()=>closePanel(),'','팝업 닫기'));panel.append(head,body);document.body.append(panel);
 let backdropDown=false;
 const outside=e=>{const b=panel.getBoundingClientRect();return e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom};
 panel.addEventListener('pointerdown',e=>{backdropDown=e.target===panel&&outside(e)});
 panel.addEventListener('click',e=>{if(backdropDown&&e.target===panel&&outside(e))closePanel();backdropDown=false});
 panel.addEventListener('cancel',e=>{e.preventDefault();closePanel()});panel.addEventListener('close',()=>{retireDialog(panel);if(calendarPanel===panel)calendarPanel=null;try{const fab=parent.document.querySelector('.mobile-new-event');if(fab)fab.style.visibility=''}catch{}returnFocus?.focus({preventScroll:true})});showCalendarDialog(panel);calendarDraft=null;
 return body;
}
let calendarCloseConfirm=null;
function dismissCloseConfirm(){
 const box=calendarCloseConfirm;if(!box)return;
 calendarCloseConfirm=null;box.close();retireDialog(box);
}
function closePanel(){
 if(calendarPanel?.dataset.busy)return;
 if(calendarCloseConfirm)return;
 if(calendarDraft&&calendarDraft.dirty){
  const panel=calendarPanel,draft=calendarDraft,focus=document.activeElement;
  const box=calendarCloseConfirm=el('dialog','','calendar-close-confirm');
  box.setAttribute('aria-labelledby','calendar-close-title');
  box.setAttribute('aria-describedby','calendar-close-description');
  const title=el('h3','저장하지 않은 변경이 있습니다.');title.id='calendar-close-title';
  const description=el('p','작성 중인 내용을 어떻게 할까요?');description.id='calendar-close-description';
  const resume=()=>{dismissCloseConfirm();if(focus?.isConnected)focus.focus({preventScroll:true})};
  const actions=el('div','','confirm-actions');
  const keepWriting=button('계속 작성',resume,'primary');keepWriting.autofocus=true;
  actions.append(keepWriting,button('내용 유지하고 닫기',()=>{
   calendarDrafts.set(draft.key,draft);calendarDraft=null;dismissCloseConfirm();panel.close();
  }),button('저장하지 않고 닫기',()=>{
   calendarDrafts.delete(draft.key);calendarDraft=null;dismissCloseConfirm();panel.close();
  },'danger'));
  box.append(title,description,actions);document.body.append(box);
  let backdropDown=false;
  const outside=e=>{const b=box.getBoundingClientRect();return e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom};
  box.addEventListener('pointerdown',e=>{backdropDown=e.target===box&&outside(e)});
  box.addEventListener('click',e=>{if(backdropDown&&e.target===box&&outside(e))resume();backdropDown=false});
  box.addEventListener('cancel',e=>{e.preventDefault();e.stopPropagation();resume()});
  panel.addEventListener('close',dismissCloseConfirm,{once:true});
  showCalendarDialog(box);keepWriting.focus({preventScroll:true});return;
 }
 calendarDraft=null;calendarPanel?.close();
}
function field(form,label,name,value='',type='text',options=null){
 const line=el('label',label),input=el(options?'select':type==='textarea'?'textarea':'input');
 if(options){for(const opt of options){const [v,t]=Array.isArray(opt)?opt:[opt,opt];input.append(new Option(t,v))}if(value&&!Array.from(input.options).some(o=>o.value===String(value)))input.append(new Option(value,value));}
 else if(type!=='textarea')input.type=type;
 input.name=name;input.setAttribute('aria-label',label);
 if(type==='checkbox'){input.checked=!!value;line.className='check';line.prepend(input)}else{input.value=value??'';line.append(input)}
 form.append(line);return input;
}
function values(form){const out=Object.fromEntries(new FormData(form));for(const i of form.querySelectorAll('input[type=checkbox]'))out[i.name]=i.checked;for(const i of form.querySelectorAll('input[name=start],input[name=end]'))out[i.name]=i.value;return out}
function section(form,title){const d=el('details');d.append(el('summary',title));form.append(d);return d}
function feedback(form){const e=el('div','','panel-error');e.setAttribute('role','status');form.append(e);return e}
async function runButton(btn,error,fn){if(btn.disabled)return;btn.disabled=true;error.textContent='저장 중…';const form=btn.closest('form'),panel=btn.closest('dialog');if(panel)panel.dataset.busy='true';if(form)form.inert=true;try{await fn()}catch(e){error.textContent=e.message}finally{if(panel)delete panel.dataset.busy;if(form)form.inert=false;btn.disabled=false}}
function mutate(){calendarEpoch++;calendarCache.clear();reloadCalendar(true)}
function selectScope(value){
 if(!calendarBoot)return;
 const member=!['my','team'].includes(value)?value:null;
 if(member&&(!calendarBoot.managed||!Object.hasOwn(calendarBoot.members,member)))return;
 if(!member)memberSearchText='';calendarBoot.member=member;calendarBoot.team=value==='team';calendarEpoch++;calendarCache.clear();
 const search=document.querySelector('.member-search');
 if(search){search.querySelector('input').value=member?calendarBoot.members[member]:'';search.querySelector('.member-search-results').hidden=true;}
 latest={...latest,events:[],roster:{},scopeLabel:member?calendarBoot.members[member]:value==='team'?(calendarBoot.viewLabel||'지점 일정'):'내 일정'};
 if(calendarPanel)calendarPanel.close();calendarLoading=true;render(latest);reloadCalendar(true);
}
let memberSearchText='';
function memberSearchControl(){
 const wrap=el('div','','member-search'),input=el('input'),list=el('div','','member-search-results');
 wrap.dataset.key='member-search';wrap.searchContext=JSON.stringify([calendarBoot.uid,calendarBoot.access,calendarBoot.members]);
 input.type='search';input.placeholder='구성원 검색';input.setAttribute('aria-label','구성원 검색');input.value=memberSearchText||(calendarBoot.member?calendarBoot.members[calendarBoot.member]:'');
 list.setAttribute('role','group');list.setAttribute('aria-label','구성원 검색 결과');list.hidden=true;wrap.append(input,list);
 const draw=()=>{list.replaceChildren();const query=input.value.trim().toLocaleLowerCase();memberSearchText=input.value;
  for(const [uid,name] of Object.entries(calendarBoot.members).sort((a,b)=>a[1].localeCompare(b[1],'ko'))){
   if(query&&!name.toLocaleLowerCase().includes(query))continue;
   list.append(button(name,()=>{memberSearchText=name;list.hidden=true;selectScope(uid)},'',name+' 일정 보기'));
  }
  if(!list.children.length)list.append(el('p','검색 결과가 없습니다.','hint'));list.hidden=false;
 };
 input.oninput=draw;input.onfocus=draw;input.onkeydown=e=>{if(e.key==='Escape'){list.hidden=true;input.blur()}if(e.key==='Enter'){e.preventDefault();list.querySelector('button')?.click()}};
 wrap.addEventListener('focusout',()=>setTimeout(()=>{if(!wrap.contains(document.activeElement))list.hidden=true},0));
 return wrap;
}
async function openDetail(id){
 const card=latest.events.find(e=>e.id===id),body=createPanel('일정 상세',card?.readable!==false);const panel=calendarPanel;
 if(document.body.dataset.shellFirst==='true'&&card?.readable!==false)detailPlaceholder(body,card);
 else body.append(el('p',card?.label||'일정을 불러오는 중…'));
 if(card&&card.readable===false){body.prepend(el('h2',card.short));body.append(el('p','이 일정은 공개된 요약 정보만 조회할 수 있습니다.'));return}
 try{panel.setAttribute('aria-busy','true');const data=await rpc('detail',{id});if(calendarPanel!==panel)return;showDetail(data,body)}catch(e){if(calendarPanel===panel){body.querySelector('[role=status]')?.remove();body.append(el('p',e.message,'panel-error'),button('다시 불러오기',()=>openDetail(id)))}}finally{panel.removeAttribute('aria-busy')}
}
function detailPlaceholder(body,card){
 body.append(el('h2',card?.short||'일정 상세'));
 for(const [label,value] of [['날짜',card?.day],['시간',card?.timePending?'시간 미정':card?.start?.slice(0,5)||''],['활동 종류',card?.kind],['상태',card?.status],['장소',card?.place],['메모',''],['활동 결과',''],['피드백','']]){
  const line=el('div','','detail-line');line.append(el('strong',label));
  if(value)line.append(document.createTextNode(value));
  else {const placeholder=el('span','','calendar-placeholder');placeholder.setAttribute('aria-hidden','true');line.append(placeholder)}
  body.append(line);
 }
 const status=el('p','상세 내용을 불러오고 있습니다.','hint');status.setAttribute('role','status');body.append(status);
}
function showDetail(data,body){
 const row=data.row;body.replaceChildren();if(dayListReturn)body.append(button('‹ 목록으로',()=>openDayList(dayListReturn)));body.append(el('h2',row.title));
 for(const [label,value] of [['날짜',row.day],['시간',row.start_time?row.start_time.slice(0,5)+(row.end_time?'–'+row.end_time.slice(0,5):''):row.time_pending?'시간 미정':'종일'],['활동 종류',row.kind],['상태',row.kind==='휴무'?'':row.status],['장소',row.place],['동행자',calendarBoot.people[row.companion]],['메모',row.note],['활동 결과',row.result],['지원 요청',row.help]]){if(value){const line=el('div','','detail-line');line.append(el('strong',label),document.createTextNode(value));body.append(line)}}
 if(row.owner===calendarBoot.uid){
  const resultButton=button('완료 · 결과 처리',()=>openResult(row),'result-trigger');resultButton.hidden=row.kind==='휴무';calendarPanel.querySelector('.panel-head').insertBefore(resultButton,calendarPanel.querySelector('.panel-head button'));
  const actions=el('div','','panel-actions');actions.append(button('일정 수정',()=>openEditor(row,'edit')),button('일정 복사',()=>openEditor(row,'copy')),button('일정 삭제',()=>deleteEvent(row),'danger'));body.append(actions);
  const next=section(body,'다음 활동 추가');next.hidden=row.kind==='휴무';next.append(button('후속 일정 작성',()=>openEditor(row,'follow')));
  const contracts=section(body,'청약·계약 입력 및 수정');contracts.hidden=row.kind==='휴무';contracts.append(button('새 청약',()=>openContract(row,null)));for(const c of data.contracts)contracts.append(button(c.insurer+' · '+Number(c.amount).toLocaleString()+'원 · '+c.status,()=>openContract(row,c),'row'));
 }
 const reviews=section(body,'피드백');reviews.open=true;paintReviews(reviews,data);
}
function openResult(row){
 const parentPanel=calendarPanel,box=el('dialog','','calendar-result-overlay');box.setAttribute('aria-label','완료 · 결과 처리');
 const close=()=>{if(!box.dataset.busy)box.close()};
 const head=el('div','','panel-head');head.append(el('h3','완료 · 결과 처리'),button('×',close,'','결과 처리 닫기'));box.append(head);
 const form=el('form');box.append(form);
 const status=field(form,'처리 결과','status','완료','text',['완료','연기','취소']);
 field(form,'활동 결과 · 선택','result',row.result||'','textarea');
 const next=el('div','','result-follow');form.append(next);
 const follow=field(next,'새 일정 날짜','follow',iso(add(date(row.day>latest.today?row.day:latest.today),1)),'date');follow.min=row.day;
 field(next,'새 일정 시작 시간','follow_start',row.start_time?.slice(0,5)||'','time');field(next,'새 일정 종료 시간 · 선택','follow_end',row.end_time?.slice(0,5)||'','time');
 const paint=()=>{next.hidden=status.value!=='연기';follow.required=status.value==='연기';status.dataset.status=status.value};status.onchange=paint;paint();
 const error=feedback(form),save=button('결과 저장',()=>{if(!form.reportValidity())return;runButton(save,error,async()=>{
  const v=values(form),data={day:row.day,title:row.title,kind:row.kind,mode:row.start_time?'시간 지정':row.time_pending?'시간 미정':'종일',start:row.start_time||'',end:row.end_time||'',place:row.place||'',note:row.note||'',support:!!row.help,help:row.help||'',help_recipient:row.help_recipient||'',companion:row.companion,common:row.common,status:v.status,result:v.result,follow:v.status==='연기'?v.follow:''};
  if(v.status==='연기')Object.assign(data,{follow_start:v.follow_start,follow_end:v.follow_end});
  await rpc('save',{id:row.id,revision:row.revision,data});box.close();openDetail(row.id);mutate();calendarStatus('저장했습니다.');
 })},'primary');form.append(save,button('닫기',close));form.onsubmit=e=>{e.preventDefault();save.click()};
 box.addEventListener('cancel',e=>{e.preventDefault();e.stopPropagation();close()});box.addEventListener('close',()=>{box.remove();parentPanel?.querySelector('.result-trigger')?.focus({preventScroll:true})});
 parentPanel.addEventListener('close',()=>box.close(),{once:true});document.body.append(box);showCalendarDialog(box);
}
function paintReviews(host,data){
 host.replaceChildren(el('summary','피드백'));const row=data.row,panel=calendarPanel;
 const refresh=async()=>{const fresh=await rpc('detail',{id:row.id});if(panel===calendarPanel)paintReviews(host,fresh)};
 for(const r of data.reviews){
  const card=el('div','','feedback-card');card.append(el('small',(r.author||'관리자')+' · '+new Date(r.created_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+(r.updated_at?' · 수정됨':'')),el('p',r.message));host.append(card);
  if(r.reviewer===calendarBoot.uid){
   const actions=el('div','','panel-actions');card.append(actions);
   actions.append(button('수정',()=>{actions.replaceChildren();const f=el('form');actions.append(f);const input=field(f,'피드백 수정','message',r.message,'textarea');input.maxLength=4000;const error=feedback(f),save=button('수정 저장',()=>runButton(save,error,async()=>{await rpc('review_edit',{id:row.id,review:r.id,version:r.edit_version,message:input.value});await refresh()}));f.append(save,button('취소',()=>paintReviews(host,data)));f.onsubmit=e=>e.preventDefault();input.focus()}));
   actions.append(button('삭제',()=>{const confirmBox=el('dialog','','calendar-close-confirm');confirmBox.setAttribute('aria-label','피드백 삭제 확인');confirmBox.append(el('h3','이 피드백을 삭제할까요?'));const error=feedback(confirmBox),remove=button('피드백 삭제',()=>runButton(remove,error,async()=>{await rpc('review_delete',{id:row.id,review:r.id,version:r.edit_version});await refresh();confirmBox.close()}),'danger');confirmBox.append(remove,button('취소',()=>confirmBox.close()));confirmBox.addEventListener('close',()=>retireDialog(confirmBox));document.body.append(confirmBox);showCalendarDialog(confirmBox)}));
  }
 }
 if(!data.reviews.length)host.append(el('p','등록된 피드백이 없습니다.','hint'));
 if(data.canReview){const f=el('form');host.append(f);const input=field(f,'피드백','message','','textarea');input.maxLength=4000;const seed=crypto.randomUUID(),error=feedback(f),save=button('피드백 등록',()=>runButton(save,error,async()=>{await rpc('review',{id:row.id,revision:row.revision,message:input.value,seed});await refresh()}),'primary');f.append(save);f.onsubmit=e=>e.preventDefault();}
}
function formatClockInput(input,event){
 const raw=input.value,pos=input.selectionStart??raw.length;
 let digits=raw.replace(/\D/g,'').slice(0,4),before=raw.slice(0,pos).replace(/\D/g,'').length;
 // Backspace over the generated separator deletes the preceding digit.
 if(event.inputType==='deleteContentBackward'&&digits.length===2&&!raw.includes(':')){digits=digits.slice(0,1);before=1}
 input.value=digits.length>=2?digits.slice(0,2)+':'+digits.slice(2):digits;
 const caret=Math.min(input.value.length,before+(before>=2?1:0));input.setSelectionRange(caret,caret);
}
function normalizeClock(value){
 let s=value.trim();if(!s)return '';
 if(/^\d{2}:\d?$/.test(s))s=s.replace(':','');
 if(/^\d{1,2}$/.test(s))s=s.padStart(2,'0')+':00';else if(/^\d{3,4}$/.test(s)){s=s.padStart(4,'0');s=s.slice(0,2)+':'+s.slice(2)}
 if(!/^\d{1,2}:\d{2}$/.test(s))return null;
 const [h,m]=s.split(':').map(Number);return h<24&&m<60?String(h).padStart(2,'0')+':'+String(m).padStart(2,'0'):null;
}
let calendarDrag=null,calendarMoving=false;
async function moveCalendarEvent(item,day){
 if(calendarMoving||item.member!==calendarBoot.uid||item.day===day)return;
 calendarMoving=true;calendarEpoch++;calendarCache.clear();const original=item.day;
 latest={...latest,events:latest.events.map(e=>e.id===item.id?{...e,day}:e)};render(latest);
 try{
  const result=await rpc('move',{id:item.id,revision:item.revision,day});
  await reloadCalendar(true);const notice=document.getElementById('move-notice');notice.replaceChildren(document.createTextNode(day+'로 이동했습니다. '));notice.hidden=false;
  const undo=button('되돌리기',async()=>{if(calendarMoving)return;calendarMoving=true;undo.disabled=true;try{await rpc('move',{id:item.id,revision:result.revision,day:original});notice.hidden=true;await reloadCalendar(true)}catch(e){notice.replaceChildren(document.createTextNode(e.message));await reloadCalendar(true)}finally{calendarMoving=false}});notice.append(undo);
 }catch(e){latest={...latest,events:latest.events.map(e=>e.id===item.id?item:e)};render(latest);await reloadCalendar(true);const notice=document.getElementById('move-notice');notice.textContent=e.message;notice.hidden=false;}
 finally{calendarMoving=false}
}
function wireCalendarDrag(chip,item){
 if(item.groupLeave)return;
 if(item.member!==calendarBoot?.uid)return;
 chip.draggable=true;chip.classList.add('draggable-event');
 chip.ondragstart=e=>{if(!matchMedia('(min-width:701px) and (pointer:fine)').matches||calendarMoving||calendarPanel){e.preventDefault();return}calendarDrag={...item};e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',item.id)};
 chip.ondragend=()=>{calendarDrag=null;suppressClickUntil=Date.now()+450;document.querySelectorAll('.drop-target').forEach(e=>e.classList.remove('drop-target'))};
}
function wireCalendarDrop(box,day){
 box.ondragover=e=>{if(calendarDrag&&calendarDrag.day!==day){e.preventDefault();e.dataTransfer.dropEffect='move';e.currentTarget.classList.add('drop-target')}};
 box.ondragleave=e=>e.currentTarget.classList.remove('drop-target');
 box.ondrop=e=>{e.preventDefault();e.currentTarget.classList.remove('drop-target');const item=calendarDrag;calendarDrag=null;suppressClickUntil=Date.now()+450;if(item)moveCalendarEvent(item,day)};
}
let recipientFlight=null,editorOpenSeq=0;
async function openEditor(row,kind,day){
 const openSeq=++editorOpenSeq;
 if(!calendarBoot.supportRecipients){
  try{recipientFlight??=rpc('support_recipients');calendarBoot.supportRecipients=await recipientFlight;}
  catch(e){calendarStatus(e.message);return}finally{recipientFlight=null}
 }

 if(openSeq!==editorOpenSeq)return;
 const editing=['edit','result'].includes(kind),key=kind+':'+(row?.id||day),saved=calendarDrafts.get(key);
 const body=createPanel({edit:'일정 수정',result:'완료 · 결과 처리',copy:'일정 복사',follow:'다음 활동 추가',new:'일정 등록'}[kind],true);
 let initial={day:day||row?.day||selected,title:row?.title||'',kind:kind==='follow'?({TA:'AP',AP:'PC'}[row.kind]||'미분류'):row?.kind||'미분류',mode:row?.start_time?'시간 지정':row?.time_pending||!row?'시간 미정':'종일',start:row?.start_time?.slice(0,5)||'',end:row?.end_time?.slice(0,5)||'',place:row?.place||'',note:row?.note||'',support:editing&&!!row.help,help:editing?row.help||'':'',help_recipient:editing?row.help_recipient||'':'',companion:row?.companion||'',common:editing&&row.common,status:editing?row.status:'예정',result:editing?row.result||'':'',repeat:false,repeats:1,follow:''};
 if(kind==='follow')initial={...initial,mode:'시간 미정',start:'',end:'',place:'',note:'',companion:''};
 if(kind==='result')initial.status='완료';
 const draft=calendarDraft=saved||{key,seed:crypto.randomUUID(),values:initial,dirty:false,row:row?{...row}:null,manualKind:false};calendarDrafts.set(key,draft);row=draft.row;
 const v=draft.values,form=el('form');body.append(form);
 let status,paintLeave=()=>{};
 if(kind!=='result'){
  const title=field(form,'일정명','title',v.title);title.required=true;title.maxLength=200;
  const pair=el('div','','pair');form.append(pair);field(pair,'날짜','day',v.day,'date').required=true;const activity=field(pair,'활동 종류','kind',v.kind,'text',calendarBoot.kinds);
  const allDay=field(form,'종일','all_day',v.all_day??v.mode==='종일','checkbox'),times=el('div','','pair');form.append(times);
  times.style.alignItems='start';
  const start=field(times,'시작 시간','start',v.start),endWrap=el('div');times.append(endWrap);const end=field(endWrap,'종료 시간 · 선택','end',v.end);
  const endError=el('p','','panel-error time-range-error');endError.setAttribute('aria-live','polite');endWrap.append(endError);
  const hint=el('p','','hint');form.append(hint);
  const mode=field(form,'시간 저장 방식','mode',v.mode,'hidden');mode.parentElement.hidden=true;
  const auto=field(form,'시간 자동 판별','auto_time','1','hidden');auto.parentElement.hidden=true;
  const updateTime=()=>{times.hidden=allDay.checked;start.disabled=end.disabled=allDay.checked;mode.value=allDay.checked?'종일':start.value.trim()?'시간 지정':'시간 미정';const t=normalizeClock(start.value);hint.textContent=allDay.checked?'종일 일정':t===null?'0~23시, 0~59분으로 입력해 주세요.':t? t+' · '+(Number(t.slice(0,2))<12?'오전 ':'오후 ')+(Number(t.slice(0,2))%12||12)+'시 '+Number(t.slice(3))+'분':'비워두면 시간 미지정으로 저장됩니다.'};
  const validateEnd=()=>{const a=normalizeClock(start.value),b=normalizeClock(end.value);const msg=allDay.checked?'':end.value.trim()&&!start.value.trim()?'시작 시간을 먼저 입력해 주세요.':a&&b&&b<=a?'종료 시간은 시작 시간보다 늦어야 합니다.':'';end.setCustomValidity(msg);endError.textContent=msg};
  for(const input of [start,end]){input.inputMode='numeric';input.placeholder='--:--';input.maxLength=5;input.oninput=e=>{formatClockInput(input,e);input.setCustomValidity('');updateTime();validateEnd()};input.onblur=()=>{const t=normalizeClock(input.value);input.setCustomValidity(t===null?'시간을 확인해 주세요. 예: 930 또는 1430':'');if(t!==null)input.value=t;updateTime();if(t!==null)validateEnd();input.dispatchEvent(new Event('change',{bubbles:true}))};}
  allDay.onchange=()=>{updateTime();validateEnd()};updateTime();validateEnd();
  const place=field(form,'장소 · 선택','place',v.place);
  const extra=section(form,'추가 정보 · 선택');extra.open=!!(v.note||v.companion||v.support||v.repeat||v.common);field(extra,'메모','note',v.note,'textarea');field(extra,'동행자','companion',v.companion,'text',[['','선택 안 함'],...Object.entries(calendarBoot.people).filter(([u])=>u!==calendarBoot.uid)]);
  title.autofocus=true;title.focus({preventScroll:true});
  const support=field(extra,'지원 요청','support',v.support,'checkbox'),help=field(extra,'지원받을 내용','help',v.help);const managers=Object.entries(calendarBoot.supportRecipients||{});
  const recipient=field(extra,'지원 요청 대상','help_recipient',v.help_recipient||(managers.length===1?managers[0][0]:''),'text',[['','관리자를 선택하세요'],...managers]);
  if(!managers.length)extra.append(el('p','연결된 요청 대상이 없습니다. 담당 관리자 연결을 확인해 주세요.','hint'));
  const supportVisibility=()=>{help.parentElement.hidden=!support.checked;recipient.parentElement.hidden=!support.checked};supportVisibility();support.onchange=supportVisibility;
  if(!editing){const repeat=field(extra,'매주 반복','repeat',v.repeat,'checkbox'),count=field(extra,'총 등록 횟수 · 이번 일정 포함','repeats',v.repeats,'number');count.min=1;count.max=52;count.parentElement.hidden=!repeat.checked;repeat.onchange=()=>count.parentElement.hidden=!repeat.checked;}
  if(calendarBoot.managed)field(extra,'지점 공통 일정','common',v.common,'checkbox');
  title.addEventListener('input',()=>{if(!editing&&kind!=='copy'&&kind!=='follow'&&!draft.manualKind){const found=[...new Set((title.value.toUpperCase().match(/\b(TA|AP|PC|CS)\b/g)||[]))];activity.value=found.length===1?found[0]:'미분류'}});
  const choice=el('div','','switch leave-switch');form.prepend(choice);
  const ordinary=button('일정',()=>{activity.value='미분류';if(title.value==='휴무')title.value='';paintLeave();form.dispatchEvent(new Event('change',{bubbles:true}))});
  const leave=button('휴무',()=>{activity.value='휴무';paintLeave();form.dispatchEvent(new Event('change',{bubbles:true}))});choice.append(ordinary,leave);
  const leaveOptions=el('div','','leave-options');pair.after(leaveOptions);
  const multi=field(leaveOptions,'여러 날','leave_multiple',!!v.leave_multiple,'checkbox');multi.parentElement.hidden=editing;
  const until=field(leaveOptions,'종료일','leave_end',v.leave_end||v.day,'date');until.min=v.day;
  const warning=el('p','','hint');leaveOptions.append(warning);
  paintLeave=()=>{
   const off=activity.value==='휴무';if(off)draft.manualKind=true;
   ordinary.classList.toggle('active',!off);leave.classList.toggle('active',off);
   title.parentElement.hidden=off;activity.parentElement.hidden=off;allDay.parentElement.hidden=off;place.parentElement.hidden=off;extra.hidden=off;leaveOptions.hidden=!off;
   until.parentElement.hidden=!multi.checked||editing;until.disabled=!off||!multi.checked||editing;
   if(off){title.value='휴무';allDay.checked=true;support.checked=false;help.value='';recipient.value='';}
   updateTime();hint.hidden=off;
   form.querySelectorAll('.status-section').forEach(x=>x.hidden=off);
   const count=(latest.events||[]).filter(e=>e.member===calendarBoot.uid&&e.kind!=='휴무'&&e.day>=form.elements.day.value&&e.day<=(multi.checked?until.value:form.elements.day.value)).length;
   warning.textContent=count?'현재 불러온 기간에 기존 일정 '+count+'건이 있습니다. 기존 일정은 유지됩니다.':'';
   const save=form.querySelector('.editor-actions .primary');if(save)save.textContent=off?(editing?'휴무 변경 저장':'휴무 등록'):(editing?'변경 저장':'일정 등록');
  };
  activity.onchange=()=>{draft.manualKind=true;paintLeave()};multi.onchange=paintLeave;until.onchange=paintLeave;
  form.elements.day.addEventListener('change',()=>{until.min=form.elements.day.value;if(until.value<until.min)until.value=until.min;paintLeave()});

 }
 if(editing){const state=kind==='result'?form:section(form,'처리 상태 · 활동 결과');state.classList.add('status-section');if(state.tagName==='DETAILS')state.open=v.status!=='예정';status=field(state,kind==='result'?'처리 결과':'처리 상태','status',v.status,'text',kind==='result'?['완료','연기','취소']:['예정','완료','연기','취소']);status.dataset.status=status.value;status.addEventListener('change',()=>status.dataset.status=status.value);field(state,'활동 결과 · 선택','result',v.result,'textarea');const follow=field(state,kind==='result'?'새 일정 날짜':'후속 일정 날짜 · 선택','follow',v.follow,'date');follow.min=v.day;field(state,'새 일정 시작 시간','follow_start',v.follow_start??row.start_time?.slice(0,5)??'','time');field(state,'새 일정 종료 시간 · 선택','follow_end',v.follow_end??row.end_time?.slice(0,5)??'','time');if(kind==='result'){follow.parentElement.hidden=status.value!=='연기';status.onchange=()=>{follow.parentElement.hidden=status.value!=='연기';if(status.value==='연기'&&!follow.value)follow.value=iso(add(date(row.day>latest.today?row.day:latest.today),1))}}}
 const error=feedback(form);
 const save=button(editing?'변경 저장':'일정 등록',()=>{for(const input of form.querySelectorAll('input[name=start],input[name=end]'))input.dispatchEvent(new Event('blur'));if(!form.reportValidity())return;runButton(save,error,async()=>{
  draft.values={...v,...values(form)};if(draft.values.kind==='휴무'&&!draft.values.leave_multiple)draft.values.leave_end='';if(kind==='result'&&draft.values.status!=='연기')draft.values.follow='';
  const result=await rpc('save',{id:editing?row.id:null,revision:editing?row.revision:null,parent:kind==='follow'?row.id:null,seed:draft.seed,data:draft.values,overlap:draft.overlap});
  if(result.overlap){draft.overlap=result.overlap;error.textContent=result.message;return}
  draft.dirty=false;calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;latest={...latest,day:result.day};selected=result.day;context=null;openDetail(result.id)}mutate();calendarStatus('저장했습니다.');
 })},'primary');const actions=el('div','','editor-actions');actions.append(button('닫기',()=>closePanel()),save);form.append(actions);
 if(editing){form.append(button('최신 기록 불러오기',()=>{if(confirm('현재 입력 대신 최신 저장 내용을 불러올까요?')){calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;openDetail(row.id)}}}));}
 paintLeave();
 const remember=()=>{draft.values={...v,...values(form)};draft.dirty=true};form.addEventListener('input',remember);form.addEventListener('change',remember);form.onsubmit=e=>{e.preventDefault();save.click()};
}
function deleteEvent(row){
 const body=createPanel('일정 삭제');body.append(el('p',row.day+' · '+row.title),el('p','일정은 즉시 삭제되며 복구할 수 없습니다. 연결된 계약·후속 활동은 보존됩니다.'));
 const f=el('form');body.append(f);if(row.series_id)field(f,'삭제 범위','scope','one','text',[['one','이번 일정만'],['future','이후 반복 일정까지']]);const error=feedback(f),save=button('일정 삭제 확인',()=>runButton(save,error,async()=>{await rpc('delete',{id:row.id,revision:row.revision,future:values(f).scope==='future'});for(const [k,d] of calendarDrafts)if(d.row?.id===row.id)calendarDrafts.delete(k);calendarPanel?.close();mutate()}),'danger');f.append(save);f.onsubmit=e=>e.preventDefault();
}
function openContract(row,old){
 const key='contract:'+(old?.id||row.id),saved=calendarDrafts.get(key),body=createPanel('청약·계약 입력 및 수정',true),f=el('form');body.append(f);
 const draft=calendarDraft=saved||{key,seed:crypto.randomUUID(),dirty:false,values:old||{},row:old};calendarDrafts.set(key,draft);old=draft.row;const v=draft.values;
 field(f,'보험사','insurer',v.insurer||calendarBoot.insurers[0],'text',calendarBoot.insurers);field(f,'보험 구분','category',v.category||'인보험','text',['인보험','일반보험','자동차보험']);field(f,'납입 방식','payment',v.payment||'월납','text',['월납','연납','일시납']);const amount=field(f,'보험료 · 원','amount',v.amount||0,'number');amount.min=1;amount.required=true;
 field(f,'접수일','day',v.day||row.day,'date').required=true;const status=field(f,'청약 상태','status',v.status||'청약 접수','text',['청약 접수','심사 중','성립','철회','미성립']);const effective=field(f,'성립일','effective',v.effective||v.day||row.day,'date');effective.parentElement.hidden=status.value!=='성립';status.onchange=()=>effective.parentElement.hidden=status.value!=='성립';field(f,'상품명 · 선택','product',v.product||'');field(f,'계약 메모 · 선택','note',v.note||'','textarea');
 const error=feedback(f),save=button('청약 저장',()=>{if(!f.reportValidity())return;runButton(save,error,async()=>{draft.values=values(f);await rpc('contract',{event:row.id,id:old?.id,revision:old?.revision,seed:draft.seed,data:draft.values});calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;openDetail(row.id)}})},'primary');f.append(save);const remember=()=>{draft.values=values(f);draft.dirty=true};f.addEventListener('input',remember);f.addEventListener('change',remember);f.onsubmit=e=>{e.preventDefault();save.click()};
}
// Preserve browser-side drafts when the host is busy. Never intercept auth/logout.
addEventListener('beforeunload',e=>{if(calendarDraft?.dirty){e.preventDefault();e.returnValue=''}});

// Date lists share the existing dialog; editor state is never rebuilt by updates.
let dayListReturn=null,dayListUndo=null;
function openDayList(day){
 if(!calendarBoot)return;
 dayListReturn=day;dayListUndo=null;
 if(day<latest.rangeStart||day>latest.rangeEnd){latest={...latest,day};selected=day;context=null;reloadCalendar()}
 const title=Number(day.slice(5,7))+'월 '+Number(day.slice(8))+'일 '+'일월화수목금토'[date(day).getUTCDay()]+'요일';
 const body=createPanel(title,true);calendarPanel.dataset.dayList=day;paintDayList();
}
function paintDayList(){
 const panel=calendarPanel,day=panel?.dataset.dayList;
 if(!day||panel.dataset.busy)return;
 const body=panel.querySelector('.panel-content'),scroll=body.scrollTop;
 const items=latest.events.filter(e=>e.day===day&&(prefs.showCompleted||!e.done)).sort((a,b)=>(b.kind==='휴무')-(a.kind==='휴무')||Number(!!a.timePending)-Number(!!b.timePending)||(a.start||'').localeCompare(b.start||'')||a.id.localeCompare(b.id));
 const fresh=el('div');fresh.append(el('p',(latest.scopeLabel||'내 일정')+(calendarLoading?' · 조회 중':' · '+items.length+'건'),'hint'));
 const nav=el('div','','day-list-nav');nav.append(button('‹ 이전 날짜',()=>openDayList(iso(add(date(day),-1)))),button('오늘',()=>openDayList(latest.today)),button('다음 날짜 ›',()=>openDayList(iso(add(date(day),1)))));fresh.append(nav);
 if(calendarLoading){const loading=el('p','일정을 불러오는 중입니다.','hint');loading.setAttribute('role','status');fresh.append(loading)}
 if(calendarLoadError)fresh.append(button('다시 불러오기',()=>reloadCalendar(true)));
 if(!items.length&&!calendarLoading&&!calendarLoadError)fresh.append(el('p','등록된 일정이 없습니다.','hint'));
 let pending=false;
 for(const item of items){
  if(item.timePending&&!pending){fresh.append(el('h4','시간 미정','day-list-group'));pending=true}
  const line=el('div','','day-list-row');line.dataset.key=item.id;
  const info=button('',()=>openDetail(item.id),'day-list-info');info.append(el('strong',item.start?item.start.slice(0,5):item.timePending?'': '종일','day-list-time'),el('span',item.short,'day-list-title'),el('small',item.kind+(item.place?' · '+item.place:''),'day-list-meta'));line.append(info);
  if(item.done)line.append(el('span','✓ 완료','day-list-done'));
  else if(item.member===calendarBoot.uid&&item.kind!=='휴무'&&item.status==='예정'&&item.revision!=null){
   const error=el('div','','panel-error');
   const complete=button('✓ 완료',()=>runButton(complete,error,async()=>{
    const result=await rpc('status',{id:item.id,revision:item.revision,status:'완료'});
    latest.events=latest.events.map(e=>e.id===item.id?{...e,done:true,status:result.status,revision:result.revision}:e);
    dayListUndo={id:item.id,revision:result.revision};
    delete panel.dataset.busy;paintDayList();
    const completed=Array.from(panel.querySelectorAll('.day-list-row')).find(row=>row.dataset.key===item.id);
    if(completed){completed.classList.add('calendar-completed');completed.addEventListener('animationend',()=>completed.classList.remove('calendar-completed'),{once:true})}
    mutate();
   }),'day-list-complete',item.short+' 완료 처리');line.append(complete,error);
  }else if(item.kind!=='휴무')line.append(el('small',item.status||''));
  line.append(button('›',()=>openDetail(item.id),'',item.short+' 상세 보기'));fresh.append(line);
 }
 if(dayListUndo){const undo=dayListUndo,notice=el('div','','day-list-notice'),error=el('span','','panel-error');const back=button('되돌리기',()=>runButton(back,error,async()=>{
  const result=await rpc('status',{id:undo.id,revision:undo.revision,status:'예정'});
  latest.events=latest.events.map(e=>e.id===undo.id?{...e,done:false,status:result.status,revision:result.revision}:e);dayListUndo=null;delete panel.dataset.busy;paintDayList();mutate();
 }));notice.append(el('span','완료 처리했습니다.'),back,error);fresh.append(notice)}
 const footer=el('div','','editor-actions');footer.append(button('＋ 일정 등록',()=>openEditor(null,'new',day),'primary'));fresh.append(footer);
 syncChildren(body,fresh);body.scrollTop=scroll;
}
