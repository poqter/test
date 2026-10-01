"""Long Korean cells and section selection regressions; no font binaries."""
from __future__ import annotations
import io,itertools,unittest
from pathlib import Path
from decimal import Decimal
from pypdf import PdfReader
from tests.streamlit_stub import install
install()
from modules.calculators.result_pdf import build_result_pdf
from modules.calculators.finance.finance_models import FinanceResult
class PdfBounds(unittest.TestCase):
 def test_all_sections_cannot_be_disabled(self):
  r=FinanceResult({'금액':Decimal(123456)},'산식',['가정'])
  with self.assertRaises(ValueError):build_result_pdf('시험',[],r,'2026-10-01',include_results=False,include_inputs=False,include_basis=False)
 def test_long_single_cell_and_multiple_pages(self):
  r=FinanceResult({'필요 금액':Decimal(123456)},'총액 − 재원 = 부족액',['입력에 따른 참고값'])
  for repetitions in (1,120,360):
   text='길이가 긴 계산 조건을 원본과 대조해 주세요. '*repetitions
   payload=build_result_pdf('가족 생활자금계산기',[('긴 조건',text)],r,'2026-10-01')
   reader=PdfReader(io.BytesIO(payload));combined=''.join('\n'.join((p.extract_text() or '').splitlines()[3:]) for p in reader.pages)
   self.assertEqual(''.join(combined.split()).count('원본과대조해주세요.'),repetitions)
 def test_many_rows_no_omission(self):
  inputs=[(f'항목 {i}',f'검증값-{i:04d}') for i in range(80)]
  r=FinanceResult({'금액':Decimal(123456)},'합산',['가정'])
  reader=PdfReader(io.BytesIO(build_result_pdf('시험',inputs,r,'2026-10-01')))
  combined=''.join('\n'.join((p.extract_text() or '').splitlines()[3:]) for p in reader.pages)
  self.assertGreater(len(reader.pages),1)
  for i in range(80):self.assertIn(f'검증값-{i:04d}',combined)
 def test_primary_results_are_equal_and_primary_first(self):
  r=FinanceResult({'보조 금액':Decimal(100),'필요 연 수익률':Decimal('2.5')},'공식',['가정'],units={'필요 연 수익률':'%'})
  text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(build_result_pdf('수익률계산기',[],r,'2026-10-01',enlarge_results=True))).pages)
  self.assertLess(text.find('필요 연 수익률'),text.find('보조 금액'))
if __name__=='__main__':unittest.main(verbosity=2)
