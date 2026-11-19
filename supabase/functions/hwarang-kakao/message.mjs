/** Deterministic, lossless, compact messages. No network and no AI billing. */
export function splitLines(lines, max=200) {
  if (!Number.isInteger(max)||max<2||max>200) throw Error('Invalid limit');
  const parts=[];let current='',blank=false;
  for (const line of lines) {
    if(typeof line!=='string')throw Error('Invalid line');
    if(!line){blank=true;continue;}
    const chunks=[];let chunk='';
    for(const cp of line){if(chunk.length+cp.length>max){chunks.push(chunk);chunk='';}chunk+=cp;}if(chunk)chunks.push(chunk);
    for(const c of chunks){const gap=current?(blank?'\n\n':'\n'):'';if(current && current.length+gap.length+c.length>max){parts.push(current);current='';}current += (current?gap:'')+c;blank=false;}
  }
  if(current)parts.push(current);return parts;
}
export function briefing(day, events, emptyConfirmed=false, weather=undefined) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Array.isArray(events))throw Error('Invalid data');
  const sorted=[...events].sort((a,b)=>(a.time_pending?'99:99':a.start_time||'99:99').localeCompare(b.time_pending?'99:99':b.start_time||'99:99')||String(a.id).localeCompare(String(b.id)));
  const lines=[`🗓 ${Number(day.slice(5,7))}월 ${Number(day.slice(8,10))}일 일정`,''];
  for(const e of sorted){
    if(typeof e.title!=='string')throw Error('Invalid title');
    const time=e.start_time&&!e.time_pending?e.start_time.slice(0,5)+(e.end_time?'~'+e.end_time.slice(0,5):''):'시간 미정';
    const status=e.status&&e.status!=='예정'?` [${e.status}]`:'';
    lines.push(`${time} ${e.title}${e.place?' · '+e.place:''}${status}`,'');
  }
  if(!sorted.length)lines.push(emptyConfirmed?'등록된 일정이 없습니다.':'아직 등록된 일정이 없습니다.','');
  if(weather!==undefined)lines.push(...weatherLines(day,weather));
  return splitLines(lines);
}

/** Staff counts only; personal weather remains in the following personal message(s). */
export function branchBriefing(day, branch) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Array.isArray(branch?.members))throw Error('Invalid branch');
  const clean=s=>String(s||'').replace(/[\r\n]+/g,' ').trim();
  const weekday='일월화수목금토'[new Date(day+'T00:00:00Z').getUTCDay()];
  const heading=`${Number(day.slice(5,7))}/${Number(day.slice(8))}(${weekday}) ${clean(branch.name)} 일정`;
  const lines=[heading,'','[직원별 일정]'];
  const scheduled=branch.members.filter(m=>m.count>0);
  for(let i=0;i<scheduled.length;i+=2)lines.push(scheduled.slice(i,i+2).map(m=>`${clean(m.name)} ${m.count}건`).join(' · '));
  if(!scheduled.length)lines.push('등록된 직원 일정 없음');
  const count=state=>branch.members.filter(m=>m.state===state).length;
  const leave=branch.members.filter(m=>m.on_leave===true||(m.on_leave===undefined&&m.state==='leave')).length;
  const missing=branch.members.filter(m=>m.state==='missing');
  lines.push('',`휴무 ${leave}명 · 일정 없음 ${count('empty')}명`);
  let line=`미등록 ${missing.length}명`,names=0;
  for(const member of missing) {
    const name=clean(member.name);
    if(name.length>200)throw Error('Member name exceeds message limit');
    const candidate=line+(names?'·':': ')+name;
    if(candidate.length<=200){line=candidate;names++;continue;}
    lines.push(line);line='미등록(계속): '+name;names=1;
    if(line.length>200){lines.push('미등록(계속):');line=name;}
  }
  lines.push(line);
  return splitLines(lines);
}

export function hasMemberBriefing(summary) {
 return ['branch_manager','team_leader','deputy_branch_manager'].includes(summary.identity?.position)
  && summary.preferences?.member_briefing_enabled!==false && Array.isArray(summary.branch?.members) && summary.branch.members.length>0;
}

export function briefingBundle(day, summary, weather) {
  const branch=hasMemberBriefing(summary)&&summary.branch;
  return [
    ...(branch?branchBriefing(day,branch).map(body=>({kind:'branch',body})):[]),
    ...briefing(day,summary.events,summary.empty_explicit,weather).map(body=>({kind:'personal',body})),
  ];
}

/** Weather is a validated daily forecast, never raw provider HTML or a user address. */
export function weatherLines(day, weather) {
  const label=typeof weather?.region_name==='string' && weather.region_name.length<=80 && !/[\r\n]/.test(weather.region_name)?weather.region_name:'';
  const heading=`🌤 ${label?label+' ':''}날씨`;
  const unavailable=()=>[heading+' · 확인하지 못했습니다.'];
  if(weather?.status!=='ok'||weather.day!==day)return unavailable();
  const numeric=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
  if((weather.low!==null&&!numeric(weather.low,-60,60))||(weather.high!==null&&!numeric(weather.high,-60,60))||(weather.low!==null&&weather.high!==null&&weather.low>weather.high))return unavailable();
  if(!/^\d{2}:\d{2}$/.test(weather.issued_time||'')||!/^\d{4}-\d{2}-\d{2}$/.test(weather.issued_day||''))return unavailable();
  if(Object.hasOwn(weather,'morning')) {
    const validCondition=s=>typeof s==='string'&&s.length<=40&&(!s||/^[가-힣\s·/(),~-]+$/.test(s));
    if(!validCondition(weather.morning)||!validCondition(weather.afternoon)||(!weather.morning&&!weather.afternoon))return unavailable();
    const temperatures=weather.low!==null&&weather.high!==null?`최저 ${weather.low}℃ · 최고 ${weather.high}℃`:weather.high!==null?`최고 ${weather.high}℃`:weather.low!==null?`최저 ${weather.low}℃`:'기온 미확인';
    const periods=[weather.morning?'오전 '+weather.morning:'',weather.afternoon?'오후 '+weather.afternoon:''].filter(Boolean).join(' · ');
    return [heading,'',periods,temperatures];
  }
  if(!numeric(weather.rain_probability,0,100))return unavailable();
  const conditions=new Set(['맑음','구름 많음','흐림','비','비 또는 눈','눈','소나기']);
  if(!conditions.has(weather.condition))return unavailable();
  const temperature=weather.low!==null&&weather.high!==null?`${weather.low}~${weather.high}℃`:weather.high!==null?`최고 ${weather.high}℃`:weather.low!==null?`최저 ${weather.low}℃`:'기온 미확인';
  return [heading,'',`${weather.condition} · ${temperature} · 강수 ${weather.rain_probability}%`];
}
