from modules.shared.maintenance import blocked
from modules.shared.collection_pages import collect_pages
from modules.consultation.coverage_proposal import _combine

def test_maintenance_is_independent_of_job_title():
    assert blocked('coverage_proposal', {'role':'user','position_code':'branch_manager'})
    assert blocked('newhire-30-v1', {})
    assert not blocked('coverage_proposal', {'role':'super_admin'})
    assert not blocked('academy', {})
    assert not blocked('sales_activity', {})

def test_partial_premium_sum_preserves_unknown_coverages():
    from modules.consultation.coverage_comparison_data import METRICS
    result=_combine([dict(notes='',premium=100000),dict(notes='',premium=None)],'현재')
    assert result['premium']==100000
    assert all(result[k] is None for k in METRICS)
    assert _combine([dict(notes='',premium=0),dict(notes='',premium=30000)],'현재')['premium']==30000

def test_pagination_handles_server_cap_and_stable_order():
    rows=[{'id':str(i)} for i in range(1203)]
    calls=[]
    def fetch(params):
        calls.append(params)
        start=int(params['offset'])
        return rows[start:start+200]
    assert collect_pages(fetch,{'order':'day.asc'})==rows
    assert all(c['order']=='day.asc,id.asc' for c in calls)
    assert calls[-1]['offset']=='1203'

def test_direct_entry_is_guarded():
    from pathlib import Path
    assert "if guard('coverage_proposal'):return" in Path('modules/consultation/coverage_proposal.py').read_text()
    assert "if guard(course['id'],profile):return" in Path('hwarang_academy/education/onboarding.py').read_text()


def test_composite_keys_do_not_reference_nonexistent_id():
    calls=[]
    collect_pages(lambda q: calls.append(q) or [], {}, ('owner','day'))
    assert calls[0]['order']=='owner.asc,day.asc'
