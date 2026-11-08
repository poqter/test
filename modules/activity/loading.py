"""Public calendar structure rendered before the access/context request."""
from calendar import Calendar
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st


def calendar_loading():
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    days = Calendar(firstweekday=0).monthdatescalendar(today.year, today.month)
    cells = ''.join(
        '<div class="hw-calendar-day' + (' is-today' if day == today else '')
        + (' outside' if day.month != today.month else '') + '"><span>'
        + str(day.day) + '</span></div>' for week in days for day in week
    )
    slot = st.empty()
    slot.markdown('''<style>
.hw-calendar-loading{background:#fff;border:1px solid #dce4ef;border-radius:16px;padding:20px;color:#17314f}
.hw-calendar-loading header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.hw-calendar-loading strong{font-size:22px}.hw-calendar-loading [role=status]{font-size:14px;color:#62748b}
.hw-calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}
.hw-calendar-weekday{text-align:center;padding:10px 0;font-size:13px;color:#62748b}
.hw-calendar-day{min-height:90px;border-top:1px solid #e7edf5;padding:8px}
.hw-calendar-day span{display:inline-flex;width:28px;height:28px;align-items:center;justify-content:center}
.hw-calendar-day.is-today span{background:#2e66cf;color:white;border-radius:50%}.hw-calendar-day.outside{color:#aab5c4}
body:has(iframe[title="modules.activity.center.sales_calendar_view"]) .hw-calendar-loading{display:none}
@media(max-width:600px){.hw-calendar-loading{padding:12px}.hw-calendar-day{min-height:65px;padding:4px}.hw-calendar-loading strong{font-size:19px}}
</style><section class="hw-calendar-loading" aria-label="캘린더 불러오기" aria-busy="true">
<header><strong>''' + f'{today.year}년 {today.month}월' + '''</strong><span role="status">일정을 불러오고 있습니다</span></header>
<div class="hw-calendar-grid">''' + ''.join('<div class="hw-calendar-weekday">'+day+'</div>' for day in '월화수목금토일')
        + cells + '</div></section>', unsafe_allow_html=True)
    return slot
