"""Supabase persistence adapter for generated Case/Session state.

The adapter uses the already server-side HWARANG Supabase service. It performs no
network activity until one of its methods is called by the application.
"""
from __future__ import annotations

from typing import Any

from .case_engine import GeneratedCase, case_to_supabase_record


class AcademyRepository:
    def __init__(self, auth_service: Any):
        self.auth = auth_service

    def create_case(self, case: GeneratedCase, *, owner_user_id: str, title: str | None = None) -> dict[str, Any]:
        rows = self.auth._request(
            "POST", "/rest/v1/academy_cases", admin=True,
            json=case_to_supabase_record(case, owner_user_id=owner_user_id, title=title),
            prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("academy case was not created")
        return rows[0]

    def get_case(self, case_id: str, *, owner_user_id: str | None = None) -> dict[str, Any] | None:
        params = {"select": "*", "id": f"eq.{case_id}", "limit": "1"}
        if owner_user_id:
            params["owner_user_id"] = f"eq.{owner_user_id}"
        rows = self.auth._request("GET", "/rest/v1/academy_cases", admin=True, params=params)
        return rows[0] if isinstance(rows, list) and rows else None

    def list_cases(self, owner_user_id: str, *, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params = {
            "select": "id,status,current_stage,title,customer_alias,customer_seed,public_state,updated_at,created_at",
            "owner_user_id": f"eq.{owner_user_id}",
            "order": "updated_at.desc",
            "limit": str(max(1, min(int(limit), 100))),
        }
        if status:
            params["status"] = f"eq.{status}"
        rows = self.auth._request("GET", "/rest/v1/academy_cases", admin=True, params=params)
        return rows if isinstance(rows, list) else []

    def update_case_state(self, case_id: str, *, owner_user_id: str, updates: dict[str, Any]) -> None:
        allowed = {"status", "current_stage", "customer_state", "public_state", "insurance_state", "journey_state", "coverage_analysis", "proposal_state", "metadata", "completed_at", "archived_at"}
        body = {k: v for k, v in updates.items() if k in allowed}
        if not body:
            return
        self.auth._request(
            "PATCH", "/rest/v1/academy_cases", admin=True,
            params={"id": f"eq.{case_id}", "owner_user_id": f"eq.{owner_user_id}"},
            json=body, prefer="return=minimal",
        )

    def create_session(
        self, *, case_id: str, user_id: str, sequence_no: int, stage: str, scenario_id: str | None,
        mode: str, difficulty: str, seed: int, customer_seed: int, training_focus: str,
        interaction_mode: str = "TEXT", engine_version: str | None = None,
        scenario_version: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "case_id": case_id,
            "user_id": user_id,
            "sequence_no": int(sequence_no),
            "stage": stage,
            "scenario_id": scenario_id,
            "mode": mode,
            "difficulty": difficulty,
            "seed": int(seed),
            "customer_seed": int(customer_seed),
            "training_focus": training_focus,
            "interaction_mode": interaction_mode,
            "engine_version": engine_version,
            "scenario_version": scenario_version,
            "evidence_log": [],
        }
        rows = self.auth._request(
            "POST", "/rest/v1/academy_sessions", admin=True,
            json=body, prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("academy session was not created")
        return rows[0]

    def save_session_progress(
        self, session_id: str, *, user_id: str, replay_inputs: list[Any], transcript: list[Any],
        session_state: dict[str, Any], evidence_log: list[Any], last_turn_no: int,
    ) -> None:
        self.auth._request(
            "PATCH", "/rest/v1/academy_sessions", admin=True,
            params={"id": f"eq.{session_id}", "user_id": f"eq.{user_id}"},
            json={
                "replay_inputs": replay_inputs,
                "transcript": transcript,
                "session_state": session_state,
                "evidence_log": evidence_log,
                "last_turn_no": int(last_turn_no),
            },
            prefer="return=minimal",
        )

    def find_reusable_assessment(
        self,
        *,
        session_id: str,
        source_snapshot_hash: str,
        framework_version: str,
        evaluator_type: str = "ai",
    ) -> dict[str, Any] | None:
        """Return an immutable assessment only when the complete source hash matches."""
        rows = self.auth._request(
            "GET",
            "/rest/v1/academy_assessments",
            admin=True,
            params={
                "select": "*",
                "session_id": f"eq.{session_id}",
                "source_snapshot_hash": f"eq.{source_snapshot_hash}",
                "framework_version": f"eq.{framework_version}",
                "evaluator_type": f"eq.{evaluator_type}",
                "order": "generated_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if isinstance(rows, list) and rows else None

    def create_assessment_snapshot(
        self,
        *,
        user_id: str,
        case_id: str,
        session_id: str,
        source_snapshot_hash: str,
        framework_version: str,
        payload: dict[str, Any],
        prompt_version: str | None = None,
        evaluator_type: str = "ai",
    ) -> dict[str, Any]:
        """Persist one immutable formal-evaluation snapshot.

        Migration 11 makes the source tuple unique.  If another worker wins a
        race, we read and return the already-created snapshot instead of
        manufacturing a second assessment record.
        """
        competency_scores = {
            str(row.get("code")): {
                "score": row.get("score"),
                "rationale": row.get("rationale"),
                "evidence_turns": list(row.get("evidence_turns") or []),
            }
            for row in payload.get("competencies") or []
            if isinstance(row, dict) and row.get("code")
        }
        evidence = [
            {
                "kind": "competency",
                "code": row.get("code"),
                "turns": list(row.get("evidence_turns") or []),
            }
            for row in payload.get("competencies") or []
            if isinstance(row, dict) and row.get("evidence_turns")
        ]

        body = {
            "user_id": user_id,
            "case_id": case_id,
            "session_id": session_id,
            "assessment_type": "original",
            "evaluator_type": evaluator_type,
            "framework_version": framework_version,
            "overall_score": payload.get("overall_score"),
            "grade": payload.get("grade"),
            "status": (payload.get("sales_outcome") or {}).get("status"),
            "competency_scores": competency_scores,
            "strengths": list(payload.get("strengths") or []),
            "development_areas": list(payload.get("development_areas") or []),
            "evidence": evidence,
            "missed_opportunities": list(payload.get("missed_opportunities") or []),
            "coaching_plan": dict(payload.get("coaching_plan") or {}),
            "next_training": {"items": list(payload.get("recommended_training") or [])},
            "report_snapshot": payload,
            "source_snapshot_hash": source_snapshot_hash,
            "metadata": {
                "prompt_version": prompt_version,
                "immutable_snapshot": True,
            },
        }

        try:
            rows = self.auth._request(
                "POST",
                "/rest/v1/academy_assessments",
                admin=True,
                json=body,
                prefer="return=representation",
            )
            if isinstance(rows, list) and rows:
                result = dict(rows[0])
                result["reused"] = False
                return result
        except Exception:
            # A concurrent worker may have won the unique snapshot insert.
            cached = self.find_reusable_assessment(
                session_id=session_id,
                source_snapshot_hash=source_snapshot_hash,
                framework_version=framework_version,
                evaluator_type=evaluator_type,
            )
            if cached:
                result = dict(cached)
                result["reused"] = True
                return result
            raise

        raise RuntimeError("academy assessment was not created")
