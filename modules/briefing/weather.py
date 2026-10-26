"""Optional KMA display data; never participates in generation or publishing gates."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import lru_cache
import html
import json
import re
import time
from pathlib import Path
import requests

KST=ZoneInfo('Asia/Seoul')
ENDPOINT='https://www.weather.go.kr/w/wnuri-fct2021/main/digital-forecast.do'
SOURCE_URL='https://www.weather.go.kr/w/forecast/overall/short-term.do'
# Public province choices mapped to verified KMA forecast locations.
REGIONS=json.loads(Path(__file__).with_name('weather_regions.json').read_text(encoding='utf-8'))
DEFAULT_REGION='1100000000'

def region_name(code):
    return next((r['name'] for r in REGIONS if r['code']==code),'서울특별시')

def checked_region(code):
    return code if any(r['code']==code for r in REGIONS) else DEFAULT_REGION

def _plain(value):
    return html.unescape(re.sub('<[^>]+>','',value)).strip()

def parse_forecast(document, region, day, *, now=None):
    now=now or datetime.now(KST)
    day=str(day)
    blocks=re.split(r'<div\s+class="dfs-daily-slide"',document)
    block=next((b for b in blocks[1:] if re.search(r'data-date="'+re.escape(day)+'"',b[:250])),None)
    if block is None:raise ValueError('forecast_date_missing')
    issued=re.search(r'<dt>단기예보[^<]*</dt>\s*<dd>(\d{2})\.(\d{2})\.\([^)]*\)\s*(\d{2}):(\d{2})</dd>',document)
    if not issued:raise ValueError('forecast_issue_time_missing')
    month,dd,hh,mm=map(int,issued.groups())
    issued_at=now.replace(month=month,day=dd,hour=hh,minute=mm,second=0,microsecond=0)
    if issued_at-now>timedelta(days=180):issued_at=issued_at.replace(year=issued_at.year-1)
    if not -timedelta(minutes=15)<=now-issued_at<=timedelta(hours=24):raise ValueError('stale_forecast')
    am=re.search(r'title="오전 날씨 ([^"]+)"',block)
    pm=re.search(r'title="오후 날씨 ([^"]+)"',block)
    if not am and not pm:raise ValueError('forecast_conditions_missing')
    def temp(label):
        m=re.search(label+r'\s*:\s*</strong>\s*<span>(-?\d+(?:\.\d+)?)℃</span>',block)
        if not m:return None
        v=float(m.group(1))
        return v if -60<=v<=60 else None
    low,high=temp('최저'),temp('최고')
    if low is not None and high is not None and low>high:raise ValueError('invalid_temperatures')
    am=_plain(am.group(1)) if am else ''
    pm=_plain(pm.group(1)) if pm else ''
    condition=pm or am
    rain=any(x in am+pm for x in ('비','눈','소나기'))
    return {'status':'ok','region_code':region,'region_name':region_name(region),'date':day,
        'condition':condition,'morning':am,'afternoon':pm,'low':low,'high':high,
        'guidance':'비·눈 예보가 있어 외출 시 대비해 주세요.' if rain else '',
        'issued_at':issued_at.isoformat(),'retrieved_at':now.isoformat(),
        'source_name':'기상청','source_url':SOURCE_URL,
        'location_note':'시·도 대표 지점 기준 · 지역 내 차이 있음',
        'temperature_note':'최저·최고는 발표 시각에 따라 관측값 포함'}

@lru_cache(maxsize=128)
def _fetch(region, day, bucket):
    now=datetime.now(KST)
    unavailable={'status':'unavailable','region_code':region,'region_name':region_name(region),'date':day}
    # A past edition must never acquire today's forecast.
    if day!=now.date().isoformat():return {**unavailable,'reason':'historical'}
    forecast_code=next(r.get('forecast_code',r['code']) for r in REGIONS if r['code']==region)
    try:
        with requests.get(ENDPOINT,params={'code':forecast_code,'unit':'m/s','hr1':'Y'},
                headers={'User-Agent':'HWARANG-Briefing/1.15 weather display'},timeout=(12,12),
                allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise ValueError('upstream_unavailable')
            data=bytearray()
            for chunk in response.iter_content(32768):
                data.extend(chunk)
                if len(data)>750000:raise ValueError('response_too_large')
            return parse_forecast(data.decode('utf-8'),region,day,now=now)
    except (requests.RequestException,ValueError,UnicodeError):
        return {**unavailable,'reason':'fetch_failed'}

def get_weather(region=DEFAULT_REGION, day=None):
    region=checked_region(region)
    day=str(day or datetime.now(KST).date())
    return dict(_fetch(region,day,int(time.time()//900)))


def weather_html(weather):
    from .presentation import e
    region=e(weather.get('region_name'))
    date=e(weather.get('date'))
    if weather.get('status')!='ok':
        message='이 날짜의 저장된 예보가 없습니다.' if weather.get('reason')=='historical' else '예보를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.'
        return f'<section class="hw-weather unavailable"><div><b>{region} 날씨</b><div class="weather-note">{date} · {message}</div></div></section>'
    condition=str(weather.get('condition') or '')
    snow='눈' in condition
    rain=any(x in condition for x in ('비','소나기'))
    cloud=any(x in condition for x in ('구름','흐림','비','눈','소나기'))
    sun='' if '흐림' in condition or rain or snow else '<circle cx="39" cy="35" r="20" fill="#FFD15C"/><g stroke="#F6B73C" stroke-width="3" stroke-linecap="round"><path d="M39 6v5M39 59v5M10 35h5M64 35h5M18 14l4 4M57 54l4 4M18 56l4-4M57 16l4-4"/></g>'
    clouds='<path d="M28 72a16 16 0 1 1 2-32 22 22 0 0 1 42 5 14 14 0 1 1 0 27Z" fill="#BFDDF2"/><path d="M27 66a12 12 0 1 1 4-23 18 18 0 0 1 35 5 10 10 0 1 1 4 18Z" fill="#F9FDFF"/>' if cloud else ''
    drops='<path d="M35 78l-3 7m20-7l-3 7m20-7l-3 7" stroke="#428DC6" stroke-width="4" stroke-linecap="round"/>' if rain else ''
    if snow:drops='<g fill="#75A7D0"><circle cx="32" cy="82" r="3"/><circle cx="49" cy="86" r="3"/><circle cx="66" cy="81" r="3"/></g>'
    icon='<svg viewBox="0 0 96 96" aria-hidden="true" focusable="false">'+sun+clouds+drops+'</svg>'
    def degree(v):return '—' if v is None else f'{float(v):g}°'
    periods=' · '.join(label+' '+str(weather[key]) for key,label in (('morning','오전'),('afternoon','오후')) if weather.get(key))
    return (f'<section class="hw-weather" data-weather-date="{date}">'+icon+'<div><div class="weather-head"><span>오늘의 날씨</span><span>'+region+'</span></div><strong>'+e(condition)+'</strong>'
        +'<div class="temps">최저 <span class="low">'+degree(weather.get('low'))+'</span> / 최고 <span class="high">'+degree(weather.get('high'))+'</span></div>'
        +'<div>'+e(periods)+'</div><div>'+e(weather.get('guidance'))+'</div></div></section>')
