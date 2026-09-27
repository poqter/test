"""DC minimum funding, actual deductions and officer retirement reconciliation."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='DC부담금 한도계산기';M=10**12
MODES=('직원 최소 부담금으로 계획','실제 납입액으로 계산')
STATES=('임원 없음','임원 재직 중','임원 당기 퇴직')
FIELDS={NAME:[('가입 직원 연간 임금총액',600000000,'원',M),('직원 계산 방식',MODES[0],'선택',MODES),
 ('직원 실제 납입액',0,'원',M),('임원 상태',STATES[0],'선택',STATES),('임원 당기 실제 부담금',0,'원',M),
 ('퇴직 임원 과거 누적 부담금',0,'원',M),('퇴직 임원 법인세법상 한도 확인액',0,'원',M),
 ('퇴직 임원 한도·누적액 확인','아니요','선택',('아니요','예')),
 ('DC 손금 반영 전 법인 과세표준',500000000,'원',M),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',('아니요','예'))]}
def dc(wages=600000000,mode=MODES[0],paid=0,state=STATES[0],officer=0,prior=0,limit=0,confirmed='아니요',base=500000000,small='아니요'):
 wages,paid,officer,prior,limit,base=map(num,(wages,paid,officer,prior,limit,base))
 if mode not in MODES or state not in STATES or confirmed not in ('예','아니요') or small not in ('예','아니요'):raise ValueError('계산 조건을 확인해 주세요.')
 if mode==MODES[0] and paid:raise ValueError('실제 납입액이 있으면 실제 납입 방식으로 바꾸세요.')
 if state==STATES[0] and (officer or prior or limit):raise ValueError('임원이 없으면 임원 금액은 0원이어야 합니다.')
 if state!=STATES[2] and (prior or limit):raise ValueError('퇴직 시 정산 금액은 임원 당기 퇴직에서 입력하세요.')
 if state==STATES[2] and confirmed!='예':raise ValueError('퇴직 임원의 누적 부담금과 법인 손금 한도를 확인해 주세요.')
 minimum=wages/12;staff=minimum if mode==MODES[0] else paid
 excess=max(D(0),prior+officer-limit) if state==STATES[2] else D(0)
 denied=min(officer,excess);recapture=max(D(0),excess-officer)
 net=staff+officer-denied-recapture;after=max(D(0),base-net)
 before_tax=bracket(base,small=='예')*D('1.1');after_tax=bracket(after,small=='예')*D('1.1')
 return FinanceResult({'직원 최소 부담금':minimum,'직원 납입 부족액':max(D(0),minimum-staff),
 '당기 손금산입액':staff+officer-denied,'임원 당기 손금불산입액':denied,'과거 부담금 익금산입액':recapture,
 '순 소득 감소액':net,'반영 후 과세표준':after,'법인세·지방세 감소 추정':before_tax-after_tax},
 '직원 최소=연간 임금/12. 임원 퇴직 누적초과=max(0,과거+당기부담금−법인한도). 당기부담금까지 손금불산입, 나머지는 익금산입. 전후 과세표준의 누진세액 차이로 비교.',
 [f'법령 대조 기준일 {AS_OF} · 근로자퇴직급여 보장법20조, 법인세법 시행령44조의2(3), 법인세법55조, 지방세법103조의20.',
 '1/12은 직원 최소 부담금이며 손금 상한이 아닙니다. 계획 모드는 적격 DC에 해당 금액을 실제 납입한다는 가정입니다. 실제 방식은 납입액 전액을 손금으로 계산하고 부족액을 별도 표시합니다.',
 '임원에게 직원의 1/12을 자동 적용하지 않습니다. 임원 재직 중 납입분은 전액 손금, 퇴직 시 누적액을 법인 손금 한도로 정산합니다. 한도는 개인 퇴직소득 한도와 다릅니다.',
 '임원 퇴직 계산은 동일 임원 1명 기준입니다. 여러 명의 한도와 부담금을 합쳐 상계하지 마세요. 한도 금액은 정관·규정 등 법인세법상 적격 금액을 확인한 값입니다.',
 '2026년 연간 일반 법인 표준세율 기준이며 공제감면·최저한세·결손금 이월효과·퇴직충당금 전환·지연이자·휴직기간 특례는 미반영합니다. 음수 세액감소는 세부담 증가입니다.',
 '직원별 가입기간·임금·최저부담금 충족 여부는 각각 확인해야 하며 직원 총액의 부족액0이 개별 직원 충족을 보장하지 않습니다.'],
 [{'항목':k,'금액':v} for k,v in [('직원 납입 가정/실제',staff),('임원 당기 납입',officer),('임원 누적 초과',excess),('반영 전 세액',before_tax),('반영 후 세액',after_tax)]])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return dc(*values)
