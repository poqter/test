from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from modules.briefing.clustering import cluster_candidates
from modules.briefing.config import DISCOVERY_LANES, SHARED_DISCOVERY_HARD_LIMIT, SHARED_DISCOVERY_SOFT_LIMIT, SHARED_DISCOVERY_TARGET
from modules.briefing.gates import route_profiles
from modules.briefing.models import SourceCandidate
from modules.briefing.normalize import canonicalize_url, classify_freshness, normalize_candidate
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient


class BriefingPhaseBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_of = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)

    def candidate(self, title: str, url: str, hours_old: int = 2) -> SourceCandidate:
        return SourceCandidate(
            title=title,
            url=url,
            source_name="테스트",
            collector_provider="fixture",
            source_kind="news",
            published_at=self.as_of - timedelta(hours=hours_old),
        )

    def test_shared_discovery_contract(self) -> None:
        self.assertEqual(len(DISCOVERY_LANES), 4)
        self.assertEqual(SHARED_DISCOVERY_TARGET, 4)
        self.assertEqual(SHARED_DISCOVERY_SOFT_LIMIT, 5)
        self.assertEqual(SHARED_DISCOVERY_HARD_LIMIT, 6)
        self.assertEqual([x.lane_code for x in DISCOVERY_LANES], [
            "official_industry", "trusted_media", "official_wire_broadcast", "general_economic_media"
        ])

    def test_freshness_gate(self) -> None:
        self.assertEqual(classify_freshness(self.as_of - timedelta(hours=36), self.as_of), "core_window")
        self.assertEqual(classify_freshness(self.as_of - timedelta(hours=37), self.as_of), "light_window")
        self.assertEqual(classify_freshness(self.as_of - timedelta(hours=96), self.as_of), "light_window")
        self.assertEqual(classify_freshness(self.as_of - timedelta(hours=97), self.as_of), "stale")
        self.assertEqual(classify_freshness(None, self.as_of), "undated")

    def test_url_tracking_removed(self) -> None:
        self.assertEqual(canonicalize_url("https://Example.com/a/?utm_source=x&b=2#z"), "https://example.com/a?b=2")

    def test_insurance_social_insurance_false_positive_removed(self) -> None:
        row = self.candidate("2026 국민건강보험료 계산 방법", "https://example.com/a")
        normalize_candidate(row, as_of=self.as_of)
        self.assertNotIn("INSURANCE", route_profiles(row, "INSURANCE"))

    def test_cross_profile_policy_event(self) -> None:
        row = self.candidate("금융당국 보험 모집 규제 시행 변경", "https://example.com/b")
        normalize_candidate(row, as_of=self.as_of)
        routed = route_profiles(row, "INSURANCE")
        self.assertIn("INSURANCE", routed)
        self.assertIn("NEWS", routed)

    def test_conservative_cluster(self) -> None:
        a = self.candidate("금융당국 보험 모집 규제 시행 변경", "https://a.example/1")
        b = self.candidate("금융당국 보험 모집 규제 시행 변경 발표", "https://b.example/2")
        for row in (a, b):
            normalize_candidate(row, as_of=self.as_of)
            row.routed_profiles = {"INSURANCE"}
        events = cluster_candidates([a, b])
        self.assertEqual(len(events), 1)
        self.assertEqual(len(events[0].candidates), 2)


    def test_lane_retry_is_bounded_to_one(self) -> None:
        class FakeClient(OpenAIWebDiscoveryClient):
            def __init__(self):
                self.responses = [
                    {"id": "r1", "model": "fixture", "output": [{"type": "web_search_call", "action": {"type": "open_page"}}]},
                    {"id": "r2", "model": "fixture", "output": [{"type": "web_search_call", "action": {"type": "search", "sources": []}}]},
                ]
            def _request(self, lane):
                return self.responses.pop(0)

        result = FakeClient().run_lane(DISCOVERY_LANES[0])
        self.assertTrue(result.search_performed)
        self.assertTrue(result.retry_used)
        self.assertEqual(result.usage.search_retry_count, 1)
        self.assertEqual(result.usage.search_actions, 1)
        self.assertEqual(len(result.candidates), 0)

    def test_search_action_detection(self) -> None:
        payload = {"output": [{"type": "web_search_call", "action": {"type": "search", "sources": []}}]}
        self.assertTrue(OpenAIWebDiscoveryClient._search_performed(payload))
        payload = {"output": [{"type": "web_search_call", "action": {"type": "open_page"}}]}
        self.assertFalse(OpenAIWebDiscoveryClient._search_performed(payload))


if __name__ == "__main__":
    unittest.main()
