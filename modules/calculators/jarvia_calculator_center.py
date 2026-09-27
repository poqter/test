"""Local calculator catalog inspired by the authenticated JARVIA list.

Only modes with verified local engines are selectable. No requests to JARVIA.
"""
from __future__ import annotations
from modules.shared.paths import PROJECT_ROOT

import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from pathlib import Path

import streamlit as st

from modules.shared.ui_components import page_header

CATALOG = json.loads((PROJECT_ROOT / 'FINANCIAL_CALCULATORS_CATALOG.json').read_text(encoding='utf-8'))
GROUPS = tuple(group['group'] for group in CATALOG['groups'])
ITEMS = {item['name']: (group['group'], item['description']) for group in CATALOG['groups'] for item in group['calculators']}
assert len(ITEMS) == 80

# Monthly deposits occur at the end of each month; amounts are in won.
FIELDS = {
    '미래가치계산기': [('principal','처음 투자할 금액',10000000),('rate','예상 수익률 (연간, %)',6.0),('years','투자 기간 (년)',20),('annual','매년 추가할 금액',200000),('timing','추가 납입 시기','매년 초')],
    '복리계산기': [('principal','초기 투자금액 (원금)',10000000),('rate','연 이자율 (%)',5.0),('years','투자 기간 (년)',10),('frequency','복리 계산 주기','월간')],
    '투자수익계산기': [('principal','투자 원금',10000000),('monthly','월 추가 투자액',0),('years','투자 기간 (년)',10),('rate','연 유효수익률 (%)',3.0)],
    '현재가치계산기': [('target','미래 금액',100000000),('years','기간 (년)',10),('rate','연 할인율 (%)',3.0)],
    '목표자금 계획계산기': [('target','목표 금액',100000000),('principal','현재 자금',10000000),('years','기간 (년)',10),('rate','연 유효수익률 (%)',3.0)],
    '수익률계산기': [('target','목표 금액',100000000),('principal','현재 자금',10000000),('years','기간 (년)',10),('rate','연 유효수익률 (%)',3.0)],
    '비상자금 진단계산기': [('spending','월 필수지출',2500000),('income','유지되는 월 소득',0),('reserve','보유 비상자금',5000000),('months','목표 준비 기간 (개월)',6)],
    '기회비용계산기': [('monthly','매월 지출액',100000),('years','기간 (년)',10),('rate','대안 연 유효수익률 (%)',3.0)],
    '연금계산기': [('principal','연금 시작 시 자금',300000000),('years','수령 기간 (년)',25),('rate','연 운용수익률 가정 (%)',2.0)],
    '은퇴계산기': [('age','현재 나이',40),('retire','은퇴 나이',65),('end','계획 종료 나이',90),('living','월 생활비',3000000),('pension','월 예상 연금',1500000),('assets','은퇴 시점 가용자금',100000000),('inflation','연 물가상승률 가정 (%)',2.0)],
    '은퇴크레바스계산기': [('months','퇴직 후 연금 개시까지 (개월)',60),('spending','월 필수지출',2500000),('income','유지되는 월 소득',0),('reserve','사용 가능한 준비금',10000000)],
    '3층연금 점검계산기': [('income','은퇴 전 월 소득',5000000),('national','국민연금 월 수령 예상',1000000),('occupational','퇴직연금 월 수령 예상',700000),('private','개인연금 월 수령 예상',500000)],
    '은퇴저축계산기': [('target','은퇴 시 목표자금',500000000),('principal','현재 자금',50000000),('years','은퇴까지 기간 (년)',20),('rate','연 유효수익률 (%)',3.0)],
    '사망보장 필요액계산기': [('living','유족 월 생활비',2500000),('years','준비 기간 (년)',10),('debt','정리할 부채',100000000),('oneoff','일시 필요액',30000000),('assets','가용 자산',50000000),('existing','기존 사망보장',50000000)],
    '중대질병 보장계산기': [('treatment','예상 치료비',30000000),('living','월 생활비',2500000),('months','소득 공백 (개월)',12),('income','유지되는 월 소득',0),('existing','기존 진단 보장',10000000),('assets','가용 자산',0)],
    '간병·장기요양 필요액계산기': [('care','월 간병·요양 비용',3000000),('months','돌봄 예상 기간 (개월)',36),('support','월 공적급여·지원 예상',500000),('income','월 가용 소득',0),('assets','준비 자금',10000000)],
    '자녀보험 필요액계산기': [('treatment','예상 치료비',30000000),('daily','1일 간병·입원 부대비',100000),('days','예상 기간 (일)',30),('education','학업 유지 자금',10000000),('existing','기존 보장·준비금',10000000)],
    '적정보험료계산기': [('income','월 가처분 소득',5000000),('premium','월 납입 보험료',500000),('ratio','보험료 예산 비율 가정 (%)',10.0)],
    '정기·종신 비교계산기': [('term','월 정기보험료',100000),('whole','월 종신보험료',400000),('years','비교 기간 (년)',20),('rate','차액 투자 연수익률 가정 (%)',3.0)],
    '의료비 부담계산기': [('medical','예상 총 의료비',10000000),('covered','실손 예상 보험금',5000000),('extra','보장 제외 비용',0)],
    '재무계산기': [('principal','현재 금융자산',10000000),('monthly','월 저축액',500000),('years','기간 (년)',10),('rate','연 유효수익률 (%)',3.0)],
}
D = lambda value: Decimal(str(value))
WON = Decimal('1')


