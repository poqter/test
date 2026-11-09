from types import SimpleNamespace
from modules.activity import read_state

def setup(monkeypatch):
    state={'hwarang_auth':{'access_token':'token','profile':{'id':'one','role':'user'}}}
    monkeypatch.setattr(read_state,'st',SimpleNamespace(session_state=state))
    return state,SimpleNamespace(_reads={'events':[{'id':'a'}]})

def test_close_reuses_snapshot_once_without_sharing_mutable_rows(monkeypatch):
    state,db=setup(monkeypatch)
    read_state.remember(db)
    db._reads['events'][0]['id']='changed'
    read_state.resume()
    assert read_state.consume()=={'events':[{'id':'a'}]}
    assert read_state.consume() is None

def test_write_invalidates_background(monkeypatch):
    state,db=setup(monkeypatch)
    read_state.remember(db)
    read_state.invalidate()
    read_state.resume()
    assert read_state.consume() is None

def test_changed_identity_or_expired_snapshot_never_reused(monkeypatch):
    state,db=setup(monkeypatch)
    read_state.remember(db);read_state.resume()
    state['hwarang_auth']['profile']['role']='admin'
    assert read_state.consume() is None
    monkeypatch.setattr(read_state,'monotonic',lambda:0)
    read_state.remember(db);read_state.resume()
    monkeypatch.setattr(read_state,'monotonic',lambda:31)
    assert read_state.consume() is None

def test_typing_reuses_reads_but_date_change_and_expiry_clear(monkeypatch):
    state,db=setup(monkeypatch)
    monkeypatch.setattr(read_state,'monotonic',lambda:100)
    read_state.refresh(db,('reports','day1'))
    db._reads['report']='value'
    read_state.refresh(db,('reports','day1'))
    assert db._reads=={'report':'value'}
    read_state.refresh(db,('reports','day2'))
    assert not db._reads
    db._reads['report']='value'
    monkeypatch.setattr(read_state,'monotonic',lambda:116)
    read_state.refresh(db,('reports','day2'))
    assert not db._reads

def test_records_restore_cache_and_write_invalidate(monkeypatch):
    import importlib.util
    from modules.activity import center as original
    spec=importlib.util.spec_from_file_location("activity_records_under_test",original.__file__)
    center=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(center)
    state,db=setup(monkeypatch)
    state['hwarang_auth']['profile']['id']='one'
    monkeypatch.setattr(center,'st',SimpleNamespace(session_state=state,secrets={},query_params={}))
    calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path))
        if path.endswith('sales_calendar_context'):
            return {'members':[{'member':'one','managed':False}], 'branch':[]}
        return []
    monkeypatch.setattr(center,'SupabaseConfig',SimpleNamespace(from_mapping=lambda _:None))
    monkeypatch.setattr(center,'HwarangAuthService',lambda _:SimpleNamespace(_request=request,http=SimpleNamespace(headers={})))
    first=center.Records()
    first.request('GET','sales_events',{'limit':'10'})
    read_state.remember(first)
    read_state.resume()
    before=len(calls)
    second=center.Records()
    second.request('GET','sales_events',{'limit':'10'})
    assert len(calls)==before
    assert second._resumed
    read_state.remember(second)
    second.request('POST','sales_events',body={'title':'new'})
    read_state.resume()
    assert read_state.consume() is None
    second.request('GET','sales_events',{'limit':'10'})
    assert len(calls)==before+2


def test_manager_reuses_reads_until_ttl_or_scope_change(monkeypatch):
    state,db=setup(monkeypatch)
    clock=[0]
    monkeypatch.setattr(read_state,'monotonic',lambda:clock[0])
    context=('manager',read_state.identity(),'week','branch')
    read_state.refresh(db,context,seconds=15)
    db._reads['events']=[{'id':'saved'}]
    clock[0]=5
    read_state.refresh(db,context,seconds=15)
    assert db._reads['events']==[{'id':'saved'}]
    clock[0]=16
    read_state.refresh(db,context,seconds=15)
    assert not db._reads
    db._reads['events']=[{'id':'new'}]
    read_state.refresh(db,('manager','different_scope'),seconds=15)
    assert not db._reads
