"""Approved fixes: pure/reference and API-contract tests, not browser simulation.

The Streamlit adapter here is explicitly a stub with numeric type contracts.
The real pinned-runtime tests live in test_streamlit_runtime.py and are executed
in a separate process so substituting a stub cannot create a false real PASS.
"""
from __future__ import annotations
import copy
import io
import json
import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.streamlit_stub import install
st = install(strict_numeric=True)
from modules.shared.numeric import decimal_number, integer_won, NumericInputError
from modules.calculators import input_design as money_ui
from modules.shared import runtime_cache as cache
from modules.shared import organization as org
from modules.calculators import structured_inputs as structured
from modules.calculators import drafts
from modules.calculators.calculator_core import calculate

ROOT = Path(__file__).resolve().parents[1]

class ApprovedFixes(unittest.TestCase):
    def setUp(self):
        st.session_state.clear(); st.query_params.clear(); st._api.events.clear()
        st._api.clicked.clear(); st._api.edited_tables.clear()
        self.old_db = os.environ.pop('HW_ORGANIZATION_DB', None)
    def tearDown(self):
        if self.old_db is not None: os.environ['HW_ORGANIZATION_DB'] = self.old_db

    def test_strict_money_accepts_exact_values(self):
        for value in (100000, 100000.0, Decimal('100000.0'), '100,000', '100000원'):
            with self.subTest(value=value): self.assertEqual(integer_won(value),100000)
        self.assertEqual(integer_won('0'),0)
        self.assertEqual(integer_won('-12'),-12)
        self.assertIsNone(integer_won('',allow_empty=True))
    def test_invalid_money_never_silently_zero(self):
        for value in (None,'','bad','1,00','12.5',float('nan'),float('inf'),True,'1e3','₩500'):
            with self.subTest(value=repr(value)), self.assertRaises(NumericInputError): integer_won(value)
    def test_remodeling_float_is_not_digit_concatenation(self):
        from modules.consultation.remodeling import money
        for value in (100000,100000.0,'100,000'):
            self.assertEqual(money(value),100000)
        with self.assertRaises(ValueError):money('12.5')
    def test_exact_money_roundtrip(self):
        for amount in (0,1,55000,1048321,123456,10**12):
            st.session_state.clear()
            value=money_ui.number_input('근로소득세액공제 확인액 (원)',value=amount,min_value=0,max_value=10**12,key='confirmed')
            self.assertEqual(value,amount)
            event=[e for e in st._api.events if e['kind']=='number_input'][-1]
            self.assertEqual(event['kwargs']['format'],'%d')
    def test_premium_keeps_every_won(self):
        value=money_ui.number_input('월 보험료 (원)',value=123456,min_value=0,max_value=10**12,key='premium')
        self.assertEqual(value,123456)
        self.assertFalse(money_ui.uses_decimal_manwon('월 보험료 (원)'))
    def test_plan_display_does_not_round_value(self):
        for amount in (2500000,1048321,1,999999999999):
            st.session_state.clear()
            value=money_ui.number_input('목표 금액 (원)',value=amount,min_value=0,max_value=10**12,key='plan',money_policy='plan_manwon')
            self.assertEqual(value,amount)
            self.assertEqual([e for e in st._api.events if e['kind']=='number_input'][-1]['kwargs']['step'],1.0)
    def test_old_money_session_migrates_exactly(self):
        st.session_state['x_manwon_decimal']=12.3456
        value=money_ui.number_input('실제 보험료 (원)',value=100000,min_value=0,max_value=10**12,key='x')
        self.assertEqual(value,123456)
        self.assertNotIn('x_manwon_decimal',st.session_state)
    def test_zero_and_cleared_input_are_distinct(self):
        money_ui.set_money_state('x','확인액',None,policy='exact_won')
        self.assertIsNone(money_ui.number_input('확인액 (원)',min_value=0,max_value=100000,value=3,key='x'))
        money_ui.set_money_state('x','확인액',0,policy='exact_won')
        self.assertEqual(money_ui.number_input('확인액 (원)',min_value=0,max_value=100000,value=3,key='x'),0)
    def test_fraction_of_won_keeps_error_visible_without_snapshot_crash(self):
        st.session_state['plan_money_v3']=0.00001
        st.session_state['hw.money_policy.plan']='plan_manwon'
        self.assertIsNone(money_ui.read_money_state('plan','목표 금액',policy='plan_manwon'))
        value=money_ui.number_input('목표 금액 (원)',value=0,min_value=0,max_value=10**12,key='plan',money_policy='plan_manwon')
        self.assertIsNone(value)
        self.assertTrue(any(e['kind']=='error' for e in st._api.events))
    def test_draft_preserves_temporarily_hidden_field(self):
        state={};drafts.activate('A',state=state)
        state['cov_A_hidden']=321;drafts.capture('A',state=state)
        state.pop('cov_A_hidden');drafts.activate('A',state=state)
        self.assertEqual(state['cov_A_hidden'],321)
    def test_editor_draft_restores_frame_not_widget_delta(self):
        import pandas as pd
        state={};name='이월결손금계산기';drafts.activate(name,state=state)
        frame=pd.DataFrame([{'발생연도':2025,'미사용 잔액(원)':123456}])
        state['hw.table_snapshot.'+name]=frame
        state['ux_table_carryforward']={'edited_rows':{0:{'미사용 잔액(원)':123456}}}
        drafts.capture(name,state=state);drafts.activate('B',state=state);drafts.activate(name,state=state)
        self.assertNotIn('ux_table_carryforward',state)
        self.assertEqual(state['hw.table_base.'+name].iloc[0,1],123456)
    def test_editor_clear_is_not_undone_by_draft(self):
        import pandas as pd
        state={};name='이월결손금계산기';drafts.activate(name,state=state)
        state['hw.table_snapshot.'+name]=pd.DataFrame([{'발생연도':2025,'미사용 잔액(원)':123456}])
        drafts.capture(name,state=state);state.pop('hw.table_snapshot.'+name)
        state['ux_table_reset_mode_'+name]='clear';drafts.activate(name,state=state)
        self.assertNotIn('hw.table_snapshot.'+name,state)
    def test_dataframe_cache_distinguishes_indexes(self):
        import pandas as pd
        a=pd.DataFrame({'금액':[100]},index=[1]);b=pd.DataFrame({'금액':[100]},index=[2])
        self.assertNotEqual(cache.fingerprint(a),cache.fingerprint(b))
    def test_won_symbol_caption_is_readable(self):
        self.assertEqual(money_ui.amount_words(2500000),'250만원')
        self.assertEqual(money_ui.amount_words(1048321),'104만 8,321원')
        self.assertEqual(money_ui.amount_words(-123456),'-12만 3,456원')
    def test_strict_stub_rejects_the_old_mixed_type_bug(self):
        with self.assertRaises(TypeError):st.number_input('old',value=10.0,min_value=0,max_value=74,step=.01)
    def test_float_adapter_homogenizes_types(self):
        self.assertEqual(money_ui.number_input('비율 (%)',value=2.0,min_value=0,max_value=100,step=.1,key='rate'),2.0)
    def test_structured_missing_and_invalid_are_not_zero(self):
        for value in (None,'','invalid',float('nan')):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):structured._won(value)
        self.assertEqual(structured._won(0),0)
    def test_empty_structured_inputs_do_not_restore_examples(self):
        self.assertTrue(structured._parse_loss_ledger('').empty)
        self.assertTrue(structured._parse_wages('').empty)
        self.assertTrue(structured._parse_wages(None).empty)
    def test_structured_ledger_parser_and_bad_years(self):
        df=structured._parse_loss_ledger('2024,123456;2025,0')
        self.assertEqual(df.iloc[0,1],123456)
        for value in ('not-a-row','2026,50','2025,x','2025,'):
            with self.subTest(value=value),self.assertRaises(ValueError):structured._parse_loss_ledger(value)
    def test_partial_table_rows_block_instead_of_disappearing(self):
        import pandas as pd
        rows,errors=structured._validate_rows('test',pd.DataFrame([{'a':2025,'b':None}]),('a','b'))
        self.assertFalse(rows);self.assertTrue(errors)
    def test_explicit_zero_table_row_is_preserved(self):
        import pandas as pd
        rows,errors=structured._validate_rows('test',pd.DataFrame([{'a':2025,'b':0}]),('a','b'))
        self.assertEqual(rows,[{'a':2025,'b':0}]);self.assertFalse(errors)
    def test_clear_table_uses_empty_model(self):
        from modules.calculators.corporate.carryforward_loss import FIELDS
        name='이월결손금계산기';fields=FIELDS[name];values=[v[1] for v in fields]
        structured.reset_table(name,example=False);structured.render(name,fields,values)
        self.assertEqual(values[0],'');self.assertFalse(st.session_state['hw.table_errors.'+name])
    def test_example_table_requires_explicit_action(self):
        from modules.calculators.corporate.carryforward_loss import FIELDS
        name='이월결손금계산기';fields=FIELDS[name];values=[v[1] for v in fields]
        structured.reset_table(name,example=True);structured.render(name,fields,values)
        self.assertNotEqual(values[0],'')
        structured.reset_table(name,example=False);structured.render(name,fields,values)
        self.assertEqual(values[0],'')
    def test_cache_hit_and_input_invalidation(self):
        state={};calls=[]
        def produce(): calls.append(1); return b'payload'
        for _ in range(5):self.assertEqual(cache.cached('x','a',produce,state=state),b'payload')
        self.assertEqual(len(calls),1)
        cache.cached('x','b',produce,state=state);self.assertEqual(len(calls),2)
        self.assertEqual(cache.statistics(state=state)['entries'],1)
    def test_cache_is_session_isolated(self):
        a={};b={}
        cache.cached('x','same',lambda:b'A',state=a)
        self.assertEqual(cache.cached('x','same',lambda:b'B',state=b),b'B')
    def test_cache_does_not_store_errors(self):
        state={};cache.cached('x','old',lambda:b'old',state=state)
        def fail():raise ValueError('test')
        with self.assertRaises(ValueError):cache.cached('x','new',fail,state=state)
        self.assertEqual(cache.statistics(state=state)['entries'],0)
    def test_cache_budget_is_bounded(self):
        state={}
        for i in range(40):cache.cached(str(i),str(i),lambda:b'x'*300,state=state,max_bytes=1000)
        self.assertLessEqual(cache.statistics(state=state)['bytes'],1000)
        self.assertLessEqual(cache.statistics(state=state)['entries'],16)
        cache.clear_scope('',state=state);self.assertEqual(cache.statistics(state=state)['entries'],0)
    def test_cache_fingerprint_includes_content_and_options(self):
        self.assertNotEqual(cache.fingerprint(b'a',{'basis':True}),cache.fingerprint(b'a',{'basis':False}))
        self.assertEqual(cache.fingerprint(io.BytesIO(b'a')),cache.fingerprint(io.BytesIO(b'a')))
    def test_draft_returns_edited_fields_without_auth_or_results(self):
        state={'password_correct':True,'login_user':'Admin'}
        drafts.activate('A',state=state);state['cov_A_0_money_v3']=123456
        state['hw.money_values']={'cov_A_0':123456};state['coverage_result_A']=b'output'
        drafts.capture('A',state=state);drafts.activate('B',state=state)
        self.assertNotIn('cov_A_0_money_v3',state)
        state['cov_B_0_money_v3']=987654;drafts.capture('B',state=state);drafts.activate('A',state=state)
        self.assertEqual(state['cov_A_0_money_v3'],123456)
        self.assertNotIn('password_correct',state[drafts.DRAFT_KEY]['A'])
        self.assertNotIn('coverage_result_A',state[drafts.DRAFT_KEY]['A'])
        self.assertTrue(state['password_correct'])
    def test_safe_error_reporting_excludes_raw_exception(self):
        from modules.shared.error_reporting import record_error,user_message
        secret='FAKE_CUSTOMER_01012345678_C:\\private.xlsx'
        stream=io.StringIO();handler=logging.StreamHandler(stream)
        logger=logging.getLogger('hwarang.errors');logger.addHandler(handler);logger.setLevel(logging.ERROR)
        try:
            try:raise ValueError(secret)
            except ValueError as error:ref=record_error(error,'test.component')
        finally:logger.removeHandler(handler)
        self.assertNotIn(secret,stream.getvalue());self.assertNotIn(secret,user_message(ref))
        self.assertTrue(ref)
    def test_org_profiles_are_versioned_and_scoped(self):
        state={};candidate=org.active_profile(state=state,db_path='')
        candidate.update(brand_name='OrgA',effective_from='2026-01-01')
        org.save_profile(candidate,role='Admin',expected_revision=0,org_id='orgA',state=state,db_path='')
        self.assertEqual(org.active_profile(org_id='orgA',state=state,db_path='')['brand_name'],'OrgA')
        self.assertNotEqual(org.active_profile(org_id='orgB',state=state,db_path='')['brand_name'],'OrgA')
    def test_org_nonadmin_and_stale_revision_rejected(self):
        state={};candidate=org.active_profile(state=state,db_path='')
        with self.assertRaises(PermissionError):org.save_profile(candidate,role='Basic',expected_revision=0,state=state,db_path='')
        org.save_profile(candidate,role='Admin',expected_revision=0,state=state,db_path='')
        with self.assertRaises(ValueError):org.save_profile(candidate,role='Admin',expected_revision=0,state=state,db_path='')
    def test_org_effective_date_and_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'settings.db')
            base=org.active_profile(db_path=path)
            candidate={**base,'brand_name':'Future','effective_from':'2099-01-01'}
            org.save_profile(candidate,role='Admin',expected_revision=0,db_path=path,org_id='A')
            self.assertEqual(org.active_profile(db_path=path,org_id='A',on_date=date(2099,1,1))['brand_name'],'Future')
            self.assertNotEqual(org.active_profile(db_path=path,org_id='A',on_date=date(2026,1,1))['brand_name'],'Future')
            self.assertNotEqual(org.active_profile(db_path=path,org_id='B',on_date=date(2099,1,1))['brand_name'],'Future')
    def test_org_menu_rules_never_grant_new_role_rights(self):
        from modules.shell.navigation import allowed_ids
        from modules.shell.app_registry import ROLE_PERMISSIONS
        for role in ROLE_PERMISSIONS:
            self.assertTrue(set(allowed_ids(role)).issubset(ROLE_PERMISSIONS[role]))
    def test_bad_org_config_is_rejected(self):
        base=org.active_profile(state={},db_path='')
        for update in ({'header_color':'javascript:x'}, {'allowed_tools':['admin_unknown']}, {'commission_default_payout_percent':101}):
            with self.subTest(update=update),self.assertRaises(ValueError):org.validate_profile({**base,**update})
    def test_scopes_describe_all88_without_claiming_new_legal_audit(self):
        rules=json.loads((ROOT/'data/calculator_rules.json').read_text())
        records=rules.get('calculators',rules.get('rules',{}))
        self.assertEqual(len(records),88)
        self.assertTrue(all(not v.get('legal_reverification_date') for v in records.values()))
    def test_home_search_hidden_for_categories(self):
        from modules.calculators.catalog_browser import render_catalog
        from modules.calculators.jarvia_calculator_center import ITEMS,GROUPS,ITEM_TAGS,NAME_TO_ID
        for group,expected in [('전체',True),('보험 기본',False),('연금·은퇴',False)]:
            st.session_state.clear();st._api.events.clear();st.session_state['jc_catalog_group']=group
            render_catalog(ITEMS,GROUPS,set(ITEMS),tags=ITEM_TAGS,ids=NAME_TO_ID)
            purposes=[e for e in st._api.events if e['kind']=='button' and str(e['kwargs'].get('key','')).startswith('jc_purpose_')]
            self.assertEqual(bool(purposes),expected)
    def test_all88_isolated_routes_never_create_navigation(self):
        from modules.calculators.jarvia_calculator_center import ITEMS,run
        for name in ITEMS:
            with self.subTest(name=name):
                st.session_state.clear();st._api.events.clear()
                run(isolated=True,fixed_name=name)
                keys=[e['kwargs'].get('key') for e in st._api.events if e['kind']=='button']
                self.assertNotIn('jc_back_catalog',keys)
                self.assertNotIn('jc_transfer_apply',keys)
                self.assertEqual(st.session_state[drafts.ACTIVE_KEY],name)
    def test_invalid_single_route_never_falls_back_to_catalog(self):
        from modules.calculators.jarvia_calculator_center import run
        run(isolated=True,fixed_name='unknown')
        self.assertFalse(any(e['kind']=='button' and 'jc_card' in str(e['kwargs']) for e in st._api.events))
    def test_search_clear_and_sidebar_navigation(self):
        from modules.calculators.calculator_shell import _show_catalog
        from modules.calculators.catalog_browser import save_query,back_to_catalog
        st.session_state.update(jc_catalog_group='전체',jc_search='증여')
        save_query();st.session_state['jc_open']='증여세계산기';back_to_catalog()
        self.assertEqual(st.session_state['jc_catalog_query'],'증여')
        _show_catalog('연금·은퇴')
        self.assertEqual(st.session_state['jc_catalog_query'],'')
        self.assertNotIn('jc_open',st.session_state)
    def test_pdf_safe_operators_preserve_numbers(self):
        from modules.shared.report_fonts import pdf_text
        self.assertEqual(pdf_text('−55,000 × 2 ≤ 110,000'),'-55,000  x  2 <= 110,000')
        self.assertIn('123,456원',pdf_text('✨ 123,456원'))

if __name__=='__main__':unittest.main(verbosity=2)