def compute(name: str, raw: dict) -> tuple[dict[str, str], str]:
    """Calculate with Decimal; return customer values and advisor formula."""
    if name not in FIELDS:
        raise ValueError('아직 계산 기능이 준비되지 않았습니다.')
    v = {key: D(value) for key, value in raw.items() if key not in ('timing','frequency')}
    if any(value < 0 for key, value in v.items() if key != 'rate') or v.get('years', D(1)) <= 0 or v.get('months', D(1)) <= 0:
        raise ValueError('금액은 0 이상, 기간은 1 이상이어야 합니다.')
    if v.get('rate', D(0)) <= -100:
        raise ValueError('연 수익률은 -100%보다 커야 합니다.')
    years, annual = v.get('years', D(1)), v.get('rate', D(0)) / 100
    monthly_rate = (D(1) + annual) ** (D(1) / 12) - 1
    count = int(years * 12)
    factor = (D(1) + monthly_rate) ** count
    annuity = (factor - 1) / monthly_rate if monthly_rate else D(count)
    initial, monthly = v.get('principal', D(0)), v.get('monthly', D(0))
    fmt = lambda amount: f'{amount.quantize(WON, rounding=ROUND_HALF_UP):,}원'
    if name == '미래가치계산기':
        annual_growth = D(1) + annual
        annual_factor = ((annual_growth ** int(years) - 1) / annual) if annual else years
        contribution = v['annual'] * annual_factor * (annual_growth if raw['timing'] == '매년 초' else D(1))
        future = initial * annual_growth ** int(years) + contribution
        invested = initial + v['annual'] * years
        return {'최종 금액 (미래 가치)':fmt(future),'처음 투자 금액':fmt(initial),'추가 저축 총액':fmt(v['annual']*years),'총 이자 수익':fmt(future-invested)}, '처음 투자액 × (1+연 수익률)^연수 + 매년 추가액 × 연금종가계수 × (연초 납입이면 1+연 수익률); JARVIA 화면의 연초·연말 선택과 대조'
    if name == '복리계산기':
        periods = {'월간':12,'연간':1,'분기별':4,'반기별':2,'일간':365}[raw['frequency']]
        future = initial * (D(1) + annual / periods) ** (int(years) * periods)
        shown = future.quantize(WON, rounding=ROUND_DOWN)
        return {'최종 금액':fmt(shown),'초기 투자금액':fmt(initial),'총 이자 수익':fmt(shown-initial)}, '원금 × (1+연 명목 이자율 ÷ 연 복리 횟수)^(기간 × 연 복리 횟수); 추가 적립 없음. 결과는 JARVIA 기본 사례에 맞춰 원 미만 절사'
    if name in ('투자수익계산기','재무계산기'):
        future = initial * factor + monthly * annuity
        return {'예상 미래 자금': fmt(future), '납입 원금 합계':fmt(initial + monthly * count), '예상 운용 차액':fmt(future - initial - monthly * count)}, '미래 자금 = 현재 자금 × (1+월수익률)^개월 + 월말 적립액 × 누적 적립계수'
    if name == '현재가치계산기':
        return {'미래 금액의 현재가치':fmt(v['target'] / (D(1)+annual) ** years)}, '현재가치 = 미래 금액 ÷ (1+연 할인율)^기간'
    if name == '목표자금 계획계산기':
        gap = max(D(0), v['target'] - initial * factor)
        return {'목표 달성에 필요한 월 저축액':fmt(gap / annuity),'현재 자금의 예상 미래가치':fmt(initial * factor)}, '월말 저축액 = max(0, 목표 금액 − 현재 자금의 미래가치) ÷ 누적 적립계수'
    if name == '수익률계산기':
        gap = max(D(0), v['target'] - initial * factor)
        return {'목표 달성에 필요한 월 저축액':fmt(gap / annuity)}, '목표자금 계획과 같은 월말 적립 산식을 사용합니다. 이름과 달리 이 화면은 필요 저축액을 계산합니다.'
    if name == '비상자금 진단계산기':
        shortfall = max(D(0), v['spending']-v['income'])
        return {'버틸 수 있는 기간':('지출 부족액 없음' if shortfall == 0 else f'{(v["reserve"]/shortfall).quantize(D("0.1"),rounding=ROUND_HALF_UP):,}개월'),'목표 비상자금':fmt(shortfall * v['months']),'추가로 필요한 금액':fmt(max(D(0),shortfall*v['months']-v['reserve']))}, '목표 비상자금 = max(0, 월 필수지출 − 유지되는 월 소득) × 목표 개월'
    if name == '기회비용계산기':
        return {'매월 지출한 총액':fmt(monthly*count),'대안 적립 시 예상 금액':fmt(monthly*annuity),'예상 운용 차액':fmt(monthly*(annuity-count))}, '기회비용 = 월말 동일 금액을 적립한 경우의 예상 미래 자금'
    return compute_insurance_pension(name, v, fmt, factor, annuity, count)



