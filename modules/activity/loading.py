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


def calendar_shell(page='캘린더', *, authenticating=False, slot=None):
    """Public labels only; never imply an empty result or expose cached identity."""
    from html import escape
    labels = {
        '캘린더': ('월간 · 주간 · 일간', '일정'),
        '활동 기록': ('일일 기록 · 주간 기록', '활동 기록'),
        '주간 기록': ('일일 기록 · 주간 기록', '주간 기록'),
        '후속 할 일': ('후속 할 일', '할 일 목록'),
        '구성원 현황': ('구성원 현황', '활동 현황'),
        '알림·피드백': ('알림·피드백', '알림 목록'),
    }
    if authenticating or page not in labels:
        page = '캘린더'
    nav, section = labels[page]
    status = '로그인 상태를 확인하고 있습니다.' if authenticating else '내용을 불러오고 있습니다.'
    slot = slot if slot is not None else st.empty()
    slot.markdown('''<style>
.hw-calendar-shell{box-sizing:border-box;min-height:min(620px,78vh);padding:18px;background:#fff;border:1px solid #dce4ef;border-radius:16px;color:#18334c}
.hw-calendar-shell h2{font-size:20px;margin:0 0 20px}.hw-calendar-shell nav{padding:12px 0;border-bottom:1px solid #e2e8ed}
.hw-calendar-shell h3{font-size:17px;margin:20px 0}.hw-calendar-shell .placeholder{height:48px;margin:12px 0;background:#f2f5f8;border-radius:8px}
.st-key-mobile_content,.st-key-mobile_stage{min-height:min(620px,78vh)}
.st-key-mobile_stage{position:relative}
.st-key-mobile_stage .hw-calendar-shell{position:absolute;inset:0;z-index:3}
</style><section class="hw-calendar-shell" aria-busy="true" aria-label="화랑 캘린더 준비">
<h2>화랑 캘린더</h2><nav>''' + escape(nav) + '</nav><h3>' + escape(section) + '</h3><p role="status">' + status + '</p>'
        + '<div class="placeholder" aria-hidden="true"></div>' * 4 + '</section>', unsafe_allow_html=True)
    return slot
