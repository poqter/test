"""Persistent calendar command boundary. Uses existing caller Records and RLS only."""
from datetime import date, datetime, timedelta, time
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
import json
from modules.shared.hwarang_auth import HwarangAuthError
from modules.activity.redesign import write_event, KST, KINDS

DAY = timedelta(days=1)
NULLABLE_TIME_PROTOCOL = 3

def identity(value):
    return str(UUID(str(value)))

def event(db, key, own=False, archived=False):
    params = {'id': 'eq.' + identity(key), 'limit': '1'}
    if archived: params['deleted_at'] = 'not.is.null'
    rows = db.request('GET', 'sales_events', params)
    if not rows or (own and rows[0]['owner'] != db.uid):
        raise HwarangAuthError('일정을 조회하거나 변경할 권한이 없습니다.')
    return rows[0]

def snapshot(db, args):
    first, last = date.fromisoformat(args['first']), date.fromisoformat(args['last'])
    if not 0 <= (last-first).days <= 62: raise ValueError('조회 기간을 확인해 주세요.')
    member = args.get('member')
    if member and (not db.me['managed'] or member not in db.members):
        raise HwarangAuthError('조회 대상 권한을 확인해 주세요.')
    team = bool(args.get('team'))
    branch = {r['member']: r for r in db.request('POST', 'rpc/sales_branch_members', body={})}
    scope = {'owner':'eq.'+member} if member else {'unit':'eq.'+db.me['unit']}
    rows = db.period('sales_events', first, last, **scope)
    details = {r['id']:r for r in rows}
    summary = db.request('POST','rpc/sales_calendar_days_v2',body={'first_day':str(first),'last_day':str(last)})
    visible = list(details.values()) if member else [details.get(r['id'],r) for r in summary if team or db.uid in (r['owner'],r.get('companion')) or r['common']]
    now = datetime.now(KST)
    cards=[]
    for row in sorted(visible,key=lambda r:(r['day'],r.get('start_time') or '',r['id'])):
        owner=branch.get(row['owner'],db.members.get(row['owner'],{})).get('label','지점 공통')
        stamp=(row.get('start_time') or ('시간 미정' if row.get('time_pending') else '종일'))[:5]
        status=row['status']
        if status=='예정' and (row['day']<str(now.date()) or row['day']==str(now.date()) and row.get('start_time') and row['start_time']<now.strftime('%H:%M:%S')): status='결과 미입력'
        label=f"{stamp} · {row['kind']} · {owner} · {status}"
        if row.get('companion'):label+=' · 동행 '+branch.get(row['companion'],{}).get('label','')
        if row.get('help'):label+=' · 지원 요청'
        cards.append(dict(start=row.get('start_time'),timePending=bool(row.get('time_pending')),place=row.get('place',''),status=row['status'],revision=row.get('revision'),id=row['id'],day=row['day'],kind=row['kind'],member=row['owner'],allDay=not row.get('start_time'),short=(row.get('title') or row['kind'])+(' · '+owner if team else ''),label=label,done=row['status']=='완료',soon=bool(row['day']==str(now.date()) and row['status']=='예정' and row.get('start_time') and 0<=(datetime.combine(now.date(),time.fromisoformat(row['start_time']),KST)-now).total_seconds()<=1800),readable=row['id'] in details))
    unit=db.members[member]['unit'] if member else db.me['unit']
    stamp=db.request('POST','rpc/sales_calendar_stamp',body={'first_day':str(first),'last_day':str(last),'p_unit':unit})
    return dict(events=cards,rangeStart=str(first),rangeEnd=str(last),syncUnit=unit,syncStamp=stamp,scopeLabel=db.members[member]['label'] if member else '지점 일정' if team else '내 일정',roster={u:r['label'] for u,r in branch.items() if not member or u==member} if team or member else {})

def detail(db,key):
    row=event(db,key)
    authors={r['member']:r['label'] for r in db.request('POST','rpc/sales_branch_members',body={})}
    return dict(row=row,canReview=bool(db.me['managed'] and db.members.get(row['owner'],{}).get('managed')),
        reviews=[{**r,'author':db.members.get(r['reviewer'],{}).get('label') or authors.get(r['reviewer']) or ('나' if r['reviewer']==db.uid else '관리자')} for r in db.request('GET','sales_reviews',{'event':'eq.'+row['id'],'deleted_at':'is.null','order':'created_at.desc'}) if r['message']!='일정 확인'],
        contracts=db.request('GET','sales_contracts',{'owner':'eq.'+db.uid,'event':'eq.'+row['id'],'order':'day.desc'}) if row['owner']==db.uid else [])

