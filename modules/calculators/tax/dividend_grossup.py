"""Resident ordinary domestic finance income, 2026 gross-up and comparison tax."""
from modules.calculators.finance.finance_models import D, num
from modules.calculators.tax.personal_tax_models import progressive_tax

def finance_tax(ordinary=0,eligible_dividend=0,other_income=0,deductions=1500000):
 ordinary,eligible_dividend,other_income,deductions=map(num,(ordinary,eligible_dividend,other_income,deductions))
 total=ordinary+eligible_dividend
 excess=max(D(0),total-D(20000000))
 addition=min(eligible_dividend,excess)*D('.10')
 other_base=max(D(0),other_income-deductions)
 comparison=progressive_tax(other_base)+total*D('.14')
 general=progressive_tax(max(D(0),other_income+excess+addition-deductions))+D(2800000) if total>20000000 else comparison
 gross=max(general,comparison)
 dividend_credit=min(addition,max(D(0),gross-comparison))
 return {'국세 산출세액':gross,'배당가산액':addition,'배당세액공제':dividend_credit,'배당공제 후 국세':gross-dividend_credit,'비교산출세액':comparison,'일반산출세액':general}
