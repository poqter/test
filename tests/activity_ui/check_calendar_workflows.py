"""Time shorthand, feedback CRUD and real mouse drag through the command boundary."""
from pathlib import Path
import socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/persistent_harness.py'),'--server.headless=true','--server.port=8519','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8519),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=b.new_page(viewport={'width':1440,'height':1000});page.goto('http://127.0.0.1:8519/?surface=mobile')
  frame=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]');expect(frame).to_be_visible();f=frame.element_handle().content_frame()
  f.wait_for_function('calendarLayoutReady && !calendarLoading')
  def click(name):f.get_by_role('button',name=name,exact=True).click()
  # Browser drag-and-drop, then undo using the returned server revision.
  chip=f.locator('.chip').first;target=f.locator('.cell[data-key="2026-11-10"]')
  chip.drag_to(target)
  expect(f.locator('#move-notice')).to_contain_text('2026-11-10로 이동했습니다.',timeout=20000)
  expect(target.locator('.chip')).to_have_count(1)
  click('되돌리기');expect(f.locator('.cell[data-key="2026-11-06"] .chip')).to_have_count(1,timeout=20000)
  click('＋ 일정 등록');expect(f.get_by_label('시작 시간',exact=True)).to_be_visible();expect(f.get_by_label('종료 시간 · 선택',exact=True)).not_to_be_visible()
  f.get_by_label('일정명',exact=True).fill('숫자 시간 테스트');f.get_by_label('시작 시간',exact=True).fill('930');f.get_by_label('시작 시간',exact=True).press('Tab')
  expect(f.get_by_label('시작 시간',exact=True)).to_have_value('09:30');expect(f.get_by_text('09:30 · 오전 9시 30분',exact=True)).to_be_visible()
  click('일정 등록');expect(f.get_by_role('heading',name='숫자 시간 테스트',exact=True)).to_be_visible(timeout=20000)
  expect(f.locator('.detail-line').filter(has_text='시간')).to_contain_text('09:30')
  f.get_by_label('피드백',exact=True).fill('첫 피드백');click('피드백 등록');expect(f.locator('.feedback-card')).to_contain_text('첫 피드백',timeout=20000)
  assert f.get_by_role('button',name='일정 확인 · 의견 저장').count()==0
  click('수정');f.get_by_label('피드백 수정',exact=True).fill('수정한 피드백');click('수정 저장')
  expect(f.locator('.feedback-card')).to_contain_text('수정한 피드백',timeout=20000);expect(f.locator('.feedback-card')).to_contain_text('수정됨')
  click('삭제');click('피드백 삭제');expect(f.locator('.feedback-card')).to_have_count(0,timeout=20000)
  click('팝업 닫기');page.set_viewport_size({'width':390,'height':844});click('＋ 일정 등록')
  f.get_by_label('일정명',exact=True).fill('빈 시간 테스트');click('일정 등록');expect(f.get_by_role('heading',name='빈 시간 테스트',exact=True)).to_be_visible(timeout=20000)
  expect(f.locator('.detail-line').filter(has_text='시간')).to_contain_text('시간 미정')
  page.screenshot(path='/tmp/calendar-workflows.png');b.close()
 print('PASS desktop drag/undo, shorthand time, blank time, feedback add/edit/delete, responsive dialogs')
finally:
 server.terminate();server.wait(timeout=10)
