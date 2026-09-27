"""Annual fixed-balance diagnostic using shared interest and wage engines."""
from modules.calculators.finance.finance_models import D, num, FinanceResult, period
from modules.calculators.corporate.deemed_interest import interest, RATES
from modules.calculators.tax.earned_income_tax import earned
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='가지급금 정밀진단계산기';M=10**12
FIELDS={NAME:[('연중 일정한 가지급금 잔액',200000000,'원',M),('적용 인정이자율',4.6,'%',100),
 ('실제 수취 이자율',0,'%',100),('대표 연간 총급여',120000000,'원',M),
 ('금리·특수관계·상여처분 조건 확인','아니요','선택',('아니요','예')),
 ('본인 포함 기본공제 인원',1,'명',100),('실제 국민연금 납부액',0,'원',M),
 ('실제 건강·장기요양보험료',0,'원',M),('실제 고용보험료',0,'원',M)]}
def diagnostic(balance=200000000,rate=4.6,received_rate=0,salary=120000000,confirmed='아니요',people=1,nps=0,health=0,employment=0):
 balance,salary,nps,health,employment=map(num,(balance,salary,nps,health,employment));rate=num(rate,0,100);received_rate=num(received_rate,0,100);people=period(people,100)
 if confirmed!='예':raise ValueError('금리 적용요건과 대표자 상여처분 대상임을 확인한 뒤 계산해 주세요.')
 actual=balance*received_rate/100
 r=interest(opening=balance,closing=balance,rate_mode=RATES[1],weighted=rate,confirmed='예',received=actual)
 addition=r.metrics['인정이자 익금산입']
 before=earned(salary=salary,people=people,nps=nps,health=health,employment=employment).metrics['예상 결정세액 (국세+지방세)']
 after=earned(salary=salary+addition,people=people,nps=nps,health=health,employment=employment).metrics['예상 결정세액 (국세+지방세)']
 return FinanceResult({'인정이자 시가':r.metrics['인정이자 시가'],'실제 수취 이자':actual,'상여처분 가정액':addition,
 '대표 소득세 증가 추정':after-before,'상여 반영 전 소득세':before,'상여 반영 후 소득세':after},
 '연간 인정이자=일정잔액×확인금리. 시가와 수입이자의 차액이 시가5% 이상 또는3억원 이상이면 익금산입. 대표자 상여처분 요건 확인 후 급여 합산 전후 결정세액 차이를 비교.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법 시행령88·89·106조, 소득세법55·59조. 기본 인정이자계산기와 근로소득세계산기의 공통 산식을 사용합니다.',
 '2026년 내내 같은 잔액·금리이며 실제 이자를 해당 연도에 수취한 경우입니다. 변동 잔액은 기본 인정이자계산기의 날짜별 잔액 기록을 이용하세요.',
 '금리 적용요건·귀속자·사외유출·소득처분은 사실관계 확인이 필요합니다. 익금산입액이 항상 대표자 상여가 되는 것은 아닙니다. 본 화면은 대표자 상여임이 확인된 사례만 계산합니다.',
 '근로소득만 있는 거주자의 일반 세액 추정입니다. 상여 전후 동일한 실제 보험료·공제인원을 적용하며 다른 특별공제는0입니다. 추가 사회보험료·법인세·지급이자 손금불산입·가산세·회수 특례는 합산하지 않습니다.',
 '이자를 지급해도 가지급금 원금이 자동 감소하지 않습니다. 원금 상환·배당·이익소각·부동산 대물변제는 별도 비교가 필요하며 본 결과를 전체 해결비용으로 보지 않습니다.'],
 [{'항목':k,'금액':v} for k,v in [('연간 수취 이자',actual),('소득 가산액',addition),('기존 급여',salary),('상여 합산 급여',salary+addition),('추가 국세·지방세',after-before)]])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return diagnostic(*values)
