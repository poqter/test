"""Calendar-year 2026 domestic company loss ledger; shared corporate tax bands."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='이월결손금계산기'
KINDS=('일반법인 80%','중소기업 등 100% 자격 확인')
FIELDS={NAME:[('발생연도, 미사용 잔액 (여러 건은 세미콜론 구분)', '2025,500000000','문자',3000),
 ('2026년 당기 세무상 소득금액',300000000,'원',10**12),('공제 한도 자격',KINDS[0],'선택',KINDS),
 ('법60조의2 제1항1호 소규모법인 해당','아니요','선택',('아니요','예'))]}
def losses(ledger='2025,500000000',income=300000000,kind=KINDS[0],small='아니요'):
 income=num(income)
 if kind not in KINDS or small not in ('아니요','예'):raise ValueError('법인 구분을 확인해 주세요.')
 entries={}
 for item in str(ledger).split(';'):
  parts=item.strip().split(',')
  if len(parts)!=2:raise ValueError('발생연도,잔액 형식으로 입력하세요. 금액에는 쉼표를 넣지 않습니다.')
  y=num(parts[0],2009,2025)
  if y!=int(y) or int(y) in entries:raise ValueError('발생연도는 중복 없는 정수로 입력하세요.')
  amount=num(parts[1])
  if amount!=int(amount):raise ValueError('잔액은 원 단위 정수로 입력하세요.')
  entries[int(y)]=amount
 if sum(entries.values())>10**12:raise ValueError('결손금 합계는 1조원 이하로 입력하세요.')
 rate=D(1) if kind==KINDS[1] else D('.8')
 budget=income*rate;used=D(0);expired=D(0);expiring=D(0);carry=D(0);rows=[]
 for year,amount in sorted(entries.items()):
  last=year+(15 if year>=2020 else 10)
  deduction=min(amount,budget) if last>=2026 else D(0)
  budget-=deduction;used+=deduction
  balance=amount-deduction
  if last<2026:expired+=amount;status='기한 만료'
  elif last==2026:expiring+=balance;status='올해 공제 종료'
  else:carry+=balance;status='다음 해 이월 가능'
  rows.append({'발생연도':str(year),'마지막 공제연도':str(last),'입력 잔액':amount,'당기 공제':deduction,'미공제 잔액':balance,'상태':status})
 base=income-used;before=bracket(income,small=='예');after=bracket(base,small=='예')
 return FinanceResult({'당기 공제액':used,'공제 후 과세표준':base,'국세 산출세액 감소':before-after,
 '지방세 포함 산출세액 감소 추정':(before-after)*D('1.1'),'이미 만료된 결손금':expired,
 '올해 말 만료 예정 잔액':expiring,'다음 해 이월 가능 잔액':carry},
 '오래된 연도부터 유효 결손금을 소득금액의80% 또는 확인된100% 한도까지 공제. 세액 감소는 공통 법인세 누진함수의 공제 전후 차이.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법13조, 시행령10조, 법률17652호 부칙 · 2026년1월1일~12월31일 사업연도.',
 '발생연도도 달력연도 사업연도인 일반 내국법인에 한합니다. 2009~2019 발생분10년, 2020년 이후15년. 2009년 이전 결손금·합병분할 승계·연결납세·사업연도 변경은 별도 검토 대상입니다.',
 '신고·경정으로 인정된 미사용 잔액만 입력합니다. 소급공제 환급, 자산수증·채무면제이익 보전 등 이미 사용한 금액은 제외합니다. 회계상 누적손실을 그대로 입력하지 않습니다.',
 '100%는 중소기업 또는 시행령상 회생계획 이행 등 적격 법인임을 확인한 경우만 선택합니다. 이 화면은 해당 자격을 자동 판정하지 않습니다.',
 '세액 감소는 공제·감면·비과세·다른 소득공제와 기납부세액 반영 전입니다. 지방세는 동일 과세표준 및 표준세율을 가정하며 실제 환급액이나 확정 절세액이 아닙니다. 올해 말 만료분은 다음 해 이월액에서 제외합니다.'],rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return losses(*values)
