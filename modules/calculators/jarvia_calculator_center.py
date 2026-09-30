"""Integrated Hwarang calculator catalog and route dispatcher.

All 88 calculators are local, deterministic tools. No external calculator
service is called at runtime.
"""
from __future__ import annotations
from modules.shared.paths import PROJECT_ROOT

import json

import streamlit as st

from modules.shared.ui_components import page_header

CATALOG = json.loads((PROJECT_ROOT / 'FINANCIAL_CALCULATORS_CATALOG.json').read_text(encoding='utf-8'))
GROUPS = tuple(group['group'] for group in CATALOG['groups'])
GROUP_COUNTS = {group['group']: len(group['calculators']) for group in CATALOG['groups']}
ITEMS = {item['name']: (group['group'], item['description']) for group in CATALOG['groups'] for item in group['calculators']}
ITEM_TAGS = {item['name']: tuple(item.get('tags', ())) for group in CATALOG['groups'] for item in group['calculators']}
ITEM_IDS = {item['id']: item['name'] for group in CATALOG['groups'] for item in group['calculators']}
NAME_TO_ID = {name: item_id for item_id, name in ITEM_IDS.items()}
assert len(ITEMS) == 88
assert sum(GROUP_COUNTS.values()) == 88

def run():
    from modules.calculators.valuation_transfer import apply_pending
    apply_pending()
    notice = st.session_state.pop('jc_transfer_notice', None)
    if notice:
        st.info(notice)
    if not st.session_state.get('jc_open'):
        page_header('화랑 CALCULATOR', '종합 계산기 센터 (88개)', '보험·생활자금·연금·재무·세금·법인 의사결정을 위한 88개 통합 계산 도구', 'QC')
    if notice:
        st.session_state['jc_open'] = st.session_state.get('jc_selected')
    from modules.calculators.catalog_browser import render_catalog, back_to_catalog
    active = st.session_state.get('jc_open')
    if active:
        st.iframe("""<script>(()=>{const w=window.parent,d=w.document;
        if(!w.__hwOpenCalculator)return;w.__hwOpenCalculator=false;
        const main=d.querySelector('[data-testid="stMain"]');
        if(main)main.scrollTop=0;w.scrollTo(0,0);
        })();</script>""",height=1)
        st.button('← 계산기 목록', key='jc_back_catalog', on_click=back_to_catalog)
    # The audited catalog is the single source of truth for public routes.
    # UI-route regression tests exercise every one of the 88 entries.
    implemented = set(ITEMS)
    ready = tuple(ITEMS)
    if not active:
        render_catalog(ITEMS, GROUPS, implemented, tags=ITEM_TAGS, ids=NAME_TO_ID)
        return
    if active in ready:
        selected = active
        from modules.calculators.pension.retirement_models import NAMES as RETIREMENT_NAMES
        from modules.calculators.tax.personal_tax_models import NAMES as PERSONAL_TAX_NAMES
        from modules.calculators.calculator_center import QUICK_CALCULATOR_NAMES
        from modules.calculators.visuals import calculator_title
        st.subheader(calculator_title(selected, ITEMS[selected][0]))
        st.caption(ITEMS[selected][1])
        if selected in QUICK_CALCULATOR_NAMES:
            from modules.calculators.calculator_center import render_quick_calculator
            render_quick_calculator(selected)
            return
        if selected in ('이익소각계산기','법인청산 세부담계산기'):
            from modules.calculators.corporate import profit_retirement; from modules.calculators.corporate import corporate_liquidation
            mod={'이익소각계산기':profit_retirement,'법인청산 세부담계산기':corporate_liquidation}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_seventh
            render_seventh(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-26 · 확인된 과세 조건의 계산')
            return
        if selected in ('명의신탁주식계산기','특수관계자 임대료계산기'):
            from modules.calculators.corporate import nominee_trust; from modules.calculators.corporate import related_party_rent
            mod={'명의신탁주식계산기':nominee_trust,'특수관계자 임대료계산기':related_party_rent}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_ninth
            render_ninth(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인 조건의 계산')
            return
        if selected == '가업승계 세부담계산기':
            from modules.calculators.corporate import business_succession as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_succession
            render_succession(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-26 · 확인된 주식평가액 · 최초 단일 승계')
            return
        if selected == '지주회사 수입배당금계산기':
            from modules.calculators.corporate import holding_company as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_holding
            render_holding(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 국내 단일 피출자법인 · 현행 일반 규정')
            return
        if selected == '고용증대 세액공제계산기':
            from modules.calculators.corporate import employment_credit as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_employment
            render_employment(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 2026년 달력연도 신규 기본공제')
            return
        if selected == '법인 부동산 보유·양도 비교계산기':
            from modules.calculators.corporate import corp_real_estate as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_estate
            render_estate(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 단일 부동산 매각 · 국세 비교')
            return
        if selected in ('키맨리스크계산기','지분 매입자금계산기','승계 재원계산기'):
            from modules.calculators.corporate import corporate_funding as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_funding
            render_funding(selected,mod.FIELDS,mod.calculate,'입력한 조건에 따른 필요 현금·부족액 시나리오')
            return
        if selected in ('주식매수선택권계산기','해외금융계좌 신고계산기'):
            from modules.calculators.corporate import stock_option; from modules.calculators.corporate import overseas_accounts
            from modules.calculators.coverage.coverage_calculator_ui import run as render_options_accounts
            mod=stock_option if selected==stock_option.NAME else overseas_accounts
            render_options_accounts(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 적용 요건 확인 후 계산')
            return
        if selected == '급여vs배당 비교계산기':
            from modules.calculators.corporate import salary_dividend as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_salary_dividend
            render_salary_dividend(selected,mod.FIELDS,mod.calculate,'법령·요율 대조일 2026-09-27 · 동일 본인 세전 수령액 비교')
            return
        if selected == '정책자금 자격진단계산기':
            from modules.calculators.corporate import policy_fund as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_policy
            render_policy(selected,mod.FIELDS,mod.calculate,'공고·법령 대조일 2026-09-27 · 기업규모 및 정책자금 사전 진단')
            return
        if selected == '비상장주식 평가계산기':
            from modules.calculators.corporate import unlisted_valuation as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_valuation
            render_valuation(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 보충적 주식 평가 · 가정 참고값 분리')
            from modules.calculators.valuation_transfer import render as render_transfer
            render_transfer()
            return
        if selected == '취득세 중과계산기':
            from modules.calculators.tax import acquisition_tax as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_acquisition
            render_acquisition(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 확인된 법인 유상취득 · 취득세 본세')
            return
        if selected == '연구인력개발비 세액공제계산기':
            from modules.calculators.corporate import rnd_credit as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_rnd
            render_rnd(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 일반 연구·인력개발비 · 사용 한도 적용 전')
            return
        if selected == '직무발명보상금계산기':
            from modules.calculators.corporate import invention_compensation as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_invention
            render_invention(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 재직·퇴직 후 직무발명보상금 · 국세 비교')
            return
        if selected == '특허권 자본화계산기':
            from modules.calculators.corporate import patent_capitalization as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_patent
            render_patent(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-27 · 개인 종합·분리과세 국세 비교')
            return
        if selected == '합병 세부담계산기':
            from modules.calculators.corporate import merger_tax as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_merger
            render_merger(selected,mod.FIELDS,mod.calculate,'2026년 개시 사업연도 · 법령 대조일 2026-09-26 · 피합병법인 국세 비교')
            return
        if selected == '특정법인 증여의제계산기':
            from modules.calculators.corporate import family_corp_gift as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_allocation
            render_allocation(selected,mod.FIELDS,mod.calculate,'일감몰아주기·특정법인 거래 · 법령 대조일 2026-09-27')
            return
        if selected == '차등배당계산기':
            from modules.calculators.corporate import differential_dividend as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_differential
            render_differential(selected,mod.FIELDS,mod.calculate,'법령 대조일 2026-09-26 · 최초 신고와 정산 구분')
            return
        if selected == '법인보험 만기계산기':
            from modules.calculators.corporate import corporate_insurance_maturity as mod
            from modules.calculators.coverage.coverage_calculator_ui import run as render_maturity
            render_maturity(selected,mod.FIELDS,mod.calculate,'2026년 만기·해약·계약 이전 · 법령 대조일 2026-09-27')
            return
        if selected in ('상여금·복리후생비 비교계산기','사내근로복지기금계산기'):
            from modules.calculators.corporate import bonus_welfare; from modules.calculators.corporate import welfare_fund
            mod={'상여금·복리후생비 비교계산기':bonus_welfare,'사내근로복지기금계산기':welfare_fund}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_sixth
            render_sixth(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected in ('업무용승용차 비용계산기','접대비 한도계산기'):
            from modules.calculators.corporate import vehicle_expense; from modules.calculators.corporate import entertainment_limit
            mod={'업무용승용차 비용계산기':vehicle_expense,'접대비 한도계산기':entertainment_limit}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_fifth
            render_fifth(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected in ('이월결손금계산기','부가세 예정신고 선택계산기'):
            from modules.calculators.corporate import carryforward_loss; from modules.calculators.corporate import vat_preliminary
            mod={'이월결손금계산기':carryforward_loss,'부가세 예정신고 선택계산기':vat_preliminary}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_fourth
            render_fourth(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected in ('성실신고 대상판정계산기','법인 4대보험계산기','법인세 중간예납계산기'):
            from modules.calculators.corporate import sincere_report; from modules.calculators.corporate import corporate_social_insurance; from modules.calculators.corporate import corporate_interim_tax
            mod={'성실신고 대상판정계산기':sincere_report,'법인 4대보험계산기':corporate_social_insurance,'법인세 중간예납계산기':corporate_interim_tax}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_third
            render_third(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected in ('개인사업자·법인 비교계산기','가지급금 정밀진단계산기','DC부담금 한도계산기'):
            from modules.calculators.corporate import corp_vs_individual; from modules.calculators.corporate import deemed_interest_diagnostic; from modules.calculators.corporate import dc_contribution
            mod={'개인사업자·법인 비교계산기':corp_vs_individual,'가지급금 정밀진단계산기':deemed_interest_diagnostic,'DC부담금 한도계산기':dc_contribution}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_corporate_next
            render_corporate_next(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected in ('법인세계산기','인정이자계산기','임원퇴직금 한도계산기'):
            from modules.calculators.corporate import corporate_tax; from modules.calculators.corporate import deemed_interest; from modules.calculators.corporate import executive_severance
            mod={'법인세계산기':corporate_tax,'인정이자계산기':deemed_interest,'임원퇴직금 한도계산기':executive_severance}[selected]
            from modules.calculators.coverage.coverage_calculator_ui import run as render_corporate
            render_corporate(selected,mod.FIELDS,mod.calculate,'2026년 기준 · 법령 대조일 2026-09-26 · 확인된 조건의 계산')
            return
        if selected == '양도소득세계산기':
            from modules.calculators.tax.capital_gains_tax import FIELDS as GF, calculate as gc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_gains
            render_gains(selected,GF,gc,'2026년 일반 부동산 단일 매매 · 법령 대조 기준일 2026-09-26')
            return
        if selected == '상속세계산기':
            from modules.calculators.tax.estate_studio import run as render_estate
            render_estate()
            return
        if selected == '증여세계산기':
            from modules.calculators.tax.gift_planning import run as render_gift
            render_gift()
            return
        if selected == '창업중소기업 세액감면계산기':
            from modules.calculators.tax.startup_tax_credit import FIELDS as CF, calculate as cc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_startup
            render_startup(selected,CF,cc,'2026년 귀속 · 법령 대조 기준일 2026-09-26 · 최저한세 등 조정 전 기본 감면')
            return
        if selected == '4대보험계산기':
            from modules.calculators.tax.social_insurance import FIELDS as SF, calculate as sc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_social
            render_social(selected,SF,sc,'2026년 직장가입자 · 요율 대조 기준일 2026-09-26')
            return
        if selected == '주택담보대출 이자공제계산기':
            from modules.calculators.tax.mortgage_deduction import FIELDS as MF, calculate as mc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_mortgage
            render_mortgage(selected,MF,mc,'2026년 귀속 · 법령 대조 기준일 2026-09-26 · 2024년 이후 신규 취득대출')
            return
        if selected == '종합소득세계산기':
            from modules.calculators.tax.global_income_tax import FIELDS as GF, calculate as gc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_global
            render_global(selected,GF,gc,'2026년 귀속 · 법령 대조 기준일 2026-09-26')
            return
        if selected == '근로소득세계산기':
            from modules.calculators.tax.earned_income_tax import FIELDS as EF, calculate as ec
            from modules.calculators.coverage.coverage_calculator_ui import run as render_earned
            render_earned(selected,EF,ec,'2026년 귀속 · 법령 대조 기준일 2026-09-26')
            return
        if selected == '임대소득세계산기':
            from modules.calculators.tax.rental_tax import FIELDS as RF, calculate as rc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_rental
            render_rental(selected,RF,rc,'2026년 귀속 · 법령 대조 기준일 2026-09-26')
            return
        if selected in PERSONAL_TAX_NAMES:
            from modules.calculators.tax.personal_tax_models import FIELDS as TF, calculate as tc, AS_OF
            from modules.calculators.coverage.coverage_calculator_ui import run as render_tax
            render_tax(selected,TF,tc,'법령 대조 기준일 '+AS_OF+' · 일반 이자·배당 시나리오 · 결과의 적용 범위 확인')
            return
        if selected in RETIREMENT_NAMES:
            from modules.calculators.pension.retirement_models import FIELDS as RF, calculate as rc
            from modules.calculators.coverage.coverage_calculator_ui import run as render_retirement
            render_retirement(selected, RF, rc, '연금·은퇴 계산 · 적용 기준과 가정은 결과에 표시됩니다.')
            return
        if selected == '퇴직금계산기':
            from modules.calculators.pension.severance import run as run_severance
            run_severance()
            return
        if selected == '은퇴저축계산기':
            from modules.calculators.pension.retirement_remaining import FIELDS as SF, saving
            from modules.calculators.coverage.coverage_calculator_ui import run as render_saving
            render_saving(selected,SF,saving,'은퇴 목표 저축 계획')
            return
        if selected == '연금 인출순서계산기':
            from modules.calculators.pension.retirement_remaining import run_order
            run_order()
            return
        if selected == '주택연금계산기':
            from modules.calculators.pension.housing_pension import run as run_housing
            run_housing()
            return
        if selected == '은퇴계산기':
            from modules.calculators.pension.retirement_plan import run as run_retirement_plan
            run_retirement_plan()
            return
        if selected == '연금계산기':
            from modules.calculators.pension.pension_calculator_ui import run as run_pension
            run_pension()
            return
        from modules.calculators.finance.finance_calculator_ui import NAMES, run as run_finance
        if selected in NAMES:
            run_finance(selected)
            return
        from modules.calculators.coverage.coverage_calculator_ui import NAMES as COVERAGE_NAMES, run as run_coverage
        if selected in COVERAGE_NAMES:
            run_coverage(selected)
            return
        st.error("계산기 화면을 불러오지 못했습니다. 계산기 목록으로 돌아가 다시 선택해 주세요.")
        return
