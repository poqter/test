(()=>{
const root=document.getElementById('hwarang-academy-alpha'),msg=document.getElementById('servermsg'),save=document.getElementById('save');let ready=false,busy=false,last=null,hydratedAck=null;
const post=(type,extra={})=>parent.postMessage({isStreamlitMessage:true,type,...extra},'*');
const clone=x=>JSON.parse(JSON.stringify(x));
const labels={draft:'학습 중',submitted:'학습 완료',approved:'검토 완료',revision_requested:'보완 필요'};
root.savedRows={};root.savedLabel=id=>labels[root.savedRows[id]?.status];
function height(){post('streamlit:setFrameHeight',{height:Math.min(16000,document.documentElement.scrollHeight+12)})}
function hydrate(rows){root.savedRows=Object.fromEntries(rows.map(w=>[w.lesson_id,w]));root.approvedMissions=rows.filter(w=>w.lesson_id.startsWith('m')&&w.status==='approved').length;root.graduated=rows.filter(w=>/^l\d+$/.test(w.lesson_id)&&['submitted','approved'].includes(w.status)).length===15&&root.approvedMissions===3;
for(const w of rows){const s=w.answers?._state;if(!s)continue;const i=Number(w.lesson_id.slice(1))-1;
if(w.lesson_id==='l02'){Object.assign(root.lessonState,s);root.lessonState.status={approved:'approved',submitted:'submitted',revision_requested:'revision',draft:'draft'}[w.status];root.demoDone=['submitted','approved'].includes(w.status);root.demoStatus=labels[w.status]}
else if(w.lesson_id.startsWith('l')){root.courseRecords[i]=s;s.status=['submitted','approved'].includes(w.status)?'학습 완료':'학습 중';if(w.status==='revision_requested')s.step=0}
else if(w.lesson_id.startsWith('m')){root.missionRecords[i]=s;if(w.status!=='draft')s.status={submitted:'제출됨',approved:'검토 완료',revision_requested:'보완 필요'}[w.status];s.feedback=Object.values(w.feedback||{}).join(' / ').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
else if(w.lesson_id.startsWith('p')){root.prepChecks[i]=s;root.prepStates[i]=s.every(Boolean)}else if(w.lesson_id.startsWith('f'))root.fieldRecords[i]=s;
}root.prepCompleted=Object.values(root.prepStates).filter(Boolean).length;}
function send(action){if(!ready||busy)return;if(action!=='reload'&&!root.active){msg.textContent='수업 또는 활동을 연 뒤 저장해 주세요.';return}const a=root.active;const w=a?root.savedRows[a.lesson]:null;if(action!=='reload'&&['submitted','approved'].includes(w?.status)){msg.textContent='이미 제출한 기록입니다. 재연습은 저장된 제출 결과를 변경하지 않습니다.';return}busy=true;save.disabled=true;msg.textContent='서버에 저장을 확인하고 있습니다…';last={id:crypto.randomUUID(),action,lesson:a?.lesson,version:w?.version||0,state:a?clone(a.state):null};post('streamlit:setComponentValue',{value:last});}
window.addEventListener('message',e=>{if(e.source!==parent||e.data.type!=='streamlit:render')return;const a=e.data.args;const initial=!ready;ready=true;if(initial||(a.reload&&a.ack!==hydratedAck)){hydrate(a.rows||[]);hydratedAck=a.ack;root.showHome()}
if(a.ack===last?.id){busy=false;save.disabled=false;root.savedRows=Object.fromEntries((a.rows||[]).map(w=>[w.lesson_id,w]));root.approvedMissions=(a.rows||[]).filter(w=>w.lesson_id.startsWith('m')&&w.status==='approved').length;root.graduated=(a.rows||[]).filter(w=>/^l\d+$/.test(w.lesson_id)&&['submitted','approved'].includes(w.status)).length===15&&root.approvedMissions===3;msg.textContent=a.error||'서버 저장 완료 · 교육 홈의 진도에 반영되었습니다.';if(a.error){if(root.active?.lesson.startsWith('m'))root.active.state.status='제출 준비';if(root.active?.lesson==='l02')root.active.state.status='draft';}last=null;}
else if(initial)msg.textContent='기존 학습 기록을 불러왔습니다. 중간 선택은 학습 중 저장을 눌러 보관하세요.';height();});
save.onclick=()=>send('save');document.getElementById('refresh').onclick=()=>send('reload');
document.addEventListener('click',()=>{queueMicrotask(()=>{if(root.pendingSubmit){root.pendingSubmit=false;send('submit')}const w=root.active&&root.savedRows[root.active.lesson];if(w?.feedback&&Object.keys(w.feedback).length&&!busy){msg.textContent=['관리자 피드백',...['good','improve','next'].map((k,i)=>['잘한 점','보완할 점','다음 연습'][i]+': '+(w.feedback[k]||''))].join('\n')}height()})});
new ResizeObserver(height).observe(document.getElementById('hwarang-academy-alpha'));
post('streamlit:componentReady',{apiVersion:1});height();
})();
