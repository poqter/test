from copy import deepcopy
from datetime import datetime, timezone
from modules.briefing.publication import extract_publication_metadata
from modules.briefing.runtime import body_quality_ready
from modules.briefing.public_body import public_html, customer_body
from modules.briefing import scheduler
from test_briefing_catch_up import Repo, at, edition


def test_article_text_extraction_excludes_navigation_and_scripts():
    result=extract_publication_metadata('<nav>메뉴 광고</nav><article><h1>제도 개편</h1><p>적용 대상은 신규 가입자이며 시행일은 11월 1일입니다.</p><script>비밀 지시</script><p>기존 계약은 제외합니다.</p></article><footer>바닥글</footer>',url='https://www.mk.co.kr/news/economy/1')
    assert '기존 계약은 제외' in result.description
    assert all(x not in result.description for x in ('메뉴 광고','비밀 지시','바닥글'))


def test_minimum_counts_and_diversity_do_not_count_more_reading():
    def issue(category,tier='core'):
        return {'title':'검수용 뉴스','summary':'확인된 사실','selection_tier':tier,'category':category,'sources':[{'url':'https://example.com/a','published_at':'2026-10-22'}]}
    body={'editorial_version':3,'profile_code':'NEWS','issues':[issue('교육'),issue('교육'),issue('사회·안전','light_digest')]}
    assert not body_quality_ready(body)
    body['issues'][2]['selection_tier']='core'
    assert body_quality_ready(body)
    body['issues'][2]['category']='교육'
    assert not body_quality_ready(body)


def test_more_reading_is_collapsed_title_only_and_escaped():
    row={'title':'추가 제목 <script>','summary':'ADDITIONAL_SUMMARY_MUST_NOT_LEAK','reading_group':'more','sources':[{'url':'https://example.com/a','published_at':'2026-10-22'}]}
    packet={'body':{'profile_code':'NEWS','issues':[row]},'sender':{'name':'검수','position':'팀장'},'briefing_date':'2026-10-22'}
    html=public_html(packet)
    assert '<details class="more-reading">' in html and 'ADDITIONAL_SUMMARY_MUST_NOT_LEAK' not in html
    assert '추가 제목 &lt;script&gt;' in html
    assert '<a class="more-title" href="https://example.com/a"' in html


def test_final_unpublished_alert_is_once_and_does_not_reserve_ai():
    repo=Repo()
    repo.saved={c:edition(c) for c in ('MARKET','NEWS','INSURANCE')}
    repo.saved['MARKET']['revision']['validation_status']='required'
    first=scheduler.catch_up(repo,at('09:07:00'))
    second=scheduler.catch_up(repo,at('09:17:00'))
    assert first['notification_required'] and not second['notification_required']
    assert first['status']==second['status']=='incomplete'
    assert not repo.paid


def test_before_nine_quality_hold_is_recorded_without_failure_alert():
    repo=Repo();repo.saved={c:edition(c) for c in ('MARKET','NEWS','INSURANCE')}
    repo.saved['MARKET']['revision']['validation_status']='required'
    result=scheduler.catch_up(repo,at('08:20:00'))
    assert not result['notification_required'] and result['status']=='incomplete'
    assert next(r for r in result['publication'] if r['profile']=='MARKET')['status']=='quality_hold'
