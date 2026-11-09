"""Browser checks with every request fulfilled locally or blocked; no server."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox'])
 ctx=b.new_context(viewport={'width':1440,'height':900})
 def route(r):
  name=r.request.url.split('/')[-1]
  f=ROOT/'modules/activity/calendar_view'/name
  if r.request.url.startswith('https://calendar.test/') and f.is_file():r.fulfill(path=str(f))
  else:r.abort()
 ctx.route('**/*',route)
 page=ctx.new_page();page.goto('https://calendar.test/index.html')
 page.evaluate("""()=>{calendarBoot={uid:'me',kinds:['AP','미분류'],people:{},managed:false};latest={events:[],day:'2026-11-09',today:'2026-11-09'};selected=latest.day;openEditor(null,'new',selected)}""")
 assert page.evaluate("calendarPanel.getAnimations().some(a=>a.effect.getTiming().duration===300)")
 # A close/reopen during entrance must not let old cleanup remove the new form.
 page.evaluate("calendarDraft=null;closePanel();openEditor(null,'new',selected)")
 page.wait_for_timeout(220)
 assert page.evaluate("calendarPanel.open && document.activeElement.name==='title'")
 start=page.get_by_label('시작 시간',exact=True);end=page.get_by_label('종료 시간 · 선택',exact=True)

 for width in (390,1440):
  page.set_viewport_size({'width':width,'height':900})
  a,z=page.evaluate("[...document.querySelectorAll('input[name=start],input[name=end]')].map(e=>{const r=e.getBoundingClientRect();return {y:r.y,height:r.height}})");assert abs(a['y']-z['y'])<1 and abs(a['height']-z['height'])<1,(width,a,z)
 expect(end).to_be_visible();expect(page.get_by_role('button',name='＋ 종료 시간')).to_have_count(0)
 start.press_sequentially('14');expect(start).to_have_value('14:');start.press_sequentially('30');expect(start).to_have_value('14:30')
 end.fill('1530');end.press('Tab');expect(end).to_have_value('15:30')
 start.fill('930');start.press('Tab');expect(start).to_have_value('09:30')
 start.fill('');end.fill('1000');end.press('Tab');expect(page.get_by_text('시작 시간을 먼저 입력해 주세요.',exact=True)).to_be_visible()
 a,z=page.evaluate("[...document.querySelectorAll('input[name=start],input[name=end]')].map(e=>{const r=e.getBoundingClientRect();return {y:r.y,height:r.height}})");assert abs(a['y']-z['y'])<1 and abs(a['height']-z['height'])<1
 start.fill('1100');start.press('Tab');expect(page.get_by_text('종료 시간은 시작 시간보다 늦어야 합니다.',exact=True)).to_be_visible()
 end.fill('');end.press('Tab');assert end.evaluate('e=>e.validationMessage')==''
 page.get_by_label('종일',exact=True).check();expect(start).not_to_be_visible();page.get_by_label('종일',exact=True).uncheck();expect(start).to_have_value('11:00')
 start.fill('12');start.press('Backspace');expect(start).to_have_value('1')
 assert page.evaluate("getComputedStyle(calendarPanel).getPropertyValue('--calendar-enter')")=='300ms'
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate("getComputedStyle(calendarPanel).getPropertyValue('--calendar-enter')")=='160ms'
 page.evaluate("calendarDraft=null;closePanel()")
 # Sample the sidebar's real width interpolation, using the app's shared styles.
 sidebar_page=ctx.new_page()
 sidebar_css=(ROOT/'modules/activity/calendar_bridge.html').read_text().split('navigationStyle.textContent=`',1)[1].split('`;',1)[0]
 sidebar_page.set_content('<style>body{display:flex}section{position:relative}</style><style>'+(ROOT/'modules/shared/workspace_design.css').read_text()+sidebar_css+'</style><div class="hw-design-2026 st-key-mobile_header"></div><section data-testid="stSidebar" aria-expanded="true">menu</section>')
 widths=sidebar_page.evaluate("async()=>{const e=document.querySelector('section');await new Promise(requestAnimationFrame);e.getBoundingClientRect();e.setAttribute('aria-expanded','false');const values=[];for(let i=0;i<28;i++){await new Promise(requestAnimationFrame);values.push(e.getBoundingClientRect().width)}return values}")
 assert any(5<x<255 for x in widths) and widths[-1]<1,widths
 sidebar_page.close()
 # Exercise the actual overlay bridge against a locally-created popover.
 bridge=(ROOT/'modules/activity/calendar_bridge.html').read_text().split('id="calendar-layout-source">',1)[1].split('</script>',1)[0]
 page.evaluate("""()=>{document.body.innerHTML='<div class="st-key-mobile_header"></div><button id="under" style="position:fixed;inset:0;width:100%;height:100%">under</button><div data-testid="stPopoverBody" style="position:fixed;left:0;top:0;width:250px;height:100%;background:white"><span class="mobile-drawer"></span></div>';window.underClicks=0;document.getElementById('under').onclick=()=>underClicks++;const trigger=document.createElement('div');trigger.dataset.testid='stPopover';trigger.innerHTML='<button aria-expanded="true">menu</button>';trigger.firstChild.onclick=()=>document.querySelector('[data-testid=stPopoverBody]').remove();document.body.append(trigger)}""")
 page.evaluate(bridge)
 expect(page.locator('#calendar-drawer-backdrop')).to_be_visible()
 page.mouse.click(360,500)
 expect(page.locator('[data-testid=stPopoverBody]')).to_have_count(0)
 expect(page.locator('#calendar-drawer-backdrop')).not_to_be_visible()
 assert page.evaluate('underClicks')==0
 print('PASS auto colon, shorthand, optional end, validation, all-day restoration, PC/mobile timing, outside tap shielding')
 b.close()
