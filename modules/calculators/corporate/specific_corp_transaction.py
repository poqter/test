"""Article 45-5: one confirmed transaction and one shareholder, no prior gifts."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.gift_tax import ordinary_tax
KINDS=('재산 무상 제공·채무 면제','저가로 제공받음','고가로 제공함','확인된 자본거래 이익')
FIELDS=[('45조의5 거래 종류',KINDS[0],'선택',KINDS),
 ('45조의5 시가 또는 확인된 거래 이익',1000000000,'원',10**12),
 ('45조의5 실제 대가',0,'원',10**12),
 ('45조의5 지배주주·친족 합산 보유비율',100,'%',100),
 ('45조의5 계산 대상 주주 보유비율',40,'%',100),
 ('45조의5 거래 포함 법인 사업연도 소득금액',1000000000,'원',10**12),
 ('45조의5 법인 산출세액−공제감면 (토지등 추가세 제외)',180000000,'원',10**12),
 ('45조의5 이번 적용 가능한 증여재산공제 (확인 후)',50000000,'원',600000000),
 ('45조의5 단일거래·과거 합산증여 없음·관계·공제·주주 적격 확인','아니요','선택',('아니요','예'))]

def transaction(kind=KINDS[0],value=1000000000,paid=0,group_share=100,share=40,corporate_income=1000000000,corporate_tax=180000000,deduction=50000000,confirmed='아니요',timely='예'):
 value,paid,corporate_income,corporate_tax,deduction=map(num,(value,paid,corporate_income,corporate_tax,deduction))
 group_share=num(group_share,0,100)/100;share=num(share,0,100)/100
 if kind not in KINDS or confirmed not in ('예','아니요') or timely not in ('예','아니요'):
  raise ValueError('거래 종류와 확인 상태를 선택하세요.')
 if share>group_share:raise ValueError('대상 주주 보유비율은 지배주주·친족 합계를 넘을 수 없습니다.')
 if deduction>600000000:raise ValueError('증여공제액의 관계별 한도를 확인하세요.')
 if kind in (KINDS[0],KINDS[3]) and paid:raise ValueError('무상·채무면제 또는 확인된 자본거래 이익은 대가를0으로 입력하세요.')
 if corporate_income==0 and corporate_tax:raise ValueError('사업연도 소득금액0원에 법인 산출세액이 있으면 세무조정을 확인하세요.')
 notes=['법령 대조일2026-09-27 · 상증세법45조의5·47·53·55·69, 시행령34조의5(2026-09-18 시행). 원본의 일감몰아주기 계산과 구별한 특정법인 거래 계산입니다.',
 '단일 거래·단일 수증 주주·과거 합산 증여 없음·국내 거주자·세대생략 없음 조건입니다. 법정 관계와 직접·간접 보유비율, 자본거래 평가액, 공제 자격은 확인된 값을 입력합니다. 서로 다른 거래 유형을 임의 합산하지 않습니다.',
 '지배주주·친족 보유 합계30% 이상인 법인을 대상으로 합니다. 저가·고가 거래는 차액이 시가30% 이상 또는3억원 이상인 경우입니다. 금전대여·용역 무상사용·반복거래·해산 특례는 별도 계산 대상입니다.',
 '법인세 상당액은 입력한 산출세액−공제감면에 거래이익/사업연도소득 비율(최대1)을 곱합니다. 지방세 및 토지등 양도 추가세액은 넣지 않습니다. 주주 증여의제이익1억원 이상에서만 과세합니다.',
 '법인세 차감 전 주주 이익을 직접 증여받은 것으로 계산한 증여세에서 주주 몫 법인세 상당액을 뺀 금액으로 세액을 제한합니다. 증여공제는 관계별 남은 적격액을 입력하며 이 계산이 자격을 승인하지 않습니다.',
 '기한 내 신고공제3%를 한도 적용 후 반영합니다. 세대생략·과거증여·외국납부·감정수수료·가산세·신고 단수처리는 포함하지 않습니다.']
 formula='증여의제이익=(거래이익−배분 법인세)×주주비율. 증여세는 직접증여세−주주 몫 법인세 한도 적용 후 신고공제.'
 if confirmed!='예':return FinanceResult({'특정법인 거래 증여세 추정':'거래·관계·공제·합산 내역 확인 필요'},formula,notes)
 if kind==KINDS[1]:
  gain=max(D(0),value-paid)
 elif kind==KINDS[2]:gain=max(D(0),paid-value)
 else:gain=value
 price_qualified=kind not in (KINDS[1],KINDS[2]) or (gain>0 and (gain>=value*D('.3') or gain>=300000000))
 allocated=min(gain,corporate_tax*min(D(1),gain/corporate_income)) if corporate_income else D(0)
 benefit=max(D(0),gain-allocated)*share
 triggered=group_share>=D('.3') and price_qualified and benefit>=100000000
 base=max(D(0),benefit-deduction) if triggered else D(0)
 raw=ordinary_tax(base) if base>=500000 else D(0)
 direct_base=max(D(0),gain*share-deduction)
 direct_tax=ordinary_tax(direct_base) if direct_base>=500000 else D(0)
 cap=max(D(0),direct_tax-allocated*share)
 capped=min(raw,cap);filing=capped*D('.03') if timely=='예' else D(0)
 metrics={'특정법인 거래 증여세 추정':capped-filing,'거래 이익':gain,'배분 법인세 상당액':allocated,
 '주주 증여의제이익':benefit,'과세 진입기준':'충족' if triggered else '미충족','증여세 과세표준':base,
 '한도 적용 전 증여세':raw,'직접증여 가정 증여세':direct_tax,'주주 몫 법인세':allocated*share,
 '증여세 한도':cap,'신고세액공제':filing}
 return FinanceResult(metrics,formula,notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
