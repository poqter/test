"""Directory preservation, malformed-row isolation and portal user journeys."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from modules.portal_repository import load_catalog, validate_catalog, filter_insurers, safe_url
from test_signature import opened

ROOT = Path(__file__).resolve().parents[1]


class PortalTests(unittest.TestCase):
    def test_original_portals_preserved(self):
        data, issues = load_catalog()
        self.assertEqual(issues, [])
        baseline = json.loads((ROOT/'docs/STAGE7_PORTAL_BASELINE.json').read_text())
        self.assertEqual([{k:r[k] for k in ('name','slug','url')} for r in data['insurers']], baseline['portals'])
        self.assertEqual(len(data['insurers']), 28)

    def test_provenance_is_not_login_verification(self):
        data, _ = load_catalog()
        self.assertEqual(sum(bool(r.get('phone_verified_at')) for r in data['insurers']),18)
        self.assertTrue(all(not r.get('portal_checked_at') for r in data['insurers']))
        self.assertTrue(all(r['phone_source_url'] for r in data['insurers'] if r.get('phone_verified_at')))

    def test_phone_search_and_aliases(self):
        data, _ = load_catalog()
        self.assertEqual(filter_insurers(data['insurers'],'1588 5656'),filter_insurers(data['insurers'],'현대해상'))
        self.assertEqual(filter_insurers(data['insurers'],'현대', '생명보험'), [])
        self.assertEqual(len(filter_insurers(data['insurers'],'현대')),1)

    def test_invalid_entry_does_not_remove_neighbors(self):
        data, _ = load_catalog()
        bad = copy.deepcopy(data)
        bad['insurers'][0]['url']='javascript:alert(1)'
        cleaned, issues=validate_catalog(bad)
        self.assertEqual(len(cleaned['insurers']),27)
        self.assertEqual(len(issues),1)
        for url in ('http://example.com','https://user:pass@example.com','https://example.com/ x'):
            with self.assertRaises(ValueError):safe_url(url)

    def test_missing_catalog_fails_locally(self):
        with patch('pathlib.Path.open',side_effect=OSError):
            data, issues=load_catalog()
        self.assertEqual(data['insurers'],[])
        self.assertTrue(issues)

    def test_favorites_survive_mode_switch(self):
        data,_=load_catalog();slug=data['insurers'][1]['slug']
        at=opened('insurer_portal')
        at.checkbox(key='_ws_f_favorite_'+slug).check().run()
        at.radio(key='f_mode').set_value('기준일').run()
        at.radio(key='f_mode').set_value('즐겨찾기').run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.checkbox),1)
        self.assertTrue(at.checkbox[0].value)

    def test_contact_popup_and_recent(self):
        data,_=load_catalog();slug=data['insurers'][1]['slug']
        at=opened('insurer_portal')
        at.button(key='f_detail_open_'+slug).click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['f_recent_details'],[slug])
        self.assertTrue(at.code)

    def test_form_scope_popup(self):
        at=opened('insurer_portal')
        at.radio(key='f_mode').set_value('서식').run()
        data,_=load_catalog();row=next(r for r in data['resources'] if r['group']=='서식')
        at.button(key='f_resource_open_'+row['id']).click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any('적용 범위' in m.value for m in at.markdown))


if __name__=='__main__':unittest.main()
