"""Notification Back handling in the real bridge, with no backend or Streamlit."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
bridge=(ROOT/'modules/activity/calendar_bridge.html').read_text().split('id="calendar-layout-source">',1)[1].split('</script>',1)[0]
html='''<div class="st-key-mobile_header"></div>
<span class="mobile-navigation-state" data-page="캘린더" data-depth="0"></span>
<input aria-label="retained draft" value="unsaved calendar draft">
<div class="st-key-mobile_history_back"><button onclick="window.navigationCalls++">back</button></div>
<button id="open">notifications</button>
<script>
window.closeCalls=0;window.navigationCalls=0;
document.getElementById('open').onclick=()=>{
 const dialog=document.createElement('div');dialog.setAttribute('role','dialog');
 dialog.innerHTML='<div class="st-key-mobile_alerts_close"><button>close</button></div>';
 dialog.querySelector('button').onclick=()=>{closeCalls++;dialog.remove()};document.body.append(dialog);
};
</script>'''
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 for embedded in (False,True):
  page=browser.new_page(viewport={'width':390,'height':844})
  page.route('https://back.test/**',lambda r:r.fulfill(body='<iframe id="app" src="/app"></iframe>' if r.request.url.endswith('/wrapper') else html,content_type='text/html'))
  page.goto('https://back.test/wrapper' if embedded else 'https://back.test/app')
  frame=page.frame_locator('#app') if embedded else page
  frame.locator('#open').click()
  app=page.locator('#app').element_handle().content_frame() if embedded else page.main_frame
  app.evaluate(bridge)
  page.wait_for_function('history.state?.hwarangCalendarBack===true')
  for expected in (1,2):
   if expected==2:
    frame.locator('#open').click()
    page.wait_for_timeout(400) # Back's double-press guard must expire.
   expect(frame.get_by_role('dialog')).to_be_visible()
   page.go_back()
   expect(frame.get_by_role('dialog')).to_have_count(0)
   expect(frame.locator('#calendar-exit-confirm')).to_have_count(0)
   expect(frame.get_by_label('retained draft')).to_have_value('unsaved calendar draft')
   assert app.evaluate('closeCalls')==expected
   assert app.evaluate('navigationCalls')==0
   assert page.url.endswith('/wrapper' if embedded else '/app')
  page.close()
 browser.close()
print('PASS notification Back closes only the popup, preserves page/draft, and survives repeated opens in standalone/embedded hosts')
