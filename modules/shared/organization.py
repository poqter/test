"""Versioned organization settings; no user/account or customer database.

Default: immutable deployment JSON + explicitly temporary session overrides.
Optional: SQLite on an operator-provided durable volume. Never assume that
Community Cloud's local filesystem is durable. The selected organization is a
server-side deployment setting, not a user-controlled query parameter.
"""
from __future__ import annotations
import copy
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAX_CONFIG_BYTES = 256 * 1024


@lru_cache(maxsize=1)
def _defaults() -> dict:
    return json.loads((ROOT / "data/organization_defaults.json").read_text(encoding="utf-8"))


def _state():
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return st.session_state if get_script_run_ctx(suppress_warning=True) else None
    except (ImportError, AttributeError):
        return None


def deployment_settings() -> dict:
    settings = {"id": "hwarang", "db_path": ""}
    if _state() is not None:
        try:
            import streamlit as st
            settings.update(dict(st.secrets.get("organization", {})))
        except (KeyError, FileNotFoundError, TypeError):
            pass
    settings["db_path"] = os.environ.get("HW_ORGANIZATION_DB", settings.get("db_path", ""))
    return settings


def _org_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("조직 ID는 영문·숫자·밑줄·하이픈 1~64자여야 합니다.")
    return value


def _connect(path: str):
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("운영 설정 DB에는 영구 볼륨의 절대 경로가 필요합니다.")
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS organization_versions (organization_id TEXT NOT NULL, revision INTEGER NOT NULL, effective_from TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY (organization_id, revision))")
    connection.commit()
    return connection


def versions(org_id: str | None = None, *, state=None, db_path: str | None = None) -> list[dict]:
    settings = deployment_settings()
    org_id = _org_id(org_id or str(settings["id"]))
    path = settings.get("db_path", "") if db_path is None else db_path
    defaults = _defaults()["organizations"].get(org_id)
    base = copy.deepcopy((defaults or _defaults()["organizations"]["hwarang"])["revisions"])
    if path:
        from contextlib import closing
        with closing(_connect(str(path))) as connection:
            records = connection.execute("SELECT payload FROM organization_versions WHERE organization_id=? ORDER BY revision", (org_id,)).fetchall()
        if records:
            return base + [json.loads(row[0]) for row in records]
    session = _state() if state is None else state
    if session is not None:
        base += copy.deepcopy(session.get("hw.organization." + org_id, []))
    return base


def active_profile(*, org_id: str | None = None, state=None, db_path: str | None = None,
                   on_date: date | None = None) -> dict:
    today = on_date or date.today()
    records = versions(org_id, state=state, db_path=db_path)
    active = [v for v in records if date.fromisoformat(v["effective_from"]) <= today]
    return copy.deepcopy(max(active or [records[0]], key=lambda v: (v["effective_from"], v["revision"])))


def validate_profile(candidate: dict) -> dict:
    from modules.shell.app_registry import APPS
    allowed = {app.id for app in APPS if app.enabled}
    out = {key: copy.deepcopy(candidate[key]) for key in (
        "effective_from", "brand_name", "header_color", "accent_color", "allowed_tools",
        "commission_default_payout_percent", "payout_rule_label") if key in candidate}
    if len(out) != 7:
        raise ValueError("조직 설정에 필수 항목이 누락됐습니다.")
    date.fromisoformat(out["effective_from"])
    for key in ("brand_name", "payout_rule_label"):
        if not isinstance(out[key], str) or not out[key].strip() or len(out[key]) > 100 or re.search(r"[\x00-\x1f]", out[key]):
            raise ValueError("조직명과 기준명은 제어문자 없는 1~100자여야 합니다.")
    for key in ("header_color", "accent_color"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(out[key])):
            raise ValueError("브랜드 색상은 #RRGGBB 형식이어야 합니다.")
    if not isinstance(out["allowed_tools"], list) or any(x not in allowed for x in out["allowed_tools"]):
        raise ValueError("운영 가능한 메뉴만 선택할 수 있습니다.")
    out["allowed_tools"] = sorted(set(out["allowed_tools"]))
    from modules.shared.numeric import decimal_number
    rate = decimal_number(out["commission_default_payout_percent"], label="지급률", allow_negative=False)
    if rate > 100:
        raise ValueError("기본 지급률은 0~100%여야 합니다.")
    out["commission_default_payout_percent"] = float(rate)
    return out


def save_profile(candidate: dict, *, role: str, expected_revision: int,
                 org_id: str | None = None, state=None, db_path: str | None = None) -> dict:
    if role != "Admin":
        raise PermissionError("관리자만 운영 설정을 변경할 수 있습니다.")
    settings = deployment_settings()
    org_id = _org_id(org_id or str(settings["id"]))
    path = settings.get("db_path", "") if db_path is None else db_path
    payload = validate_profile(candidate)
    payload.update(revision=expected_revision + 1, changed_by=role,
                   changed_at=datetime.now(timezone.utc).isoformat())
    if path:
        connection = _connect(str(path))
        try:
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute("SELECT COALESCE(MAX(revision),0) FROM organization_versions WHERE organization_id=?", (org_id,)).fetchone()[0]
            if latest != expected_revision:
                raise ValueError("다른 변경이 먼저 저장됐습니다. 최신 설정을 다시 불러오세요.")
            connection.execute("INSERT INTO organization_versions VALUES (?,?,?,?)", (org_id, payload["revision"], payload["effective_from"], json.dumps(payload, ensure_ascii=False)))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    else:
        session = _state() if state is None else state
        if session is None:
            raise ValueError("세션 또는 명시적인 영구 DB 경로가 필요합니다.")
        existing = versions(org_id, state=session, db_path="")
        if max(v["revision"] for v in existing) != expected_revision:
            raise ValueError("최신 설정을 다시 불러온 뒤 저장하세요.")
        session.setdefault("hw.organization." + org_id, []).append(payload)
    return copy.deepcopy(payload)


def current_brand_fingerprint() -> str:
    from hashlib import sha256
    profile = active_profile()
    return sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def permitted_tools(tool_ids: list[str]) -> list[str]:
    # Only remove existing role permissions; organization settings never grant
    # access that the application's unchanged role map does not allow.
    enabled = set(active_profile()["allowed_tools"])
    return [tool for tool in tool_ids if tool in enabled]
