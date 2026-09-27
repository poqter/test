"""General VAT taxpayer notice vs filing eligibility, not a VAT liability engine."""
from decimal import ROUND_DOWN
from .finance_models import D,num,FinanceResult
from .personal_tax_models import AS_OF
NAME='부가세 예정신고 선택계산기'
KINDS=('개인 일반과세자','법인 일반과세자');YN=('아니요','예')
FIELDS={NAME:[('사업자 구분',KINDS[0],'선택',KINDS),('직전6개월 법정 조정 후 납부세액',20000000,'원',10**12),
 ('직전6개월 공급가액',2000000000,'원',10**12),('이번3개월 공급가액',400000000,'원',10**12),
 ('이번3개월 예상세액 구분','납부','선택',('납부','환급')),('이번3개월 예상세액 절댓값',3000000,'원',10**12),
 ('조기환급 법정 요건 확인','아니요','선택',YN),('이번 과세기간 시작 시 간이→일반 전환','아니요','선택',YN)]}
def preliminary(kind=KINDS[0],prior_tax=20000000,prior_sales=2000000000,sales=400000000,mode='납부',amount=3000000,early='아니요',converted='아니요'):
 if kind not in KINDS or mode not in ('납부','환급') or early not in YN or converted not in YN:raise ValueError('사업자 및 세액 구분을 확인해 주세요.')
 if kind==KINDS[1] and converted=='예':raise ValueError('법인은 간이과세 전환 대상이 아닙니다.')
 prior_tax,prior_sales,sales,amount=map(num,(prior_tax,prior_sales,sales,amount))
 tax=amount if mode=='납부' else -amount;payment=max(D(0),tax)
 notice_target=kind==KINDS[0] or prior_sales<150000000
 raw=(prior_tax/2/1000).quantize(D(1),rounding=ROUND_DOWN)*1000
 notice=raw if notice_target and raw>=500000 and converted=='아니요' else D(0)
 decline=sales*3<prior_sales or tax*3<prior_tax
 optional=decline or early=='예'
 can_file=not notice_target or optional
 if not notice_target:status='예정신고 의무';choice='예정신고·납부';difference='비교 대상 아님'
 elif optional:
  status='예정신고 선택 가능'
  choice='예정신고 시 납부액 감소' if payment<notice else '납부액 감소 없음 — 환급·신고 사유 확인'
  difference=notice-payment
 else:status='선택 신고 요건 미충족';choice='예정고지 납부' if notice else '예정고지 징수 없음';difference='선택 신고 불가 — 차이 미표시'
 refund=max(D(0),-tax)
 return FinanceResult({'예정신고 구분':status,'예정고지 납부액':notice if notice_target else '고지 대상 아님',
 '가능한 처리':choice,'예정신고 시 납부 추정':payment if can_file else '선택 신고 불가',
 '선택 신고 시 당장 납부액 감소':difference,
 '조기환급 신청 추정':refund if can_file and early=='예' else D(0),
 '확정신고로 넘길 일반 환급 추정':refund if can_file and early=='아니요' else D(0)},
 '고지 대상: 개인 일반과세자 또는 직전 공급가액1.5억원 미만 법인. 조정 후 직전 세액50%에서 천원 미만 버림, 50만원 미만이면 미징수. 공급가액 또는 납부세액이 직전기간의1/3 미만이거나 조기환급 요건이면 선택 신고.',
 [f'법령 대조 기준일 {AS_OF} · 부가가치세법48조, 시행령90조·107조 · 계속사업 일반과세자 예정신고 판단.',
 '직전 납부세액은 법48조의 공제·감면과 결정·경정 등을 반영한 금액입니다. 현재 예상세액은 매출·매입세액과 공제 등을 별도로 계산한 확인액이며 공급가액만으로 산출하지 않습니다.',
 '정확히1/3이면 사업부진 요건에 해당하지 않습니다. 예정고지 대상이 아닌 법인은 선택 비교 없이 예정신고 의무로 표시합니다. 일반과세 전환자 및 50만원 미만은 고지를 징수하지 않습니다.',
 '선택 신고를 하면 해당 예정고지는 없었던 것으로 봅니다. 납부액 차이는 당장 자금 차이이며 연간 세금 절감액이 아닙니다. 음수는 오히려 추가 납부입니다.',
 '일반 환급액은 예정신고만으로 즉시 환급되지 않습니다. 조기환급은 영세율·사업설비 등 법정 자격과 적격 신고를 따로 확인한 경우에만 신청 추정액으로 표시합니다.',
 '법정 예정기간은1~3월 및7~9월이며 종료 후25일 이내 신고·납부합니다. 공휴일·토요일 및 개별 기한 연장 적용은 실제 고지서와 신고 안내를 확인하세요. 신설·폐업·면세·간이과세자·수시부과·세무서 별도 미징수 사유는 이 화면 범위 밖입니다.'],
 [{'판정 항목':'공급가액 부진','해당':'예' if sales*3<prior_sales else '아니요'},
 {'판정 항목':'납부세액 부진','해당':'예' if tax*3<prior_tax else '아니요'},
 {'판정 항목':'조기환급 자격 확인','해당':early}])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return preliminary(*values)
