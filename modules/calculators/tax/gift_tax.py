"""Ordinary gift tax using confirmed valuations and prior-assessment amounts.

Never infer historical deductions/taxes from today's relationship or rates.
Prior figures are reconciled aggregates from the relevant 10-year ledger.
"""
from datetime import date
import calendar
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import AS_OF
from modules.calculators.tax.transfer_tax_rules import ordinary_tax

NAME='증여세계산기'
RELATIONS=('배우자에게','성년 자녀·손자녀에게','미성년 자녀·손자녀에게','부모·조부모에게','기타 친족에게 (4촌 혈족·3촌 인척)','그 밖의 사람에게')
ALLOWANCES=(600000000,50000000,20000000,50000000,10000000,0)
YESNO=('아니요','예')
SPECIAL=('미적용','혼인신고일 전후 2년 요건 확인','출생·입양일부터 2년 요건 확인')
M=10**12
FIELDS={NAME:[
 ('증여일 (2026년 증여)',AS_OF,'날짜',0),
 ('받는 사람과의 관계',RELATIONS[0],'선택',RELATIONS),
 ('받는 사람은 국내 거주자','예','선택',YESNO),
 ('부동산 세법상 평가액',0,'원',M),
 ('현금·예금',1000000000,'원',M),
 ('상장주식 최종 평가액 (필요한 할증 반영 후)',0,'원',M),
 ('비상장주식 최종 평가액 (필요한 할증 반영 후)',0,'원',M),
 ('채권·증권 최종 평가액',0,'원',M),
 ('기타 과세대상 재산 평가액',0,'원',M),
 ('객관적으로 입증된 인수채무 (부담부증여)',0,'원',M),
 ('해당 관계군에서 지난 10년간 사용한 일반 증여공제 총액',0,'원',600000000),
 ('혼인·출산 추가 공제 요건',SPECIAL[0],'선택',SPECIAL),
 ('혼인·출산 공제를 이미 받은 누적 금액 (10년 제한 없음)',0,'원',100000000),
 ('이번 혼인·출산 공제 신청액',0,'원',100000000),
 ('이번 적격 감정평가수수료 (법정 한도 확인 후)',0,'원',M),
 ('이번 적격 재해손실 공제액',0,'원',M),
 ('10년 이내 동일인 과거 증여 과세가액 합계 (직계존속 배우자 포함)',0,'원',M),
 ('위 합산 재산의 과거 공제·평가수수료 합계 (중복 없이)',0,'원',M),
 ('위 합산 재산에 대응하는 과거 과세표준 (공제한도 검토용)',0,'원',M),
 ('위 합산 재산의 과거 산출세액 (신고공제 전·할증 제외·중복 없이)',0,'원',M),
 ('위 과거 재산 중 세대생략 할증 대상 재산가액',0,'원',M),
 ('위 과거 재산에 종전에 납부한 세대생략 할증액',0,'원',M),
 ('이번 증여는 손자녀 등 세대생략 대상','아니요','선택',YESNO),
 ('최근친 사망에 따른 세대생략 예외 요건 확인','아니요','선택',YESNO),
 ('기한 내 적정 신고로 3% 신고세액공제 적용','예','선택',YESNO),
]}


def allowance(relation):
 if relation not in RELATIONS:raise ValueError('받는 사람과의 관계를 확인해 주세요.')
 return D(ALLOWANCES[RELATIONS.index(relation)])


