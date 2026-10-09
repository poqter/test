"""Scheduled/explicit checks. Never prints credentials or raw database content."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import argparse,json,os
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from modules.briefing.scheduler import run_scheduled
from modules.briefing.repository import BriefingRepository
from modules.briefing.preflight import run_runtime_preflight
from modules.briefing.diagnostics import build_info,failure_diagnostic


def configuration_failure(result):
    if isinstance(result,dict):
        if result.get('status') in ('configuration_required','failed','blocked'):return True
        return any(configuration_failure(value) for value in result.values())
    if isinstance(result,list):return any(configuration_failure(value) for value in result)
    return False

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['check','prepare','market','daily','publish','recover'],required=True)
    args=parser.parse_args();path=Path('briefing-operation-status.json')
    code=0
    try:
        if args.action=='check':
            repo=BriefingRepository();day=datetime.now(ZoneInfo('Asia/Seoul')).date()
            from modules.briefing.direct_sources import probe_direct_sources,load_direct_source_specs_from_env
            probe=probe_direct_sources(load_direct_source_specs_from_env())
            source_ok=any(r.get('status')=='ok' and r.get('dated_candidates',0)>0 for r in probe['direct_sources'].values())
            result={'status':'checked' if source_ok else 'configuration_required','feed_probe':probe,'project_openai_api_calls':0,'ai_enabled':repo.ai_generation_enabled(),
                'policy':{k:repo.operating_policy().get(k) for k in ('scheduled_generation_enabled','automatic_publication_enabled','external_sharing_approved')},
                'settings':[c.to_dict() for c in run_runtime_preflight()], 'operations':repo.operation_status(day)}
        else:result=run_scheduled(args.action)
        if configuration_failure(result):code=2
        report={'build':build_info(),'action':args.action,'checked_at':datetime.now(timezone.utc).isoformat(),'result':result}
        print(json.dumps(report,ensure_ascii=False))
    except Exception as exc:
        report={'action':args.action,'status':'failed','diagnostic':failure_diagnostic(exc)};code=1
        print('Daily briefing could not complete. Download the protected operation status; retries are limited.',file=sys.stderr)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(f"### 화랑 브리핑 {args.action}\n\n종료 코드: {code} · 엔진 {build_info()['engine_version']}\n\n상세 결과: briefing-operation-status.json 아티팩트. 조회·공유·PDF는 AI 요청 없음.\n")
    sys.exit(code)