def compute_insurance_pension(name, v, fmt, factor, annuity, count):
    """Scenario models; benefits, contract exclusions and tax are not inferred."""
    zero = D(0)
    if name == '사망보장 필요액계산기':
        from modules.calculators.calculator_core import calculate
        result = calculate('coverage', v)
        return {key:fmt(value) for key,value in result.items()}, '기존 화랑 필요 보장액 계산식 통합: 월 생활비 × 12 × 준비기간 + 부채 + 일시 필요액 − 가용 자산 − 기존 보장'
    if name == '은퇴계산기':
        from modules.calculators.calculator_core import calculate
        result = calculate('retirement', {**v,'inflation':v['inflation']/100})
        return {key:fmt(value) for key,value in result.items()}, '기존 화랑 은퇴 생활자금 계산식 통합: 물가 반영 월 부족액 × 12 × 은퇴 기간 − 은퇴 시점 가용자금'
    if name == '은퇴크레바스계산기':
        from modules.calculators.calculator_core import calculate
        result = calculate('income',{**v,'duration':v['months']})
        return {key:fmt(value) for key,value in result.items()}, '기존 화랑 소득 공백 계산식 통합: max(0, 월 필수지출 − 유지 소득) × 공백 기간 − 준비금'
    if name == '중대질병 보장계산기':
        monthly = max(zero, v['living']-v['income'])
        need = v['treatment'] + monthly*v['months']
        return {'가정상 필요액':fmt(need),'추가 필요 보장액':fmt(max(zero,need-v['existing']-v['assets']))}, '예상 치료비 + max(0, 월 생활비 − 유지 소득) × 소득 공백 기간 − 기존 보장 − 가용 자산'
    if name == '간병·장기요양 필요액계산기':
        monthly = max(zero,v['care']-v['support']-v['income'])
        return {'월 가정상 부족액':fmt(monthly),'추가 준비액':fmt(max(zero,monthly*v['months']-v['assets']))}, '월 부족액 = max(0, 예상 간병비 − 공적급여·지원 − 가용 소득); 추가 준비액 = 월 부족액 × 기간 − 준비 자금'
    if name == '자녀보험 필요액계산기':
        need = v['treatment']+v['daily']*v['days']+v['education']
        return {'총 예상 비용':fmt(need),'추가 준비액':fmt(max(zero,need-v['existing']))}, '예상 치료비 + 일당 부대비 × 기간 + 학업 유지 자금 − 기존 보장·준비금'
    if name == '적정보험료계산기':
        if v['income'] == 0:
            raise ValueError('월 가처분 소득은 0보다 커야 합니다.')
        budget=v['income']*v['ratio']/100
        return {'보험료의 소득 대비 비율':f'{(v["premium"]/v["income"]*100).quantize(D("0.1")):,}%','설정한 보험료 예산':fmt(budget),'예산 대비 여유액':fmt(max(zero,budget-v['premium']))}, '보험료 ÷ 가처분 소득 × 100; 예산은 사용자가 입력한 비율로 계산하며 적정 가입 비율 판정이 아닙니다.'
    if name == '정기·종신 비교계산기':
        if v['whole'] < v['term']:
            raise ValueError('차액 적립 비교에는 종신보험료가 정기보험료 이상이어야 합니다.')
        saving=(v['whole']-v['term'])*annuity
        return {'정기보험 총 납입액':fmt(v['term']*count),'종신보험 총 납입액':fmt(v['whole']*count),'보험료 차액 투자 시 예상 적립액':fmt(saving)}, '정기·종신 보장 내용과 해지환급금은 비교하지 않음; 매월 보험료 차액을 월말에 투자한 시나리오'
    if name == '의료비 부담계산기':
        if v['covered'] > v['medical']:
            raise ValueError('예상 실손 보험금은 예상 총 의료비보다 클 수 없습니다.')
        return {'실손 미가입 가정 부담액':fmt(v['medical']+v['extra']),'실손 가입 가정 부담액':fmt(v['medical']-v['covered']+v['extra']),'보장 차액':fmt(v['covered'])}, '총 의료비 − 입력한 예상 보험금 + 별도 보장 제외 비용; 실손 세대별 공제 및 지급 가능 여부는 판정하지 않음'
    if name == '연금계산기':
        if annuity <= 0:
            raise ValueError('수령 기간과 수익률을 확인해 주세요.')
        payout=v['principal']*factor/annuity
        return {'월말 정액 인출 가능액':fmt(payout),'예상 총 인출액':fmt(payout*count)}, '월 인출액 = 연금 시작 자금 × (1+월 수익률)^수령개월 ÷ 누적 적립계수; 연금보험 지급률과 세금은 미반영'
    if name == '3층연금 점검계산기':
        if v['income'] <= 0:
            raise ValueError('은퇴 전 월 소득은 0보다 커야 합니다.')
        total=v['national']+v['occupational']+v['private']
        return {'월 연금 합계':fmt(total),'소득대체율':f'{(total/v["income"]*100).quantize(D("0.1")):,}%'}, '국민연금 + 퇴직연금 + 개인연금; 소득대체율 = 월 연금 합계 ÷ 은퇴 전 월 소득'
    if name == '은퇴저축계산기':
        gap=max(zero,v['target']-v['principal']*factor)
        return {'목표 달성 월 저축액':fmt(gap/annuity),'현재 자금의 예상 미래가치':fmt(v['principal']*factor)}, '기존 화랑 목표 달성 월 저축액 산식 통합: 월말 정액 적립 기준 목표 부족액 ÷ 누적 적립계수'
    raise ValueError('아직 계산 기능이 준비되지 않았습니다.')

