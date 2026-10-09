"""All prices/articles here are clearly synthetic; never production data."""
from datetime import datetime,timezone,timedelta
from modules.briefing.market_metrics import METRICS,validated_metrics
AS_OF=datetime(2026,10,8,22,30,tzinfo=timezone.utc)


def observations(external=True):
    rows=[]
    for i,(code,(label,unit)) in enumerate(METRICS.items()):
        rows.append({'code':code,'instrument_code':code,'value':4.2 if code=='US10Y' else 1000+i*200,
            'previous_value':4.1 if code=='US10Y' else 990+i*200,'unit':unit,
            'observed_at':(AS_OF-timedelta(hours=2)).isoformat(),'previous_observed_at':(AS_OF-timedelta(days=1,hours=2)).isoformat(),
            'source_name':'검수용 가상 관측','source_url':'https://example.org/metric/'+code,
            'observation_kind':'nominal_treasury_yield' if code=='US10Y' else 'spot_exchange_rate' if code=='USDKRW' else 'closing_index',
            'display_allowed':True,'external_allowed':external,'license_reference':'synthetic-test-license' if external else '',
            'provider':'synthetic','reference_definition':'검수용 가상 데이터 · 실시간 시세 아님'})
    return rows


def content(code='NEWS',count=10,external=True):
    return {'profile_code':code,'profile_label':{'NEWS':'종합뉴스 브리핑','MARKET':'경제·금융 브리핑','INSURANCE':'보험업계 브리핑'}[code],
        'as_of':AS_OF.isoformat(),'issues':[{'event_key':'event-'+str(i),'title':f'검수용 가상 소식 {i+1} · 독자가 쉽게 읽을 수 있는 제목',
            'summary':'레이아웃 검수용 가상 자료입니다. 실제 뉴스나 금융 관측을 뜻하지 않습니다.',
            'why_important':'새롭게 확인된 사실과 보도된 배경을 짧게 설명하는 영역입니다.',
            'impact_summary':'영향은 조건을 붙여 설명하고, 확인할 변수를 함께 표시합니다.',
            'representative':i==0,'category':'소비자·사회이슈' if code=='INSURANCE' else '사회·안전',
            'communication_state':'customer_ready','conversation_payload':{'internal_secret':'직원만 확인'},
            'sources':[{'title':'원문 기사','source_name':'검수용 출처','url':f'https://{"hankyung.com" if i%2 else "mk.co.kr"}/article/{i}',
                'published_at':(AS_OF-timedelta(hours=i+1)).isoformat()}]} for i in range(count)],
        'market_metrics':validated_metrics(observations(external),AS_OF) if code=='MARKET' else {},
        'market_flow':['검수용 가상 해설입니다. 지표 변화와 기사 배경을 함께 보여줍니다.','가정한 영향에는 조건을 붙입니다. 실제 투자 판단용 정보가 아닙니다.','다음 관측값과 기사 원문을 확인하는 안내 영역입니다.'] if code=='MARKET' else [],
        'internal_secret':'내부 정보','costs':{'key':'비밀'},'research':{}}


def packet(code='NEWS',count=10):
    from modules.briefing.sharing import build_packet
    return build_packet({'content_payload':content(code,count)}, {'briefing_date':'2026-10-09'},
        {'revision_no':1,'revision_type':'initial'}, {'name':'검수용 이름','position':'팀장'},
        'https://project.example.org/functions/v1/briefing-public','x'*43)
