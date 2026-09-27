import csv,io,unittest
from modules import coverage_models,corporate_funding,retirement_models,retirement_plan,housing_pension,severance
from modules.calculator_exports import build_exports
class PlanningExports(unittest.TestCase):
 def test_customer_and_advisor_share_snapshot(self):
  for mod in (coverage_models,corporate_funding,retirement_models,retirement_plan,housing_pension,severance):
   for name,fields in mod.FIELDS.items():
    with self.subTest(name=name):
     values=[f[1] for f in fields];result=mod.calculate(name,values)
     text,data=build_exports(name,fields,values,result,'2026-09-27 12:00')
     rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
     for key,value in result.display().items():
      self.assertIn(key+': '+value,text)
      self.assertIn([key,value],rows)
     for f,v in zip(fields,values):
      self.assertIn(str(v),text)
     self.assertIn(['산식',result.formula],rows)
     for note in result.assumptions:
      self.assertIn(note,text)
      self.assertIn(['가정',note],rows)

 def test_remaining_retirement_exports(self):
  from modules.retirement_remaining import SAVE,ORDER,FIELDS,saving,withdrawal
  values=[f[1] for f in FIELDS[SAVE]]
  r=saving(SAVE,values)
  text,data=build_exports(SAVE,FIELDS[SAVE],values,r,'2026-09-27')
  for k,v in r.display().items():self.assertIn(k+': '+v,text);self.assertIn(v,data.decode('utf-8-sig'))
  for net in (False,True):
   r=withdrawal(3000000,20,[('연금',100000000,5.5),('투자',100000000,0),('예금',100000000,0)],net)
   text,data=build_exports(ORDER,[],[],r,'2026-09-27')
   rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
   for k,v in r.display().items():self.assertIn(k+': '+v,text);self.assertIn([k,v],rows)

 def test_later_detail_columns_are_not_discarded(self):
  from modules.finance_models import FinanceResult
  r=FinanceResult({'합계':1},'검증',[],[{'항목':'A','금액':1},{'항목':'B','세율':15,'차감액':2}])
  _,data=build_exports('상세 검증',[],[],r,'2026-09-27')
  rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
  self.assertIn(['항목','금액','세율','차감액'],rows)
  self.assertIn(['B','','15','2'],rows)

 def test_reset_clears_modes_inputs_and_results(self):
  from modules.session_store import reset_page
  state={'gift_mode':'x','wo_basis':'x','retirement_mode':'x','cov_x_0':1,'coverage_result_x':2,'pp_result':3,'jc_valuation_transfer':('x',1),'active_app':'quick_calculators','password_correct':True}
  reset_page('quick_calculators',state=state)
  self.assertEqual(state,{'active_app':'quick_calculators','password_correct':True})
