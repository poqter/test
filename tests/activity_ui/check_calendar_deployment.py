"""Smoke test for the isolated deployment without credentials or production access."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import subprocess,sys,socket,time
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'calendar_app.py'),'--server.headless=true','--server.port=8523','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for _ in range(100):
 try:
  with socket.create_connection(('127.0.0.1',8523),timeout=.2):break
 except OSError:time.sleep(.2)
try:
 from playwright.sync_api import sync_playwright,expect
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8523/?briefing_health=1')
  expect(page.get_by_text('HWARANG_ACTIVITY_RELEASE=',exact=False)).to_be_visible(timeout=30000)
  print('PASS isolated calendar entry release probe',page.url)
  page.goto('http://127.0.0.1:8523/')
  expect(page.get_by_text('HWARANG 계정 연결 정보가 설정되지 않았습니다.',exact=False)).to_be_visible(timeout=30000)
  assert 'view=mobile-calendar' in page.url or '/calendar' in page.url,page.url
  expect(page.get_by_test_id('stException')).to_have_count(0)
  print('PASS isolated calendar route and missing-secret gate; no auth bypass')
  page.goto('http://127.0.0.1:8523/calendar')
  expect(page.get_by_text('HWARANG 계정 연결 정보가 설정되지 않았습니다.',exact=False)).to_be_visible(timeout=30000)
  expect(page.get_by_test_id('stException')).to_have_count(0)
  print('PASS installed calendar URL route')
  b.close()
finally:
 server.terminate();server.wait(timeout=10)
