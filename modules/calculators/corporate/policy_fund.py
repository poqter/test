"""Official-rule pre-screening; recommendations do not assert loan approval."""
from datetime import date
from modules.calculators.finance.finance_models import num, period, FinanceResult
NAME='정책자금 자격진단계산기';M=10**12
# 2025-09-01 amended SME Framework Decree Annex 1, effective current 2026.
INDUSTRIES={'제조업 (금속가공)':('C25',1200),'제조업 (식품)':('C10',1200),'제조업 (화학)':('C20',1200),'제조업 (전자·반도체)':('C26',1000),'제조업 (전기장비)':('C28',1800),'제조업 (기계)':('C29',1200),'건설업':('F',1200),'도매업':('G46',1200),'소매업':('G47',1200),'운수·창고업':('H',1000),'숙박업':('I55',400),'음식점업':('I56',400),'출판업':('J58',1000),'정보서비스·소프트웨어':('J58/J62',1000),'정보서비스':('J63',1000),'연구개발업':('M70',600),'전문서비스업':('M71',600),'기타 전문·과학기술':('M73',600),'보건업':('Q86',600),'기타 개인서비스업':('S96',600)}
SMALL_LIMITS={'C25':120,'C10':120,'C20':120,'C26':120,'C28':120,'C29':120,'F':80,'G46':60,'G47':60,'H':100,'J58':50,'J58/J62':50,'J63':50,'M70':30,'M71':30,'M73':30,'Q86':15,'S96':15,'I55':15,'I56':15}
YN=('아니오','예')
FIELDS={NAME:[('주된 업종',next(iter(INDUSTRIES)),'선택',tuple(INDUSTRIES)),('법정 산정 평균매출액등',5000000000,'원',M),('상시근로자 수',20,'명',100000),('사업개시일','2018-01-01','날짜',None),('자산총계',3000000000,'원',M),('대표 만 나이',45,'세',120),('최근 연간 수출액 (USD)',0,'USD',10**10),('수도권 소재 여부',YN[0],'선택',YN),('벤처기업 여부',YN[0],'선택',YN),('독립성·관계기업 매출·유예 적용 검토','미확인','선택',('미확인','일반 중소기업 요건 확인','요건 불충족')),('법정 창업기업 해당',YN[1],'선택',YN),('신산업 창업분야 해당',YN[0],'선택',YN),('공고상 긴급 경영애로·재해 해당',YN[0],'선택',YN),('융자제한·제외 업종·체납·부채·지원이력 검토','미확인','선택',('미확인','제한 없음 확인','제한 있음')),('진단 기준일','2026-09-27','날짜',None)]}
def diagnose(industry=next(iter(INDUSTRIES)),sales=5000000000,workers=20,start='2018-01-01',assets=3000000000,age=45,exports=0,capital=YN[0],venture=YN[0],independence='미확인',startup=YN[1],new_industry=YN[0],distress=YN[0],restrictions='미확인',asof='2026-09-27'):
 if industry not in INDUSTRIES:raise ValueError('주된 업종을 선택하세요.')
 sales,assets,exports=map(num,(sales,assets,exports));workers=period(workers,100000,True);age=period(age,120,True)
 start=date.fromisoformat(str(start));asof=date.fromisoformat(str(asof))
 if asof!=date(2026,9,27):raise ValueError('이 진단의 공고 대조 기준일은 2026-09-27입니다.')
 if start>asof:raise ValueError('사업개시일은 기준일 이후일 수 없습니다.')
 if any(v not in YN for v in (capital,venture,startup,new_industry,distress)):raise ValueError('기업 조건을 확인하세요.')
 years=asof.year-start.year-((asof.month,asof.day)<(start.month,start.day))
 code,limit=INDUSTRIES[industry];size_ok=sales<=limit*100000000 and assets<500000000000
 status='규모 기준 충족' if size_ok else '일반 규모 기준 초과'
 if independence=='요건 불충족':status='독립성 등 요건 불충족'
 elif independence=='미확인':status+=' · 독립성 등 미확인'
 elif independence!='일반 중소기업 요건 확인':raise ValueError('독립성 검토 상태를 확인하세요.')
 if restrictions not in ('미확인','제한 없음 확인','제한 있음'):raise ValueError('융자제한 검토 상태를 확인하세요.')
 candidates=[]
 eligible=size_ok and independence!='요건 불충족' and restrictions!='제한 있음'
 if eligible:
  if startup=='예' and (years<7 or new_industry=='예' and years<10):candidates.append(('혁신창업사업화자금','창업기반지원 업력·창업 요건 검토'))
  if startup=='예' and age<=39 and years<3:candidates.append(('청년전용창업자금','만 39세 이하·업력 3년 미만, 법정 창업 등 세부 심사 필요'))
  if years>=7 or startup=='아니오':candidates.append(('신성장기반자금 — 혁신성장지원','업력 7년 이상 또는 창업자 비해당 기업, 자금 용도 심사 필요'))
  if exports>0:candidates.append(('신시장진출지원자금','수출 초보기업 분류 검토' if exports<100000 else '수출기업 글로벌화 분류 검토'))
  if distress=='예':candidates.append(('긴급경영안정자금','해당 경영애로 사유·피해 규모·공고 우대조건 심사 필요'))
 small='규모 기준 충족' if size_ok and sales<=SMALL_LIMITS[code]*100000000 else '규모 기준 초과'
 if independence!='일반 중소기업 요건 확인':small+=' · 독립성 등 별도 확인'
 review='공고·기업 평가 추가 확인 필요' if eligible else '일반 요건상 추천 보류 · 유예·예외 별도 확인'
 notes=['공고·법령 대조일 2026-09-27. 중소기업기본법 시행령 제3조·제8조·별표1·별표3(2025-09-01 개정), 중진공 세부사업 안내 및 2026년 융자계획 변경공고 기준 사전 진단입니다.',
 '입력 매출은 단순 당년 매출이 아니라 법정 평균매출액등입니다. 자산은 5천억원 미만, 업종별 매출은 기준 이하입니다. 관계기업·독립성·유예 및 세부 업종 코드를 확인해야 최종 중소기업 판정이 가능합니다.',
 '목록은 추가 검토할 사업입니다. 신청 가능·승인·대출 한도를 확정하지 않습니다. 체납·휴폐업·신용·부채비율·지원이력·소상공인 제외와 예외·예산·접수 일정은 공고별 심사가 필요합니다.',
 '업력은 정확한 사업개시일을 기준으로 계산합니다. 법인전환 등은 최초 사업의 개시일을 입력합니다. 청년전용의 3~7년 예외 추천 유형은 별도 검토합니다.',
 '혁신성장·긴급자금을 일괄 추천하지 않습니다. 긴급자금은 경영애로 사유가 확인된 경우만 후보로 표시합니다. 벤처 인증만으로 기술보증 승인이나 정책대출 자격을 단정하지 않습니다.',
 f'입력 상시근로자 {workers}명, 수도권 {capital}, 벤처 {venture}. 이 정보는 사업별 우대·제외 확인에 사용되며 중소기업 매출 규모 판정 자체를 바꾸지 않습니다. 신용·기술보증부 대출은 각각 보증기관의 별도 심사 대상입니다.',
 '공식 안내: https://www.kosmes.or.kr/nsh/SH/SBI/SHSBI004M0.do · https://www.kosmes.or.kr/nsh/SH/SBI/SHSBI007M0.do · https://www.kosmes.or.kr/nsh/SH/SBI/SHSBI006M0.do']
 return FinanceResult({'중소기업 사전 판정':status,'추가 검토 사업 수':len(candidates),'만 업력':years,'소기업 사전 판정':small,'판정 상태':review},'업종별 법정 평균매출액 한도와 자산 규모를 비교하고, 정확한 업력·대표 나이·수출·경영애로 조건으로 사업 검토 목록을 구성합니다.',notes,[{'검토 사업':n,'확인할 사항':why} for n,why in candidates],units={'추가 검토 사업 수':'건','만 업력':'년'})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return diagnose(*values)
