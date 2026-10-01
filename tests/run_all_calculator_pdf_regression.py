"""PDF contents from the actual 88 recorded inputs and calculated outputs.

Text/snapshot checks and renderer bounds are separate from human visual review.
Every section combination is generated; a parseable header alone is not PASS.
"""
from __future__ import annotations
import io,itertools,json,re,sys,unicodedata,os
from pathlib import Path
from decimal import Decimal
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests.streamlit_stub import install
install()
from tests.run_calculator_regression import CATALOG_NAMES,_discover,_special_cases
from modules.calculators.result_pdf import build_result_pdf
from modules.shared.report_fonts import pdf_text

def normalized(text):return re.sub(r'\s+','',unicodedata.normalize('NFC',str(text)))
def input_text(value):
    if value is None:return '미적용'
    if isinstance(value,bool):return '예' if value else '아니오'
    if isinstance(value,(int,float,Decimal)):return format(value,',')
    if isinstance(value,str) and re.fullmatch(r'-?\d+(?:\.\d+)?',value):return format(Decimal(value),',')
    return str(value)

def run():
    discovered,special=_discover(),_special_cases()
    fixtures=json.loads((ROOT/'tests/fixtures/engine_baseline.json').read_text())['cases']
    rows=[];combination_count=0;pages_total=0
    evidence=os.environ.get('HW_PDF_EVIDENCE_DIR')
    if evidence:Path(evidence).mkdir(parents=True,exist_ok=True)
    for name in CATALOG_NAMES:
        try:
            result=special[name][0]() if name in special else discovered[name][0](name,discovered[name][1])
            from modules.calculators.calculator_center import QUICK_CALCULATORS
            from modules.calculators.calculator_catalog import MODES
            if name in QUICK_CALCULATORS:
                spec=MODES[QUICK_CALCULATORS[name]]
                result.formula=spec[3];result.assumptions=[spec[4]]
            inputs=[(v['label']+(' ('+v['unit']+')' if v['unit'] else ''),v['value']) for v in fixtures[name]['inputs']]
            assert inputs,'actual input fixture required'
            for flags in itertools.product((False,True),repeat=3):
                if not any(flags):continue
                for enlarged in ((False,True) if flags[0] else (False,)):
                    payload=build_result_pdf(name,inputs,result,'2026-10-01 09:34',include_results=flags[0],include_inputs=flags[1],include_basis=flags[2],enlarge_results=enlarged)
                    assert payload.startswith(b'%PDF')
                    reader=PdfReader(io.BytesIO(payload));assert reader.pages
                    text=normalized('\n'.join(page.extract_text() or '' for page in reader.pages))
                    assert normalized(pdf_text(name)) in text
                    assert 'CALCULATIONREPORT' not in text
                    assert '계산시각' not in text
                    assert '01계산' not in text and '02계산' not in text and '03산출' not in text
                    if flags[2]:
                        assert '산출근거및적용조건' in text
                    if flags[0]:
                        assert '계산결과' in text
                        for label,value in result.display().items():
                            assert normalized(pdf_text(value)) in text, 'missing displayed result: '+label
                    if flags[1]:
                        assert '계산에사용한입력' in text
                        for label,value in inputs:
                            assert normalized(pdf_text(label)) in text,'missing input label: '+label
                            expected_value = normalized(pdf_text(input_text(value)))
                            # Customer PDFs may suppress a redundant '(원)' rendering when the
                            # same amount is already shown in 만원. Raw numeric fixtures remain exact.
                            assert expected_value in text,'missing input value: '+label
                    if flags[0] and flags[1]:
                        assert text.index('계산에사용한입력') < text.index('계산결과')
                    combination_count+=1;pages_total+=len(reader.pages)
                    if evidence and flags==(True,True,True) and not enlarged:
                        (Path(evidence)/(fixtures[name]['id']+'.pdf')).write_bytes(payload)
            rows.append({'name':name,'status':'PASS'})
        except Exception as exc:rows.append({'name':name,'status':'FAIL','detail':f'{type(exc).__name__}: {exc}'})
    return {'scope':'actual_inputs_and_output_text_all_section_combinations','count':len(rows),'passed':sum(r['status']=='PASS' for r in rows),'variants':combination_count,'pages':pages_total,'results':rows}
if __name__=='__main__':
    report=run();print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['count']==report['passed'] else 1)