def gift(gift_date=AS_OF,relation=RELATIONS[0],resident='예',real_estate=0,cash=1000000000,
         listed=0,unlisted=0,bonds=0,other=0,debt=0,used_regular=0,special=SPECIAL[0],
         used_special=0,special_request=0,appraisal=0,disaster=0,prior_value=0,prior_deductions=0,
         prior_base=0,prior_tax=0,prior_skip_value=0,prior_skip_tax=0,skip='아니요',skip_exception='아니요',timely='예'):
 try:gift_date=gift_date if type(gift_date) is date else date.fromisoformat(str(gift_date))
 except ValueError:raise ValueError('증여일을 확인해 주세요.') from None
 if gift_date.year!=2026:raise ValueError('현재 세법 판정은 2026년 증여를 지원합니다. 미래 계획은 분할 시뮬레이션을 사용해 주세요.')
 cap=allowance(relation)
 if any(v not in YESNO for v in (resident,skip,skip_exception,timely)) or special not in SPECIAL:
  raise ValueError('공제·할증 조건을 확인해 주세요.')
 amounts=list(map(num,(real_estate,cash,listed,unlisted,bonds,other,debt,used_regular,used_special,special_request,appraisal,disaster,prior_value,prior_deductions,prior_base,prior_tax,prior_skip_value,prior_skip_tax)))
 real_estate,cash,listed,unlisted,bonds,other,debt,used_regular,used_special,special_request,appraisal,disaster,prior_value,prior_deductions,prior_base,prior_tax,prior_skip_value,prior_skip_tax=amounts
 gross=sum(amounts[:6],D(0))
 if debt>gross:raise ValueError('인수채무는 이번 증여재산 평가액을 초과할 수 없습니다.')
 net=gross-debt
 if used_special>100000000 or special_request>100000000:raise ValueError('혼인·출산 공제 누적 한도는 1억원입니다.')
 if used_regular>600000000:raise ValueError('지난 일반 공제액을 확인해 주세요.')
 if disaster>net:raise ValueError('재해손실은 채무 차감 후 이번 재산가액 이하여야 합니다.')
 if special_request and (resident!='예' or relation not in RELATIONS[1:3] or special==SPECIAL[0]):
  raise ValueError('혼인·출산 공제는 거주자가 직계존속으로부터 받은 적격 증여에만 적용합니다.')
 if skip=='예' and relation not in RELATIONS[1:3]:raise ValueError('세대생략 할증은 자녀가 아닌 직계비속에게 증여할 때 적용합니다.')
 if skip_exception=='예' and skip!='예':raise ValueError('세대생략 대상 여부와 예외 선택을 함께 확인해 주세요.')
 if prior_deductions>prior_value or prior_base>prior_value or prior_skip_value>prior_value:
  raise ValueError('과거 공제·과표·할증 대상액은 과거 증여가액 이하여야 합니다.')
 if not prior_value and any((prior_deductions,prior_base,prior_tax,prior_skip_value,prior_skip_tax)):
  raise ValueError('과거 증여가액 없이 과거 공제·세액을 입력할 수 없습니다.')
 if prior_skip_tax and not prior_skip_value:raise ValueError('과거 세대생략 대상액 없이 할증 세액을 입력할 수 없습니다.')
 if prior_tax and not prior_base:raise ValueError('과거 과세표준 없이 납부세액공제를 적용할 수 없습니다.')
 aggregate=prior_value>=10000000
 previous=prior_value if aggregate else D(0)
 previous_deduction=prior_deductions if aggregate else D(0)
 regular=min(net,max(D(0),cap-used_regular)) if resident=='예' else D(0)
 special_amount=min(max(D(0),net-regular),special_request,max(D(0),D(100000000)-used_special)) if resident=='예' else D(0)
 base=max(D(0),net+previous-previous_deduction-regular-special_amount-appraisal-disaster)
 raw=ordinary_tax(base) if base>=500000 else D(0)
 # Amount for the 2bn test includes aggregated gifts; allocation explicitly
 # separates skipped-generation gifts from exempt prior/current gifts.
 total_value=gross+previous
 skipped=(gross if skip=='예' and skip_exception!='예' else D(0))+(prior_skip_value if aggregate else D(0))
 surcharge_rate=D('.4') if relation==RELATIONS[2] and total_value>2000000000 else D('.3')
 surcharge=max(D(0),raw*skipped/total_value*surcharge_rate-(prior_skip_tax if aggregate else D(0))) if total_value else D(0)
 credit_limit=raw*min(prior_base,base)/base if aggregate and base else D(0)
 paid_credit=min(prior_tax,credit_limit) if aggregate else D(0)
 before_filing=max(D(0),raw+surcharge-paid_credit)
 filing=before_filing*D('.03') if timely=='예' else D(0)
 due=before_filing-filing
 # Statutory month-end date only, no unverified holiday/calendar adjustment.
 ym=gift_date.year*12+gift_date.month-1+3;y,m=divmod(ym,12)
 deadline=date(y,m+1,calendar.monthrange(y,m+1)[1])
 rows=[{'항목':k,'금액':v} for k,v in (
  ('이번 재산 평가액',gross),('인수채무',debt),('채무 차감 후 이번 과세가액',net),
  ('과거 합산 과세가액',previous),('합산 재산의 과거 공제 등',previous_deduction),
  ('이번 일반 증여공제',regular),('이번 혼인·출산 공제',special_amount),('이번 평가수수료',appraisal),
  ('이번 재해손실 공제',disaster),('누적 과세표준',base),('기본 산출세액',raw),
  ('추가 세대생략 할증',surcharge),('과거 납부세액 공제한도',credit_limit),
  ('과거 납부세액공제',paid_credit),('신고세액공제',filing),('이번 증여세 추정',due))]
 return FinanceResult({'이번 증여세 추정액':due,'과세표준':base,'이번 일반 증여공제':regular,
  '이번 혼인·출산 공제':special_amount,'추가 세대생략 할증':surcharge,
  '과거 납부세액공제':paid_credit,'법정 신고기한 기준일 (휴일 연장 전)':deadline.isoformat(),
  '부담부증여 양도세': '별도 양도세 계산 필요' if debt else '해당 없음'},
  '이번 순재산+동일인10년 합산재산−합산 재산의 과거 공제−이번 일반/혼인출산/재해 공제−평가수수료=과세표준. '
  '50만원 미만 과세최저한 적용. 누진 산출세액+당회 세대생략 할증−한도 내 과거 산출세액공제−기한 내 신고공제3%.',
  [f'법령 대조 기준일 {AS_OF} · 상속세및증여세법 제47·53·53의2·55~58·68·69조, 시행령 제46의3조.',
   '일반 과세대상 증여의 확인된 평가액을 계산합니다. 주식 할증·평가액 산정, 합산배제 증여·가업/창업 특례, 외국납부 공제, 가산세는 현재 자동 계산 범위 밖입니다. 비거주자는 국내 과세대상 재산만 입력합니다.',
   '받는 사람을 기준으로 관계를 선택합니다. 기타 친족 공제는 4촌 이내 혈족·3촌 이내 인척입니다. 부모·조부모 등 직계존속 공제 사용액은 관계군 전체 10년 누적입니다.',
   '과거 합산은 동일 증여자 기준이며 증여자가 직계존속이면 그 배우자를 포함합니다. 과거 합계 1천만원 미만은 합산 제외하되 이미 사용한 공제는 별도 차감합니다.',
   '과거 금액은 10년 기간과 신고서를 대조한 합계를 입력합니다. 여러 신고서에 반복된 합산액·산출세액을 중복 입력하지 않습니다. 납부세액공제에는 실제 납부액이 아닌 신고공제 전 해당 재산의 산출세액(할증 별도)을 사용합니다. 기간 경계·제척기간·다른 과거 증여의 영향은 검증이 남아 있습니다.',
   '혼인·출산 공제는 두 유형을 합쳐 수증자 누적1억원 한도입니다. 자녀 수 또는10년 경과로 한도가 새로 생기지 않습니다. 날짜·신고사실 등 요건을 확인한 금액만 적용합니다.',
   '손자녀 등 세대생략은30%, 미성년 수증자의 합산 포함 재산20억원 초과는40%. 최근친 사망 예외와 과거 할증액을 별도로 반영합니다.',
   '부담부증여의 채무는 객관적 입증 요건을 충족한 금액만 입력합니다. 증여자의 양도세·수증자의 취득세는 이 결과에 포함되지 않습니다.',
   '원 단위 반올림 추정치입니다. 신고기한 표시는 월말 기준일이며 토요일·공휴일·기한연장 여부는 별도 달력 대조가 남아 있습니다. 기한후 신고를 선택하면3%공제를 제외하지만 가산세를0원으로 확정하지 않습니다.'],rows)


def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('계산기 입력을 확인해 주세요.')
 return gift(*values)
