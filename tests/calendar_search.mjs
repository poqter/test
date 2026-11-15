import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('modules/activity/calendar_view/search.js','utf8');
let calls=[],resolveFetch,denied=false,reauth=0;
const ctx=vm.createContext({Date,JSON,Math,Map,AbortController,setTimeout,clearTimeout,Promise,
 date:s=>new Date(s+'T12:00:00Z'),iso:d=>d.toISOString().slice(0,10),
 calendarBoot:{uid:'me',access:'a',team:false,member:null},latest:{events:[],mobileSession:{url:'https://example.invalid',token:'fake',viewScope:'daily'}},
 calendarPanel:null,calendarMemory:null,calendarCache:new Map(),render:()=>{},calendarAction:()=>reauth++,
 fetch:async(url,opts)=>{calls.push(JSON.parse(opts.body));if(denied)return {ok:false,status:403};return new Promise(r=>resolveFetch=r)}});
vm.runInContext(source,ctx);vm.runInContext('paintCalendarSearch=()=>{}',ctx);
const reset=()=>vm.runInContext("calendarSearch={key:calendarSearchKey(),rows:[],query:'',offset:0,first:'2026-01-01',last:'2026-12-31',busy:false}",ctx);
const query={query:'상담',first:'2026-01-01',last:'2026-12-31'};
assert.equal(ctx.searchMonth('2026-08-31',6),'2027-02-28');
reset();const pending=ctx.searchCalendar(query,false);assert.equal(calls.length,1);
await ctx.searchCalendar(query,false);assert.equal(calls.length,1,'duplicate submit blocked');
ctx.resetCalendarSearch();resolveFetch({ok:true,json:async()=>({rows:[{id:'old'}]})});await pending;
assert.equal(vm.runInContext('calendarSearch',ctx),null,'late scope result discarded');
reset();let p=ctx.searchCalendar(query,false);resolveFetch({ok:true,json:async()=>({rows:[{id:'one'}],hasMore:true})});await p;
p=ctx.searchCalendar(query,true);assert.equal(calls.at(-1).p_offset,1);resolveFetch({ok:true,json:async()=>({rows:[{id:'one'},{id:'two'}],hasMore:false})});await p;
assert.equal(vm.runInContext('calendarSearch.rows.length',ctx),2);assert.equal(vm.runInContext('calendarSearch.offset',ctx),3,'pagination tracks consumed rows, not deduped size');
const before=calls.length;await ctx.searchCalendar({...query,last:'2028-01-01'},false);assert.equal(calls.length,before,'invalid range never hits API');
denied=true;await ctx.searchCalendar(query,false);assert.equal(reauth,1);assert.equal(vm.runInContext('calendarSearch',ctx),null);
console.log('PASS search single flight / literal parameters / stale scope discard / bounded dates / month clamp / pagination / denied purge');
