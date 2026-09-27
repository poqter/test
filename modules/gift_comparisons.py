"""Gift comparison scenarios; shared engines, explicit scope and no lifetime claims."""
from .finance_models import D,FinanceResult,num
from .gift_tax import gift,RELATIONS,YESNO,AS_OF
from .capital_gains_tax import gains,ASSETS,SCOPE
from .transfer_tax_rules import ordinary_tax
BURDEN='부담부증여·일반증여 비교'
INHERIT='증여·상속 세액 비교'
VALUATIONS=('시가 평가·확인된 실지 취득가액','기준시가 평가·동일 기준 취득가액 별도 확인')
M=10**12
FIELDS={BURDEN:[
 ('증여재산 세법상 평가액',1000000000,'원',M),('객관적으로 입증된 인수채무',400000000,'원',M),
 ('재산 전체 취득가액 (평가방식과 일치)',600000000,'원',M),
 ('채무 양도 부분에 직접 귀속되는 적격 필요경비',0,'원',M),
 ('취득일','2016-09-26','날짜',0),('증여일',AS_OF,'날짜',0),
 ('받는 사람과의 관계',RELATIONS[1],'선택',RELATIONS),
 ('자산 종류',ASSETS[0],'선택',ASSETS),('양도세 취득·평가 기준',VALUATIONS[0],'선택',VALUATIONS),
 ('비사업용 토지','아니요','선택',YESNO),('주택·입주권·분양권 수 (세대 기준)',1,'개',100),
 ('조정대상지역 주택','아니요','선택',YESNO),
 ('등기된 일반 1주택 비과세 요건 확인 (기타 특례 제외)','아니요','선택',YESNO),
 ('올해 남은 양도 기본공제',2500000,'원',2500000),
 ('주택 실제 거주 만 연수',0,'년',100),
 ],INHERIT:[
 ('이전할 재산가액',1000000000,'원',M),('증여받는 사람과의 관계',RELATIONS[1],'선택',RELATIONS),
 ('그 밖의 순상속 과세가액 (채무·장례 등 반영 후)',0,'원',M),
 ('확인된 상속 공제 합계 (종합한도 적용 전)',500000000,'원',M),
 ('상속인 자격·공제 및 합산 제외 가정 확인','아니요','선택',YESNO),
 ]}

def burden(value=1000000000,debt=400000000,cost=600000000,expense=0,acquire='2016-09-26',when=AS_OF,
           relation=RELATIONS[1],asset=ASSETS[0],valuation=VALUATIONS[0],nonbusiness='아니요',houses=1,
           regulated='아니요',special='아니요',basic=2500000,residence=0):
 value,debt,cost,expense,basic=[num(v) for v in (value,debt,cost,expense,basic)]
 if value<=0 or debt>value:raise ValueError('재산가액은 0 초과, 인수채무는 재산가액 이하여야 합니다.')
 if valuation not in VALUATIONS or special not in YESNO:raise ValueError('평가 방식과 특례 여부를 확인해 주세요.')
 if not debt and expense:raise ValueError('인수채무가 없으면 채무 양도 부분의 필요경비도 0원입니다.')
 ratio=debt/value
 # Validate property/date/rate options even for a zero-debt scenario.
 check=gains(transfer=when,acquire=acquire,asset=asset,scope=SCOPE[0],sale=value,cost=cost,
             expenses=0,basic=basic,nonbusiness=nonbusiness,houses=houses,regulated=regulated,qualified=special,residence=residence)
 normal=gift(gift_date=when,relation=relation,cash=0,real_estate=value)
 reduced=gift(gift_date=when,relation=relation,cash=0,real_estate=value,debt=debt)
 national=local=D(0);detail=[]
 if debt:
  cg=gains(transfer=when,acquire=acquire,asset=asset,sale=debt,cost=cost*ratio,expenses=expense,
           basic=basic,nonbusiness=nonbusiness,houses=houses,regulated=regulated,qualified=special,residence=residence,exemption_full_sale=value)
  national=cg.metrics['소득세'];local=cg.metrics['지방소득세 추정'];detail=cg.rows
 normal_tax=normal.metrics['이번 증여세 추정액'];reduced_tax=reduced.metrics['이번 증여세 추정액']
 total=reduced_tax+national+local
 rows=[{'항목':'수증자 증여세','일반증여':normal_tax,'부담부증여':reduced_tax},
       {'항목':'증여자 양도소득세','일반증여':D(0),'부담부증여':national},
       {'항목':'증여자 지방소득세','일반증여':D(0),'부담부증여':local},
       {'항목':'비교 세액 합계','일반증여':normal_tax,'부담부증여':total},
       {'항목':'수증자가 인수하는 채무','일반증여':D(0),'부담부증여':debt},
       {'항목':'이전 순재산 (세금 전)','일반증여':value,'부담부증여':value-debt}]
 rows += [{'항목':'양도 상세: '+r['항목'],'부담부증여':r['금액']} for r in detail]
 return FinanceResult({'일반증여 비교 세액':normal_tax,'부담부증여 비교 세액':total,'두 방식 세액 차이':normal_tax-total,
  '수증자 증여세':reduced_tax,'증여자 양도소득세':national,'증여자 지방소득세':local,
  '채무 비율':ratio*100,'안분 취득가액':cost*ratio},
  '채무 비율=인수채무/재산가액. 양도 취득가액=전체 취득가액×채무 비율. '
  '부담부 비교세액=채무 차감 증여세+채무 부분 양도소득세+지방소득세.',
  [f'법령 대조 기준일 {AS_OF} · 소득세법 시행령159조·상속세및증여세법47조. 평가방식: {valuation}.',
   '입증된 채무를 실제 인수하는 거주자의 최초 증여, 기한 내 신고를 가정합니다. 배우자·직계존비속 채무는 객관적 입증이 전제입니다. 과거 증여·세대생략·특별공제는 이 비교에서 미반영입니다.',
   '증여자가 직접 취득한 단독소유 부동산입니다. 주거용 오피스텔은 주택으로 선택합니다. 일반1주택 비과세는 자격 확인 후 전체 증여가액으로12억원 초과 비율을 산정하여 채무 부분 차익에 적용합니다. 다주택 중과 특례·상속증여 취득·미등기·공동소유·혼합자산은 이 화면에서 지원하지 않습니다.',
   '기준시가 평가면 취득가액도 동일 기준으로 확인하여 입력해야 합니다. 환산취득가액·기준시가 자동 조회는 하지 않습니다. 필요경비는 전체액이 아닌 채무 양도 부분에 적법하게 귀속되는 금액입니다.',
   '고가주택 판단은 인수채무만이 아니라 전체 증여가액을 기준으로 합니다. 국세청 서면4팀-1499(2006-05-30)의 안분 원칙과 현행 시행령160조의12억원 기준을 반영합니다.',
   '일반증여와 부담부증여는 이전 순재산이 다릅니다. 세액 차이를 같은 순재산 이전의 절세액으로 해석하지 않습니다. 채무 원금·이자·취득세·등기비용·부가가치세·추후 양도세는 합계에 포함하지 않습니다.',
   '일반증여 비교는 증여자가 채무를 별도 정리하고 채무 없는 재산 전액을 이전하는 가정입니다. 증여자가 수증자 세금을 대신 지급하는 추가 증여는 미반영입니다. 원 단위 반올림 추정치입니다.'],rows,units={'채무 비율':'%'})

