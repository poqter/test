"""Deterministic editorial checks. No model requests and no public audit data."""
import re


def text_key(value):
    return re.sub(r'[^0-9a-z가-힣]', '', str(value).lower())


def remove_unchanged_repeats(rows, previous):
    for row in rows:
        same = next((old for old in previous if
                     (old.get('event_key') == row.event_key or text_key(old.get('title')) == text_key(row.title))
                     and text_key(old.get('summary')) == text_key(row.summary)), None)
        row.profile_payload['prior_day_check'] = 'unchanged' if same else 'new_or_updated'
        if same:
            row.selection_tier = 'excluded'
            row.profile_payload['selection_decision'] = 'unchanged_prior_day'


def verified_extras(rows, phase_b, profile):
    """Optional dated weather and official schedules; no guessed values or times."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    kst=ZoneInfo('Asia/Seoul'); day=phase_b.as_of.astimezone(kst).date()
    events={e.event_key:e for e in phase_b.events}
    weather=[]; calendar=[]
    for row in rows:
        if row.validation_status!='ok' or row.profile_payload.get('essential_facts_complete') is not True:
            continue
        sources=[c for c in events[row.event_key].candidates if c.source_kind=='official'
                 and c.published_at and c.published_at<=phase_b.as_of]
        if not sources: continue
        item={'title':row.title,'summary':row.summary,'sources':[{'url':c.canonical_url or c.url,
              'source_name':c.source_name,'published_at':c.published_at.isoformat()} for c in sources[:2]]}
        if profile=='NEWS' and row.profile_payload.get('editorial_kind')=='weather' and row.profile_payload.get('event_date')==str(day):
            weather.append(item)
        if profile=='MARKET' and row.profile_payload.get('scheduled_at'):
            try:
                instant=datetime.fromisoformat(row.profile_payload['scheduled_at'].replace('Z','+00:00'))
                if instant.tzinfo and instant>phase_b.as_of and instant.astimezone(kst).date()==day:
                    calendar.append({**item,'scheduled_at':instant.astimezone(kst).isoformat()})
            except (ValueError,TypeError):pass
    return {'weather':weather[:1], 'calendar':sorted(calendar,key=lambda r:r['scheduled_at'])[:3]}
