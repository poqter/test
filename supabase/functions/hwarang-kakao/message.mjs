/** Deterministic, lossless, compact messages. No network and no AI billing. */
export function splitLines(lines, max=200) {
  if (!Number.isInteger(max)||max<2||max>200) throw Error('Invalid limit');
  const parts=[];let current='';
  for (const line of lines) {
    if(typeof line!=='string')throw Error('Invalid line');
    if(!line)continue;
    const chunks=[];let chunk='';
    for(const cp of line){if(chunk.length+cp.length>max){chunks.push(chunk);chunk='';}chunk+=cp;}if(chunk)chunks.push(chunk);
    for(const c of chunks){if(current && current.length+1+c.length>max){parts.push(current);current='';}current += (current?'\n':'')+c;}
  }
  if(current)parts.push(current);return parts;
}
export function briefing(day, events, emptyConfirmed=false) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Array.isArray(events))throw Error('Invalid data');
  const sorted=[...events].sort((a,b)=>(a.time_pending?'99:99':a.start_time||'99:99').localeCompare(b.time_pending?'99:99':b.start_time||'99:99')||String(a.id).localeCompare(String(b.id)));
  const lines=[`🗓 ${Number(day.slice(5,7))}월 ${Number(day.slice(8,10))}일 일정`];
  for(const e of sorted){
    if(typeof e.title!=='string')throw Error('Invalid title');
    const time=e.start_time&&!e.time_pending?e.start_time.slice(0,5)+(e.end_time?'~'+e.end_time.slice(0,5):''):'시간 미정';
    const status=e.status&&e.status!=='예정'?` [${e.status}]`:'';
    lines.push(`${time} ${e.title}${e.place?' · '+e.place:''}${status}`);
  }
  if(!sorted.length)lines.push(emptyConfirmed?'등록된 일정이 없습니다.':'아직 등록된 일정이 없습니다.');
  return splitLines(lines);
}
