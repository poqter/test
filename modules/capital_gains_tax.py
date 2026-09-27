"""2026 single domestic property sale; explicitly confirmed ordinary scope."""
from datetime import date
from . import housing_surcharge as hs
from .finance_models import D,FinanceResult,num,period
from .personal_tax_models import AS_OF,progressive_tax
NAME='양도소득세계산기'
YESNO=('아니요','예')
ASSETS=('상가·업무용 오피스텔','토지','주택')
SCOPE=('직접 취득한 국내 부동산 단독 소유·단일 양도','상속·증여 취득 또는 이월과세','공동소유·겸용주택·용도변경·복수 양도·기타 특례')
M=10**12
FIELDS={NAME:[
 ('양도일 (2026년)',AS_OF,'날짜',0),('취득일','2016-09-26','날짜',0),
 ('자산 종류',ASSETS[0],'선택',ASSETS),('계산 대상 범위',SCOPE[0],'선택',SCOPE),
 ('양도가액',1000000000,'원',M),('취득가액 (취득 부대비용 포함)',600000000,'원',M),
 ('별도 필요경비 (취득가액과 중복 제외)',10000000,'원',M),
 ('올해 남은 양도소득 기본공제',2500000,'원',2500000),
 ('미등기 중과 대상','아니요','선택',YESNO),
 ('비사업용 토지','아니요','선택',YESNO),
 ('소득세법 제104조 제4항 지정지역 등 추가 중과 대상','아니요','선택',YESNO),
 ('주택·입주권·분양권 수 (세대 기준)',1,'개',100),
 ('양도 주택이 조정대상지역에 소재','아니요','선택',YESNO),
 ('1세대 1주택 비과세 요건 별도 확인 (거주 등 포함)','아니요','선택',YESNO),
 ('주택 실제 거주 만 연수',0,'년',100),
]}

FIELDS[NAME] += hs.FIELDS

def full_years(start,end):
 return end.year-start.year-((end.month,end.day)<(start.month,start.day))