def inheritance_compare(value=1000000000,relation=RELATIONS[1],other=0,deductions=500000000,confirmed='아니요'):
 value,other,deductions=[num(v) for v in (value,other,deductions)]
 if value+other>M:raise ValueError('비교 과세가액 합계는 1조원 이하여야 합니다.')
 if confirmed!='예':raise ValueError('상속인 자격·공제 및 사전증여 합산 제외 가정을 확인해 주세요.')
 g=gift(cash=value,relation=relation)
 # Whole-estate scenario, not an independent tax on each recipient's share.
 before_base=max(D(0),other-deductions);after_base=max(D(0),other+value-deductions)
 before=(ordinary_tax(before_base) if before_base>=500000 else D(0))*D('.97')
 after=(ordinary_tax(after_base) if after_base>=500000 else D(0))*D('.97')
 incremental=after-before;gt=g.metrics['이번 증여세 추정액']
 return FinanceResult({'현재 증여세':gt,'재산 포함 전체 상속세':after,'재산 제외 상속세':before,
  '해당 재산으로 늘어나는 상속세':incremental,'증여세 − 상속세 증가분':gt-incremental},
  '전체 상속세=세율(max(0,다른 순과세가액+이전재산−확인공제))×97%. '
  '상속세 증가분=재산 포함 전체 세액−재산 제외 세액. 이를 현재 증여세와 비교.',
  [f'법령 대조 기준일 {AS_OF} · 상속세및증여세법26·53·56조의 일반 세율·공제를 공유합니다.',
   '현재 재산가액과 세법을 고정한 두 개의 독립 시나리오입니다. 재산을 증여하지 않고 전부 상속하는 경우와, 해당 재산을 합산 대상 기간 밖에 미리 증여한 경우를 비교합니다.',
   '거주자·일반 상속, 세대생략 없음·기한 내 신고 가정. 받는 사람의 상속인 자격과 공제액을 별도 확인해야 합니다. 공제 합계에는 채무·장례비를 다시 넣지 않습니다.',
   '상속인에게 10년 이내, 상속인 외의 자에게 5년 이내 사전증여한 재산이 상속에 합산되는 경우는 지원하지 않습니다. 그러한 경우의 증여세액공제·공제한도 변화도 미반영입니다.',
   '공제액은 양쪽 시나리오에 동일하게 유지하는 가정입니다. 재산 이전으로 배우자·금융재산 공제가 달라지는 경우 별도 상속 계산이 필요합니다. 실제 상속 시점·가격상승·추가소득·취득세·세금 납부재원은 미반영입니다.',
   '기본값 공제5억원은 자동 자격판정 결과가 아닙니다. 다른 순과세가액에는 채무·장례 등 차감과 필요한 합산을 이미 반영합니다. 이전 재산의 개별 지분만으로 전체 상속세를 계산하지 않습니다.'],
  [{'구분':'현재 증여','과세표준':g.metrics['과세표준'],'세액':gt},
   {'구분':'재산 포함 상속','과세표준':after_base,'세액':after},
   {'구분':'재산 제외 상속','과세표준':before_base,'세액':before}])

def calculate(name,values):
 if name not in FIELDS or len(values)!=len(FIELDS[name]):raise ValueError('계산 입력을 확인해 주세요.')
 return (burden if name==BURDEN else inheritance_compare)(*values)
