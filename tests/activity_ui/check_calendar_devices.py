"""Device chrome visibility and real monthly selection/editor integration."""
from pathlib import Path
import socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/mobile_harness.py'),'--server.headless=true','--server.port=8504','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8504),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox'])
  for ua,touch,width,mobile in [('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile',True,390,True),('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15',True,1024,True),('Mozilla/5.0 (Windows NT 10.0; Win64; x64)',False,1440,False)]:
   c=b.new_context(viewport={'width':width,'height':900},user_agent=ua,has_touch=touch)
   if touch:c.add_init_script("Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5})")
   page=c.new_page();page.goto('http://127.0.0.1:8504');cal=page.frame_locator('iframe[title="modules.activity.center.sales_calendar_view"]')
   expect(cal.get_by_role('button',name='월간',exact=True)).to_have_attribute('aria-pressed','true')
   page.evaluate("""() => {const badge=document.createElement('a');badge.className='_viewerBadge_probe';badge.textContent='Streamlit';badge.href='https://streamlit.io/cloud';document.body.append(badge);const avatar=document.createElement('div');avatar.className='_profilePreview_probe';avatar.innerHTML='<a><img data-testid="appCreatorAvatar"></a>';document.body.append(avatar)}""")
   expect(page.locator('._viewerBadge_probe')).to_be_hidden()
   expect(page.locator('._profilePreview_probe')).to_be_hidden()
   day=cal.get_by_role('button',name='2026-11-06 일정 보기',exact=True);day.click();expect(page.get_by_role('dialog')).to_have_count(0)
   page.wait_for_timeout(450);day.click();expect(page.get_by_role('dialog')).to_be_visible();expect(page.get_by_role('dialog').get_by_test_id('stDateInput').locator('input').first).to_have_value('2026-11-06')
   page.get_by_role('button',name='✕',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
   page.wait_for_timeout(450);day.click();expect(page.get_by_role('dialog')).to_be_visible();page.get_by_role('button',name='✕',exact=True).click()
   cal.locator('.view-settings > summary').click();cal.get_by_label('주말 표시',exact=True).uncheck();expect(cal.locator('.view-settings')).to_have_attribute('open','')
   page.reload();expect(cal.get_by_role('button',name='월간',exact=True)).to_have_attribute('aria-pressed','true');cal.locator('.view-settings > summary').click();expect(cal.get_by_label('주말 표시',exact=True)).not_to_be_checked()
   c.close()
  b.close()
 print('PASS phone/tablet/desktop chrome, monthly repeated selection, cancel/reopen, persisted preferences')
finally:
 server.terminate();server.wait(timeout=10)
