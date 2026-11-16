import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const current=fs.readFileSync('modules/activity/calendar_view/persistent.js','utf8');
const calendar=fs.readFileSync('modules/activity/calendar_view/index.html','utf8');
const rangeHelpers=calendar.slice(calendar.indexOf('function monthGridStart('),calendar.indexOf('async function weekStartRequest('));
const before=process.env.CALENDAR_BASE_REF?execFileSync('git',['show',process.env.CALENDAR_BASE_REF+':modules/activity/calendar_view/persistent.js'],{encoding:'utf8'}):null;
function harness(source){
 let revision=1,requests=[],deny=false;
 const entry=(revision)=>({id:'event',owner:'me',day:'2026-11-15',kind:'AP',title:'Version '+revision,status:'예정',common:false,time_pending:true});
 const ctx={console,Map,Set,Date,JSON,Object,Array,Promise,Error,AbortController,setTimeout,clearTimeout,addEventListener:()=>{},
 document:{getElementById:()=>({textContent:''})},parent:{},configureSync:()=>{},checkSync:()=>{},signalPending:false,context:null,selected:null,
 date:s=>new Date(s+'T00:00:00Z'),add:(d,n)=>new Date(+d+n*86400000),iso:d=>d.toISOString().slice(0,10),
 render:a=>{ctx.latest=a},fetch:async(url,options)=>{
  const sentRevision=revision;
  requests.push({url,body:JSON.parse(options.body)});
  await new Promise(r=>setTimeout(r,20));
  if(deny)return {ok:false,status:403};
  const data={rows:[entry(sentRevision)],summary:[entry(sentRevision)],branch:[{member:'me',label:'Me'}],unit:'unit',stamp:'v'+sentRevision};
  if(url.endsWith('sales_calendar_stamp'))return {ok:true,json:async()=>data.stamp};
  if((url.endsWith('sales_calendar_changes')||url.endsWith('sales_calendar_compact'))){
   const known=JSON.parse(options.body).p_known;
   Object.assign(data,{versions:{'2026-11-15':'v'+sentRevision},replaceFirst:known?'2026-11-15':'2026-10-26',replaceLast:known?'2026-11-15':'2026-12-06'});
   if(known?.['2026-11-15']==='v'+sentRevision)return {ok:true,json:async()=>({unchanged:true,versions:data.versions,stamp:data.stamp})};
  }
  return {ok:true,json:async()=>data};
 }};
 vm.createContext(ctx);
 vm.runInContext("let prefs={showWeekends:true},monthWeekStart=1,calendarSearchFocus=null;"+rangeHelpers,ctx);
 vm.runInContext(source,ctx);
 vm.runInContext("calendarBoot={uid:'me',access:'scope',fast:true,team:true,member:null,members:{me:'Me'}};latest={day:'2026-11-15',mode:'월간',events:[],mobileSession:{url:'https://synthetic.invalid',key:'fake',token:'fake'}}",ctx);
 return {ctx,run:code=>vm.runInContext(code,ctx),requests,bump:()=>revision++,deny:()=>deny=true};
}
const median=values=>[...values].sort((a,b)=>a-b)[Math.floor(values.length/2)];
async function bench(source){
 const h=harness(source),samples=[],counts=[];
 await h.run('reloadCalendar()');
 for(let i=0;i<7;i++){h.bump();const count=h.requests.length,t=performance.now();await h.run('reloadCalendar()');samples.push(performance.now()-t);counts.push(h.requests.length-count);}
 return {medianMs:Math.round(median(samples)),rangeMs:[Math.round(Math.min(...samples)),Math.round(Math.max(...samples))],requests:counts};
}
const old=before?await bench(before):null,now=await bench(current);
if(old)assert(old.requests.every(n=>n===2));assert(now.requests.every(n=>n===1));
const racing=harness(current);const pending=racing.run('reloadCalendar()');racing.bump();const saved=racing.run('mutate()');await Promise.all([pending,saved]);assert.equal(racing.requests.length,2,'write must bypass an in-flight pre-write read');assert.match(racing.run("latest.events[0].short"),/Version 2/);
const staleDenied=harness(current);const normalFetch=staleDenied.ctx.fetch;let calls=0;
staleDenied.ctx.fetch=async(...args)=>{if(++calls===1){await new Promise(r=>setTimeout(r,50));return {ok:false,status:403};}return normalFetch(...args);};
const deniedOld=staleDenied.run('reloadCalendar()');staleDenied.run('calendarEpoch++');await staleDenied.run('reloadCalendar()');await deniedOld;assert.equal(staleDenied.run('latest.events.length'),1,'obsolete denial must not erase a newer authorized view');
const h=harness(current);
await h.run('Promise.all([reloadCalendar(),reloadCalendar(),reloadCalendar()])');assert.equal(h.requests.length,1,'same concurrent request shared');
h.run("latest.events.push({id:'keep',day:'2026-11-16',short:'Unchanged'})");
h.bump();await h.run('mutate()');assert.equal(h.run("latest.events.find(e=>e.id==='keep').short"),'Unchanged');assert.match(h.run("latest.events.find(e=>e.id==='event').short"),/Version 2/);
assert.equal(h.run('calendarCache.size'),1,'save retains validated range cache');
h.run("calendarBoot.team=false");await h.run('reloadCalendar()');assert.equal(h.run('calendarCache.size'),2);
h.run("calendarBoot.team=true");await h.run('reloadCalendar()');assert(h.requests.at(-1).body.p_known,'scope return reuses its own versions');
h.deny();await h.run('reloadCalendar()');assert.equal(h.run('calendarCache.size'),0);assert.equal(h.run('latest.events.length'),0);assert.equal(h.run('calendarLoadError'),true);
console.log(JSON.stringify({pass:true,condition:'7 repeats; synthetic 20ms per HTTP request; changed cached range',before:old,after:now,checks:'single-flight / day merge / retained cache / scope-separated reuse / denied cache purge'}));
