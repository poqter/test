"""2026 full-year domestic corporate ordinary-income estimate."""
from .finance_models import D,num,FinanceResult
from .personal_tax_models import AS_OF
NAME='법인세계산기';M=10**12
KINDS=('중소기업 7%','중소기업 졸업 후 첫3년 8%','졸업 후 다음2년 9%','일반법인 누진 최저한세')
YESNO=('아니요','예')
FIELDS={NAME:[('세무상 소득 계산 전 이익 (법인세비용 차감 전)',500000000,'원',M),
 ('소득 가산 세무조정',0,'원',M),('소득 차감 세무조정·당기 손실',0,'원',M),
 ('적격 이월결손금 (발생연도·신고·사용액 확인)',0,'원',M),('결손금100% 한도 자격 확인','예','선택',YESNO),
 ('최저한세 구분',KINDS[0],'선택',KINDS),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YESNO),
 ('최저한세 대상 공제·감면 신청액',0,'원',M),('최저한세 제외 공제·감면 확인액',0,'원',M),
 ('국세 기납부세액',0,'원',M),('별도 법인지방소득세 공제·감면 확인액',0,'원',M),('지방세 기납부세액',0,'원',M),
 ('별도 확인된 농어촌특별세 납부세액',0,'원',M)]}

def bracket(base,small=False):
 base=num(base,0,3*M)
 if small:
  if base<=20000000000:return base*D('.2')
  if base<=300000000000:return D(4000000000)+(base-20000000000)*D('.22')
  return D(65600000000)+(base-300000000000)*D('.25')
 if base<=200000000:return base*D('.1')
 if base<=20000000000:return D(20000000)+(base-200000000)*D('.2')
 if base<=300000000000:return D(3980000000)+(base-20000000000)*D('.22')
 return D(65580000000)+(base-300000000000)*D('.25')

def minimum(base,kind):
 if kind not in KINDS:raise ValueError('최저한세 구분을 확인해 주세요.')
 if kind!=KINDS[3]:return base*D(('.07','.08','.09')[KINDS.index(kind)])
 return min(base,D(10000000000))*D('.1')+min(max(D(0),base-10000000000),D(90000000000))*D('.12')+max(D(0),base-100000000000)*D('.17')

def corporate(profit=500000000,add=0,subtract=0,loss=0,full_loss='예',kind=KINDS[0],small='아니요',subject=0,exempt=0,prepaid=0,local_credit=0,local_prepaid=0,agri_due=0):
 vals=[num(v) for v in (profit,add,subtract,loss,subject,exempt,prepaid,local_credit,local_prepaid,agri_due)]
 profit,add,subtract,loss,subject,exempt,prepaid,local_credit,local_prepaid,agri_due=vals
 if full_loss not in YESNO or small not in YESNO or kind not in KINDS:raise ValueError('법인 분류를 확인해 주세요.')
 if kind==KINDS[0] and full_loss!='예':raise ValueError('확인된 중소기업이면 이월결손금 공제100% 한도입니다.')
 income=profit+add-subtract;allowed=min(loss,max(D(0),income)*(D(1) if full_loss=='예' else D('.8')))
 base=max(D(0),income-allowed)
 raw=bracket(base,small=='예');amt=minimum(base,kind)
 applied=min(subject,max(D(0),raw-amt));after=raw-applied
 exempt_used=min(exempt,after);national=after-exempt_used
 local_raw=bracket(base,small=='예')/10;local=max(D(0),local_raw-local_credit)
 national_balance=national-prepaid;local_balance=local-local_prepaid
 return FinanceResult({'국세 납부·환급 추정':national_balance,'지방세 납부·환급 추정':local_balance,
 '세목별 차감액 단순 합계':national_balance+local_balance+agri_due,'과세표준':base,'산출 법인세':raw,
 '최저한세 기준액':amt,'적용된 최저한세 대상 공제':applied,'최저한세로 제한된 신청액':subject-applied,
 '최저한세 제외 적용액':exempt_used,'결정 법인세':national,'법인지방소득세 산출액':local_raw,'공제한 이월결손금':allowed},
 '소득=세전이익+가산−차감. 결손금은 소득80% 또는 적격100% 한도. 과표에2026누진세율 적용. 최저한세 대상 공제는 산출세액−최저한세 이내, 제외 공제는 그 후 적용. 지방세는 별도 과표·세율로 산출.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법13·55조, 조세특례제한법132조, 지방세법103조의20.',
 '2026년1월1일~12월31일 사업연도의 국내 영리법인 일반소득만 지원합니다. 단기사업연도·연결납세·조합·토지등양도 추가법인세·비과세소득/소득공제 및 최저한세 과표 가산조정은 미지원입니다.',
 '법인세비용을 뺀 당기순이익을 그대로 넣지 않습니다. 손실은 차감 칸에 입력합니다. 이월결손금은 기한과 과거 사용액을 검토한 금액이며 원장 자동심사는 하지 않습니다.',
 '중소기업·졸업유예·소규모법인 자격은 별도 확인합니다. 최저한세 대상과 제외 공제는 분리 입력하며 항목별 자격·적용 순서·이월가능 여부는 자동 판정하지 않습니다.',
 '국세 공제감면액을 지방세에 자동 적용하지 않습니다. 지방세는 표준세율 기준이며 조례·사업장 안분·외국납부 조정은 미지원입니다. 농특세는 과세·비과세 구분 후 확인된 세액을 별도 입력합니다.',
 '음수는 해당 세목의 예상 환급입니다. 세목별 납부·환급은 별도 처리되므로 단순합계를 실제 일괄납부액으로 보지 않습니다. 가산세·신고 단수처리 미반영.'],
 [{'항목':k,'금액':v} for k,v in [('세무상 소득',income),('공제 결손금',allowed),('과세표준',base),('산출 국세',raw),('최저한세',amt),('적용 대상공제',applied),('제외 공제',exempt_used),('결정 국세',national),('산출 지방세',local_raw),('결정 지방세',local),('농특세 확인액',agri_due)]])

def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return corporate(*values)
