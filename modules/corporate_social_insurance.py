"""Employer totals, applying existing per-person rates and caps before summing."""
from .finance_models import D,num,period,FinanceResult
from .social_insurance import insurance,SIZES
from .personal_tax_models import AS_OF
NAME='법인 4대보험계산기';M=10**12
MODES=('총급여를 직원 수로 균등 배분한 추정','직원별 월 보수 입력')
FIELDS={NAME:[('2026년 산정 월',9,'월',12),('입력 방식',MODES[0],'선택',MODES),('월 보수 총액 (비과세 제외)',50000000,'원',M),
 ('직원 수',10,'명',1000),('직원별 월 보수 (원, 세미콜론으로 구분)',';'.join(['5000000']*10),'문자',20000),
 ('사업장 규모·우선지원 유형',SIZES[0],'선택',SIZES),('확인된 산재 총요율 % (미확인은 빈칸)','','문자',20)]}
def company_insurance(month=9,mode=MODES[0],total=50000000,count=10,records=';'.join(['5000000']*10),size=SIZES[0],accident_rate=''):
 month=period(month,12);total=num(total);count=period(count,1000)
 if mode not in MODES:raise ValueError('입력 방식을 확인해 주세요.')
 if mode==MODES[0]:bases=[total/count]*count
 else:
  parts=str(records).split(';')
  if len(parts)>1000 or any(not v.strip() for v in parts):raise ValueError('직원별 보수를 빈 항목 없이 세미콜론으로 구분해 주세요.')
  bases=[num(v.strip().replace(',','')) for v in parts]
  if len(bases)!=count or sum(bases)!=total:raise ValueError('직원별 보수의 인원과 합계가 직원 수·월 보수 총액과 일치해야 합니다.')
 missing=accident_rate is None or str(accident_rate).strip()==''
 sums={k:D(0) for k in ('국민연금','건강보험','장기요양보험','고용보험 실업급여','고용안정·직업능력개발','산재보험')};rows=[];own=D(0)
 for j,base in enumerate(bases,1):
  r=insurance(month,base,base,base,size=size,accident_rate=accident_rate);own+=r.metrics['본인 부담 월 보험료']
  for item in r.rows:
   v=item['사업주 부담']
   if not isinstance(v,str):sums[item['보험']]+=v
  rows.append({'직원 번호':j,'월 보수':base,'연금 적용 소득':r.metrics['국민연금 적용 기준소득월액'],'직원 부담':r.metrics['본인 부담 월 보험료'],
   '회사 부담 (산재 제외)':r.metrics['사업주 부담 소계 (산재 제외)'],'회사 부담 합계':r.metrics['사업주 부담 월 보험료']})
 subtotal=sum(v for k,v in sums.items() if k!='산재보험');full='산재 총요율 입력 필요' if missing else subtotal+sums['산재보험']
 return FinanceResult({'회사 부담 월 보험료':full,'회사 부담 소계 (산재 제외)':subtotal,'직원 부담 월 보험료 합계':own,
 '회사 월액의12배 (연간 확정액 아님)':full if missing else full*12,
 **{f'회사 {k}':('산재 총요율 입력 필요' if k=='산재보험' and missing else v) for k,v in sums.items()}},
 '직원별 보수에 각 보험 상·하한과 단수처리를 먼저 적용한 뒤 합산합니다. 회사는 실업급여 외 규모별 고용안정·직업능력개발과 확인된 산재 총요율을 추가 부담합니다.',
 [f'요율·법령 대조 기준일 {AS_OF} · 2026년{month}월 · 기존4대보험계산기의 공통 계산식 사용.',
 '전 직원이 국민연금·건강·장기요양·고용·산재 일반 부과대상이고 각 보험 신고기준 보수가 동일한 경우입니다. 대표자·임원·65세 이후 채용·납부예외·일용직·외국인 등은 개별 가입조건을 별도로 검토해야 합니다.',
 '총급여 방식은 모든 직원에게 같은 보수를 가정합니다. 총급여와 인원만 같아도 실제 급여분포에 따라 상한 적용 결과가 달라지므로 확정 고지액이 아닙니다.',
 '직원별 방식은 입력 인원 및 총액 일치 여부를 검사합니다. 보험별 신고기준 보수가 다른 경우 기존 개인4대보험계산기에서 각각 계산해야 합니다.',
 '사업장 규모 선택은 이 화면의 인원만으로 자동 확정하지 않습니다. 우선지원 여부·기업 단위 상시인원·보험료율 유예를 확인합니다. 요율 유예·두루누리 등 지원은 미반영입니다.',
 '산재율 미입력은 면제가 아닙니다. 회사 총액을 미확인으로 표시하고 산재 제외 소계를 구분합니다. 출퇴근재해·개별실적 등을 포함한 실제 적용 총요율을 입력합니다.',
 '월액의12배는 같은 조건의 비교이며7월 연금한도 변경·보수변동·보험료 정산을 반영한 연간 확정액이 아닙니다. 법인세 절감액은 별도이며 비용 전체를 세금 절감으로 표시하지 않습니다.'],rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
 return company_insurance(*values)
