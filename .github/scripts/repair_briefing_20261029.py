"""One dated, explicitly approved repair; original failed runs remain immutable."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from copy import deepcopy
from datetime import date,datetime
import json,uuid
from modules.briefing.repository import BriefingRepository
from modules.briefing.runtime import generate_and_store_briefings
from modules.briefing.scheduler import cutoff,publish_ready,KST
from modules.briefing.execution_policy import checkpoint_identity,token_exhausted_response
from modules.briefing.diagnostics import build_info

DAY=date(2026,10,29)

def main():
    if datetime.now(KST).date()!=DAY:raise RuntimeError('Dated recovery authorization has expired')
    if not build_info()['code_matches_release']:raise RuntimeError('Release manifest mismatch')
    repo=BriefingRepository()
    if not repo.operating_policy().get('scheduled_generation_enabled'):raise RuntimeError('Scheduled generation paused')
    outcomes={}
    for code in ('MARKET','NEWS'):
        existing=repo.bundle_for_date(code,DAY,include_draft=True)
        if existing:
            outcomes[code]={'status':'existing_edition_preserved'};continue
        original=repo.daily_run_status(DAY,code)
        if original.get('status') not in ('failed','blocked'):raise RuntimeError('Unexpected original run state')
        key=f'{DAY}:APPROVED_REPAIR_V1_{code}';owner=str(uuid.uuid4())
        claim=repo.claim_run(key,DAY,'APPROVED_REPAIR_V1_'+code,owner,False)
        if not claim.get('claimed'):
            outcomes[code]={'status':'repair_already_claimed'};continue
        saved=deepcopy(original.get('checkpoint') or {})
        saved['incident_recovery']={'date':str(DAY),'authorization':'Owner approved higher output limit and recovery',
                                   'original_run_key':f'{DAY}:{code}','original_status':original['status']}
        if code=='MARKET':
            if not saved.get('phase_b') or not token_exhausted_response(saved.get('analysis_responses',{}).get(code)):
                repo.save_run(key,owner,saved,'blocked');raise RuntimeError('Market incident evidence changed')
        else:
            # Explicit owner authorization permits proceeding with saved direct feeds;
            # the original uncertain search and usage records are never erased or replayed.
            if not saved.get('direct_collection'):raise RuntimeError('Saved direct feeds missing')
            saved['incident_recovery']['original_pending_request']=saved.get('pending_request')
            saved['incident_recovery']['original_charge_uncertain']=saved.get('charge_uncertain')
            saved.pop('pending_request',None);saved['charge_uncertain']=False
            saved.pop('partial_b',None)
        saved['input_identity']=checkpoint_identity(cutoff(DAY,code),(code,))
        def save(state):repo.save_run(key,owner,state)
        def before(kind):
            if kind!='analysis' or saved.get('repair_request_started'):raise RuntimeError('Only one approved analysis per missing profile')
            if saved.get('pending_request') or saved.get('charge_uncertain'):raise RuntimeError('Unconfirmed request')
            saved['repair_request_started']=True
            saved['pending_request']={'kind':kind,'at':datetime.now(KST).isoformat()};save(saved)
            try:repo.reserve_request(DAY,kind)
            except Exception:
                saved.pop('pending_request',None);save(saved);raise
        try:
            save(saved)
            result=generate_and_store_briefings(repository=repo,profile_codes=(code,),force_shadow=True,
                as_of=cutoff(DAY,code),checkpoint=saved,save_checkpoint=save,before_request=before,
                trigger_type='retry',allow_partial_market=code=='MARKET',saved_material_only=code=='NEWS')
            repo.save_run(key,owner,saved,'completed')
            outcomes[code]={'status':'completed','profiles':[r.profile_code for r in result.profiles]}
        except Exception as exc:
            repo.save_run(key,owner,saved,'blocked' if saved.get('pending_request') or saved.get('charge_uncertain') else 'failed')
            outcomes[code]={'status':'failed','error_type':type(exc).__name__,'message':str(exc)[:250]}
        outcomes[code]['publication']=publish_ready(repo,DAY,(code,))
    Path('briefing-repair-status.json').write_text(json.dumps(outcomes,ensure_ascii=False,indent=2))
    print(json.dumps(outcomes,ensure_ascii=False))
    return 0 if all(repo.bundle_for_date(code,DAY) for code in ('MARKET','NEWS')) else 2

if __name__=='__main__':sys.exit(main())
