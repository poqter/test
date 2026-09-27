"""Supplementary unlisted equity valuation, rules checked 2026-09-27."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
NAME='비상장주식 평가계산기'; M=10**12
METHODS=('일반 가중평균','사업개시 전·3년 미만','청산·휴폐업·계속사업 곤란','잔여 존속기한 3년 이내','3년 연속 결손')
EXEMPT=('해당 없음','중소기업','직전 3년 평균매출 5천억원 미만 중견기업','법정 계속 결손','시행령 제53조 제8항 기타 제외 확인')
FACTORS=('일반 0%','IT 가정 +20%','바이오 가정 +30%','브랜드 가정 +10%','F&B 가정 -10%')
FIELDS={NAME:[('평가기준일','2026-09-27','날짜',None),('현재 발행주식 총수',100000,'주',10**10),('액면가 (평가 산식에는 미사용)',5000,'원',M),('법정 부동산 비율',0.0,'%',100),('자산 중 주식 비율',0.0,'%',100),('평가 조건',METHODS[0],'선택',METHODS),('자산 장부가',3000000000,'원',M),('자산 평가 조정액 (음수 가능)','0','문자',30),('부채 장부가',1000000000,'원',M),('부채 평가 조정액 (음수 가능)','0','문자',30)] + [(f'{y}년 전 당기순손익','300000000','문자',30) for y in (1,2,3)]+[(f'{y}년 전 순손익 평가 조정액','0','문자',30) for y in (1,2,3)]+[(f'{y}년 전 법정 조정 발행주식수',100000,'주',10**10) for y in (1,2,3)]+[('최대주주·특수관계인 여부','아니오','선택',('아니오','예')),('할증 제외 요건',EXEMPT[0],'선택',EXEMPT),('참고 시나리오 보정',FACTORS[0],'선택',FACTORS),('참고 경영권 프리미엄',0.0,'%',100),('시가 우선·세법상 조정금액 및 적용 요건 확인','미확인','선택',('미확인','확인'))]}
def signed(v):return num(str(v).replace(',',''),-M,M)
def value(date='2026-09-27',shares=100000,par=5000,re=0,stock=0,method=METHODS[0],assets=3000000000,asset_adj='0',liab=1000000000,liab_adj='0',p1='300000000',p2='300000000',p3='300000000',a1='0',a2='0',a3='0',n1=100000,n2=100000,n3=100000,major='아니오',exempt=EXEMPT[0],factor=FACTORS[0],premium=0,confirmed='미확인'):
 from datetime import date as dt
 when=dt.fromisoformat(str(date))
 if not dt(2026,2,27)<=when<=dt(2026,9,27):raise ValueError('확인한 법령 적용 범위는 2026-02-27~2026-09-27입니다.')
 if confirmed!='확인':raise ValueError('인정 시가 우선 적용 여부, 평가 방법과 세법상 자산·부채·순손익 조정금액을 확인해 주세요.')
 if method not in METHODS or exempt not in EXEMPT or factor not in FACTORS or major not in ('예','아니오'):raise ValueError('조건을 확인하세요.')
 shares=period(shares,10**10);num(par);re=num(re,0,100);stock=num(stock,0,100);premium=num(premium,0,100)
 net_assets=num(assets)+signed(asset_adj);debts=num(liab)+signed(liab_adj)
 if net_assets<0 or debts<0:raise ValueError('조정 후 자산·부채는 음수일 수 없습니다.')
 nav=max(D(0),net_assets-debts)/shares
 profits=[signed(p)+signed(a) for p,a in zip((p1,p2,p3),(a1,a2,a3))]
 ns=[period(n,10**10) for n in (n1,n2,n3)]
 weighted=max(D(0),sum(p/n*w for p,n,w in zip(profits,ns,(3,2,1)))/6)
 earnings=weighted/D('.1');ew=2 if re>=50 else 3
 blend=(earnings*ew+nav*(5-ew))/5
 floor=nav*(1 if re>=80 or stock>=80 else D('.8'))
 if method in METHODS[1:4]:base=nav
 else:base=max(blend,floor)
 # Continuing tax losses affect premium eligibility, not an automatic NAV-only rule.
 surcharge=D('.2') if major=='예' and exempt==EXEMPT[0] else D(0)
 tax_value=base*(1+surcharge)
 scenario=base*(D(1)+ (D(0),D('.2'),D('.3'),D('.1'),D('-.1'))[FACTORS.index(factor)])*(1+premium/100)
 metrics={'1주당 보충적 평가액':tax_value,'입력 할증 조건을 일괄 적용한 전체 주식 참고액':tax_value*shares,'1주당 순자산가치':nav,'1주당 순손익가치':earnings,'할증 전 평가액':base,'가정에 따른 1주당 참고값':scenario}
 notes=['법령 기준·대조일 2026-09-27. 상증세법 제63조, 시행령 제53~56조, 시행규칙 제17조. 시행령은 2026-09-18 시행본, 환원율 연 10%.',
 '인정 시가가 없는 경우의 보충적 평가입니다. 자산·부채 조정에 영업권 포함 여부 등 세법상 평가를 반영하고, 순손익 조정액은 당기순손익을 시행령 제56조의 평가용 순손익으로 맞추는 차액입니다.',
 '과거 주식수는 증감자 등을 반영해 법정 조정한 수를 입력합니다. 자기주식의 상호참조 평가·종류주식 차등 권리·평가심의위원회 평가액은 자동 산출하지 않습니다.',
 '2026-02-27 이후 부동산 또는 주식 비율 80% 이상은 가중평균액과 순자산가치 중 큰 금액입니다. 3년 결손 자체는 순자산 100% 평가 사유가 아닙니다.',
 '할증 제외는 법정 자격을 확인하여 선택합니다. 계속 결손은 회계상 3개년 적자와 동일하지 않습니다. 최대주주 할증은 해당 주주의 주식에만 적용하며 전체 참고액은 회사의 실제 거래가격이 아닙니다.',
 '업종 보정·경영권 프리미엄은 사용자가 선택한 가정이며 법정 세무 평가나 검증된 시장가격이 아닙니다. 액면가는 참고 입력입니다.']
 rows=[{'항목':f'{y}년 전 조정 순손익','금액':p,'평가용 주식수':n} for y,p,n in zip((1,2,3),profits,ns)]+[{'항목':'가중평균 평가액','금액':blend},{'항목':'일반 평가 하한','금액':floor},{'항목':'할증률','금액':surcharge}]
 return FinanceResult(metrics,'순손익: 3개년 1주당 평가용 순손익×(3,2,1)/6÷10%. 일반 손익:자산 3:2, 부동산 50% 이상 2:3. 일반 순자산 하한 80%, 법정 80% 보유 법인 100%. 해당 특수 사유는 순자산 단독.',notes,rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return value(*values)
