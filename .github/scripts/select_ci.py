"""Conservative CI selection. Unknown paths and unavailable diffs select all."""
import os
import subprocess
from pathlib import Path

GROUPS = ("python", "operations", "activity", "pdf", "academy", "kakao", "reader", "keepalive")
# Only narrow, audited source roots are selective; everything else fails closed.
RULES = {
    "modules/calculators/": {"python", "operations", "pdf"},
    "data/calculator": {"python", "operations", "pdf"},
    "FINANCIAL_CALCULATORS_CATALOG.json": {"python", "operations", "pdf"},
    "modules/briefing/": {"python", "operations", "reader", "pdf"},
    "public_reader/": {"python", "reader"},
    "modules/activity/": {"python", "operations", "activity", "kakao", "academy"},
    "android/calendar-widget/": {"python", "activity"},
}
DOCS = {"docs/HWARANG_MASTER_ROADMAP.md", "docs/HWARANG_PROJECT_CHECKPOINT.md"}

def select(paths, force=False):
    if force or not paths:
        return set(GROUPS)
    selected = set()
    for path in paths:
        if path in DOCS:
            continue
        match = next((groups for prefix, groups in RULES.items()
                      if (path.startswith(prefix) if prefix.endswith("/") or prefix == "data/calculator"
                          else path == prefix)), None)
        if match is None:
            return set(GROUPS)
        selected.update(match)
    return selected

def changed_paths(base, head, event):
    if not base or not head or set(base) == {"0"}:
        raise ValueError("missing comparison ref")
    # --no-renames captures both paths for renames; -z handles unusual filenames.
    span = f"{base}...{head}" if event == "pull_request" else f"{base}..{head}"
    raw = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z", span, "--"])
    return [p.decode("utf-8", errors="strict") for p in raw.split(b"\0") if p]

def main():
    event = os.environ.get("CI_EVENT", "")
    try:
        paths = changed_paths(os.environ.get("CI_BASE"), os.environ.get("CI_HEAD"), event)
        groups = select(paths, force=event not in {"pull_request", "push"})
    except (OSError, ValueError, subprocess.SubprocessError):
        groups = set(GROUPS)
    with open(os.environ["GITHUB_OUTPUT"], "a") as out:
        for name in GROUPS:
            print(f"{name}={'true' if name in groups else 'false'}", file=out)
        print(f"any={'true' if groups else 'false'}", file=out)
        print(f"node={'true' if groups & {'academy', 'activity', 'kakao', 'reader'} else 'false'}", file=out)
        print(f"browser={'true' if groups else 'false'}", file=out)
    print("Selected groups:", ", ".join(sorted(groups)) or "documentation only")

if __name__ == "__main__":
    main()
