"""Run checks in separate processes; never treat an unavailable test as PASS.

Default: local pure/strict-adapter/PDF checks, runtime/browser marked NOT_RUN.
--runtime requires the real pinned Python/Streamlit environment.
--browser starts disposable local servers and a real Chromium browser.
Results go to artifacts/ (or --out), not to the deployment source tree.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def execute(name,command,out,env=None,timeout=300):
    start=time.perf_counter()
    environment=os.environ.copy();environment['HW_TEST_OUTPUT_DIR']=str(out)
    if env:environment.update(env)
    try:
        process=subprocess.run(command,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,env=environment,timeout=timeout)
        text=process.stdout+'\n'+process.stderr
        status='PASS' if process.returncode==0 else 'FAIL'
        result={'name':name,'status':status,'returncode':process.returncode}
    except subprocess.TimeoutExpired as error:
        text='TIMEOUT: '+str(error);result={'name':name,'status':'FAIL','returncode':None}
    (out/(name+'.log')).write_text(text,encoding='utf-8')
    result.update(seconds=round(time.perf_counter()-start,3),log=name+'.log')
    return result


def run(out,*,runtime=False,browser=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    python=sys.executable
    commands=[
      ('syntax',[python,'-m','compileall','-q','app.py','calculator_app.py','modules','tests','tools']),
      ('import_adapter',[python,'tests/run_import_smoke.py']),
      ('engine_smoke',[python,'tests/run_calculator_regression.py']),
      ('engine_baseline_88',[python,'tests/run_snapshot_regression.py']),
      ('first_render_adapter_88',[python,'tests/run_ui_route_smoke.py']),
      ('button_export_contract_88',[python,'tests/run_interaction_contract.py']),
      ('approved_fixes',[python,'-m','unittest','tests.test_approved_fixes','-v']),
      ('independent_reference_cases',[python,'-m','unittest','tests.test_reference_cases','-v']),
      ('business_modules',[python,'-m','unittest','tests.test_business_regression','-v']),
      ('release_apply_rollback',[python,'-m','unittest','tests.test_release_tools','-v']),
      ('document_pdf_smoke',[python,'tests/run_pdf_smoke.py']),
      ('pdf_text_options_88',[python,'tests/run_all_calculator_pdf_regression.py']),
      ('pdf_long_text_boundaries',[python,'-m','unittest','tests.test_pdf_bounds','-v']),
      ('architecture',[python,'tests/run_architecture_validation.py']),
    ]
    if (ROOT/'release_manifest.json').exists():commands.append(('file_integrity',[python,'tools/verify_release.py']))
    results=[]
    for name,command in commands:
        row=execute(name,command,out);results.append(row);print(row['status'],name,flush=True)
    if (ROOT/'.git').exists():results.append(execute('git_diff_check',['git','diff','--check'],out))
    else:results.append({'name':'git_diff_check','status':'SKIP','reason':'No Git checkout; file integrity is checked separately.'})
    if runtime:
        results.append(execute('pinned_dependency_check',[python,'-m','pip','check'],out))
        results.append(execute('real_streamlit_runtime',[python,'-m','pytest','-q','tests/test_streamlit_runtime.py'],out,env={'HW_REQUIRE_PINNED_RUNTIME':'1'},timeout=1200))
    else:
        results.extend([{'name':'pinned_dependency_check','status':'NOT_RUN','reason':'Clean Python3.12 install not executed in this offline run.'},
                        {'name':'real_streamlit_runtime','status':'NOT_RUN','reason':'Not substituted by the strict adapter tests; use --runtime.'}])
    if browser:results.append(execute('real_browser',[python,'tests/run_browser_checks.py','--out',str(out/'browser')],out,timeout=600))
    else:results.append({'name':'real_browser','status':'NOT_RUN','reason':'Browser rendering, Cloud wake and real concurrency are not part of offline tests.'})
    versions={}
    for package in ('streamlit','pandas','numpy','openpyxl','reportlab','pypdf','PyMuPDF'):
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package]=None
    from modules.shared.build_info import BUILD_ID
    report={'build_id':BUILD_ID,'tested_at_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
            'packages':versions,'scope':'No independent all-88 legal/tax certification; snapshots check behavioral equivalence.',
            'counts':{status:sum(row['status']==status for row in results) for status in ('PASS','FAIL','SKIP','NOT_RUN')},'checks':results}
    (out/'release_validation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/validation')
    parser.add_argument('--runtime',action='store_true')
    parser.add_argument('--browser',action='store_true')
    args=parser.parse_args();report=run(args.out,runtime=args.runtime,browser=args.browser)
    print(json.dumps(report['counts'],indent=2))
    raise SystemExit(1 if report['counts']['FAIL'] else 0)
