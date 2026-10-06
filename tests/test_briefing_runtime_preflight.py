import os
from unittest.mock import patch

from modules.briefing.direct_sources import DirectSourceSpec
from modules.briefing.preflight import preflight_ready, run_runtime_preflight


def test_preflight_passes_with_runtime_config_and_verified_source():
    env = {
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SECRET_KEY": "secret",
        "OPENAI_API_KEY": "key",
        "BRIEFING_DISCOVERY_MODEL": "model",
    }
    specs = [DirectSourceSpec("official", "Official", "https://example.org/feed", profile_hints=("NEWS",))]
    with patch.dict(os.environ, env, clear=True):
        checks = run_runtime_preflight(direct_sources=specs)
    assert preflight_ready(checks)
    assert any(c.code == "routine_model" and c.ok for c in checks)


def test_preflight_blocks_placeholder_or_missing_runtime_config():
    specs = [DirectSourceSpec("placeholder", "Placeholder", "https://VERIFIED.example/feed")]
    with patch.dict(os.environ, {}, clear=True):
        checks = run_runtime_preflight(direct_sources=specs)
    assert not preflight_ready(checks)
    failed = {c.code for c in checks if c.required and not c.ok}
    assert "openai_api_key" in failed
    assert "direct_sources" in failed
