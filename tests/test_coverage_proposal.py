from io import BytesIO
from pypdf import PdfReader
from modules.consultation.coverage_comparison_data import _classify, _amount, format_coverage
from modules.consultation.coverage_brief_report import briefing_pdf, comparison_pdf
from modules.consultation.analyzer_sample import sample_workbook
from modules.consultation.analyzer_model import parse_source_file
from modules.shell.app_registry import ROLE_PERMISSIONS, APP_BY_ID


def test_diagnoses_are_not_confused_with_narrower_or_condition_specific_coverages():
    assert _classify('암진단비(유사암제외)') == '일반암'
    assert _classify('유사암진단비') == '유사암'
    assert _classify('뇌혈관질환진단비') == '뇌혈관질환'
    assert _classify('뇌졸중진단비') is None
    assert _classify('뇌출혈진단비') is None
    assert _classify('급성심근경색증진단비') is None
    assert _classify('뇌혈관질환산정특례대상진단비') is None
    assert _classify('허혈성심장질환진단비') == '허혈성심장질환'
    assert _classify('허혈성심장질환수술비') == '뇌·심장 치료'


def test_money_units_and_unverified_values():
    assert _amount('3천만') == 30_000_000
    assert _amount('6백만') == 6_000_000
    assert _amount('2,000만원') == 20_000_000
    assert format_coverage(None) == '확인 필요'
    assert format_coverage(0) == '0원 (확인됨)'


def test_reports_generate_embedded_korean_text_and_unknowns():
    parsed = parse_source_file(sample_workbook())
    doc=PdfReader(BytesIO(briefing_pdf(parsed)))
    text=''.join(p.extract_text() or '' for p in doc.pages)
    assert '현재 보험 보장 브리핑' in text
    current={'name':'현재 보험','premium':238092,'일반암':30000000,'유사암':None,'뇌혈관질환':10000000,'허혈성심장질환':10000000,'notes':''}
    plan={'name':'제안','premium':None,'일반암':30000000,'유사암':None,'뇌혈관질환':10000000,'허혈성심장질환':10000000,'notes':''}
    doc=PdfReader(BytesIO(comparison_pdf(current,[plan],'제안','보장기간 확인','')))
    text=''.join(p.extract_text() or '' for p in doc.pages)
    assert '뇌혈관질환' in text and '허혈성심장질환' in text
    assert '확인 필요' in text and '추천 제안' in text
    assert '뇌출혈 진단금' not in text


def test_menu_available_to_all_standard_roles():
    assert APP_BY_ID['coverage_proposal'].module_path=='modules.consultation.coverage_proposal'
    assert all('coverage_proposal' in ROLE_PERMISSIONS[role] for role in ('Admin','Manager1','Basic','Crew','Dream'))


def test_default_organization_allows_proposal_menu():
    from modules.shared.organization import active_profile, permitted_tools
    assert 'coverage_proposal' in active_profile(db_path='', state={})['allowed_tools']
    assert 'coverage_proposal' in permitted_tools(['coverage_proposal'])


def test_multiple_contracts_preserve_unknowns_and_keep_conditions_visible():
    from modules.consultation.coverage_proposal import _combine
    a={'premium':100000, '일반암':30000000, '유사암':None, '뇌혈관질환':10000000, '허혈성심장질환':0, 'notes':'첫 계약의 조건'}
    b={'premium':20000, '일반암':10000000, '유사암':5000000, '뇌혈관질환':None, '허혈성심장질환':10000000, 'notes':'두 번째 계약의 조건'}
    combined=_combine([a,b],'현재 보험')
    assert combined['premium']==120000 and combined['일반암']==40000000
    assert combined['유사암'] is None and combined['뇌혈관질환'] is None
    assert combined['허혈성심장질환']==10000000
    assert '첫 계약의 조건' in combined['notes'] and '두 번째 계약의 조건' in combined['notes']


def test_pdf_comparison_supports_multiple_proposals_without_treating_unknown_as_zero():
    current={'name':'현재','premium':10000,'일반암':None,'유사암':None,'뇌혈관질환':None,'허혈성심장질환':None,'notes':''}
    plans=[{**current,'name':f'제안 {i}'} for i in range(6)]
    doc=PdfReader(BytesIO(comparison_pdf(current,plans,'제안 5','조건 확인','면책기간 확인')))
    text=''.join(p.extract_text() or '' for p in doc.pages)
    assert all(f'제안 {i}' in text for i in range(6))
    assert '확인 필요' in text
