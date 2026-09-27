"""Personal business current-year revenue test, including mixed industries."""
from fractions import Fraction
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='성실신고 대상판정계산기';M=10**12
FIELDS={NAME:[('15억원 기준 업종의 해당 연도 수입금액',0,'원',M),('7억5천만원 기준 업종의 해당 연도 수입금액',0,'원',M),
 ('5억원 기준 업종의 해당 연도 수입금액',500000000,'원',M),('성실신고 확인에 직접 사용한 비용',0,'원',M),
 ('확인서 제출 및 비용공제 자격 확인','아니요','선택',('아니요','예'))]}
def sincere(retail=0,manufacturing=0,service=500000000,fee=0,eligible='아니요'):
 values=list(map(num,(retail,manufacturing,service)));fee=num(fee)
 if eligible not in ('아니요','예'):raise ValueError('비용 공제 자격을 확인해 주세요.')
 thresholds=[D(1500000000),D(750000000),D(500000000)]
 # Rational comparison avoids Decimal 1/3 rounding errors at exact mixed boundaries.
 ratio=sum((Fraction(v)/Fraction(t) for v,t in zip(values,thresholds)),Fraction(0))
 target=ratio>=1;idx=max(range(3),key=lambda k:values[k]);main=thresholds[idx]
 converted=D(ratio.numerator)*main/D(ratio.denominator);percent=D(ratio.numerator)*100/D(ratio.denominator)
 credit=min(D(1200000),fee*D('.6')) if target and eligible=='예' else ('자격 확인 필요' if target else D(0))
 return FinanceResult({'수입금액 기준 판정':'대상' if target else '비대상','기준 대비 비율':percent,
 '주업종 기준 환산 수입금액':converted,'주업종 기준금액':main,'주업종 환산 기준까지 부족액':max(D(0),main-converted),
 '확인비용 공제 산식금액 (납부세액 한도 적용 전)':credit},
 '각 업종 수입금액÷각 업종 기준금액의 합계가1 이상이면 대상. 주업종 환산수입=그 합계×주업종 기준. 확인비용은 적격 제출 시60%, 연120만원 한도.',
 [f'법령 대조 기준일 {AS_OF} · 2026년 귀속 개인사업자 · 소득세법 시행령133·208조, 소득세법70조의2, 조세특례제한법126조의6.',
 '직전연도가 아니라 해당 과세기간 수입금액입니다. 순이익이 아니며 사업용 유형자산 양도 수입은 제외합니다. 동일 개인의 단독사업장·겸영업종 수입을 해당 기준군별로 합산합니다.',
 '15억원: 농림어업·광업·도소매(상품중개 제외)·법정 부동산매매 등. 7.5억원: 제조·숙박음식·운수창고·정보통신·금융보험·상품중개·해당 건설 등. 5억원: 임대·전문과학기술·교육·보건·예술·기타 해당 서비스 등.',
 '별표3의3 사업서비스업은5억원 기준군으로 입력합니다. 비주거용 건물 건설업 등 예외가 있으므로 업종명만으로 임의 분류하지 않습니다. 실제 업종분류·주업종이 동일 수입인 경우 및 공동사업장별 판정은 별도 확인 대상입니다.',
 '이 화면은 개인사업자 판정입니다. 법인 성실신고확인 대상은 지분·상시근로자·수입구조·법인전환 등 별도 요건이며 본 수입금액 기준을 적용하지 않습니다.',
 '대상자는 확인서를 제출하는 경우 다음 해6월30일까지 신고·납부하는 일반 규정이 적용됩니다. 기한 연장·공휴일 특례 등은 별도입니다.',
 '비용공제는 직접 사용한 적격 비용과 제출·추징에 따른 제한 여부를 확인합니다. 표시액은 산식상 금액이며 당기 세액한도·이월·추징은 미계산입니다. 미제출 가산세를 수입금액만으로 확정하지 않습니다.'],
 [{'기준군':label,'수입금액':v,'기준금액':t} for label,v,t in zip(('15억원군','7.5억원군','5억원군'),values,thresholds)],{'기준 대비 비율':'%'})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return sincere(*values)
