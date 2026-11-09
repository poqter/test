"""Calendar DOM continuity and isolated panels on phone/tablet with fake data."""
from pathlib import Path
import socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/mobile_harness.py'),'--server.headless=true','--server.port=8507','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8507),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox'])
  for width in (390,820):
   page=b.new_page(viewport={'width':width,'height':900});page.goto('http://127.0.0.1:8507')
   frame_element=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]');expect(frame_element).to_be_visible()
   frame=frame_element.element_handle().content_frame();frame.wait_for_selector('.cell')
   frame.evaluate('window.__continuity="same-calendar"')
   for _ in range(3):
    page.get_by_role('button',name='일정 등록',exact=True).click();expect(page.get_by_role('dialog')).to_be_visible()
    page.get_by_role('dialog').get_by_role('button',name='✕',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
    page.wait_for_timeout(250)
    assert frame.evaluate('window.__continuity')=='same-calendar'
   frame.locator('.view-settings > summary').click();frame.get_by_label('완료 일정 표시',exact=True).uncheck()
   page.wait_for_timeout(250);assert frame.evaluate('window.__continuity')=='same-calendar'
   frame.get_by_role('button',name='보기 설정 닫기').click()
   expect(page.get_by_text('결과 미입력 일정',exact=True)).to_have_count(0)
   assert frame.evaluate('window.__continuity')=='same-calendar'
   expect(page.locator('[data-testid="stException"]')).to_have_count(0)
   page.close()
  b.close()
 print('PASS phone/tablet: repeated cancel retains calendar iframe; local filter and isolated panel')
finally:
 server.terminate();server.wait(timeout=10)
