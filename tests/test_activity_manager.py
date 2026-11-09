from datetime import date, datetime
from modules.activity.manager import required_days, summarize
from test_activity_redesign import app, button


def test_summary_uses_authorized_members_unique_submissions_and_elapsed_weekdays():
    start,end,today=date(2026,11,2),date(2026,11,8),date(2026,11,4)
    event=dict(id='e',owner='a',day='2026-11-03',kind='AP',status='완료',help='지원')
    report=dict(id='r',owner='a',day='2026-11-02',period='일일',submitted=True,data={})
    rows=summarize({'a':{'label':'직원'}},[event,dict(event,id='deleted',deleted_at='now'),dict(event,id='outside',owner='b'),dict(event,id='pending',status='예정',help='')],
        [report,dict(report,id='duplicate'),dict(report,day='2026-11-05'),dict(report,day='2026-11-03',submitted=False)],[],
        [dict(owner='a',due='2026-11-03',scheduled=None),dict(owner='a',due='2026-11-03',scheduled='done')],start,end,today,datetime(2026,11,4,12))
    assert len(rows)==1
    r=rows[0]
    assert (r['submitted'],r['required'],r['unsubmitted'])==(1,3,2)
    assert (r['counts']['AP'],r['help'],r['missing'],r['late'])==(1,1,1,1)
    assert required_days(start,end,date(2026,11,1))==[]
    assert len(required_days(start,end,date(2026,11,8)))==5
    assert required_days(end,end,end)==[end]


def test_member_week_navigation_and_weekends_do_not_expand_daily_rows():
    at=app('redesign.member_detail(FakeRecords(),UID,date(2026,11,6),"주간")')
    assert not at.exception
    dates=next(c for c in at.segmented_control if c.label=='날짜 선택')
    assert len(dates.options)==5
    next(t for t in at.toggle if t.label=='주말 포함').set_value(True).run()
    assert not at.exception
    assert len(next(c for c in at.segmented_control if c.label=='날짜 선택').options)==7
    button(at,'›').click().run()
    assert not at.exception
    assert next(d for d in at.date_input if d.label=='조회 기준일').value==date(2026,11,13)
    next(t for t in at.toggle if t.label=='주말 포함').set_value(False).run()
    assert not at.exception
    assert len(next(c for c in at.segmented_control if c.label=='날짜 선택').options)==5


def test_manager_summary_filters_and_member_permission():
    at=app('st.session_state.setdefault("sales_menu","구성원 현황")\ncenter.run()')
    next(c for c in at.segmented_control if c.label=='표시').set_value('지원 요청').run()
    assert not at.exception
    assert any('조건에 맞는 구성원' in i.value for i in at.info)
    denied=app('redesign.member_detail(FakeRecords(),"not-in-scope",date(2026,11,6),"주간")')
    assert not denied.exception
    assert any('조회 권한' in e.value for e in denied.error)


def test_manager_paginates_large_teams_and_search_resets_page():
    at=app('''class LargeTeam(FakeRecords):
    def __init__(self):
        super().__init__()
        self.members.update({f"extra-{i}":{"label":f"추가 직원 {i}","unit":"unit","managed":False} for i in range(60)})
center.Records=LargeTeam
st.session_state.setdefault("sales_menu","구성원 현황")
center.run()
''')
    assert not at.exception
    assert len([b for b in at.button if b.key and b.key.startswith('member_open_')])==25
    next(s for s in at.selectbox if s.label=='목록 페이지').set_value(3).run()
    assert not at.exception
    assert len([b for b in at.button if b.key and b.key.startswith('member_open_')])==12
    next(t for t in at.text_input if t.label=='직원 이름 검색').input('테스트 작성자').run()
    assert not at.exception
    assert len([b for b in at.button if b.key and b.key.startswith('member_open_')])==1
