"""Gift planning scenarios share the ordinary gift-tax engine."""
from datetime import date, timedelta
from .finance_models import D, FinanceResult, num, period
from .gift_tax import gift, allowance, RELATIONS, YESNO, AS_OF, NAME, FIELDS, calculate

SPLIT='10년 초과 간격 분할 증여'
DISTRIBUTE='수증자별 분산 증여'
OPTIMIZE='가족별 증여 배분 비교'
from .gift_comparisons import BURDEN,INHERIT,FIELDS as COMPARE_FIELDS,calculate as compare_calculate
PLAN_NOTES=[f'법령 대조 기준일 {AS_OF} · 현재 세법을 고정한 명목금액 시나리오입니다.',
 '거주자·동일 증여자·기존 증여와 사용 공제 없음·기한 내 신고·현금 증여를 가정합니다. 재산가치 변동, 증여자가 대신 내는 세금, 취득세·상속 합산 및 미래 법령 변경은 미반영합니다.']


def _int_won(v):
 n=num(v)
 if n!=int(n):raise ValueError('증여 계획 금액은 원 단위 정수로 입력해 주세요.')
 return int(n)


def _tax(amount,relation,skip=False):
 return gift(cash=amount,relation=relation,skip='예' if skip else '아니요').metrics['이번 증여세 추정액']


def distributed(recipients,comparison_relation=RELATIONS[1]):
 if not 1<=len(recipients)<=30:raise ValueError('수증자는 1~30명입니다.')
 allowance(comparison_relation)
 rows=[];total=D(0);tax=D(0)
 for i,(relation,amount,skip) in enumerate(recipients,1):
  amount=_int_won(amount);allowance(relation)
  if type(skip) is not bool:raise ValueError('세대생략 여부를 확인해 주세요.')
  t=_tax(amount,relation,skip)
  total+=amount;tax+=t
  rows.append({'수증자':i,'관계':relation,'증여액':D(amount),'세대생략':'예' if skip else '아니요','예상 증여세':t})
 single=_tax(total,comparison_relation)
 return FinanceResult({'총 증여액':total,'분산 증여세 합계':tax,'비교 대상 관계':comparison_relation,'비교 대상 1인 증여세':single,'분산 시 세액 차이':single-tax},
  '각 수증자별 공제·과세최저한·세대생략 할증·신고공제를 계산한 뒤 세액을 합산합니다.',
  PLAN_NOTES+['1인 비교 대상 관계를 직접 선택합니다. 손자녀 비교에서는 사망에 따른 예외 없이 할증 대상이라고 가정합니다.'],rows)


def _add_years(d,n):
 try:return d.replace(year=d.year+n)
 except ValueError:return d.replace(year=d.year+n,day=28)


def split(total=1000000000,relation=RELATIONS[1],count=2,birth='1990-01-01',start=AS_OF):
 total=_int_won(total);count=period(count,4)
 if count<2:raise ValueError('분할 횟수는 2~4회입니다.')
 allowance(relation)
 try:
  start=start if type(start) is date else date.fromisoformat(str(start))
  birth=birth if type(birth) is date else date.fromisoformat(str(birth))
 except ValueError:raise ValueError('계획일·생년월일을 확인해 주세요.') from None
 if start.year!=2026:raise ValueError('첫 증여 계획일은 2026년으로 입력해 주세요.')
 if relation in RELATIONS[1:3]:
  if birth>start:raise ValueError('생년월일은 첫 증여일 이전이어야 합니다.')
  age=start.year-birth.year-((start.month,start.day)<(birth.month,birth.day))
  if (relation==RELATIONS[2]) != (age<19):raise ValueError('첫 증여 시점 성년·미성년 선택과 생년월일이 일치하지 않습니다.')
 rows=[];tax=D(0);when=start
 for i in range(count):
  if i:when=_add_years(when,10)+timedelta(days=1)
  rel=relation
  if relation in RELATIONS[1:3]:
   age=when.year-birth.year-((when.month,when.day)<(birth.month,birth.day))
   rel=RELATIONS[2] if age<19 else RELATIONS[1]
  amount=total//count+(1 if i<total%count else 0)
  t=_tax(amount,rel);tax+=t
  rows.append({'회차':i+1,'계획일':when.isoformat(),'관계·나이 구분':rel,'증여액':D(amount),'공제 한도':allowance(rel),'예상 증여세':t})
 single=_tax(total,relation)
 return FinanceResult({'일시 증여세':single,'분할 증여세 합계':tax,'명목 세액 차이':single-tax,'총 증여액':D(total)},
  '원 단위로 균등 분할하고 이전 회차로부터10년+1일 뒤에 다음 증여를 가정합니다. 자녀는 각 계획일의 나이로 공제를 구분합니다.',
  PLAN_NOTES+['첫 증여 시점 미성년이면 생년월일에 따라 이후 성년 공제로 전환합니다. 단순히 미성년 공제를 모든 회차에 반복하지 않습니다.',
  '각 회차 사이 다른 증여가 없어 공제 한도가 회복되는 가정입니다. 원본의 정확히10년 경계 표현 대신10년을 초과하는 계획일을 사용합니다. 증여자 생존·증여 실행·세율 유지가 보장되는 계획은 아닙니다.'],rows)


