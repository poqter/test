from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

import requests

from .config import DiscoveryLaneSpec
from .models import DiscoveryLaneResult, DiscoveryUsage, SourceCandidate


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
        if not self.api_key:
            raise BriefingDiscoveryError("OPENAI_API_KEY is not configured")
        if not self.model:
            raise BriefingDiscoveryError("BRIEFING_DISCOVERY_MODEL is not configured")

    def _request(self, lane: DiscoveryLaneSpec) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "input": lane.query,
            "tools": [{"type": "web_search"}],
            "tool_choice": "required",
            "max_tool_calls": 1,
            "include": ["web_search_call.results", "web_search_call.action.sources"],
        }
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
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _usage(data: dict[str, Any]) -> DiscoveryUsage:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
        output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
        return DiscoveryUsage(
            model_name=str(data.get("model") or "") or None,
            service_tier=str(data.get("service_tier") or "") or None,
            input_tokens=int(usage.get("input_tokens") or 0),
            cached_input_tokens=int(input_details.get("cached_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
        )

    @staticmethod
    def _web_items(data: dict[str, Any]) -> list[dict[str, Any]]:
        output = data.get("output")
        return [item for item in output if isinstance(item, dict) and item.get("type") == "web_search_call"] if isinstance(output, list) else []

    @classmethod
    def _search_performed(cls, data: dict[str, Any]) -> bool:
        for item in cls._web_items(data):
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            if action.get("type") == "search":
                return True
        return False

    @staticmethod
    def _append_source(target: list[dict[str, Any]], source: Any) -> None:
        if not isinstance(source, dict):
            return
        url = str(source.get("url") or source.get("link") or "").strip()
        title = str(source.get("title") or source.get("name") or "").strip()
        if url and title:
            target.append(source)

    @classmethod
    def _extract_source_rows(cls, data: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item in cls._web_items(data):
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
            dedup.setdefault(url, source)
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
            if not (url and title):
                continue
            rows.append(SourceCandidate(
                title=title,
                url=url,
                description=str(source.get("snippet") or source.get("description") or ""),
                published_at=cls._parse_datetime(source.get("published_at") or source.get("published") or source.get("date")),
                retrieved_at=retrieved_at,
                source_name=str(source.get("publisher") or source.get("source") or "Web Search"),
                publisher_name=str(source.get("publisher") or source.get("source") or "") or None,
                collector_provider="openai_web_search",
                source_kind="discovery",
                endpoint_role="discovery",
                metadata={"lane_code": lane.lane_code, "profile_hint": lane.profile_code},
            ))
        return rows

    def run_lane(self, lane: DiscoveryLaneSpec) -> DiscoveryLaneResult:
        first = self._request(lane)
        usage = self._usage(first)
        usage.web_tool_calls = len(self._web_items(first))
        usage.search_actions = 1 if self._search_performed(first) else 0
        data = first
        retry_used = False
        if usage.search_actions == 0:
            retry_used = True
            second = self._request(lane)
            second_usage = self._usage(second)
            usage.input_tokens += second_usage.input_tokens
            usage.cached_input_tokens += second_usage.cached_input_tokens
            usage.output_tokens += second_usage.output_tokens
            usage.reasoning_tokens += second_usage.reasoning_tokens
            usage.web_tool_calls += len(self._web_items(second))
            second_search = 1 if self._search_performed(second) else 0
            usage.search_actions += second_search
            usage.search_retry_count = 1
            data = second
        return DiscoveryLaneResult(
            lane_code=lane.lane_code,
            profile_code=lane.profile_code,
            candidates=self._candidates(data, lane) if usage.search_actions else [],
            usage=usage,
            search_performed=usage.search_actions > 0,
            retry_used=retry_used,
            raw_response_id=str(data.get("id") or "") or None,
        )
