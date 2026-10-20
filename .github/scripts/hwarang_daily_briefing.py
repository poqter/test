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


def configuration_failure(result, *, action=None):
    if action == 'catch_up':
        # Delivery is authoritative; a transient earlier exception may have recovered.
        return not isinstance(result, dict) or result.get('status') not in ('published', 'before_publication_time')
    if action == 'check':
        # Historical failures are evidence, not failures of this readiness check.
        if not isinstance(result, dict):
            return True
        return (
            result.get('status') in ('configuration_required', 'failed', 'blocked')
            or any(check.get('required') and not check.get('ok')
                   for check in result.get('settings', []))
        )
    if isinstance(result,dict):
        # Missing editions and QA holds are not successful publication.
        if result.get('status') in ('configuration_required','failed','blocked','no_snapshot','quality_hold','organization_approval_required'):return True
        return any(configuration_failure(value) for value in result.values())
    if isinstance(result,list):return any(configuration_failure(value) for value in result)
    return False

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['check','prepare','market','daily','publish','recover','catch_up'],required=True)
    args=parser.parse_args();path=Path('briefing-operation-status.json')
    code=0
    try:
        if args.action=='check':
            repo=BriefingRepository();day=datetime.now(ZoneInfo('Asia/Seoul')).date()
            from modules.briefing.direct_sources import probe_direct_sources,load_direct_source_specs_from_env
            probe=probe_direct_sources(load_direct_source_specs_from_env())
            source_ok=any(r.get('status')=='ok' and r.get('dated_candidates',0)>0 for r in probe['direct_sources'].values())
            checks=[c.to_dict() for c in run_runtime_preflight()]
            required_ready=all(c['ok'] for c in checks if c['required'])
            policy = repo.operating_policy()
            result={'status':'checked' if source_ok and required_ready else 'configuration_required','feed_probe':probe,'project_openai_api_calls':0,'ai_enabled':repo.ai_generation_enabled(),
                'policy':{k:policy.get(k) for k in ('scheduled_generation_enabled','automatic_publication_enabled','external_sharing_approved')},
                'settings':checks, 'operations':repo.operation_status(day),
                'today_editions':{code: ({'status':b['revision'].get('publication_status'),
                    'validation':b['revision'].get('validation_status'), 'date':str(b['briefing']['briefing_date'])}
                    if (b:=repo.bundle_for_date(code,day,include_draft=True)) else {'status':'no_snapshot'})
                    for code in ('MARKET','NEWS','INSURANCE')}}
        else:result=run_scheduled(args.action)
        if configuration_failure(result, action=args.action):code=2
        report={'build':build_info(),'action':args.action,'checked_at':datetime.now(timezone.utc).isoformat(),'result':result}
        print(json.dumps(report,ensure_ascii=False))
    except Exception as exc:
        report={'action':args.action,'status':'failed','diagnostic':failure_diagnostic(exc)};code=1
        print('Daily briefing could not complete. Download the protected operation status; retries are limited.',file=sys.stderr)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(f"### 화랑 브리핑 {args.action}\n\n종료 코드: {code} · 엔진 {build_info()['engine_version']}\n\n상세 결과: briefing-operation-status.json 아티팩트. 조회·공유·PDF는 AI 요청 없음.\n")
            if args.action == 'catch_up' and isinstance(report.get('result'), dict):
                delivery = report['result']
                f.write('\n오늘 게시 상태: '+str(delivery.get('status'))+'\n\n')
                for row in delivery.get('publication', []):
                    f.write('- '+str(row.get('profile'))+': '+str(row.get('status'))+'\n')
    sys.exit(code)
