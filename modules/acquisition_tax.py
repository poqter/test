"""Corporate acquisition principal tax for confirmed paid acquisition regimes."""
from .finance_models import D,num,FinanceResult
NAME='취득세 중과계산기';M=10**12
KINDS=('상가·업무용','주택','토지 (농지 제외)')
REGIMES=('미확인','비주택 일반 유상취득','대도시 법인 설립·지점 설치·전입 중과','법인 주택 중과')
YN=('아니요','예')
FIELDS={NAME:[('확인된 취득세 과세표준',800000000,'원',M),('부동산 종류',KINDS[0],'선택',KINDS),('확인된 적용 구분',REGIMES[0],'선택',REGIMES),('유상 승계취득·중과 제외·감면·다른 중과 중복 없음 확인','아니요','선택',YN)]}
def acquisition(base=800000000,kind=KINDS[0],regime=REGIMES[0],confirmed='아니요'):
 base=num(base)
 if kind not in KINDS or regime not in REGIMES or confirmed not in YN:raise ValueError('부동산 종류와 적용 구분을 확인하세요.')
 notes=['법령 대조일 2026-09-27 · 지방세법 제11조·제13조제2항·제13조의2. 확인된 법인 유상 승계취득의 취득세 본세 계산입니다.',
 '취득대금만이 아닌 확인된 취득세 과세표준을 입력합니다. 부대비용·부가세 등의 포함 여부를 자동 판정하지 않습니다.',
 '대도시 중과는 주소와 법인 설립 연수만으로 확정하지 않습니다. 지점 설치·전입, 산업단지 제외, 중과 제외 업종, 취득 목적과 시기를 함께 확인해야 합니다.',
 '일반 비주택 4%, 제13조제2항 대도시 중과 8%, 법인 주택 중과 12%의 확인된 세 가지 경우만 계산합니다. 주택 중과 제외·농지·무상취득·원시취득·고급주택 등 다른 중과 및 중복 적용·조례 조정·감면은 별도 검증 대상입니다.',
 '지방교육세·농어촌특별세·신고 단수처리는 포함하지 않습니다. 결과는 취득 관련 총비용이나 최종 신고세액이 아닙니다.',
 '주택 결과의 4% 비교액은 중과 산식의 기준입니다. 중과 제외 주택에 실제 적용할 일반세율로 해석하지 않습니다.']
 formula='일반 비주택: 과세표준×4%. 대도시 중과: 과세표준×(4%×3−2%×2). 법인 주택 중과: 과세표준×(4%+2%×4).'
 if regime==REGIMES[0] or confirmed!='예':return FinanceResult({'취득세 본세':'취득 유형과 중과·제외 요건 확인 필요'},formula,notes)
 if kind=='주택' and regime!=REGIMES[3]:raise ValueError('주택은 법인 주택 중과 요건 확인 시에만 계산합니다. 중과 제외 주택은 별도 검증 대상입니다.')
 if kind!='주택' and regime==REGIMES[3]:raise ValueError('법인 주택 중과는 주택에만 선택하세요.')
 rate={REGIMES[1]:D('.04'),REGIMES[2]:D('.08'),REGIMES[3]:D('.12')}[regime]
 tax=base*rate;reference=base*D('.04')
 metrics={'취득세 본세':tax,'적용 세율':rate*100,'4% 기준 비교액':reference,'4% 기준 대비 추가 본세':tax-reference}
 return FinanceResult(metrics,formula,notes,[{'적용 구분':regime,'과세표준':base,'세율(%)':rate*100,'본세':tax}],units={'적용 세율':'%'})
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return acquisition(*values)
