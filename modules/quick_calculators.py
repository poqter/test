"""A1-A6: transparent scenario calculators; no external API or persistence."""
import calendar
from datetime import date
import streamlit as st
from .ui_components import page_header
from .workspace_tools import field, session_notice, source_notes


def add_months(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def age_result(birth, reference):
    if birth > reference:
        raise ValueError("생년월일은 기준일보다 늦을 수 없습니다.")
    years = reference.year - birth.year
    if add_months(birth, years * 12) > reference:
        years -= 1
    threshold = add_months(birth, years * 12 + 6)
    insurance = years + int(reference >= threshold)
    next_change = threshold if reference < threshold else add_months(birth, (years + 1) * 12 + 6)
    return years, insurance, next_change


def total_premium(amount, months, paid_months):
    if min(amount, months, paid_months) < 0 or paid_months > months:
        raise ValueError("기납입 개월은 전체 납입 개월 이하여야 합니다.")
    return amount * months, amount * paid_months, amount * (months - paid_months)


def coverage_gap(monthly, years, debt, one_off, assets, existing):
    need = monthly * 12 * years + debt + one_off
    return need, max(0, need - assets - existing)


def money(label, key, value=0):
    return field("number_input", label + " (만원)", key, value, min_value=0, max_value=10000000, step=10)


def run():
    page_header("빠른 계산", "상담 퀵 계산기", "단위와 가정을 확인하며 필요한 숫자를 빠르게 계산합니다.", "QC")
    session_notice("a_")
    mode=st.radio("계산 선택",("보험나이", "다음 상령일", "총 납입보험료", "필요 보장액", "소득 공백·비상자금", "납입면제 효과"),horizontal=True,key="a_mode")
    if mode in ("보험나이", "다음 상령일"):
        birth=field("date_input","생년월일","a_birth",date(1990,1,1),min_value=date(1900,1,1),max_value=date.today())
        reference=field("date_input","신규 가입 가정 기준일","a_reference",date.today(),min_value=date(1900,1,1),max_value=date(2100,12,31))
        try:
            years,insurance,change=age_result(birth,reference)
            cols=st.columns(3)
            cols[0].metric("만 나이",f"{years}세")
            cols[1].metric("신규 가입 보험나이",f"{insurance}세")
            cols[2].metric("다음 상령일",change.isoformat())
            st.info(f"다음 변경일까지 {(change-reference).days}일 · 생일로부터 6개월 이상인 끝수는 1년으로 계산합니다.")
            st.caption("신규 가입 참고 계산입니다. 기존 계약의 보험나이 증가는 계약해당일 기준일 수 있습니다. 월말은 해당 월 말일로 보정하며 윤일·상품별 예외는 보험사 전산에서 확인하세요. 보험료 인상률을 예측하지 않습니다.")
        except ValueError as exc: st.error(str(exc))
        source_notes(["보험나이"])
    elif mode == "총 납입보험료":
        amount=money("월 보험료","a_premium",10)
        months=field("number_input","전체 납입 개월","a_months",240,min_value=0,max_value=1200)
        paid=field("number_input","기납입 개월","a_paid",0,min_value=0,max_value=1200)
        try:
            values=total_premium(amount,months,paid)
            for col,label,val in zip(st.columns(3),("총 납입 예정","기납입 추정","향후 납입 예정"),values): col.metric(label,f"{val:,.0f}만원")
        except ValueError as exc: st.error(str(exc))
        st.caption("월 보험료 × 개월 수. 보험료가 일정하다는 가정이며 갱신·감액·중도해지·할인 및 투자수익은 반영하지 않습니다.")
    elif mode == "필요 보장액":
        monthly=money("유족 월 생활비","a_living",250)
        years=field("number_input","생활비 준비 기간 (년)","a_years",10,min_value=0,max_value=60)
        debt=money("정리할 부채","a_debt",10000)
        oneoff=money("교육비 등 일시 필요액","a_oneoff",3000)
        assets=money("사용 가능한 금융자산","a_assets",5000)
        existing=money("해당 위험에 지급되는 기존 보장","a_existing",5000)
        need,gap=coverage_gap(monthly,years,debt,oneoff,assets,existing)
        a,b=st.columns(2); a.metric("총 필요 재원",f"{need:,.0f}만원"); b.metric("가정상 부족 재원",f"{gap:,.0f}만원")
        st.caption("생활비 × 12 × 기간 + 부채 + 일시 필요액 − 가용자산 − 동일 지급사유의 기존 보장. 물가·수익률·세금 제외. 권장 가입금액이나 판매 적합성 판정이 아닙니다.")
    elif mode == "소득 공백·비상자금":
        spending=money("월 필수지출","a_spending",250)
        income=money("공백 중 유지되는 월 소득","a_income",0)
        duration=field("number_input","공백 기간 (개월)","a_duration",6,min_value=0,max_value=120)
        reserve=money("이미 마련한 비상자금","a_reserve",500)
        monthly=max(0,spending-income); target=monthly*duration
        a,b,c=st.columns(3); a.metric("월 부족액",f"{monthly:,.0f}만원"); b.metric("기간 필요액",f"{target:,.0f}만원"); c.metric("추가 준비액",f"{max(0,target-reserve):,.0f}만원")
        st.caption("기간 필요액 = max(필수지출 − 유지소득, 0) × 공백 개월. 비상자금 사용 가능성·가족의 실제 상황을 별도로 확인합니다.")
    else:
        premium=money("월 보험료","a_waiver_premium",10)
        remain=field("number_input","남은 납입 개월","a_remain",120,min_value=0,max_value=1200)
        eligible=field("slider","납입면제 대상 보험료 비율 (%)","a_eligible",100,min_value=0,max_value=100)
        st.metric("면제 조건 충족 가정 시 향후 면제액",f"{premium*remain*eligible/100:,.0f}만원")
        st.caption("월 보험료 × 남은 개월 × 대상 비율. 면제 발생 가능성·현재가치·환급금은 계산하지 않습니다. 실제 면제 사유, 제외 특약, 갱신 후 적용 여부는 약관 확인이 필요합니다.")
