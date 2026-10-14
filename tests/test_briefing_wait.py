from modules.briefing.openai_analysis import OpenAIAnalysisClient

def test_analysis_wait_is_bounded_and_explicit_override_wins(monkeypatch):
    monkeypatch.delenv('BRIEFING_ANALYSIS_TIMEOUT_SECONDS',raising=False)
    assert OpenAIAnalysisClient('test','test').timeout==180
    monkeypatch.setenv('BRIEFING_ANALYSIS_TIMEOUT_SECONDS','9999')
    assert OpenAIAnalysisClient('test','test').timeout==300
    assert OpenAIAnalysisClient('test','test',timeout=42).timeout==42
    monkeypatch.setenv('BRIEFING_ANALYSIS_TIMEOUT_SECONDS','invalid')
    assert OpenAIAnalysisClient('test','test').timeout==180