def run(run_legacy):
    from modules.calculators.valuation_transfer import apply_pending
    if st.session_state.pop('jc_home_entry', False):
        for k in ('jc_open','jc_selected','jc_search','jc_catalog_query','jc_catalog_group','jc_catalog_last','jc_catalog_restore','jc_group','jc_transfer_notice'):
            st.session_state.pop(k, None)
    linked = st.session_state.pop('jc_link_entry', None)
    if linked in ITEMS:
        from modules.shared.session_store import reset_page
        reset_page('quick_calculators')
        st.session_state['jc_open'] = linked
        st.session_state['jc_selected'] = linked
    dedicated = bool(st.session_state.get("hw_calc_locked"))
    if not dedicated: apply_pending()
    notice=st.session_state.pop('jc_transfer_notice',None)
    if notice:st.info(notice)
    if not dedicated and not st.session_state.get('jc_open'):
        page_header('재무·보험 계산', '재무·보험 계산기', '업무별 계산기와 결과를 확인하세요', 'QC')
    if notice:
        st.session_state['jc_open'] = st.session_state.get('jc_selected')
    from modules.calculators.catalog_browser import render_catalog, back_to_catalog
    active = st.session_state.get('jc_open')
    if active and not dedicated:
        with st.container(horizontal=True, vertical_alignment='center'):
            st.button('← 계산기 목록', key='jc_back_catalog', on_click=back_to_catalog)
            from modules.calculators.catalog_browser import new_tab_link
            if active in ITEMS:
                new_tab_link(active)
                from modules.calculators.dedicated_tab import render_launcher
                render_launcher([active])
    from modules.calculators.pension.retirement_models import NAMES as RETIREMENT_NAMES
    from modules.calculators.tax.personal_tax_models import NAMES as PERSONAL_TAX_NAMES
    implemented = set(FIELDS) | {'연금계산기','주택연금계산기','은퇴저축계산기','연금 인출순서계산기','퇴직금계산기'} | set(RETIREMENT_NAMES)
    implemented |= set(PERSONAL_TAX_NAMES)
    implemented.add('임대소득세계산기')
    implemented.add('근로소득세계산기')
    implemented.add('종합소득세계산기')
    implemented.add('주택담보대출 이자공제계산기')
    implemented.add('4대보험계산기')
    implemented.add('창업중소기업 세액감면계산기')
    implemented.add('증여세계산기')
    implemented.add('상속세계산기')
    implemented.add('양도소득세계산기')
    implemented.update(('이익소각계산기','법인청산 세부담계산기'))
    implemented.add('차등배당계산기')
    implemented.add('특정법인 증여의제계산기')
    implemented.add('합병 세부담계산기')
    implemented.add('특허권 자본화계산기')
    implemented.add('직무발명보상금계산기')
    implemented.add('연구인력개발비 세액공제계산기')
    implemented.update(('키맨리스크계산기','지분 매입자금계산기','승계 재원계산기'))
    implemented.update(('주식매수선택권계산기','해외금융계좌 신고계산기'))
    implemented.add('급여vs배당 비교계산기')
    implemented.add('정책자금 자격진단계산기')
    implemented.add('비상장주식 평가계산기')
    implemented.add('취득세 중과계산기')
    implemented.add('법인 부동산 보유·양도 비교계산기')
    implemented.add('고용증대 세액공제계산기')
    implemented.add('지주회사 수입배당금계산기')
    implemented.add('가업승계 세부담계산기')
    implemented.update(('명의신탁주식계산기','특수관계자 임대료계산기'))
    implemented.add('법인보험 만기계산기')
    implemented.update(('상여금·복리후생비 비교계산기','사내근로복지기금계산기'))
    implemented.update(('업무용승용차 비용계산기','접대비 한도계산기'))
    implemented.update(('이월결손금계산기','부가세 예정신고 선택계산기'))
    implemented.update(('성실신고 대상판정계산기','법인 4대보험계산기','법인세 중간예납계산기'))
    implemented.update(('개인사업자·법인 비교계산기','가지급금 정밀진단계산기','DC부담금 한도계산기'))
    implemented.update(('법인세계산기','인정이자계산기','임원퇴직금 한도계산기'))
    ready = [name for name in ITEMS if name in implemented]
    if not active:
        render_catalog(ITEMS, GROUPS, implemented)
        return
    if active == '__basic__':
        run_legacy()
        return
    if active in ready:
        selected = active
        st.subheader(selected)
        st.caption(ITEMS[selected][1])
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
            from modules.calculators.tax.estate_calculator import FIELDS as IF, calculate as ic
            from modules.calculators.coverage.coverage_calculator_ui import run as render_estate
            render_estate(selected,IF,ic,'2026년 거주자 일반 상속 · 법령 대조 기준일 2026-09-26')
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
        from modules.shared.page_layouts import work_panels
        _input_panel, _result_panel = work_panels("general_calculator")
        with _input_panel:
            st.caption('계산식 구현 초안 · 원본 화면 대조 진행 중')
            with st.form('jc_form'):
                values = {}
                for key,label,default in FIELDS[selected]:
                    if key == 'timing':
                        values[key] = st.selectbox(label,['매년 초','매년 말'])
                    elif key == 'frequency':
                        values[key] = st.selectbox(label,['월간','연간','분기별','반기별','일간'])
                    elif key in ('rate','inflation','ratio'):
                        values[key] = st.number_input(label,value=float(default),min_value=-99.99 if key != 'ratio' else 0.0,max_value=100.0,step=0.1)
                    else:
                        values[key] = st.number_input(label,value=int(default),min_value=1 if key in ('years','months','days') else 0,max_value=120 if key in ('years','age','retire','end') else 1200 if key in ('months','days') else 10**12,step=1 if key in ('years','months','days','age','retire','end') else 10000)
                submit = st.form_submit_button('계산하기', type='primary')
            if submit:
                try:
                    output, formula = compute(selected, values)
                except (ValueError, OverflowError, ArithmeticError) as exc:
                    st.warning(str(exc))
                    st.session_state.pop('jc_result',None)
                else:
                    st.session_state['jc_result'] = (selected, values, output, formula)
        with _result_panel:
            result = st.session_state.get('jc_result')
            if result and result[0] == selected and result[1] == values:
                _, _, output, formula = result
                customer, advisor = st.tabs(['고객용 결과','설계사용 상세 계산'])
                with customer:
                    st.subheader(selected)
                    for label, val in output.items():
                        st.metric(label,val)
                    st.caption('입력한 조건에 따른 가정값입니다. 실제 수익이나 가입 결과를 보장하지 않습니다.')
                with advisor:
                    st.markdown('**적용 조건**')
                    for key,label,_ in FIELDS[selected]:
                        st.write(f'{label}: {values[key] if key in ("timing","frequency") else format(values[key], ",")}' + ('%' if key in ('rate','inflation','ratio') else ''))
                    st.markdown('**계산식**')
                    st.write(formula)
                    st.caption(f'계산일: {date.today().isoformat()} · 입력 조건에 따른 시나리오 · 세금 및 수수료 별도')
