from datetime import time
from pathlib import Path
import sys
from streamlit.testing.v1 import AppTest
from modules.activity.ux import copy_event, shifted_end, refreshed_counts, report_totals, schedule_time

ROOT=Path(__file__).resolve().parents[1]
BASE=f'''import sys
sys.path.insert(0,{str(ROOT)!r})
sys.path.insert(0,{str(ROOT / "tests")!r})
import streamlit as st
from datetime import date
from activity_fixture import FakeRecords, UID, EVENT
from modules.activity import center, redesign
st.session_state.setdefault("hwarang_auth",{{"profile":{{"id":UID,"position_code":"team_leader","role":"user"}}}})
center.Records=FakeRecords
'''

def app(tail):return AppTest.from_string(BASE+tail,default_timeout=20).run()
def button(at,label):return next(b for b in at.button if b.label==label)
def text(at,label):return next(t for t in at.text_area if t.label==label)
def number(at,label):return next(n for n in at.number_input if n.label==label)

def test_copy_excludes_identity_results_and_links():
    row={"id":"secret","owner":"someone","case_id":"case","previous_event":"parent","result":"done","help":"support","common":True,"status":"완료","title":"상담","place":"지점"}
    copied=copy_event(row)
    assert not set(("id","owner","case_id","previous_event")) & copied.keys()
    assert copied["title"]=="상담" and copied["status"]=="예정" and not copied["result"] and not copied["common"]

def test_duration_and_overnight_validation():
    assert shifted_end(time(14),time(16),time(15))==time(17)
    assert shifted_end(time(14),time(23,30),time(15)) is None
    assert shifted_end(None,time(16),None) is None
    assert schedule_time({"time_pending":True})=="시간 미정"
    assert schedule_time({})=="종일"

def test_refresh_is_idempotent_and_week_only_submitted():
    counts={"상담":5};sources={"a":"상담"};current={"a":"상담","b":"상담"}
    result=refreshed_counts(counts,sources,current,["상담"])
    assert result=={"상담":6}
    assert refreshed_counts(result,current,current,["상담"])==result
    assert report_totals([{"submitted":False,"data":{"counts":{"상담":99}}},{"submitted":True,"data":{"counts":{"상담":2}}}],["상담"])=={"상담":2}

def test_daily_keeps_manual_input_and_saves_all_fields():
    at=app('redesign.reports(FakeRecords(),date(2026,11,6),"일일")')
    assert not at.exception
    number(at,"상담").set_value(7).run()
    text(at,"주요 성과 · 진행사항").input("직접 입력한 활동").run()
    assert number(at,"상담").value==7
    button(at,"임시 저장").click().run()
    assert not at.exception
    saved=at.session_state["fixture_reports"][0]
    assert saved["data"]["counts"]["상담"]==7 and saved["data"]["note"]=="직접 입력한 활동"
    assert saved["submitted"] is False

def test_weekly_daily_roundtrip_retains_week_draft():
    at=app('st.session_state.setdefault("sales_menu","주간 기록")\ncenter.run()')
    assert not at.exception
    text(at,"주요 성과 · 진행사항").input("주간 작성 중").run()
    button(at,"미제출 · 작성하기").click().run()
    assert not at.exception
    # Daily modal and weekly background each have one note field.
    at.text_area[-1].input("일일 추가 기록").run()
    # Use last draft button (dialog) rather than background weekly draft.
    [b for b in at.button if b.label=="임시 저장"][-1].click().run()
    assert not at.exception
    assert text(at,"주요 성과 · 진행사항").value=="주간 작성 중"
    assert not at.session_state.get("sales_route")

def test_event_edit_preserves_duration_and_revision():
    at=app('st.session_state.setdefault("sales_route",{"type":"edit","id":EVENT})\ncenter.run()')
    assert not at.exception
    next(t for t in at.time_input if t.label=="시작 시간").set_value(time(16)).run()
    assert next(t for t in at.time_input if t.label=="종료 시간 · 선택").value==time(17)
    button(at,"변경 저장").click().run()
    assert not at.exception
    assert at.session_state["fixture_events"][0]["start_time"]=="16:00:00"
    assert at.session_state["fixture_events"][0]["revision"]==2

def test_overview_and_member_detail_render():
    at=app('st.session_state.setdefault("sales_menu","구성원 현황")\ncenter.run()')
    assert not at.exception
    button(at,"테스트 구성원 ›").click().run()
    assert not at.exception
    assert any(s.value=="테스트 구성원" for s in at.subheader)

def test_event_conflict_keeps_input_and_does_not_write():
    at=app('st.session_state.setdefault("fixture_conflict",True)\nst.session_state.setdefault("sales_route",{"type":"edit","id":EVENT})\ncenter.run()')
    next(t for t in at.text_input if t.label=="고객 또는 일정명").input("수정 중인 제목").run()
    button(at,"변경 저장").click().run()
    assert not at.exception and at.error
    at.run()
    assert next(t for t in at.text_input if t.label=="고객 또는 일정명").value=="수정 중인 제목"
    assert not at.session_state["fixture_writes"]

def test_dirty_date_switch_keeps_previous_until_confirmed():
    at=app('redesign.reports(FakeRecords(),date(2026,11,6),"일일")')
    text(at,"주요 성과 · 진행사항").input("보존할 내용").run()
    at.date_input[0].set_value(__import__('datetime').date(2026,11,5)).run()
    assert at.warning and text(at,"주요 성과 · 진행사항").value=="보존할 내용"
    button(at,"계속 작성").click().run()
    assert at.date_input[0].value==__import__('datetime').date(2026,11,6)
    assert text(at,"주요 성과 · 진행사항").value=="보존할 내용"

def test_daily_submit_requires_confirmation():
    at=app('redesign.reports(FakeRecords(),date(2026,11,6),"일일")')
    button(at,"기록 제출").click().run()
    assert not at.session_state["fixture_writes"]
    button(at,"제출 확인").click().run()
    assert not at.exception and at.session_state["fixture_reports"][0]["submitted"]

def test_mobile_reference_path_and_fields_render():
    at=app('original=redesign.ux.compact\nredesign.ux.compact=lambda:True\ntry: redesign.reports(FakeRecords(),date(2026,11,6),"일일")\nfinally: redesign.ux.compact=original')
    assert not at.exception
    assert len(at.number_input)>=8
    assert any(e.proto.popover.label=="오늘 일정 참고" for e in at.get("popover"))
