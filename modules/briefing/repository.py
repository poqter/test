from __future__ import annotations

import os
from typing import Any

import requests


class BriefingRepositoryError(RuntimeError):
    pass


class BriefingRepository:
    """Server-side Supabase REST repository for Briefing Engine operational records."""

    def __init__(self, url: str | None = None, secret_key: str | None = None, timeout: float = 12.0):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.secret_key = (secret_key or os.getenv("SUPABASE_SECRET_KEY", "")).strip()
        self.timeout = timeout
        self.http = requests.Session()
        if not self.url or not self.secret_key:
            raise BriefingRepositoryError("Supabase server credentials are not configured")

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                 json: Any = None, prefer: str | None = None) -> Any:
        headers = {"apikey": self.secret_key, "Authorization": f"Bearer {self.secret_key}", "Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.http.request(method, self.url + path, params=params, json=json, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BriefingRepositoryError("Briefing database request failed") from exc
        if not 200 <= response.status_code < 300:
            raise BriefingRepositoryError(f"Briefing database HTTP {response.status_code}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def profiles(self) -> list[dict[str, Any]]:
        rows = self._request("GET", "/rest/v1/hwarang_briefing_profiles", params={"select": "*", "order": "profile_code.asc"})
        return rows if isinstance(rows, list) else []

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "/rest/v1/hwarang_briefing_jobs", json=payload, prefer="return=representation")
        if not isinstance(rows, list) or not rows:
            raise BriefingRepositoryError("Briefing job insert returned no row")
        return rows[0]

    def update_job(self, job_id: str, payload: dict[str, Any]) -> None:
        self._request("PATCH", "/rest/v1/hwarang_briefing_jobs", params={"id": f"eq.{job_id}"}, json=payload, prefer="return=minimal")

    def log_api_usage(self, payload: dict[str, Any]) -> None:
        self._request("POST", "/rest/v1/hwarang_briefing_api_usage", json=payload, prefer="return=minimal")
