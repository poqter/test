/** Port of modules/briefing/weather.py. Existing public page only; no alternate provider fallback. */
export const WEB_WEATHER_ENDPOINT='https://www.weather.go.kr/w/wnuri-fct2021/main/digital-forecast.do';
const validDay=s=>/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s+'T00:00:00Z'))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
export function parseWebWeather(document,{day,now=new Date(),forecast_code=undefined}) {
 const today=new Date(now.getTime()+9*3600000).toISOString().slice(0,10);
 if(typeof document!=='string'||!validDay(day)||day!==today)throw Error('Weather date unavailable');
 if(forecast_code!==undefined&&(!/^\d{10}$/.test(forecast_code)||!new RegExp('dongCode='+forecast_code+'(?:[&#"\\s]|$)').test(document)))throw Error('Weather region mismatch');
 const block=document.split(/<div\s+class="dfs-daily-slide"/).slice(1).find(b=>b.slice(0,250).includes(`data-date="${day}"`));
 const issue=document.match(/<dt>단기예보[^<]*<\/dt>\s*<dd>(\d{2})\.(\d{2})\.\([^)]*\)\s*(\d{2}):(\d{2})<\/dd>/);
 if(!block||!issue)throw Error('Weather structure changed');
 const [,month,date,hour,minute]=issue;
 if(Number(hour)>23||Number(minute)>59)throw Error('Invalid issue time');
 let year=Number(today.slice(0,4)),issuedDay=`${year}-${month}-${date}`;
 if(!validDay(issuedDay))throw Error('Invalid issue date');
 let issued=new Date(`${issuedDay}T${hour}:${minute}:00+09:00`);
 if(issued-now>180*86400000){issuedDay=`${--year}-${month}-${date}`;if(!validDay(issuedDay))throw Error('Invalid issue date');issued=new Date(`${issuedDay}T${hour}:${minute}:00+09:00`);}
 if(now-issued>24*3600000||issued-now>15*60000)throw Error('Stale weather');
 const condition=part=>{const raw=block.match(new RegExp(`title="${part} 날씨 ([^"]+)"`))?.[1]||'';if(raw&&!/^[가-힣\s·/(),~-]{1,40}$/.test(raw))throw Error('Invalid weather condition');return raw.trim();};
 const morning=condition('오전'),afternoon=condition('오후');if(!morning&&!afternoon)throw Error('Conditions unavailable');
 const temperature=label=>{const raw=block.match(new RegExp(label+'\\s*:\\s*</strong>\\s*<span>(-?\\d+(?:\\.\\d+)?)℃</span>'))?.[1];if(raw===undefined)return null;const v=Number(raw);return v>=-60&&v<=60?v:null;};
 const low=temperature('최저'),high=temperature('최고');if(low!==null&&high!==null&&low>high)throw Error('Invalid temperature order');
 return {status:'ok',day,low,high,morning,afternoon,issued_day:issuedDay,issued_time:hour+':'+minute};
}
export async function fetchWebWeather(fetcher,{day,forecast_code,now=new Date()}) {
 if(!/^\d{10}$/.test(forecast_code||''))throw Error('Invalid weather region');
 if(day!==new Date(now.getTime()+9*3600000).toISOString().slice(0,10))throw Error('Historical weather unavailable');
 const url=new URL(WEB_WEATHER_ENDPOINT);url.search=new URLSearchParams({code:forecast_code,unit:'m/s',hr1:'Y'}).toString();
 const response=await fetcher(url,{headers:{'User-Agent':'HWARANG-Briefing/1.15 weather display'},signal:AbortSignal.timeout(4000),redirect:'error'});
 if(!response.ok)throw Error('Weather unavailable');
 const reader=response.body?.getReader();if(!reader)throw Error('Weather unavailable');let length=0;const chunks=[];
 try{for(;;){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>750000)throw Error('Weather too large');chunks.push(value);}}finally{await reader.cancel().catch(()=>{});}
 const bytes=new Uint8Array(length);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
 return parseWebWeather(new TextDecoder('utf-8',{fatal:true}).decode(bytes),{day,now,forecast_code});
}
