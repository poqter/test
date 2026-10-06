"""Per-request discovery guard; observed usage never gets clamped to the cap."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .config import SHARED_DISCOVERY_HARD_LIMIT

DISCOVERY_REQUEST_HARD_LIMIT = 6  # four primary lanes plus at most two retries
REQUEST_TOOL_CALL_LIMIT = 1


class DiscoveryBudgetError(RuntimeError):
    pass


class DiscoveryBudget:
    def __init__(self, on_response: Callable[[dict[str, Any]], None] | None = None):
        self.requests: list[dict[str, Any]] = []
        self.search_actions = 0
        self.web_tool_calls = 0
        self.on_response = on_response

    def can_request(self) -> bool:
        return (len(self.requests) < DISCOVERY_REQUEST_HARD_LIMIT
                and self.search_actions + REQUEST_TOOL_CALL_LIMIT <= SHARED_DISCOVERY_HARD_LIMIT)

    def begin(self, lane_code: str, profile_code: str, *, retry: bool) -> dict[str, Any]:
        if not self.can_request():
            raise DiscoveryBudgetError("Shared Discovery request blocked before API call: budget exhausted")
        record = {"request_no": len(self.requests) + 1, "lane_code": lane_code,
                  "profile_code": profile_code, "retry": retry,
                  "requested_max_tool_calls": REQUEST_TOOL_CALL_LIMIT,
                  "status": "started", "usage": None, "usage_available": False}
        self.requests.append(record)
        return record

    def finish(self, record: dict[str, Any], details: dict[str, Any]) -> None:
        record.update(details)
        usage = record.get("usage") or {}
        self.search_actions += int(usage.get("search_actions") or 0)
        self.web_tool_calls += int(usage.get("web_tool_calls") or 0)
        record["cumulative_search_actions"] = self.search_actions
        record["tool_limit_anomaly"] = int(usage.get("web_tool_calls") or 0) > REQUEST_TOOL_CALL_LIMIT
        # Persist each observed response before checking its actual tool count.
        # A provider-side overshoot has already happened; never hide that cost.
        if self.on_response:
            self.on_response(deepcopy(record))
        if self.search_actions > SHARED_DISCOVERY_HARD_LIMIT:
            raise DiscoveryBudgetError("Shared Discovery hard limit exceeded in API response; further calls stopped")

    def snapshot(self) -> dict[str, Any]:
        return {"search_action_hard_limit": SHARED_DISCOVERY_HARD_LIMIT,
                "request_hard_limit": DISCOVERY_REQUEST_HARD_LIMIT,
                "requested_max_tool_calls": REQUEST_TOOL_CALL_LIMIT,
                "request_count": len(self.requests), "observed_search_actions": self.search_actions,
                "observed_web_tool_calls": self.web_tool_calls,
                "usage_unknown_requests": sum(not r.get("usage_available") for r in self.requests),
                "requests": deepcopy(self.requests)}
