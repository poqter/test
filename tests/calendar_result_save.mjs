// Execute the actual result-overlay save callback with synthetic UI and RPC only.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('modules/activity/calendar_view/persistent.js','utf8');
const code=source.slice(source.indexOf('function openResult('),source.indexOf('function paintReviews('));
async function check(updatedCount,rejected=false){
 const buttons=[],messages=[],details=[],writes=[];let closed=0,mutations=0,pending;
 const node=()=>({dataset:{},children:[],append(...items){this.children.push(...items)},setAttribute(){},addEventListener(){},querySelector(){return node()},focus(){},close(){closed++},reportValidity(){return true}});
 const ctx={calendarPanel:node(),latest:{today:'2026-11-17'},el:node,field:(_host,_label,name,value)=>({name,value,dataset:{}}),
 button:(label,click)=>{const b={label,click};buttons.push(b);return b},feedback:node,
 runButton:(_button,_error,action)=>(pending=action()),values:()=>({status:'완료',result:'상담 완료'}),
 date:s=>new Date(s+'T00:00:00Z'),add:(d,n)=>new Date(+d+n*86400000),iso:d=>d.toISOString().slice(0,10),
 rpc:async(op,args)=>{writes.push({op,args});if(rejected)throw Error('synthetic conflict');return {id:'event',updated_count:updatedCount}},
 openDetail:id=>details.push(id),mutate:()=>mutations++,calendarStatus:s=>messages.push(s),document:{body:node()},showCalendarDialog(){}};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 ctx.row={id:'event',revision:7,day:'2026-11-17',title:'상담',kind:'AP',start_time:'10:00:00',status:'예정'};
 vm.runInContext('openResult(row)',ctx);
 buttons.find(b=>b.label==='결과 저장').click();const saving=pending;
 if(rejected){await assert.rejects(saving,/synthetic conflict/);assert.equal(closed,0);assert.equal(messages.length,0);assert.equal(mutations,0);}
 else {await saving;assert.equal(closed,1);assert.deepEqual(details,['event']);assert.equal(mutations,1);assert.deepEqual(messages,[updatedCount>1?'반복 일정 '+updatedCount+'건을 저장했습니다.':'저장했습니다.']);}
 assert.equal(writes.length,1);assert.equal(writes[0].args.revision,7);assert.equal(writes[0].args.data.result,'상담 완료');
}
await check(1);await check(3);await check(undefined);await check(1,true);
console.log(JSON.stringify({pass:true,checks:'single result save / repeated-count feedback / legacy response / failure keeps form open'}));
