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
 const hostEntering=typeof receiveHost==='function'?receiveHost(a):false;
 if(a.hosted&&!a.hostActive)return;
 if(!a.boot)return;
 fitCalendar();
 if(calendarBoot&&(calendarBoot.uid!==a.boot.uid||calendarBoot.access!==a.boot.access)){calendarEpoch++;calendarSeq++;stopRealtime();calendarCache.clear();calendarDrafts.clear();if(calendarPanel)calendarPanel.close();calendarBoot=null;context=null;lastRender=null;}
 if(!calendarBoot){
  calendarBoot=a.boot;
  try{parent.__hwarangCalendarMemory??={};calendarMemory=parent.__hwarangCalendarMemory[calendarBoot.uid]??={drafts:new Map()};calendarDrafts=calendarMemory.drafts; if(calendarMemory.access!==a.boot.access){calendarMemory.cache=new Map();calendarMemory.access=a.boot.access;}for(const [k,v] of calendarMemory.cache||[])calendarCache.set(k,v);}catch{}
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
  const response=await fetch(session.url+'/rest/v1/rpc/sales_calendar_payload',{method:'POST',headers:{apikey:session.key,Authorization:'Bearer '+session.token,'Content-Type':'application/json'},body:JSON.stringify({first_day:first,last_day:last,p_member:member||null,p_team:!!team}),signal:controller.signal});
  if(!response.ok){if(response.status===401)calendarAction('reauth');if(response.status===403){calendarCache.clear();if(calendarMemory)calendarMemory.cache=new Map();latest={...latest,events:[],roster:{}};}throw Error('일정을 불러오지 못했습니다. 다시 확인해 주세요.');}
  const data=await response.json(),details=new Map(data.rows.map(r=>[r.id,r])),branch=Object.fromEntries(data.branch.map(r=>[r.member,r.label]));
  const rows=member?data.rows:data.summary.map(r=>details.get(r.id)||r);
  const now=new Date(),kst=new Date(now.getTime()+9*3600000).toISOString(),today=kst.slice(0,10),clock=kst.slice(11,19);
  const events=rows.sort((a,b)=>(a.day+(a.start_time||'')+a.id).localeCompare(b.day+(b.start_time||'')+b.id)).map(r=>{
   const owner=branch[r.owner]||calendarBoot.members[r.owner]||'지점 공통',stamp=(r.start_time||(r.time_pending?'시간 미정':'종일')).slice(0,5);
   const overdue=r.status==='예정'&&(r.day<today||r.day===today&&r.start_time&&r.start_time<clock);
   let label=stamp+' · '+r.kind+' · '+owner+' · '+(overdue?'결과 미입력':r.status);
   if(r.companion)label+=' · 동행 '+(branch[r.companion]||'');if(r.help)label+=' · 지원 요청';
   const seconds=r.start_time?(new Date(r.day+'T'+r.start_time+'+09:00')-now)/1000:-1;
   return {id:r.id,day:r.day,kind:r.kind,member:r.owner,allDay:!r.start_time,short:(r.title||r.kind)+(team?' · '+owner:''),label,done:r.status==='완료',soon:r.day===today&&r.status==='예정'&&seconds>=0&&seconds<=1800,readable:details.has(r.id)};
  });
  return {events,rangeStart:first,rangeEnd:last,syncUnit:data.unit,syncStamp:data.stamp,scopeLabel:member?calendarBoot.members[member]:team?'지점 일정':'내 일정',roster:team||member?Object.fromEntries(Object.entries(branch).filter(([u])=>!member||u===member)):{}};
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
 if(action==='event'){openDetail(value);return}
 if(action==='scope'){openScope();return}
 if(action==='refresh'){reloadCalendar(true);return}
 if(action==='reauth'){if(calendarFlight){setTimeout(()=>calendarAction('reauth'),1000);return}post('streamlit:setComponentValue',{value:{action:'reauth',nonce:crypto.randomUUID()},dataType:'json'});return}
}
function createPanel(title){
 dismissCloseConfirm();
 if(calendarPanel){calendarPanel.remove();calendarPanel=null;}
 const returnFocus=document.activeElement;
 try{const fab=parent.document.querySelector('.mobile-new-event');if(fab)fab.style.visibility='hidden'}catch{}
 const panel=calendarPanel=el('dialog','','calendar-panel');panel.setAttribute('aria-label',title);
 const head=el('div','','panel-head'),body=el('div','','panel-content');head.append(el('h3',title),button('×',()=>closePanel(),'','팝업 닫기'));panel.append(head,body);document.body.append(panel);
 let backdropDown=false;
 const outside=e=>{const b=panel.getBoundingClientRect();return e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom};
 panel.addEventListener('pointerdown',e=>{backdropDown=e.target===panel&&outside(e)});
 panel.addEventListener('click',e=>{if(backdropDown&&e.target===panel&&outside(e))closePanel();backdropDown=false});
 panel.addEventListener('cancel',e=>{e.preventDefault();closePanel()});panel.addEventListener('close',()=>{panel.remove();if(calendarPanel===panel)calendarPanel=null;try{const fab=parent.document.querySelector('.mobile-new-event');if(fab)fab.style.visibility=''}catch{}returnFocus?.focus({preventScroll:true})});panel.showModal();calendarDraft=null;
 return body;
}
let calendarCloseConfirm=null;
function dismissCloseConfirm(){
 const box=calendarCloseConfirm;if(!box)return;
 calendarCloseConfirm=null;box.close();box.remove();
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
  box.showModal();keepWriting.focus({preventScroll:true});return;
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
function values(form){const out=Object.fromEntries(new FormData(form));for(const i of form.querySelectorAll('input[type=checkbox]'))out[i.name]=i.checked;return out}
function section(form,title){const d=el('details');d.append(el('summary',title));form.append(d);return d}
function feedback(form){const e=el('div','','panel-error');e.setAttribute('role','status');form.append(e);return e}
async function runButton(btn,error,fn){if(btn.disabled)return;btn.disabled=true;error.textContent='저장 중…';const form=btn.closest('form'),panel=btn.closest('dialog');if(panel)panel.dataset.busy='true';if(form)form.inert=true;try{await fn()}catch(e){error.textContent=e.message}finally{if(panel)delete panel.dataset.busy;if(form)form.inert=false;btn.disabled=false}}
function mutate(){calendarEpoch++;calendarCache.clear();reloadCalendar(true)}
function openScope(){
 const body=createPanel('조회 대상'),form=el('form');body.append(form);
 const options=[['my','내 일정'],['team','지점 일정'],...Object.entries(calendarBoot.members).map(([u,n])=>[u,n])];
 const input=field(form,'직원 이름 검색 · 선택','scope',calendarBoot.member||(calendarBoot.team?'team':'my'),'text',options);
 // A local search filters authorized names only.
 const search=field(form,'이름 검색','search');search.oninput=()=>{for(const o of input.options)o.hidden=!['my','team'].includes(o.value)&&!o.textContent.includes(search.value)};
 const apply=button('적용',()=>{calendarBoot.member=['my','team'].includes(input.value)?null:input.value;calendarBoot.team=input.value==='team';calendarEpoch++;calendarCache.clear();latest={...latest,events:[],roster:{},scopeLabel:input.selectedOptions[0].textContent};calendarPanel.close();reloadCalendar(true)},'primary');form.append(apply);form.onsubmit=e=>e.preventDefault();
}
async function openDetail(id){
 const card=latest.events.find(e=>e.id===id),body=createPanel('일정 상세');body.append(el('p',card?.label||'일정을 불러오는 중…'));const panel=calendarPanel;
 if(card&&card.readable===false){body.append(el('p','이 일정은 공개된 요약 정보만 조회할 수 있습니다.'));return}
 try{const data=await rpc('detail',{id});if(calendarPanel!==panel)return;showDetail(data,body)}catch(e){if(calendarPanel===panel)body.append(el('p',e.message,'panel-error'))}
}
function showDetail(data,body){
 const row=data.row;body.replaceChildren();body.append(el('h2',row.title));
 for(const [label,value] of [['날짜',row.day],['시간',row.start_time?row.start_time.slice(0,5)+(row.end_time?'–'+row.end_time.slice(0,5):''):row.time_pending?'시간 미정':'종일'],['활동 종류',row.kind],['상태',row.status],['장소',row.place],['동행자',calendarBoot.people[row.companion]],['메모',row.note],['활동 결과',row.result],['지원 요청',row.help]]){if(value){const line=el('div','','detail-line');line.append(el('strong',label),document.createTextNode(value));body.append(line)}}
 if(row.owner===calendarBoot.uid){
  const actions=el('div','','panel-actions');actions.append(button('일정 수정',()=>openEditor(row,'edit')),button('완료 · 결과 처리',()=>openEditor(row,'result'),'primary'),button('일정 복사',()=>openEditor(row,'copy')),button('일정 삭제',()=>deleteEvent(row),'danger'));body.append(actions);
  const next=section(body,'다음 활동 추가');next.append(button('후속 일정 작성',()=>openEditor(row,'follow')));
  const task=el('form');next.append(task);field(task,'할 일','title').maxLength=200;field(task,'기한','due',row.day>latest.today?row.day:latest.today,'date');const error=feedback(task),seed=crypto.randomUUID();const save=button('할 일 추가',()=>runButton(save,error,async()=>{await rpc('task',{id:row.id,seed,...values(task)});error.textContent='할 일을 추가했습니다.';save.hidden=true}));task.append(save);task.onsubmit=e=>e.preventDefault();
  const contracts=section(body,'청약·계약 입력 및 수정');contracts.append(button('새 청약',()=>openContract(row,null)));for(const c of data.contracts)contracts.append(button(c.insurer+' · '+Number(c.amount).toLocaleString()+'원 · '+c.status,()=>openContract(row,c),'row'));
 }
 const reviews=section(body,'확인 · 피드백');for(const r of data.reviews)reviews.append(el('p',r.created_at.slice(0,10)+' · '+r.message+(r.revision!==row.revision?' · 이전 버전':'')));
 if(data.canReview){const f=el('form');reviews.append(f);field(f,'피드백 또는 변경 요청','message');const error=feedback(f),save=button('일정 확인 · 의견 저장',()=>runButton(save,error,async()=>{await rpc('review',{id:row.id,revision:row.revision,message:values(f).message});error.textContent='의견을 저장했습니다.';save.hidden=true}));f.append(save);f.onsubmit=e=>e.preventDefault();}
}
function openEditor(row,kind,day){
 const editing=['edit','result'].includes(kind),key=kind+':'+(row?.id||day),saved=calendarDrafts.get(key);
 const body=createPanel({edit:'일정 수정',result:'완료 · 결과 처리',copy:'일정 복사',follow:'다음 활동 추가',new:'일정 등록'}[kind]);
 let initial={day:day||row?.day||selected,title:row?.title||'',kind:kind==='follow'?({TA:'AP',AP:'PC'}[row.kind]||'미분류'):row?.kind||'미분류',mode:row?.start_time?'시간 지정':row?.time_pending||!row?'시간 미정':'종일',start:row?.start_time?.slice(0,5)||'',end:row?.end_time?.slice(0,5)||'',place:row?.place||'',note:row?.note||'',support:editing&&!!row.help,help:editing?row.help||'':'',companion:row?.companion||'',common:editing&&row.common,status:editing?row.status:'예정',result:editing?row.result||'':'',repeat:false,repeats:1,follow:''};
 if(kind==='follow')initial={...initial,mode:'시간 미정',start:'',end:'',place:'',note:'',companion:''};
 if(kind==='result')initial.status='완료';
 const draft=calendarDraft=saved||{key,seed:crypto.randomUUID(),values:initial,dirty:false,row:row?{...row}:null,manualKind:false};calendarDrafts.set(key,draft);row=draft.row;
 const v=draft.values,form=el('form');body.append(form);
 let status;
 if(kind!=='result'){
  const title=field(form,'일정명','title',v.title);title.required=true;title.maxLength=200;
  const pair=el('div','','pair');form.append(pair);field(pair,'날짜','day',v.day,'date').required=true;const activity=field(pair,'활동 종류','kind',v.kind,'text',calendarBoot.kinds);
  const mode=field(form,'시간','mode',v.mode,'text',['시간 지정','종일','시간 미정']),times=el('div','','pair');form.append(times);const start=field(times,'시작 시간','start',v.start,'time'),end=field(times,'종료 시간 · 선택','end',v.end,'time');times.hidden=mode.value!=='시간 지정';mode.onchange=()=>times.hidden=mode.value!=='시간 지정';
  let lastStart=start.value;start.onchange=()=>{if(lastStart&&end.value&&start.value){const mins=s=>Number(s.slice(0,2))*60+Number(s.slice(3));const shifted=mins(end.value)+mins(start.value)-mins(lastStart);end.value=shifted>=0&&shifted<1440?String(Math.floor(shifted/60)).padStart(2,'0')+':'+String(shifted%60).padStart(2,'0'):'';}lastStart=start.value};
  const place=field(form,'장소 · 선택','place',v.place);
  const extra=section(form,'추가 정보 · 선택');extra.open=!!(v.note||v.companion||v.support||v.repeat||v.common);field(extra,'메모','note',v.note,'textarea');field(extra,'동행자','companion',v.companion,'text',[['','선택 안 함'],...Object.entries(calendarBoot.people).filter(([u])=>u!==calendarBoot.uid)]);
  title.autofocus=true;title.focus({preventScroll:true});
  const support=field(extra,'지원 요청','support',v.support,'checkbox'),help=field(extra,'지원받을 내용','help',v.help);help.parentElement.hidden=!support.checked;support.onchange=()=>help.parentElement.hidden=!support.checked;
  if(!editing){const repeat=field(extra,'매주 반복','repeat',v.repeat,'checkbox'),count=field(extra,'총 등록 횟수 · 이번 일정 포함','repeats',v.repeats,'number');count.min=1;count.max=52;count.parentElement.hidden=!repeat.checked;repeat.onchange=()=>count.parentElement.hidden=!repeat.checked;}
  if(calendarBoot.managed)field(extra,'지점 공통 일정','common',v.common,'checkbox');
  title.addEventListener('input',()=>{if(!editing&&kind!=='copy'&&kind!=='follow'&&!draft.manualKind){const found=[...new Set((title.value.toUpperCase().match(/\b(TA|AP|PC|CS)\b/g)||[]))];activity.value=found.length===1?found[0]:'미분류'}});
  activity.onchange=()=>{draft.manualKind=true;if(activity.value==='휴무'){mode.value='종일';times.hidden=true;if(!title.value.trim())title.value='휴무'}};
 }
 if(editing){const state=kind==='result'?form:section(form,'처리 상태 · 활동 결과');if(state.tagName==='DETAILS')state.open=v.status!=='예정';status=field(state,kind==='result'?'처리 결과':'처리 상태','status',v.status,'text',kind==='result'?['완료','연기','취소']:['예정','완료','연기','취소']);field(state,'활동 결과 · 선택','result',v.result,'textarea');const follow=field(state,kind==='result'?'새 일정 날짜':'후속 일정 날짜 · 선택','follow',v.follow,'date');follow.min=v.day;if(kind==='result'){follow.parentElement.hidden=status.value!=='연기';status.onchange=()=>{follow.parentElement.hidden=status.value!=='연기';if(status.value==='연기'&&!follow.value)follow.value=iso(add(date(row.day>latest.today?row.day:latest.today),1))}}}
 const error=feedback(form);
 const save=button(editing?'변경 저장':'일정 등록',()=>{if(!form.reportValidity())return;runButton(save,error,async()=>{
  draft.values={...v,...values(form)};if(kind==='result'&&draft.values.status!=='연기')draft.values.follow='';
  const result=await rpc('save',{id:editing?row.id:null,revision:editing?row.revision:null,parent:kind==='follow'?row.id:null,seed:draft.seed,data:draft.values,overlap:draft.overlap});
  if(result.overlap){draft.overlap=result.overlap;error.textContent=result.message;return}
  draft.dirty=false;calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;latest={...latest,day:result.day};selected=result.day;context=null;openDetail(result.id)}mutate();calendarStatus('저장했습니다.');
 })},'primary');const actions=el('div','','editor-actions');actions.append(button('닫기',()=>closePanel()),save);form.append(actions);
 if(editing){form.append(button('최신 기록 불러오기',()=>{if(confirm('현재 입력 대신 최신 저장 내용을 불러올까요?')){calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;openDetail(row.id)}}}));}
 const remember=()=>{draft.values={...v,...values(form)};draft.dirty=true};form.addEventListener('input',remember);form.addEventListener('change',remember);form.onsubmit=e=>{e.preventDefault();save.click()};
}
async function calendarTrash(){
 const body=createPanel('삭제한 일정');body.append(el('p','삭제 후 30일 동안 개별 복구할 수 있습니다. 연결된 계약·후속 기록은 보존됩니다.'));const panel=calendarPanel;
 try{const rows=await rpc('trash');if(panel!==calendarPanel)return;if(!rows.length)body.append(el('p','복구할 일정이 없습니다.'));for(const row of rows){const line=el('div','','detail-line'),error=feedback(line),restore=button('복구',()=>runButton(restore,error,async()=>{await rpc('archive',{id:row.id,revision:row.revision,restore:true});line.remove();mutate()}));line.prepend(el('p',row.day+' · '+row.title));line.append(restore);body.append(line)}}catch(e){if(panel===calendarPanel)body.append(el('p',e.message,'panel-error'))}
}
function deleteEvent(row){
 const body=createPanel('일정 삭제');body.append(el('p',row.day+' · '+row.title),el('p','달력과 활동 집계에서 제외됩니다. 계약·후속 활동은 보존되며, 30일 동안 개별 복구할 수 있습니다.'));
 const f=el('form');body.append(f);if(row.series_id)field(f,'삭제 범위','scope','one','text',[['one','이번 일정만'],['future','이후 반복 일정까지']]);const error=feedback(f),save=button('일정 삭제 확인',()=>runButton(save,error,async()=>{await rpc('archive',{id:row.id,revision:row.revision,future:values(f).scope==='future'});for(const [k,d] of calendarDrafts)if(d.row?.id===row.id)calendarDrafts.delete(k);mutate();calendarTrash()}),'danger');f.append(save);f.onsubmit=e=>e.preventDefault();
}
function openContract(row,old){
 const key='contract:'+(old?.id||row.id),saved=calendarDrafts.get(key),body=createPanel('청약·계약 입력 및 수정'),f=el('form');body.append(f);
 const draft=calendarDraft=saved||{key,seed:crypto.randomUUID(),dirty:false,values:old||{},row:old};calendarDrafts.set(key,draft);old=draft.row;const v=draft.values;
 field(f,'보험사','insurer',v.insurer||calendarBoot.insurers[0],'text',calendarBoot.insurers);field(f,'보험 구분','category',v.category||'인보험','text',['인보험','일반보험','자동차보험']);field(f,'납입 방식','payment',v.payment||'월납','text',['월납','연납','일시납']);const amount=field(f,'보험료 · 원','amount',v.amount||0,'number');amount.min=1;amount.required=true;
 field(f,'접수일','day',v.day||row.day,'date').required=true;const status=field(f,'청약 상태','status',v.status||'청약 접수','text',['청약 접수','심사 중','성립','철회','미성립']);const effective=field(f,'성립일','effective',v.effective||v.day||row.day,'date');effective.parentElement.hidden=status.value!=='성립';status.onchange=()=>effective.parentElement.hidden=status.value!=='성립';field(f,'상품명 · 선택','product',v.product||'');field(f,'계약 메모 · 선택','note',v.note||'','textarea');
 const error=feedback(f),save=button('청약 저장',()=>{if(!f.reportValidity())return;runButton(save,error,async()=>{draft.values=values(f);await rpc('contract',{event:row.id,id:old?.id,revision:old?.revision,seed:draft.seed,data:draft.values});calendarDrafts.delete(key);if(calendarDraft===draft){calendarDraft=null;openDetail(row.id)}})},'primary');f.append(save);const remember=()=>{draft.values=values(f);draft.dirty=true};f.addEventListener('input',remember);f.addEventListener('change',remember);f.onsubmit=e=>{e.preventDefault();save.click()};
}
// Preserve browser-side drafts when the host is busy. Never intercept auth/logout.
addEventListener('beforeunload',e=>{if(calendarDraft?.dirty){e.preventDefault();e.returnValue=''}});
