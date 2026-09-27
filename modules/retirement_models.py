"""Retirement scenarios independently implemented from observed inputs and primary sources."""
from .finance_models import D,FinanceResult,num,period,coefficients
NAMES=('은퇴크레바스계산기','국민연금 수령시기계산기','3층연금 점검계산기','연금 인출기간계산기','연금저축·IRP 세액공제계산기','사적연금 과세계산기','일시금·연금 세금비교계산기','IRP 적립계산기')
M=10**12
FIELDS={
NAMES[0]:[('퇴직 나이',60,'세',120),('연금 개시 나이',65,'세',120),('월 생활비',3000000,'원',M),('공백기 월 소득',1000000,'원',M)],
NAMES[1]:[('정상 월 연금액',1200000,'원',M),('정상 개시 나이',65,'세',65),('앞당길 기간',5,'년',5),('미룰 기간',5,'년',5),('자금 사용 종료 나이',90,'세',120)],
NAMES[2]:[('목표 월 생활비',3000000,'원',M),('국민연금 월액',1200000,'원',M),('퇴직연금 월액',500000,'원',M),('개인연금 월액',300000,'원',M)],
NAMES[3]:[('은퇴 시점 자산',500000000,'원',M),('월 인출액',2500000,'원',M),('인출 시작 나이',65,'세',120),('연 운용수익률',4,'%',100),('연 물가상승률',2.5,'%',100)],
NAMES[4]:[('소득금액 (근로소득만 있으면 총급여)',60000000,'원',M),('연금저축 연 납입액',6000000,'원',M),('IRP 연 납입액',3000000,'원',M),('소득 구분: 근로소득만 0 / 종합소득 1',0,'구분',1)],
NAMES[5]:[('연간 과세대상 사적연금',12000000,'원',M),('수령 나이',65,'세',120),('종신계약 요건 충족: 아니오 0 / 예 1',0,'구분',1)],
NAMES[6]:[('퇴직금 총액',100000000,'원',M),('일시금 퇴직소득세 (지방세 포함)',5000000,'원',M)],
NAMES[7]:[('IRP 연 납입액',9000000,'원',18000000),('납입 기간',15,'년',100),('연간 총급여',60000000,'원',M),('연 수익률',4,'%',100),('별도 연금저축 연 납입액',0,'원',18000000),('연금수령 가정 세율',5.5,'%',100)]}
LEGAL_DATE='2026-09-26'
SOURCES={
 'credit':'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1032880515',
 'tax':'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7888&mi=2312',
 'nps':'https://www.nps.or.kr/pnsinfo/ntpsklg/getOHAF0100M0.do'}

def credit(income,pension,irp,comprehensive=False):
 income,pension,irp=map(num,(income,pension,irp))
 eligible_p=min(pension,D(6000000));eligible_i=min(irp,max(D(0),D(9000000)-eligible_p))
 rate=D('.15') if income<=(45000000 if comprehensive else 55000000) else D('.12')
 return eligible_p,eligible_i,rate

