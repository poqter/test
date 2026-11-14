"""Release maintenance gates, independent of account permissions."""
MAINTENANCE = {
    "fp-foundation-v2": "새 FP 교육 과정과 고객 미션을 검수하고 있습니다.",
    "coverage_proposal": "보장비교 보고서의 합산과 고객용 출력을 점검하고 있습니다.",
    "newhire-30-v1": "수업 구성과 학습 화면을 보완하고 있습니다.",
}

def blocked(key, profile):
    return key in MAINTENANCE and (profile or {}).get("role") != "super_admin"

def guard(key, profile=None):
    import streamlit as st
    if profile is None:
        profile = (st.session_state.get("hwarang_auth") or {}).get("profile") or {}
    if blocked(key, profile):
        st.info("🔒 기능 정비 중 · " + MAINTENANCE[key])
        return True
    if key in MAINTENANCE:
        st.caption("관리자 검수용 · 일반 사용자에게는 잠겨 있습니다.")
    return False
