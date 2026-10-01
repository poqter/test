"""Compare all 88 engines against pre-change numerical/display snapshots.

This proves change equivalence for the recorded scenarios, not tax-law truth.
"""
from __future__ import annotations
import json,sys
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.streamlit_stub import install
install()
from tests.run_calculator_regression import _discover,_special_cases

def run():
    fixture=json.loads((ROOT/'tests/fixtures/engine_baseline.json').read_text())
    discovered,special=_discover(),_special_cases()
    results=[]
    for name,expected in fixture['cases'].items():
        try:
            result=special[name][0]() if name in special else discovered[name][0](name,discovered[name][1])
            actual={k:str(v) if isinstance(v,Decimal) else v for k,v in result.metrics.items()}
            assert actual==expected['metrics'], 'raw metric values changed'
            assert result.display()==expected['display'], 'displayed result changed'
            assert expected['inputs'], 'missing actual scenario inputs'
        except Exception as exc: results.append({'name':name,'status':'FAIL','detail':str(exc)})
        else: results.append({'name':name,'status':'PASS'})
    return {'scope':'baseline_equivalence_not_independent_legal_validation','count':len(results),'passed':sum(r['status']=='PASS' for r in results),'results':results}
if __name__=='__main__':
    r=run();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['passed']==r['count'] else 1)
