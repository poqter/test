from unittest.mock import Mock
import pytest
from modules.briefing.repository import BriefingRepository, BriefingRepositoryError
from test_briefing_release import bundle


def sharing_repo():
    repo = BriefingRepository('https://example.org', 'synthetic')
    repo.operating_policy = lambda: {'external_sharing_approved': True}
    repo.bundle_for_date = lambda code, day: bundle(code, day)
    repo.public_endpoint_ready = lambda: True
    repo.public_base_url = lambda: 'https://example.org'
    repo._upload_share_assets = Mock()
    return repo


def request_handler(existing=None, registered=None):
    def request(method, path, **kwargs):
        if path.endswith('/profiles'):
            return [{'display_name':'이름','position_code':'TEAM','is_active':True}]
        if path.endswith('/positions'):
            return [{'display_name':'팀장'}]
        if path.endswith('hwarang_find_reusable_share'):
            return existing
        if path.endswith('hwarang_register_combined_share_once'):
            return registered or {'token':kwargs['json']['p_token'], 'public_packet':kwargs['json']['p_packet']}
        return None
    return request


def test_exact_reuse_does_not_upload_or_register_or_extend_expiry():
    repo = sharing_repo()
    old = {'token':'a'*43, 'public_packet':{'sender':{'name':'이름'}}, 'expires_at':'2026-11-01'}
    repo._request = Mock(side_effect=request_handler(existing=old))
    assert repo.create_combined_share('2026-10-09', ['NEWS'], 'user') == (old['token'],old['public_packet'])
    repo._upload_share_assets.assert_not_called()
    assert not any('register' in c.args[1] or c.args[0]=='PATCH' for c in repo._request.call_args_list)


def test_cleanup_storage_first_then_row_and_continues_until_empty():
    repo = sharing_repo(); token='a'*43
    batch={'shares':[{'token':token,'paths':[token+'/v/preview.png',token+'/v/briefing.pdf']}], 'orphans':[]}
    repo._request=Mock(side_effect=[batch, [], True, {'shares':[], 'orphans':[]}])
    assert repo.cleanup_expired_shares()=={'deleted_shares':1,'deleted_orphan_files':0,'failed':0}
    calls=repo._request.call_args_list
    assert calls[1].args[0]=='DELETE'
    assert calls[2].args[1].endswith('hwarang_finish_share_cleanup')


def test_cleanup_storage_failure_keeps_row_for_retry():
    repo=sharing_repo();token='a'*43
    repo._request=Mock(side_effect=[{'shares':[{'token':token,'paths':[token+'/v/preview.png']}]},BriefingRepositoryError('unavailable')])
    assert repo.cleanup_expired_shares()['failed']==1
    assert not any(c.args[1].endswith('hwarang_finish_share_cleanup') for c in repo._request.call_args_list)


def test_cleanup_rejects_cross_token_paths():
    repo=sharing_repo()
    repo._request=Mock(return_value={'shares':[{'token':'a'*43,'paths':['b'*43+'/v/preview.png']}]})
    assert repo.cleanup_expired_shares()['failed']==1
    assert repo._request.call_count==1


def test_storage_deletion_batches_at_api_limit():
    repo=sharing_repo();repo._request=Mock()
    repo._delete_share_asset_paths(['p/'+str(i) for i in range(1001)])
    assert [len(c.kwargs['json']['prefixes']) for c in repo._request.call_args_list]==[1000,1]
