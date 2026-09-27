"""2026 earned income: compare eligible standard and itemized deductions."""
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import progressive_tax, AS_OF
from modules.calculators.pension.retirement_models import credit

NAME='근로소득세계산기';M=10**12
MODES=('유리한 방식 비교','특별공제 적용','표준세액공제 적용')
FIELDS={NAME:[
 ('연간 총급여 (비과세 제외)',60000000,'원',M),
 ('기본공제 대상 인원 (본인 포함)',1,'명',100),
 ('2026년 자녀세액공제 대상 인원 (9세 이상·2017년생 제외)',0,'명',99),
 ('국민연금 등 공적연금 실제 납부액',0,'원',M),
 ('건강·장기요양보험 실제 본인부담액',0,'원',M),
 ('고용보험 실제 본인부담액',0,'원',M),
 ('주택자금 소득공제액 (요건·한도 확인 후)',0,'원',M),
 ('연금저축 공제 대상 납입액',0,'원',18000000),
 ('IRP 공제 대상 납입액',0,'원',18000000),
 ('일반 보장성보험료',0,'원',M),
 ('장애인 전용 보장성보험료',0,'원',M),
 ('일반 의료비 (실손 보전액 등 제외)',0,'원',M),
 ('본인·6세 이하·65세 이상 등 한도 없는 의료비',0,'원',M),
 ('미숙아·선천성이상아 의료비',0,'원',M),
 ('난임시술비',0,'원',M),
 ('교육비 공제 대상액 (개인별 한도 적용 후)',0,'원',M),
 ('당해연도 일반·특례 기부금 공제 대상액 (한도 적용 후)',0,'원',M),
 ('공제 비교 방식',MODES[0],'선택',MODES),
 ('기납부 세액 합계 (국세+지방세, 미확인은 빈칸)','','문자',30),
]}


def wage_deduction(salary):
 salary=num(salary)
 if salary<=5000000:return salary*D('.7')
 if salary<=15000000:return D(3500000)+(salary-5000000)*D('.4')
 if salary<=45000000:return D(7500000)+(salary-15000000)*D('.15')
 if salary<=100000000:return D(12000000)+(salary-45000000)*D('.05')
 return min(D(20000000),D(14750000)+(salary-100000000)*D('.02'))


def wage_credit(salary,tax):
 salary=num(salary);tax=num(tax)
 raw=tax*D('.55') if tax<=1300000 else D(715000)+(tax-1300000)*D('.3')
 if salary<=33000000:cap=D(740000)
 elif salary<=70000000:cap=max(D(660000),D(740000)-(salary-33000000)*D('.008'))
 elif salary<=120000000:cap=max(D(500000),D(660000)-(salary-70000000)*D('.5'))
 else:cap=max(D(200000),D(500000)-(salary-120000000)*D('.5'))
 return min(raw,cap)


def medical_credit(salary,general,unlimited,premature,infertility):
 threshold=num(salary)*D('.03');total=D(0)
 for amount,limit,rate in ((general,7000000,'.15'),(unlimited,M,'.15'),(premature,M,'.2'),(infertility,M,'.3')):
  amount=num(amount);eligible=max(D(0),amount-threshold)
  threshold=max(D(0),threshold-amount)
  total+=min(eligible,D(limit))*D(rate)
 return total


