from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
from typing import Any

import requests

from .config import DiscoveryLaneSpec
from .discovery_budget import DiscoveryBudget, REQUEST_TOOL_CALL_LIMIT
from .models import DiscoveryLaneResult, DiscoveryUsage, SourceCandidate
from .normalize import is_safe_url, publisher_domain
from .publication import parse_publication_date
from .source_policy import LANE_DOMAINS, source_identity


class BriefingDiscoveryError(RuntimeError):
    pass


class OpenAIWebDiscoveryClient:
    """Low-level Responses API client for the four focused discovery lanes.

    Search and Event classification are deliberately separated. This client only
    collects discovery metadata and never decides CORE/LIGHT importance.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 45.0):
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = (model or os.getenv("BRIEFING_DISCOVERY_MODEL", "")).strip()
        self.timeout = timeout
        self.http = requests.Session()
        self.as_of = datetime.now(timezone.utc)
        self.before_request = None
        if not self.api_key:
            raise BriefingDiscoveryError("OPENAI_API_KEY is not configured")
        if not self.model:
            raise BriefingDiscoveryError("BRIEFING_DISCOVERY_MODEL is not configured")

    def _request(self, lane: DiscoveryLaneSpec) -> dict[str, Any]:
        local_now = self.as_of.astimezone(ZoneInfo("Asia/Seoul"))
        oldest = (local_now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        query_dates = f"after:{oldest.date().isoformat()} before:{(local_now+timedelta(days=1)).date().isoformat()}"
        payload = {
            "model": self.model,
            "input": (
                f"기준시각={self.as_of.isoformat()}. 전날 00:00 KST부터 기준시각까지 게시된 새 자료만 탐색한다. "
                f"한국 기준 날짜={local_now.isoformat()}. 검색어에 {query_dates}를 포함한다. "
                "web_search 도구를 정확히 한 번 사용하고 검색 쿼리도 하나만 작성한다. "
                "여러 하위 주제별 검색이나 추가 탐색 없이 첫 검색 결과의 새 기사/발표 원문 링크만 반환한다. "
                "홈페이지·목록·첨부파일·오래된 해설은 제외한다. 게시일을 추측하지 않는다. " + lane.query
            ),
            "tools": [{"type": "web_search", "filters": {"allowed_domains": list(LANE_DOMAINS[lane.lane_code])}}],
            "tool_choice": "required",
            "max_tool_calls": REQUEST_TOOL_CALL_LIMIT,
            "parallel_tool_calls": False,
            "max_output_tokens": 2000,
            "include": ["web_search_call.action.sources"],
        }
        if self.before_request:
            self.before_request("web")
        try:
            response = self.http.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BriefingDiscoveryError("OpenAI discovery request failed") from exc
        if not 200 <= response.status_code < 300:
            raise BriefingDiscoveryError(f"OpenAI discovery HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise BriefingDiscoveryError("OpenAI discovery returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BriefingDiscoveryError("OpenAI discovery returned invalid response")
        return data

    @staticmethod
    def _usage(data: dict[str, Any]) -> DiscoveryUsage:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
        output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
        def count(value: Any) -> int:
            try:
                return max(0, int(value or 0))
            except (ValueError, TypeError, OverflowError):
                return 0
        return DiscoveryUsage(
            model_name=str(data.get("model") or "") or None,
            service_tier=str(data.get("service_tier") or "") or None,
            input_tokens=count(usage.get("input_tokens")),
            cached_input_tokens=count(input_details.get("cached_tokens")),
            output_tokens=count(usage.get("output_tokens")),
            reasoning_tokens=count(output_details.get("reasoning_tokens")),
        )

    @staticmethod
    def _web_items(data: dict[str, Any]) -> list[dict[str, Any]]:
        output = data.get("output")
        return [item for item in output if isinstance(item, dict) and item.get("type") == "web_search_call"] if isinstance(output, list) else []

    @classmethod
    def _search_performed(cls, data: dict[str, Any]) -> bool:
        for item in cls._web_items(data):
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            if action.get("type") == "search" and item.get("status") not in {"in_progress", "searching", "failed", "incomplete", "cancelled"}:
                return True
        return False

    @classmethod
    def _search_count(cls, data: dict[str, Any]) -> int:
        return sum(isinstance(item.get("action"), dict) and item["action"].get("type") == "search" for item in cls._web_items(data))

    @classmethod
    def _search_status_counts(cls, data: dict[str, Any]) -> dict[str, int]:
        counts = {"completed": 0, "nonfinal": 0, "failed": 0, "unknown": 0}
        for item in cls._web_items(data):
            if not isinstance(item.get("action"), dict) or item["action"].get("type") != "search":
                continue
            status = item.get("status")
            category = ("completed" if status == "completed" else "nonfinal" if status in {"in_progress", "searching"}
                        else "failed" if status in {"failed", "incomplete", "cancelled"} else "unknown")
            counts[category] += 1
        return counts

    @staticmethod
    def _action_queries(item: dict[str, Any]) -> list[str]:
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        queries = action.get("queries")
        if not isinstance(queries, list):
            queries = [action["query"]] if isinstance(action.get("query"), str) else []
        return [query[:500] for query in queries[:8] if isinstance(query, str)]

    @staticmethod
    def _append_source(target: list[dict[str, Any]], source: Any) -> None:
        if not isinstance(source, dict):
            return
        url = str(source.get("url") or source.get("link") or "").strip()
        title = str(source.get("title") or source.get("name") or "").strip()
        if is_safe_url(url):
            target.append(source)

    @classmethod
    def _extract_source_rows(cls, data: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item in cls._web_items(data):
            if item.get("status") in {"in_progress", "searching", "failed", "incomplete", "cancelled"}:
                continue
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            for key in ("results", "sources"):
                values = item.get(key)
                if isinstance(values, list):
                    for source in values:
                        cls._append_source(found, source)
                values = action.get(key)
                if isinstance(values, list):
                    for source in values:
                        cls._append_source(found, source)
        # Current Responses variants may expose cited URLs as message annotations.
        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content in item.get("content") or []:
                    if not isinstance(content, dict):
                        continue
                    for annotation in content.get("annotations") or []:
                        if not isinstance(annotation, dict):
                            continue
                        source = annotation.get("url_citation") if isinstance(annotation.get("url_citation"), dict) else annotation
                        cls._append_source(found, source)
        dedup: dict[str, dict[str, Any]] = {}
        for source in found:
            url = str(source.get("url") or source.get("link") or "").strip()
            merged = dedup.setdefault(url, dict(source))
            for key, value in source.items():
                if value and not merged.get(key):
                    merged[key] = value
        return list(dedup.values())

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @classmethod
    def _candidates(cls, data: dict[str, Any], lane: DiscoveryLaneSpec) -> list[SourceCandidate]:
        retrieved_at = datetime.now(timezone.utc)
        rows: list[SourceCandidate] = []
        for source in cls._extract_source_rows(data):
            url = str(source.get("url") or source.get("link") or "").strip()
            title = str(source.get("title") or source.get("name") or "").strip()
            identity = source_identity(url)
            if not is_safe_url(url) or not identity:
                continue
            rows.append(SourceCandidate(
                title=title,
                url=url,
                description=str(source.get("snippet") or source.get("description") or ""),
                published_at=parse_publication_date(source.get("published_at") or source.get("published") or source.get("datePublished"), url=url),
                retrieved_at=retrieved_at,
                source_name=str(source.get("publisher") or source.get("source") or publisher_domain(url) or "출처"),
                publisher_name=str(source.get("publisher") or source.get("source") or "") or None,
                collector_provider="openai_web_search",
                source_kind=identity[0],
                source_tier=identity[1],
                endpoint_role="discovery",
                metadata={"lane_code": lane.lane_code, "profile_hint": lane.profile_code},
            ))
        return rows

    def _observed_request(self, lane: DiscoveryLaneSpec, budget: DiscoveryBudget, *, retry: bool) -> dict[str, Any]:
        record = budget.begin(lane.lane_code, lane.profile_code, retry=retry)
        try:
            data = self._request(lane)
        except BriefingDiscoveryError as exc:
            budget.finish(record, {"status": "request_failed", "failure_message": str(exc)[:240]})
            raise
        usage = self._usage(data)
        usage.web_tool_calls = len(self._web_items(data))
        usage.search_actions = self._search_count(data)
        usage.search_retry_count = int(retry)
        items = self._web_items(data)
        parse_error = None
        try:
            candidates = self._candidates(data, lane)
        except (TypeError, ValueError, AttributeError, OverflowError) as exc:
            candidates = []
            parse_error = type(exc).__name__
        budget.finish(record, {
            "status": str(data.get("status") or "completed"),
            "response_id": str(data.get("id") or "")[:160] or None,
            "returned_max_tool_calls": data.get("max_tool_calls") if isinstance(data.get("max_tool_calls"), int) else None,
            "usage": asdict(usage), "usage_available": isinstance(data.get("usage"), dict),
            "search_status_counts": self._search_status_counts(data),
            "actions": [{"id": str(item.get("id") or "")[:160] or None,
                         "type": str((item.get("action") or {}).get("type") or "unknown")[:40],
                         "status": str(item.get("status") or "unknown"),
                         "query_count": len(item["action"]["queries"]) if isinstance(item.get("action"), dict) and isinstance(item["action"].get("queries"), list) else len(self._action_queries(item)),
                         "queries": self._action_queries(item)}
                        for item in items[:64] if not item.get("action") or isinstance(item["action"], dict)],
            "source_candidates": [{"title": row.title[:300], "url": row.url,
                                   "source_kind": row.source_kind, "description": row.description[:700],
                                   "published_at": row.published_at.isoformat() if row.published_at else None}
                                  for row in candidates[:40]],
            "candidate_parse_error": parse_error,
        })
        if parse_error:
            raise BriefingDiscoveryError("OpenAI discovery source metadata could not be parsed")
        if data.get("status") in {"failed", "incomplete", "cancelled", "queued", "in_progress"}:
            raise BriefingDiscoveryError("OpenAI discovery response is incomplete or failed")
        return data

    def run_lane(self, lane: DiscoveryLaneSpec, *, budget: DiscoveryBudget | None = None,
                 allow_retry: bool = True, retry: bool = False) -> DiscoveryLaneResult:
        budget = budget or DiscoveryBudget()
        start = len(budget.requests)
        first = self._observed_request(lane, budget, retry=retry)
        usage = self._usage(first)
        usage.web_tool_calls = len(self._web_items(first))
        usage.search_actions = self._search_count(first)
        data = first
        retry_used = retry
        usage.search_retry_count = int(retry)
        if usage.search_actions == 0 and allow_retry and not retry and budget.can_request():
            retry_used = True
            second = self._observed_request(lane, budget, retry=True)
            second_usage = self._usage(second)
            usage.input_tokens += second_usage.input_tokens
            usage.cached_input_tokens += second_usage.cached_input_tokens
            usage.output_tokens += second_usage.output_tokens
            usage.reasoning_tokens += second_usage.reasoning_tokens
            usage.web_tool_calls += len(self._web_items(second))
            second_search = self._search_count(second)
            usage.search_actions += second_search
            usage.search_retry_count = 1
            data = second
        return DiscoveryLaneResult(
            lane_code=lane.lane_code,
            profile_code=lane.profile_code,
            candidates=self._candidates(data, lane) if self._search_performed(data) else [],
            usage=usage,
            search_performed=self._search_performed(data),
            retry_used=retry_used,
            raw_response_id=str(data.get("id") or "") or None,
            request_diagnostics=budget.snapshot()["requests"][start:],
        )
