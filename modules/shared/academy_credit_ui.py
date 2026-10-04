"""User-facing Training Credit + Voice allowance strip for HWARANG ACADEMY."""
from __future__ import annotations

import html

import streamlit as st

from modules.shared.ai_guardrails import (
    TrainingCreditStatus,
    training_credit_display_state,
    voice_display_state,
)


def _safe_percent(value: float) -> float:
    return max(0.0, min(float(value or 0), 100.0))


def render_training_credit_strip(status: TrainingCreditStatus | None) -> None:
    """Show user entitlement without exposing API currency/cost.

    Credits may already exist in the DB before paid AI launch. They stay hidden
    while the global AI service is OFF so users are not shown a quota for a
    feature that cannot yet consume it.
    """
    if not status or not status.service_enabled:
        return

    training_label, training_severity = training_credit_display_state(status)
    training_percent = _safe_percent(status.remaining_percent)

    voice_label, voice_severity = voice_display_state(
        status.voice_remaining_percent,
        allocation_seconds=status.voice_allocation_seconds,
        warning_percent=status.remaining_warning_percent,
    )
    voice_percent = _safe_percent(status.voice_remaining_percent)

    show_training = status.text_enabled or status.assessment_enabled or status.available_credits > 0
    show_voice = status.voice_enabled or status.voice_allocation_seconds > 0
    if not show_training and not show_voice:
        return

    rows: list[str] = []
    if show_training:
        rows.append(
            f"""
            <div class="hw-credit-row" data-state="{html.escape(training_severity)}">
              <div>
                <div class="hw-credit-name">훈련 크레딧</div>
                <div class="hw-credit-detail">이번 달 기본 {status.monthly_available_credits:,} · 구매 크레딧 {status.purchased_available_credits:,}</div>
              </div>
              <div class="hw-credit-bar"><div class="hw-credit-fill" style="width:{training_percent:.1f}%"></div></div>
              <div class="hw-credit-value">{status.available_credits:,}</div>
              <div class="hw-credit-state">{html.escape(training_label)}</div>
            </div>
            """
        )

    if show_voice:
        rows.append(
            f"""
            <div class="hw-credit-row" data-state="{html.escape(voice_severity)}">
              <div>
                <div class="hw-credit-name">음성 이용량</div>
                <div class="hw-credit-detail">Voice는 훈련 크레딧과 별도 관리됩니다.</div>
              </div>
              <div class="hw-credit-bar"><div class="hw-credit-fill" style="width:{voice_percent:.1f}%"></div></div>
              <div class="hw-credit-value">{status.voice_available_seconds / 60:.0f}분</div>
              <div class="hw-credit-state">{html.escape(voice_label)}</div>
            </div>
            """
        )

    training_low = show_training and status.training_low
    voice_low = show_voice and status.voice_low
    contact = ""
    if status.contact_url and (training_low or voice_low or status.available_credits <= 0):
        contact = (
            f'<a class="hw-credit-contact" href="{html.escape(status.contact_url)}" '
            f'target="_blank" rel="noopener noreferrer">'
            f'{html.escape(status.contact_label)} →</a>'
        )

    st.markdown(
        f"""
        <style>
        .hw-credit-shell{{margin:0 0 12px;padding:10px 14px;border:1px solid #e0e8f1;border-radius:15px;background:#fff;box-shadow:0 5px 18px rgba(35,73,105,.05);color:#183750}}
        .hw-credit-row{{display:grid;grid-template-columns:minmax(180px,1.4fr) minmax(140px,1fr) 86px 88px;gap:14px;align-items:center;padding:5px 0}}
        .hw-credit-row+.hw-credit-row{{border-top:1px solid #edf2f7;margin-top:7px;padding-top:12px}}
        .hw-credit-name{{font-size:12px;font-weight:850}}
        .hw-credit-detail{{margin-top:2px;font-size:11px;color:#7b8da0}}
        .hw-credit-bar{{height:7px;border-radius:99px;background:#edf2f7;overflow:hidden}}
        .hw-credit-fill{{height:100%;border-radius:99px;background:#2d6ca3}}
        .hw-credit-row[data-state="warning"] .hw-credit-fill{{background:#b17a2e}}
        .hw-credit-row[data-state="critical"] .hw-credit-fill,.hw-credit-row[data-state="blocked"] .hw-credit-fill{{background:#b74b4b}}
        .hw-credit-value{{font-size:13px;font-weight:900;text-align:right}}
        .hw-credit-state{{font-size:11px;font-weight:800;text-align:right;white-space:nowrap}}
        .hw-credit-contact{{display:inline-block;margin-top:8px;font-size:12px;font-weight:800;color:#2268ad;text-decoration:none}}
        @media(max-width:760px){{.hw-credit-row{{grid-template-columns:1fr 90px}}.hw-credit-bar{{grid-column:1/3}}.hw-credit-state{{text-align:left}}}}
        </style>
        <div class="hw-credit-shell">
          {''.join(rows)}
          {contact}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if show_training and status.available_credits <= 0:
        st.info(
            "훈련 크레딧을 모두 사용했습니다. 학습 기록은 유지됩니다. "
            "추가 이용이 필요하면 관리자에게 문의해 주세요."
        )
    elif training_low:
        st.caption(
            f"훈련 크레딧이 기본 제공량 기준 {status.remaining_warning_percent}% 이하 구간입니다. "
            "구매 크레딧은 만료되지 않으며 기본 크레딧이 먼저 사용됩니다."
        )
