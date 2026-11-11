import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('modules/activity/activity_monitor/index.html','utf8').split('<body><script>')[1].split('</script>')[0];
let now=100000,seq=0,timers=new Map(),handlers={},parentHandlers={},fetches=0,version='a',posts=[],callback,subscription;
const document={hidden:false};let input=false,dialog=false;
const parent={document:{querySelector:()=>dialog, get activeElement(){return {matches:()=>input}},addEventListener:(t,f)=>parentHandlers[t]=f},postMessage:m=>posts.push(m)};
const context={document,parent,location:{origin:'https://app.test'},crypto:{randomUUID:()=>String(++seq)},Date:{now:()=>now},Math:{random:()=>0,min:Math.min},AbortController,Error,JSON,console,
 setTimeout:(f,delay)=>{const id=++seq;timers.set(id,{f,at:now+delay});return id},clearTimeout:id=>timers.delete(id),addEventListener:(t,f)=>handlers[t]=f,
 fetch:async()=>{fetches++;return {ok:true,json:async()=>version}},
 HwarangRealtime:{RealtimeClient:class{channel(){return {on(t,filter,f){callback=f;return this},subscribe(f){subscription=f}}}removeAllChannels(){return Promise.resolve()}disconnect(){}}}};
context.window=context;vm.createContext(context);vm.runInContext(source,context);
const tick=async ms=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();now+=ms;for(let i=0;i<10;i++){const ready=[...timers].filter(([id,t])=>t.at<=now);if(!ready.length)break;for(const[id,t]of ready){timers.delete(id);await t.f()}await Promise.resolve()}};
handlers.message({source:parent,origin:'https://app.test',data:{type:'streamlit:render',args:{uid:'one',viewScope:'daily',first:'2026-11-01',last:'2026-11-30',owner:'one',stamp:'a',url:'https://db.test'}}});
subscription('SUBSCRIBED');await tick(0);assert.equal(fetches,1);
for(let i=0;i<100;i++)callback({new:{owner:'one',topic:'sales_reports',day:'2026-11-04'}});
await tick(500);assert.equal(fetches,1);await tick(1500);assert.equal(fetches,2);assert.equal(posts.filter(p=>p.type==='streamlit:setComponentValue').length,0);
input=true;version='b';callback({new:{owner:'one',topic:'sales_reports',day:'2026-11-04'}});await tick(2000);await tick(2000);
assert.equal(posts.filter(p=>p.type==='streamlit:setComponentValue').length,0);
input=false;parentHandlers.focusout();await tick(250);assert.equal(posts.filter(p=>p.type==='streamlit:setComponentValue').length,1);
document.hidden=true;handlers.visibilitychange();const before=fetches;await tick(600000);assert.equal(fetches,before);
document.hidden=false;handlers.visibilitychange();await tick(0);assert.ok(fetches>before);
input=true;version='c';callback({new:{owner:'one',topic:'scope',day:'1900-01-01'}});await tick(2000);await tick(2000);
assert.equal(posts.filter(p=>p.type==='streamlit:setComponentValue').at(-1).value.scope,true);
console.log('PASS burst100 coalescing, minimum2sec, unchanged-no-rerun, focused-input defer, hidden pause, resume-check, scope revoke');
