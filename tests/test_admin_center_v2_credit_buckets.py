from __future__ import annotations

from pathlib import Path

from modules.shared.ai_guardrails import (
    TrainingCreditStatus,
    get_training_credit_status,
    training_credit_display_state,
)


ROOT = Path(__file__).resolve().parents[1]


class _Auth:
    def _request(self, method, path, **kwargs):
        assert path.endswith("get_hwarang_ai_entitlement_status")
        return [{
            "training_allocation_credits": 1500,
            "training_balance_credits": 1500,
            "training_reserved_credits": 0,
            "training_available_credits": 1500,
            "training_remaining_percent": 100,
            "monthly_credit_period": "2026-11-01",
            "monthly_grant_credits": 1000,
            "monthly_balance_credits": 1000,
            "monthly_reserved_credits": 0,
            "monthly_available_credits": 1000,
            "purchased_balance_credits": 500,
            "purchased_reserved_credits": 0,
            "purchased_available_credits": 500,
            "training_warning_threshold_credits": 200,
            "training_low": False,
            "voice_allocation_seconds": 0,
            "voice_balance_seconds": 0,
            "voice_reserved_seconds": 0,
            "voice_available_seconds": 0,
            "voice_remaining_percent": 0,
            "voice_low": False,
            "service_enabled": True,
            "text_enabled": True,
            "voice_enabled": False,
            "assessment_enabled": True,
            "soft_limit_percent": 80,
            "remaining_warning_percent": 20,
            "contact_label": "문의",
            "contact_url": "",
        }]


def test_credit_status_exposes_monthly_and_purchased_buckets():
    status = get_training_credit_status(_Auth(), "user-1")
    assert status is not None
    assert status.monthly_grant_credits == 1000
    assert status.monthly_available_credits == 1000
    assert status.purchased_available_credits == 500
    assert status.available_credits == 1500
    assert status.remaining_warning_percent == 20
    assert training_credit_display_state(status)[0] == "여유"


def test_purchased_credit_prevents_false_low_warning():
    status = TrainingCreditStatus(
        allocation_credits=500,
        balance_credits=500,
        available_credits=500,
        monthly_grant_credits=1000,
        monthly_balance_credits=0,
        monthly_available_credits=0,
        purchased_balance_credits=500,
        purchased_available_credits=500,
        warning_threshold_credits=200,
        training_low=False,
        remaining_warning_percent=20,
    )
    label, severity = training_credit_display_state(status)
    assert label in {"보통", "여유"}
    assert severity not in {"warning", "critical", "blocked"}


def test_migration_13_defines_monthly_first_permanent_bucket_policy():
    sql = (ROOT / "supabase/migrations/13_Admin_Center_V2_Credit_Buckets.sql").read_text(encoding="utf-8")
    assert "monthly_free_credits bigint not null default 1000" in sql
    assert "remaining_warning_percent integer not null default 20" in sql
    assert "purchased_balance_credits" in sql
    assert "monthly_balance_credits" in sql
    assert "v_reserve_monthly := least(p_estimated_credits, v_monthly_available)" in sql
    assert "v_actual_monthly := least(p_actual_credits, v_monthly_consumable)" in sql
    assert "Monthly free Training Credit reset (KST)" in sql
    assert "admin_bulk_grant_hwarang_purchased_credits" in sql


def test_admin_center_uses_dedicated_navigation_and_remaining_warning_ui():
    source = (ROOT / "modules/shared/admin_center_ui.py").read_text(encoding="utf-8")
    assert "def render_sidebar()" in source
    assert "← WORKSPACE로 돌아가기" in source
    assert "잔여 이용량 경고 기준" in source
    assert "월 기본 → 구매/추가" in source
    assert "조치 필요" in source
    assert "AI 서비스 긴급 정지 확인" in source


def test_workspace_uses_admin_button_not_toggle():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.button("관리자 센터 →"' in source
    assert 'st.toggle("관리자 센터"' not in source
    assert "render_admin_sidebar()" in source


def test_academy_payload_contains_credit_breakdown():
    source = (ROOT / "academy_app.py").read_text(encoding="utf-8")
    assert '"monthly_available"' in source
    assert '"purchased_available"' in source
    assert '"warning_percent"' in source
