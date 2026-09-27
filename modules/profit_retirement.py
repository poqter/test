from .shareholder_distribution import *
NAME='이익소각계산기'
FIELDS={NAME:[('소각 대가',500000000,'원',M),('소각 대상 주식 세무상 취득가액',100000000,'원',M),*TAX_FIELDS]}
def retirement(received=500000000,basis=100000000,other_financial=0,other=0,deductions=1500000,mode=MODES[0],confirmed_tax=0):
 metrics=distribution(received,basis,other_financial,other,deductions,mode,confirmed_tax)
 return FinanceResult(metrics,'의제배당=max(0, 소각 대가−대상 주식 취득가액). 일반 금융소득 합계가 2천만원 이하이면 15.4%, 초과하면 확인된 비대상 비교과세 또는 확인된 결정세액 증가분.',NOTES,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return retirement(*values)
