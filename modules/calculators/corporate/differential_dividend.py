"""Excess-dividend preliminary gift tax and confirmed settlement, one donor/event."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.gift_tax import gift, RELATIONS, allowance
from modules.calculators.tax.personal_tax_models import AS_OF
from modules.calculators.corporate.shareholder_distribution import distribution, MODES, TAX_FIELDS
NAME='차등배당계산기';M=10**12;YN=('아니요','예')
STAGES=('최초 신고: 법정 소득세 상당액','정산: 확인된 실제 소득세액')
SETTLEMENT=('확인된 정산 소득세액 입력','종합과세 과세표준으로 계산','적격 분리과세 세율로 계산','소득세 과세제외·비과세 요건 확인')
FIELDS={NAME:[('회사 총 배당금',300000000,'원',M),('수혜주주 지분율',30,'%',100),('수혜주주 세전 배당금',200000000,'원',M),
 ('전체 과소배당 중 해당 특수관계 최대주주 귀속 비율',100,'%',100),('최대주주·특수관계·단일 증여자 요건 확인','아니요','선택',YN),
 ('최근 1년 내 동일 초과배당 거래 있음','아니요','선택',YN),('계산 단계',STAGES[0],'선택',STAGES),
 ('정산용 초과배당 실제 소득세액 (국세·시행규칙 기준)',0,'원',M),('정산용 실제 소득세액 확인','아니요','선택',YN),
 ('최초 신고 증여세액 (정산 차액 계산용)',0,'원',M),('증여자에서 수증자로의 관계',RELATIONS[1],'선택',RELATIONS),
 ('관계군 10년 내 이미 사용한 일반 공제',0,'원',600000000),('10년 합산 대상 과거 증여가액',0,'원',M),
 ('합산 재산에 적용한 과거 공제',0,'원',M),('과거 합산 대상 과세표준',0,'원',M),('과거 산출세액 공제 확인액',0,'원',M),
 ('손자녀 등 세대생략 해당','아니요','선택',YN),('세대생략 최근친 사망 예외','아니요','선택',YN),('기한 내 신고','예','선택',YN),*TAX_FIELDS,('정산 소득세액 계산 방식',SETTLEMENT[0],'선택',SETTLEMENT),('초과배당 발생연도 종합소득 과세표준 (확인액)',0,'원',M),('초과배당에 적용되는 분리과세 국세율 (확인율)',14,'%',100)]}
def equivalent(excess):
 """Statutory table, intentionally retain its 4,000-won boundary steps."""
 excess=num(excess)
 for limit,start,base,rate in [(57600000,0,0,'.14'),(88000000,57600000,8060000,'.24'),(150000000,88000000,15360000,'.35'),(300000000,150000000,37060000,'.38'),(500000000,300000000,94060000,'.40'),(1000000000,500000000,174060000,'.42'),(M,1000000000,384060000,'.45')]:
  if excess<=limit:return D(base)+(excess-start)*D(rate)
def differential(total=300000000,share=30,received=200000000,ratio=100,eligible='아니요',repeated='아니요',stage=STAGES[0],actual=0,actual_confirmed='아니요',first_tax=0,relation=RELATIONS[1],used=0,prior_value=0,prior_deductions=0,prior_base=0,prior_tax=0,skip='아니요',exception='아니요',timely='예',other_financial=0,other=0,deductions=1500000,mode=MODES[0],confirmed_tax=0,settlement=SETTLEMENT[0],settlement_base=0,separate_rate=14):
 total,received,actual,first_tax,used,prior_value,prior_deductions,prior_base,prior_tax=map(num,(total,received,actual,first_tax,used,prior_value,prior_deductions,prior_base,prior_tax))
 if settlement not in SETTLEMENT:raise ValueError('정산 소득세액 계산 방식을 확인하세요.')
 settlement_base=num(settlement_base);separate_rate=num(separate_rate,0,100)
 if settlement!=SETTLEMENT[0] and (stage!=STAGES[1] or actual):raise ValueError('정산 자동계산은 정산 단계에서 선택하고 실제 소득세액 수동 입력은0으로 두세요.')
 share=num(share,0,100)/100;ratio=num(ratio,0,100)/100
 if any(x not in YN for x in (eligible,repeated,actual_confirmed,skip,exception,timely)) or stage not in STAGES:raise ValueError('계산 조건을 확인하세요.')
 allowance(relation)
 if received>total:raise ValueError('주주 배당금은 회사 총 배당금 이하여야 합니다.')
 if repeated=='예':raise ValueError('1년 내 동일 초과배당은 합산 검토가 필요합니다. 반복 거래 자동 정산은 아직 지원하지 않습니다.')
 if stage==STAGES[0] and (actual or first_tax or actual_confirmed=='예'):raise ValueError('실제 소득세와 최초 신고세액 입력은 정산 단계에서 사용합니다.')
 normal=total*share;difference=max(D(0),received-normal);excess=difference*ratio
 # Ordinary domestic dividend is not a return of capital: full amount is income.
 income=distribution(received,0,other_financial,other,deductions,mode,confirmed_tax)
 preliminary=equivalent(excess)
 metrics={'지분 비례 배당금':normal,'지분 비례액 초과분':difference,'법정 비율 반영 초과배당금액':excess,'배당소득세 증가 추정':income['개인세 증가 추정']}
 notes=[f'법령 대조 기준일 {AS_OF} · 상증세법41조의2, 시행령31조의2, 시행규칙10조의3 및 별지10호의5.',
 '초과배당=(실제 배당−지분 비례 배당)의 양수 부분×전체 과소배당 중 특수관계 최대주주 귀속 비율. 단일 증여자·한 번의 거래만 지원합니다. 최대주주·특수관계·귀속비율 판정은 입력 전에 확인합니다.',
 '최초 신고 소득세 상당액은 초과배당에 대한 법정 표로 계산한 국세 상당액이며 실제 납부 소득세나 지방소득세 포함 금액이 아닙니다. 원본의 전체 배당세액 비례 배분과 구분합니다.',
 '최초 신고기한이 다음 해 6월1일(성실신고자는7월1일) 이후인 경우 실제 소득세액 적용 여부를 검토하고 정산 모드의 실제 소득세액을 사용하세요. 기한·휴일 자동 판정은 미지원입니다.',
 '정산용 실제 소득세액은 시행규칙10조의3제2항 기준으로 확인한 초과배당 귀속 국세입니다. 전체 배당 원천징수액, 지방세 포함 금액, 배당세액공제 후 임의 증분과 혼동하지 마세요. 정산 자동계산은 확인된 해당 연도 종합소득 과세표준에서 초과배당 유무에 따른 기본세율 세액 차이와 초과배당14% 중 큰 금액을 적용합니다. 분리과세는 확인된 국세율을 적용하고 적격 과세제외·비과세는0원입니다. 소득구분·과세표준·세율은 확인 입력이며, 신고서 전체 과세표준을 역산하지 않습니다.',
 '미성년이라는 이유만으로 세대생략 할증을 적용하지 않습니다. 부모→자녀와 조부모→손자녀를 구분합니다. 과거 증여가 세대생략 대상인 복합 사례는 이 화면에서 지원하지 않습니다.',
 '일반 증여세 공통 계산식을 사용합니다. 과거 증여의 10년 합산·공제사용액·산출세액은 확인된 금액만 입력하세요. 혼인출산 공제·외국납부·가산세는 미지원입니다.',
 '전체 배당의 종합소득세는 배당가산 여부 미확인 시 자동 확정하지 않습니다. 가산 대상 확인 모드는 공통 배당가산·비교세액 계산을 사용합니다. 확정세액 모드는 전체 배당으로 증가한 국세·지방세 결정세액입니다.',
 '정산 차액은 정산 후 증여세−최초 신고 증여세입니다. 음수는 환급 추정이며 총부담 계산에 최초 신고세액을 다시 더하지 않습니다. 최초 신고 결과는 잠정치입니다.']
 if eligible!='예' and excess:
  metrics.update({'증여세 추정':'최대주주·특수관계 요건 확인 필요','세후 수령 추정':'증여세 검토 필요'})
  return FinanceResult(metrics,'초과배당 금액을 계산하되 미확인 과세요건은 최종세액으로 표시하지 않습니다.',notes)
 if stage==STAGES[1] and excess and actual_confirmed!='예':raise ValueError('정산용 실제 소득세액을 확인해 주세요.')
 if stage==STAGES[1] and settlement!=SETTLEMENT[0]:
  from modules.calculators.tax.personal_tax_models import progressive_tax
  if settlement==SETTLEMENT[1]:actual=max(excess*D('.14'),progressive_tax(settlement_base)-progressive_tax(max(D(0),settlement_base-excess)))
  elif settlement==SETTLEMENT[2]:actual=excess*separate_rate/100
  else:actual=D(0)
 if actual>excess:raise ValueError('정산용 실제 소득세액은 초과배당금액 이하여야 합니다.')
 deduct=preliminary if stage==STAGES[0] else actual
 value=excess-deduct
 if excess:
  gr=gift(relation=relation,cash=value,used_regular=used,prior_value=prior_value,prior_deductions=prior_deductions,prior_base=prior_base,prior_tax=prior_tax,skip=skip,skip_exception=exception,timely=timely)
  due=gr.metrics['이번 증여세 추정액'];rows=gr.rows
 else:
  if first_tax:raise ValueError('초과배당이 없는 정산은 기존 신고 내용의 별도 검토가 필요합니다.')
  due=D(0);rows=[]
 tax=income['개인세 증가 추정'];known=not isinstance(tax,str)
 metrics.update({'증여재산에서 차감하는 소득세 상당액':deduct,'증여재산가액':value,'증여세 추정':due,
 '소득세·증여세 합계 추정':tax+due if known else '배당소득세 확인 필요',
 '세후 수령 추정':received-tax-due if known else '배당소득세 확인 필요'})
 if stage==STAGES[1]:metrics['정산 추가 납부·환급 추정']=due-first_tax
 return FinanceResult(metrics,'초과배당−법정 소득세 상당액 또는 정산용 실제 소득세=증여재산가액. 공통 증여세 계산 후, 전체 배당 소득세와 합산합니다.',notes,rows)
def calculate(name,values):
 if name!=NAME or len(values) not in (24,len(FIELDS[NAME])):raise ValueError('입력 항목을 확인하세요.')
 return differential(*values)
