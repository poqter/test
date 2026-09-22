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
    from .calculator_center import run as run_center
    run_center()
