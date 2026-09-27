"""2026 related-party loan estimate; keep interest and expense bases distinct."""
from datetime import date,timedelta
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='인정이자계산기';M=10**12;I=M*366
MODES=('기초·기말 평균 추정','확인된 순적수 입력','날짜별 잔액 기록')
RATES=('당좌대출이자율 4.6%','확인된 가중평균차입이자율')
FIELDS={NAME:[('사업연도 시작일 (2026년 내)','2026-01-01','날짜',0),('사업연도 종료일 (2026년 내)','2026-12-31','날짜',0),
 ('적수 계산 방식',MODES[0],'선택',MODES),('기초 순대여 잔액',100000000,'원',M),('기말 순대여 잔액',100000000,'원',M),
 ('확인된 인정이자 대상 순적수',36500000000,'원·일',I),
 ('잔액 기록: 날짜,대여잔액,상계가능가수금잔액; 다음 기록','2026-01-01,100000000,0','문자',20000),
 ('이자율 방식',RATES[0],'선택',RATES),('가중평균차입이자율 (선택 시)',4.6,'%',100),
 ('금리 적용·특수관계·상계 및 제외액 검토 확인','아니요','선택',('아니요','예')),
 ('회사에 계상한 해당 수입이자',0,'원',M),
 ('지급이자 부인용 업무무관 대여 순적수 (별도 확인)',36500000000,'원·일',I),
 ('업무무관 부동산·동산 적수',0,'원·일',I),('적격 총차입금 적수',0,'원·일',I),('안분 대상 지급이자',0,'원',M)]}

def _date(v):
 try:return v if type(v) is date else date.fromisoformat(str(v))
 except ValueError:raise ValueError('날짜는 YYYY-MM-DD 형식으로 입력해 주세요.') from None

def balance_integral(start,end,records):
 if not isinstance(records,str):raise ValueError('잔액 기록 형식을 확인해 주세요.')
 parsed=[]
 for line in records.replace('\n',';').split(';'):
  if not line.strip():continue
  parts=[x.strip() for x in line.split(',')]
  if len(parts)!=3:raise ValueError('기록은 날짜,대여잔액,상계가능가수금잔액 형식이며 금액에는 쉼표를 넣지 않습니다.')
  when=_date(parts[0]);loan=num(parts[1]);deposit=num(parts[2])
  if not start<=when<=end:raise ValueError('잔액 기록일은 사업연도 안이어야 합니다.')
  parsed.append((when,loan,deposit))
 if not parsed or len(parsed)>366:raise ValueError('사업연도 시작일을 포함한 잔액 기록을 입력해 주세요.')
 parsed.sort()
 if parsed[0][0]!=start or len({x[0] for x in parsed})!=len(parsed):raise ValueError('시작일 잔액이 필요하며 같은 날짜를 중복 입력할 수 없습니다.')
 integral=D(0);rows=[]
 for i,(when,loan,deposit) in enumerate(parsed):
  stop=parsed[i+1][0] if i+1<len(parsed) else end+timedelta(days=1)
  days=(stop-when).days;net=max(D(0),loan-deposit);product=net*days;integral+=product
  rows.append({'시작일':str(when),'마지막 적용일':str(stop-timedelta(days=1)),'일수':days,'순대여 잔액':net,'적수':product})
 return integral,rows

def interest(start='2026-01-01',end='2026-12-31',mode=MODES[0],opening=100000000,closing=100000000,integral=36500000000,
             records='2026-01-01,100000000,0',rate_mode=RATES[0],weighted=4.6,confirmed='아니요',received=0,
             unrelated=36500000000,other=0,borrowing=0,paid=0):
 start,end=_date(start),_date(end)
 if start.year!=2026 or end.year!=2026 or start>end:raise ValueError('현재는 2026년 내 시작·종료 사업연도를 지원합니다.')
 if confirmed!='예':raise ValueError('이자율 선택 요건·특수관계·상계 가능성·적용 제외액을 먼저 확인해 주세요.')
 if mode not in MODES or rate_mode not in RATES:raise ValueError('계산 방식을 확인해 주세요.')
 opening,closing,received,paid=[num(v) for v in (opening,closing,received,paid)]
 integral,unrelated,other,borrowing=[num(v,0,I) for v in (integral,unrelated,other,borrowing)]
 weighted=num(weighted,0,100);days=(end-start).days+1;rows=[]
 if mode==MODES[0]:integral=(opening+closing)/2*days
 elif mode==MODES[2]:integral,rows=balance_integral(start,end,records)
 rate=D('.046') if rate_mode==RATES[0] else weighted/100
 fair=integral*rate/365;difference=max(D(0),fair-received)
 addition=difference if difference>=300000000 or difference>=fair*D('.05') else D(0)
 if paid and not borrowing:raise ValueError('지급이자가 있으면 적격 총차입금 적수도 입력해야 합니다.')
 ratio=min(D(1),(unrelated+other)/borrowing) if borrowing else D(0)
 denied=paid*ratio
 return FinanceResult({'인정이자 시가':fair,'인정이자 익금산입':addition,'지급이자 손금불산입':denied,
 '소득 가산액 합계':addition+denied,'적용 순적수':integral,'수입이자와 차액':difference,'지급이자 안분율':ratio*100},
 '인정이자=대상 순적수×확인 금리/365. 차액이3억원 이상 또는 시가5% 이상이면 차액 익금산입. 지급이자 부인=지급이자×min(1,(업무무관 대여순적수+기타자산적수)/차입금적수).',
 [f'법령 대조 기준일 {AS_OF} · 법인세법 시행령53·88·89조, 시행규칙43조.',
 '단일 특수관계인·동일 적용금리·2026년 기준입니다. 가중평균차입이자율이 원칙이며 당좌4.6% 선택 시 해당 사업연도와 이후2개 사업연도 적용 요건 등을 확인합니다. 금리와 자격은 자동 판정하지 않습니다.',
 '평균 추정은 기중 변동을 재현하지 않습니다. 날짜별 기록은 각 날짜부터 유효한 확정 잔액이며 당일 포함·다음 변경일 제외입니다. 거래 원장의 초일·말일 처리에 맞게 유효일을 정리해야 합니다.',
 '가수금은 동일인·상계 가능 요건을 확인한 잔액만 입력합니다. 각 구간에서 음수 순잔액을0으로 처리하여 다른 기간의 대여금과 잘못 상계하지 않습니다.',
 '인정이자 대상과 지급이자 부인 대상은 별도로 판정한 적수입니다. 직원대여 등 제외요건, 별도 상환·이자약정, 다른 지급이자 손금불산입 우선순위는 수동 검토 범위입니다.',
 '소득처분과 원천징수세액은 귀속자·사외유출 사실을 확인해야 하므로 자동 확정하지 않습니다. 이 결과는 추가 법인세 자체가 아니라 소득금액 조정액입니다. 복수 금리·복수 귀속자·연도를 걸치는 사업연도·신고 단수처리는 미지원입니다.'],
 rows or [{'항목':k,'금액':v} for k,v in [('대상 순적수',integral),('시가 이자',fair),('계상 이자',received),('차액',difference),('익금산입',addition),('지급이자 부인',denied)]],
 units={'적용 순적수':'원·일','지급이자 안분율':'%'})

def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return interest(*values)
