"""A slow published-status query must never block home navigation."""
from pathlib import Path
import subprocess,sys,time,socket
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'tests/activity_ui/home_harness.py'),'--server.headless=true','--server.port=8519','--browser.gatherUsageStats=false'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8519),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000})
  page.goto('http://127.0.0.1:8519')
  expect(page.locator('.st-key-brand_feature_analysis')).to_be_visible()
  started=time.monotonic()
  expect(page.get_by_role('heading',name='자료·교육',exact=True)).to_be_visible()
  expect(page.get_by_text('오늘의 브리핑 · 게시 상태 확인 중',exact=True)).to_be_visible()
  collapse=page.get_by_test_id('stSidebarCollapseButton').locator('button')
  brand=page.locator('.sig-brand').bounding_box();box=collapse.bounding_box()
  assert box['y']>=brand['y'] and box['y']+box['height']<=brand['y']+brand['height'],(brand,box)
  assert box['x']>=brand['x'] and box['x']+box['width']<=brand['x']+brand['width'],(brand,box)
  collapse.click();opener=page.get_by_test_id('stExpandSidebarButton');expect(opener).to_be_visible()
  assert opener.bounding_box()['y']<48
  page.locator('.st-key-brand_analyze button').click()
  expect(page.get_by_role('heading',name='OPENED analyzer')).to_be_visible(timeout=3000)
  assert time.monotonic()-started<6,'Navigation waited for an eight-second briefing request'
  expect(page.get_by_test_id('stException')).to_have_count(0)
  page.screenshot(path='/tmp/home-instant.png')
  print('PASS all menus and navigation available before slow briefing; sidebar header controls aligned')
  browser.close()
finally:server.terminate();server.wait(timeout=10)
