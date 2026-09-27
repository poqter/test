"""Month-end balance reporting threshold and statutory baseline penalty."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
NAME='해외금융계좌 신고계산기';M=10**12
STATUS=('미신고','기한 내 전액 신고','과소신고')
ELIGIBILITY=('거주자·내국법인, 면제 없음 확인','법정 신고의무 면제 확인','비거주자·외국법인 확인','미확인')
FIELDS={NAME:[('월말 합산 잔액 중 최대액',800000000,'원',M),('해외 금융소득 (참고)',0,'원',M),('신고 상태',STATUS[0],'선택',STATUS),('미신고·과소신고 금액 (과소신고 선택 시)',0,'원',M),('신고의무 자격',ELIGIBILITY[3],'선택',ELIGIBILITY),('과태료 계산 사유','신고기한 경과 위반','선택',('신고기한 경과 위반','신고기한 전 예상')),('원화 환산·월말 모든 계좌 합산액 확인','미확인','선택',('미확인','확인'))]}
def monthly_peak(months):
 if len(months)!=12:raise ValueError('월말 합산 잔액 12개를 입력하세요.')
 return max(num(x) for x in months)
def accounts(peak=800000000,income=0,status=STATUS[0],omitted=0,eligibility=ELIGIBILITY[3],timing='신고기한 경과 위반',confirmed='미확인'):
 peak,income,omitted=map(num,(peak,income,omitted))
 if status not in STATUS or eligibility not in ELIGIBILITY or timing not in ('신고기한 경과 위반','신고기한 전 예상'):raise ValueError('신고 조건을 확인하세요.')
 if confirmed!='확인' or eligibility==ELIGIBILITY[3]:raise ValueError('거주자·면제 자격과 월말 원화 합산 잔액을 확인해 주세요.')
 if omitted>peak:raise ValueError('미신고 금액은 신고 기준 잔액을 초과할 수 없습니다.')
 subject=peak>D(500000000) and eligibility==ELIGIBILITY[0]
 missing=peak if status==STATUS[0] else omitted if status==STATUS[2] else D(0)
 penalty=min(missing*D('.1'),D(1000000000)) if subject else D(0)
 if timing=='신고기한 전 예상':penalty=D(0)
 verdict='신고 대상' if subject else '금액 기준 미달' if peak<=D(500000000) else '입력한 자격상 신고 대상 제외'
 return FinanceResult({'신고 대상 판단':verdict,'판단 잔액':peak,'미신고·과소신고 기본 과태료 추정':penalty,'해외 금융소득 (별도 과세 검토)':income},
 '매월 말일 모든 대상 해외계좌의 원화 환산 잔액을 합산하고 그중 최대액이 5억원 초과인지 비교합니다. 기한 경과 미·과소신고 기본 과태료=min(누락액×10%,10억원).',[
 '법령 대조일 2026-09-27 · 국제조세조정법 제53·54조 및 시행령 제147조. 현행 기본 과태료 기준을 적용한 참고 계산입니다.',
 '일중 최고액이나 개별 계좌별 연중 최고액의 합이 아닙니다. 예금·증권·보험·가상자산 등 대상 계좌를 각 월말 기준으로 평가·환산하고 공동명의·실질소유 규정을 반영합니다. 5억원과 같은 금액은 초과가 아닙니다.',
 '원칙적으로 보유연도 다음 해 6월 1~30일 신고합니다. 신고기한 전 예상 선택 시 현재 과태료는 0원이며, 신고의무 자체가 없어지는 것은 아닙니다.',
 '면제에는 법정 단기 외국인 거주자, 재외국민의 국내 거소일수 요건, 법정 기관, 다른 신고로 확인되는 계좌 등의 요건이 있습니다. 확인된 자격을 입력해야 하며 자동 거주자 판정은 하지 않습니다.',
 '표시액은 가감경 전 기본액입니다. 자진 수정·기한후 신고 감경, 부과기관 재량 가감경, 정당한 사유, 출처 미소명 추가 과태료·형사처벌·명단공개는 포함하지 않습니다. 신고 완료는 기한 내 정확한 전액 신고를 뜻합니다.',
 '해외 금융소득은 신고 잔액·과태료에 더하지 않습니다. 국내 소득세·외국납부세액공제·해외신탁 신고는 별도 의무입니다.'
 ],[{'항목':'금액 기준','값':500000000},{'항목':'누락액','값':missing},{'항목':'기본 과태료율','값':'10%'},{'항목':'기본 한도','값':1000000000}])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return accounts(*values)