def parse_clock(value):
    value=str(value).strip()
    if value.isdigit():
        if len(value)<=2:value=value.zfill(2)+':00'
        elif len(value) in (3,4):value=value.zfill(4)[:2]+':'+value.zfill(4)[2:]
        else:raise ValueError('시간은 0~23시, 분은 0~59분으로 입력해 주세요.')
    try:return time.fromisoformat(value).isoformat()
    except ValueError:raise ValueError('시간은 0~23시, 분은 0~59분으로 입력해 주세요.')

def save_event(db,a):
    old=event(db,a['id'],own=True) if a.get('id') else None
    parent=event(db,a['parent'],own=True) if a.get('parent') else None
    v=a['data']; day=date.fromisoformat(v['day'])
    title=str(v.get('title','')).strip()
    if not title or len(title)>200:raise ValueError('일정명을 200자 이내로 입력해 주세요.')
    kind=v.get('kind','미분류')
    if kind not in KINDS and (not old or kind!=old['kind']):raise ValueError('활동 종류를 확인해 주세요.')
    mode=v.get('mode','시간 미정')
    if v.get('auto_time'):
        mode='종일' if v.get('all_day') else '시간 지정' if str(v.get('start','')).strip() else '시간 미정'
        if mode=='시간 미정' and str(v.get('end','')).strip():raise ValueError('종료 시간보다 시작 시간을 먼저 입력해 주세요.')
    start=(v.get('start') or None) if mode=='시간 지정' else None
    end=(v.get('end') or None) if start else None
    if mode=='시간 지정' and not start:raise ValueError('시작 시간을 입력해 주세요.')
    if start:start=parse_clock(start)
    if end:end=parse_clock(end)
    if end and end<=start:raise ValueError('종료 시간은 시작 시간보다 늦어야 합니다.')
    follow=date.fromisoformat(v['follow']) if v.get('follow') else None
    if follow and follow<day:raise ValueError('후속 일정 날짜를 확인해 주세요.')
    companion=v.get('companion') or None
    if companion:
        people={r['member'] for r in db.request('POST','rpc/sales_branch_members',body={})}
        if companion==db.uid or companion not in people and (not old or companion!=old.get('companion')):raise ValueError('동행자를 확인해 주세요.')
    status=v.get('status','예정') if old else '예정'
    if status not in ('예정','완료','연기','취소'):raise ValueError('상태를 확인해 주세요.')
    common=bool(v.get('common'))
    if common and not db.me['managed'] and (not old or not old.get('common')):raise HwarangAuthError('공통 일정 권한을 확인해 주세요.')
    body=dict(day=str(day),title=title,kind=kind,start_time=start,end_time=end,time_pending=mode=='시간 미정',place=str(v.get('place','')),note=str(v.get('note','')),help=str(v.get('help','')) if v.get('support') else '',companion=companion,common=common,status=status,result=str(v.get('result','')) if old else '')
    repeat=int(v.get('repeats',1)) if v.get('repeat') and not old else 1
    if not 1<=repeat<=52:raise ValueError('반복 횟수는 1~52회입니다.')
    if start and status=='예정':
        stop=day+7*(repeat-1)*DAY; days={str(day+7*i*DAY) for i in range(repeat)}
        candidates=db.period('sales_events',day,stop,owner='eq.'+db.uid,status='eq.예정')
        overlap=[r['id'] for r in candidates if r['id']!=(old or {}).get('id') and r['day'] in days and r.get('start_time') and (r['start_time']==start or r['start_time']<(end or start) and (r.get('end_time') or r['start_time'])>start)]
        if companion:
            cursor=day
            while cursor<=stop:
                edge=min(stop,cursor+62*DAY)
                candidates=db.request('POST','rpc/sales_calendar_days_v2',body={'first_day':str(cursor),'last_day':str(edge)})
                overlap.extend(r['id'] for r in candidates if r['id']!=(old or {}).get('id') and r['day'] in days and r['status']=='예정' and companion in (r['owner'],r.get('companion')) and r.get('start_time')==start)
                cursor=edge+DAY
        signature=str(uuid5(NAMESPACE_URL,json.dumps([body,repeat,sorted(set(overlap))],sort_keys=True)))
        if overlap and a.get('overlap')!=signature:return {'overlap':signature,'message':'본인 또는 동행자의 기존 일정과 시간이 겹칩니다. 그대로 저장하려면 저장 버튼을 한 번 더 눌러 주세요.'}
    if old:
        # Never replace the editor's revision with the newest revision.
        original={**old,'revision':int(a['revision'])}
        write_event(db,original,body,follow)
        key=old['id']
    else:
        seed=identity(a['seed'])
        rows=[{**body,'unit':db.me['unit'],'previous_event':parent['id'] if parent else None,'series_id':seed if repeat>1 else None,'day':str(day+i*7*DAY),'id':str(uuid5(NAMESPACE_URL,seed+str(i)))} for i in range(repeat)]
        db.request('POST','sales_events',body=rows,prefer='resolution=ignore-duplicates')
        stored=db.request('GET','sales_events',{'id':'in.('+','.join(r['id'] for r in rows)+')'})
        indexed={r['id']:r for r in stored}
        if any(r['id'] not in indexed or any(indexed[r['id']].get(k)!=v for k,v in r.items()) for r in rows):raise HwarangAuthError('저장을 확인하지 못했습니다. 입력을 유지한 채 다시 시도해 주세요.')
        key=rows[0]['id']
    return {'id':key,'day':str(day)}

