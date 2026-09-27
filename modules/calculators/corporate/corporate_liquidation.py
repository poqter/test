"""Separate corporate tax basis, distributable cash, and shareholder cost."""
from modules.calculators.corporate.shareholder_distribution import *
from modules.calculators.corporate.corporate_tax import bracket
NAME='법인청산 세부담계산기';YN=('아니요','예')
FIELDS={NAME:[('세무조정 후 청산 잔여재산가액',2000000000,'원',M),('조정 후 자기자본 총액 (자본금+잉여금 등)',100000000,'원',M),
 ('청산 재산·자기자본의 세무조정 확인','아니요','선택',YN),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YN),
 ('청산 법인세 차감 전 실제 분배 가능 재산',2000000000,'원',M),('해당 주주 분배 비율',100,'%',100),('해당 주식 세무상 취득가액',100000000,'원',M),*TAX_FIELDS]}
def liquidation(residual=2000000000,equity=100000000,confirmed='아니요',small='아니요',pool=2000000000,share=100,basis=100000000,other_financial=0,other=0,deductions=1500000,mode=MODES[0],confirmed_tax=0):
 residual,equity,pool,basis=map(num,(residual,equity,pool,basis));share=num(share,0,100)/100
 if confirmed not in YN or small not in YN:raise ValueError('법인 조건을 확인하세요.')
 if confirmed!='예':
  # Do not confuse illustrative book values with a settled corporate tax basis.
  for x in (other_financial,other,deductions,confirmed_tax):num(x)
  if mode not in MODES:raise ValueError('과세 방식을 확인하세요.')
  return FinanceResult({'청산 법인세 차감 전 분배 재산':pool,'청산 과세표준·세액':'세무조정 확인 필요','주주 세후 수령 추정':'세무조정 확인 필요'},'조정된 잔여재산과 자기자본을 확인한 후 계산합니다.',[f'법령 대조 기준일 {AS_OF}',*LIQ_NOTES,*NOTES])
 base=max(D(0),residual-equity);national=bracket(base,small=='예');local=national/10;company=national+local
 if company>pool:raise ValueError('분배 재산이 청산 세액보다 작습니다. 추가 납부재원과 재산·부채를 확인하세요.')
 dist=(pool-company)*share
 metrics=distribution(dist,basis,other_financial,other,deductions,mode,confirmed_tax)
 metrics={'청산 과세표준':base,'청산 법인세 국세':national,'청산 법인지방소득세':local,'회사 청산세 합계':company,'회사 세후 분배 가능 재산':pool-company,**metrics}
 # A single shareholder's tax must not be labelled the entire company's total burden.
 return FinanceResult(metrics,'청산 과표=max(0, 조정 잔여재산−조정 자기자본). 국세·지방세 차감 후 분배재산×주주 비율. 의제배당=max(0, 주주 분배액−주식 취득가액).',LIQ_NOTES+NOTES,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
LIQ_NOTES=['법인세법79·83조, 지방세법103조의41·42. 2026년 세율 기준 일반 내국 영리법인 해산이며 합병·분할·조직변경은 미지원입니다.',
 '자기자본은 납입자본금만이 아닙니다. 잉여금, 환급법인세 가산, 잉여금 한도 결손금 상계, 2년 내 자본전입을 검토한 조정 후 금액을 입력합니다. 음수 자기자본과 특수 청산은 지원하지 않습니다.',
 '청산 과세용 잔여재산과 현금·현물 분배재산을 구분합니다. 부채·청산비용·각 사업연도 소득과 세금은 입력 전 정산하고, 여기서 계산하는 청산세는 분배재산에 아직 차감하지 않은 전제입니다. 이미 차감한 청산세를 이중 차감하지 마세요.',
 '현물 평가, 재산 환가, 결손금 원장과 자기자본 조정은 자동 판정하지 않습니다. 기납부 청산세가 없는 단일 최종분배 가정이며 분할분배·중간신고·기납부·가산세·지방세 안분은 미지원입니다.',
 '분배비율은 주주 한 명의 적법하게 확정된 비율입니다. 모든 주주의 개인세 합계나 차등분배에 따른 증여세는 계산하지 않습니다.']
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return liquidation(*values)
