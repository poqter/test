"""Small, secret-free build and failure diagnostics for manager-only downloads."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ENGINE_VERSION = "1.10.0-launch"
DIAGNOSTIC_SCHEMA = "briefing-daily-diagnostics-v4"


def release_matches(actual: dict[str, str], manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    expected = manifest.get("briefing_code_sha256") or {}
    if not isinstance(expected, dict):
        expected = {}
    mismatch = sorted(name for name in set(actual) | set(expected) if actual.get(name) != expected.get(name))
    return bool(expected) and not mismatch and manifest.get("engine_version") == ENGINE_VERSION, mismatch


@lru_cache(maxsize=1)
def build_info() -> dict[str, Any]:
    root = Path(__file__).parent
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}
    try:
        manifest = json.loads((root.parents[1] / "STAGE1_CHANGED_FILES.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            manifest = {}
    except (OSError, ValueError):
        manifest = {}
    matches, mismatch = release_matches(actual, manifest)
    return {"engine_version": ENGINE_VERSION, "code_sha256": actual,
            "code_matches_release": matches, "mismatched_files": mismatch,
            "release_manifest_version": manifest.get("engine_version")}


def failure_diagnostic(exc: Exception) -> dict[str, Any]:
    details = getattr(exc, "diagnostics", {})
    return {"schema_version": DIAGNOSTIC_SCHEMA, **build_info(), "status": "failed",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "failure_message": str(exc)[:500],
            "diagnostics": details if isinstance(details, dict) else {},
            "note": "응답이 없거나 실패한 요청도 과금되었을 수 있습니다. 진단의 관측 사용량은 실제 청구액이 아닙니다. 추가 생성 전 이 결과를 검토합니다."}