def optimize(total=1000000000,spouse='예',adults=2,minors=0):
 total=_int_won(total);adults=period(adults,30,True);minors=period(minors,30,True)
 if spouse not in YESNO:raise ValueError('배우자 포함 여부를 확인해 주세요.')
 relations=([RELATIONS[0]] if spouse=='예' else [])+[RELATIONS[1]]*adults+[RELATIONS[2]]*minors
 if not 1<=len(relations)<=30:raise ValueError('배분 대상은 합계1~30명이어야 합니다.')
 caps=[int(allowance(r)) for r in relations];n=len(caps)
 if total<=sum(caps):
  left=total;amounts=[]
  for cap in caps:a=min(cap,left);amounts.append(a);left-=a
 else:
  excess=total-sum(caps);candidates=[]
  # A 500k tax-free threshold creates a discontinuity; uniform division alone
  # is not globally minimal. Enumerate untaxed recipients, then use convex
  # bracket equalisation among the remaining recipients, in whole KRW.
  if excess<=n*499999:
   q,r=divmod(excess,n);bases=[q+(i<r) for i in range(n)]
   candidates.append(bases)
  for untaxed in range(n):
   rest=excess-untaxed*499999
   if rest<0:continue
   q,r=divmod(rest,n-untaxed)
   candidates.append([499999]*untaxed+[q+(i<r) for i in range(n-untaxed)])
  best=min(candidates,key=lambda bases:sum((_tax(cap+base,rel) for cap,base,rel in zip(caps,bases,relations)),D(0)))
  amounts=[c+b for c,b in zip(caps,best)]
 result=distributed([(r,a,False) for r,a in zip(relations,amounts)],relations[0])
 result.metrics['총액 보존 확인']=sum(amounts)==total and '입력 총액과 일치' or '불일치'
 result.formula='기본 공제 한도를 배분한 뒤, 과세최저한50만원 미만에 남길 인원별 후보와 나머지 균등 과표를 비교해 최소 세액 후보를 선택합니다.'
 result.assumptions=PLAN_NOTES+['배우자·자녀의 최초 현금 증여에 한정한 세액 최소 배분입니다. 동일 최소세액 배분이 여러 개일 수 있습니다. 가족별 필요자금·소유권·수익률 등은 최적화 대상에 포함하지 않습니다.',
  '세대생략·기존 공제 사용·혼인출산 공제가 있으면 이 자동 배분 가정에 해당하지 않습니다. 원 단위 배분 후 총액을 보존합니다.']
 return result


def run():
 import streamlit as st
 from .coverage_calculator_ui import run as render
 mode=st.selectbox('증여 계산 방식',('증여세 상세 계산',DISTRIBUTE,BURDEN,SPLIT,INHERIT,OPTIMIZE),key='gift_mode')
 if mode=='증여세 상세 계산':
  render(NAME,FIELDS,calculate,'2026년 증여 · 법령 대조 기준일 '+AS_OF)
 elif mode in (BURDEN,INHERIT):
  render(mode,COMPARE_FIELDS,compare_calculate,'법령 대조 기준일 '+AS_OF+' · 적용 가정을 확인한 비교')
 elif mode==SPLIT:
  fs=[('총 증여 목표액',1000000000,'원',10**12),('첫 증여 관계',RELATIONS[1],'선택',RELATIONS),
      ('분할 횟수',2,'회',4),('자녀 생년월일 (자녀 관계 선택 시)','1990-01-01','날짜',0),('첫 증여 계획일',AS_OF,'날짜',0)]
  render(SPLIT,{SPLIT:fs},lambda _,v:split(*v),'현재 세법 고정 · 10년 초과 간격 시뮬레이션')
 elif mode==OPTIMIZE:
  fs=[('총 증여액',1000000000,'원',10**12),('배우자 포함','예','선택',YESNO),('성년 자녀 수',2,'명',30),('미성년 자녀 수',0,'명',30)]
  render(OPTIMIZE,{OPTIMIZE:fs},lambda _,v:optimize(*v),'현재 가정에서의 세액 최소 배분')
 else:
  count=st.number_input('수증자 수',1,30,3,key='gift_recipient_count')
  fs=[('1인 집중 증여 비교 관계',RELATIONS[1],'선택',RELATIONS)]
  for i in range(count):
   fs.extend([(f'수증자{i+1} 관계',RELATIONS[0] if i==0 else RELATIONS[1],'선택',RELATIONS),
              (f'수증자{i+1} 증여액',600000000 if i==0 else 200000000,'원',10**12),
              (f'수증자{i+1} 손자녀 등 세대생략 대상','아니요','선택',YESNO)])
  render(DISTRIBUTE,{DISTRIBUTE:fs},lambda _,v:distributed([(v[i],v[i+1],v[i+2]=='예') for i in range(1,len(v),3)],v[0]),'수증자별 현금 증여 비교')
