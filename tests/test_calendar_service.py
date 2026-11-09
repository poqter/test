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


def test_bootstrap_renders_before_event_queries(db):
 from datetime import date
 from modules.activity.calendar_service import bootstrap
 boot=bootstrap(db,date(2026,11,6),date(2026,11,6),'월간',False,None)
 assert boot['events']==[] and boot['ready'] is False
 assert ('GET','sales_events') not in st.session_state.get('fixture_reads',[])
 assert 'recent' not in boot
 with pytest.raises(ValueError):command(db,'recent',{'day':'2026-11-06'})

@pytest.mark.parametrize('editing', [False, True])
@pytest.mark.parametrize('mode,start,end,expected', [
 ('시간 지정','13:00','',('13:00:00',None)),
 ('시간 지정','13:00',None,('13:00:00',None)),
 ('시간 지정','13:00','14:00',('13:00:00','14:00:00')),
 ('시간 미정','','',(None,None)),
 ('종일','13:00','14:00',(None,None)),
])
def test_optional_times_are_nullable_on_create_and_edit(db,editing,mode,start,end,expected):
 a=payload(mode=mode,start=start,end=end)
 if editing:a.update(id=EVENT,revision=1)
 result=command(db,'save',a)
 row=next(r for r in st.session_state['fixture_events'] if r['id']==result['id'])
 assert (row['start_time'],row['end_time'])==expected
 assert row['time_pending']==(mode=='시간 미정')


def test_quick_complete_preserves_fields_and_undo(db):
 before=deepcopy(st.session_state['fixture_events'][0])
 result=command(db,'status',{'id':EVENT,'revision':1,'status':'완료'})
 current=st.session_state['fixture_events'][0]
 assert current['status']=='완료' and result['revision']==2
 assert all(current[k]==v for k,v in before.items() if k not in ('status','revision'))
 command(db,'status',{'id':EVENT,'revision':2,'status':'예정'})
 assert current['status']=='예정'

def test_quick_complete_rejects_other_owner_and_stale_undo(db):
 command(db,'status',{'id':EVENT,'revision':1,'status':'완료'})
 with pytest.raises(HwarangAuthError):command(db,'status',{'id':EVENT,'revision':1,'status':'예정'})
 assert st.session_state['fixture_events'][0]['status']=='완료'
 st.session_state['fixture_events'][0]['owner']=OTHER
 with pytest.raises(HwarangAuthError):command(db,'status',{'id':EVENT,'revision':2,'status':'예정'})

@pytest.mark.parametrize('raw,expected',[('9','09:00:00'),('930','09:30:00'),('14','14:00:00'),('1430','14:30:00'),('14:30','14:30:00')])
def test_auto_time(db,raw,expected):
 result=command(db,'save',payload(auto_time='1',start=raw,end=''))
 row=next(r for r in st.session_state['fixture_events'] if r['id']==result['id'])
 assert row['start_time']==expected and not row['time_pending']

@pytest.mark.parametrize('patch',[{'start':'25'},{'start':'1370'},{'start':'','end':'1500'}])
def test_invalid_auto_time(db,patch):
 with pytest.raises(ValueError):command(db,'save',payload(auto_time='1',**patch))

def test_move_preserves_fields_and_guards_owner_revision(db):
 before=deepcopy(st.session_state['fixture_events'][0])
 result=command(db,'move',{'id':EVENT,'revision':1,'day':'2026-11-10'})
 row=st.session_state['fixture_events'][0]
 assert row['day']=='2026-11-10'
 assert all(row[k]==v for k,v in before.items() if k not in ('day','revision'))
 with pytest.raises(HwarangAuthError):command(db,'move',{'id':EVENT,'revision':1,'day':before['day']})
 command(db,'move',{'id':EVENT,'revision':result['revision'],'day':before['day']})
 row['owner']=OTHER
 with pytest.raises(HwarangAuthError):command(db,'move',{'id':EVENT,'revision':row['revision'],'day':'2026-11-12'})

def test_feedback_crud_author_and_conflict(db):
 command(db,'review',{'id':EVENT,'revision':1,'message':'피드백'})
 r=st.session_state['fixture_reviews'][0]
 args={'id':EVENT,'review':r['id'],'version':1,'message':'수정'}
 r['reviewer']=OTHER
 with pytest.raises(HwarangAuthError):command(db,'review_edit',args)
 r['reviewer']=UID
 command(db,'review_edit',args)
 assert r['message']=='수정' and r['edit_version']==2
 with pytest.raises(HwarangAuthError):command(db,'review_delete',args)
 command(db,'review_delete',{**args,'version':2})
 assert command(db,'detail',{'id':EVENT})['reviews']==[]

def test_fp_branch_summary_has_title_without_detail_access(db,monkeypatch):
 db.me['managed']=False
 st.session_state['fixture_events'][0]['owner']=OTHER
 monkeypatch.setattr(db,'period',lambda *a,**k:[])
 data=command(db,'load',{'first':'2026-11-01','last':'2026-11-30','team':True})
 assert data['events'][0]['short'].startswith('상담 테스트')
 assert data['events'][0]['readable'] is False
