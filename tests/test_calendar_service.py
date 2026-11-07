"""Command-boundary regression: authorisation, conflict and retry behaviour."""
from copy import deepcopy
import pytest
import streamlit as st
from activity_fixture import FakeRecords, UID, OTHER, EVENT
from modules.activity.calendar_service import command
from modules.shared.hwarang_auth import HwarangAuthError

@pytest.fixture
def db(monkeypatch):
 monkeypatch.setattr(st,'session_state',{})
 return FakeRecords()

def payload(**changes):
 return {'seed':'44444444-4444-4444-8444-444444444444','data':dict(day='2026-11-09',title='새 일정',kind='TA',mode='시간 미정',place='',note='',companion=None,support=False,common=False,status='예정',result='') | changes}

def test_repeat_retry_is_idempotent(db):
 a=payload(repeat=True,repeats=3)
 one=command(db,'save',a);two=command(db,'save',a)
 assert one==two
 rows=st.session_state['fixture_events']
 assert len(rows)==4
 assert [r['day'] for r in rows[1:]]==['2026-11-09','2026-11-16','2026-11-23']
 assert len({r['series_id'] for r in rows[1:]})==1

def test_revision_conflict_does_not_overwrite(db):
 a=payload();a.update(id=EVENT,revision=0)
 before=deepcopy(st.session_state['fixture_events'])
 with pytest.raises(HwarangAuthError):command(db,'save',a)
 assert st.session_state['fixture_events']==before

def test_cannot_write_another_person(db):
 st.session_state['fixture_events'][0]['owner']=OTHER
 for op,args in [('save',dict(payload(),id=EVENT,revision=1)),('archive',{'id':EVENT,'revision':1}),('task',{'id':EVENT,'seed':'44444444-4444-4444-8444-444444444444','title':'x','due':'2026-11-09'})]:
  with pytest.raises(HwarangAuthError):command(db,op,args)

def test_scope_is_validated_on_server(db):
 db.me['managed']=False
 with pytest.raises(HwarangAuthError):command(db,'load',{'first':'2026-11-01','last':'2026-11-30','member':OTHER})
 with pytest.raises(HwarangAuthError):command(db,'save',payload(common=True))
 with pytest.raises(ValueError):command(db,'load',{'first':'2026-01-01','last':'2026-11-30'})

def test_overlap_requires_matching_confirmation(db):
 a=payload();a['data'].update(day='2026-11-06',mode='시간 지정',start='14:00',end='15:00')
 response=command(db,'save',a);assert response['overlap'];assert len(st.session_state['fixture_events'])==1
 a['overlap']=response['overlap'];assert command(db,'save',a)['id'];assert len(st.session_state['fixture_events'])==2

def test_deleted_event_cannot_be_edited(db):
 command(db,'archive',{'id':EVENT,'revision':1})
 with pytest.raises(HwarangAuthError):command(db,'save',dict(payload(),id=EVENT,revision=1))
 command(db,'archive',{'id':EVENT,'revision':2,'restore':True})
 assert st.session_state['fixture_events'][0]['deleted_at'] is None

def test_data_validation(db):
 for patch in [{'title':''},{'mode':'시간 지정','start':'15:00','end':'14:00'},{'repeat':True,'repeats':53},{'follow':'2026-11-01'}]:
  a=payload();a['data'].update(patch)
  with pytest.raises(ValueError):command(db,'save',a)
 assert len(st.session_state['fixture_events'])==1

def test_feedback_permission_and_revision(db):
 db.me['managed']=False
 with pytest.raises(HwarangAuthError):command(db,'review',{'id':EVENT,'revision':1,'message':'확인'})
 db.me['managed']=True
 with pytest.raises(HwarangAuthError):command(db,'review',{'id':EVENT,'revision':0,'message':'확인'})
 command(db,'review',{'id':EVENT,'revision':1,'message':'확인'})
 assert st.session_state['fixture_writes'][-1]['revision']==1

def test_follow_task_and_contract_fields(db):
 seed='44444444-4444-4444-8444-444444444444'
 command(db,'task',{'id':EVENT,'seed':seed,'title':'후속 확인','due':'2026-11-09'})
 assert st.session_state['fixture_writes'][-1]['source']==EVENT
 v={'day':'2026-11-06','insurer':'테스트 보험사','category':'인보험','payment':'월납','amount':120000,'status':'성립','effective':'2026-11-09','product':'테스트 상품','note':'검증'}
 command(db,'contract',{'event':EVENT,'seed':seed,'data':v})
 saved=st.session_state['fixture_writes'][-1]
 assert saved['event']==EVENT and saved['amount']==120000 and saved['effective']=='2026-11-09'
 with pytest.raises(ValueError):command(db,'contract',{'event':EVENT,'seed':seed,'data':dict(v,effective='2026-11-01')})
 st.session_state['fixture_events'][0]['owner']=OTHER
 with pytest.raises(HwarangAuthError):command(db,'contract',{'event':EVENT,'seed':seed,'data':v})
