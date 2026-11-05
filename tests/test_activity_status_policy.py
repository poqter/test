from unittest.mock import Mock
from modules.activity.status_policy import unregistered_exclusions, summary_groups


def test_only_unregistered_seniors_are_excluded():
    states={'leader':'미등록','deputy':'미등록','team':'미등록','senior_active':'일정 있음','senior_empty':'일정 없음'}
    groups=summary_groups(states,{uid:uid for uid in states},{'leader','senior_active','senior_empty'})
    assert groups['미등록']==['deputy','team']
    assert groups['일정 있음']==['senior_active']
    assert groups['일정 없음']==['senior_empty']


def test_position_filter_is_scoped_and_not_system_role():
    auth=Mock();auth._request.return_value=[{'id':'one'}]
    assert unregistered_exclusions(auth,['one','two'])=={'one'}
    params=auth._request.call_args.kwargs['params']
    assert params['id']=='in.(one,two)'
    assert params['position_code']=='in.(branch_manager,division_head,chief_representative)'
    assert params['select']=='id'
    assert 'role' not in params


def test_empty_candidates_skip_query():
    auth=Mock()
    assert unregistered_exclusions(auth,[])==set()
    auth._request.assert_not_called()
