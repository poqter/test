from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from modules.briefing.weather import parse_forecast, weather_html, get_weather, _fetch
from modules.briefing.presentation import article_html
from modules.briefing.public_body import public_html

NOW=datetime(2026,10,26,8,0,tzinfo=ZoneInfo('Asia/Seoul'))
DOC='''<div class="dfs-daily-slide" data-date="2026-10-26"><span title="오전 날씨 구름많음"></span><span title="오후 날씨 비"></span><strong>최저 : </strong><span>11℃</span><strong>최고 : </strong><span>19℃</span></div><div class="dfs-daily-slide" data-date="2026-10-27"><span title="오후 날씨 맑음"></span><strong>최저 : </strong><span>8℃</span></div><dt>단기예보(초단기예보 이후 모레까지):</dt><dd>10.26.(월) 05:00</dd>'''

def test_weather_uses_requested_day_and_explicit_issue_time():
    w=parse_forecast(DOC,'1100000000','2026-10-26',now=NOW)
    assert (w['low'],w['high'],w['morning'],w['afternoon'])==(11,19,'구름많음','비')
    assert w['issued_at'].endswith('05:00:00+09:00')
    assert '대표 지점' in w['location_note']
    assert '비·눈' in w['guidance']

def test_weather_fails_closed_on_wrong_day_stale_or_missing_condition():
    for doc,day in [(DOC,'2026-10-25'),(DOC.replace('10.26.(월) 05:00','10.24.(토) 05:00'),'2026-10-26'),(DOC.replace('title="오전 날씨','title="x').replace('title="오후 날씨','title="x'),'2026-10-26')]:
        with pytest.raises(ValueError):parse_forecast(doc,'1100000000',day,now=NOW)

def test_historical_weather_does_not_fetch_current(monkeypatch):
    import modules.briefing.weather as w
    monkeypatch.setattr(w.requests,'get',lambda *a,**k:pytest.fail('historical views must not fetch today'))
    assert get_weather(day='2020-01-01')['reason']=='historical'

def test_weather_failure_is_nonfatal(monkeypatch):
    import modules.briefing.weather as w
    monkeypatch.setattr(w.requests,'get',lambda *a,**k:(_ for _ in ()).throw(w.requests.Timeout()))
    _fetch.cache_clear()
    result=get_weather()
    assert result['status']=='unavailable'
    assert '예보를 불러오지 못했습니다' in weather_html(result)
    _fetch.cache_clear()

def test_cards_escape_text_and_link_title_and_footer():
    row={'title':'<script>bad()</script>','summary':'<img onerror=x>','category':'<b>분류</b>',
         'sources':[{'url':'https://example.com/news','source_name':'신문','published_at':'2026-10-26T07:00:00+09:00'}]}
    markup=article_html(row,lead=True)
    assert '<script>' not in markup and '<img ' not in markup
    assert markup.count('https://example.com/news')==2
    assert 'hw-news lead' in markup and '원문 ↗' in markup
    row['sources'][0]['url']='javascript:alert(1)'
    assert 'javascript:' not in article_html(row)

def test_weather_only_on_selected_news_panel_and_customer_identity_stays():
    w=parse_forecast(DOC,'1100000000','2026-10-26',now=NOW)
    packet={'sender':{'name':'박병선','position':'팀장'},'briefing_date':'2026-10-26','body':{
        'profile_code':'COMBINED','sections':[{'profile_code':'MARKET','profile_label':'경제·금융'},{'profile_code':'NEWS','profile_label':'종합뉴스'}],
        'issues':[],'weather_forecast':w}}
    markup=public_html(packet)
    assert markup.count('data-weather-date=')==1
    assert markup.index('id="section-1"')<markup.index('data-weather-date=')
    assert markup.index('박병선 팀장')<markup.index('role="tabpanel"')
    assert 'ArrowRight' in markup and '서울특별시' in markup
