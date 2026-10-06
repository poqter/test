from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "modules/shared/admin_center_ui.py").read_text(encoding="utf-8")


def test_dashboard_recent_section_is_login_only():
    assert 'event_code": "eq.LOGIN_SUCCESS"' in SOURCE
    assert '<div class="hw-section-head">최근 로그인</div>' in SOURCE
    assert '최근 로그인 · 활동' not in SOURCE
    assert '"로그인 앱"' in SOURCE


def test_global_activity_nav_removed_but_user_detail_activity_kept():
    assert '("activity", "활동 기록")' not in SOURCE
    assert '"activity": "활동 기록"' not in SOURCE
    assert 'def _user_activity(' in SOURCE
    assert '[7, 30, 90]' in SOURCE
    assert 'created_at": f"gte.{since}"' in SOURCE
