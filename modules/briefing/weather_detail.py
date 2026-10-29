"""Expanded staff weather card; observations and forecasts remain distinct."""
from datetime import datetime, timedelta
from functools import lru_cache
import html
import re
import requests
from .weather import KST, REGIONS, _plain


def periods(document, day):
    rows=[]
    for attrs, body in re.findall(r'<ul\b([^>]*\bclass="item\s[^>]+)>(.*?)</ul>', document, re.S):
        date=re.search(r'data-date="([^"]+)"',attrs)
        hour=re.search(r'data-time="(\d{2}):00"',attrs)
        if not date or date[1]!=day or not hour:continue
        condition=re.search(r'class="wic [^"]*" title="([^"]+)"',body)
        pop=re.search(r'강수확률:\s*</span>\s*<span>(\d+)%</span>',body)
        rows.append({'hour':int(hour[1]),'condition':_plain(condition[1]) if condition else '',
                     'pop':int(pop[1]) if pop and 0<=int(pop[1])<=100 else None})
    result=[]
    for label,start,end,code in [('오전',1,12,'am'),('오후',13,18,'pm'),('저녁',19,24,None)]:
        subset=[r for r in rows if start<=r['hour']<=end]
        values=[r['pop'] for r in subset if r['pop'] is not None]
        chosen=max(subset,key=lambda r:(any(x in r['condition'] for x in ('비','눈','소나기')),r['pop'] if r['pop'] is not None else -1),default={})
        condition=chosen.get('condition','')
        pop=max(values) if values else None
        if code:
            blocks=re.split(r'<div\s+class="dfs-daily-slide"',document)
            block=next((b for b in blocks[1:] if f'data-date="{day}"' in b[:250]),'')
            daily=re.search(r'title="'+label+r' 날씨 ([^"]+)"',block)
            probability=re.search(r'class="daily-pop-'+code+r'".*?<span>(\d+)%</span>',block,re.S)
            # Daily AM/PM summaries also retain the elapsed part of the period.
            condition=_plain(daily[1]) if daily else condition
            if probability and 0<=int(probability[1])<=100:pop=int(probability[1])
        result.append({'label':label,'condition':condition,'pop':pop})
    return result


def parse_observation(document, *, now):
    m=re.search(r'class="updated-at"[^>]*><span>(\d{2})\.(\d{2})\.\([^)]*\)\s*(\d{2}):(\d{2})</span>',document)
    if not m:raise ValueError('observation_time_missing')
    month,day,hour,minute=map(int,m.groups())
    at=now.replace(month=month,day=day,hour=hour,minute=minute,second=0,microsecond=0)
    if at-now>timedelta(days=180):at=at.replace(year=at.year-1)
    if not -timedelta(minutes=15)<=now-at<=timedelta(hours=2):raise ValueError('stale_observation')
    def number(pattern):
        match=re.search(pattern,document)
        value=float(match[1]) if match else None
        return value if value is not None and -60<=value<=60 else None
    temperature=number(r'class="tmp">\s*(-?\d+(?:\.\d+)?)\s*<small>℃')
    feels=number(r'class="chill">체감\((-?\d+(?:\.\d+)?)℃\)')
    if temperature is None:raise ValueError('observation_temperature_missing')
    return {'current':temperature,'feels_like':feels,'observed_at':at.isoformat()}


@lru_cache(maxsize=128)
def observation(region, day, bucket):
    now=datetime.now(KST)
    if day!=now.date().isoformat():return {}
    code=next(r.get('forecast_code',r['code']) for r in REGIONS if r['code']==region)
    try:
        with requests.get('https://www.weather.go.kr/w/wnuri-fct2021/main/current-weather.do',
                params={'code':code,'unit':'m/s'},headers={'User-Agent':'HWARANG-Briefing weather display'},
                timeout=(5,7),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:return {}
            data=bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data)>150000:return {}
            return parse_observation(data.decode('utf-8'),now=now)
    except (requests.RequestException,ValueError,UnicodeError):return {}


def detailed_html(weather):
    e=lambda v:html.escape(str(v if v is not None else ''),quote=True)
    degree=lambda v:'—' if v is None else f'{float(v):g}°'
    from .weather import weather_icon
    def icon(condition):
        return weather_icon(condition) if condition else '—'
    cards=[]
    forecast=weather.get('periods') or []
    for row in forecast:
        pop=row.get('pop')
        cards.append('<div class="hw-weather-period"><span>'+e(row['label'])+'</span><span class="hw-weather-symbol" aria-hidden="true">'+icon(row.get('condition'))+'</span><b>'+e(row.get('condition') or '예보 없음')+'</b><span class="hw-weather-pop">강수 '+('—' if pop is None else str(pop)+'%')+'</span></div>')
    wet=any((r.get('pop') or 0)>=60 or any(x in r.get('condition','') for x in ('비','눈','소나기')) for r in forecast)
    cold=weather.get('feels_like') is not None and weather['feels_like']<12
    advice='우산을 챙겨 주세요.' if wet else '외출 전 시간대별 예보를 확인해 주세요.'
    if cold:advice+=' 쌀쌀하니 겉옷도 준비하세요.'
    if weather.get('status')!='ok':advice='예보를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.'
    def clock(key):
        try:return datetime.fromisoformat(weather[key]).astimezone(KST).strftime('%H:%M')
        except (KeyError,ValueError,TypeError):return '확인 불가'
    hour=datetime.now(KST).hour
    current_period=next((r for r in forecast if r['label']==('오전' if hour<12 else '오후' if hour<18 else '저녁')), {})
    main_icon='<div class="hw-weather-large-icon" title="'+e(current_period.get('label',''))+' 예보" aria-hidden="true">'+icon(current_period.get('condition'))+'</div>'
    return ('<section class="hw-weather hw-weather-expanded" aria-label="오늘의 날씨">'
      '<div class="hw-weather-heading"><b>오늘의 날씨</b><span>'+e(weather.get('region_name'))+'</span></div>'
      '<div class="hw-weather-main">'+main_icon+'<div class="hw-weather-now"><span class="hw-weather-current-label">현재 기온</span><strong>'+degree(weather.get('current'))+'</strong>'
      '<span>체감 '+degree(weather.get('feels_like'))+'</span><span class="hw-weather-range">최저 <b>'+degree(weather.get('low'))+'</b> · 최고 <b>'+degree(weather.get('high'))+'</b></span></div>'
      '<div class="hw-weather-periods">'+''.join(cards)+'</div></div>'
      '<div class="hw-weather-advice">'+e(advice)+'</div><div class="hw-weather-meta">기상청 · 현재 '+clock('observed_at')+' / 예보 '+clock('issued_at')+' 기준 · 시·도 대표 지점'
      '<span>오전·오후는 반일 예보, 저녁은 19–24시 최대 강수확률</span></div></section>')
