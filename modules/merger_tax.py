"""2026 absorbed-company incremental corporate tax, Article44/55."""
from .finance_models import D,num,period,FinanceResult
from .corporate_tax import bracket
NAME='합병 세부담계산기';M=10**12;YN=('아니요','예');MODES=('미확인: 비적격 가정 비교','적격 요건 및 장부가액 적용 확인')
FIELDS={NAME:[('세무상 확정 양도가액',5000000000,'원',M),('세무상 자산 장부가액',3000000000,'원',M),('세무상 부채 장부가액',0,'원',M),('합병손익 반영 전 과세소득 (손실은 다음 칸)',0,'원',M),('합병손익 반영 전 당기 손실',0,'원',M),('법정 사업연도 월수 (1개월 미만 끝수 포함 여부 확인)',12,'개월',12),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YN),('적격합병 적용',MODES[0],'선택',MODES)]}
def merger(consideration=5000000000,assets=3000000000,liabilities=0,income=0,loss=0,months=12,small='아니요',mode=MODES[0]):
 consideration,assets,liabilities,income,loss=map(num,(consideration,assets,liabilities,income,loss));months=period(months,12)
 if small not in YN or mode not in MODES:raise ValueError('적용 조건을 확인하세요.')
 if income and loss:raise ValueError('동일한 합병 전 소득과 손실을 중복 입력하지 마세요.')
 net=assets-liabilities;gain=consideration-net;base=income-loss
 def tax(v):
  annual=max(D(0),v)*12/D(months)
  if annual>3*M:raise ValueError('연환산 과세표준이 지원 범위를 초과합니다.')
  return bracket(annual,small=='예')*D(months)/12
 before=tax(base);nonqualified=tax(base+gain);delta=nonqualified-before
 applied_gain=D(0) if mode==MODES[1] else gain;after=tax(base+applied_gain)
 metrics={'합병에 따른 국세 산출세액 증감':after-before,'비적격 가정 국세 증감':delta,'순자산 장부가액':net,'비적격 가정 양도손익':gain,'적용 양도손익':applied_gain,'합병 전 국세 산출세액':before,'합병 반영 후 국세 산출세액':after,'법인지방소득세 및 주주 세금':'별도 계산 필요','판정':mode}
 notes=['법령 대조일 2026-09-26 · 법인세법44조·55조. 2026년 개시 국내 피합병법인의 일반소득 국세 산출세액 비교입니다.',
 '양도손익=세법상 양도가액−(세무상 자산−부채). 시가를 양도가액으로 자동 대체하지 않습니다. 양도가액은 합병대가 및 법정 가감액을 검토한 확정 수치입니다. 납입자본금은 순자산 장부가액이 아닙니다.',
 '기존 법인세 누진 계산식을 공유합니다. 1년 미만 사업연도는 과표를12개월로 환산해 세율 적용 후 월수/12를 곱합니다. 법정 월수는 확인 입력이며 날짜 자동산정은 지원하지 않습니다.',
 '적격 요건 및 장부가액 적용을 확인한 경우 양도손익0을 적용합니다. 사업계속·주식대가80%·주주보유·고용승계 등 요건과 예외는 자동 판정하지 않습니다.',
 '적격합병은 영구 면세가 아닙니다. 미래 자산처분·사후관리 위반·자산조정계정·주주 의제배당·취득세·지방소득세는 이 결과에 포함하지 않습니다. 국세 결과를 전체 합병 세금으로 제시하지 않습니다.',
 '이월결손금·공제감면·최저한세·추가법인세·기납부세액은 미반영입니다. 음수 증감은 당기 산출세액 감소이며 환급 확정액이 아닙니다. 합병 전 손실은 당기 손실만 입력합니다.']
 return FinanceResult(metrics,'합병 후 산출세액−합병 전 산출세액. 적격 장부가 적용 시 양도손익0; 비적격은 실제 양도가액−순자산 장부가액.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return merger(*values)
