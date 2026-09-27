"""JARVIA's family-corp card actually implements Article45-3 work allocation."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.personal_tax_models import AS_OF
from modules.calculators.tax.gift_tax import ordinary_tax
from modules.calculators.corporate import specific_corp_transaction as specific
NAME='특정법인 증여의제계산기';M=10**12;KINDS=('중소기업','중견기업','그 밖의 기업');YN=('아니요','예')
FIELDS={NAME:[('적용 제도','일감몰아주기 (45조의3)','선택',('일감몰아주기 (45조의3)','특정법인 거래 (45조의5)')),
 ('기업 규모',KINDS[0],'선택',KINDS),('조정 후 특수관계법인 거래비율',60,'%',100),('직접 보유 지분율',40,'%',100),
 ('과세제외·세무조정 반영 세후영업이익',500000000,'원',M),('조정 후 특수관계법인 매출액',3000000000,'원',M),
 ('지배주주·친족 및 기업 규모·조정 수치 확인','아니요','선택',YN),('간접 출자관계 있음','아니요','선택',YN),
 ('해당 기간 수혜법인 배당소득',0,'원',M),('사업연도 말 수혜법인 배당가능이익',0,'원',M),('배당 기간·금액 요건 확인','아니요','선택',YN),('기한 내 신고','예','선택',YN)]}
FIELDS[NAME] += specific.FIELDS
def allocation(regime='일감몰아주기 (45조의3)',kind=KINDS[0],trade=60,share=40,profit=500000000,sales=3000000000,confirmed='아니요',indirect='아니요',dividend=0,available=0,div_confirmed='아니요',timely='예', *specific_values):
 if regime=='특정법인 거래 (45조의5)':return specific.transaction(*specific_values,timely=timely)
 if regime!='일감몰아주기 (45조의3)':raise ValueError('적용 제도를 선택하세요.')
 if kind not in KINDS or any(x not in YN for x in (confirmed,indirect,div_confirmed,timely)):raise ValueError('계산 조건을 확인하세요.')
 trade=num(trade,0,100)/100;share=num(share,0,100)/100
 profit,sales,dividend,available=map(num,(profit,sales,dividend,available))
 if trade==0 and sales:raise ValueError('거래비율이0이면 특수관계 매출액도0이어야 합니다.')
 if trade>0 and sales==0:raise ValueError('특수관계 거래비율에 대응하는 매출액을 입력하세요.')
 if indirect=='예':raise ValueError('간접출자는 출자경로별 공제 순서와 과세제외매출 조정이 필요해 아직 지원하지 않습니다.')
 if dividend and (div_confirmed!='예' or available<=0 or share<=0):raise ValueError('배당공제는 적격 기간·배당가능이익·지분을 확인한 뒤 계산합니다.')
 notes=[f'법령 대조 기준일 {AS_OF} · 상증세법45조의3·47·55·56·69, 시행령34조의3. 원본 카드의 실제 기능인 일감몰아주기를 계산합니다. 45조의5 특정법인 무상·저가거래 계산이 아닙니다.',
 '단일 수혜법인·직접출자 주주·전체 사업연도 기준입니다. 지배주주/친족 여부, 규모, 과세제외매출과 세후영업이익을 확인한 수치를 사용합니다. 매출에 임의 이익률을 곱해 영업이익을 추정하지 않습니다.',
 '중소: 거래50%·보유10% 초과. 중견: 거래40%·보유10% 초과. 그 밖: 보유3% 초과이고 거래30% 초과 또는 거래20% 초과·특수관계 매출1천억원 초과.',
 '과세 진입기준과 계산 시 차감 비율은 다릅니다. 중견은 거래20%·보유5%를 차감하고, 그 밖의 기업은 거래5%만 차감합니다.',
 '세후영업이익은 시행령34조의3제12항의 세무조정·법인세 배분·과세매출비율 반영 후 금액입니다. 일반 당기순이익이 아닙니다. 세무조정 자동화·사업부문 구분·간접출자는 미지원입니다.',
 '배당공제=적격 배당소득×직접출자 증여의제이익÷(사업연도 말 배당가능이익×직접지분). 이익 한도이며 적격 신고기간 내 배당만 사용합니다.',
 '일감몰아주기는 합산배제 증여재산입니다. 일반 배우자·자녀 공제나 다른10년 증여를 자동 합산하지 않습니다. 과표50만원 미만 과세최저한과 기한 내 신고공제3% 반영. 외국납부·감정수수료·가산세·신고 단수는 미지원입니다.']
 if confirmed!='예':return FinanceResult({'일감몰아주기 증여세 추정':'기업·주주·조정금액 확인 필요'},'확인된 직접출자 조건으로 기업 규모별 과세 기준과 증여이익을 계산합니다.',notes)
 i=KINDS.index(kind);normal=(D('.5'),D('.4'),D('.3'))[i];limit=D('.1') if i<2 else D('.03')
 triggered=share>limit and (trade>normal or (i==2 and trade>D('.2') and sales>100000000000))
 trade_factor=max(D(0),trade-(D('.5'),D('.2'),D('.05'))[i]);share_factor=max(D(0),share-(D('.1'),D('.05'),D(0))[i])
 benefit=profit*trade_factor*share_factor if triggered else D(0)
 reduction=min(benefit,dividend*benefit/(available*share)) if dividend else D(0)
 base=benefit-reduction;raw=ordinary_tax(base) if base>=500000 else D(0);filing=raw*D('.03') if timely=='예' else D(0)
 metrics={'일감몰아주기 증여세 추정':raw-filing,'배당공제 전 증여의제이익':benefit,'적용 배당소득 공제':reduction,'증여세 과세표준':base,'증여세 산출세액':raw,'신고세액공제':filing,'규모별 과세 진입기준':'충족' if triggered else '미충족'}
 return FinanceResult(metrics,'규모별 진입기준 충족 시 조정 세후영업이익×규모별 거래계수×보유계수−적격 배당공제. 증여세 누진세율 적용 후 신고공제.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values) not in (12,len(FIELDS[NAME])):raise ValueError('입력 항목을 확인하세요.')
 return allocation(*values)