def calculate(name,values):
 if name not in FIELDS or len(values)!=len(FIELDS[name]):raise ValueError('입력 항목 수를 확인해 주세요.')
 v=[num(x,0,f[3]) for x,f in zip(values,FIELDS[name])]
 for x,f in zip(v,FIELDS[name]):
  if f[2] in ('세','년','구분'):period(x,f[3],True)
 notes=[];rows=[];units={}
 if name==NAMES[0]:
  age,start,expense,income=v;n=int(max(D(0),start-age)*12);monthly=max(D(0),expense-income);r=(D('1.035')/D('1.025'))**(D(1)/12)-1
  pv=monthly*(1-(1+r)**-n)/r
  metrics={'공백기 필요자금':pv,'공백 기간':D(n)/12,'월 필요액':monthly,'단순 합계':monthly*n};units={'공백 기간':'년'}
  formula='월 부족액=max(0,생활비−소득); 월 실질할인율=(1.035/1.025)^(1/12)−1; 월말 현금흐름 현재가치'
  notes=['운용수익률 3.5%, 물가상승률 2.5%의 고정 가정입니다. 필요자금은 퇴직 시점 구매력 기준입니다.']
 elif name==NAMES[1]:
  base,normal,early,late,end=v
  if normal<60:raise ValueError('정상 개시 나이는 60~65세로 입력해 주세요.')
  em=base*(1-D('.06')*early);lm=base*(1+D('.072')*late)
  metrics={'정상수령 월액':base,'조기수령 월액':em,'연기수령 월액':lm,'조기 총수령액':em*max(D(0),end-normal+early)*12,'정상 총수령액':base*max(D(0),end-normal)*12,'연기 총수령액':lm*max(D(0),end-normal-late)*12,'정상·조기 손익분기':f'{normal+early*em/(base-em):.1f}세' if early and base else '비교 차이 없음','연기·정상 손익분기':f'{normal+late+late*base/(lm-base):.1f}세' if late and base else '비교 차이 없음'}
  formula='조기: 정상월액×(1−0.06×년); 연기: 정상월액×(1+0.072×년); 총액=월액×수령개월'
  notes=['제도 확인일 '+LEGAL_DATE+' · 국민연금공단 안내','조기·연기 수급 자격 충족, 전액 수령 가정. 소득활동 감액·세금·물가·부분 연기는 제외합니다.',SOURCES['nps']]
 elif name==NAMES[2]:
  goal,a,b,c=v;total=a+b+c
  metrics={'부족한 월 생활비':max(D(0),goal-total),'목표 충족률':total/goal*100 if goal else '목표금액 0원','확보한 월 연금':total};units={'목표 충족률':'%'}
  formula='국민연금+퇴직연금+개인연금; 부족액=max(0,목표−합계)';notes=['동일한 수령 시점·화폐가치의 월액을 입력합니다. 물가와 세금은 별도 반영하지 않습니다.']
 elif name==NAMES[3]:
  assets,withdraw,age,rate,inflation=v;r=((1+rate/100)/(1+inflation/100))**(D(1)/12)-1
  if withdraw==0 or (r>=0 and assets*r>=withdraw and assets>0):months=None;balance=assets
  else:
   balance=assets;months=0
   for m in range(1,120*12+1):
    after=balance*(1+r)-withdraw
    if after<0:break
    months=m;balance=after
    if m%12==0:rows.append({'경과 개월':m,'잔액':balance})
    if balance==0:break
   if months==1440:months=None
  metrics={'전액 인출 가능 개월':D(months) if months is not None else '120년 내 소진 없음','전액 인출 가능 기간':D(months)/12 if months is not None else '120년 이상','마지막 전액 인출 나이':f'{age+D(months)/12:.1f}세' if months is not None else '기간 내 소진 없음'};units={'전액 인출 가능 개월':'개월','전액 인출 가능 기간':'년'}
  formula='월 실질수익률로 운용 후 월말 인출; 전액 인출 가능한 달까지 집계'
  notes=['월 인출액은 현재 구매력 유지 가정입니다. 마지막 부분 인출은 전액 인출 횟수에서 제외합니다.']
 elif name==NAMES[4]:
  income,pension,irp,kind=v;ep,ei,rate=credit(income,pension,irp,bool(kind));tax=(ep+ei)*rate
  metrics={'세액공제 가능액 (지방세 효과 포함)':tax*D('1.1'),'소득세 공제 가능액':tax,'지방세 감소 효과':tax*D('.1'),'공제 대상 합계':ep+ei,'적용 공제율 (지방세 포함)':rate*110,'연금저축 인정액':ep,'IRP 인정액':ei};units={'적용 공제율 (지방세 포함)':'%'}
  formula='연금저축 인정=min(납입,600만원); IRP 인정=min(납입,900만원−연금저축 인정); 소득구분별12/15% 공제, 지방세 효과10%'
  notes=['법령 대조 기준일 '+LEGAL_DATE+' · 소득세법 제59조의3','실제 환급액이 아닌 공제 가능액입니다. 납부할 소득세·다른 공제에 따라 사용 가능한 공제액이 제한됩니다. ISA 전환 추가한도와 이전·퇴직금 재원은 제외합니다.',SOURCES['credit']]
 elif name==NAMES[5]:
  taxable,age,lifetime=v
  if age<55:raise ValueError('이 화면은 55세 이상 적법한 연금수령을 가정합니다.')
  low=D('.055') if age<70 else D('.044') if age<80 else D('.033')
  if lifetime:low=min(low,D('.033'))
  rate=D('.165') if taxable>15000000 else low;tax=taxable*rate
  metrics={'분리과세 선택 시 세금':tax,'적용 세율':rate*100,'세후 수령액':taxable-tax,'연령·계약 기준 원천징수세율':low*100};units={'적용 세율':'%','연령·계약 기준 원천징수세율':'%'}
  formula='과세대상 사적연금 1500만원 이하: 연령별5.5/4.4/3.3%; 초과:16.5% 분리과세 선택 시나리오'
  notes=['세제 기준일 2026-01-01 · 대조일 '+LEGAL_DATE,'세액공제 받은 납입액·운용수익 재원만 입력합니다. 이연퇴직소득·과세제외 원금·부득이한 인출은 제외합니다. 1500만원 초과 시 종합과세 선택과의 유불리는 별도입니다.',SOURCES['tax']]
 elif name==NAMES[6]:
  amount,tax=v
  if tax>amount:raise ValueError('퇴직소득세는 퇴직금 총액을 넘을 수 없습니다.')
  metrics={'일시금 세금':tax,'1~10년차 동일재원 세금':tax*D('.7'),'11~20년차 동일재원 세금':tax*D('.6'),'21년차 이후 동일재원 세금':tax*D('.5')}
  formula='비교 대상 이연퇴직소득에 귀속되는 퇴직소득세 × 수령연차별 70/60/50%'
  notes=['적용 기준일 2026-01-01 · 대조일 '+LEGAL_DATE,'동일한 재원을 각 수령연차에 받았을 때의 비교입니다. 전체 퇴직금을 여러 해에 나눠 받을 때는 연차별 인출액에 배분해야 합니다. 연금수령 요건·한도 충족 가정.',SOURCES['tax']]
 else:
  annual,years,income,rate,other,taxrate=v
  if annual+other>18000000:raise ValueError('일반 연금계좌 합산 납입은 연 1800만원 이하로 입력해 주세요.')
  ep,ei,credit_rate=credit(income,other,annual);year_credit=ei*credit_rate*D('1.1');factor=coefficients(rate/100,int(years))[1];total=annual*factor;principal=annual*years;untaxed=(annual-ei)*years;taxable=max(D(0),total-untaxed);tax=taxable*taxrate/100
  metrics={'최종 세후 자산 (가정)':total-tax,'연간 세액공제 가능액':year_credit,'기간 총 세액공제 가능액':year_credit*years,'세전 평가액':total,'과세제외 납입원금':untaxed,'가정 인출세액':tax}
  formula='매년 말 납입 복리 적립; 세액공제 미적용 원금은 과세대상에서 제외; 나머지에 입력한 가정세율 적용'
  notes=['세액공제 법령 대조일 '+LEGAL_DATE,'전 기간 동일 소득·공제한도를 가정합니다. 공제액은 재투자하지 않습니다. 세후 자산은 적법한 연금수령으로 분산 인출하는 단순 가정이며 일시금 실수령액이 아닙니다. 실제 연간 과세대상액·나이·공제 사용 여부에 따라 세금이 달라집니다.',SOURCES['credit'],SOURCES['tax']]
 if not rows:rows=[{'항목':k,'결과':str(x)} for k,x in metrics.items()]
 return FinanceResult(metrics,formula,notes,rows,units)
