from modules.shared.ai_guardrails import credit_display_state, make_idempotency_key


def test_credit_display_state_boundaries():
    assert credit_display_state(100, allocation_credits=1000)[0] == "매우 여유"
    assert credit_display_state(75, allocation_credits=1000)[0] == "여유"
    assert credit_display_state(50, allocation_credits=1000)[0] == "보통"
    assert credit_display_state(20, allocation_credits=1000)[0] == "얼마 남지 않음"
    assert credit_display_state(5, allocation_credits=1000)[0] == "이용량 추가 필요"
    assert credit_display_state(0, allocation_credits=1000)[0] == "이용 한도 도달"
    assert credit_display_state(100, allocation_credits=0)[0] == "이용량 미지급"


def test_idempotency_key_is_stable_and_turn_scoped():
    a = make_idempotency_key(
        user_id="u1",
        academy_session_id="s1",
        turn_no=3,
        purpose="customer",
        payload_fingerprint="abc",
    )
    b = make_idempotency_key(
        user_id="u1",
        academy_session_id="s1",
        turn_no=3,
        purpose="CUSTOMER",
        payload_fingerprint="abc",
    )
    c = make_idempotency_key(
        user_id="u1",
        academy_session_id="s1",
        turn_no=4,
        purpose="CUSTOMER",
        payload_fingerprint="abc",
    )
    assert a == b
    assert a != c
    assert len(a) == 64


def test_sql_migration_has_no_normal_per_minute_limit():
    from pathlib import Path
    sql = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "09_Admin_Operations_AI_Guardrails.sql"
    ).read_text(encoding="utf-8")
    assert "requests_per_minute" not in sql
    assert "reserve_hwarang_ai_request" in sql
    assert "hwarang_ai_credit_ledger" in sql
    assert "hwarang_ai_session_locks" in sql
