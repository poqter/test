from pathlib import Path

TASK_THEME = Path(__file__).resolve().parents[1] / "modules" / "shared" / "task_theme.py"
APP = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = TASK_THEME.read_text(encoding="utf-8")
APP_SOURCE = APP.read_text(encoding="utf-8")


def test_sidebar_reopen_control_keeps_header_interactive():
    assert '[data-testid="stHeader"]{' in SOURCE
    assert 'height:48px!important' in SOURCE
    assert 'min-height:48px!important' in SOURCE
    assert 'pointer-events:auto!important' in SOURCE
    assert 'overflow:visible!important' in SOURCE
    assert '[data-testid="stSidebarCollapsedControl"]' in SOURCE
    assert '[data-testid="stExpandSidebarButton"]' in SOURCE
    assert '[data-testid="stSidebarCollapseButton"]' in SOURCE


def test_workspace_recovers_with_expanded_sidebar_on_new_mount():
    assert 'initial_sidebar_state="expanded"' in APP_SOURCE
