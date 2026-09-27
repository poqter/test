"""Incremental credit: do not count contributions already using the annual cap."""
from modules.calculators.pension.retirement_models import credit, SOURCES, LEGAL_DATE
from modules.calculators.finance.finance_models import D, num

def incremental_credit(income,existing_pension,existing_irp,extra_monthly,extra_pension_annual):
 income,p,i,extra,allocation=map(num,(income,existing_pension,existing_irp,extra_monthly,extra_pension_annual))
 annual=extra*12
 if allocation>annual:raise ValueError('추가 연금저축 배분액은 추가 월 납입액의 12배 이하여야 합니다.')
 if p+i+annual>18000000:raise ValueError('기존·추가 연금계좌 합산 납입은 연 1800만원 이하여야 합니다.')
 bp,bi,rate=credit(income,p,i);ap,ai,_=credit(income,p+allocation,i+annual-allocation)
 return (ap+ai-bp-bi)*rate*D('1.1')

def attach(result,inputs):
 amount=incremental_credit(**inputs)
 result.metrics['추가 납입 첫해 세액공제 가능액']=amount
 result.assumptions.extend(['세액공제 법령 대조일 '+LEGAL_DATE+' · 소득세법 제59조의3', '근로소득만 있는 경우의 총급여 기준입니다. 기존 공제한도 사용분을 차감한 첫해 추가 공제 가능액이며, 실제 환급액은 결정세액에 따라 달라집니다. 세액공제액은 자산에 재투자하지 않습니다. 전액을 연금계좌에 납입하는 시나리오입니다.',SOURCES['credit']])
 result.formula+='; 추가 공제액=(추가 후 공제대상액−기존 공제대상액)×소득별 공제율×1.1'
 return result
