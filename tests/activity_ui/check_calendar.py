"""Browser regression for the shipped calendar component (no backend access)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
HTML=(ROOT/'modules/activity/calendar_view/index.html').read_text()
ARGS=dict(mode='주간',day='2026-11-06',today='2026-11-06',events=[
    dict(id='a',day='2026-11-06',kind='AP',short='첫 상담',label='AP 첫 상담',member='one'),
    dict(id='b',day='2026-11-07',kind='CS',short='주말 일정',label='CS 주말 일정',member='one')],roster={'one':'테스트'},mobileSession={},rangeStart='2026-10-26',rangeEnd='2026-11-15')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1100,'height':850})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('https://activity.test/persistent.js',lambda route:route.fulfill(path=str(ROOT/'modules/activity/calendar_view/persistent.js'),content_type='application/javascript'))
    page.route('https://activity.test/',lambda route:route.fulfill(body=HTML,content_type='text/html'))
    page.goto('https://activity.test/')
    page.evaluate("()=>{calendarBoot={uid:'one',team:false,member:null};rpc=async(op,a)=>({events:[],rangeStart:a.first,rangeEnd:a.last})}")
    page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',ARGS)
    assert page.locator('.cell').count()==5
    page.locator('.view-settings > summary').click()
    assert not page.get_by_label('주말 표시',exact=True).is_checked()
    page.get_by_label('주말 표시',exact=True).click()
    assert page.locator('.cell').count()==7
    assert page.locator('[data-key="2026-11-07"] .chip').inner_text().endswith('주말 일정')
    page.get_by_label('주말 표시',exact=True).click()
    assert page.locator('.cell').count()==5
    page.get_by_role('button',name='보기 설정 닫기').click()
    # Same payload: no DOM mutation. Changed event: update only the existing node.
    page.evaluate('window.savedCell=document.querySelector("[data-key=\\"2026-11-06\\"]");window.savedChip=savedCell.querySelector(".chip");window.savedNav=document.querySelector("#nav button");')
    page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',ARGS)
    assert page.evaluate('savedCell===document.querySelector("[data-key=\\"2026-11-06\\"]")')
    ARGS['events'][0]['short']='다른 직원이 수정한 내용'
    page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',ARGS)
    assert page.evaluate('savedChip===document.querySelector("[data-key=\\"2026-11-06\\"] .chip")')
    assert page.evaluate('savedNav===document.querySelector("#nav button")')
    assert page.locator('[data-key="2026-11-06"] .chip').inner_text().endswith('다른 직원이 수정한 내용')
    # Keep the compact preview; more opens every event for that day.
    ARGS['events'] += [dict(ARGS['events'][0],id='c'),dict(ARGS['events'][0],id='d')]
    page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',ARGS)
    assert page.locator('#agenda .row').count()==2
    page.locator('[data-key="2026-11-06"] .more').click()
    assert page.locator('dialog .row').count()==3
    page.locator('dialog').get_by_role('button',name='전체 일정 닫기',exact=True).click()
    # Weekend exclusion across a month/year boundary and day navigation.
    for month,days in [('2026-11-01',30),('2027-01-01',30)]:
        args=dict(ARGS,mode='월간',day=month,hideWeekends=True)
        page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',args)
        assert page.locator('.cell').count()==days
        assert page.evaluate('[...document.querySelectorAll(".cell")].every(c=>![0,6].includes(date(c.dataset.key).getUTCDay()))')
    page.evaluate('a=>render(a)',dict(ARGS,mode='날짜별',hideWeekends=True))
    page.get_by_role('button',name='다음 기간').click()
    assert page.locator('#agenda h3').inner_text().startswith('11월 9일')
    page.get_by_role('button',name='이전 기간').click()
    assert page.locator('#agenda h3').inner_text().startswith('11월 6일')
    # Mobile weekly layout remains single-column and does not overflow.
    page.set_viewport_size({'width':390,'height':700})
    page.evaluate('a=>render(a)',dict(ARGS,hideWeekends=True))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('#grid').evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length')==1
    # Stable no-change probes, coalesced change notification, hidden pause and offline retention.
    args=dict(ARGS,hideWeekends=True,syncStamp='v1',syncUnit='unit',mobileSession=dict(uid='one',url='https://activity.test',key='public',token='fake'))
    page.evaluate('a=>{loadPrefs(a);prefs.showWeekends=false;render(a)}',args)
    page.evaluate("window.syncCalls=0;window.syncChanges=0;window.fetch=async()=>{syncCalls++;return {ok:true,json:async()=>window.mockStamp||'v1'}};calendarAction=(action)=>{if(action==='refresh')syncChanges++};window.keptCell=document.querySelector('[data-key=\"2026-11-06\"]')")
    page.evaluate('checkSync()')
    page.wait_for_timeout(50)
    assert page.evaluate('syncCalls')==1 and page.evaluate('syncChanges')==0
    page.evaluate("window.mockStamp='v2';checkSync()")
    page.wait_for_timeout(50)
    page.evaluate('checkSync()');page.wait_for_timeout(50)
    assert page.evaluate('syncChanges')==1
    assert page.evaluate('keptCell===document.querySelector(\'[data-key="2026-11-06"]\')')
    page.evaluate('parentVisible=false;checkSync()');before=page.evaluate('syncCalls')
    page.evaluate('checkSync()');assert page.evaluate('syncCalls')==before
    page.evaluate("parentVisible=true;window.fetch=async()=>{throw Error('offline')};checkSync()")
    assert '연결 확인 중' in page.locator('#refreshing').inner_text()
    assert page.evaluate('keptCell===document.querySelector(\'[data-key="2026-11-06"]\')')
    assert not errors,errors
    browser.close()
print('PASS calendar weekdays, toggle, weekend data retention, keyed updates, navigation and mobile layout')