def command(db,op,a):
    db._reads.clear()
    if op=='load':return snapshot(db,a)
    if op=='detail':return detail(db,a['id'])
    if op=='save':return save_event(db,a)
    if op=='move':
        row=event(db,a['id'],own=True)
        if row['revision']!=int(a['revision']):raise HwarangAuthError('일정이 변경됐습니다. 최신 일정을 확인해 주세요.')
        day=str(date.fromisoformat(a['day']))
        if day!=row['day']:
            body={k:row.get(k) for k in ('day','start_time','end_time','time_pending','title','kind','place','note','help','companion','common','status','result')}
            body['day']=day
            write_event(db,row,body)
        current=event(db,row['id'],own=True)
        return {'id':row['id'],'day':current['day'],'revision':current['revision']}
    if op in ('review_edit','review_delete'):
        row=event(db,a['id'])
        found=db.request('GET','sales_reviews',{'id':'eq.'+identity(a['review']),'event':'eq.'+row['id'],'deleted_at':'is.null','limit':'1'})
        if not found or found[0]['reviewer']!=db.uid:raise HwarangAuthError('본인이 작성한 피드백만 변경할 수 있습니다.')
        version=int(a['version'])
        if found[0]['edit_version']!=version:raise HwarangAuthError('피드백이 변경됐습니다. 다시 열어 확인해 주세요.')
        text=str(a.get('message','')).strip()
        if op=='review_edit' and (not text or len(text)>4000):raise ValueError('피드백을 1~4000자로 입력해 주세요.')
        body={'message':text} if op=='review_edit' else {'deleted_at':datetime.now(KST).isoformat()}
        updated=db.request('PATCH','sales_reviews',{'id':'eq.'+found[0]['id'],'reviewer':'eq.'+db.uid,'edit_version':'eq.'+str(version)},body=body,prefer='return=representation')
        if not updated:raise HwarangAuthError('피드백 변경 결과를 확인하지 못했습니다. 다시 확인해 주세요.')
        return {'ok':True}
    if op=='status':
        row=event(db,a['id'],own=True)
        target=a.get('status')
        if target not in ('완료','예정') or row['status'] not in ('완료','예정'):
            raise ValueError('이 일정은 상세 화면에서 상태를 변경해 주세요.')
        if row['revision']!=int(a['revision']):
            raise HwarangAuthError('다른 화면에서 변경했습니다. 최신 목록을 확인한 뒤 다시 시도해 주세요.')
        body={k:row.get(k) for k in ('day','start_time','end_time','time_pending','title','kind','place','note','help','companion','common','status','result')}
        body['status']=target
        write_event(db,row,body)
        current=event(db,row['id'],own=True)
        return {'id':current['id'],'status':current['status'],'revision':current['revision']}
    if op=='trash':
        return db.request('GET','sales_events',{'owner':'eq.'+db.uid,'deleted_at':'gte.'+(datetime.now(KST)-30*DAY).isoformat(),'order':'deleted_at.desc,day.asc'})
    if op=='archive':
        row=event(db,a['id'],own=True,archived=bool(a.get('restore')))
        if row['revision']!=int(a['revision']):raise HwarangAuthError('다른 화면에서 변경했습니다. 최신 기록을 확인해 주세요.')
        count=db.request('POST','rpc/sales_archive_event',body={'p_id':row['id'],'p_revision':row['revision'],'p_future':bool(a.get('future')) and not a.get('restore'),'p_restore':bool(a.get('restore'))})
        if not count:raise HwarangAuthError('변경 결과를 확인하지 못했습니다. 최신 기록을 확인해 주세요.')
        return {'ok':True}
    if op=='task':
        row=event(db,a['id'],own=True);title=str(a.get('title','')).strip()
        if not title or len(title)>200:raise ValueError('할 일을 200자 이내로 입력해 주세요.')
        body={'id':identity(a['seed']),'source':row['id'],'due':str(date.fromisoformat(a['due'])),'title':title}
        db.request('POST','sales_followups',body=body,prefer='resolution=ignore-duplicates')
        return {'ok':True}
    if op=='review':
        row=event(db,a['id'])
        if not db.me['managed'] or not db.members.get(row['owner'],{}).get('managed'):raise HwarangAuthError('피드백 작성 권한이 없습니다.')
        if row['revision']!=int(a['revision']):raise HwarangAuthError('일정이 변경됐습니다. 최신 일정을 확인해 주세요.')
        text=str(a.get('message','')).strip()
        if not text or len(text)>4000:raise ValueError('피드백을 1~4000자로 입력해 주세요.')
        db.request('POST','sales_reviews',body={'id':identity(a['seed']) if a.get('seed') else str(uuid5(NAMESPACE_URL,row['id']+db.uid+str(row['revision'])+text)),'event':row['id'],'revision':row['revision'],'message':text},prefer='resolution=ignore-duplicates')
        return {'ok':True}
    if op=='contract':
        row=event(db,a['event'],own=True);v=a['data'];old=None
        if a.get('id'):
            found=db.request('GET','sales_contracts',{'id':'eq.'+identity(a['id']),'owner':'eq.'+db.uid,'event':'eq.'+row['id'],'limit':'1'})
            if not found:raise HwarangAuthError('청약을 변경할 권한이 없습니다.')
            old={**found[0],'revision':int(a['revision'])}
        amount=int(v['amount']);day=date.fromisoformat(v['day']);effective=date.fromisoformat(v['effective']) if v['status']=='성립' and v.get('effective') else None
        if amount<=0:raise ValueError('보험료를 입력해 주세요.')
        if v['status']=='성립' and (not effective or effective<day):raise ValueError('성립일은 접수일 이후로 선택해 주세요.')
        if v['category'] not in ('인보험','일반보험','자동차보험') or v['payment'] not in ('월납','연납','일시납') or v['status'] not in ('청약 접수','심사 중','성립','철회','미성립'):raise ValueError('청약 항목을 확인해 주세요.')
        body={k:str(v.get(k,'')) for k in ('insurer','category','payment','status','product','note')}
        body.update(day=str(day),effective=str(effective) if effective else None,amount=amount,event=row['id'])
        if old:db.save('sales_contracts',body,old)
        else:
            body['id']=identity(a['seed']);db.request('POST','sales_contracts',body=body,prefer='resolution=ignore-duplicates')
        return {'ok':True}
    raise ValueError('지원하지 않는 요청입니다.')

def bootstrap(db,today,day,mode,team,member):
    first=day.replace(day=1); first-=first.weekday()*DAY
    people={u:r['label'] for u,r in db.branch.items()} if hasattr(db,'branch') else {r['member']:r['label'] for r in db.request('POST','rpc/sales_branch_members',body={})}
    catalog=json.loads((Path(__file__).resolve().parents[2]/'data/portal_catalog.json').read_text())
    return dict(access=json.dumps(db.members,sort_keys=True),ready=False,fast=bool(getattr(db,'fast_calendar',False)),uid=db.uid,managed=bool(db.me['managed']),people=people,members={u:r['label'] for u,r in db.members.items()} if db.me['managed'] else {},insurers=[r['name'] for r in catalog['insurers'] if r['group'] in ('생명보험','손해보험')],kinds=KINDS,day=str(day),today=str(today),mode=mode,team=team,member=member,events=[],roster={},rangeStart=str(first),rangeEnd=str(first+41*DAY),syncUnit=db.members[member]['unit'] if member else db.me['unit'],syncStamp=None,scopeLabel=db.members[member]['label'] if member else '지점 일정' if team else '내 일정')
