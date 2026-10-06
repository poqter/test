from __future__ import annotations

from dataclasses import dataclass, asdict
import os
from typing import Any
from urllib.parse import urlparse

from .config import (
    DISCOVERY_LANES,
    SHARED_DISCOVERY_HARD_LIMIT,
    SHARED_DISCOVERY_SOFT_LIMIT,
    SHARED_DISCOVERY_TARGET,
)
from .direct_sources import DirectSourceSpec, load_direct_source_specs_from_env
from .diagnostics import build_info


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    code: str
    ok: bool
    required: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _valid_direct_source(spec: DirectSourceSpec) -> bool:
    parsed = urlparse(spec.url)
    return (
        parsed.scheme in {"https", "http"}
        and bool(parsed.netloc)
        and ".example" not in parsed.netloc.lower()
        and bool(spec.source_code.strip())
        and bool(spec.source_name.strip())
    )


def run_runtime_preflight(*, direct_sources: list[DirectSourceSpec] | None = None, require_direct_sources: bool = True) -> list[PreflightCheck]:
    """Validate Phase B live-smoke prerequisites without calling OpenAI or source URLs."""
    if direct_sources is None:
        try:
            direct_sources = load_direct_source_specs_from_env()
            direct_source_parse_ok = True
        except (KeyError, TypeError, ValueError):
            direct_sources = []
            direct_source_parse_ok = False
    else:
        direct_source_parse_ok = True

    integrity_ok = bool(build_info()["code_matches_release"])
    checks = [
        PreflightCheck("deployment_integrity", integrity_ok, True,
                       "배포 파일이 수정 패키지와 일치합니다" if integrity_ok
                       else "배포 파일이 수정 패키지와 일치하지 않습니다. 새 파일과 STAGE1_CHANGED_FILES.json을 함께 적용하고 앱을 다시 시작하세요."),
        PreflightCheck(
            "supabase_url",
            _present("SUPABASE_URL"),
            True,
            "SUPABASE_URL configured" if _present("SUPABASE_URL") else "SUPABASE_URL is missing",
        ),
        PreflightCheck(
            "supabase_secret",
            _present("SUPABASE_SECRET_KEY"),
            True,
            "SUPABASE_SECRET_KEY configured" if _present("SUPABASE_SECRET_KEY") else "SUPABASE_SECRET_KEY is missing",
        ),
        PreflightCheck(
            "openai_api_key",
            _present("OPENAI_API_KEY"),
            True,
            "OPENAI_API_KEY configured" if _present("OPENAI_API_KEY") else "OPENAI_API_KEY is missing",
        ),
        PreflightCheck(
            "discovery_model",
            _present("BRIEFING_DISCOVERY_MODEL"),
            True,
            "BRIEFING_DISCOVERY_MODEL configured" if _present("BRIEFING_DISCOVERY_MODEL") else "BRIEFING_DISCOVERY_MODEL is missing",
        ),
        PreflightCheck(
            "routine_model",
            _present("BRIEFING_ROUTINE_MODEL") or _present("BRIEFING_DISCOVERY_MODEL"),
            True,
            (
                "BRIEFING_ROUTINE_MODEL configured"
                if _present("BRIEFING_ROUTINE_MODEL")
                else "routine model will reuse BRIEFING_DISCOVERY_MODEL"
                if _present("BRIEFING_DISCOVERY_MODEL")
                else "BRIEFING_ROUTINE_MODEL/BRIEFING_DISCOVERY_MODEL is missing"
            ),
        ),
        PreflightCheck(
            "discovery_lanes",
            len(DISCOVERY_LANES) == 4,
            True,
            f"focused search lanes={len(DISCOVERY_LANES)} (expected 4)",
        ),
        PreflightCheck(
            "shared_budget",
            (SHARED_DISCOVERY_TARGET, SHARED_DISCOVERY_SOFT_LIMIT, SHARED_DISCOVERY_HARD_LIMIT) == (4, 5, 6),
            True,
            f"shared discovery budget={SHARED_DISCOVERY_TARGET}/{SHARED_DISCOVERY_SOFT_LIMIT}/{SHARED_DISCOVERY_HARD_LIMIT}",
        ),
        PreflightCheck(
            "direct_source_json",
            direct_source_parse_ok,
            True,
            "BRIEFING_DIRECT_SOURCES_JSON parsed" if direct_source_parse_ok else "BRIEFING_DIRECT_SOURCES_JSON is invalid JSON/config",
        ),
        PreflightCheck(
            "direct_sources",
            bool(direct_sources) and all(_valid_direct_source(s) for s in direct_sources),
            require_direct_sources,
            (
                f"verified direct sources configured={len(direct_sources)}"
                if direct_sources and all(_valid_direct_source(s) for s in direct_sources)
                else "no verified direct sources configured (or placeholder URL detected)"
            ),
        ),
    ]
    return checks


def preflight_ready(checks: list[PreflightCheck]) -> bool:
    return all(check.ok for check in checks if check.required)
