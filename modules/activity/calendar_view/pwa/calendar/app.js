'use strict';
const $=id=>document.getElementById(id),f=$('form').elements;
const dstr=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
const today=()=>new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Seoul'}));
let cursor=today(),session,people={},rows=[],requestNo=0,draft,installPrompt;
const sessionKey='hwarang.calendar.session',draftKey=()=> 'hwarang.calendar.draft.'+session.uid;
function button(label,fn,cls){const b=document.createElement('button');b.textContent=label;b.type='button';b.className=cls||'';b.onclick=e=>{e.stopPropagation();fn()};return b}
function gate(){session=null;$('logout').hidden=true;$('summary').hidden=true;$('empty').hidden=true;sessionStorage.removeItem(sessionKey);$('gate').hidden=false;$('grid').replaceChildren();$('restore').hidden=true}
async function api(path,method='GET',body,prefer){const res=await fetch(session.url+'/rest/v1/'+path,{method,headers:{apikey:session.key,Authorization:'Bearer '+session.token,'Content-Type':'application/json',Prefer:prefer||'return=representation'},body:body?JSON.stringify(body):undefined});if(!res.ok){if(res.status===401){gate();throw Error('로그인이 만료되었습니다. WORKSPACE에서 다시 연결해 주세요.')}throw Error('처리하지 못했습니다. 입력 내용과 연결을 확인하고 다시 시도해 주세요.')}let t=await res.text();return t?JSON.parse(t):null}
async function statusToday(){
 if(!session)return;const day=dstr(today());
 const [members,events,confirmed]=await Promise.all([api('rpc/sales_members','POST',{}),api('rpc/sales_calendar_days','POST',{first_day:day,last_day:day}),api('sales_empty_days?select=owner&day=eq.'+day)]);
 const checked=new Set(confirmed.map(r=>r.owner));
 function state(u){const mine=events.filter(r=>!r.common&&(r.owner===u||r.companion===u)),active=mine.filter(r=>!['취소','연기'].includes(r.status));if(active.some(r=>r.kind!=='휴무'||r.start_time))return '일정 있음';if(active.length)return '휴무';if(checked.has(u))return '일정 없음';if(mine.length&&mine.every(r=>r.status==='취소'))return '모두 취소';return '미등록'}
 const groups={};for(const member of members.filter(r=>r.managed&&people[r.member])){const k=state(member.member);(groups[k]??=[]).push(member.label)}
 $('summary').hidden=!Object.keys(groups).length;$('summaryTitle').textContent=(session.branch?'오늘의 지점':'오늘의 조직')+' · 미등록 '+(groups['미등록']||[]).length+'명 · 일정 없음 '+(groups['일정 없음']||[]).length+'명';$('summaryList').replaceChildren();for(const [k,v] of Object.entries(groups)){const line=document.createElement('div');line.textContent=k+' · '+v.join(', ');$('summaryList').append(line)}
 $('empty').hidden=!['일정 없음','미등록','모두 취소'].includes(state(session.uid));$('empty').textContent=checked.has(session.uid)?'오늘 일정 없음 · 되돌리기':'오늘 일정 없음';$('empty').onclick=async()=>{try{if(checked.has(session.uid))await api('sales_empty_days?owner=eq.'+session.uid+'&day=eq.'+day,'DELETE');else await api('sales_empty_days','POST',{day},'resolution=ignore-duplicates,return=minimal');await statusToday()}catch(e){$('msg').textContent=e.message}};
}

function option(value,label){return new Option(label,value)}
function label(r){return r.title||[people[r.owner],r.kind].filter(Boolean).join(' · ')}
function showList(day,items){$('agenda').replaceChildren();$('listTitle').textContent=day+' · '+items.length+'건';items.forEach(r=>$('agenda').append(button((r.start_time?.slice(0,5)||(r.time_pending?'시간 미정':'종일'))+' · '+label(r)+(r.companion?' · 동행 '+(people[r.companion]||''):'')+' · '+r.status,()=>{if(r.owner===session.uid){$('list').close();openForm(day,r)}})));$('agenda').append(button('이 날짜에 일정 등록',()=>{$('list').close();openForm(day)}));$('list').showModal()}
function render(){const y=cursor.getFullYear(),m=cursor.getMonth(),first=new Date(y,m,1),offset=(first.getDay()+6)%7;
 $('month').textContent=y+'년 '+(m+1)+'월';const grid=$('grid');grid.replaceChildren();const n=Math.ceil((offset+new Date(y,m+1,0).getDate())/7)*7;
 for(let i=0;i<n;i++){let date=new Date(y,m,1-offset+i),day=dstr(date),box=document.createElement('div');box.className='cell'+(date.getMonth()===m?'':' muted');box.onclick=()=>openForm(day);box.append(button(date.getDate(),()=>openForm(day),'date'+(day===dstr(today())?' today':'')));let items=rows.filter(r=>r.day===day&&($('scope').value==='branch'||r.owner===session.uid||r.companion===session.uid||r.common));items.slice(0,2).forEach(r=>box.append(button(label(r),()=>r.owner===session.uid?openForm(day,r):showList(day,[r]),'event '+r.kind)));if(items.length>2)box.append(button('+'+(items.length-2)+'건',()=>showList(day,items),'more'));grid.append(box)}}
