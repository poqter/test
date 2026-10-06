from __future__ import annotations

import json
from datetime import datetime, timezone

from modules.briefing.models import SharedEventCandidate, SourceCandidate
from modules.briefing.openai_analysis import OpenAIAnalysisClient


class FakeResponse:
    status_code = 200
    content = b"{}"
    def json(self):
        return {
            "model": "fixture-model",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({"events": [{
                        "event_key": "e1", "importance_score": 70, "category": "사회·안전",
                        "issue_status": "진행 중", "title": "제목", "summary": "요약",
                        "why_important": "중요", "impact_summary": "영향", "action_state": "reference_today",
                        "communication_state": "not_applicable", "audience_segments": [],
                        "recommended_expression": "", "check_first": "", "avoid_expression": "",
                        "next_step": "확인", "workspace_tool_codes": [], "confidence": "high"
                    }]}, ensure_ascii=False)
                }]
            }]
        }


class FakeSession:
    def __init__(self):
        self.last_json = None
    def post(self, *args, **kwargs):
        self.last_json = kwargs.get("json")
        return FakeResponse()


def test_phase_c_openai_request_is_model_only_structured_output():
    now = datetime.now(timezone.utc)
    source = SourceCandidate(
        title="제목", url="https://example.com/1", source_name="Example", collector_provider="fixture",
        source_kind="news", published_at=now, retrieved_at=now, publisher_domain="example.com",
        freshness_tier="core_window", routed_profiles={"NEWS"},
    )
    event = SharedEventCandidate("e1", "제목", [source], {"NEWS"}, now, now)
    client = OpenAIAnalysisClient(api_key="test", model="fixture-model")
    fake = FakeSession()
    client.http = fake
    rows, usage = client.analyze("NEWS", [event])
    assert rows[0]["event_key"] == "e1"
    assert usage.input_tokens == 10
    assert "tools" not in fake.last_json
    assert fake.last_json["text"]["format"]["type"] == "json_schema"
    assert fake.last_json["text"]["format"]["strict"] is True
