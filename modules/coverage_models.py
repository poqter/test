"""Independent coverage planning scenarios, KRW. Source observations in audit/evidence."""
from .finance_models import D, FinanceResult, num, period, fv

NAMES=('사망보장 필요액계산기','중대질병 보장계산기','간병·장기요양 필요액계산기','자녀보험 필요액계산기','적정보험료계산기','정기·종신 비교계산기','의료비 부담계산기')
# label, default, unit, maximum
FIELDS={
NAMES[0]:[('유족 월 생활비',3000000,'원',10**12),('생활비 필요 기간',20,'년',120),('자녀 교육비 총액',100000000,'원',10**12),('남은 부채',200000000,'원',10**12),('비상자금',10000000,'원',10**12),('즉시 현금화 가능 자산',50000000,'원',10**12),('기존 사망보장액',300000000,'원',10**12)],
NAMES[1]:[('예상 치료비',50000000,'원',10**12),('월 소득',5000000,'원',10**12),('회복·휴직 기간',12,'개월',1440),('간병·요양 추가비용',10000000,'원',10**12),('기존 진단비 보장액',30000000,'원',10**12)],
NAMES[2]:[('월 간병·요양비',2000000,'원',10**12),('간병 예상 기간',5,'년',120),('몇 년 뒤 시작',20,'년',120),('본인부담 비율',20,'%',100),('기존 간병보험 월 보장액',300000,'원',10**12)],
NAMES[3]:[('진단비 목표액',30000000,'원',10**12),('1일 입원비',100000,'원',10**12),('예상 입원일수',30,'일',36500),('수술 대비 자금',10000000,'원',10**12),('교육 연속성 자금',20000000,'원',10**12),('기존 자녀보험 보장액',10000000,'원',10**12)],
NAMES[4]:[('월 소득',5000000,'원',10**12),('보장성 보험료 월납',400000,'원',10**12),('저축성 보험료 월납',300000,'원',10**12)],
NAMES[5]:[('종신보험 월 보험료',300000,'원',10**12),('정기보험 월 보험료',80000,'원',10**12),('납입 기간',20,'년',120),('보장금액',300000000,'원',10**12),('차액 운용수익률',4,'%',100)],
NAMES[6]:[('연간 의료비',5000000,'원',10**12),('누적 기간',10,'년',120),('급여 비율',60,'%',100),('의료비 상승률',4,'%',100)]}

REAL=D('1.04')/D('1.025')
def pv(monthly,years):
    r=REAL**(D(1)/12)-1
    return monthly*(1-(1+r)**(-int(years)*12))/r

