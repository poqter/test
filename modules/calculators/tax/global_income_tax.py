"""Comprehensive income scenario; confirmed credits remain explicit inputs."""
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import progressive_tax, AS_OF
from modules.calculators.pension.retirement_models import credit

NAME='종합소득세계산기';M=10**12
STANDARD=('일반 비근로소득자 7만원','성실사업자 요건 충족 12만원','근로소득자 표준공제 요건 충족 13만원','표준공제 미적용')
BOOK_MODES=('확인된 공제액 사용','요건 확인 후 자동 계산')
BOOK_ELIGIBILITY=('미확인 또는 요건 불충족','간편장부 대상자가 자발적 복식부기로 신고·서류 제출·5년 보관 요건 충족')
FIELDS={NAME:[
 ('사업 수입금액',80000000,'원',M),('사업 필요경비',30000000,'원',M),
 ('근로소득금액 (근로소득공제 차감 후)',0,'원',M),
 ('종합과세 임대소득금액 (필요경비 차감 후)',0,'원',M),
 ('종합과세 연금소득금액 (소득공제 차감 후)',0,'원',M),
 ('종합과세 기타소득금액 (필요경비 차감 후)',0,'원',M),
 ('기본공제 대상 인원 (본인 포함)',1,'명',100),
 ('국민연금 등 실제 공적연금 납부액',0,'원',M),
 ('연금저축 공제 대상 납입액',0,'원',18000000),('IRP 공제 대상 납입액',0,'원',18000000),
 ('표준세액공제 적용 조건',STANDARD[0],'선택',STANDARD),
 ('기장 방식','복식부기','선택',('복식부기','간편장부')),
 ('기장세액공제 (적격 여부·한도 확인액)',0,'원',1000000),
 ('근로소득세액공제 (확인액)',0,'원',740000),
 ('추가 소득공제 (공적연금·본인공제 외 확인액)',0,'원',M),
 ('추가 국세 세액공제 (위 공제 외 확인액)',0,'원',M),
 ('기납부 세액 합계 (국세+지방세, 미확인은 빈칸)','','문자',30),
 ('기장세액공제 계산 방식',BOOK_MODES[0],'선택',BOOK_MODES),
 ('기장세액공제 자격',BOOK_ELIGIBILITY[0],'선택',BOOK_ELIGIBILITY),
 ('공제 대상 장부로 계산한 사업소득금액 (임대 포함)',0,'원',M),
 ('신고해야 할 소득금액의 20% 이상 누락 여부','아니오','선택',('아니오','예')),
]}