async function load(){if(!session)return;const seq=++requestNo,y=cursor.getFullYear(),m=cursor.getMonth(),a=dstr(new Date(y,m,1)),b=dstr(new Date(y,m+1,0));
 try{const [summary,own]=await Promise.all([api('rpc/sales_calendar_days','POST',{first_day:a,last_day:b}),api('sales_events?deleted_at=is.null&owner=eq.'+session.uid+'&day=gte.'+a+'&day=lte.'+b)]);if(seq!==requestNo)return;let byId=new Map(own.map(r=>[r.id,r]));rows=summary.map(r=>byId.get(r.id)||r).sort((a,b)=>(a.start_time||'').localeCompare(b.start_time||''));render();await statusToday();$('msg').textContent=''}catch(e){$('msg').textContent=e.message}}
function remember(){if(!draft||!session)return;draft.values=Object.fromEntries(new FormData($('form')));localStorage.setItem(draftKey(),JSON.stringify(draft));$('restore').hidden=false}
function openForm(day,row,restore=false){if(!session)return;let old=localStorage.getItem(draftKey());if(!restore&&old&& !confirm('작성 중인 내용이 있습니다. 새로 작성할까요?'))return;
 draft=restore?JSON.parse(old):{id:row?.id||crypto.randomUUID(),revision:row?.revision,series:row?.series_id,manual:!!row,values:{day,title:row?.title||'',kind:row?.kind||'미분류',timing:row?.start_time?'시간 지정':row&&!row.time_pending?'종일':'시간 미정',start:row?.start_time?.slice(0,5)||'',end:row?.end_time?.slice(0,5)||'',companion:row?.companion||'',place:row?.place||'',note:row?.note||'',status:row?.status||'예정'}};
 for(const [k,v] of Object.entries(draft.values))if(f[k])f[k].value=v;
 $('deleteEvent').hidden=!draft.revision;$('times').hidden=f.timing.value!=='시간 지정';$('heading').textContent=draft.revision?'내 일정 수정':'내 일정에 등록';$('error').textContent='';$('sheet').showModal();f.title.focus()}
$('form').oninput=()=>{if(!draft.manual){const matches=[...new Set((f.title.value.toUpperCase().match(/(?<![A-Z0-9])(TA|AP|PC|CS)(?![A-Z0-9])/g)||[]))];f.kind.value=matches.length===1?matches[0]:'미분류'}remember()};
f.kind.oninput=e=>{e.stopPropagation();draft.manual=true;if(f.kind.value==='휴무'){f.timing.value='종일';if(!f.title.value.trim())f.title.value='휴무';$('times').hidden=true}remember()};
f.timing.onchange=()=>$('times').hidden=f.timing.value!=='시간 지정';
$('form').onsubmit=async e=>{e.preventDefault();remember();let timed=f.timing.value==='시간 지정';if(timed&&(!f.start.value||(f.end.value&&f.end.value<=f.start.value))){$('error').textContent='시작·종료 시간을 확인해 주세요.';return}
 const body={day:f.day.value,title:f.title.value.trim(),kind:f.kind.value,status:f.status.value,companion:f.companion.value||null,place:f.place.value,note:f.note.value,time_pending:f.timing.value==='시간 미정',start_time:timed?f.start.value:null,end_time:timed?(f.end.value||null):null};if(!body.title)return;
 $('save').disabled=true;$('save').textContent='저장 중';try{if(draft.revision){const saved=await api('sales_events?id=eq.'+draft.id+'&revision=eq.'+draft.revision,'PATCH',body);if(!saved.length)throw Error('다른 화면에서 먼저 변경했습니다. 최신 일정을 다시 열어 주세요.')}else await api('sales_events','POST',{...body,unit:session.unit,id:draft.id},'resolution=ignore-duplicates,return=minimal');
 localStorage.removeItem(draftKey());$('restore').hidden=true;draft=null;$('sheet').close();cursor=new Date(body.day+'T12:00:00');await load()}catch(err){$('error').textContent=err.message}finally{$('save').disabled=false;$('save').textContent='저장'}};
