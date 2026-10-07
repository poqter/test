from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "modules/shared/admin_center_ui.py").read_text(encoding="utf-8")


def test_dashboard_recent_section_is_login_only():
    assert 'LOGIN_SUCCESS' in SOURCE
    assert '<div class="hw-section-head">최근 로그인</div>' in SOURCE
    assert '최근 로그인 · 활동' not in SOURCE
    assert '"로그인 앱"' in SOURCE


def test_general_user_activity_history_is_not_rendered():
    assert '("activity", "활동 기록")' not in SOURCE
    assert '"activity": "활동 기록"' not in SOURCE
    assert 'def _user_activity(' not in SOURCE
    assert 'LOGIN_SUCCESS' in SOURCE
