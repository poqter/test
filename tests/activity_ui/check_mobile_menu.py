"""Prevent detached chevron clicks from being mistaken for outside presses."""
from pathlib import Path
import os,socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/mobile_harness.py'),'--server.headless=true','--server.port=8540','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8540),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  engine=os.environ.get('HW_TEST_BROWSER','chromium')
  browser=getattr(p,engine).launch(headless=True)
  for touch in (False,True):
   page=browser.new_page(viewport={'width':390,'height':844},has_touch=touch)
   page.goto('http://127.0.0.1:8540')
   expect(page.get_by_test_id('stApp')).to_have_attribute('data-test-script-state','notRunning')
   toggle=page.get_by_role('button',name='☰',exact=True)
   drawer=page.locator('[data-testid=stPopoverBody]').filter(has=page.locator('.mobile-drawer'))
   page.evaluate("""document.addEventListener('click',e=>{
    if(e.composedPath().some(n=>n.getAttribute?.('data-testid')==='stPopoverButton'))window.menuClickTarget=e.target;
   },true)""")
   for i in range(10):
    # Hit the chevron's location, not just the label or keyboard trigger.
    icon=toggle.locator('[data-testid=stIconMaterial]')
    box=icon.bounding_box()
    if touch:page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
    else:page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
    expect(drawer).to_be_visible()
    assert page.evaluate('menuClickTarget.isConnected'), 'Opening replaced the original click target'
    # The outside-click grace period is 50ms; keep checking after it expires.
    page.wait_for_timeout(100)
    expect(drawer).to_be_visible()
    drawer.get_by_role('button',name='패널 닫기',exact=True).click()
    expect(drawer).not_to_be_visible()
   toggle.focus();toggle.press('Enter');expect(drawer).to_be_visible()
   toggle.press('Escape');expect(drawer).not_to_be_visible()
   page.close()
  browser.close()
 print('PASS mobile menu: retained click target, repeated mouse/touch, Enter/Escape')
finally:
 server.terminate();server.wait(timeout=10)
