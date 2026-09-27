"""Incremental national tax comparison for a single confirmed property disposal."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.capital_gains_tax import gains, ASSETS
from modules.calculators.corporate.corporate_tax import bracket
NAME='법인 부동산 보유·양도 비교계산기';M=10**12;YN=('아니요','예')
EXTRA=('미확인','추가과세 없음 확인','주택 20% 적용 확인','비사업용 토지 10% 적용 확인')
FIELDS={NAME:[('양도일 (2026년)','2026-09-27','날짜',0),('취득일','2021-09-27','날짜',0),
 ('자산 종류',ASSETS[0],'선택',ASSETS),('양도가액',1500000000,'원',M),
 ('개인 취득가액 (세무상 조정·부대비용 반영)',1000000000,'원',M),('개인 별도 필요경비',0,'원',M),
 ('법인 양도 당시 세무상 장부가액',1000000000,'원',M),('법인 일반소득에서 손금 인정되는 양도비용',0,'원',M),
 ('매각 반영 전 법인 과세표준 (결손금 없는 경우)',0,'원',M),('법인 토지등 양도 추가과세 구분',EXTRA[0],'선택',EXTRA),
 ('개인 비사업용 토지 해당','아니요','선택',YN),('개인 1세대 1주택 비과세 요건 확인','아니요','선택',YN),
 ('개인 실제 거주 만 연수',0,'년',100),('개인 올해 남은 양도 기본공제',2500000,'원',2500000),
 ('개인 일반 단독·단일 양도 및 법인 12개월 일반과세·등기·과세 조건 확인','아니요','선택',YN)]}
def estate(transfer='2026-09-27',acquire='2021-09-27',asset=ASSETS[0],sale=1500000000,cost=1000000000,expenses=0,book=1000000000,corp_expenses=0,corp_base=0,extra=EXTRA[0],nonbusiness='아니요',qualified='아니요',residence=0,basic=2500000,confirmed='아니요'):
 sale,cost,expenses,book,corp_expenses,corp_base=map(num,(sale,cost,expenses,book,corp_expenses,corp_base))
 if asset not in ASSETS or extra not in EXTRA or any(v not in YN for v in (nonbusiness,qualified,confirmed)):raise ValueError('자산 종류·과세 조건을 확인하세요.')
 if extra==EXTRA[2] and asset!='주택' or extra==EXTRA[3] and asset!='토지':raise ValueError('법인 추가과세 구분과 자산 종류가 맞지 않습니다.')
 notes=['법령 대조일 2026-09-27 · 2026년 단일 국내 부동산 매각의 국세 비교. 소득세법 제95·103·104조 및 법인세법 제55·55조의2.',
 '개인은 기존 양도소득세 계산을 공유합니다. 등기된 직접 매입·단독 소유·단일 양도이며 다주택 중과·지정지역 추가 중과·분양권·겸용 등 특례는 지원하지 않습니다. 취득가액은 감가상각 등 필요한 세무상 조정을 반영한 값입니다.',
 '법인은 2026년 개시 12개월 일반법인입니다. 소규모 특례법인·결손금·감면·공제·다른 부동산 양도손익 통산은 미반영합니다. 양도 장부가액과 비용은 개인 취득가액과 별도로 확인합니다.',
 '법인 일반세액은 매각 반영 전후 누진세액 차이입니다. 매각손실로 인한 음수 세액은 기존 소득에 대한 당기 산출세액 감소를 뜻합니다. 과세표준은0원 하한이며 초과손실의 이월 효과는 계산하지 않습니다. 토지등 추가과세는 양도가액−장부가액에 확인된 세율을 적용하며 일반소득의 양도비용을 다시 빼지 않습니다.',
 '추가과세 적용·제외는 별도 확인합니다. 주택 임대 유형·비사업용 판정 등 요건 자동심사는 지원하지 않습니다. 미등기·권리 양도는 대상이 아닙니다.',
 '국세만 비교합니다. 지방소득세·취득세·보유세·부가가치세·배당 등 법인 자금 인출 세금·가산세·신고 단수처리는 제외합니다. 법인과 개인 중 어느 소유 방식이 전체적으로 유리한지를 단정하지 않습니다.']
 formula='개인: 기존 양도세 엔진의 국세. 법인: 세율함수(기존과표+매각일반소득)−세율함수(기존과표)+토지등 추가과세.'
 if confirmed!='예' or extra==EXTRA[0]:return FinanceResult({'매각 국세 비교':'개인·법인 과세 범위와 추가과세 구분 확인 필요'},formula,notes)
 personal=gains(transfer=transfer,acquire=acquire,asset=asset,sale=sale,cost=cost,expenses=expenses,basic=basic,nonbusiness=nonbusiness,qualified=qualified,residence=residence)
 ordinary_gain=sale-book-corp_expenses
 regular=bracket(max(D(0),corp_base+ordinary_gain))-bracket(corp_base)
 additional_base=max(D(0),sale-book);extra_rate={EXTRA[1]:D(0),EXTRA[2]:D('.2'),EXTRA[3]:D('.1')}[extra]
 additional=additional_base*extra_rate;corporate=regular+additional;individual=personal.metrics['소득세']
 metrics={'개인 매각 국세 추정':individual,'법인 매각 국세 증가 추정':corporate,'개인−법인 국세 차이':individual-corporate,'법인 일반 법인세 증가':regular,'법인 토지등 양도 추가세액':additional}
 rows=[dict(구분='개인',**r) for r in personal.rows if r['항목']!='지방세']
 rows += [{'구분':'법인','항목':k,'금액':v} for k,v in [('매각 일반소득',ordinary_gain),('기존 과세표준',corp_base),('매각 후 과세표준',max(D(0),corp_base+ordinary_gain)),('추가과세 대상 소득',additional_base),('일반세액 증가',regular),('토지등 추가세액',additional)]]
 return FinanceResult(metrics,formula,notes,rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return estate(*values)
