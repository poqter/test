import csv,io,unittest
from modules import unlisted_valuation,salary_dividend,corporate_funding,stock_option,overseas_accounts,policy_fund
from modules.calculator_exports import build_exports
class LastEightExports(unittest.TestCase):
 def test_confirmed_snapshots_have_identical_values(self):
  for mod in (unlisted_valuation,salary_dividend,corporate_funding,stock_option,overseas_accounts,policy_fund):
   for name,fields in mod.FIELDS.items():
    values=[f[1] for f in fields]
    if mod==unlisted_valuation:values[23]='확인'
    elif mod==salary_dividend:values[14]='확인'
    elif mod==stock_option:values[-1]='확인'
    elif mod==overseas_accounts:values[-1]='확인';values[4]=overseas_accounts.ELIGIBILITY[0]
    with self.subTest(name=name):
     r=mod.calculate(name,values)
     text,data=build_exports(name,fields,values,r,'2026-09-27')
     rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
     for key,value in r.display().items():
      self.assertIn(key+': '+value,text);self.assertIn([key,value],rows)
     self.assertIn(['산식',r.formula],rows)
