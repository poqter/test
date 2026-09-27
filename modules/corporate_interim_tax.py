"""2026 calendar-year national corporate interim payment comparison."""
from .finance_models import D,num,period,FinanceResult
from .corporate_tax import bracket
from .personal_tax_models import AS_OF
NAME='법인세 중간예납계산기';M=10**12
STATUS=('직전 세액 확정·일반 선택 대상','직전 세액 미확정','공시대상기업집단 비중소기업 등 가결산 의무')
YESNO=('아니요','예')
FIELDS={NAME:[('직전 사업연도 산출국세 (가산세 제외)',60000000,'원',M),('직전 가산세',0,'원',M),
 ('직전 공제·감면세액',0,'원',M),('직전 원천징수·수시부과세액',0,'원',M),('직전 사업연도 개월 수',12,'개월',12),
 ('직전 사업연도 중소기업','예','선택',YESNO),('신고 조건',STATUS[0],'선택',STATUS),
 ('2026년1~6월 가결산 과세표준',200000000,'원',M),('상반기 적용 가능한 공제·감면 확인액',0,'원',M),
 ('상반기 원천징수·수시부과세액',0,'원',M),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YESNO),
 ('합병·분할 없는 당해연도 신설법인','아니요','선택',YESNO),('현재 중소기업 (분납기한용)','예','선택',YESNO),
 ('2026 직권2개월 납부기한 연장 대상 확인','아니요','선택',YESNO)]}
def interim(prior=60000000,penalty=0,credit=0,withheld=0,months=12,prior_sme='예',status=STATUS[0],base=200000000,current_credit=0,current_withheld=0,small='아니요',new='아니요',current_sme='예',extension='아니요'):
 prior,penalty,credit,withheld,base,current_credit,current_withheld=map(num,(prior,penalty,credit,withheld,base,current_credit,current_withheld));months=period(months,12)
 if status not in STATUS or any(v not in YESNO for v in (prior_sme,small,new,current_sme,extension)):raise ValueError('법인 구분과 신고 조건을 확인해 주세요.')
 if credit>prior:raise ValueError('직전 공제감면은 가산세를 제외한 산출세액을 넘을 수 없습니다.')
 previous=max(D(0),prior+penalty-credit-withheld)*6/months
 raw=bracket(base*2,small=='예')/2
 if current_credit>raw:raise ValueError('상반기 공제감면 확인액은 산출국세 이하여야 합니다.')
 current=max(D(0),raw-current_credit-current_withheld)
 exempt=new=='예' or (status!=STATUS[1] and prior_sme=='예' and previous<500000)
 forced=status in STATUS[1:] or prior==0
 if exempt:selected=D(0);method='중간예납 의무 없음 (입력 조건 기준)'
 elif forced:selected=current;method='가결산 의무'
 elif current<previous:selected=current;method='가결산 선택'
 else:selected=previous;method='직전연도 선택' if previous<current else '두 방식 동일'
 installment=max(D(0),selected-10000000) if selected<=20000000 else selected/2
 first=selected-installment
 due='2026-11-02' if extension=='예' else '2026-08-31'
 second=('2027-01-04' if current_sme=='예' else '2026-11-30') if extension=='예' else ('2026-11-02' if current_sme=='예' else '2026-09-30')
 return FinanceResult({'중간예납 납부 추정':selected,'적용 방식':method,'직전연도 방식 참고액':previous if status!=STATUS[1] else '직전 세액 미확정',
 '가결산 방식 세액':current,'최대 분납 선택 시1차 납부':first,'최대 분납 가능액':installment,
 '일반 신고기한':'2026-08-31' if not exempt else '입력 조건상 의무 없음',
 '1차 납부기한':due if not exempt else '해당 없음','분납기한':second if installment else '해당 없음'},
 '직전방식=max(0,산출국세+가산세−공제감면−원천징수·수시부과)×6/직전개월. 가결산=2026누진세율(상반기과표×2)/2−확인공제감면−기납부. 의무가결산·면제 여부를 먼저 판정하고 허용된 방법만 비교.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법55·63·63조의2·64조 · 2026년12월 결산 일반 내국법인.',
 '직전 세액에서 토지등양도 추가법인세·투자상생세액은 제외합니다. 직전연도 중간예납세액 자체를 원천징수·수시부과에 넣지 않습니다. 가결산 과표는 결손금·비과세·소득공제 등 검토 후 금액입니다.',
 '직전 중소기업이고 직전방식 계산액50만원 미만이면 면제, 정확히50만원이면 면제가 아닙니다. 직전 세액 미확정 시 금액만으로 면제하지 않습니다.',
 '직전 산출세액0인 일반법인은 가결산이 원칙입니다. 공시대상기업집단 비중소기업 등 의무 대상은 싼 직전방식을 선택하지 않습니다. 유동화전문회사 등 예외·합병/분할·연결납세·학교법인·비영리 특례는 미지원입니다.',
 '휴업 무수입 확인·납부기한 경과 시 강제 직전방식 등은 자동 판정하지 않습니다. 8월31일 기한 내 신고 비교 시나리오이며 기한 후 납부지연가산세는 별도입니다.',
 '공제감면 입력은 중간예납기간 적용요건·최저한세 검토 후 확인된 적용액입니다. 과표 계산·최저한세·공제 이월을 이 화면이 자동 판단하지 않습니다.',
 '2026 직권연장은 대상 확인 시 납부기한만 반영하며 신고기한은8월31일입니다. 개별 신청 연장·다른 결산월은 지원하지 않습니다. 지방소득세를 임의로10% 더하지 않습니다.',
 '중간예납은 연간 확정세액에서 차감하는 선납세금입니다. 더 낮은 선납액은 영구적인 절세액이 아니며 음수 계산분을 중간 환급으로 표시하지 않습니다.'],
 [{'항목':k,'금액':v} for k,v in [('직전 순 기준세액',max(D(0),prior+penalty-credit-withheld)),('직전 방식 참고액',previous),('상반기 연환산 과표',base*2),('가결산 산출국세',raw),('가결산 차감 후',current)]])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return interim(*values)
