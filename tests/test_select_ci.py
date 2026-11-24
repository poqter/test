import importlib.util
from pathlib import Path
import subprocess

spec = importlib.util.spec_from_file_location("select_ci", Path(__file__).resolve().parents[1] / ".github/scripts/select_ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

def test_unknown_and_critical_paths_run_everything():
    for path in ("modules/shared/permissions.py", "supabase/migrations/new.sql", ".github/workflows/briefing_checks.yml", "unclassified.py", "requirements.txt", "tests/test_foundation.py"):
        assert ci.select([path]) == set(ci.GROUPS)
    assert ci.select([]) == set(ci.GROUPS)
    assert ci.select(["modules/calculators/a.py"], force=True) == set(ci.GROUPS)

def test_selective_and_union():
    calc = ci.select(["modules/calculators/a.py"])
    assert calc == {"python", "operations", "pdf"}
    briefing = ci.select(["modules/briefing/scheduler.py"])
    assert briefing == {"python", "operations", "reader", "pdf"}
    assert ci.select(["modules/calculators/a.py", "modules/briefing/scheduler.py"]) == calc | briefing
    assert ci.select(["docs/HWARANG_MASTER_ROADMAP.md"]) == set()
    assert ci.select(["docs/HWARANG_MASTER_ROADMAP.md", "unknown"]) == set(ci.GROUPS)

def test_git_diff_includes_renamed_source_and_destination(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()
    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    (tmp_path / "critical.py").write_text("x = 1")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "docs").mkdir()
    git("mv", "critical.py", "docs/HWARANG_MASTER_ROADMAP.md")
    git("commit", "-m", "rename")
    head = git("rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    assert set(ci.changed_paths(base, head, "pull_request")) == {"critical.py", "docs/HWARANG_MASTER_ROADMAP.md"}
    assert ci.select(ci.changed_paths(base, head, "push")) == set(ci.GROUPS)
