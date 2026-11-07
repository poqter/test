"""Install entry, native prompt wiring, fallback and installed-app state."""
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
  b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':390,'height':844},user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile')
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8504')
  page.get_by_role('button',name='☰',exact=True).click()
  drawer=page.locator('[data-testid="stPopoverBody"]');install=drawer.get_by_role('button',name='홈 화면에 설치',exact=True)
  expect(install).to_be_visible();install.click()
  panel=page.get_by_role('dialog',name='홈 화면에 설치');expect(panel).to_be_visible();expect(panel).to_contain_text('Safari에서 공유 버튼')
  panel.get_by_role('button',name='설치 안내 닫기').click();expect(panel).to_have_count(0)
  page.evaluate("window.promptCalls=0;const e=new Event('beforeinstallprompt',{cancelable:true});e.prompt=async()=>{promptCalls++};e.userChoice=Promise.resolve({outcome:'dismissed'});dispatchEvent(e)")
  page.get_by_role('button',name='☰',exact=True).click()
  install.click();assert page.evaluate('promptCalls')==1;expect(panel).to_have_count(0)
  install.click();expect(panel).to_be_visible();panel.get_by_role('button',name='설치 안내 닫기').click()
  page.get_by_role('button',name='☰',exact=True).click()
  page.evaluate("dispatchEvent(new Event('appinstalled'))");expect(install).to_be_hidden()
  assert page.locator('link[rel="manifest"]').get_attribute('href').endswith('/app/static/calendar-manifest.json')
  assert not errors,errors
  b.close()
 print('PASS sidebar install, iOS guidance, prompt consumption, dismiss fallback, installed hiding')
finally:
 server.terminate();server.wait(timeout=10)
