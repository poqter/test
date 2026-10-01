"""Explicit button/export contract checks using a strict stub, NOT browser tests."""
import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.streamlit_stub import install
st=install(strict_numeric=True)
from modules.calculators.jarvia_calculator_center import ITEMS,run
from tests.run_calculator_regression import _discover
from modules.calculators.coverage.coverage_calculator_ui import _set_inputs
from modules.calculators.input_design import set_money_state
from modules.calculators.input_policy import policy_for_field
from modules.calculators.structured_inputs import reset_table
import importlib
D=_discover()
res=[]
for name in ITEMS:
 st.session_state.clear();st._api.events.clear();st._api.clicked.clear()
 st.session_state['jc_open']=name
 try:
  run()
  buttons=[e for e in st._api.events if e['kind']=='button']
  calc=[e for e in buttons if e['args'] and ('계산' in str(e['args'][0]) or '분석' in str(e['args'][0])) and '목록' not in str(e['args'][0]) and '자세히' not in str(e['args'][0]) and not e['kwargs'].get('disabled')]
  if name in D:
   fn,vals,source=D[name]
   mod=importlib.import_module(source)
   entries=mod.FIELDS[name]
   _set_inputs(name,entries,example=True)
   for i,(f,v) in enumerate(zip(entries,vals)):
    if f[2]=='원': set_money_state(f'cov_{name}_{i}',f[0],v,policy=policy_for_field(name,i,f[0]))
    else: st.session_state[f'cov_{name}_{i}']=v
   reset_table(name,example=True)
  st._api.events.clear()
  run()
  buttons=[e for e in st._api.events if e['kind']=='button']
  calc=[e for e in buttons if e['args'] and str(e['args'][0]) in ('계산하기','계산','분석하기','퇴직금 계산','상속세 계산','증여세 계산')]
  ids=[e['kwargs'].get('key',e['args'][0]) for e in calc]
  st._api.clicked.update(ids)
  st._api.events.clear()
  run()
  errs=[e for e in st._api.events if e['kind']=='error']
  down=[e for e in st._api.events if e['kind']=='download_button']
  res.append({'name':name,'buttons':ids,'errors':[str(e['args']) for e in errs],'downloads':len(down),'status':'PASS'})
 except Exception as e:
  res.append({'name':name,'status':'FAIL','error':str(e),'trace':traceback.format_exc()})
for row in res:
 if row.get('errors') or not row.get('downloads'):
  row['status']='FAIL'
report={'scope':'strict_stub_button_and_export_contract_not_real_Streamlit',
        'count':len(res),'passed':sum(row['status']=='PASS' for row in res),'results':res}
print(json.dumps(report,ensure_ascii=False,indent=2))
for r in res:
 if r['status']=='FAIL' or r.get('errors') or not r.get('downloads'): print(json.dumps(r,ensure_ascii=False))
print('count',len(res),'exceptions',sum(r['status']=='FAIL' for r in res),'download',sum(bool(r.get('downloads')) for r in res))

raise SystemExit(0 if len(res)==88 and all(r["status"]=="PASS" for r in res) else 1)
