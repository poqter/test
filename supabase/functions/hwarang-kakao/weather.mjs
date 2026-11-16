/** Official KMA public-data gateway only. No HTML scraping, geolocation, AI or paid fallback. */
export const WEATHER_ENDPOINT='https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst';
const dayPattern=/^\d{4}-\d{2}-\d{2}$/;
const compact=s=>s.replaceAll('-','');
const validDay=s=>dayPattern.test(s)&&Number.isFinite(Date.parse(s+'T00:00:00Z'))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
const iso=s=>`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;
export function forecastBase(now=new Date()) {
 const local=new Date(now.getTime()+9*3600000-10*60000);
 const hour=local.getUTCHours();let selected=[2,5,8,11,14,17,20,23].filter(h=>h<=hour).at(-1);
 if(selected===undefined){local.setUTCDate(local.getUTCDate()-1);selected=23;}
 return {base_date:local.toISOString().slice(0,10).replaceAll('-',''),base_time:String(selected).padStart(2,'0')+'00'};
}
export function parseWeather(payload,{day,nx,ny,base_date,base_time}) {
 if(!validDay(day)||!['00','0'].includes(String(payload?.response?.header?.resultCode)))throw Error('Weather unavailable');
 if(!/^\d{8}$/.test(base_date)||!validDay(iso(base_date))||!['0200','0500','0800','1100','1400','1700','2000','2300'].includes(base_time))throw Error('Invalid weather issue');
 const body=payload.response.body,rows=body?.items?.item;
 if(!Array.isArray(rows)||rows.length>2000||Number(body.totalCount)>rows.length)throw Error('Incomplete weather');
 const wanted=rows.filter(r=>r.fcstDate===compact(day));
 if(!wanted.length)throw Error('Weather date unavailable');
 const hours=new Map();
 for(const row of wanted){
  if(!/^([01]\d|2[0-3])00$/.test(row.fcstTime))throw Error('Invalid forecast hour');
  if(['POP','SKY','PTY'].includes(row.category)){const group=hours.get(row.fcstTime)||new Set();if(group.has(row.category))throw Error('Duplicate forecast');group.add(row.category);hours.set(row.fcstTime,group);}
 }
 if(!hours.size||[...hours.values()].some(group=>group.size!==3))throw Error('Partial weather coverage');
 const dayDelta=(Date.parse(day+'T00:00:00Z')-Date.parse(iso(base_date)+'T00:00:00Z'))/86400000;
 if(dayDelta<0||dayDelta>1)throw Error('Stale forecast date');
 const firstHour=dayDelta===0?Number(base_time.slice(0,2))+1:0;
 for(let hour=firstHour;hour<=23;hour++)if(!hours.has(String(hour).padStart(2,'0')+'00'))throw Error('Incomplete hourly forecast');
 for(const row of rows)if(!/^\d{8}$/.test(row.fcstDate)||String(row.baseDate)!==base_date||String(row.baseTime)!==base_time||Number(row.nx)!==nx||Number(row.ny)!==ny)throw Error('Weather mismatch');
 const values=(category,min,max)=>wanted.filter(r=>r.category===category).map(r=>{
  if(!/^-?\d+(\.\d+)?$/.test(String(r.fcstValue)))throw Error('Invalid weather value');
  const v=Number(r.fcstValue);if(!Number.isFinite(v)||v<min||v>max)throw Error('Invalid weather value');return v;
 });
 const lows=values('TMN',-60,60),highs=values('TMX',-60,60),rain=values('POP',0,100),sky=values('SKY',1,4),pty=values('PTY',0,4);
 if(!rain.length||!sky.length||!pty.length||sky.some(v=>![1,3,4].includes(v))||pty.some(v=>!Number.isInteger(v)))throw Error('Weather categories unavailable');
 const low=lows.length?Math.min(...lows):null,high=highs.length?Math.max(...highs):null;
 if(low!==null&&high!==null&&low>high)throw Error('Invalid weather temperatures');
 const precipitation=pty.includes(2)?2:pty.includes(3)?3:pty.includes(4)?4:pty.includes(1)?1:0;
 const condition=precipitation?({1:'비',2:'비 또는 눈',3:'눈',4:'소나기'})[precipitation]:({1:'맑음',3:'구름 많음',4:'흐림'})[Math.max(...sky)];
 return {status:'ok',day,low,high,rain_probability:Math.max(...rain),condition,issued_day:iso(base_date),issued_time:base_time.slice(0,2)+':'+base_time.slice(2)};
}
export async function fetchWeather(fetcher,key,query) {
 if(typeof key!=='string'||!key.trim())throw Error('Weather not configured');
 if(!Number.isInteger(query.nx)||!Number.isInteger(query.ny)||query.nx<1||query.nx>149||query.ny<1||query.ny>253)throw Error('Invalid weather grid');
 const url=new URL(WEATHER_ENDPOINT);url.search=new URLSearchParams({serviceKey:key,pageNo:'1',numOfRows:'2000',dataType:'JSON',base_date:query.base_date,base_time:query.base_time,nx:String(query.nx),ny:String(query.ny)}).toString();
 const response=await fetcher(url,{signal:AbortSignal.timeout(4000),redirect:'error'});
 if(!response.ok)throw Error('Weather unavailable');
 const reader=response.body?.getReader();if(!reader)throw Error('Weather unavailable');let length=0;const chunks=[];
 try{for(;;){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>750000)throw Error('Weather too large');chunks.push(value);}}finally{await reader.cancel().catch(()=>{});}
 const data=new Uint8Array(length);let offset=0;for(const chunk of chunks){data.set(chunk,offset);offset+=chunk.length;}
 return parseWeather(JSON.parse(new TextDecoder().decode(data)),query);
}
