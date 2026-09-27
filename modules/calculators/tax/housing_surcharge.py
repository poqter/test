"""2026 Article 104(7) rates and confirmed transition documentation."""
from datetime import date
import calendar
from modules.calculators.finance.finance_models import D
MODES=('미확인','중과 제외 사유 없음 확인','기타 법정 중과 제외 요건 확인','2026년 계약·허가 경과규정 검토')
REGIONS=('일반 4개월 지역','시행령 표의 6개월 지역 확인')
FIELDS=[('다주택 중과 적용 판단',MODES[0],'선택',MODES),
 ('경과규정 매매계약일','2026-05-09','날짜',0),
 ('경과규정 계약금 수령 증빙 확인','아니요','선택',('아니요','예')),
 ('경과규정 지역 구분',REGIONS[0],'선택',REGIONS),
 ('토지거래허가 대상','아니요','선택',('아니요','예')),
 ('토지거래허가 신청일','2026-05-09','날짜',0),
 ('해당 신청에 대한 허가 취득 확인','아니요','선택',('아니요','예'))]
def as_date(v):
 try:return v if type(v) is date else date.fromisoformat(str(v))
 except (TypeError,ValueError):raise ValueError('계약일·허가 신청일을 확인하세요.') from None

def add_months(day,months):
 month=day.month-1+months;y=day.year+month//12;m=month%12+1
 return date(y,m,min(day.day,calendar.monthrange(y,m)[1]))

def surcharge(transfer,years,houses,mode=MODES[0],contract='2026-05-09',deposit='아니요',region=REGIONS[0],permit='아니요',applied='2026-05-09',approved='아니요'):
 if mode not in MODES or region not in REGIONS or any(x not in ('예','아니요') for x in (deposit,permit,approved)):
  raise ValueError('중과 판단과 계약·허가 조건을 확인하세요.')
 cutoff=date(2026,5,9)
 if years>=2 and transfer<=cutoff:return D(0),'2년 이상 보유·2026-05-09 이전 양도'
 if mode==MODES[0]:raise ValueError('조정대상지역 다주택의 법정 주택 수와 중과 제외 여부를 확인하세요.')
 if mode==MODES[2]:return D(0),'기타 법정 중과 제외 확인'
 if mode==MODES[3]:
  contract=as_date(contract);applied=as_date(applied)
  if contract>transfer:raise ValueError('매매계약일은 양도일 이후일 수 없습니다.')
  months=6 if region==REGIONS[1] else 4
  deadline=add_months(contract,months)
  eligible=years>=2 and deposit=='예'
  if permit=='예':
   eligible=eligible and applied<=cutoff and applied<=contract and approved=='예'
   if contract>cutoff:deadline=min(deadline,date(2026,11 if months==6 else 9,9))
  else:eligible=eligible and contract<=cutoff
  if eligible and transfer<=deadline:return D(0),f'계약·허가 경과규정 충족, 양도 기한 {deadline}'
  reason=f'경과규정 미충족 (입력 계약 기준 기한 {deadline})'
 else:reason='중과 제외 사유 없음 확인'
 return D('.2') if houses==2 else D('.3'),reason
