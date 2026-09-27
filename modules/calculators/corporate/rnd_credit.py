"""General R&D credit generated before utilization limits, 2026."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
NAME='연구인력개발비 세액공제계산기'; M=10**12
SIZES=('중소기업','중견기업 (법정 요건 확인)','그 밖의 기업')
TRANSITIONS=('해당 없음','최초 중소기업 제외 후 3년 이내','그 이후 2년 이내')
MODES=('유리한 쪽 자동 선택','당기분','증가분'); YN=('아니요','예')
FIELDS={NAME:[('당기 적격 일반 연구·인력개발비',200000000,'원',M),
 ('직전연도 적격 일반 연구·인력개발비',150000000,'원',M),
 ('2년 전 적격 일반 연구·인력개발비',150000000,'원',M),
 ('3년 전 적격 일반 연구·인력개발비',150000000,'원',M),
 ('4년 전 적격 일반 연구·인력개발비',150000000,'원',M),
 ('당기 수입금액 (기업회계 매출액)',10000000000,'원',M),
 ('기업 규모',SIZES[0],'선택',SIZES),('중소기업 졸업 경과 적용 (유예 종료 확인)',TRANSITIONS[0],'선택',TRANSITIONS),
 ('공제 방식',MODES[0],'선택',MODES),
 ('적격 비용·기업 유형·경과 적용·각 연도 12개월·조직재편 없음 확인','아니요','선택',YN)]}
def rnd(current=200000000,prior=150000000,y2=150000000,y3=150000000,y4=150000000,revenue=10000000000,size=SIZES[0],transition=TRANSITIONS[0],mode=MODES[0],confirmed='아니요'):
 current,prior,y2,y3,y4,revenue=map(num,(current,prior,y2,y3,y4,revenue))
 if size not in SIZES or transition not in TRANSITIONS or mode not in MODES or confirmed not in YN:raise ValueError('기업 규모·경과 적용·공제 방식을 확인하세요.')
 if size==SIZES[0] and transition!=TRANSITIONS[0]:raise ValueError('중소기업과 졸업 후 경과 적용은 함께 선택할 수 없습니다.')
 notes=['법령 대조일 2026-09-27 · 2026년 일반 연구·인력개발비 · 조세특례제한법 제10조, 시행령 제9조. 당기 및 과거 입력 연도는 각각 12개월이고 합병·분할·사업양수 등은 없는 조건입니다.',
 '입력 비용은 적격성 확인 및 출연금 등 제외 후 금액입니다. 연구소 인정만으로 모든 지출이 공제되는 것은 아닙니다. 비용별 적격 판정과 증빙 자동검토는 지원하지 않습니다.',
 '과거 4년 평균은 비용 발생 연도 수로 나눕니다. 4년 모두 발생액이 없거나 직전연도 금액이 이 평균보다 작으면 증가분 선택이 불가능합니다. 증가분 기준은 평균이 아닌 직전연도 금액입니다.',
 '중소기업 졸업 경과는 유예기간 종료와 최초 제외 시점을 확인한 경우에만 선택합니다. 중견기업은 이 공제의 법정 요건 충족 기준이며 명칭만으로 판정하지 않습니다.',
 '표시액은 사용 한도 적용 전 발생 공제액입니다. 최저한세·공제 순서·다른 감면·이월공제·당기 납부세액·지방세는 미반영이므로 현금 환급이나 실제 세금 감소액이 아닙니다.',
 '신성장·원천기술 및 국가전략기술 별도 공제, 단기 사업연도와 조직재편 내역, 기업 구분 자동판정은 별도 검증 대상입니다.']
 formula='당기분=적격 당기 비용×공제율. 증가분=max(0,당기−직전연도 비용)×규모별 공제율. 증가분 자격 확인 후 선택합니다.'
 if confirmed!='예':return FinanceResult({'발생 공제액 (사용 한도 적용 전)':'적격 비용·유형·연도 조건 확인 필요'},formula,notes)
 history=[prior,y2,y3,y4];count=sum(v>0 for v in history);avg=sum(history)/count if count else D(0)
 eligible=bool(count) and prior>=avg
 if mode=='증가분' and not eligible:raise ValueError('과거 4년 발생액이 없거나 직전연도 금액이 연평균보다 적어 증가분 방식을 선택할 수 없습니다.')
 if size==SIZES[0]:rate=D('.25')
 elif transition==TRANSITIONS[1]:rate=D('.20')
 elif transition==TRANSITIONS[2]:rate=D('.15')
 elif size==SIZES[1]:rate=D('.08')
 else:
  if revenue==0:raise ValueError('그 밖의 기업은 당기분 공제율 산정을 위해 0원 초과 수입금액이 필요합니다. 무매출 사례는 별도 검증 대상입니다.')
  rate=min(D('.02'),current/revenue/D(2))
 increase_rate={SIZES[0]:D('.50'),SIZES[1]:D('.40'),SIZES[2]:D('.25')}[size]
 flat=current*rate;increment=max(D(0),current-prior)*increase_rate if eligible else None
 better='증가분' if increment is not None and increment>flat else '당기분'
 selected=better if mode==MODES[0] else mode;amount=increment if selected=='증가분' else flat
 metrics={'발생 공제액 (사용 한도 적용 전)':amount,'선택 방식':selected,'발생액이 큰 방식':better,'당기분 공제율':rate*100,'당기분 발생 공제액':flat,'증가분 발생 공제액':increment if eligible else '법정 선택 조건 미충족','직전 4년 비용 발생 연도 평균':avg}
 rows=[{'방식':'당기분','계산 대상':current,'공제율(%)':rate*100,'공제액':flat,'선택 가능':'예'}, {'방식':'증가분','계산 대상':max(D(0),current-prior),'공제율(%)':increase_rate*100,'공제액':increment if eligible else '선택 불가','선택 가능':'예' if eligible else '아니요'}]
 return FinanceResult(metrics,formula,notes,rows,units={'당기분 공제율':'%'})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return rnd(*values)
