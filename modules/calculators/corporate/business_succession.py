"""Single first-transfer succession comparison with confirmed stock valuation."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.tax.gift_tax import gift, RELATIONS
NAME='가업승계 세부담계산기';M=10**12;YN=('아니요','예')
FIELDS={NAME:[('이번 이전 주식의 확인된 최종 평가액',3920000000,'원',M),('부모의 계속 경영기간',15,'년',100),('부모 나이',62,'세',120),('수증자 나이',35,'세',120),('일반 증여: 과거 증여·사용 공제 없음 확인','아니요','선택',YN),('특례: 최초 단일 수증자·전액 가업자산·모든 적격요건 확인','아니요','선택',YN),('상속 공제: 별도 상속요건 및 가업상속재산 확인','아니요','선택',YN)]}
def succession(value=3920000000,years=15,parent=62,child=35,no_prior='아니요',eligible='아니요',inheritance='아니요'):
 value=num(value);years=period(years,100,allow_zero=True);parent=period(parent,120);child=period(child,120)
 if any(x not in YN for x in (no_prior,eligible,inheritance)):raise ValueError('확인 상태를 선택하세요.')
 cap=D(0) if years<10 else D(30000000000 if years<20 else 40000000000 if years<30 else 60000000000)
 general='과거 증여·공제 확인 필요';special='적격요건 확인 필요';special_base='미확인'
 if no_prior=='예':
  general=gift(relation=RELATIONS[1] if child>=19 else RELATIONS[2],cash=0,unlisted=value,timely='아니요').metrics['이번 증여세 추정액']
 if eligible=='예':
  if parent<60 or child<18 or years<10:raise ValueError('증여특례는 부모60세·수증자18세·계속경영10년 이상 요건을 확인해야 합니다.')
  if value>cap:raise ValueError('업력별 특례 한도를 넘는 재산은 일반 과세와의 배분 검증이 남아 있어 현재 계산하지 않습니다.')
  special_base=max(D(0),value-1000000000)
  special=min(special_base,D(12000000000))*D('.1')+max(D(0),special_base-12000000000)*D('.2')
 metrics={'일반 증여 산출세액':general,'가업승계 증여특례 산출세액':special,'동일 재산 산출세액 차이':general-special if isinstance(general,D) and isinstance(special,D) else '두 시나리오 조건 확인 필요','특례 과세표준':special_base,'업력별 법정 한도':cap,'상속 시 가업공제 한도 시뮬레이션':min(value,cap) if inheritance=='예' and years>=10 else '별도 상속요건 확인 필요'}
 notes=['법령 대조일 2026-09-26 · 조세특례제한법30조의6(2026-09-18 시행), 시행령27조의6, 상증세법18조의2. 일반 증여 계산은 기존 증여세 엔진을 공유합니다.',
 '확인된 최종 주식평가액을 입력합니다. 비상장주식 평가계산기에서 순손익·순자산 가중평가, 순자산 하한, 부동산 비율 및 최대주주 할증 조건을 계산한 뒤 이전 주식 수를 지정해 이 화면에 평가액을 전달할 수 있습니다. 인정 시가 우선 및 법정 평가 조건은 확인해야 합니다.',
 '산출세액끼리 비교하며 일반 증여의3% 신고공제도 이 비교에서는 적용하지 않습니다. 일반 증여는 거주자인 자녀에게 최초 증여하는 경우만 지원합니다. 이전 증여가 있으면 기존 증여세 계산기를 사용해 계산 내역을 확인할 수 있습니다.',
 '증여특례는 최초 단일 수증자·이전가액 전액이 적격 가업자산인 범위입니다.10억원 공제 후 과표120억원까지10%, 초과20%.10/20/30년 경영 한도300/400/600억원. 일부 공식 안내의60억원 구간 대신 현행 조문120억원을 적용합니다.',
 '중소·중견기업, 업종·자산·매출·지분·대표재직·수증자 거주와 가업종사·기한내 신청·사후관리 등은 확인 입력입니다. 나이와 업력만으로 적격 판정하지 않습니다. 과거 특례·여러 수증자·일부 사업무관자산·한도초과·상장차익·추징은 미지원입니다.',
 '상속공제는 별도 상속요건을 충족한 가업재산의 한도 시뮬레이션이며 상속세 계산 결과가 아닙니다. 일반 증여세에서 상속공제액을 빼지 않습니다. 전체 상속재산·공제한도·사전증여 합산은 상속세 통합 검증이 남아 있습니다.']
 return FinanceResult(metrics,'일반 증여 산출세액과 (적격 가업자산−10억원)의10%·20% 특례 산출세액 비교. 가업상속공제 한도는 별도 표시.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return succession(*values)
