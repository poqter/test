from datetime import datetime, timezone
import pytest

from modules.briefing.direct_sources import DirectSourceSpec, probe_direct_sources
from modules.briefing.fsc_board import BOARD_URL, article_body, parse_board, supports_feed
from modules.briefing.gates import route_profiles
from tests.test_briefing_source_probe import FeedResponse, FeedSession, RSS

NOW = datetime(2026,10,6,14,16,tzinfo=timezone.utc)
SPEC = DirectSourceSpec('fsc_press','금융위원회','http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111',profile_hints=('INSURANCE','NEWS'))
TITLE = '보험금 지급 기준 변경'
TEXT = '새 보험금 지급 기준을 발표했습니다. 적용 시점과 대상 계약을 확인합니다. ' * 8


def board(title=TITLE,date='2026-10-06',link='/no010101/123'):
    return f'<nav>다른 제목 2099-01-01</nav><div class="board-list-wrap"><ul><li><div class="subject"><a href="{link}" title="{title}">{title}<span class="newbbs-span">오늘 등록</span></a></div><div class="file"><a href="/comm/getFile">첨부파일</a></div><div class="day">{date}</div></li></ul></div>'


def detail(title=TITLE,date='2026-10-06',body=TEXT):
    return f'<div class="board-view-wrap"><div class="header"><div class="subject">{title}</div><div class="day"><span>{date}</span><span>조회수 : 123</span></div><div class="info">담당자 연락처 02-000-0000</div></div><div class="body"><div class="cont"><p>{body}</p><script>ga unrelated</script></div></div><div class="foot">이전글 다른 이야기</div></div>'


def html(value):
    return FeedResponse(value.encode(),headers={'Content-Type':'text/html;charset=UTF-8'})


def test_verified_board_parser_uses_row_date_and_article_url_not_attachments_or_body_dates():
    row = parse_board(board(),SPEC,NOW)[0]
    row.description = article_body(detail(body=TEXT+' 사건일 2026-09-01'),row)
    assert row.published_at.isoformat() == '2026-10-05T15:00:00+00:00'
    assert '/no010101/123?' in row.url and '/comm/' not in row.url
    assert '연락처' not in row.description and '이전글' not in row.description and 'unrelated' not in row.description
    assert 'INSURANCE' in route_profiles(row,'INSURANCE')


@pytest.mark.parametrize('value', ['<html>service unavailable</html>',board(date=''),board(link='https://evil.example/no010101/123')])
def test_unrecognized_board_or_missing_dates_fail_closed(value):
    with pytest.raises(ValueError,match='layout_changed'):
        parse_board(value,SPEC,NOW)


@pytest.mark.parametrize('value', [detail(title='다른 기사'),detail(date='2026-10-05'),detail(body='첨부파일만 있음')])
def test_unverified_article_date_title_or_body_does_not_pass(value):
    row = parse_board(board(),SPEC,NOW)[0]
    with pytest.raises(ValueError): article_body(value,row)


def test_rss_503_falls_back_without_secret_change_and_preserves_primary_failure():
    session = FeedSession(FeedResponse(status=503),html(board()),html(detail()))
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    health = packet['direct_sources']['fsc_press']
    assert health['status'] == 'ok' and health['fallback_used']
    assert health['primary']['http_status'] == 503 and health['primary_status'] == 'failed'
    assert health['fallback']['verified_articles'] == health['fresh_candidates'] == 1
    assert session.calls[1][0] == BOARD_URL
    assert packet['project_openai_api_calls'] == packet['db_writes'] == 0


def test_working_rss_does_not_call_fallback():
    session = FeedSession(FeedResponse(RSS))
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    assert len(session.calls) == 1 and packet['direct_sources']['fsc_press']['status'] == 'ok'
    assert not packet['direct_sources']['fsc_press'].get('fallback_used')


def test_unavailable_article_body_is_not_promoted_to_paid_analysis_candidate():
    session = FeedSession(FeedResponse(status=503),html(board()),FeedResponse(status=503))
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    assert packet['direct_sources']['fsc_press']['status'] == 'failed'
    assert packet['direct_sources']['fsc_press']['fallback']['failure_reason'] == 'fsc_article_bodies_unavailable'
    assert packet['candidate_sample'] == []


def test_old_board_rows_do_not_cause_article_requests():
    session = FeedSession(FeedResponse(status=503),html(board(date='2026-09-01')))
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    assert len(session.calls) == 2 and packet['direct_sources']['fsc_press']['status'] == 'empty_valid'


def test_general_fsc_finance_story_is_not_forced_into_insurance_by_profile_hint():
    row = parse_board(board(title='은행 예금 정책 변경'),SPEC,NOW)[0]
    row.description = '금융감독원 은행 예금 감독 정책을 변경합니다.' * 8
    assert 'INSURANCE' not in route_profiles(row,'INSURANCE')
    assert 'NEWS' in route_profiles(row,'NEWS')


def test_rejected_destination_does_not_trigger_fallback():
    session = FeedSession()
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: False)
    assert not session.calls and not packet['direct_sources']['fsc_press'].get('fallback_used')


def test_fallback_detail_requests_stop_at_six_articles():
    rows = ''.join(board(link=f'/no010101/{i}').split('<ul>')[1].split('</ul>')[0] for i in range(7))
    listing = f'<div class="board-list-wrap"><ul>{rows}</ul></div>'
    session = FeedSession(FeedResponse(status=503),html(listing),*[html(detail()) for _ in range(6)])
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    assert len(session.calls) == 8
    assert packet['direct_sources']['fsc_press']['fallback']['verified_articles'] == 6


def test_fallback_cross_publisher_redirect_is_not_followed():
    session = FeedSession(FeedResponse(status=503),FeedResponse(status=302,headers={'Location':'https://evil.example/a'}))
    packet = probe_direct_sources([SPEC],as_of=NOW,session=session,destination_check=lambda url: True)
    assert len(session.calls) == 2 and packet['direct_sources']['fsc_press']['status'] == 'failed'


@pytest.mark.parametrize('url',[ 'https://evil.example/about/fsc_bbs_rss/?fid=0111',
                               'https://fsc.go.kr/about/fsc_bbs_rss/?fid=0112',
                               'https://fsc.go.kr/about/fsc_bbs_rss/?fid=0111&token=secret'])
def test_fallback_is_registered_only_for_this_verified_public_feed(url):
    assert not supports_feed(url)
