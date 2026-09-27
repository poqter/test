"""Maturity/cancellation cash and tax-basis reconciliation, not officer transfer."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='법인보험 만기계산기';M=10**12
MODES=('만기 수령','중도 해약','대표에게 계약자 변경')
FIELDS={NAME:[('처리 유형',MODES[0],'선택',MODES),('원천징수 전 수령액 / 계약 이전 시 확인 평가액',200000000,'원',M),
 ('제거할 회계 장부상 보험자산',150000000,'원',M),('세무조정 반영 후 세무상 보험자산 잔액',150000000,'원',M),
 ('보험 정산 전 당기 세무상 소득 (손실은 음수)','0','문자',30),
 ('과거 비용처리·유보 및 세무상 잔액 확인','아니요','선택',('아니요','예')),
 ('법60조의2 제1항1호 소규모법인 해당','아니요','선택',('아니요','예')),
 ('실제 원천징수된 국세·지방세 합계',0,'원',M)]}
from modules.calculators.corporate.insurance_transfer import FIELDS as TRANSFER_FIELDS
FIELDS[NAME]+=TRANSFER_FIELDS
def maturity(mode=MODES[0],received=200000000,book=150000000,tax_basis=150000000,income='0',confirmed='아니요',small='아니요',withheld=0,*transfer_values):
 if mode not in MODES or confirmed not in ('아니요','예') or small not in ('아니요','예'):raise ValueError('보험 및 법인 구분을 확인하세요.')
 if mode==MODES[2]:
  if confirmed!='예':raise ValueError('세무상 보험자산과 이전 조건을 확인하세요.')
  if withheld:raise ValueError('계약 이전은 보험금 원천징수액을 0으로 입력하세요. 개인 세액을 별도 계산합니다.')
  from modules.calculators.corporate.insurance_transfer import transfer
  return transfer(received,book,tax_basis,income,small,*transfer_values)
 received,book,tax_basis,withheld=map(num,(received,book,tax_basis,withheld));income=num(income,-M,M)
 if withheld>received:raise ValueError('원천징수액은 보험 수령액 이하여야 합니다.')
 accounting=received-book;profit=received-tax_basis;adjustment=book-tax_basis
 before=max(D(0),income);after=max(D(0),income+profit)
 delta=(bracket(after,small=='예')-bracket(before,small=='예'))*D('1.1')
 metrics={'원천징수 후 실제 입금액':received-withheld,'회계상 보험 정산손익':accounting,
 '세무상 보험 정산손익':profit if confirmed=='예' else '세무상 잔액 미확인',
 '회계손익 대비 세무조정':adjustment if confirmed=='예' else '세무상 잔액 미확인',
 '국세·지방세 산출세액 증감':delta if confirmed=='예' else '세무상 잔액 미확인',
 '정산 후 과세표준 추정':after if confirmed=='예' else '세무상 잔액 미확인',
 '세액 증감 반영 경제적 유입 추정':received-delta if confirmed=='예' else '세액 확인 필요'}
 return FinanceResult(metrics,'회계손익=수령액−회계자산. 세무손익=수령액−확인된 세무자산. 정산 전후 양의 소득에 공통 법인세 누진함수를 적용한 차이가 산출세액 증감. 실제 입금은 수령액−원천징수액.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법15·19·55조, 국세청 보험료 자산·손금 구분 해석 및 공통 법인세 계산식 · 2026년12개월 내국법인.',
 '과거 납입보험료 전액을 자동 차감하지 않습니다. 기존 손금처리분을 다시 차감하면 중복 공제가 됩니다. 장부자산과 세무상 자산은 유보 등으로 다를 수 있어 각각 입력합니다.',
 '보험료의 비용·자산 구분은 보험계약과 수익자·환급조건에 따라 달라집니다. 이 화면은 그 적정성을 자동 판정하지 않고 확인된 세무상 잔액을 사용합니다.',
 '보험 정산 전 소득에는 이번 보험손익을 중복 포함하지 않습니다. 이월결손금·비과세·소득공제·세액공제·최저한세·특별세 등은 미반영입니다. 손실은0으로 버리지 않고 당기 소득 감소에 반영하되, 남는 결손금의 미래 세금효과는 계산하지 않습니다.',
 '산출세액 증감이 음수이면 당기 산출세액 감소 추정입니다. 실제 입금액과 세금효과를 반영한 경제적 비교값은 다릅니다. 원천징수는 기납부세액이므로 경제적 비교에서 세금과 이중 차감하지 않습니다. 실제 추가 납부·환급은 기납부세액 전체로 정산해야 합니다.',
 '대표자에게 계약을 넘기는 거래는 별도 분기이며 실제 퇴직·한도 확인 없이 전액 퇴직급여로 간주하지 않습니다. 개인의 보험차익 비과세 요건을 법인에 그대로 적용하지 않습니다.'],
 [{'항목':'회계상 제거자산','금액':book},{'항목':'세무상 제거자산 입력','금액':tax_basis},
 {'항목':'보험 정산 전 소득','금액':income},{'항목':'원천징수 기납부세액','금액':withheld}])
def calculate(name,values):
 if name!=NAME or len(values) not in (8,len(FIELDS[NAME])):raise ValueError('입력 항목을 확인하세요.')
 return maturity(*values)
