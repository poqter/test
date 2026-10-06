from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "modules/shared/task_theme.py").read_text(encoding="utf-8")


def test_header_layer_keeps_sidebar_reopen_control_unclipped():
    assert '[data-testid="stHeader"]{height:48px!important;min-height:48px!important' in SOURCE
    assert '[data-testid="stSidebarCollapsedControl"]' in SOURCE
    assert '[data-testid="stExpandSidebarButton"]' in SOURCE
    assert 'z-index:10050!important' in SOURCE
    assert 'width:40px!important;height:40px!important' in SOURCE
