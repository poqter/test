"""Real Streamlit/browser tests with fake data; never touches production."""
from pathlib import Path
import os,socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
log=open('/tmp/hwarang-persistent-test.log','w')
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/persistent_harness.py'),'--server.headless=true','--server.port=8511','--browser.gatherUsageStats=false'],cwd=ROOT,stdout=log,stderr=log)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8511),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  launch={'headless':True,'args':['--no-sandbox','--no-zygote','--single-process']}
  if os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE'):launch['executable_path']=os.environ['PLAYWRIGHT_CHROMIUM_EXECUTABLE']
  for width in (390,820,1440):
   browser=p.chromium.launch(**launch)
   page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda e:(errors.append(str(e)),print('JSERROR',e,flush=True)))
   page.goto('http://127.0.0.1:8511/?surface='+('pc' if width==1440 else 'mobile'));iframe=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]');expect(iframe).to_be_visible()
   f=iframe.element_handle().content_frame();expect(f.locator('.cell')).to_have_count(30)
   f.evaluate('''() => {window.__calendarTest={grid:document.querySelector('#grid'),token:crypto.randomUUID(),blank:0};function sample(){if(document.querySelector('#grid')!==window.__calendarTest.grid)window.__calendarTest.blank++;requestAnimationFrame(sample)}sample()}''')
   f.wait_for_function('calendarLayoutReady');assert f.evaluate('calendarSeq')==1, 'Empty shell starts exactly one load';token=f.evaluate('window.__calendarTest.token');height=iframe.bounding_box()['height']
   def click(name):
    try:f.get_by_role('button',name=name,exact=True).click()
    except Exception:
     page.screenshot(path='/tmp/calendar-failure.png');print('GEOMETRY',iframe.bounding_box(),f.evaluate('({inner:innerHeight,frame:lastFrameHeight,body:document.body.getBoundingClientRect().toJSON(),panel:calendarPanel?.getBoundingClientRect().toJSON(),client:calendarPanel?.clientHeight,scroll:calendarPanel?.scrollHeight,scrollTop:calendarPanel?.scrollTop})'),flush=True);raise
   def backdrop():
    box=iframe.bounding_box();page.mouse.click(box['x']+2,box['y']+2)
   click('＋ 일정 등록');expect(f.get_by_role('dialog')).to_be_visible();expect(f.get_by_label('일정명',exact=True)).to_be_focused()
   f.evaluate("async () => {await Promise.all(calendarPanel.getAnimations().map(a=>a.finished.catch(()=>{})))}")
   geometry=f.evaluate("({b:calendarPanel.getBoundingClientRect().toJSON(),w:innerWidth,h:innerHeight})")
   assert abs(geometry['b']['x']+geometry['b']['width']/2-geometry['w']/2)<3
   assert abs(geometry['b']['y']+geometry['b']['height']/2-geometry['h']/2)<3
   f.evaluate("document.fonts.ready")
   assert f.evaluate("[...document.fonts].some(x=>x.family==='HW LINE Seed' && x.status==='loaded')")
   backdrop();expect(f.get_by_role('dialog')).to_have_count(0)
   click('＋ 일정 등록');f.get_by_label('일정명',exact=True).fill('배경 클릭 작성 보존')
   f.evaluate("async () => {await Promise.all(calendarPanel.getAnimations().map(a=>a.finished.catch(()=>{})))}")
   before=f.locator('dialog.calendar-panel').bounding_box()
   backdrop();expect(f.get_by_role('dialog',name='저장하지 않은 변경이 있습니다.',exact=True)).to_be_visible()
   assert f.locator('dialog.calendar-panel dialog').count()==0
   assert f.locator('dialog.calendar-panel').bounding_box()==before
   expect(f.get_by_role('button',name='계속 작성',exact=True)).to_be_focused()
   page.screenshot(path=f'/tmp/calendar-confirm-{width}.png')
   f.locator('body').press('Escape');expect(f.locator('.calendar-close-confirm')).to_have_count(0)
   expect(f.get_by_label('일정명',exact=True)).to_have_value('배경 클릭 작성 보존')
   backdrop();backdrop();expect(f.locator('.calendar-close-confirm')).to_have_count(0)
   expect(f.get_by_label('일정명',exact=True)).to_have_value('배경 클릭 작성 보존')
   backdrop();click('계속 작성')
   f.locator('body').press('Escape');click('내용 유지하고 닫기')
   click('＋ 일정 등록');expect(f.get_by_label('일정명',exact=True)).to_have_value('배경 클릭 작성 보존')
   backdrop();click('저장하지 않고 닫기')
   click('＋ 일정 등록');expect(f.get_by_label('일정명',exact=True)).to_have_value('')
   f.evaluate("calendarPanel.dataset.busy='true'");backdrop();expect(f.get_by_role('dialog')).to_be_visible()
   f.locator('body').press('Escape');expect(f.get_by_role('dialog')).to_be_visible()
   f.evaluate("delete calendarPanel.dataset.busy");click('팝업 닫기')
   assert f.get_by_label('최근 장소',exact=True).count()==0
   click('다음 기간');expect(f.locator('#nav h2')).to_have_text('2026년 12월')
   click('이전 기간');expect(f.locator('#nav h2')).to_have_text('2026년 11월')
   click('주간');expect(f.locator('#grid')).to_have_class('grid weekends-off week')
   click('다음 기간');expect(f.locator('#nav h2')).to_have_text('11월 9일 – 11월 13일');click('월간')
   click('2026-11-06 일정 보기');click('주간')
   f.get_by_role('button',name='14:00 · AP · 테스트 작성자 · 결과 미입력',exact=True).first.click()
   click('일정 수정');f.get_by_label('일정명',exact=True).fill('수정 확인 '+str(width))
   if width==390:
    page.evaluate('history.back()');expect(f.get_by_role('button',name='계속 작성',exact=True)).to_be_visible();click('계속 작성')
   click('팝업 닫기');click('내용 유지하고 닫기')
   f.get_by_role('button',name='14:00 · AP · 테스트 작성자 · 결과 미입력',exact=True).first.click();click('일정 수정')
   expect(f.get_by_label('일정명',exact=True)).to_have_value('수정 확인 '+str(width))
   click('변경 저장');expect(f.get_by_role('heading',name='수정 확인 '+str(width),exact=True)).to_be_visible()
   detail=f.get_by_role('dialog',name='일정 상세',exact=True)
   detail.evaluate('e=>e.dataset.resultContinuity="preserved"')
   click('완료 · 결과 처리')
   overlay=f.get_by_role('dialog',name='완료 · 결과 처리',exact=True)
   expect(overlay).to_be_visible()
   assert overlay.bounding_box()['width']<=width
   overlay.get_by_label('처리 결과',exact=True).select_option('연기')
   overlay.get_by_label('새 일정 날짜',exact=True).fill('2026-11-20')
   overlay.get_by_label('새 일정 시작 시간',exact=True).fill('16:10')
   overlay.get_by_label('새 일정 종료 시간 · 선택',exact=True).fill('15:00')
   overlay.get_by_role('button',name='결과 저장',exact=True).click()
   expect(overlay.get_by_text('새 일정 종료 시간은 시작 시간보다 늦어야 합니다.',exact=True)).to_be_visible()
   expect(detail).to_have_attribute('data-result-continuity','preserved')
   overlay.get_by_label('새 일정 종료 시간 · 선택',exact=True).fill('17:20')
   overlay.get_by_label('활동 결과 · 선택',exact=True).fill('시간 재조정')
   overlay.get_by_role('button',name='결과 저장',exact=True).click()
   expect(overlay).to_have_count(0)
   expect(f.get_by_role('dialog',name='일정 상세',exact=True)).to_contain_text('시간 재조정')
   expect(f.get_by_role('dialog',name='일정 상세',exact=True)).to_contain_text('14:00–15:00')
   click('팝업 닫기')
   click('＋ 일정 등록');f.get_by_label('일정명',exact=True).fill('반복 일정 테스트')
   f.locator('summary').filter(has_text='추가 정보 · 선택').click();f.get_by_label('매주 반복',exact=True).check();f.get_by_label('총 등록 횟수 · 이번 일정 포함',exact=True).fill('2')
   click('일정 등록');expect(f.get_by_role('heading',name='반복 일정 테스트',exact=True)).to_be_visible()
   f.wait_for_function('!calendarLoading && !calendarFlight')
   repeat_ids=f.evaluate("latest.events.filter(e=>e.short==='반복 일정 테스트').map(e=>e.id)")
   assert len(repeat_ids)==2
   click('일정 삭제')
   expect(f.get_by_role('dialog')).to_contain_text('즉시 삭제되며 복구할 수 없습니다')
   click('일정 삭제 확인');expect(f.get_by_role('dialog')).to_have_count(0)
   expect(f.get_by_role('button',name='복구',exact=True)).to_have_count(0)
   f.wait_for_function('!calendarLoading && !calendarFlight')
   remaining=f.evaluate("latest.events.filter(e=>e.short==='반복 일정 테스트').map(e=>e.id)")
   assert len(remaining)==1 and remaining[0] in repeat_ids
   # Settings and scope stay inside the mounted frame; no host widget recreation.
   click('월간')
   f.locator('.view-settings > summary').click();f.get_by_label('주말 표시',exact=True).check();expect(f.locator('.cell')).to_have_count(42)
   f.get_by_label('주말 표시',exact=True).uncheck();expect(f.locator('.cell')).to_have_count(30);click('보기 설정 닫기')
   f.get_by_label('구성원 검색',exact=True).fill('테스트 작성자');f.get_by_role('button',name='테스트 작성자 일정 보기',exact=True).click()
   f.get_by_role('button',name='내 일정',exact=True).click()
   f.wait_for_function('!calendarLoading && !calendarFlight');assert f.evaluate('window.__calendarTest.token')==token
   assert f.evaluate('window.__calendarTest.blank')==0
   assert iframe.bounding_box()['height']==height
   # A reused server boot must refresh when the frame is mounted again.
   f.evaluate('''() => {const boot={...calendarBoot};calendarBoot=null;receiveCalendar({boot,bootFresh:false,mobileSession:latest.mobileSession});}''')
   f.wait_for_function('!calendarLoading && !calendarFlight')
   expect(page.locator('[data-testid="stException"]')).to_have_count(0)
   page.emulate_media(reduced_motion='reduce')
   click('＋ 일정 등록');expect(f.get_by_label('일정명',exact=True)).to_be_focused()
   assert f.evaluate("getComputedStyle(calendarPanel).transitionDuration")== '0s'
   click('팝업 닫기');expect(f.get_by_role('dialog')).to_have_count(0)
   assert not errors,errors
   page.screenshot(path=f'/tmp/calendar-persistent-{width}.png')
   print('PASS',width,'navigation/forms/drafts/save/repeat/permanent delete; persistent frame/grid/height',flush=True);browser.close()
  browser.close()
finally:
 server.terminate();server.wait(timeout=10);log.close()