def calculate(name,values):
    if name not in FIELDS or len(values)!=len(FIELDS[name]):raise ValueError('입력 항목을 확인해 주세요.')
    v=[num(x,0,f[3]) for x,f in zip(values,FIELDS[name])]
    for x,f in zip(v,FIELDS[name]):
        if f[2] in ('년','개월','일'):period(x,f[3],allow_zero=True)
    rows=[];units={};notes=[]
    if name==NAMES[0]:
        m,y,edu,debt,emergency,assets,insured=v
        life=pv(m,y);total=life+edu+debt+emergency;ready=assets+insured
        metrics={'추가 필요보장액':max(D(0),total-ready),'총 필요자금':total,'준비된 자금':ready}
        parts={'생활비 현재가치':life,'교육비':edu,'부채 상환':debt,'비상자금':emergency,'보유 자산':assets,'기존 보장':insured}
        formula='월 실질할인율 = (1.04 / 1.025)^(1/12) − 1; 생활비를 매월 말 할인한 현재가치 + 교육비 + 부채 + 비상자금 − 자산 − 기존 보장'
        notes=['운용수익률 연 4%, 물가상승률 연 2.5% 가정. 유족연금·퇴직금은 별도 반영하지 않습니다.']
    elif name==NAMES[1]:
        treatment,income,months,extra,insured=v;lost=income*months;total=treatment+lost+extra
        metrics={'추가 필요보장액':max(D(0),total-insured),'총 필요자금':total,'소득 공백 손실':lost}
        parts={'치료비':treatment,'소득 손실':lost,'간병·요양 추가비용':extra,'기존 보장':insured}
        formula='치료비 + 월 소득 × 휴직 개월 + 추가비용 − 기존 진단비 (0원 하한)'
    elif name==NAMES[2]:
        monthly,years,delay,share,insured=v;burden=monthly*share/100;start=pv(burden,years);present=start/REAL**delay;cover=pv(insured,years)/REAL**delay
        metrics={'추가 필요자금':max(D(0),present-cover),'월 본인부담액':burden,'현재가치 필요액':present}
        parts={'간병 시작 시점 필요액':start,'기존 보장 현재가치':cover}
        formula='월 비용 × 본인부담률의 월말 현금흐름을 실질할인율로 할인; 간병 시작까지 추가 할인; 기존 월 보장의 현재가치를 차감'
        notes=['운용수익률 연 4%, 물가상승률 연 2.5% 가정. 본인부담률은 전체 비용에 적용하는 시나리오 입력값입니다.','기존 월 보장도 같은 실질할인율로 할인하는 원본 비교 모형입니다. 실제 정액 급부·비급여·보장기간은 계약별로 확인해야 합니다.']
    elif name==NAMES[3]:
        diagnosis,daily,days,surgery,education,insured=v;hospital=daily*days;total=diagnosis+hospital+surgery+education
        metrics={'추가 필요보장액':max(D(0),total-insured),'총 필요보장':total,'입원비 합계':hospital}
        parts={'진단비':diagnosis,'입원비':hospital,'수술 대비 자금':surgery,'교육 연속성 자금':education,'기존 보장':insured}
        formula='진단비 + 일 입원비 × 입원일수 + 수술자금 + 교육자금 − 기존 보장 (0원 하한)'
    elif name==NAMES[4]:
        income,risk,saving=v
        if income==0:raise ValueError('비중을 계산하려면 월 소득을 0원보다 크게 입력해 주세요.')
        ratio=risk/income*100;low=income*D('.10');high=income*D('.12')
        metrics={'보장성 보험료 비중':ratio,'10% 기준까지 차액':low-risk,'12% 기준까지 차액':high-risk,'전체 보험료 비중':(risk+saving)/income*100}
        units={'보장성 보험료 비중':'%','전체 보험료 비중':'%'}
        parts={'10% 참고금액':low,'12% 참고금액':high,'보장성 보험료':risk,'저축성 보험료':saving}
        formula='보장성 보험료 ÷ 월 소득 × 100; 참고금액 − 보장성 보험료'
        notes=['10%·12%는 비교용 가정이며 법정 기준이나 가입 권고가 아닙니다. 지출·부채·보장내용을 함께 판단해야 합니다.','원본의 남은 여력은 10% 구간에서 기준이 바뀝니다. 화랑은 두 기준의 차액을 각각 표시합니다.']
    elif name==NAMES[5]:
        whole,term,years,coverage,rate=v;n=int(years)*12;delta=whole-term;monthly=max(D(0),delta);r=(1+rate/100)**(D(1)/12)-1
        end=fv(D(0),monthly,r,n)
        metrics={'차액 운용 시 최종 금액':end,'월 보험료 차이':delta,'납입 기간 총 차액':delta*n}
        parts={'보장금액':coverage,'종신보험 총 납입액':whole*n,'정기보험 총 납입액':term*n,'운용 원금':monthly*n}
        formula='연 유효수익률을 월 수익률로 환산; 양수인 보험료 차액을 매월 말 적립'
        notes=[f'연 유효수익률 {rate}% 가정. 세금·투자비용·종신보험 해지환급금은 반영하지 않습니다.','정기보험 종료 후 보장 차이는 금액 비교에 포함되지 않습니다. 정기보험료가 더 비싸면 차액 투자는 0원입니다.']
    else:
        annual,years,share,inflation=v;after=annual*(share/100*D('.2')+(1-share/100)*D('.3'));benefit=annual-after
        cumulative=D(0)
        for year in range(int(years)):
            factor=(1+inflation/100)**year;cumulative+=benefit*factor
            rows.append({'연차':year+1,'보험 없을 때 부담':annual*factor,'보험 적용 후 부담':after*factor,'누적 보장 효과':cumulative})
        metrics={'기간 누적 보장 효과':cumulative,'보험 없을 때 첫해 부담':annual,'보험 적용 후 첫해 부담':after}
        parts={'첫해 보장 효과':benefit}
        formula='급여 부분 × 20% + 비급여 부분 × 30%; 매년 의료비 상승률을 적용해 차액 누적'
        notes=[f'급여 비율 {share}%, 급여 자기부담 20%, 비급여 자기부담 30%, 의료비 상승률 {inflation}%의 단순 시나리오입니다.','연간 의료비는 건강보험 적용 후 실손 청구 대상 본인부담액입니다. 면책·공제금·한도·보험료는 제외하며 실제 보험금 산정용이 아닙니다.']
    detail=[{'항목':k,'금액':v} for k,v in parts.items()]
    if rows:notes.append('연도별 누적값과 결과는 동일한 계산값을 사용합니다.')
    return FinanceResult(metrics,formula,notes,rows or detail,units)