def earned(salary=60000000,people=1,children=0,nps=0,health=0,employment=0,
           housing=0,pension=0,irp=0,insurance=0,disabled_insurance=0,
           medical=0,medical_unlimited=0,medical_premature=0,medical_infertility=0,
           education=0,donation=0,mode=MODES[0],prepaid=''):
 salary,nps,health,employment,housing,pension,irp,insurance,disabled_insurance,medical,medical_unlimited,medical_premature,medical_infertility,education,donation=map(num,(salary,nps,health,employment,housing,pension,irp,insurance,disabled_insurance,medical,medical_unlimited,medical_premature,medical_infertility,education,donation))
 people=period(people,100);children=period(children,99,True)
 if children>=people:raise ValueError('자녀세액공제 인원은 본인을 제외한 기본공제 인원 이하여야 합니다.')
 if mode not in MODES:raise ValueError('공제 비교 방식을 확인해 주세요.')
 if pension+irp>18000000:raise ValueError('일반 연금계좌 납입액 합계는 연 1800만원 이하여야 합니다.')
 deduction=wage_deduction(salary);income=salary-deduction
 child=D(0) if not children else D(250000) if children==1 else D(550000)+(children-2)*400000
 p,i,rate=credit(salary,pension,irp);pension_credit=(p+i)*rate
 insurance_credit=min(insurance,D(1000000))*D('.12')+min(disabled_insurance,D(1000000))*D('.15')
 med_credit=medical_credit(salary,medical,medical_unlimited,medical_premature,medical_infertility)
 education_credit=education*D('.15')
 donation_credit=min(donation,D(10000000))*D('.15')+max(D(0),donation-10000000)*D('.3')
 base_deduction=D(people)*1500000+nps
 alternatives=[]
 for kind in ('특별공제 적용','표준세액공제 적용'):
  itemized=kind=='특별공제 적용'
  deductions=base_deduction+(health+employment+housing if itemized else 0)
  base=max(D(0),income-deductions);gross=progressive_tax(base);wc=wage_credit(salary,gross)
  special=insurance_credit+med_credit+education_credit+donation_credit if itemized else D(130000)
  total_credit=wc+child+pension_credit+special;net=max(D(0),gross-total_credit)
  alternatives.append({'방식':kind,'소득공제':deductions,'과세표준':base,'산출국세':gross,'근로소득세액공제':wc,'자녀세액공제':child,'연금계좌공제':pension_credit,'특별 또는 표준공제':special,'결정국세':net,'지방세 추정':net*D('.1'),'총 세금':net*D('1.1')})
 result=min(alternatives,key=lambda r:r['총 세금']) if mode==MODES[0] else next(r for r in alternatives if r['방식']==mode)
 total=result['총 세금']
 paid=None if prepaid is None or str(prepaid).strip()=='' else num(str(prepaid).replace(',','').strip())
 metrics={'예상 결정세액 (국세+지방세)':total,'선택된 공제 방식':result['방식'],'근로소득공제':deduction,
          '과세표준':result['과세표준'],'환급 예상액':max(D(0),paid-total) if paid is not None else '기납부 세액 미입력',
          '추가 납부 예상액':max(D(0),total-paid) if paid is not None else '기납부 세액 미입력'}
 return FinanceResult(metrics,
  '총급여−구간별 근로소득공제−인적·공적연금 소득공제−선택한 특별소득공제=과세표준. '
  '기본세율 산출세액에서 근로·자녀·연금계좌 및 특별/표준 세액공제를 차감합니다. '
  '표준130,000원과 특별공제는 두 시나리오로 비교하며 중복하지 않습니다.',
  [f'법령 대조 기준일 {AS_OF} · 2026년 귀속 · 소득세법 제47조·제59조~제59조의4. 자녀공제는 법률 제21548호 부칙 경과규정 적용.',
   '국민연금·건강·고용보험은 실제 본인 납부액만 입력합니다. 미입력 0원은 추정 보험료로 대체하지 않습니다.',
   '자녀는 기본공제 요건을 충족한 2026년 9세 이상(2017년생 제외) 인원입니다. 기본공제 대상은 소득·나이 요건과 다른 가족의 중복 공제 여부를 확인한 인원만 입력합니다.',
   '의료비는 보전받은 금액과 비공제 비용을 제외한 적격 비용입니다. 일반→한도 없는 비용→미숙아→난임 순서로 급여3% 문턱을 차감하며 일반 항목만 700만원 한도를 적용합니다.',
   '교육비·기부금·주택자금은 자격·개인별 한도 등을 적용한 공제 대상액입니다. 기부금 종류별 한도·이월금, 정치자금·고향사랑, 월세, 신용카드, 출산입양 공제, 추가 인적공제, 세액감면은 아직 미반영합니다.',
   '근로소득만 있는 일반 거주자 시나리오입니다. 지방세는 결정국세의 10% 추정이며 신고서 단수처리를 적용한 확정 신고세액은 아닙니다. 기납부액은 반드시 국세와 지방세를 합해 입력합니다.'],alternatives)


def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return earned(*values)
