from __future__ import annotations

from datetime import date, datetime, timezone
import os
from typing import Any, Iterable

import requests


class BriefingRepositoryError(RuntimeError):
    pass


class BriefingRepository:
    """Server-side Supabase REST repository for the Briefing Engine.

    Browser clients never receive the service-role credential.  The Streamlit
    server uses this repository for generation, publication and read-only UI
    queries against the Migration 16 schema.
    """

    def __init__(self, url: str | None = None, secret_key: str | None = None, timeout: float = 15.0):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.secret_key = (secret_key or os.getenv("SUPABASE_SECRET_KEY", "")).strip()
        self.timeout = timeout
        self.http = requests.Session()
        if not self.url or not self.secret_key:
            raise BriefingRepositoryError("Supabase server credentials are not configured")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.http.request(
                method,
                self.url + path,
                params=params,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BriefingRepositoryError("Briefing database request failed") from exc
        if not 200 <= response.status_code < 300:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("message") or payload.get("details") or "")[:240]
            except ValueError:
                pass
            suffix = f": {detail}" if detail else ""
            raise BriefingRepositoryError(f"Briefing database HTTP {response.status_code}{suffix}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _first(rows: Any) -> dict[str, Any] | None:
        return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None

    @staticmethod
    def _iso(value: date | datetime | str) -> str:
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)

    def profiles(self) -> list[dict[str, Any]]:
        rows = self._request(
            "GET",
            "/rest/v1/hwarang_briefing_profiles",
            params={"select": "*", "order": "profile_code.asc"},
        )
        return rows if isinstance(rows, list) else []

    def profile(self, profile_code: str) -> dict[str, Any] | None:
        return self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_profiles",
            params={"profile_code": f"eq.{profile_code}", "select": "*", "limit": "1"},
        ))

    # ------------------------------------------------------------------
    # Job / operational logging
    # ------------------------------------------------------------------
    def next_attempt_no(self, job_key: str) -> int:
        row = self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_jobs",
            params={"job_key": f"eq.{job_key}", "select": "attempt_no", "order": "attempt_no.desc", "limit": "1"},
        ))
        return int(row.get("attempt_no") or 0) + 1 if row else 1

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST", "/rest/v1/hwarang_briefing_jobs", json=payload, prefer="return=representation"
        )
        row = self._first(rows)
        if not row:
            raise BriefingRepositoryError("Briefing job insert returned no row")
        return row

    def update_job(self, job_id: str, payload: dict[str, Any]) -> None:
        self._request(
            "PATCH",
            "/rest/v1/hwarang_briefing_jobs",
            params={"id": f"eq.{job_id}"},
            json=payload,
            prefer="return=minimal",
        )

    def checkpoint(self, job_id: str, checkpoint_code: str, payload: dict[str, Any] | None = None) -> None:
        body = {"job_id": job_id, "checkpoint_code": checkpoint_code, "payload": payload or {}}
        self._request(
            "POST",
            "/rest/v1/hwarang_briefing_checkpoints",
            params={"on_conflict": "job_id,checkpoint_code"},
            json=body,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def log_api_usage(self, payload: dict[str, Any]) -> None:
        self._request(
            "POST", "/rest/v1/hwarang_briefing_api_usage", json=payload, prefer="return=minimal"
        )

    def audit(self, payload: dict[str, Any]) -> None:
        self._request(
            "POST", "/rest/v1/hwarang_briefing_audit_log", json=payload, prefer="return=minimal"
        )

    # ------------------------------------------------------------------
    # Briefing / Revision / Snapshot writes
    # ------------------------------------------------------------------
    def get_or_create_briefing(self, profile_code: str, briefing_date: date | str, briefing_type: str = "MORNING") -> dict[str, Any]:
        date_value = self._iso(briefing_date)
        params = {
            "profile_code": f"eq.{profile_code}",
            "briefing_date": f"eq.{date_value}",
            "briefing_type": f"eq.{briefing_type}",
            "select": "*",
            "limit": "1",
        }
        existing = self._first(self._request("GET", "/rest/v1/hwarang_briefings", params=params))
        if existing:
            return existing
        rows = self._request(
            "POST",
            "/rest/v1/hwarang_briefings",
            json={"profile_code": profile_code, "briefing_date": date_value, "briefing_type": briefing_type},
            prefer="return=representation",
        )
        row = self._first(rows)
        if not row:
            # Concurrent creator may have won the unique race.
            row = self._first(self._request("GET", "/rest/v1/hwarang_briefings", params=params))
        if not row:
            raise BriefingRepositoryError("Briefing record could not be created")
        return row

    def next_revision_no(self, briefing_id: str) -> int:
        row = self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_revisions",
            params={"briefing_id": f"eq.{briefing_id}", "select": "revision_no", "order": "revision_no.desc", "limit": "1"},
        ))
        return int(row.get("revision_no") or 0) + 1 if row else 1

    def create_revision(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST", "/rest/v1/hwarang_briefing_revisions", json=payload, prefer="return=representation"
        )
        row = self._first(rows)
        if not row:
            raise BriefingRepositoryError("Briefing revision insert returned no row")
        return row

    def update_revision(self, revision_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self._first(self._request(
            "PATCH",
            "/rest/v1/hwarang_briefing_revisions",
            params={"id": f"eq.{revision_id}"},
            json=payload,
            prefer="return=representation",
        ))

    def create_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST", "/rest/v1/hwarang_briefing_snapshots", json=payload, prefer="return=representation"
        )
        row = self._first(rows)
        if not row:
            raise BriefingRepositoryError("Briefing snapshot insert returned no row")
        return row

    def upsert_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_key = str(payload["event_key"])
        existing = self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_events",
            params={"event_key": f"eq.{event_key}", "select": "*", "limit": "1"},
        ))
        if existing:
            first_seen = existing.get("first_seen_at") or payload.get("first_seen_at")
            update = {
                "canonical_title": payload.get("canonical_title") or existing.get("canonical_title"),
                "primary_category": payload.get("primary_category") or existing.get("primary_category"),
                "event_status": payload.get("event_status") or existing.get("event_status") or "active",
                "first_seen_at": first_seen,
                "last_seen_at": payload.get("last_seen_at") or existing.get("last_seen_at"),
                "metadata": payload.get("metadata") or existing.get("metadata") or {},
            }
            row = self._first(self._request(
                "PATCH",
                "/rest/v1/hwarang_briefing_events",
                params={"id": f"eq.{existing['id']}"},
                json=update,
                prefer="return=representation",
            ))
            return row or existing
        rows = self._request(
            "POST", "/rest/v1/hwarang_briefing_events", json=payload, prefer="return=representation"
        )
        row = self._first(rows)
        if not row:
            raise BriefingRepositoryError("Briefing event insert returned no row")
        return row

    def ensure_event_update(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        event_id = str(payload["event_id"])
        update_key = str(payload["update_key"])
        existing = self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_event_updates",
            params={"event_id": f"eq.{event_id}", "update_key": f"eq.{update_key}", "select": "*", "limit": "1"},
        ))
        if existing:
            return existing
        rows = self._request(
            "POST", "/rest/v1/hwarang_briefing_event_updates", json=payload, prefer="return=representation"
        )
        return self._first(rows)

    def insert_sources(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        result = self._request(
            "POST", "/rest/v1/hwarang_briefing_sources", json=rows, prefer="return=representation"
        )
        return result if isinstance(result, list) else []

    def insert_issues(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        result = self._request(
            "POST", "/rest/v1/hwarang_briefing_issues", json=rows, prefer="return=representation"
        )
        return result if isinstance(result, list) else []

    def insert_actions(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        result = self._request(
            "POST", "/rest/v1/hwarang_briefing_actions", json=rows, prefer="return=representation"
        )
        return result if isinstance(result, list) else []

    def link_issue_sources(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self._request(
                "POST", "/rest/v1/hwarang_briefing_issue_sources", json=rows, prefer="return=minimal"
            )

    def publish_revision(self, briefing_id: str, revision_id: str, *, actor_user_id: str | None = None) -> None:
        self._request("POST", "/rest/v1/rpc/hwarang_publish_briefing", json={
            "p_briefing": briefing_id, "p_revision": revision_id, "p_actor": actor_user_id})

    def claim_run(self, key, day, group, owner, retry=False):
        return self._request("POST", "/rest/v1/rpc/hwarang_claim_briefing_run", json={
            "p_key": key, "p_date": str(day), "p_group": group, "p_owner": owner, "p_retry": retry})

    def save_run(self, key, owner, checkpoint, status="running"):
        ok = self._request("POST", "/rest/v1/rpc/hwarang_checkpoint_briefing_run", json={
            "p_key": key, "p_owner": owner, "p_checkpoint": checkpoint, "p_status": status})
        if ok is not True: raise BriefingRepositoryError("자동 실행 잠금이 만료되었습니다. 중복 호출을 중단합니다.")

    def reserve_request(self, day, kind):
        if self._request("POST", "/rest/v1/rpc/hwarang_reserve_briefing_request", json={"p_date": str(day), "p_kind": kind}) is not True:
            raise BriefingRepositoryError("오늘의 API 호출 상한에 도달했습니다. 저장된 결과를 재사용합니다.")

    def finish_stale_jobs(self, day, codes):
        self._request("PATCH", "/rest/v1/hwarang_briefing_jobs", params={
            "briefing_date": "eq."+str(day), "profile_code": self._in_filter(codes),
            "job_status": "in.(scheduled,collecting,normalizing,analyzing,generating,validating)"},
            json={"job_status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(),
                  "failure_code": "EXPIRED_LEASE", "failure_message": "Expired execution replaced by one recovery run"})

    def create_share(self, revision_id, sender_user_id, public_packet):
        import secrets
        token = secrets.token_urlsafe(32)
        revision = self._first(self._request("GET", "/rest/v1/hwarang_briefing_revisions", params={"id": "eq."+revision_id, "select": "*"}))
        if not revision or revision.get("publication_status") != "published" or not revision.get("external_share_allowed") or not revision.get("external_qa_passed"):
            raise BriefingRepositoryError("공개 검수가 끝난 브리핑만 고객에게 공유할 수 있습니다.")
        existing = self._first(self._request("GET", "/rest/v1/hwarang_briefing_public_shares", params={
            "revision_id": "eq."+revision_id, "sender_user_id": "eq."+sender_user_id, "revoked_at": "is.null",
            "expires_at": "gt."+datetime.now(timezone.utc).isoformat(), "select": "token,public_packet", "limit": "1"}))
        if existing: return existing["token"], existing["public_packet"]
        # Load the immutable sanitized snapshot on the server; never trust a caller-provided body.
        snapshot = self._snapshot_for_revision(revision_id)
        body = (snapshot or {}).get("external_content_payload") or {}
        from .public_body import customer_body
        checked = customer_body({**body, "market_metrics": {"items": [dict(r, external_allowed=True) for r in body.get("market_metrics", [])]}})
        if not checked.get("issues"): raise BriefingRepositoryError("고객 공유 본문을 확인할 수 없습니다.")
        sender = self._first(self._request("GET", "/rest/v1/profiles", params={"id": "eq."+sender_user_id, "select": "*"}))
        if not sender or not sender.get("is_active", False) or not str(sender.get("display_name") or "").strip(): raise BriefingRepositoryError("공유자 계정을 확인할 수 없습니다.")
        briefing = self._first(self._request("GET", "/rest/v1/hwarang_briefings", params={"id": "eq."+str(revision['briefing_id']), "select": "briefing_date"}))
        position = self._first(self._request("GET", "/rest/v1/positions", params={"code": "eq."+str(sender.get("position_code") or ""), "select": "display_name"}))
        if not position: raise BriefingRepositoryError("등록 직함을 확인할 수 없습니다.")
        public_packet = {"body": checked, "briefing_date": (briefing or {}).get("briefing_date"),
                         "sender": {"name": sender.get("display_name") or "", "position": (position or {}).get("display_name") or ""}}
        self._request("POST", "/rest/v1/hwarang_briefing_public_shares", json={"token": token, "revision_id": revision_id,
            "sender_user_id": sender_user_id, "public_packet": public_packet})
        return token, public_packet

    def public_share(self, token):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", str(token)): return None
        row = self._first(self._request("GET", "/rest/v1/hwarang_briefing_public_shares", params={
            "token": "eq."+token, "revoked_at": "is.null", "expires_at": "gt."+datetime.now(timezone.utc).isoformat(), "select": "revision_id,public_packet"}))
        if not row: return None
        revision = self._first(self._request("GET", "/rest/v1/hwarang_briefing_revisions", params={"id": "eq."+row['revision_id'], "select": "publication_status,external_share_allowed,external_qa_passed"}))
        if not revision or revision.get("publication_status") != "published" or not revision.get("external_share_allowed") or not revision.get("external_qa_passed"): return None
        return row.get("public_packet")

    def revoke_share(self, token, actor):
        self._request("PATCH", "/rest/v1/hwarang_briefing_public_shares", params={"token": "eq."+token, "sender_user_id": "eq."+actor}, json={"revoked_at": datetime.now(timezone.utc).isoformat()})

    def hide_revision(self, briefing_id, revision_id, actor):
        self.update_revision(revision_id, {"publication_status": "hidden", "external_share_allowed": False})
        self._request("PATCH", "/rest/v1/hwarang_briefings", params={"id": "eq."+briefing_id, "current_published_revision_id": "eq."+revision_id}, json={"current_published_revision_id": None})
        self.audit({"actor_type": "user", "actor_user_id": actor, "action": "BRIEFING_HIDDEN", "briefing_id": briefing_id, "revision_id": revision_id, "details": {}})

    # ------------------------------------------------------------------
    # UI reads
    # ------------------------------------------------------------------
    def _snapshot_for_revision(self, revision_id: str) -> dict[str, Any] | None:
        return self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_snapshots",
            params={"revision_id": f"eq.{revision_id}", "select": "*", "limit": "1"},
        ))

    def _latest_revision(self, briefing_id: str) -> dict[str, Any] | None:
        return self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefing_revisions",
            params={"briefing_id": f"eq.{briefing_id}", "select": "*", "order": "revision_no.desc", "limit": "1"},
        ))

    @staticmethod
    def _in_filter(values: Iterable[str]) -> str:
        clean = [str(value).strip() for value in values if str(value).strip()]
        return f"in.({','.join(clean)})"

    def latest_summaries(self, profile_codes: Iterable[str], *, include_draft: bool = False) -> dict[str, dict[str, Any] | None]:
        codes = tuple(dict.fromkeys(str(code).strip().upper() for code in profile_codes if str(code).strip()))
        result = {code: None for code in codes}
        if not codes: return result
        rows = self._request("GET", "/rest/v1/hwarang_briefings", params={
            "profile_code": self._in_filter(codes),
            "select": "id,profile_code,briefing_date,briefing_type,current_published_revision_id,created_at",
            "order": "briefing_date.desc,created_at.desc", "limit": str(max(10,len(codes)*10)),
        })
        if not isinstance(rows,list) or not rows: return result
        candidates = {code: [] for code in codes}
        for row in rows:
            code=str(row.get("profile_code") or "").upper()
            if code in candidates and len(candidates[code])<10: candidates[code].append(row)
        briefing_ids=[str(r.get("id")) for group in candidates.values() for r in group if r.get("id")]
        revision_by_briefing={}; revision_by_id={}
        if include_draft and briefing_ids:
            revisions=self._request("GET","/rest/v1/hwarang_briefing_revisions",params={
                "briefing_id":self._in_filter(briefing_ids),
                "select":"id,briefing_id,revision_no,revision_type,publication_status,validation_status,coverage_status,generated_at",
                "order":"revision_no.desc"})
            for rev in revisions if isinstance(revisions,list) else []:
                bid=str(rev.get("briefing_id") or "")
                if bid and bid not in revision_by_briefing: revision_by_briefing[bid]=rev
        else:
            ids=[str(r.get("current_published_revision_id")) for group in candidates.values() for r in group if r.get("current_published_revision_id")]
            if ids:
                revisions=self._request("GET","/rest/v1/hwarang_briefing_revisions",params={"id":self._in_filter(ids),"select":"id,briefing_id,revision_no,revision_type,publication_status,validation_status,coverage_status,generated_at"})
                revision_by_id={str(r.get("id")):r for r in (revisions if isinstance(revisions,list) else []) if r.get("id")}
        selected={}
        for code,group in candidates.items():
            for briefing in group:
                rev=revision_by_briefing.get(str(briefing.get("id") or "")) if include_draft else revision_by_id.get(str(briefing.get("current_published_revision_id") or ""))
                if rev: selected[code]=(briefing,rev); break
        ids=[str(pair[1].get("id")) for pair in selected.values() if pair[1].get("id")]
        if not ids: return result
        snapshots=self._request("GET","/rest/v1/hwarang_briefing_snapshots",params={"revision_id":self._in_filter(ids),"select":"id,revision_id,fast_brief_payload,today_action_payload,qa_payload,snapshot_created_at"})
        byrev={str(r.get("revision_id")):r for r in (snapshots if isinstance(snapshots,list) else []) if r.get("revision_id")}
        for code,(briefing,rev) in selected.items():
            snap=byrev.get(str(rev.get("id") or ""))
            if snap: result[code]={"briefing":briefing,"revision":rev,"snapshot":snap}
        return result

    def latest_bundle(self, profile_code: str, *, include_draft: bool = False) -> dict[str, Any] | None:
        briefings = self._request(
            "GET",
            "/rest/v1/hwarang_briefings",
            params={"profile_code": f"eq.{profile_code}", "select": "*", "order": "briefing_date.desc,created_at.desc", "limit": "10"},
        )
        if not isinstance(briefings, list):
            return None
        for briefing in briefings:
            revision: dict[str, Any] | None = None
            if include_draft:
                revision = self._latest_revision(str(briefing["id"]))
            elif briefing.get("current_published_revision_id"):
                revision = self._first(self._request(
                    "GET",
                    "/rest/v1/hwarang_briefing_revisions",
                    params={"id": f"eq.{briefing['current_published_revision_id']}", "select": "*", "limit": "1"},
                ))
            if revision:
                snapshot = self._snapshot_for_revision(str(revision["id"]))
                if snapshot:
                    return self.bundle_from_parts(briefing, revision, snapshot)
        return None

    def bundle_for_date(self, profile_code: str, briefing_date: date | str, *, include_draft: bool = False) -> dict[str, Any] | None:
        briefing = self._first(self._request(
            "GET",
            "/rest/v1/hwarang_briefings",
            params={
                "profile_code": f"eq.{profile_code}",
                "briefing_date": f"eq.{self._iso(briefing_date)}",
                "select": "*",
                "limit": "1",
            },
        ))
        if not briefing:
            return None
        revision = self._latest_revision(str(briefing["id"])) if include_draft else None
        if not include_draft and briefing.get("current_published_revision_id"):
            revision = self._first(self._request(
                "GET",
                "/rest/v1/hwarang_briefing_revisions",
                params={"id": f"eq.{briefing['current_published_revision_id']}", "select": "*", "limit": "1"},
            ))
        if not revision:
            return None
        snapshot = self._snapshot_for_revision(str(revision["id"]))
        return self.bundle_from_parts(briefing, revision, snapshot) if snapshot else None

    def bundle_from_parts(self, briefing: dict[str, Any], revision: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(snapshot["id"])
        issues = self._request(
            "GET",
            "/rest/v1/hwarang_briefing_issues",
            params={"snapshot_id": f"eq.{snapshot_id}", "select": "id,snapshot_id,event_id,issue_key,sort_order,category,issue_status,selection_tier,evidence_status,title,summary,fact_payload,analysis_payload", "order": "selection_tier.asc,sort_order.asc"},
        )
        actions = self._request(
            "GET",
            "/rest/v1/hwarang_briefing_actions",
            params={"snapshot_id": f"eq.{snapshot_id}", "select": "id,snapshot_id,issue_id,event_id,action_state,communication_state,title,summary,audience_segments,conversation_payload,workspace_actions,sort_order", "order": "sort_order.asc"},
        )
        sources = self._request(
            "GET",
            "/rest/v1/hwarang_briefing_sources",
            params={"snapshot_id": f"eq.{snapshot_id}", "select": "id,snapshot_id,source_name,publisher_name,title,url,canonical_url,published_at", "order": "published_at.desc.nullslast"},
        )
        issue_rows = issues if isinstance(issues, list) else []
        relations: list[dict[str, Any]] = []
        issue_ids = [str(row.get("id")) for row in issue_rows if row.get("id")]
        if issue_ids:
            relations_raw = self._request(
                "GET",
                "/rest/v1/hwarang_briefing_issue_sources",
                params={"issue_id": f"in.({','.join(issue_ids)})", "select": "issue_id,source_id,relation_type"},
            )
            relations = relations_raw if isinstance(relations_raw, list) else []
        return {
            "briefing": briefing,
            "revision": revision,
            "snapshot": snapshot,
            "issues": issue_rows,
            "actions": actions if isinstance(actions, list) else [],
            "sources": sources if isinstance(sources, list) else [],
            "issue_sources": relations,
        }

    def history(self, profile_code: str, *, limit: int = 60, include_draft: bool = False) -> list[dict[str, Any]]:
        rows=self._request("GET","/rest/v1/hwarang_briefings",params={
            "profile_code":f"eq.{profile_code}","select":"id,profile_code,briefing_date,briefing_type,current_published_revision_id,created_at",
            "order":"briefing_date.desc","limit":str(max(1,min(limit,120)))})
        if not isinstance(rows,list) or not rows: return []
        briefing_ids=[str(r.get("id")) for r in rows if r.get("id")]; byb={}; byid={}
        if include_draft and briefing_ids:
            revisions=self._request("GET","/rest/v1/hwarang_briefing_revisions",params={"briefing_id":self._in_filter(briefing_ids),"select":"id,briefing_id,revision_no,revision_type,publication_status,validation_status,coverage_status,generated_at","order":"revision_no.desc"})
            for rev in revisions if isinstance(revisions,list) else []:
                bid=str(rev.get("briefing_id") or "")
                if bid and bid not in byb: byb[bid]=rev
        else:
            ids=[str(r.get("current_published_revision_id")) for r in rows if r.get("current_published_revision_id")]
            if ids:
                revisions=self._request("GET","/rest/v1/hwarang_briefing_revisions",params={"id":self._in_filter(ids),"select":"id,briefing_id,revision_no,revision_type,publication_status,validation_status,coverage_status,generated_at"})
                byid={str(r.get("id")):r for r in (revisions if isinstance(revisions,list) else []) if r.get("id")}
        selected=[]
        for briefing in rows:
            rev=byb.get(str(briefing.get("id") or "")) if include_draft else byid.get(str(briefing.get("current_published_revision_id") or ""))
            if rev: selected.append((briefing,rev))
        ids=[str(rev.get("id")) for _,rev in selected if rev.get("id")]; snapshots=[]
        if ids: snapshots=self._request("GET","/rest/v1/hwarang_briefing_snapshots",params={"revision_id":self._in_filter(ids),"select":"id,revision_id,fast_brief_payload,today_action_payload,qa_payload,snapshot_created_at"})
        byrev={str(r.get("revision_id")):r for r in (snapshots if isinstance(snapshots,list) else []) if r.get("revision_id")}
        return [{"briefing":b,"revision":r,"snapshot":byrev[str(r["id"])]} for b,r in selected if str(r.get("id") or "") in byrev]

    def event_updates_many(self, event_ids: Iterable[str], *, limit_per_event: int = 6) -> dict[str,list[dict[str,Any]]]:
        ids=tuple(dict.fromkeys(str(x).strip() for x in event_ids if str(x).strip()))
        if not ids: return {}
        rows=self._request("GET","/rest/v1/hwarang_briefing_event_updates",params={"event_id":self._in_filter(ids),"select":"id,event_id,update_type,evidence_status,title,change_summary,observed_at,effective_at","order":"observed_at.desc"})
        grouped={x:[] for x in ids}
        for row in rows if isinstance(rows,list) else []:
            eid=str(row.get("event_id") or "")
            if eid in grouped and len(grouped[eid])<max(1,limit_per_event): grouped[eid].append(row)
        return grouped

    def event_updates(self, event_id: str, *, limit: int = 6) -> list[dict[str, Any]]:
        rows = self._request(
            "GET",
            "/rest/v1/hwarang_briefing_event_updates",
            params={"event_id": f"eq.{event_id}", "select": "*", "order": "observed_at.desc", "limit": str(limit)},
        )
        return rows if isinstance(rows, list) else []
