"""The real iframe/grid paints on click, before a deliberately slow server."""
from pathlib import Path
import socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'tests/activity_ui/host_harness.py'),'--server.headless=true','--server.port=8522','--browser.gatherUsageStats=false'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8522),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  for width in (1440,390):
   page=browser.new_page(viewport={'width':width,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8522/?fail=1' if width==390 else 'http://127.0.0.1:8522')
   iframe=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]')
   iframe.wait_for(state='attached');f=iframe.element_handle().content_frame()
   f.wait_for_function('typeof workspaceHost!=="undefined" && !!workspaceHost && !!latest')
   f.evaluate("window.testFrame=crypto.randomUUID();window.testGrid=document.querySelector('.cell');")
   token=f.evaluate('testFrame')
   expect(iframe).not_to_be_visible()
   started=time.monotonic();page.get_by_role('button',name='영업활동 관리 열기',exact=True).click()
   expect(iframe).to_be_visible(timeout=700)
   expect(f.locator('.cell').first).to_be_visible(timeout=700)
   assert time.monotonic()-started<1,'Calendar waited for server context'
   expect(page.get_by_role('heading',name='홈 본문',exact=True)).not_to_be_visible()
   assert f.evaluate('calendarBoot===null'),'Calendar is already rendered before access/context'
   expect(f.get_by_role('button',name='＋ 일정 등록')).to_be_disabled()
   if width==390:
    expect(f.get_by_role('button',name='다시 불러오기',exact=True)).to_be_visible(timeout=10000)
    expect(iframe).to_be_visible()
    f.get_by_role('button',name='다시 불러오기',exact=True).click()
   f.wait_for_function('!!calendarBoot && !calendarLoading',timeout=20000)
   assert f.evaluate('testFrame')==token
   assert f.evaluate("testGrid===document.querySelector('.cell')"),'Grid replaced on authorization'
   f.get_by_role('button',name='＋ 일정 등록',exact=True).click()
   field=f.get_by_label('일정명',exact=True);field.fill('유지할 초안');field.evaluate('e=>e.setSelectionRange(2,2)')
   f.evaluate("window.testPanel=calendarPanel;window.testInput=document.activeElement;render({...latest,events:[...latest.events,{id:'remote',day:latest.day,kind:'AP',short:'다른 직원 변경',label:'다른 직원 변경',readable:false}]})")
   expect(field).to_have_value('유지할 초안')
   assert f.evaluate('calendarPanel===testPanel && document.activeElement===testInput && testInput.selectionStart===2')
   f.get_by_role('button',name='팝업 닫기').click();f.get_by_role('button',name='내용 유지하고 닫기').click()
   if width==390:page.get_by_test_id('stExpandSidebarButton').click()
   page.get_by_role('button',name='홈',exact=True).click()
   expect(page.get_by_role('heading',name='홈 본문',exact=True)).to_be_visible(timeout=15000)
   expect(iframe).not_to_be_visible()
   if width==390:page.get_by_test_id('stSidebarCollapseButton').locator('button').click()
   page.get_by_role('button',name='영업활동 관리 열기',exact=True).click();expect(iframe).to_be_visible(timeout=700)
   f.wait_for_function('!workspaceHost.pending() && parentVisible && !calendarLoading',timeout=20000)
   assert f.evaluate('testFrame')==token
   f.get_by_role('button',name='＋ 일정 등록',exact=True).click();expect(field).to_have_value('유지할 초안')
   f.get_by_label('시작 시간',exact=True).fill('13:00')
   f.get_by_label('종료 시간 · 선택',exact=True).fill('12:00')
   f.get_by_role('button',name='일정 등록',exact=True).click()
   expect(f.get_by_text('종료 시간은 시작 시간보다 늦어야 합니다.',exact=True)).to_be_visible(timeout=15000)
   expect(f.get_by_role('button',name='일정 등록',exact=True)).to_be_enabled()
   expect(field).to_have_value('유지할 초안')
   f.get_by_label('종료 시간 · 선택',exact=True).fill('')
   f.get_by_role('button',name='일정 등록',exact=True).click()
   expect(f.get_by_role('heading',name='유지할 초안',exact=True)).to_be_visible(timeout=15000)
   assert not errors,errors
   print(f'PASS {width}: immediate real grid, same iframe/nodes, server hydration, editor focus, retained draft and reentry',flush=True)
   page.close()
  browser.close()
finally:server.terminate();server.wait(timeout=10)