def comprehensive(revenue=80000000,expenses=30000000,wage=0,rent=0,pension_income=0,other=0,
                  people=1,nps=0,pension=0,irp=0,standard=STANDARD[0],books='복식부기',
                  bookkeeping_credit=0,earned_credit=0,extra_deductions=0,extra_credits=0,prepaid='',
                  book_mode=BOOK_MODES[0],book_eligibility=BOOK_ELIGIBILITY[0],book_income=0,book_omission='아니오'):
 revenue,expenses,wage,rent,pension_income,other,nps,pension,irp,bookkeeping_credit,earned_credit,extra_deductions,extra_credits=map(num,(revenue,expenses,wage,rent,pension_income,other,nps,pension,irp,bookkeeping_credit,earned_credit,extra_deductions,extra_credits))
 people=period(people,100)
 if expenses>revenue:raise ValueError('사업 결손금 통산 사례는 아직 지원하지 않습니다. 수입과 경비를 확인해 주세요.')
 if standard not in STANDARD or books not in ('복식부기','간편장부'):raise ValueError('공제 조건과 기장 방식을 확인해 주세요.')
 business=revenue-expenses;total=business+wage+rent+pension_income+other
 if wage and not (business+rent+pension_income+other):raise ValueError('근로소득만 있는 경우 근로소득세계산기를 사용해 주세요.')
 if wage and standard in STANDARD[:2]:raise ValueError('근로소득이 있으면 비근로소득자 표준공제를 적용할 수 없습니다.')
 if not wage and standard==STANDARD[2]:raise ValueError('근로소득이 없으면 근로소득자 표준공제를 적용할 수 없습니다.')
 if not wage and earned_credit:raise ValueError('근로소득이 없는 경우 근로소득세액공제는 0원입니다.')
 if earned_credit>740000:raise ValueError('근로소득세액공제 최대 한도를 확인해 주세요.')
 if bookkeeping_credit and (books!='복식부기' or not business+rent):raise ValueError('기장공제는 적격 복식부기 사업소득이 있어야 합니다.')
 if bookkeeping_credit>1000000:raise ValueError('기장세액공제 한도는 100만원입니다.')
 if pension+irp>18000000:raise ValueError('일반 연금계좌 납입액 합계는 연 1800만원 이하여야 합니다.')
 deductions=D(people)*1500000+nps+extra_deductions;base=max(D(0),total-deductions)
 gross=progressive_tax(base);p,i,rate=credit(total,pension,irp,True);pc=(p+i)*rate
 if book_mode not in BOOK_MODES or book_eligibility not in BOOK_ELIGIBILITY or book_omission not in ('아니오','예'):
  raise ValueError('기장공제 계산 방식과 적격 조건을 확인해 주세요.')
 book_income=num(book_income)
 if book_income>business+rent:raise ValueError('기장공제 대상 소득은 합산한 사업·임대소득 이하여야 합니다.')
 if book_mode==BOOK_MODES[1]:
  if bookkeeping_credit:raise ValueError('자동 계산 시 확인된 기장공제액 입력은 0으로 두세요.')
  if books!='복식부기':raise ValueError('기장공제 자동 계산은 복식부기 신고를 선택해야 합니다.')
  bookkeeping_credit=(min(D(1000000),gross*book_income/total*D('.2'))
                       if total and book_eligibility==BOOK_ELIGIBILITY[1] and book_omission=='아니오' else D(0))
 elif bookkeeping_credit and book_omission=='예':
  raise ValueError('20% 이상 소득 누락에 해당하면 기장세액공제를 적용할 수 없습니다.')
 sc=D((70000,120000,130000,0)[STANDARD.index(standard)])
 all_credits=sc+pc+bookkeeping_credit+earned_credit+extra_credits
 national=max(D(0),gross-all_credits);local=national*D('.1');tax=national+local
 paid=None if prepaid is None or str(prepaid).strip()=='' else num(str(prepaid).replace(',','').strip())
 return FinanceResult(
  {'예상 결정세액 (국세+지방세)':tax,'종합소득금액':total,'과세표준':base,
   '연금계좌 세액공제 가능액':pc,'기장세액공제 적용액':bookkeeping_credit,'환급 예상액':max(D(0),paid-tax) if paid is not None else '기납부 세액 미입력',
   '추가 납부 예상액':max(D(0),tax-paid) if paid is not None else '기납부 세액 미입력'},
  '사업수입−필요경비+근로·임대·연금·기타 소득금액−인적·공적연금·확인된 추가 소득공제=과세표준. '
  '기본세율 산출국세−연금계좌공제−적격 표준공제−기장공제−확인된 공제=결정국세(최저0). '
  '적격 기장공제=min(100만원, 산출국세×적격 기장 사업소득/종합소득금액×20%). 지방세는 국세10% 추정.',
  [f'법령 대조 기준일 {AS_OF} · 2026년 귀속 · 소득세법 제55조·제59조의3·제59조의4제9항.',
   '각 소득은 과세대상 소득금액입니다. 분리과세·비과세 금액과 금융소득은 제외합니다. 결손금·이월결손금·소득공제 종합한도는 자동 판정하지 않습니다.',
   '공적연금은 확인된 실제 납부액만 반영합니다. 연금저축600만원·IRP합산900만원 한도, 종합소득4500만원 이하15%/초과12% 국세 공제율을 적용합니다.',
   '성실사업자12만원은 법정 성실사업자 요건과 조세특례제한법 제122조의3 공제 미신청 조건을 확인한 경우입니다. 근로소득자13만원은 특별소득·특별세액·월세공제 미신청 요건을 충족해야 합니다.',
   '기장공제 자동 계산은 소득세법 제56조의2에 따라 간편장부 대상자의 자발적 복식부기·신고서류 제출·5년 보관 요건을 확인한 경우 적용합니다. 20% 이상 소득 누락이면 공제하지 않습니다. 기장의무자 판정과 최저한세·다른 감면과의 조합은 별도 검증 대상입니다.',
   '근로소득세액공제는 아직 확인액 입력입니다. 기장공제 수동 입력과 자동 계산을 중복 적용하지 않습니다.',
   '추가 공제에 이미 입력한 공제를 중복 입력하지 마세요. 표준공제와 양립하지 않는 특별공제가 있으면 표준공제 미적용을 선택해야 합니다. 세액감면·농특세·가산세 및 신고서 단수처리는 미반영합니다.',
   '11월 중간예납은 당해 예상세액의 절반으로 확정하지 않으므로 표시하지 않습니다. 고객 결과는 입력한 확인 공제액을 전제로 한 추정입니다.'],
  [{'항목':k,'금액':v} for k,v in [('사업소득금액',business),('근로소득금액',wage),('임대소득금액',rent),('연금소득금액',pension_income),('기타소득금액',other),('소득공제 합계',deductions),('산출국세',gross),('표준세액공제',sc),('연금계좌 세액공제',pc),('그 밖의 확인 공제',bookkeeping_credit+earned_credit+extra_credits),('결정국세',national),('지방세 추정',local)]])


def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return comprehensive(*values)
