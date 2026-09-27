"""Four retirement modes, independently reconciled with observed JARVIA cases."""
from .finance_models import D, FinanceResult, num, period, coefficients

MODES=('필요 은퇴자금','필요 월 저축액','가능 월 인출액','자금 지속기간')
COMMON=[('현재 나이',35,'세',120),('은퇴 나이',65,'세',120),('계획 종료 나이',85,'세',120),('연 운용수익률',6,'%',100),('연 물가상승률',3,'%',100)]
M=10**12
FIELDS={
 MODES[0]:COMMON+[('현재 연 소득',70000000,'원',M),('은퇴 생활비 비율',70,'%',100),('월 연금',1200000,'원',M),('기타 월 소득',300000,'원',M),('현재 자산',0,'원',M),('소득 대비 저축률',10,'%',100)],
 MODES[1]:COMMON+[('목표 은퇴자금',800000000,'원',M),('현재 자산',30000000,'원',M)],
 MODES[2]:COMMON+[('은퇴 시점 자산',800000000,'원',M)],
 MODES[3]:COMMON+[('인출 시작 시점 자산',600000000,'원',M),('월 인출액',2000000,'원',M)]}

def calculate(mode, values):
 if mode not in FIELDS or len(values)!=len(FIELDS[mode]):raise ValueError('입력 항목을 확인해 주세요.')
 v=[num(x,0,f[3]) for x,f in zip(values,FIELDS[mode])]
 age,retire,end,rate,inflation=v[:5]
 for x in (age,retire,end):period(x,120,True)
 if not age<=retire<end:raise ValueError('현재 나이 ≤ 은퇴 나이 < 계획 종료 나이로 입력해 주세요.')
 r=((1+rate/100)/(1+inflation/100))**(D(1)/12)-1
 n=int((retire-age)*12);k=int((end-retire)*12)
 growth,fv=coefficients(r,n);pv=D(k) if not r else (1-(1+r)**-k)/r
 rows=[];units={}
 notes=['모든 금액은 현재 구매력 기준입니다. 월 저축·인출액은 물가에 맞춰 명목금액이 증가하는 실질 고정액입니다. 세금·수수료는 제외합니다.','연 실질수익률=(1+운용수익률)/(1+물가상승률)−1; 이를 월 유효수익률로 환산합니다. 월말 저축·인출 가정입니다.']
 if mode==MODES[0]:
  income,ratio,pension,other,assets,saving=v[5:];monthly=max(D(0),income*ratio/1200-pension-other);need=monthly*pv;payment=income*saving/1200;projected=assets*growth+payment*fv
  metrics={'필요 은퇴자금':need,'예상 은퇴자산':projected,'부족 자금':max(D(0),need-projected),'월 필요 인출액':monthly}
  formula='월 필요액=max(0,연소득×생활비비율÷12−월연금−기타소득); 필요자금=월필요액×연금현가계수; 예상자산=현재자산 복리+월저축 적립'
 elif mode==MODES[1]:
  target,assets=v[5:];grown=assets*growth;gap=max(D(0),target-grown)
  if n==0 and gap>0:raise ValueError('은퇴까지 저축할 기간이 없습니다. 현재 자산 또는 목표를 조정해 주세요.')
  payment=gap/fv if n else D(0)
  metrics={'필요 월 저축액':payment,'현재 자산의 은퇴시점 가치':grown,'추가 마련 자금':gap}
  formula='월저축=max(0,목표−현재자산×(1+r)^n)÷월말적립계수'
 elif mode==MODES[2]:
  assets=v[5];payment=assets/pv
  metrics={'가능 월 인출액':payment,'인출 기간':D(k)/12};units={'인출 기간':'년'}
  formula='월인출=은퇴시점자산÷월말연금현가계수'
 else:
  assets,payment=v[5:]
  if payment==0 or (r>=0 and assets>0 and assets*r>=payment):
   months=None
  elif assets==0:months=D(0)
  elif r==0:months=assets/payment
  else:months=-(1-assets*r/payment).ln()/(1+r).ln()
  metrics={'수학적 지속기간':months/12 if months is not None else '고정 가정상 소진 없음','전액 인출 가능 개월':D(int(months)) if months is not None else '고정 가정상 소진 없음'}
  units={'수학적 지속기간':'년','전액 인출 가능 개월':'개월'}
  formula='기간=−ln(1−자산×r÷월인출)÷ln(1+r); 무이자는 자산÷월인출. 전액 지급 개월은 내림.'
  notes.append('지속기간은 입력한 인출 시작 시점부터 계산합니다. 계획 종료 나이가 소진 기간을 제한하지 않습니다. 수학적 소수 기간과 전액 인출 가능 횟수를 구분합니다.')
 # Advisor ledger uses the same monthly recurrence as the headline formulas.
 if mode in MODES[:2]:
  balance=assets
  rows.append({'경과 개월':0,'자산':balance,'월 흐름':payment})
  for m in range(1,n+1):
   balance=balance*(1+r)+payment
   if m%12==0 or m==n:rows.append({'경과 개월':m,'자산':balance,'월 흐름':payment})
 else:
  balance=assets;horizon=k if mode==MODES[2] else min(1440,int(months)+1) if months is not None else 1440
  rows.append({'경과 개월':0,'자산':balance,'월 흐름':-payment})
  for m in range(1,horizon+1):
   available=balance*(1+r);paid=min(payment,available);balance=max(D(0),available-paid)
   if m%12==0 or m==horizon or balance==0:rows.append({'경과 개월':m,'자산':balance,'월 흐름':-paid})
   if balance==0:break
  if mode==MODES[3]:notes.append('상세 잔액표는 최대 120년까지 표시하며 마지막 달은 가능한 금액만 인출합니다.')
 return FinanceResult(metrics,formula,notes,rows,units)

def run():
 import streamlit as st
 from .coverage_calculator_ui import run as render
 mode=st.selectbox('계산 모드',MODES,key='retirement_mode')
 render(mode,FIELDS,calculate,'은퇴계산기 · 네 가지 계획 시나리오')