def gains(transfer=AS_OF,acquire='2016-09-26',asset=ASSETS[0],scope=SCOPE[0],sale=1000000000,cost=600000000,
          expenses=10000000,basic=2500000,unregistered='아니요',nonbusiness='아니요',designated='아니요',
          houses=1,regulated='아니요',qualified='아니요',residence=0,
          surcharge_mode=hs.MODES[0],contract='2026-05-09',deposit='아니요',region=hs.REGIONS[0],
          permit='아니요',applied='2026-05-09',approved='아니요',exemption_full_sale=None):
 try:
  transfer=transfer if type(transfer) is date else date.fromisoformat(str(transfer))
  acquire=acquire if type(acquire) is date else date.fromisoformat(str(acquire))
 except (TypeError,ValueError):raise ValueError('취득일과 양도일을 확인해 주세요.') from None
 if transfer.year!=2026 or acquire>transfer:raise ValueError('2026년 양도이며 취득일이 양도일 이전이어야 합니다.')
 if scope!=SCOPE[0]:raise ValueError('상속·증여·공동소유·복수 양도 등은 아직 검증 중입니다. 일반 매매로 대체 계산하지 않습니다.')
 if asset not in ASSETS or any(v not in YESNO for v in (unregistered,nonbusiness,designated,regulated,qualified)):
  raise ValueError('자산 및 과세 조건을 확인해 주세요.')
 if designated=='예' and (asset!='토지' or nonbusiness!='예'):
  raise ValueError('지정지역 추가 중과는 이 화면에서 법104조4항의 적용이 확인된 비사업용 토지만 지원합니다.')
 sale,cost,expenses,basic=[num(v) for v in (sale,cost,expenses,basic)]
 if sale<=0 or basic>2500000:raise ValueError('양도가액은 0 초과, 남은 기본공제는 250만원 이하여야 합니다.')
 houses=period(houses,100); residence=period(residence,100,allow_zero=True)
 years=full_years(acquire,transfer)
 if residence>years:raise ValueError('거주 만 연수는 보유 만 연수를 초과할 수 없습니다.')
 if nonbusiness=='예' and asset!='토지':raise ValueError('비사업용 토지는 자산 종류를 토지로 선택해 주세요.')
 surcharge_rate=D(0);surcharge_reason='다주택 중과 대상 아님'
 if asset=='주택' and houses>1 and regulated=='예':
  surcharge_rate,surcharge_reason=hs.surcharge(transfer,years,houses,surcharge_mode,contract,deposit,region,permit,applied,approved)
 if qualified=='예' and (asset!='주택' or houses!=1 or unregistered=='예' or years<2):
  raise ValueError('이 화면의 비과세 계산은 등기된 일반 1주택을 2년 이상 보유하고 요건을 별도 확인한 경우만 지원합니다.')
 if asset!='주택' and residence:raise ValueError('거주 연수는 주택에만 입력합니다.')
 raw_gain=sale-cost-expenses
 exemption_value=sale if exemption_full_sale is None else num(exemption_full_sale)
 if exemption_value<sale or exemption_value<=0:raise ValueError('고가주택 판정 전체가액은 양도로 보는 금액 이상이어야 합니다.')
 taxable_ratio=max(D(0),(exemption_value-D(1200000000))/exemption_value) if qualified=='예' else D(1)
 taxable_gain=max(D(0),raw_gain)*taxable_ratio
 ltd_rate=D(min(years,15))*D('.02') if years>=3 and unregistered!='예' and not surcharge_rate else D(0)
 if qualified=='예' and years>=3 and residence>=2:
  ltd_rate=D(min(years,10)+min(residence,10))*D('.04')
 ltd=taxable_gain*ltd_rate
 basic_applied=min(max(D(0),taxable_gain-ltd),basic) if unregistered!='예' else D(0)
 base=max(D(0),taxable_gain-ltd-basic_applied)
 ordinary=progressive_tax(base)+(base*D('.1') if nonbusiness=='예' else D(0)) + base*surcharge_rate + (base*D('.1') if designated=='예' else D(0))
 short_rate=D('.7' if asset=='주택' else '.5') if years<1 else D('.6' if asset=='주택' else '.4') if years<2 else D(0)
 short=base*short_rate
 unregistered_tax=base*D('.7') if unregistered=='예' else D(0)
 national=max(ordinary,short,unregistered_tax)
 local=national*D('.1')
 return FinanceResult({'양도세 추정 합계 (지방세 포함)':national+local,'소득세':national,'지방소득세 추정':local,
   '양도차익':raw_gain,'과세 대상 양도차익':taxable_gain,'장기보유특별공제':ltd,'과세표준':base,
   '장기보유 공제율':ltd_rate*100,'보유 만 연수':years,'다주택 가산 세율':surcharge_rate*100,'중과 판단':surcharge_reason},
   '양도차익=매도가−취득가−필요경비. 적격 1주택은 차익×max(0,(매도가−12억원)/매도가). '
   '과표=max(0,과세차익−장기보유공제−기본공제). 적용 가능한 누진·단기·미등기 세액 중 큰 금액을 적용.',
   [f'법령 대조 기준일 {AS_OF} · 소득세법 제55·95·103·104조, 시행령 제160조.',
    '직접 매입한 국내 단독 소유 부동산의 단일 매각을 계산합니다. 증여·상속 취득, 공동소유, 겸용주택, 용도변경, 복수 매각 합산, 분양권·입주권, 감면은 미지원입니다.',
    '1주택 비과세 자격은 취득 당시 조정대상지역·거주 요건 등을 별도 확인한 값입니다. 예외적 2년 미만 비과세는 지원하지 않습니다. 주거용 오피스텔은 주택으로 입력합니다.',
    '조정대상지역 다주택은 법정 제외 주택 등을 반영한 주택·권리 수와 중과 판단을 확인합니다. 중과 대상이면2주택20%p/3개 이상30%p를 가산하고 장기보유공제를 배제하며 단기세액과 비교합니다. 2년 이상 보유의2026-05-09 이전 양도 및 계약·허가 경과규정을 구별합니다.',
    '경과규정은 시행령167조의3·167조의10 등(2026-07-01 시행본)을 기준으로 계약·허가·계약금 증빙과4/6개월 기한을 검토합니다. 6개월 지역은 서울의 강남·서초·송파·용산 외21개구와 경기도 수원 장안·팔달·영통, 성남 수정·중원·분당, 안양 동안, 과천, 용인 수지, 광명, 하남, 의왕입니다. 조정대상지역 지정 자체 및 다른 제외 사유는 자동 조회하지 않습니다.',
    '지정지역 비사업용 토지 추가 중과를 선택하면 공고 전 계약 등 제외사유 없이 법104조4항 적용이 확인된 것으로 보고 비사업용10%p에10%p를 더합니다.',
    '미등기는 장기보유 및 기본공제를 배제합니다. 예정신고 세액공제는 없습니다. 양도차손은 표시하지만 다른 양도소득과 통산하지 않습니다.',
    '원 단위 반올림 예상치입니다. 지방세는 국세의 10%로 추산하며 별도 감면·가산세·신고서 단수처리는 미반영입니다.'],
   [{'항목':k,'금액':v} for k,v in [('원래 양도차익',raw_gain),('과세 대상 차익',taxable_gain),('장기보유공제',ltd),('실제 기본공제',basic_applied),('과세표준',base),('누진 세액 (비사업용 가산 포함)',ordinary),('단기 세액 후보',short),('미등기 세액 후보',unregistered_tax),('선택된 국세',national),('지방세',local)]],
   units={'장기보유 공제율':'%','보유 만 연수':'년','다주택 가산 세율':'%'})

def calculate(name,values):
 if name!=NAME or len(values) not in (15,len(FIELDS[NAME])):raise ValueError('계산기 입력 항목을 확인해 주세요.')
 return gains(*values)
