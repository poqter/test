"""Shared resident shareholder distribution model, with explicit gross-up scope."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.personal_tax_models import financial, AS_OF
M=10**12
MODES=('배당가산 여부 미확인','배당가산 비대상 확인','확인된 추가 결정세액 입력','배당가산 대상 확인')
TAX_FIELDS=[('다른 일반 금융소득 (배당가산 비대상)',0,'원',M),('기타 종합소득금액',0,'원',M),('적용 가능한 소득공제 합계',1500000,'원',M),('종합과세 계산 방식',MODES[0],'선택',MODES),('이 거래로 증가하는 국세·지방세 결정세액 (확인 모드만)',0,'원',M)]
def distribution(received,basis,other_financial=0,other=0,deductions=1500000,mode=MODES[0],confirmed_tax=0):
 received,basis,other_financial,other,deductions,confirmed_tax=map(num,(received,basis,other_financial,other,deductions,confirmed_tax))
 if mode not in MODES:raise ValueError('종합과세 계산 방식을 확인하세요.')
 if received+other_financial>M:raise ValueError('수령액과 다른 금융소득의 합계는 1조원 이하여야 합니다.')
 dividend=max(D(0),received-basis)
 if mode!=MODES[2] and confirmed_tax:raise ValueError('확인된 세액을 사용하려면 확인 입력 모드를 선택하세요.')
 if not dividend:
  if confirmed_tax:raise ValueError('의제배당이 없으면 추가 배당세액은 0원이어야 합니다.')
  tax=D(0);status='의제배당 없음'
 elif mode==MODES[2]:tax=confirmed_tax;status='외부 확인된 결정세액 증가분'
 elif dividend+other_financial<=20000000:tax=dividend*D('.154');status='일반 국내 금융소득 합계 2천만원 이하'
 elif mode==MODES[3]:
  from modules.calculators.tax.dividend_grossup import finance_tax
  before=finance_tax(other_financial,0,other,deductions)["배당공제 후 국세"]
  after=finance_tax(other_financial,dividend,other,deductions)["배당공제 후 국세"]
  tax=(after-before)*D("1.1");status="적격 배당가산·배당세액공제 적용, 기타 공제 전"
 elif mode==MODES[1]:
  before=financial(interest=other_financial,dividends=0,other=other,deductions=deductions).metrics['국세·지방세 합계 (공제 전 추정)']
  after=financial(interest=other_financial,dividends=dividend,other=other,deductions=deductions).metrics['국세·지방세 합계 (공제 전 추정)']
  tax=after-before;status='배당가산 비대상 비교과세·기타 세액공제 전'
 else:tax='배당가산·배당세액공제 검토 필요';status=tax
 if not isinstance(tax,str) and tax>received:raise ValueError('추가 결정세액은 수령액 이하여야 합니다.')
 return {'주주 수령액 (개인세 전)':received,'주식 취득가액':basis,'의제배당액':dividend,'일반 원천징수 추정':dividend*D('.154'),
 '개인세 증가 추정':tax,'주주 세후 수령 추정':received-tax if not isinstance(tax,str) else tax,'과세 검토 상태':status}
NOTES=[f'법령 대조 기준일 {AS_OF} · 소득세법17조2항1·3호, 17조3·4항, 62조. 국내 거주 개인 주주의 일반 국내 의제배당만 지원합니다.',
 '취득가액은 해당 소각·분배 대상 주식의 세무상 취득금액입니다. 회사 납입자본금과 다를 수 있습니다. 취득가액 불분명·증여주식·무상주식의 세무상 금액은 별도 확인하세요.',
 '배당가산 대상 확인 모드는 10% 가산과 비교세액 한도를 적용합니다. 다른 금융소득은 배당가산 비대상으로 가정합니다. 해당 여부 미확인 시 2천만원 초과 최종세액을 표시하지 않습니다. 비대상 확인 모드는 다른 금융소득도 배당가산 비대상인 경우만 사용합니다.',
 '확인 세액은 거래 전후 국세·지방세 결정세액 차이입니다. 원천징수 후 추가 납부액이 아니며 원천징수액을 다시 더하지 않습니다. 원천징수 추정은 최종세액과 별도입니다.',
 '비거주자·법인주주·해외배당·분리과세 특례·부당행위계산·증여·양도소득세·증권거래세·건강보험료 및 신고 단수처리는 미지원입니다. 법률상 소각 여부·거래 시가·재원은 별도 검토합니다.']
