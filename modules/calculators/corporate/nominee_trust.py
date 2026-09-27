"""Scoped 2026 nominee-share deemed gift assessment, distinct from return."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.gift_tax import ordinary_tax
NAME='명의신탁주식계산기';M=10**12
MODES=('2026년 최초 명의신탁','실제 소유자에게 환원')
PROOF=('미확인·입증하지 못함','조세회피 목적 없음 입증 확인')
YN=('아니요','예')
FIELDS={NAME:[('검토 거래',MODES[0],'선택',MODES),('명의신탁일 기준 확인된 주식 평가액',500000000,'원',M),('조세회피 목적 검토',PROOF[0],'선택',PROOF),('환원 상대방이 실제 소유자임을 확인','아니요','선택',YN)]}
def assess(mode=MODES[0],value=500000000,proof=PROOF[0],owner='아니요'):
 if mode not in MODES or proof not in PROOF or owner not in YN:raise ValueError('거래와 입증 상태를 확인하세요.')
 value=num(value)
 notes=['법령 대조일 2026-09-26 · 상속세 및 증여세법4조의2·45조의2·47·55·56. 2026년 최초 명의신탁의 증여의제 산출세액을 계산합니다.',
 '주식 평가액과 명의신탁 성립일은 확인 입력입니다. 미명의개서의 의제시기·취득일 평가, 과거 연도, 주식평가 자동화는 지원하지 않습니다.',
 '합산배제 재산으로 일반 가족관계 공제와 다른 10년 증여를 적용하지 않습니다. 과세표준50만원 미만은 과세최저한을 반영합니다. 납세의무자는 실제 소유자입니다.',
 '표시 금액은 산출세액입니다. 신고세액공제·감정수수료·가산세·기납부세액을 반영한 최종 납부세액이 아닙니다. 조세회피 목적 없음의 입증은 자동 판정하지 않습니다.',
 '실제 소유자에게 환원하는 거래 자체와 최초 명의신탁 과세는 별개입니다. 환원이 확인돼도 최초 명의신탁 증여세·배당소득세 등이 사라지지 않습니다.']
 if mode==MODES[1]:
  metrics={'환원 거래 자체 증여세':D(0) if owner=='예' else '실제 소유자 확인 필요','최초 명의신탁 세액':'당시 법령·평가액으로 별도 검토','현재 거래 판정':'실소유자 환원 확인' if owner=='예' else '판정 보류'}
 else:
  excluded=proof==PROOF[1];base=D(0) if excluded else value
  metrics={'명의신탁 증여세 산출세액':ordinary_tax(base) if base>=500000 else D(0),'증여세 과세표준':base,'판정':'입증 확인을 전제로 과세 제외' if excluded else '명의신탁 과세요건 충족을 전제로 한 추정','최종 납부세액':'공제·가산세 등 별도 확인'}
 return FinanceResult(metrics,'최초 명의신탁: 확인된 평가액에 증여세 누진세율 적용. 입증된 과세 제외 및 실소유자 환원은 별도 구분.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return assess(*values)
