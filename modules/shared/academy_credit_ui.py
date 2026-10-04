"""User-facing Training Credit + VOICE allowance strip for HWARANG ACADEMY."""
from __future__ import annotations

import html

import streamlit as st

from modules.shared.ai_guardrails import (
    TrainingCreditStatus,
    credit_display_state,
    voice_display_state,
)


def _bar(
    *,
    title: str,
    percent: float,
    label: str,
    severity: str,
) -> str:
    p = max(0.0, min(float(percent or 0), 100.0))
    return f"""
      <div class="hw-usage-row" data-state="{html.escape(severity)}">
        <span class="hw-usage-title">{html.escape(title)}</span>
        <div class="hw-usage-bar"><div class="hw-usage-fill" style="width:{p:.1f}%"></div></div>
        <span class="hw-usage-percent">{p:.0f}% 남음</span>
        <span class="hw-usage-state">{html.escape(label)}</span>
      </div>
    """


def render_training_credit_strip(status: TrainingCreditStatus | None) -> None:
    """Show user-facing entitlement without exposing API currency/cost."""
    if not status or not status.is_configured:
        return

    rows: list[str] = []
    low_any = False

    if status.allocation_credits > 0 or status.text_enabled or status.assessment_enabled:
        label, severity = credit_display_state(
            status.remaining_percent,
            allocation_credits=status.allocation_credits,
        )
        rows.append(
            _bar(
                title="훈련 크레딧",
                percent=status.remaining_percent,
                label=label,
                severity=severity,
            )
        )
        low_any = low_any or (
            status.allocation_credits > 0
            and status.remaining_percent <= 10
        )

    if status.voice_is_configured:
        label, severity = voice_display_state(
            status.voice_remaining_percent,
            allocation_seconds=status.voice_allocation_seconds,
        )
        rows.append(
            _bar(
                title="음성 이용량",
                percent=status.voice_remaining_percent,
                label=label,
                severity=severity,
            )
        )
        low_any = low_any or (
            status.voice_allocation_seconds > 0
            and status.voice_remaining_percent <= 10
        )

    if not rows:
        return

    contact = ""
    if status.contact_url and low_any:
        contact = (
            f'<a class="hw-usage-contact" href="{html.escape(status.contact_url)}" '
            f'target="_blank" rel="noopener noreferrer">'
            f'{html.escape(status.contact_label)} →</a>'
        )

    st.markdown(
        f"""
        <style>
        .hw-usage-shell{{
          margin:0 0 10px;padding:10px 14px;
          border:1px solid #dce7f2;border-radius:14px;background:#fff;
          box-shadow:0 5px 18px rgba(35,73,105,.06);
          color:#17344f
        }}
        .hw-usage-row{{
          display:grid;grid-template-columns:92px minmax(110px,1fr) 66px 94px;
          gap:12px;align-items:center;min-height:28px
        }}
        .hw-usage-row+.hw-usage-row{{border-top:1px solid #edf2f7;margin-top:7px;padding-top:7px}}
        .hw-usage-title{{font-size:12px;font-weight:850;white-space:nowrap}}
        .hw-usage-bar{{height:7px;background:#edf2f7;border-radius:99px;overflow:hidden}}
        .hw-usage-fill{{height:100%;background:#2f6fa8;border-radius:99px}}
        .hw-usage-row[data-state="warning"] .hw-usage-fill{{background:#b47b2c}}
        .hw-usage-row[data-state="critical"] .hw-usage-fill,
        .hw-usage-row[data-state="blocked"] .hw-usage-fill{{background:#b64e4e}}
        .hw-usage-percent{{font-size:12px;color:#6d8398;white-space:nowrap;text-align:right}}
        .hw-usage-state{{font-size:12px;font-weight:800;white-space:nowrap}}
        .hw-usage-contact{{
          display:inline-block;margin-top:8px;font-size:12px;font-weight:800;
          color:#2268ad;text-decoration:none
        }}
        @media(max-width:700px){{
          .hw-usage-row{{grid-template-columns:88px 1fr 64px}}
          .hw-usage-state{{grid-column:2/4}}
        }}
        </style>
        <div class="hw-usage-shell">
          {''.join(rows)}
          {contact}
        </div>
        """,
        unsafe_allow_html=True,
    )

    training_exhausted = (
        status.allocation_credits > 0 and status.available_credits <= 0
    )
    voice_exhausted = (
        status.voice_allocation_seconds > 0
        and status.voice_available_seconds <= 0
    )

    if training_exhausted and voice_exhausted:
        st.info(
            "훈련 크레딧과 음성 이용량을 모두 사용했습니다. "
            "진행 중인 학습 기록은 유지됩니다. 추가 이용은 관리자에게 문의해 주세요."
        )
    elif training_exhausted:
        st.info(
            "텍스트 AI·코칭·정식평가 이용량을 모두 사용했습니다. "
            "학습 기록은 유지됩니다. 추가 이용은 관리자에게 문의해 주세요."
        )
    elif voice_exhausted:
        st.info(
            "음성 이용량을 모두 사용했습니다. 텍스트 훈련은 남은 훈련 크레딧 범위에서 계속 이용할 수 있습니다. "
            "추가 음성 이용은 관리자에게 문의해 주세요."
        )
