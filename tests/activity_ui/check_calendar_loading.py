"""Slow context must show dates immediately and never leave the home body behind."""
from pathlib import Path
import subprocess,sys,time,socket
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'tests/activity_ui/loading_harness.py'),'--server.headless=true','--server.port=8521','--browser.gatherUsageStats=false'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8521),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  for width in (1440,390):
   page=browser.new_page(viewport={'width':width,'height':1000})
   page.goto('http://127.0.0.1:8521/?fail=1' if width==390 else 'http://127.0.0.1:8521/')
   expect(page.get_by_role('heading',name='안녕하세요, 테스트님')).to_be_visible()
   if width==390:page.get_by_test_id('stExpandSidebarButton').click()
   started=time.monotonic()
   page.get_by_role('button',name='영업활동 관리',exact=True).click()
   expect(page.locator('.hw-calendar-loading')).to_be_visible(timeout=2000)
   assert time.monotonic()-started<3
   expect(page.get_by_text('홈 본문 7',exact=True)).not_to_be_visible(timeout=1000)
   expect(page.get_by_role('heading',name='안녕하세요, 테스트님')).not_to_be_visible()
   expect(page.locator('.hw-calendar-day.is-today')).to_have_count(1)
   if width==390:
    page.get_by_test_id('stSidebarCollapseButton').locator('button').click()
    page.wait_for_timeout(400)
   page.screenshot(path=f'/tmp/calendar-loading-{width}.png')
   if width==390:
    expect(page.get_by_text('요청을 완료하지 못했습니다. 입력 내용은 유지됩니다. 연결 확인 실패')).to_be_visible(timeout=8000)
    expect(page.locator('.hw-calendar-loading')).to_have_count(0)
    page.get_by_role('button',name='다시 불러오기').click()
    expect(page.locator('.hw-calendar-loading')).to_be_visible()
   iframe=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]')
   expect(iframe).to_be_visible(timeout=15000)
   expect(page.locator('.hw-calendar-loading')).not_to_be_visible()
   expect(page.get_by_test_id('stException')).to_have_count(0)
   if width==1440:
    page.get_by_role('button',name='홈',exact=True).click()
    expect(page.get_by_role('heading',name='안녕하세요, 테스트님')).to_be_visible()
    expect(iframe).to_have_count(0)
    page.get_by_role('button',name='영업활동 관리',exact=True).click()
    expect(page.locator('.hw-calendar-loading')).to_be_visible(timeout=2000)
    expect(page.get_by_text('홈 본문 7',exact=True)).not_to_be_visible()
    expect(iframe).to_be_visible(timeout=10000)
   print(f'PASS {width}: dates before slow context, no home residue, error/retry',flush=True)
   page.close()
  browser.close()
finally:server.terminate();server.wait(timeout=10)
