'use strict';
(()=>{
 const log=document.getElementById('messages'),input=document.getElementById('message'),form=document.getElementById('composer'),send=document.getElementById('send'),status=document.getElementById('request-status'),controls=document.getElementById('retry-controls'),newer=document.getElementById('new-message');
 let model=null,pending=null,failed='',busy=false,composing=false,identity='',lastAck='',savedScroll=0,atBottom=true;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function post(type,payload={}){parent.postMessage({isStreamlitMessage:true,type,...payload},'*')}
 function height(){post('streamlit:setFrameHeight',{height:document.documentElement.scrollHeight})}
 function jump(){log.scrollTop=log.scrollHeight;newer.hidden=true}
 function bubble(m,cls='',note=''){return `<article class="message ${esc(m.role)} ${cls}"><span class="name">${m.role==='advisor'?'나':esc(model.customer_name)}</span><div class="bubble">${esc(m.text)}${m.attachment==='insurance'?'<div class="attachment">📄 증권 · 고객 자료에서 확인할 수 있어요.</div>':''}</div>${note?`<small>${esc(note)}</small>`:''}</article>`}
 function render(force=false){
  const near=atBottom,top=savedScroll;
  log.innerHTML=(model.messages||[]).map(m=>bubble(m)).join('');
  if(pending)log.insertAdjacentHTML('beforeend',bubble({role:'advisor',text:pending.text},'pending','전송 중'));
  if(failed&&!pending)log.insertAdjacentHTML('beforeend',bubble({role:'advisor',text:failed},'failed','전송되지 않음 · 평가에 반영되지 않았습니다'));
  if(busy)log.insertAdjacentHTML('beforeend','<article class="message typing"><span class="name">'+esc(model.customer_name)+'</span><div class="bubble"><i></i><i></i><i></i> 답변을 준비하고 있어요.</div></article>');
  for(const signal of model.signals||[]){const p=document.createElement('p');p.className='signal';p.textContent='관찰 · '+signal.label+' / “'+signal.quote+'”';log.append(p)}
  status.textContent=busy?'고객이 답변을 준비하고 있습니다.':model.error?.message||'';
  controls.hidden=!failed||busy;document.getElementById('retry').disabled=Boolean(model.error?.blocked);document.getElementById('edit').disabled=Boolean(model.error?.blocked);
  input.disabled=busy||model.disabled||Boolean(model.error?.blocked);send.disabled=input.disabled;
  document.getElementById('customer-name').textContent=model.customer_name+' 고객';document.getElementById('chat-stage').textContent=model.stage_label;document.getElementById('room-state').textContent=busy?'답변 중':model.disabled?'장면 완료':'대화 중';
  requestAnimationFrame(()=>{if(force||near)jump();else{log.scrollTop=top;newer.hidden=false}height()});
 }
 function submit(text){text=text.trim();if(!text||busy||model.disabled||model.error?.blocked)return;const id=crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random();pending={id,text};failed='';busy=true;input.value='';document.getElementById('count').textContent='0 / 2400';render(true);post('streamlit:setComponentValue',{value:{event_id:id,kind:'send',text,version:model.version},dataType:'json'})}
 form.addEventListener('submit',e=>{e.preventDefault();submit(input.value)});input.addEventListener('compositionstart',()=>composing=true);input.addEventListener('compositionend',()=>composing=false);input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!composing&&!e.isComposing){e.preventDefault();submit(input.value)}});input.addEventListener('input',()=>{document.getElementById('count').textContent=input.value.length+' / 2400'});
 document.getElementById('retry').onclick=()=>submit(failed);document.getElementById('edit').onclick=()=>{input.value=failed;failed='';model.error=null;render();input.focus();input.dispatchEvent(new Event('input'))};newer.onclick=jump;
 log.addEventListener('scroll',()=>{savedScroll=log.scrollTop;atBottom=log.scrollHeight-log.clientHeight-log.scrollTop<55;if(atBottom)newer.hidden=true});
 addEventListener('message',e=>{if(e.source!==parent||e.data?.type!=='streamlit:render')return;const next=e.data.args.model;if(!next)return;const nextId=next.session_id+':'+next.branch;const reset=identity!==nextId;identity=nextId;
  if(reset){pending=null;failed='';busy=false;input.value='';lastAck='';atBottom=true;savedScroll=0}
  model=next;
  if(model.ack&&model.ack!==lastAck){lastAck=model.ack;if(!pending||model.ack===pending.id){pending=null;busy=false;failed=model.error?.text||''}}
  if(!pending&&model.error?.text)failed=model.error.text;
  render(reset);if(!busy&&!model.error)input.focus({preventScroll:true});
 });
 post('streamlit:componentReady',{apiVersion:1});height();new ResizeObserver(height).observe(document.querySelector('.chat-shell'));
})();
