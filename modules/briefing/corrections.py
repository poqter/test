"""A correction creates a new immutable edition, with the original evidence."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from .public_body import customer_body
from .repository import BriefingRepositoryError

EDIT_FIELDS=('title','summary','why_important','impact_summary')


def corrected_content(content, event_key, changes, reason):
    result=deepcopy(content)
    if not str(reason).strip():raise ValueError('정정 사유를 입력해 주세요.')
    if set(changes)-set(EDIT_FIELDS):raise ValueError('검증된 출처·날짜·지표는 문구 정정에서 변경할 수 없습니다.')
    issue=next((r for r in result.get('issues',[]) if r.get('event_key')==event_key),None)
    if not issue:raise ValueError('정정할 기사를 확인할 수 없습니다.')
    for field,value in changes.items():
        value=str(value).strip()
        if len(value)>4000 or field in ('title','summary') and not value:raise ValueError('제목·요약을 확인해 주세요.')
        issue[field]=value
    result.setdefault('corrections',[]).append({'event_key':event_key,'reason':str(reason).strip()[:1000],
        'corrected_at':datetime.now(timezone.utc).isoformat()})
    return result


def apply_correction(repo, bundle, event_key, changes, reason, actor):
    from .runtime import body_quality_ready
    from .sharing import build_packet
    # This permission is checked again on the server, independently of the UI.
    repo.require_manager(actor)
    old=bundle['revision'];briefing=bundle['briefing'];snap=bundle['snapshot']
    if old.get('publication_status')!='published':raise BriefingRepositoryError('현재 공개본만 정정할 수 있습니다.')
    latest=repo._first(repo._request('GET','/rest/v1/hwarang_briefings',params={'id':'eq.'+briefing['id'],'select':'current_published_revision_id'}))
    if not latest or latest.get('current_published_revision_id')!=old['id']:raise BriefingRepositoryError('현재 공개본을 다시 열어 주세요.')
    content=corrected_content(snap['content_payload'],event_key,changes,reason);external=customer_body(content)
    if not body_quality_ready(content):raise BriefingRepositoryError('정정본의 출처 또는 본문을 확인할 수 없습니다.')
    public_ready=body_quality_ready(external)
    if content.get('profile_code')=='MARKET':public_ready=public_ready and len(external['market_metrics'])==6 and 3<=len(external['market_flow'])<=5
    rev=repo.create_revision({'briefing_id':briefing['id'],'revision_no':repo.next_revision_no(briefing['id']),
        'revision_type':'correction','validation_status':'ok','coverage_status':old['coverage_status'],
        'generated_at':datetime.now(timezone.utc).isoformat(),'data_as_of':old.get('data_as_of'),
        'created_by':actor,'change_summary':reason[:1000],'version_trace':old.get('version_trace') or {}})
    qa={**(snap.get('qa_payload') or {}),'internal_body_ready':True,'public_body_ready':public_ready,'correction_of':old['id']}
    fast=deepcopy(snap.get('fast_brief_payload') or {})
    before=next(r for r in snap['content_payload']['issues'] if r['event_key']==event_key)
    for item in fast.get('items',[]):
        if item.get('title')==before.get('title'):item.update({k:v for k,v in changes.items() if k in ('title','summary')})
    today=deepcopy(snap.get('today_action_payload') or {})
    for group in today.values():
        if isinstance(group,list):
            for item in group:
                if isinstance(item,dict) and item.get('event_key')==event_key:item.update({k:v for k,v in changes.items() if k in ('title','summary')})
    new_snap=repo.create_snapshot({'revision_id':rev['id'],'content_payload':content,'external_content_payload':external,
        'content_hash':sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'fast_brief_payload':fast,'today_action_payload':today,'qa_payload':qa})
    # Copy full relational rows, replacing IDs. No old snapshot is overwritten.
    def read(table):return repo._request('GET','/rest/v1/'+table,params={'snapshot_id':'eq.'+snap['id'],'select':'*'}) or []
    def clone(row):return {**{k:v for k,v in row.items() if k not in ('id','created_at','snapshot_id')},'snapshot_id':new_snap['id']}
    sources=read('hwarang_briefing_sources');new_sources=repo.insert_sources([clone(r) for r in sources])
    source_map={r['id']:next(n['id'] for n in new_sources if n['canonical_url']==r['canonical_url']) for r in sources}
    issues=read('hwarang_briefing_issues');copies=[]
    for row in issues:
        item=clone(row)
        if row['issue_key'].endswith(':'+event_key):
            item.update({k:v for k,v in changes.items() if k in ('title','summary')})
            item['analysis_payload']={**(item.get('analysis_payload') or {}),**{k:v for k,v in changes.items() if k not in ('title','summary')}}
        copies.append(item)
    new_issues=repo.insert_issues(copies);issue_map={r['id']:next(n['id'] for n in new_issues if n['issue_key']==r['issue_key']) for r in issues}
    links=bundle.get('issue_sources') or []
    repo.link_issue_sources([{**r,'issue_id':issue_map[r['issue_id']],'source_id':source_map[r['source_id']]} for r in links if r['issue_id'] in issue_map and r['source_id'] in source_map])
    actions=[]
    for row in read('hwarang_briefing_actions'):
        item=clone(row);item['issue_id']=issue_map.get(row.get('issue_id'))
        if row.get('issue_id') in issue_map and any(i['id']==row['issue_id'] and i['issue_key'].endswith(':'+event_key) for i in issues):
            item.update({k:v for k,v in changes.items() if k in ('title','summary')})
        actions.append(item)
    repo.insert_actions(actions)
    # Private assets are prepared before changing the current published pointer.
    shares=repo._request('GET','/rest/v1/hwarang_briefing_public_shares',params={'revision_id':'eq.'+old['id'],
        'revoked_at':'is.null','expires_at':'gt.'+datetime.now(timezone.utc).isoformat(),'select':'token,public_packet'}) or []
    refreshed=[]
    if public_ready:
        for row in shares:
            identity=(row.get('public_packet') or {}).get('sender')
            if not identity:continue
            packet=build_packet(new_snap,briefing,rev,identity,repo.public_base_url(),row['token'])
            repo._upload_share_assets(row['token'],packet);refreshed.append((row['token'],packet))
    repo.publish_revision(briefing['id'],rev['id'],actor_user_id=actor)
    for token,packet in refreshed:
        repo._request('PATCH','/rest/v1/hwarang_briefing_public_shares',params={'token':'eq.'+token,'revision_id':'eq.'+old['id']},
            json={'revision_id':rev['id'],'public_packet':packet})
    repo.audit({'actor_type':'user','actor_user_id':actor,'action':'BRIEFING_CORRECTED','briefing_id':briefing['id'],
        'revision_id':rev['id'],'details':{'previous_revision':old['id'],'event_key':event_key,'reason':reason[:1000]}})
    return rev
