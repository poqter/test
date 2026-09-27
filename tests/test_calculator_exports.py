import csv,io,unittest
from modules.calculator_exports import build_exports
from modules.retirement_remaining import withdrawal
class Exports(unittest.TestCase):
 def test_snapshot_and_formula_injection(self):
  r=withdrawal(100,1,[('=HYPERLINK("x")',2000,0)],True)
  text,data=build_exports('계산',[('이름','', '문자',100)],[ '=HYPERLINK("x")'],r,'2026-09-26 22:10')
  self.assertTrue(data.startswith(b'\xef\xbb\xbf'));parsed=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
  for k,v in r.display().items():self.assertIn(k+': '+v,text);self.assertTrue(any(row[0]==k for row in parsed))
  cells=[v for row in parsed for v in row]
  self.assertFalse(any(v.startswith('=HYPERLINK') for v in cells));self.assertIn('계산에 사용한 입력',text)
