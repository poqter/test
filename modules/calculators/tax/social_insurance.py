"""2026 ordinary employee insurance; confirmed bases, month-specific NPS caps."""
from decimal import ROUND_DOWN
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import AS_OF

NAME='4대보험계산기'
SIZES=('150인 미만','150인 이상 우선지원 대상','150~999인 우선지원 비대상','1000인 이상·국가·지자체')
YESNO=('예','아니요')
M=10**12
FIELDS={NAME:[
 ('2026년 보험료 산정 월',9,'월',12),
 ('국민연금 신고 소득월액 (비과세 제외)',4000000,'원',M),
 ('건강보험 신고 보수월액',4000000,'원',M),
 ('고용·산재보험 보수월액',4000000,'원',M),
 ('국민연금 부과 대상',YESNO[0],'선택',YESNO),
 ('건강·장기요양보험 부과 대상',YESNO[0],'선택',YESNO),
 ('고용보험 실업급여 부과 대상',YESNO[0],'선택',YESNO),
 ('고용안정·직업능력개발 부과 대상',YESNO[0],'선택',YESNO),
 ('사업장 규모·우선지원 유형',SIZES[0],'선택',SIZES),
 ('사업장 확인 산재 총요율 % (출퇴근재해·개별실적 등 포함, 미확인은 빈칸)','','문자',20),
]}


def floor10(v):
 return (D(v)/10).to_integral_value(rounding=ROUND_DOWN)*10


def insurance(month=9,nps_base=4000000,health_base=4000000,employment_base=4000000,
              nps_on='예',health_on='예',unemployment_on='예',training_on='예',size=SIZES[0],accident_rate=''):
 month=period(month,12)
 nps_base,health_base,employment_base=map(num,(nps_base,health_base,employment_base))
 if size not in SIZES or any(v not in YESNO for v in (nps_on,health_on,unemployment_on,training_on)):
  raise ValueError('보험 가입 및 사업장 유형을 확인해 주세요.')
 lower,upper=(400000,6370000) if month<=6 else (410000,6590000)
 assessed_nps=min(D(upper),max(D(lower),(nps_base/1000).to_integral_value(rounding=ROUND_DOWN)*1000))
 nps=floor10(assessed_nps*D('.0475')) if nps_on=='예' else D(0)
 health=floor10(min(D(9183480),max(D(20160),health_base*D('.0719')))/2) if health_on=='예' else D(0)
 care=floor10(health*D('.009448')/D('.0719'))
 unemployment=floor10(employment_base*D('.009')) if unemployment_on=='예' else D(0)
 training_rate=(D('.0025'),D('.0045'),D('.0065'),D('.0085'))[SIZES.index(size)]
 training=floor10(employment_base*training_rate) if training_on=='예' else D(0)
 accident=None if accident_rate is None or str(accident_rate).strip()=='' else floor10(employment_base*num(str(accident_rate).strip(),0,100)/100)
 own=nps+health+care+unemployment
 known_company=own+training
 rows=[{'보험':'국민연금','본인 부담':nps,'사업주 부담':nps},
       {'보험':'건강보험','본인 부담':health,'사업주 부담':health},
       {'보험':'장기요양보험','본인 부담':care,'사업주 부담':care},
       {'보험':'고용보험 실업급여','본인 부담':unemployment,'사업주 부담':unemployment},
       {'보험':'고용안정·직업능력개발','본인 부담':D(0),'사업주 부담':training},
       {'보험':'산재보험','본인 부담':D(0),'사업주 부담':accident if accident is not None else '요율 미입력'}]
 return FinanceResult(
  {'본인 부담 월 보험료':own,'사업주 부담 월 보험료':known_company+accident if accident is not None else '산재 총요율 입력 필요',
   '사업주 부담 소계 (산재 제외)':known_company,'본인 부담 월액의 12배 (연간 확정액 아님)':own*12,
   '국민연금 적용 기준소득월액':assessed_nps if nps_on=='예' else D(0)},
  '국민연금: 천원 미만 절사 소득에 해당 월 상·하한 후 노사 각각 4.75%. 건강: 보수×7.19%에 월 보험료 상·하한 후 절반. '
  '장기요양: 건강보험료×0.9448/7.19. 실업급여 노사 각각0.9%. 사업주는 규모별0.25~0.85% 및 확인 산재 총요율 추가. 항목별10원 미만 버림 추정.',
  [f'요율·법령 대조 기준일 {AS_OF} · 2026년 {month}월 일반 사업장 근로자 기준.',
   '국민연금 상·하한은 1~6월 40만~637만원, 7~12월 41만~659만원입니다. 월액의 12배는 동일 조건 가정이며 7월 한도변경·보수변동·정산을 반영한 연간 확정액이 아닙니다.',
   '건강보험 노사 합산 보수월액보험료 하한20,160원·상한9,183,480원. 장기요양은 근사치13.14% 대신 공단 공시 비율0.9448/7.19를 사용합니다.',
   '산재는 사업주 전액 부담입니다. 요율을 모르면 회사 총액을 0원으로 채우지 않고 미확인으로 표시합니다. 고지서의 출퇴근재해·개별실적 등을 포함한 실제 총요율을 입력합니다.',
   '국민연금·건강보험 부과 대상으로 선택하면 신고소득 0원에도 법정 하한을 적용합니다. 납부예외·미가입은 부과 대상 아니요를 선택합니다.',
   '지역가입자, 공무원·사학, 외국인 특례, 두루누리 등 지원·감면, 복수 사업장 안분, 보수 외 소득 보험료 및 연말정산은 현재 미반영합니다. 실제 고지액이 우선하며, 개별 단수처리 최종 검증 전 추정입니다.'],rows)


def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return insurance(*values)
