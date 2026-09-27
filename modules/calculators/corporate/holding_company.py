"""Domestic dividend exclusion under current ordinary rule, single investee."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
NAME='지주회사 수입배당금계산기';M=10**12;YN=('아니요','예');RULES=('현행 일반 규정','종전 지주회사 경과규정 (적용 범위 밖)');STATUS=('미확인','적용 대상 확인','적용 제외 확인')
FIELDS={NAME:[('적용 규정',RULES[0],'선택',RULES),('수입배당금',200000000,'원',M),('배당기준일 현재 3개월 이상 계속 보유한 지분율',80,'%',100),('배당 유형·법인·보유기간의 적용 대상 여부',STATUS[0],'선택',STATUS),('손금불산입 이자 제외 후 법정 차입금 이자',0,'원',M),('해당 주식 장부가액 적수',0,'원·일',365*M),('자산총액 적수',0,'원·일',365*M),('이자·적수 및 조정항목 확인','아니요','선택',YN),('익금불산입 전 배당 포함 조정소득',500000000,'원',M),('익금불산입 전 당기 손실',0,'원',M),('세액 비교용 조정소득 확인','아니요','선택',YN),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YN)]}
def holding(rule=RULES[0],dividend=200000000,share=80,status=STATUS[0],interest=0,stock_days=0,asset_days=0,adjusted='아니요',income=500000000,loss=0,base_confirmed='아니요',small='아니요'):
 if rule!=RULES[0]:raise ValueError('종전 지주회사 경과규정은 적용 자격·구간별 검증이 남아 있어 아직 지원하지 않습니다.')
 if status not in STATUS or any(x not in YN for x in (adjusted,base_confirmed,small)):raise ValueError('확인 조건을 선택하세요.')
 dividend,interest,income,loss=map(num,(dividend,interest,income,loss));share=num(share,0,100)
 stock_days=num(stock_days,0,365*M);asset_days=num(asset_days,0,365*M)
 if income and loss:raise ValueError('조정소득과 당기 손실 중 한 가지만 입력하세요.')
 if interest and asset_days<=0:raise ValueError('이자가 있으면 자산총액 적수를 입력하세요.')
 rate=D(1) if share>=50 else D('.8') if share>=20 else D('.3')
 notes=['법령 대조일 2026-09-27 · 법인세법18조의2(2026-07-01), 시행령17조의2(2026-02-27). 단일 국내 피출자법인의 현행 일반 익금불산입 규정입니다.',
 '지분율50% 이상100%,20% 이상50% 미만80%,20% 미만30%. 배당기준일 현재3개월 이상 계속 보유한 주식 기준 지분입니다. 최근 취득주식 배당 등 적용 제외 금액을 섞지 않습니다.',
 '이자 차감=법정 차입금 이자×해당 주식 세무상 장부가액 적수÷자산총액 적수×익금불산입률. 이미 손금불산입한 이자는 제외하고, 국가·지자체 현물출자 주식 등 법정 조정을 확인합니다. 적수는 일별 잔액 합계이며 기말잔액이 아닙니다.',
 '배당 유형·보유기간·지급법인·수취법인에 따른 적용 제외는 확인 입력입니다. 여러 피출자법인의 차감 합산·일별 원장·적격 판정 자동화·외국법인 배당·종전 지주회사 경과규정은 미지원입니다.',
 '국세 절감은 익금불산입 전후 산출세액 차이입니다. 기존 법인세 엔진을 공유하며2026년 개시12개월 사업연도 기준입니다. 조정소득은 수입배당금 포함, 익금불산입 전 금액입니다. 이월결손금·공제감면·최저한세·지방세·기납부·단기사업연도는 미반영합니다.']
 if status==STATUS[0] or (status==STATUS[1] and adjusted!='예'):
  return FinanceResult({'익금불산입액':'배당 적용요건·이자 조정 확인 필요','지분에 따른 기준 비율':f'{rate*100:.0f}%'},'배당×비율−법정 이자 배분액. 조정사항 확인 후0원 하한 적용.',notes)
 deduction=interest*stock_days/asset_days*rate if interest and status==STATUS[1] else D(0)
 exclusion=max(D(0),dividend*rate-deduction) if status==STATUS[1] else D(0)
 metrics={'익금불산입액':exclusion,'익금 산입 배당금':dividend-exclusion,'지분에 따른 기준 비율':f'{rate*100:.0f}%','지급이자 차감 계산액':deduction,'국세 산출세액 절감 추정':'조정소득 확인 필요'}
 if base_confirmed=='예':
  before=max(D(0),income-loss);after=max(D(0),income-loss-exclusion)
  metrics.update({'국세 산출세액 절감 추정':bracket(before,small=='예')-bracket(after,small=='예'),'적용 전 과세표준 단순 추정':before,'적용 후 과세표준 단순 추정':after})
 return FinanceResult(metrics,'익금불산입=max(0,배당×법정 비율−이자×주식 적수÷자산 적수×비율). 세액 비교는 전후 누진세액 차이.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return holding(*values)
