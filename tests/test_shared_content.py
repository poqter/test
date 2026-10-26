from unittest.mock import Mock
from modules.briefing.shared_content import split_packet, IDENTITY, TOKEN, WEATHER
from modules.briefing.sharing import build_combined_packet
from modules.briefing.repository import BriefingRepository
from test_briefing_release import bundle

def packet(sender='설계사',weather=None,codes=('NEWS','MARKET')):
    return build_combined_packet([bundle(c) for c in codes],{'name':sender,'position':'팀장'},'https://example.org','x'*43,selected_codes=codes,weather=weather)

def test_people_share_content_but_not_identity():
    a=split_packet(packet('A'),'https://example.org');b=split_packet(packet('B'),'https://example.org')
    assert a['content_id']==b['content_id']
    assert a['preview_id']!=b['preview_id'] and a['reuse_key']!=b['reuse_key']
    assert 'sender' not in a['content']['packet']
    assert all(marker in a['content']['html_template'] for marker in (IDENTITY,TOKEN,WEATHER))

def test_regions_share_body_and_personal_preview_but_have_different_links():
    a=split_packet(packet(weather={'status':'unavailable','region_code':'서울'}),'https://example.org')
    b=split_packet(packet(weather={'status':'unavailable','region_code':'부산'}),'https://example.org')
    assert a['content_id']==b['content_id'] and a['preview_id']==b['preview_id']
    assert a['weather_id']!=b['weather_id'] and a['reuse_key']!=b['reuse_key']

def test_scope_changes_reuse_preview_only():
    a=split_packet(packet(codes=('NEWS',)),'https://example.org');b=split_packet(packet(codes=('MARKET',)),'https://example.org')
    assert a['preview_id']==b['preview_id'] and a['content_id']!=b['content_id']

def test_weather_timestamp_changes_do_not_create_duplicates():
    p=packet(weather={'status':'ok','region_code':'서울','low':10,'issued_at':'old'})
    a=split_packet(p,'https://example.org');p['body']['weather_forecast']['issued_at']='new'
    assert a==split_packet(p,'https://example.org')
    p['body']['weather_forecast']['low']=11
    assert a['reuse_key']!=split_packet(p,'https://example.org')['reuse_key']

def test_shared_lookup_returns_saved_packet_without_upload():
    from test_briefing_share_lifecycle import sharing_repo,request_handler
    repo=sharing_repo();repo._upload_shared_preview=Mock();saved=packet();legacy=request_handler()
    def request(method,path,**kw):
        if path.endswith('hwarang_find_shared_link'):return 'a'*43
        return legacy(method,path,**kw)
    repo._request=Mock(side_effect=request);repo.public_share=Mock(return_value=saved)
    assert repo.create_combined_share('2026-10-09',['NEWS'],'user')==('a'*43,saved)
    repo._upload_shared_preview.assert_not_called()

def test_preview_existing_object_is_not_rendered_or_uploaded():
    repo=BriefingRepository('https://example.org','test');repo.http=Mock();repo.http.head.return_value.status_code=200
    repo._upload_shared_preview('a'*64,{})
    repo.http.post.assert_not_called()