$('restore').onclick=()=>openForm(null,null,true);$('close').onclick=()=>$('sheet').close();$('hideList').onclick=()=>$('list').close();
$('prev').onclick=()=>{cursor=new Date(cursor.getFullYear(),cursor.getMonth()-1,1);load()};$('next').onclick=()=>{cursor=new Date(cursor.getFullYear(),cursor.getMonth()+1,1);load()};$('now').onclick=()=>{cursor=today();load()};$('scope').onchange=render;
for(const k of ['미분류','TA','AP','PC','CS','청약','교육','회의','휴무','기타'])f.kind.add(option(k,k));
for(const w of '월화수목금토일'){const s=document.createElement('span');s.textContent=w;$('weekdays').append(s)}
async function start(s){session=s;$('logout').hidden=false;sessionStorage.setItem(sessionKey,JSON.stringify(s));$('gate').hidden=true;$('scope').value=s.branch?'branch':'my';try{const members=await api('rpc/sales_branch_members','POST',{});if(!members.some(m=>m.member===s.uid)){gate();return}people=Object.fromEntries(members.map(m=>[m.member,m.label]));f.companion.replaceChildren(option('','선택 안 함'));for(const [u,n] of Object.entries(people))if(u!==s.uid)f.companion.add(option(u,n));$('restore').hidden=!localStorage.getItem(draftKey());await load()}catch(e){$('msg').textContent=e.message}}
const root='https://zaynrfzzrtuiherbhoee.supabase.co',publicKey='sb_publishable_NdoOryxAxzTedYSewD0GGA_lHiOG2bx';
const embedded = window.parent !== window;
function host(type, data={}) { parent.postMessage({isStreamlitMessage:true,type,...data},location.origin); }
if(embedded){
 let current;
 addEventListener('message',e=>{
  if(e.source!==parent || e.origin!==location.origin || e.data?.type!=='streamlit:render')return;
  const account=e.data.args?.account;
  if(account?.url?.replace(/\/$/,'')!==root || !account.token)return;
  if(current!==account.token){current=account.token;start(account)}
  host('streamlit:setFrameHeight',{height:Math.max(520,window.parent.innerHeight-60)});
 });
 host('streamlit:componentReady',{apiVersion:1});
}else{
 const saved=sessionStorage.getItem(sessionKey);
 if(saved)start(JSON.parse(saved));else gate();
}
addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('install').hidden=false});$('install').onclick=()=>installPrompt?.prompt();
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{});

$('logout').onclick=async()=>{if(embedded){gate();host('streamlit:setComponentValue',{value:'logout',dataType:'json'});return}if(session)await fetch(session.url+'/auth/v1/logout?scope=local',{method:'POST',headers:{apikey:session.key,Authorization:'Bearer '+session.token}}).catch(()=>{});gate()};
if(window.opener){
 const source=window.opener;
 const receive=e=>{if(e.source===source&&e.origin===location.origin&&e.data?.type==='hwarang.calendar.session'&&e.data.session?.url?.replace(/\/$/,'')===root){removeEventListener('message',receive);window.opener=null;start(e.data.session)}};
 addEventListener('message',receive);source.postMessage({type:'hwarang.calendar.ready'},location.origin);
}

$('deleteEvent').onclick=async()=>{
 if(!draft?.revision||!session)return;
 let future=false;
 if(draft.series)future=confirm('이후 반복 일정도 함께 삭제할까요? 취소를 누르면 이번 일정만 선택합니다.');
 if(!confirm(f.day.value+' · '+f.title.value+'\n'+(future?'이후 반복 일정까지':'이번 일정만')+' 삭제합니다. 즉시 삭제되며 복구할 수 없습니다. 연결된 계약·후속 활동은 보존됩니다.'))return;
 $('deleteEvent').disabled=true;
 try{
 await api('rpc/sales_delete_event','POST',{p_id:draft.id,p_revision:draft.revision,p_future:future});
 localStorage.removeItem(draftKey());draft=null;$('restore').hidden=true;$('sheet').close();await load();
 }catch(e){$('error').textContent=e.message}finally{$('deleteEvent').disabled=false}
};
