from modules.shared import operations


def test_report_incidents_copy_only_diagnostic_fields():
    incidents = {'incidents': [{
        'session_id': '12345678-aaaa-bbbb-cccc-123456789012',
        'purpose': 'EVALUATOR',
        'reason': 'evidence_quote_mismatch',
        'recorded_at': '2026-11-14T03:00:00Z',
        'credit_status': 'failed',
        'credits_charged': 0,
        'cost_status': 'unknown',
        'raw_dialogue': '원본이 복사되면 안 됩니다.',
    }]}

    issue, = operations.studio_report_issues(incidents)
    request = operations.request_text([issue])
    assert '2026-11-14 12:00 KST' in request
    assert '학습자 원문과 인용 불일치' in request
    assert '예약 해제 · 0 Credit' in request
    assert '공급자 비용 금액 미확인' in request
    assert '원본이 복사되면 안 됩니다.' not in request
