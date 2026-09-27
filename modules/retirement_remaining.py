"""Saving and withdrawal-order models from observed scenarios."""
from .finance_models import D,FinanceResult,num,period,coefficients
SAVE='은퇴저축계산기';ORDER='연금 인출순서계산기';M=10**12
FIELDS={SAVE:[('현재 나이',40,'세',120),('은퇴 나이',60,'세',120),('목표 자금 (오늘 가치)',500000000,'원',M),('현재 자산',50000000,'원',M),('연 운용수익률',4,'%',100),('연 물가상승률',2.5,'%',100)]}

def saving(name,values):
 if name!=SAVE or len(values)!=6:raise ValueError('입력 항목을 확인해 주세요.')
 age,retire,target,assets,rate,inflation=[num(v,0,f[3]) for v,f in zip(values,FIELDS[SAVE])]
 age=period(age,120,True);retire=period(retire,120,True)
 if retire<age:raise ValueError('은퇴 나이는 현재 나이 이상이어야 합니다.')
 n=(retire-age)*12;r=((1+rate/100)/(1+inflation/100))**(D(1)/12)-1;g,f=coefficients(r,n);grown=assets*g;gap=max(D(0),target-grown)
 if n==0 and gap:raise ValueError('저축 기간이 없습니다. 부족한 목표액을 현재 자산으로 보완해야 합니다.')
 payment=gap/f if n else D(0);balance=assets;rows=[{'경과 개월':0,'자산':balance}]
 for m in range(1,n+1):
  balance=balance*(1+r)+payment
  if m%12==0:rows.append({'경과 개월':m,'자산':balance})
 return FinanceResult({'매달 필요한 저축액':payment,'현재 자금의 은퇴시점 가치':grown,'추가 마련 자금':gap,'총 추가 납입액':payment*n,'추가 납입금 운용손익':gap-payment*n},'월 실질수익률=((1+수익률)/(1+물가))^(1/12)−1; 월저축=max(0,목표−현재자산 복리)÷월말적립계수',['목표·저축액은 오늘 구매력 기준입니다. 매월 명목 납입액을 물가만큼 늘려 실질 저축액을 유지합니다. 세금·수수료는 제외합니다.'],rows)

def withdrawal(monthly,years,accounts,net=False):
 need=num(monthly)*period(years,120,True)*12
 if not 1<=len(accounts)<=3:raise ValueError('계좌는 1~3개를 입력해 주세요.')
 parsed=[]
 for i,(name,balance,rate) in enumerate(accounts):
  if not str(name).strip():raise ValueError('계좌 이름을 입력해 주세요.')
  parsed.append((str(name),num(balance),num(rate,0,100),i))
 parsed.sort(key=lambda a:(a[2],a[3]));left=need;tax=total=D(0);rows=[]
 for name,balance,rate,_ in parsed:
  factor=1-rate/100
  gross=min(balance,left/factor) if net and factor else D(0) if net else min(balance,left)
  levy=gross*rate/100;received=gross-levy;left=max(D(0),left-(received if net else gross));total+=gross;tax+=levy
  rows.append({'순위':len(rows)+1,'계좌':name,'가정 실효세율 (%)':rate,'인출액':gross,'가정 세금':levy,'세후 조달액':received,'인출 후 잔액':balance-gross})
 first=next((r['계좌'] for r in rows if r['인출액']>0),'인출 없음')
 return FinanceResult({'먼저 인출할 계좌':first,'기간 필요액':need,'총 인출액':total,'가정 세금 합계':tax,'세후 조달액':total-tax,'부족액':left},'입력한 고정 실효세율 오름차순으로 배분; 세후 목표 모드는 인출액=필요액÷(1−실효세율)', ['입력값 기준의 정적 비교입니다. 실효세율은 인출액 전체 대비 예상 세금 비율이며 법정세율을 자동 적용하지 않습니다. 예적금 원금에 이자소득세율 15.4%를 그대로 입력하면 안 됩니다.','기본 세전 인출 목표 모드는 원본 비교 기준입니다. 세후 생활비 충족 여부는 세후 목표 모드를 선택하세요.','계좌 운용수익·물가·연금수령 한도·연도별 과세·건강보험료·계좌 내 법정 인출순서는 반영하지 않습니다. 실제 세금 최적화 결과를 의미하지 않습니다.'],rows)

def run_order():
 import streamlit as st
 from .coverage_calculator_ui import run as render
 net=st.radio('목표 금액 기준',['세전 인출액','세후 생활비'],key='wo_basis')=='세후 생활비'
 fields=[('월 목표액',3000000,'원',M),('기간',20,'년',120)]
 for i,(name,rate) in enumerate([('연금저축·IRP',5.5),('일반 투자계좌',0.0),('예적금',0.0)]):
  fields.extend([(f'계좌 {i+1} 이름',name,'문자',100),(f'계좌 {i+1} 잔액',100000000,'원',M),(f'계좌 {i+1} 예상 실효세율',rate,'%',100)])
 title=ORDER+(' · 세후 목표' if net else ' · 세전 목표')
 def calc(name,v):return withdrawal(v[0],v[1],[tuple(v[i:i+3]) for i in (2,5,8)],net)
 render(title,{title:fields},calc,'계좌별 고정 실효세율 시나리오')
