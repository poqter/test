"""Three cash-gap scenarios: arithmetic only, no tax or insurance eligibility decision."""
from .finance_models import D,num,period,FinanceResult
NAMES=('키맨리스크계산기','지분 매입자금계산기','승계 재원계산기');M=10**12
FIELDS={NAMES[0]:[('월 영업손실 예상액',20000000,'원',M),('영향 지속 기간',12,'개월',1200),('인력 대체 비용',100000000,'원',M),('상환 필요 연대보증 채무',1000000000,'원',M),('즉시 동원 가능 자금',0,'원',M),('이 상황에 지급 가능한 기존 보장액',0,'원',M)],
 NAMES[1]:[('회사 전체 지분 가치',5000000000,'원',M),('매입할 지분율',30.0,'%',100),('이미 준비된 자금',200000000,'원',M)],
 NAMES[2]:[('승계 주식 평가액 (참고)',3000000000,'원',M),('별도 계산한 예상 상속·증여세',800000000,'원',M),('승계 운영자금',200000000,'원',M),('이미 준비된 재원',0,'원',M)]}
def gap_result(need,available,components,formula,notes):
 gap=max(D(0),need-available);surplus=max(D(0),available-need)
 metrics={'추가 필요자금':gap,'총 필요자금':need,'준비된 자금·보장':available,'필요액 초과 준비자금':surplus}
 return FinanceResult(metrics,formula,notes,[{'항목':k,'금액':v} for k,v in components]+[{'항목':k,'금액':v} for k,v in metrics.items()])
def keyman(monthly=20000000,months=12,replacement=100000000,debt=1000000000,cash=0,insurance=0):
 monthly,replacement,debt,cash,insurance=map(num,(monthly,replacement,debt,cash,insurance));months=period(months,1200,True)
 loss=monthly*months
 return gap_result(loss+replacement+debt,cash+insurance,[('영업 공백 손실',loss),('인력 대체 비용',replacement),('상환 필요 채무',debt)],'월 영업손실×영향 개월+대체비용+상환 필요 채무−동원 자금−지급 가능한 보장액, 부족액 최저 0원.',[
 '사용자 가정에 따른 현금 부족 시나리오입니다. 채무가 즉시 전액 상환된다고 자동 판단하지 않으며 실제 필요한 상환액을 입력합니다.',
 '영업손실·대체비용·채무에 같은 현금 소요를 중복 넣지 않습니다. 보장액은 같은 사건에서 실제 사용 가능한 금액이며 지급 시점·수익자·면책·세금은 별도 확인합니다.',
 '물가·할인·차입금 이자와 지급시차는 미반영입니다. 계산된 부족액이 보험 가입 권고액이나 보장 지급 확정액은 아닙니다.'])
def buyout(value=5000000000,share=30,cash=200000000):
 value,cash=map(num,(value,cash));share=num(share,0,100);price=value*share/100
 return gap_result(price,cash,[('회사 전체 지분 가치',value),('매입 지분 가액',price)],'회사 전체 지분 가치×매입 지분율÷100−준비자금, 부족액 최저 0원.',[
 '회사 전체 지분 가치와 입력 지분율의 단순 비례 추정입니다. 부채 포함 기업가치 대신 주주 지분 가치를 입력합니다.',
 '시가 평가·경영권 프리미엄·종류주식·당사자 합의·자기주식 취득 요건을 자동 판단하지 않습니다. 세금·수수료·조달 이자는 제외합니다.'])
def succession(value=3000000000,tax=800000000,working=200000000,cash=0):
 value,tax,working,cash=map(num,(value,tax,working,cash))
 return gap_result(tax+working,cash,[('주식 평가액 (참고)',value),('입력한 예상 세액',tax),('승계 운영자금',working)],'입력한 예상 상속·증여세+운영자금−준비 재원, 부족액 최저 0원. 주식 평가액은 필요 현금에 더하지 않습니다.',[
 '세액을 새로 산출하는 계산기가 아닙니다. 세금 계산기에서 검토한 예상 납부세액을 입력하며 주식 평가액은 설명용 참고값입니다.',
 '연부연납·분납·물납·차입·보험금 지급 시점과 이자·운영자금의 기간별 흐름은 미반영입니다. 준비 재원과 운영자금을 중복 계상하지 않습니다.'])
def calculate(name,values):
 if name not in FIELDS or len(values)!=len(FIELDS[name]):raise ValueError('계산기와 입력 항목을 확인하세요.')
 return {NAMES[0]:keyman,NAMES[1]:buyout,NAMES[2]:succession}[name](*values)
