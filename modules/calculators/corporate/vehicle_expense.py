"""Single corporate passenger car, 2026 twelve-month fiscal year."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='업무용승용차 비용계산기';M=10**12
MODES=('구입','리스','렌트');YN=('아니요','예')
FIELDS={NAME:[('보유 형태',MODES[0],'선택',MODES),('구입 차량 세무상 취득가액',60000000,'원',M),
 ('당기 이전 누적 상각액 (구입)',0,'원',M),('당기 보유·임차 월수',12,'개월',12),
 ('유류·보험·세금·수선 등 별도 비용 (임차료와 중복 제외)',4000000,'원',M),('당기 리스·렌트료',0,'원',M),
 ('리스료에 포함된 보험료·자동차세',0,'원',M),('리스 수선비 구분 가능','아니요','선택',YN),('리스료에 포함된 실제 수선비',0,'원',M),
 ('운행기록부 작성','예','선택',YN),('기록부상 업무사용 비율',80,'%',100),
 ('보유·임차기간 전체 업무전용보험 가입 확인','예','선택',YN),
 ('법인 전용번호판 요건 충족 또는 부착대상 아님','예','선택',YN),
 ('시행령42조2항 소규모 부동산임대 등 법인','아니요','선택',YN),('전기 감가상각 한도초과 이월액',0,'원',M)]}
def vehicle(mode='구입',price=60000000,accumulated=0,months=12,other=4000000,rent=0,lease_excluded=0,known='아니요',repairs=0,logged='예',business=80,insured='예',plate='예',small='아니요',carry=0):
 if mode not in MODES or any(x not in YN for x in (known,logged,insured,plate,small)):raise ValueError('차량 구분을 확인하세요.')
 price,accumulated,other,rent,lease_excluded,repairs,carry=map(num,(price,accumulated,other,rent,lease_excluded,repairs,carry))
 months=period(months,12);business=num(business,0,100)/100
 if accumulated>price:raise ValueError('누적 상각액은 취득가액 이하여야 합니다.')
 if carry and months!=12:raise ValueError('과거 이월액 추인은 연중 계속 보유·임차 차량만 지원합니다.')
 if mode=='구입':
  if rent or lease_excluded or repairs:raise ValueError('구입 차량은 임차료 항목을0으로 입력하세요.')
  depreciation=min(price/5*D(months)/12,price-accumulated);total=depreciation+other
 else:
  if mode=='렌트' and (lease_excluded or repairs):raise ValueError('렌트에는 리스 전용 비용을 입력하지 않습니다.')
  if lease_excluded>rent:raise ValueError('리스 제외비용이 임차료를 초과합니다.')
  maintenance=repairs if known=='예' else (rent-lease_excluded)*D('.07')
  if mode=='리스' and maintenance>rent-lease_excluded:raise ValueError('리스 수선비가 잔여 임차료를 초과합니다.')
  if mode=='리스' and known=='아니요' and repairs:raise ValueError('수선비 미구분이면 실제 수선비를0으로 입력하세요.')
  depreciation=rent*D('.7') if mode=='렌트' else rent-lease_excluded-maintenance
  total=rent+other
 cap=D(4000000 if small=='예' else 8000000)*months/12
 no_log_cap=D(5000000 if small=='예' else 15000000)*months/12
 ratio=business if logged=='예' else (min(D(1),no_log_cap/total) if total else D(0))
 if insured=='아니요' or plate=='아니요':ratio=D(0)
 business_dep=depreciation*ratio;business_other=(total-depreciation)*ratio
 allowed_dep=min(business_dep,cap);newcarry=max(D(0),business_dep-cap)
 released=min(carry,max(D(0),cap-business_dep)) if insured=='예' and plate=='예' else D(0)
 allowed=allowed_dep+business_other
 return FinanceResult({'당기 비용 손금 인정액':allowed,'과거 이월액 당기 추인':released,'총 손금 산입액':allowed+released,
 '업무사용 불인정액':total*(1-ratio),'감가상각 한도초과 신규 이월':newcarry,'차기 이월잔액':carry-released+newcarry,
 '당기 차량 관련비용':total,'적용 업무사용 비율':ratio*100},
 '구입은5년 정액법, 리스는 임차료−보험·자동차세−수선비, 렌트는 임차료70%를 상각상당액으로 계산. 전체 비용에 업무비율 적용 후 상각부분에 연800만원 한도 적용.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법27조의2, 시행령50조의2·42조2항, 시행규칙27조의2 · 2026년12개월 사업연도, 차량1대.',
 '미작성 시 총비용과 연1500만원 기준으로 업무비율을 계산한 후 감가상각 한도를 별도로 적용합니다. 소규모 부동산임대 등 적격 법인은 각각500만원·400만원. 보유·임차월수로 안분하며 월 미만은1개월입니다.',
 '전체기간 업무전용보험 미가입 또는 필요한 법인 전용번호판 미부착이면 당기 인정액0원입니다. 일부기간 보험가입·번호판 변경은 이 화면에서 계산하지 않습니다. 구입 입력은2016년 이후 취득 차량의 강제상각 대상이며 누적 상각액은 과거 손금한도 적용 전입니다.',
 '리스 수선비 미구분 시 보험료·자동차세 차감 후 금액의7%를 사용합니다. 임차료에 들어 있는 비용을 별도 유지비에 다시 넣지 않습니다. 금융리스 세무상 소유자 특례는 제외합니다.',
 '업무사용 불인정액과 상각 한도초과 이월액은 구분합니다. 과거 이월액 추인은 연중 계속 사용 조건이며, 매각·임차종료·해산·처분손실 및 개인사업자 차량은 별도 검증 대상입니다. 세액 감소나 대표자 상여세액을 확정하지 않습니다.'],
 [{'항목':'상각비 또는 상당액','총액':depreciation,'업무금액':business_dep,'당기인정':allowed_dep},
 {'항목':'그 외 비용','총액':total-depreciation,'업무금액':business_other,'당기인정':business_other}],{'적용 업무사용 비율':'%'})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return vehicle(*values)
