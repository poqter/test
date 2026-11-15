import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('modules/activity/calendar_view/sync.js','utf8');
let listeners=[],clients=0,checks=0,channels=0,timers=new Map(),id=0;
const context={console,JSON,Set,Object,document:{hidden:false},parentVisible:true,syncTimer:null,syncConfig:null,
 calendarBoot:{access:JSON.stringify({me:{unit:'a'},peer:{unit:'b'},other:{unit:'b'}})},
 calendarCache:new Map(),calendarAction:()=>{},checkSync:()=>checks++,scheduleSync:()=>{},addEventListener:()=>{},
 setTimeout:f=>{timers.set(++id,f);return id},clearTimeout:i=>timers.delete(i),
 HwarangRealtime:{RealtimeClient:class{
 constructor(){clients++}channel(){channels++;return {on(t,filter,callback){listeners.push({filter,callback});return this},subscribe(f){f('SUBSCRIBED');return this}}}
 setAuth(){return Promise.resolve()}removeAllChannels(){return Promise.resolve()}disconnect(){}
 }}};
vm.createContext(context);vm.runInContext(source,context);
const config={fast:true,syncStamp:'v1',syncUnit:'a',mobileSession:{url:'https://example.invalid',uid:'me',token:'fake',viewScope:'{"position":"division_head"}'}};
context.syncConfig=config;context.configureRealtime(config);
assert.deepEqual(listeners.filter(x=>x.filter.table==='sales_calendar_signals').map(x=>x.filter.filter),['unit=eq.a','unit=eq.b']);
assert.equal(channels,1,'multiple units share one websocket channel');
const b=listeners.find(x=>x.filter.filter==='unit=eq.b');
for(let i=0;i<100;i++)b.callback();assert.equal(timers.size,1,'burst batches to one probe');
for(const f of timers.values())f();timers.clear();assert.equal(checks,2);
context.configureRealtime(config);assert.equal(clients,1,'same scope reuses client');
listeners=[];context.configureRealtime({...config,mobileSession:{...config.mobileSession,viewScope:'daily'}});
assert.deepEqual(listeners.filter(x=>x.filter.table==='sales_calendar_signals').map(x=>x.filter.filter),['unit=eq.a']);
context.document.hidden=true;context.configureRealtime(config);assert.equal(timers.size,0);
console.log('PASS multi-unit filters / dedup / single channel / reuse / scope reduction / burst100 -> 1 probe / hidden stop');
