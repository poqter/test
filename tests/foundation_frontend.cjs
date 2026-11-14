const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fake=()=>({innerHTML:'',querySelectorAll:()=>[],querySelector:()=>null});const main=fake(),nav=fake(),root={querySelector:s=>s==='main'?main:nav},save={},refresh={},message={};let receive,click,posts=[];
const parent={postMessage:x=>posts.push(x)};
const ctx={document:{getElementById:id=>({'save':save,'refresh':refresh,'servermsg':message}[id]||root),addEventListener:(t,fn)=>{click=fn},documentElement:{scrollHeight:1000}},parent,window:{addEventListener:(t,fn)=>{receive=fn}},queueMicrotask:fn=>fn(),crypto:{randomUUID:()=>String(posts.length)},ResizeObserver:class{observe(){}}};vm.createContext(ctx);
const html=fs.readFileSync('hwarang_academy/education/interactive_frontend/index.html','utf8');const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
scripts[2]=scripts[2].replace('root.showHome();\n})();','root.test={D,M,go,set:(p,t)=>{pick=p;transfer=t}};root.showHome();\n})();');
scripts.forEach(s=>vm.runInContext(s,ctx));vm.runInContext(fs.readFileSync('hwarang_academy/education/interactive_frontend/bridge.js','utf8'),ctx);
const render=(args)=>receive({source:parent,data:{type:'streamlit:render',args}});render({rows:[],ack:null});
const {D,M,go}=root.test;
for(const k of Object.keys(D)){const i=Number(k),d=D[k];root.openCore(i);go('nextConcept');go('nextConcept');go('nextConcept');root.test.set(d.a,d.ta);go('check');go('transfer');go('checkTransfer');go('finish');assert(root.pendingSubmit);click();const event=posts.filter(p=>p.type==='streamlit:setComponentValue').at(-1).value;assert.equal(event.action,'submit');assert.equal(event.state.pick,d.a);render({ack:event.id,rows:[{lesson_id:event.lesson,status:'submitted',answers:{_state:event.state}}]});}
root.openExtraCourse('mission',0);const r=root.missionRecords[0];for(let j=0;j<3;j++){r.choice=M[0].steps[j][3];go('missionCheck');go('missionNext')}r.confirm=true;go('missionSubmit');assert.equal(r.status,'제출 준비');click();let e=posts.filter(p=>p.type==='streamlit:setComponentValue').at(-1).value;
render({ack:e.id,rows:[],error:'저장 실패'});assert.equal(r.status,'제출 준비');assert.equal(r.history.length,0);
go('missionSubmit');click();e=posts.filter(p=>p.type==='streamlit:setComponentValue').at(-1).value;render({ack:e.id,rows:[{lesson_id:'m1',status:'submitted',answers:{_state:e.state}}]});assert.equal(r.status,'제출됨');assert.equal(r.history.length,1);
assert(!main.innerHTML.includes('피드백 상태 체험'));console.log('PASS: all 14 core submissions and mission pending/failure/success acknowledgement states');
