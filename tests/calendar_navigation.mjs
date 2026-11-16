// Deterministic, dependency-free client regression tests. No production data.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const source=fs.readFileSync('modules/activity/calendar_view/persistent.js','utf8');
const calendar=fs.readFileSync('modules/activity/calendar_view/index.html','utf8');
const rangeHelpers=calendar.slice(calendar.indexOf('function monthGridStart('),calendar.indexOf('async function weekStartRequest('));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(input=source){
 const requests=[],sent=[],nodes=new Map();
 const node=()=>({textContent:'',hidden:false,children:[],replaceChildren(...children){this.children=children},append(...children){this.children.push(...children)},prepend(){},setAttribute(){},removeAttribute(){}});
 const ctx={console,Map,Set,Date,JSON,Object,Array,Promise,Error,AbortController,DOMException,
 crypto:{randomUUID:()=>String(Math.random())},setTimeout,clearTimeout,queueMicrotask,
 addEventListener:()=>{},document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)},createTextNode:text=>text,querySelectorAll:()=>[]},parent:{},
 configureSync:()=>{},checkSync:()=>{},signalPending:false,context:null,selected:null,
 date:s=>new Date(s+'T00:00:00Z'),add:(d,n)=>new Date(+d+n*86400000),iso:d=>d.toISOString().slice(0,10),
 render:a=>{ctx.latest=a},button:(label,click)=>({label,click}),post:(_,message)=>sent.push(message.value),
 fetch:(url,options)=>new Promise((resolve,reject)=>{
  const req={body:JSON.parse(options.body),signal:options.signal,resolve,reject,aborted:false};requests.push(req);
  options.signal.addEventListener('abort',()=>{req.aborted=true;reject(new DOMException('Aborted','AbortError'))},{once:true});
 })};
 vm.createContext(ctx);vm.runInContext("let prefs={showWeekends:true},monthWeekStart=1,calendarSearchFocus=null;"+rangeHelpers,ctx);vm.runInContext(input,ctx);
 const run=code=>vm.runInContext(code,ctx);
 run("calendarBoot={uid:'me',access:'scope',fast:true,team:true,member:null,members:{me:'Me'}};latest={day:'2026-11-15',mode:'월간',events:[],mobileSession:{url:'https://synthetic.invalid',key:'fake',token:'fake'}}");
 const respond=(req,rows=[],extra={})=>req.resolve({ok:true,json:async()=>({compact:true,rows,branch:[{member:'me',label:'Me'}],unit:'unit',stamp:'v1',versions:{'2026-11-15':'v1'},...extra})});
 const settle=(result={})=>run(`{const q=calendarFlight;clearTimeout(q.timer);calendarFlight=null;q.resolve(${JSON.stringify(result)});sendNext();}`);
 const clear=()=>run('if(calendarFlight)clearTimeout(calendarFlight.timer)');
 return {ctx,run,requests,sent,nodes,respond,settle,clear};
}
const row=(id,day)=>({id,owner:'me',day,kind:'AP',title:id,status:'예정',revision:1,time_pending:true,readable:true});

