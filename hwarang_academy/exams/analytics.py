"""Explicit KST date windows and latest-per-person/per-subject exam metrics."""
from datetime import datetime, timezone, timedelta
KST=timezone(timedelta(hours=9))

def stamp(value):
    if not value:return None
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(KST)

def mode_label(row):
    return '오답 복습' if row.get('source_kind')=='review' else '모의시험' if row['mode']=='exam' else '자유학습'

def in_window(row,start,end):
    dt=stamp(row.get('submitted_at') or row.get('updated_at') or row['started_at'])
    return start<=dt.date()<=end

def latest_sections(rows):
    latest={}
    for r in sorted(rows,key=lambda x:x.get('submitted_at') or x['started_at'],reverse=True):
        if r['mode']!='exam' or r['status']!='submitted' or r.get('source_kind')=='review':continue
        for s in (r.get('result') or {}).get('sections',[]):
            latest.setdefault((r['user_id'],s['name']),s)
    return latest

def summarize(members,rows):
    ids={m['id'] for m in members};rows=[r for r in rows if r['user_id'] in ids]
    latest=latest_sections(rows);people=[]
    for m in members:
        mine=[r for r in rows if r['user_id']==m['id']]
        scores=[s for (uid,_),s in latest.items() if uid==m['id']]
        state='미참여' if not mine else '학습 중' if any(r['status']=='active' for r in mine) else '학습 완료'
        below=any(not s['passed'] for s in scores)
        people.append({**m,'attempts':mine,'scores':scores,'state':state,'below':below,
                       'last':max((r.get('updated_at') or r['started_at'] for r in mine),default=None)})
    by_subject={}
    for (_,name),s in latest.items():
        item=by_subject.setdefault(name,{'total':0,'passed':0});item['total']+=1;item['passed']+=int(s['passed'])
    return people,by_subject
