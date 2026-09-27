"""2026 calendar-year first component of integrated employment tax credit."""
from .finance_models import D,num,FinanceResult
NAME='고용증대 세액공제계산기';KINDS=('중소기업','중견기업','대기업 등');REGIONS=('수도권 밖','수도권');YN=('아니요','예')
FIELDS={NAME:[('기업 규모',KINDS[0],'선택',KINDS),('동일 사업장 지역',REGIONS[0],'선택',REGIONS),('2025년 상시근로자 수',10.0,'명(연평균)',100000),('2026년 상시근로자 수',13.0,'명(연평균)',100000),('2025년 청년등상시근로자 수',2.0,'명(연평균)',100000),('2026년 청년등상시근로자 수',2.0,'명(연평균)',100000),('업종·규모·근로자 자격·연평균 및 2026 신규공제 요건 확인','아니요','선택',YN)]}
def employment(kind=KINDS[0],region=REGIONS[0],previous=10,current=13,young_previous=2,young_current=2,confirmed='아니요'):
 if kind not in KINDS or region not in REGIONS or confirmed not in YN:raise ValueError('계산 조건을 확인하세요.')
 p,c,yp,yc=[num(v,0,100000) for v in (previous,current,young_previous,young_current)]
 if yp>p or yc>c:raise ValueError('청년등 인원은 해당 연도 전체 상시근로자를 초과할 수 없습니다.')
 notes=['법령 대조일 2026-09-27 · 조세특례제한법29조의8 및 시행령26조의8(2026-09-18). 2025·2026년이 각각1월1일~12월31일인 계속사업자의2026년 신규 기본공제만 계산합니다.',
 '근로자 수는 적격 상시근로자의 법정 연평균 확인값입니다. 임원·최대주주와 친족·근로기간 및 시간 요건 등 제외, 청년·장애·60세이상·경력단절 등의 자격을 확인한 값을 입력합니다. 단순 연말 재직인원이 아닙니다.',
 '2026년 중소기업 단가: 청년등 수도권700만원/밖1000만원, 그 외400만원/밖700만원. 중견 청년500만원·그 외300만원, 대기업 등 청년300만원·그 외0원.',
 '증가 인원은 유형별 증가와 전체 증가 중 작은 수이며 음수는0입니다. 중견은 전체 증가5명 초과, 대기업 등10명 초과일 때만 적용합니다. 최소인원 공제는 일반 증가분부터 배분하고 나머지는 청년 단가로 차감합니다.',
 '2024년1월1일 개시 연도는 현행 비교대상에서 제외되므로 이 범위의2026년 계산은2025년 대비 항목만 적용합니다. 2027·2028년의 유지분 가산, 비달력 사업연도·창업·합병·다지역·기업규모 전환·종전 공제의 경과규정은 미지원입니다.',
 '산출 공제액이며 실제 납부세금 감소나 환급액이 아닙니다. 최저한세·중복공제 배제·이월·농어촌특별세·육아휴직 복귀 등 추가공제는 별도 검증 중입니다. 구제도의 추징 설명을2026년 신규 기본공제에 일괄 적용하지 않습니다.']
 if confirmed!='예':return FinanceResult({'2026년 신규 기본공제 산출액':'적용요건·연평균 확인 필요'},'유형별 증가인원×단가−비중소기업 최소고용증가인원 차감.',notes)
 total=max(D(0),c-p);young=min(total,max(D(0),yc-yp));other=min(total,max(D(0),(c-yc)-(p-yp)))
 if kind==KINDS[0]:yr,ordinary=(10000000,7000000) if region==REGIONS[0] else (7000000,4000000);minimum=D(0)
 elif kind==KINDS[1]:yr,ordinary,minimum=5000000,3000000,D(5)
 else:yr,ordinary,minimum=3000000,0,D(10)
 gross=young*yr+other*ordinary
 reduction=min(other,minimum)*ordinary+max(D(0),minimum-other)*yr if minimum else D(0)
 eligible=total>minimum;credit=max(D(0),gross-reduction) if eligible else D(0)
 metrics={'2026년 신규 기본공제 산출액':credit,'전체 증가 인원':total,'청년등 적용 증가 인원':young,'그 외 적용 증가 인원':other,'최소인원 차감 전 계산액':gross,'최소인원 차감액':min(gross,reduction) if eligible else D(0),'최소 고용증가 기준':'충족' if eligible else '미충족','추가 연도 공제':'2027년 이후 별도 계산'}
 return FinanceResult(metrics,'유형별 증가를 전체 증가 한도로 계산한 후 중견5명·대기업10명 최소인원 차감. 경계와 동일하면 공제하지 않습니다.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()],units={k:'명' for k in ('전체 증가 인원','청년등 적용 증가 인원','그 외 적용 증가 인원')})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return employment(*values)