// Same visible period joins its existing read. A different period cancels it,
// does not turn cancellation into an error, and only the latest range renders.
{
 const h=harness();const first=h.run('reloadCalendar()'),same=h.run('reloadCalendar()');
 assert.equal(h.requests.length,1,'same-period navigation shares one HTTP read');
 const next=h.run("latest.day='2026-12-15';reloadCalendar()");
 assert.equal(h.requests.length,2);assert.equal(h.requests[0].aborted,true,'obsolete period read is aborted');
 h.respond(h.requests[1],[row('december','2026-12-15')]);
 await Promise.all([first,same,next]);
 assert.equal(h.run('latest.events[0].id'),'december');assert.equal(h.run('calendarLoadError'),false);
 assert.equal(h.run('calendarLoads.size'),0,'settled and aborted requests leave no busy marker');
}
// A → B → A must start a fresh A read instead of joining its aborted promise.
{
 const h=harness();const a=h.run('reloadCalendar()');
 const b=h.run("latest.day='2026-12-15';reloadCalendar()");
 const again=h.run("latest.day='2026-11-15';reloadCalendar()");
 assert.equal(h.requests.length,3,'returning to aborted A starts a new read');
 assert(h.requests[0].aborted);assert(h.requests[1].aborted);assert(!h.requests[2].aborted);
 h.respond(h.requests[2],[row('latest-A','2026-11-15')]);await Promise.all([a,b,again]);
 assert.equal(h.run('latest.events[0].id'),'latest-A');assert.equal(h.run('calendarLoadError'),false);
 assert.equal(h.run('calendarLoads.size'),0);assert.equal(h.run('calendarLoadControllers.size'),0);
}
// Confirmed writes must still bypass a previous read of the same period.
{
 const h=harness();const before=h.run('reloadCalendar()');
 const after=h.run('mutate()');assert.equal(h.requests.length,2);
 h.respond(h.requests[1],[row('after-write','2026-11-15')]);await after;await before;
 assert.equal(h.run('latest.events[0].id'),'after-write');assert.equal(h.run('calendarLoadError'),false);
}
// Drag movement uses known day versions and leaves unrelated period caches intact.
// The authoritative changed span can include another user's simultaneous update.
{
 const h=harness();const initial=h.run('reloadCalendar()');
 h.respond(h.requests[0],[row('moving','2026-11-15'),row('untouched','2026-11-20')]);await initial;
 h.run("calendarCache.set('unrelated-period',{events:[{id:'other-month',day:'2027-02-01'}],versions:{'2027-02-01':'v1'}})");
 const moved=h.run("moveCalendarEvent(latest.events.find(e=>e.id==='moving'),'2026-11-16')");
 assert.equal(h.sent.at(-1).value.op,'move');
 h.settle({revision:2});await flush();
 assert.equal(h.run("latest.events.find(e=>e.id==='moving').day"),'2026-11-16','conditional revalidation must not repaint the pre-move cached day');
 assert(h.requests[1].body.p_known,'move refresh retains known versions for incremental response');
 h.respond(h.requests[1],[{...row('moving','2026-11-16'),revision:2},{...row('peer-change','2026-11-16'),owner:'peer'}],{replaceFirst:'2026-11-15',replaceLast:'2026-11-16',versions:{'2026-11-15':'v2','2026-11-16':'v2'}});
 await moved;
 assert.equal(h.run("calendarCache.get('unrelated-period').events[0].id"),'other-month');
 assert.equal(h.run("latest.events.filter(e=>e.id==='moving').length"),1);
 assert.equal(h.run("latest.events.find(e=>e.id==='moving').day"),'2026-11-16');
 assert(h.run("latest.events.some(e=>e.id==='untouched')"));assert(h.run("latest.events.some(e=>e.id==='peer-change')"));
 // An overlapping week may have been loaded after the move; undo must mark it
 // stale too, not just the cache entries that existed at the first movement.
 h.run("calendarCache.set('overlap-week',{rangeStart:'2026-11-09',rangeEnd:'2026-11-29',events:[{id:'moving',day:'2026-11-16'}],versions:{'2026-11-16':'v2'}})");
 const undo=h.nodes.get('move-notice').children.find(child=>child?.label==='되돌리기');
 assert(undo,'existing undo remains available');const undone=undo.click();
 assert.equal(h.run("calendarCache.get('overlap-week').movePending"),true,'undo marks revalidated overlapping cache pending');
 assert.equal(h.sent.at(-1).value.args.day,'2026-11-15');assert.equal(h.sent.at(-1).value.args.revision,2);
 h.settle({revision:3});await flush();assert(h.requests[2].body.p_known,'undo also uses conditional versions');
 h.respond(h.requests[2],[{...row('moving','2026-11-15'),revision:3},{...row('peer-change','2026-11-16'),owner:'peer'}],{replaceFirst:'2026-11-15',replaceLast:'2026-11-16',versions:{'2026-11-15':'v3','2026-11-16':'v3'}});
 await undone;assert.equal(h.run("latest.events.find(e=>e.id==='moving').day"),'2026-11-15');
 assert(h.run("calendarCache.has('unrelated-period')"));h.clear();
}
// Navigation detail requests share identical work, while obsolete queued reads
// are removed without cancelling or reordering writes and ordinary detail reads.
{
 const h=harness();const a=h.run("rpc('detail',{id:'A',lazy_contracts:true},{detailNavigation:true})");
 const same=h.run("rpc('detail',{id:'A',lazy_contracts:true},{detailNavigation:true})");
 assert.equal(h.sent.length,1);assert.equal(h.run('calendarQueue.length'),0,'same detail joins in-flight navigation read');
 h.settle({row:{id:'A'}});assert.equal((await a).row.id,'A');assert.equal((await same).row.id,'A');h.clear();
}
{
 const h=harness();const saving=h.run("rpc('save',{id:'saving'})");
 const old=h.run("rpc('detail',{id:'old'},{detailNavigation:true})").then(()=>false,()=>true);
 const normal=h.run("rpc('detail',{id:'review-refresh'})");
 const nextWrite=h.run("rpc('move',{id:'moving',day:'2026-11-16'})");
 const newest=h.run("rpc('detail',{id:'new'},{detailNavigation:true})");
 assert.equal(await old,true,'obsolete queued navigation read is rejected');
 assert.equal(h.sent.length,1,'active write stays in flight');
 assert.deepEqual(JSON.parse(h.run('JSON.stringify(calendarQueue.map(q=>[q.op,q.args.id]))')),[['detail','review-refresh'],['move','moving'],['detail','new']]);
 h.settle({saved:true});await saving;assert.equal(h.sent.at(-1).value.args.id,'review-refresh');
 h.settle({row:{id:'review-refresh'}});await normal;assert.equal(h.sent.at(-1).value.op,'move');
 h.settle({revision:2});await nextWrite;assert.equal(h.sent.at(-1).value.args.id,'new');
 h.settle({row:{id:'new'}});assert.equal((await newest).row.id,'new');h.clear();
}
// Controlled baseline/current queue benchmark, synthetic data and no network.
async function detailBenchmark(input){
 const h=harness(input);const write=h.run("rpc('save',{id:'saving'})");
 const details=['A','B','C'].map(id=>h.run(`rpc('detail',{id:'${id}'},{detailNavigation:true})`).then(()=>true,()=>false));
 h.settle({saved:true});await write;
 while(h.run('!!calendarFlight'))h.settle({row:{id:'synthetic'}});
 await Promise.all(details);const count=h.sent.filter(q=>q.value.op==='detail').length;h.clear();return count;
}
const baseline=process.env.CALENDAR_BASE_REF?execFileSync('git',['show',process.env.CALENDAR_BASE_REF+':modules/activity/calendar_view/persistent.js'],{encoding:'utf8'}):null;
const detailCounts={beforeDetailReads:baseline?await detailBenchmark(baseline):null,afterDetailReads:await detailBenchmark(source)};
if(baseline)assert.equal(detailCounts.beforeDetailReads,3);assert.equal(detailCounts.afterDetailReads,1);
console.log(JSON.stringify({pass:true,syntheticCounts:{rapidABA:{readsStarted:3,aborted:2,completed:1},threeDetailSelectionsBehindWrite:detailCounts},checks:'same-period sharing / obsolete read abort / final-range render / post-write epoch / move conditional refresh / unrelated cache retention / concurrent day updates / detail coalescing / obsolete queued detail removal / preserved writes and review reads'}));
