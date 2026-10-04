"""User-facing Training Credit strip for HWARANG ACADEMY."""
from __future__ import annotations

import html
import streamlit as st

from modules.shared.ai_guardrails import TrainingCreditStatus, credit_display_state


def render_training_credit_strip(status: TrainingCreditStatus | None) -> None:
    """Render only after credit/runtime is actually configured.

    Before paid AI launch (service disabled and no allocation), nothing is shown.
    """
    if not status or not status.is_configured:
        return

    label, severity = credit_display_state(
        status.remaining_percent,
        allocation_credits=status.allocation_credits,
    )
    percent = max(0.0, min(float(status.remaining_percent), 100.0))
    contact = ""
    if status.contact_url and (percent <= 10 or status.available_credits <= 0):
        contact = (
            f'<a class="hw-credit-contact" href="{html.escape(status.contact_url)}" '
            f'target="_blank" rel="noopener noreferrer">'
            f'{html.escape(status.contact_label)} →</a>'
        )

    st.markdown(
        f"""
        <style>
        .hw-credit-strip{{
            display:flex;align-items:center;gap:14px;
            margin:0 0 10px;padding:10px 14px;
            border:1px solid #dce7f2;border-radius:14px;background:#fff;
            box-shadow:0 5px 18px rgba(35,73,105,.06);
            color:#17344f;
        }}
        .hw-credit-title{{font-size:12px;font-weight:850;white-space:nowrap}}
        .hw-credit-bar{{flex:1;min-width:110px;height:7px;background:#edf2f7;border-radius:99px;overflow:hidden}}
        .hw-credit-fill{{height:100%;width:{percent:.1f}%;background:#2f6fa8;border-radius:99px}}
        .hw-credit-state{{font-size:12px;font-weight:800;white-space:nowrap}}
        .hw-credit-percent{{font-size:12px;color:#6d8398;white-space:nowrap}}
        .hw-credit-contact{{font-size:12px;font-weight:800;color:#2268ad;text-decoration:none;white-space:nowrap}}
        @media(max-width:700px){{
          .hw-credit-strip{{flex-wrap:wrap}}
          .hw-credit-bar{{order:4;flex-basis:100%}}
        }}
        </style>
        <div class="hw-credit-strip" data-state="{html.escape(severity)}">
          <span class="hw-credit-title">훈련 크레딧</span>
          <div class="hw-credit-bar"><div class="hw-credit-fill"></div></div>
          <span class="hw-credit-percent">{percent:.0f}% 남음</span>
          <span class="hw-credit-state">{html.escape(label)}</span>
          {contact}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if status.available_credits <= 0 and status.allocation_credits > 0:
        st.info(
            "AI 훈련 이용량을 모두 사용했습니다. 진행 중인 학습 기록은 유지됩니다. "
            "추가 이용이 필요하면 관리자에게 문의해 주세요."
        )
