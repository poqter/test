from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from modules.briefing.weather_detail import periods,parse_observation,detailed_html

NOW=datetime(2026,10,29,9,15,tzinfo=ZoneInfo('Asia/Seoul'))
OBS='<a class="updated-at"><span>10.29.(목) 09:00</span></a><span class="tmp">8.2<small>℃</small></span><span class="chill">체감(7.6℃)</span>'

def row(day,hour,pop,condition='흐림'):
    return f'<ul class="item vs-item" data-date="{day}" data-time="{hour}:00"><span class="wic DB04" title="{condition}"></span><span>강수확률: </span><span>{pop}%</span></ul>'

def test_observation_requires_fresh_valid_values():
    result=parse_observation(OBS,now=NOW)
    assert result['current']==8.2 and result['feels_like']==7.6
    for doc in [OBS.replace('09:00','06:00'),OBS.replace('8.2','999'),OBS.replace('10.29','10.28')]:
        with pytest.raises(ValueError):parse_observation(doc,now=NOW)
    assert parse_observation(OBS.replace('체감(7.6℃)','체감(-)'),now=NOW)['feels_like'] is None

def test_evening_only_today_and_max_not_next_day():
    doc=row('2026-10-29','19',20)+row('2026-10-29','24',70,'비')+row('2026-10-30','01',99)
    result=periods(doc,'2026-10-29')
    assert result[2]=={'label':'저녁','condition':'비','pop':70}
    assert result[0]['pop'] is None

def test_daily_summaries_preserve_elapsed_morning():
    doc='<div class="dfs-daily-slide" data-date="2026-10-29"><span title="오전 날씨 맑음"></span><div class="daily-pop-am"><strong>오전 강수확률</strong><span>0%</span></div></div>'
    assert periods(doc,'2026-10-29')[0]=={'label':'오전','condition':'맑음','pop':0}
    assert periods(row('2026-10-29','20',101),'2026-10-29')[2]['pop'] is None

def test_markup_distinguishes_unknown_and_zero_and_escapes():
    markup=detailed_html({'status':'ok','region_name':'<script>x</script>','current':0,'periods':[{'label':'오전','condition':'맑음','pop':0},{'label':'저녁','condition':'','pop':None}]})
    assert '0°' in markup and '강수 0%' in markup and '강수 —' in markup
    assert '<script>' not in markup and '현재 확인 불가' in markup
