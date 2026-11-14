import copy
import pytest
from modules.shared import operations as o


def sample(**kwargs):
    run=dict(id=12,workflow_id=3,run_attempt=1,name='Activity browser',status='completed',conclusion='failure',head_sha='a'*40,html_url='https://github.com/poqter/test/actions/runs/12',created_at='2026-11-14T00:00:00Z',updated_at='2026-11-14T00:01:00Z')
    run.update(kwargs)
    return o.run_issue(run)


def test_failure_is_not_claimed_user_error():
    issue=sample()
    assert issue['result']=='실패' and issue['impact']=='영향 미확인'
    assert '원인 미확정'==issue['classification']
    assert o.state('completed','skipped')=='미실행'
    assert o.state('completed','cancelled')!='통과'


@pytest.mark.parametrize('scope',o.SCOPES)
def test_request_scope_preserves_policy(scope):
    text=o.request_text([sample()],scope)
    assert '최신 적용본' in text and '실제 기능 오류' in text
    if scope==o.SCOPES[0]: assert '코드·DB 수정이나 배포는 하지' in text
    if scope==o.SCOPES[1]: assert '운영 반영·배포를 진행하지' in text
    if scope==o.SCOPES[2]: assert '운영 배포와 결과 확인까지' in text


def test_redaction():
    raw='password=foo\ntoken=secret\na@b.com 010-1234-5678 901231-1234567 ghp_abc123 https://a.test/a?secret=x'
    cleaned=o.redact(raw)
    for bad in ['foo','secret','a@b.com','010-1234','901231','ghp_abc']: assert bad not in cleaned


class Auth:
    def __init__(self,allowed=True):self.allowed=allowed;self.rows=[];self.calls=[]
    def _require_super_admin(self,actor):
        if not self.allowed:raise PermissionError()
    def _request(self,method,path,**kwargs):
        self.calls.append((method,path,kwargs))
        if method=='POST':
            self.rows.append(dict(id=len(self.rows)+1,created_at=o.now(),**copy.deepcopy(kwargs['json'])))
            return self.rows[-1:]
        req=kwargs.get('params',{}).get('details->>request_id','eq.')[3:]
        return [r for r in self.rows if r['details']['request_id']==req] if req else self.rows


def test_review_denies_nonadmin_before_read_write():
    auth=Auth(False)
    with pytest.raises(PermissionError):o.review_history(auth,'user')
    with pytest.raises(PermissionError):o.save_review(auth,'user',sample(),'확인 중',{},'','req')
    assert not auth.calls


def test_review_is_append_only_and_reconciles_retry():
    auth=Auth();issue=sample();checks={c:True for c in o.CHECKS}
    o.save_review(auth,'admin',issue,'검토 완료',checks,'확인','req')
    o.save_review(auth,'admin',issue,'검토 완료',checks,'확인','req')
    assert len(auth.rows)==1
    assert issue['result']=='실패'
    assert all(path=='/rest/v1/hwarang_admin_audit_log' for _,path,_ in auth.calls)
    with pytest.raises(ValueError):o.save_review(auth,'admin',issue,'검토 완료',{},'','req2')


def test_new_evidence_changes_review_identity():
    assert sample()['evidence']!=sample(run_attempt=2)['evidence']


def test_old_briefing_is_not_automatically_called_failed():
    result=o.briefing_issues({'jobs':[],'publications':[{'profile_code':'NEWS','briefing_date':'2020-01-01','current_published_revision_id':'x'}]})
    assert result[0]['result']=='확인 필요'


def test_ui_review_and_request_scopes():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('operations_harness.py'))).run()
    assert not app.exception
    assert '운영 반영·배포를 진행하지' in next(x.value for x in app.text_area if x.label=='요청문 미리보기')
    next(s for s in app.selectbox if s.label=='요청 범위').set_value(o.SCOPES[2]).run()
    assert not app.exception
    assert '운영 배포와 결과 확인까지' in next(x.value for x in app.text_area if x.label=='요청문 미리보기')
    for checkbox in app.checkbox:checkbox.check()
    next(s for s in app.selectbox if s.label=='점검 상태').set_value('검토 완료')
    next(b for b in app.button if b.label=='점검 기록 저장').click().run()
    assert not app.exception and any('저장했습니다' in x.value for x in app.success)
    assert app.session_state['test_reviews'][0]['details']['status']=='검토 완료'
    assert any('실패' in x.value for x in app.markdown)


def test_schedule_is_kst_and_future():
    from datetime import datetime,timezone
    rows=o.schedules(datetime(2026,11,14,0,0,tzinfo=timezone.utc))
    assert rows and all('KST' in r['다음 예정 (KST)'] for r in rows)


def test_batch_request_not_silently_truncated():
    issues=[dict(sample(),fact='확인 내용'*1000) for _ in range(6)]
    assert o.request_text(issues).endswith('별도 승인을 받아줘.')


def test_step_area_uses_context_without_install_false_positive():
    assert o.area('Run python -m pip install requests briefing')=='검사 환경 준비'
    assert o.area('Run daily operation briefing')=='브리핑'
    assert o.area('check_install.py')=='홈 화면 설치'

def test_detail_refresh_updates_request_preview():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('operations_harness.py'))).run()
    next(b for b in app.button if b.label=='단계별 근거 불러오기').click().run()
    assert not app.exception
    text=next(x.value for x in app.text_area if x.label=='요청문 미리보기')
    assert 'tests/example.py' in text and 'Mobile browser' in text


def test_ui_navigation_filters_and_batch_preserve_selected_evidence():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('operations_harness.py'))).run()
    assert app.session_state['ops_selected']=='github:7'
    next(b for b in app.button if b.key=='ops_pick:github:7').click().run()
    assert app.session_state['ops_mobile_detail']
    next(b for b in app.button if b.label=='← 문제 목록').click().run()
    assert not app.session_state['ops_mobile_detail']
    next(s for s in app.selectbox if s.label=='표시할 항목').set_value('전체').run()
    next(b for b in app.button if b.key=='ops_pick:github:8').click().run()
    assert app.session_state['ops_selected']=='github:8'
    text=next(x.value for x in app.text_area if x.label=='요청문 미리보기')
    assert 'Foundation checks' in text and '[문제 github:8]' in text
    app.multiselect[0].set_value(['github:7','github:8']).run()
    assert not app.exception
    assert any('[문제 github:7]' in c.value and '[문제 github:8]' in c.value for c in app.code)
    next(b for b in app.button if b.label=='최신 상태 조회').click().run()
    assert not app.exception and app.session_state['ops_selected']=='github:8'
