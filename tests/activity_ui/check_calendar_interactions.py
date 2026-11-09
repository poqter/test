from pathlib import Path
from playwright.sync_api import sync_playwright,expect
html=(Path(__file__).resolve().parents[2]/'modules/activity/calendar_view/index.html').read_text()
a=dict(mode='월간',day='2026-11-06',today='2026-11-06',events=[dict(id='a',day='2026-11-06',kind='AP',short='상담',label='AP 상담',done=True)],mobileSession={'uid':'test'},hideMobileApp=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('https://cal.test/',lambda r:r.fulfill(body=html,content_type='text/html'));page.goto('https://cal.test/');page.evaluate('window.sent=[];addEventListener("message",e=>{if(e.data.value)sent.push(e.data.value)})');page.evaluate('a=>render(a)',a);page.wait_for_timeout(50);page.evaluate('sent=[]')
 page.get_by_text('보기 설정',exact=True).first.click();page.get_by_label('완료 일정 표시',exact=True).uncheck();expect(page.locator('.chip')).to_have_count(0);expect(page.locator('.view-settings')).to_have_attribute('open','');page.get_by_role('button',name='기본값으로 되돌리기').click();expect(page.locator('.chip')).to_have_count(1)
 assert not page.evaluate('sent.some(x=>x.action==="weekends")'), 'Completed filtering/reset must stay local'
 page.get_by_label('주말 표시',exact=True).check();page.wait_for_timeout(50);assert page.evaluate('sent.at(-1).action')=='weekends'
 page.get_by_role('button',name='보기 설정 닫기').click();expect(page.locator('.view-settings')).not_to_have_attribute('open','')
 day=page.locator('.cell[data-key="2026-11-06"]');day.click(position={'x':45,'y':3});page.wait_for_timeout(100);assert not page.evaluate('sent.some(x=>x.action==="new")')
 day.click(position={'x':45,'y':3});page.wait_for_timeout(100);assert not page.evaluate('sent.some(x=>x.action==="new")')
 page.wait_for_timeout(450);day.click(position={'x':45,'y':3});page.wait_for_timeout(50);assert page.evaluate('sent.at(-1).action')=='new'
 page.get_by_role('button',name='주간',exact=True).click();page.wait_for_timeout(50);assert page.evaluate('sent.at(-1).value')=='주간'
 page.evaluate('a=>render({...a,mode:"주간"})',a);page.get_by_role('button',name='일별',exact=True).click();page.wait_for_timeout(50);assert page.evaluate('sent.at(-1).value')=='날짜별'
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert not errors,errors
 page.screenshot(path='/tmp/calendar-final.png');b.close()
print('PASS preferences, first/repeat tap, debounce, mode controls, mobile width')
