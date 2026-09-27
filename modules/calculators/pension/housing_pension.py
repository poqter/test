"""Official published table and explicitly labelled between-price estimates."""
import json
from pathlib import Path
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
DATA=json.loads(Path(__file__).with_name('housing_pension_rates.json').read_text())
NAME='주택연금계산기'
FIELDS={NAME:[('부부 중 연소자 나이',65,'세',90),('주택 시세',600000000,'원',1200000000)]}
def calculate(name,values):
 if name!=NAME or len(values)!=2:raise ValueError('입력 항목을 확인해 주세요.')
 age=period(values[0],90);price=num(values[1],100000000,1200000000)
 if age<55:raise ValueError('현재 일람표의 나이 범위는 55~90세입니다.')
 row=DATA['monthly'][str(age)];x=price/D(100000000);low=int(x);fraction=x-low
 amount=D(row[low-1]) if not fraction else D(row[low-1])+(D(row[low])-row[low-1])*fraction
 kind='공식 일람표 금액' if not fraction else '공식 일람표 사이 선형 추정액'
 notes=['지급표 적용일 '+DATA['effective_date']+' · 자료 확인일 '+DATA['checked_date'],'일반주택·종신지급 정액형 기준입니다. 우대형·오피스텔·인출금 설정은 반영하지 않습니다. 가입 자격 판정은 포함하지 않습니다.',kind+'입니다. 표는 천원 단위로 공시됩니다. 1억원 사이 가격은 선형 보간하며 실제 약정금액과 다를 수 있습니다.','현재 지원 범위: 연소자 55~90세, 주택가격 1억~12억원. 범위 밖 금액은 임의 외삽하지 않습니다.',DATA['source']]
 return FinanceResult({'예상 월 수령액':amount,'예상 연 수령액':amount*12},'해당 나이의 공식 일람표 조회. 중간 가격은 인접 두 가격 지급액의 선형 보간.',notes,[{'주택가격':(i+1)*100000000,'공시 월 수령액':n} for i,n in enumerate(row)])
def run():
 from modules.calculators.coverage.coverage_calculator_ui import run as render
 render(NAME,FIELDS,calculate,'주택연금 · 한국주택금융공사 공시표 기반 추정')
