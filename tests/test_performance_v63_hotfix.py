from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_read_cache_helpers_are_present():
    source = (ROOT / "modules/shared/admin_center_ui.py").read_text(encoding="utf-8")
    assert "def _cached_admin_read(" in source
    assert "def _clear_admin_read_cache(" in source
    assert '_ADMIN_READ_CACHE_KEY = "hw_admin_read_cache_v1"' in source


def test_insurer_portal_renderer_is_present():
    source = (ROOT / "modules/resources/insurer_portal.py").read_text(encoding="utf-8")
    assert "def portal_grid(" in source
    assert 'PORTAL_CSS = """<style>' in source
    assert "portal_grid(rows)" in source
    assert "def _logo_cached(" in source
