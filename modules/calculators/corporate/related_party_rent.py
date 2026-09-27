"""Corporate related-party annual rent, adverse direction and statutory threshold."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
NAME='특수관계자 임대료계산기';M=10**12
DIRECTIONS=('법인이 임차','법인이 임대');METHODS=('시가 미확인','비교 가능한 시가 확인','보충적 산식 적용요건 확인');YN=('아니요','예')
FIELDS={NAME:[('거래 방향',DIRECTIONS[0],'선택',DIRECTIONS),('실제 연간 임대료',24000000,'원',M),('시가 확인 방법',METHODS[0],'선택',METHODS),('확인된 시가 연간 임대료',20000000,'원',M),('부동산 시가',1000000000,'원',M),('임대보증금',0,'원',M),('특수관계·적용대상 및 예외 없음 확인','아니요','선택',YN)]}
def assess(direction=DIRECTIONS[0],actual=24000000,method=METHODS[0],market=20000000,property_value=1000000000,deposit=0,confirmed='아니요'):
 if direction not in DIRECTIONS or method not in METHODS or confirmed not in YN:raise ValueError('계산 조건을 확인하세요.')
 actual,market,property_value,deposit=map(num,(actual,market,property_value,deposit))
 notes=['법령 대조일 2026-09-26 · 법인세법 시행령88조1항6·7호 및3항,89조1·2·4·5항, 시행규칙6조. 정기예금이자율 연3.1%.',
 '연간 일정한 임대조건·동일 보증금 기준·부가세 제외 금액을 비교합니다. 단기 계약·기간 중 조건변경·현물 대가·개인 상대방 과세는 별도 검토합니다.',
 '비교 가능한 제3자 거래 시가와 법정 평가 순서를 먼저 적용합니다. 보충적 산식은89조1·2항을 적용할 수 없는 경우에만 선택하세요. 부동산 시가50%에서 보증금을 차감한 금액에 연3.1%를 곱합니다.',
 '법인 임차의 고가 지급은 손금불산입, 법인 임대의 저가 수취는 익금산입 검토 대상입니다. 차액3억원 이상 또는 시가5% 이상 기준을 적용합니다.',
 '세무조정 검토액이며 법인세 또는 확정 처분금액이 아닙니다. 특수관계 여부·사택 등 예외·경제적 합리성·소득처분·원천징수를 자동 판정하지 않습니다. 반대 방향 거래도 상대방 세금이 없다는 뜻이 아닙니다.']
 if method==METHODS[0]:return FinanceResult({'세무조정 검토액':'시가 확인 필요','판정':'보류'},'동일 조건의 연간 시가를 확인한 후 거래 방향별 차액과 법정 기준을 비교합니다.',notes)
 if method==METHODS[2]:
  if deposit>property_value/2:raise ValueError('보증금이 부동산 시가의50%를 초과합니다. 음수 임대료로 판정하지 않으며 별도 시가 검토가 필요합니다.')
  market=(property_value/2-deposit)*D('.031')
 signed=actual-market;adverse=max(D(0),signed if direction==DIRECTIONS[0] else -signed)
 threshold=adverse>0 and (adverse>=300000000 or adverse>=market*D('.05'))
 adjustment=adverse if threshold else D(0)
 metrics={'세무조정 검토액':adjustment if confirmed=='예' else '적용요건 확인 필요','비교 시가 연간 임대료':market,'실제 임대료 − 시가':signed,'법인에 불리한 차액':adverse,'시가 대비 절대 차이율':f'{abs(signed)/market*100:.2f}%' if market else '시가0원: 비율 계산 불가','금액·비율 기준':'충족' if threshold else '미충족','조정 검토 유형':('손금불산입' if direction==DIRECTIONS[0] else '익금산입') if threshold else '이 계산의 조정 대상 없음'}
 return FinanceResult(metrics,'불리한 차액≥3억원 또는 불리한 차액≥시가×5%일 때 거래 방향별 세무조정 검토.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return assess(*values)
