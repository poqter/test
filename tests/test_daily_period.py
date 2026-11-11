from datetime import date
from types import SimpleNamespace
from copy import deepcopy
from modules.activity.period_summary import daily_rows, totals, date_table, period_bounds
from modules.activity import center as original
import importlib.util
spec=importlib.util.spec_from_file_location('period_records_under_test',original.__file__)
center=importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)


def test_source_deduplicates_and_excludes_drafts_legacy_and_outside_scope():
    rows=[dict(id='a',owner='one',day='2026-11-02',period='일일',submitted=True,revision=1,data={'counts':{'AP':2}})]
    rows += [dict(rows[0],revision=2,data={'counts':{'AP':3}}),dict(rows[0],period='주간',data={'counts':{'AP':99}}),dict(rows[0],owner='two'),dict(rows[0],submitted=False)]
    assert totals(daily_rows(rows,date(2026,11,1),date(2026,11,30),{'one'}))['AP']==3
    data=date_table(rows,date(2026,11,1),date(2026,11,3),{'one':{}},date(2026,11,2))
    assert [r['제출'] for r in data]==['0/1명','1/1명','예정']
    assert period_bounds(date(2026,2,25),'월간')==(date(2026,2,1),date(2026,2,28))


def test_twenty_sessions_reuse_unchanged_data_and_fetch_only_after_change(monkeypatch):
    calls=[]
    state={}
    monkeypatch.setattr(center,'st',SimpleNamespace(session_state=state))
    version=['v1']
    for uid in range(20):
        state.clear()
        db=object.__new__(center.Records)
        db.uid=str(uid);db.view_scope='daily';db.members={str(uid):{'label':str(uid)}}
        def request(method,path,body=None):
            calls.append(path)
            return version[0] if path.endswith('_stamp') else {'stamp':version[0],'reports':[],'events':[],'contracts':[]}
        db.request=request
        for _ in range(3):db.activity_bundle(date(2026,11,1),date(2026,11,30))
        version[0]='v2'
        db.activity_bundle(date(2026,11,1),date(2026,11,30))
        version[0]='v1'
    assert calls.count('rpc/sales_activity_bundle')==40
    assert calls.count('rpc/sales_activity_stamp')==60


def test_cached_period_cannot_escape_owner_or_date(monkeypatch):
    db=object.__new__(center.Records)
    db._activity_bundle=('2026-11-01','2026-11-30','one',{'reports':[{'owner':'one','day':'2026-11-02'}]})
    calls=[]
    db.request=lambda *args:calls.append(args) or []
    assert db.period('sales_reports',date(2026,11,2),date(2026,11,2),owner='eq.one')
    assert not db.period('sales_reports',date(2026,11,2),date(2026,11,2),owner='eq.two')
    assert not db.period('sales_reports',date(2026,12,2),date(2026,12,2),owner='eq.one')
    assert len(calls)==2
