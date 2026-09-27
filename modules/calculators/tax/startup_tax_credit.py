"""2026 ordinary startup relief before minimum-tax and overlap adjustments."""
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import AS_OF

NAME='창업중소기업 세액감면계산기'
REGIONS=('수도권 밖','수도권 인구감소지역 (지정 확인)','수도권 일반지역 (과밀·인구감소 제외)','수도권 과밀억제권역')
QUALIFICATIONS=('미확인 또는 불충족','적격 업종·중소기업·실질 창업·계속사업 요건 확인')
KINDS=('일반 창업','청년 창업 요건 확인 (병역·대표자·최대주주 등 포함)')
FIRST=('최초 소득 발생연도 확인','현재까지 소득 미발생 확인','최초 소득 발생연도 미확인')
M=10**12
FIELDS={NAME:[
 ('감면 대상 사업소득에 대응하는 산출국세',12000000,'원',M),
 ('창업 연도 (2020~2026년)',2024,'년',2026),
 ('최초 소득 발생 상태',FIRST[2],'선택',FIRST),
 ('최초 소득 발생연도 (확인 상태일 때만 입력)',0,'년',2026),
 ('창업 지역 (법정 권역 확인)',REGIONS[0],'선택',REGIONS),
 ('창업 유형',KINDS[0],'선택',KINDS),
 ('감면 기본 요건',QUALIFICATIONS[0],'선택',QUALIFICATIONS),
 ('2026년 연 환산 수입금액 (미확인은 빈칸)','','문자',30),
 ('2024년 이전 창업 신성장서비스업 특례 요건 확인','아니요','선택',('아니요','예')),
]}


def startup(tax=12000000,start_year=2024,first_state=FIRST[2],first_year=0,
            region=REGIONS[0],kind=KINDS[0],qualification=QUALIFICATIONS[0],revenue='',new_service='아니요'):
 tax=num(tax);start_year=period(start_year,2026);first_year=period(first_year,2026,True)
 if start_year<2020:raise ValueError('현재 자동 계산은 2020~2026년 창업분입니다. 이전 창업은 경과규정 검증 대상입니다.')
 if first_state not in FIRST or region not in REGIONS or kind not in KINDS or qualification not in QUALIFICATIONS or new_service not in ('아니요','예'):
  raise ValueError('감면 요건 선택을 확인해 주세요.')
 revenue=None if revenue is None or str(revenue).strip()=='' else num(str(revenue).replace(',','').strip())
 if first_state==FIRST[0]:
  if first_year<start_year:raise ValueError('최초 소득 발생연도는 창업연도 이후여야 합니다.')
  begin=min(first_year,start_year+5)
 else:
  if first_year:raise ValueError('최초 소득 발생연도는 확인 상태에서만 입력해 주세요.')
  begin=start_year+5 if first_state==FIRST[1] else None
 if first_state==FIRST[1] and tax:
  raise ValueError('현재까지 소득 미발생 상태이면 해당 사업 산출세액은 0원이어야 합니다.')
 youth=kind==KINDS[1]
 small=revenue is not None and revenue<=104000000 and not youth
 crowded=region==REGIONS[3]
 general_capital=region==REGIONS[2]
 if start_year<=2025:
  rate=D(50 if crowded else 100) if youth or small else D(0 if crowded else 50)
 else:
  rate=D(50 if crowded else 75 if general_capital else 100) if youth or small else D(0 if crowded else 25 if general_capital else 50)
 if new_service=='예':
  if start_year>2024 or youth or crowded:
   raise ValueError('이 신성장서비스 특례는 2024년 이전 과밀억제권역 밖 일반 창업에 한해 지원합니다.')
  if begin is not None and begin<=2026<=begin+2:rate=max(rate,D(75))
 cap=D(500000000) if start_year>=2025 else None
 end=begin+4 if begin is not None else None
 active=begin is not None and begin<=2026<=end
 remaining=max(0,end-max(2026,begin)+1) if begin is not None else None
 reasons=[]
 if qualification!=QUALIFICATIONS[1]:reasons.append('기본 감면 요건 미확인')
 if begin is None:reasons.append('최초 소득 발생연도 미확인')
 if not youth and revenue is None:reasons.append('수입금액 미확인: 소규모 창업 우대율 판단 필요')
 if reasons:
  relief=' / '.join(reasons)
 elif not active:
  relief=D(0)
 else:
  relief=tax*rate/100
  if cap is not None:relief=min(relief,cap)
 known=isinstance(relief,D)
 rows=[{'항목':'2026년 산출국세','값':tax},
       {'항목':'일반/청년·소규모/신성장 기본 감면율','값':str(rate)+'%'},
       {'항목':'감면 시작연도','값':str(begin) if begin is not None else '미확인'},
       {'항목':'감면 종료연도','값':str(end) if end is not None else '미확인'},
       {'항목':'2026년 감면기간 해당','값':'예' if active else '아니요' if begin is not None else '미확인'},
       {'항목':'연간 법정 감면 한도','값':cap if cap is not None else '2025년 이전 창업: 5억원 신설 한도 적용 제외'}]
 return FinanceResult(
  {'기본 감면 계산액 (최저한세 등 조정 전)':relief,
   '기본 감면율 (확인된 입력 조건 기준)':rate,
   '감면 시작연도':str(begin) if begin is not None else '최초 소득 발생연도 확인 필요',
   '감면 종료연도':str(end) if end is not None else '미확인',
   '2026년 포함 잔여 감면 연도 수':remaining if remaining is not None else '미확인',
   '기본 감면 차감 후 산출국세 (최종 납부액 아님)':tax-relief if known else '요건 확인 필요'},
  '시작연도=min(최초 소득 발생연도, 창업연도+5); 종료=시작+4. '
  '2026년이 기간 내이면 적격 사업 대응 산출국세×창업시기·지역·청년/소규모 유형별 비율. '
  '2025년 이후 창업에는 연간5억원 감면 한도 적용. 최초 소득연도 미확인을 창업연도로 대체하지 않습니다.',
  [f'법령 대조 기준일 {AS_OF} · 2026년 귀속 · 조세특례제한법 제6조 제1·5·6·13항 및 시행령 제5조.',
   '달력연도 과세기간의 일반 창업·청년·소규모 및 확인된 신성장서비스업을 지원합니다. 법인 결산월이 다르거나 창업벤처·에너지신기술·보육센터 유형은 아직 미지원합니다.',
   '청년은 창업 당시 15~34세(법정 병역기간 최대6년 차감), 법인 대표자 최대주주 등과 공동사업 요건을 확인한 경우만 선택합니다. 현재 나이만으로 판정하지 않습니다.',
   '일반 창업의 연 환산 수입금액 1억400만원 이하는 2026년 소규모 우대율 대상 여부에 반영합니다. 미입력 금액을 0원으로 간주하지 않습니다.',
   '지역은 법정 과밀억제권역·인구감소지역 지정과 소재지 변경 이력을 확인해야 합니다. 법인 전환·사업 승계·동종 재창업 등은 실질 창업에서 제외될 수 있습니다.',
   '표시 감면액은 최저한세·공제감면 중복제한·고용증가 추가감면·지방소득세·기납부액을 조정하기 전입니다. 최종 납부세액이나 확정 절세액이 아닙니다. 향후 수입·세법이 달라질 수 있어 남은 연도 총 감면액은 확정 표시하지 않습니다.'],rows,
   units={'기본 감면율 (확인된 입력 조건 기준)':'%','2026년 포함 잔여 감면 연도 수':'년'})


def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return startup(*values)
