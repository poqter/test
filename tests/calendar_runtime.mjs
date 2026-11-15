import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html=fs.readFileSync('modules/activity/calendar_view/index.html','utf8');
const indexSource=html.slice(html.indexOf('function calendarEventIndex'),html.indexOf('function render(a)'));
const indexCtx=vm.createContext({Map});vm.runInContext(indexSource,indexCtx);
let reads=0;
const events=Array.from({length:4200},(_,i)=>({id:i,member:'m'+i%20,kind:i%9?'AP':'휴무',get day(){reads++;return 'd'+i%42}}));
const indexed=indexCtx.calendarEventIndex(events);
assert.equal([...indexed.byDay.values()].flat().length,4200);
for(const rows of indexed.byDay.values())assert(rows.slice(0,rows.findIndex(r=>r.kind!=='휴무')).every(r=>r.kind==='휴무'));
const builtReads=reads;
for(let i=0;i<42;i++)indexed.byDay.get('d'+i);
for(let m=0;m<20;m++)for(let i=0;i<7;i++)indexed.byMemberDay.get('m'+m+'|d'+i);
assert.equal(reads,builtReads,'render lookups must not rescan event dates');
let requests=0,timers=new Map(),tid=0,online;
const ctx=vm.createContext({console,Map,Date,JSON,Math,AbortController,Promise,
 document:{hidden:false,querySelector:()=>({textContent:''})},navigator:{onLine:true},
 calendarBoot:{team:true},calendarLoading:false,calendarFlight:null,calendarLoads:new Map(),signalPending:false,signalTimer:null,
 realtimeReady:true,configureRealtime:()=>{},stopRealtime:()=>{},emit:()=>{},
 setTimeout:f=>{timers.set(++tid,f);return tid},clearTimeout:i=>timers.delete(i),
 addEventListener:(name,fn)=>{if(name==='online')online=fn},fetch:async()=>{requests++;return {ok:true,json:async()=> 'v1'}}});
const sync=html.slice(html.indexOf('let lastSyncStarted='),html.indexOf('let lastFrameHeight='));vm.runInContext(sync,ctx);
vm.runInContext("configureSync({fast:true,syncStamp:'v1',syncUnit:'u',rangeStart:'2026-11-01',rangeEnd:'2026-11-30',mobileSession:{uid:'me',token:'fake',url:'https://synthetic.invalid'}})",ctx);
ctx.calendarLoads.set('current',Promise.resolve());await ctx.checkSync();assert.equal(requests,0);assert(ctx.signalPending);
ctx.calendarLoads.clear();ctx.navigator.onLine=false;await ctx.checkSync();assert.equal(requests,0);assert.equal(timers.size,0);
ctx.navigator.onLine=true;await ctx.checkSync();assert.equal(requests,1);
ctx.document.hidden=true;vm.runInContext('lastSyncStarted=0',ctx);await ctx.checkSync();assert.equal(requests,1);assert.equal(timers.size,0);
console.log(JSON.stringify({pass:true,events:4200,dayReadsDuringIndex:builtReads,dayReadsDuring182Lookups:reads-builtReads,checks:'linear indexing / no duplicate probe during payload / offline stop / online resume / hidden stop'}));
