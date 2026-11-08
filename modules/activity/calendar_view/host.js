/* Keep the real calendar iframe mounted across workspace navigation. No data is
 * fetched on home; a delegated click reveals its already-rendered date grid. */
let workspaceHost=null,calendarAccessPending=false,workspaceHostTick=null;
function receiveHost(a){
 if(!a.hosted)return;
 if(a.hostTick&&workspaceHostTick===a.hostTick)return false;
 workspaceHostTick=a.hostTick;
 if(!workspaceHost){
  const d=parent.document,frame=window.frameElement,host=frame.closest('.st-key-sales_calendar_host');
  if(!host)return;
  const style=d.createElement('style');style.textContent='.hw-calendar-opening .st-key-hw_workspace_body{visibility:hidden!important}.st-key-sales_calendar_host{position:fixed!important;z-index:20;background:#f5f7fa;margin:0!important}.st-key-sales_calendar_host[hidden]{display:none!important}';d.head.append(style);
  let opening=false,active=false,uid=a.hostUid,disposed=false,scheduled=false;
  const layout=()=>{
   scheduled=false;if(disposed)return;
   if(!frame.isConnected){dispose();return;}
   const anchor=active?d.getElementById('sales-calendar-anchor'):null;
   if(!opening&&!active){host.hidden=true;return;}
   const target=anchor||d.querySelector('.st-key-hw_workspace_body');if(!target)return;
   const rect=target.getBoundingClientRect();
   const top=anchor?rect.top:Math.max(12,rect.top),height=Math.max(420,Math.min(900,parent.innerHeight-top-24));
   host.hidden=false;host.style.left=rect.left+'px';host.style.top=top+'px';host.style.width=rect.width+'px';
   if(anchor){anchor.style.height=height+'px';opening=false;d.documentElement.classList.remove('hw-calendar-opening');}
   if(lastFrameHeight!==height){frameViewport='';lastFrameHeight=height;fitCalendar();}
  };
  const schedule=()=>{if(!scheduled){scheduled=true;parent.requestAnimationFrame(layout)}};
  const suspend=()=>{active=false;opening=false;host.hidden=true;d.documentElement.classList.remove('hw-calendar-opening');parentVisible=false;stopRealtime();calendarEpoch++;calendarSeq++;};
  const clear=()=>{suspend();calendarCache.clear();calendarDrafts.clear();calendarMemory=null;calendarBoot=null;syncConfig=null;dismissCloseConfirm();calendarPanel?.remove();calendarPanel=null;calendarDraft=null;latest=null;lastRender=null;context=null;try{delete parent.__hwarangCalendarMemory}catch{}showCalendarShell(a.hostToday,uid);};
  const click=e=>{
   const b=e.target.closest('button');if(!b)return;
   const entry=b.closest('.st-key-brand_tile_sales,.st-key-hw_sidebar_sales');
   if(entry){
    if(active)return;
    opening=true;calendarAccessPending=true;parentVisible=false;stopRealtime();calendarEpoch++;calendarSeq++;
    // Retain the same grid nodes, but do not expose cached private data before
    // server access validation on reentry.
    calendarLoading=true;calendarLoadError=false;
    if(latest)render({...latest,events:[],roster:{},syncUnit:null});
    d.documentElement.classList.add('hw-calendar-opening');layout();return;
   }
   const leaving=b.closest('[class*="st-key-v2_nav_"],.st-key-hw_sidebar_briefing,.st-key-hw_sidebar_analyzer,.st-key-wb_home,.st-key-hw_open_admin_center,.st-key-v2_logout')||b.getAttribute('role')==='tab';
   if(leaving){
    if(calendarPanel?.open){e.preventDefault();e.stopImmediatePropagation();closePanel();return;}
    if(b.closest('.st-key-v2_logout')){clear();return;}
    suspend();
   }
  };
  const observer=new MutationObserver(schedule);observer.observe(d.body,{childList:true,subtree:true});
  d.addEventListener('click',click,true);d.addEventListener('scroll',schedule,true);parent.addEventListener('resize',schedule);
  function dispose(){if(disposed)return;disposed=true;observer.disconnect();d.removeEventListener('click',click,true);d.removeEventListener('scroll',schedule,true);parent.removeEventListener('resize',schedule);style.remove();d.documentElement.classList.remove('hw-calendar-opening');stopRealtime();try{delete parent.__hwarangCalendarMemory}catch{}}
  workspaceHost={update(args){
   if(uid!==args.hostUid){clear();uid=args.hostUid;}
   const entering=!!args.hostActive&&!active;
   active=!!args.hostActive;opening=false;parentVisible=active&&!d.hidden;calendarAccessPending=active&&!args.boot;
   d.documentElement.classList.remove('hw-calendar-opening');
   if(!active)suspend();
   layout();return entering;
  },pending:()=>opening,dispose};
  showCalendarShell(a.hostToday,a.hostUid);
 }
 const entering=workspaceHost.update(a);
 if(a.hostError){
  calendarLoading=false;calendarLoadError=true;
  if(latest)render({...latest,events:[],roster:{},syncUnit:null});
  calendarStatus('일정을 불러오지 못했습니다. 다시 시도해 주세요.');
 }
 return entering;
}
function showCalendarShell(today,uid){
 if(latest)return;
 calendarLoading=true;
 render({day:today,today,mode:'월간',events:[],roster:{},scopeLabel:'내 일정',mobileSession:{uid},syncUnit:null});
 calendarStatus('일정을 불러오는 중…');
}
