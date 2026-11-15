/* Search data lives only in this authorized calendar instance, never browser storage. */
let calendarSearch=null,calendarSearchFocus=null,calendarSearchController=null;
function calendarSearchKey(){return JSON.stringify([calendarBoot?.uid,calendarBoot?.access,latest?.mobileSession?.viewScope,calendarBoot?.team,calendarBoot?.member])}
function resetCalendarSearch(){calendarSearchController?.abort();calendarSearchController=null;calendarSearch=null;calendarSearchFocus=null;if(calendarPanel?.dataset.search)calendarPanel.close();}
function searchMonth(day,months){const d=date(day),original=d.getUTCDate();d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()+months);const last=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate();d.setUTCDate(Math.min(original,last));return iso(d)}
function openCalendarSearch(){
 if(!calendarBoot||!latest.mobileSession)return;
 if(!calendarSearch||calendarSearch.key!==calendarSearchKey()){
  resetCalendarSearch();calendarSearch={key:calendarSearchKey(),query:'',first:searchMonth(latest.today,-3),last:searchMonth(latest.today,6),rows:[],hasMore:false,attempted:false,busy:false,error:'',offset:0};
 }
 const state=calendarSearch,body=createPanel('일정 검색',true);calendarPanel.dataset.search='true';
 body.append(el('p',(latest.scopeLabel||'내 일정')+' · 일정명·장소 검색','hint'));
 const form=el('form');form.className='calendar-search-form';
 const query=field(form,'검색어','query',state.query);query.type='search';query.required=true;query.maxLength=100;query.placeholder='일정명 또는 장소';
 const period=el('details');period.append(el('summary','검색 기간'));const dates=el('div','','calendar-search-dates');
 const first=field(dates,'시작일','first',state.first,'date'),last=field(dates,'종료일','last',state.last,'date');first.required=last.required=true;period.append(dates);form.append(period);
 const submit=button('검색',()=>form.requestSubmit(),'primary');submit.type='submit';submit.onclick=null;form.append(submit);body.append(form);
 const status=el('p','','hint');status.setAttribute('role','status');status.dataset.searchStatus='true';body.append(status);
 const results=el('div','','calendar-search-results');body.append(results);
 const inputs=()=>({query:query.value.trim(),first:first.value,last:last.value});
 form.onsubmit=e=>{e.preventDefault();searchCalendar(inputs(),false)};
 body.searchInputs=inputs;paintCalendarSearch();query.focus();
}
function paintCalendarSearch(){
 if(!calendarPanel?.dataset.search||!calendarSearch)return;
 const body=calendarPanel.querySelector('.panel-content'),state=calendarSearch,status=body.querySelector('[data-search-status]'),results=body.querySelector('.calendar-search-results');
 body.querySelector('button[type=submit]').disabled=state.busy;
 status.textContent=state.busy?'검색 중…':state.error||(!state.attempted?'검색어를 입력하고 검색을 눌러 주세요.':state.rows.length?`${state.first} ~ ${state.last} · ${state.rows.length}건${state.hasMore?' 이상':''}`:'검색 결과가 없습니다.');
 results.replaceChildren();
 for(const row of state.rows){
  const b=button('',()=>jumpToSearchEvent(row),'calendar-search-result');b.disabled=state.busy;
  b.append(el('strong',row.title||row.kind),el('span',`${row.day} · ${row.start_time?row.start_time.slice(0,5):row.time_pending?'시간 미정':'종일'}${calendarBoot.team||calendarBoot.member?' · '+(row.owner_label||calendarBoot.people[row.owner]||'구성원'):''}`));
  if(row.place)b.append(el('small',row.place));results.append(b);
 }
 if(state.error)results.append(button('다시 검색',()=>searchCalendar(body.searchInputs(),false)));
 if(state.hasMore){const more=button('20건 더 보기',()=>searchCalendar(body.searchInputs(),true));more.disabled=state.busy;results.append(more)}
}
async function searchCalendar(input,more){
 const state=calendarSearch;if(!state||state.busy)return;
 if(!input.query||input.query.length>100||!input.first||!input.last||date(input.last)<date(input.first)||(date(input.last)-date(input.first))/86400000>365){state.error='검색어와 기간을 확인해 주세요. 검색 기간은 최대 1년입니다.';paintCalendarSearch();return}
 more=more&&state.query===input.query&&state.first===input.first&&state.last===input.last;
 if(!more){state.rows=[];state.hasMore=false;state.offset=0;}
 Object.assign(state,input,{busy:true,error:'',attempted:true});paintCalendarSearch();
 const controller=calendarSearchController=new AbortController(),timer=setTimeout(()=>controller.abort(),15000),session=latest.mobileSession;
 try{
  const response=await fetch(session.url+'/rest/v1/rpc/sales_calendar_search',{method:'POST',headers:{apikey:session.key,Authorization:'Bearer '+session.token,'Content-Type':'application/json','X-Hwarang-View-Scope':session.viewScope||'daily'},body:JSON.stringify({p_query:state.query,first_day:state.first,last_day:state.last,p_team:!!calendarBoot.team,p_member:calendarBoot.member||null,p_offset:more?state.offset:0}),signal:controller.signal});
  if(state!==calendarSearch||state.key!==calendarSearchKey())return;
  if(!response.ok){if(response.status===401||response.status===403){resetCalendarSearch();calendarPanel?.close();calendarCache.clear();if(calendarMemory)calendarMemory.cache=new Map();latest={...latest,events:[],roster:{}};render(latest);calendarAction('reauth');return}throw Error('검색하지 못했습니다. 다시 시도해 주세요.');}
  const data=await response.json();if(state!==calendarSearch||state.key!==calendarSearchKey())return;
  state.rows=more?[...state.rows,...data.rows.filter(r=>!state.rows.some(old=>old.id===r.id))]:data.rows;state.offset=(more?state.offset:0)+data.rows.length;state.hasMore=!!data.hasMore;
 }catch{if(state===calendarSearch)state.error='검색하지 못했습니다. 연결을 확인하고 다시 시도해 주세요.';}
 finally{clearTimeout(timer);if(calendarSearchController===controller)calendarSearchController=null;if(state===calendarSearch){state.busy=false;paintCalendarSearch();}}
}
async function jumpToSearchEvent(row){
 const state=calendarSearch;if(!state||state.busy)return;
 state.busy=true;paintCalendarSearch();const key=state.key,panel=calendarPanel;
 calendarSearchFocus={id:row.id,day:row.day};latest={...latest,day:row.day};selected=row.day;context=latest.mode+row.day;selectedByUser=null;
 await reloadCalendar(true);
 if(state!==calendarSearch||key!==calendarSearchKey())return;
 state.busy=false;
 if(calendarPanel!==panel||!panel.open)return;
 if(calendarLoadError){state.error='해당 날짜를 불러오지 못했습니다. 다시 시도해 주세요.';paintCalendarSearch();return}
 const found=latest.events.find(e=>e.id===row.id&&e.day===row.day);
 if(!found){calendarSearchFocus=null;state.rows=state.rows.filter(e=>e.id!==row.id);state.error='일정이 변경·삭제됐거나 조회 권한이 달라졌습니다. 다시 검색해 주세요.';paintCalendarSearch();return}
 openDayList(row.day);
 requestAnimationFrame(()=>{const target=calendarPanel?.querySelector('.calendar-search-highlight');target?.scrollIntoView({block:'nearest'});target?.querySelector('button')?.focus({preventScroll:true});});
}
