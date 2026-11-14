"""Stable comparison editors and read-only downloads, with synthetic inputs."""
from pathlib import Path
import socket, subprocess, sys, time
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'tests/activity_ui/stability_harness.py'),'--server.headless=true','--server.port=8533','--browser.gatherUsageStats=false'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:socket.create_connection(('127.0.0.1',8533),.2).close();break
  except OSError:time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  for width in (1440,390):
   page=browser.new_page(viewport={'width':width,'height':1000})
   page.route('**/app/static/LINESeedKR-Bd.woff2',lambda route:route.fulfill(path=str(root/'static/LINESeedKR-Bd.woff2'),content_type='font/woff2'))
   page.goto('http://127.0.0.1:8533')
   title=page.get_by_role('textbox',name='자료 제목',exact=True)
   expect(title).to_be_visible()
   title.fill('입력 보존 검수');title.press('Tab')
   expect(title).to_have_value('입력 보존 검수')
   page.evaluate("window.originalTitle=document.querySelector('input[aria-label=\"자료 제목\"]')")
   page.get_by_role('button',name='+ 조건 추가',exact=True).first.click()
   expect(page.get_by_role('textbox',name='납입기간',exact=True)).to_have_count(3)
   expect(title).to_have_value('입력 보존 검수')
   assert page.evaluate("window.originalTitle===document.querySelector('input[aria-label=\"자료 제목\"]')")
   expect(page.get_by_text('전체 실행 횟수: 1',exact=True)).to_be_visible()
   page.get_by_role('button',name='예시 입력내용 입력하기',exact=True).click()
   page.get_by_role('button',name='예시로 교체',exact=True).click()
   step = page.locator('.st-key-hw_steps_enroll_step').get_by_text('3. 미리보기·PDF 저장', exact=True)
   expect(step).to_have_count(1)
   step.click()
   page.get_by_text('현재 보험료·조건·보장 내용을 확인했습니다.',exact=True).click()
   with page.expect_download() as download:page.get_by_role('button',name='PDF 저장',exact=True).click()
   assert download.value.suggested_filename.endswith('.pdf')
   expect(page.get_by_test_id('stException')).to_have_count(0)
   expect(page.get_by_text('전체 실행 횟수: 1',exact=True)).to_be_visible()
   page.evaluate("document.querySelector('[data-testid=stMain]').scrollTop=0")
   page.evaluate('document.fonts.ready')
   page.screenshot(path=f'/tmp/stability-comparison-{width}.png',full_page=True)
   page.goto('http://127.0.0.1:8533/?tool=calculator')
   page.get_by_role('button',name='예시 입력',exact=True).click()
   page.get_by_role('button',name='계산하기',exact=True).click()
   expect(page.get_by_role('button',name='결과 PDF 저장')).to_be_visible()
   with page.expect_download() as download:page.get_by_role('button',name='결과 PDF 저장').click()
   assert download.value.suggested_filename.endswith('.pdf')
   expect(page.get_by_test_id('stException')).to_have_count(0)
   expect(page.get_by_text('전체 실행 횟수: 1',exact=True)).to_be_visible()
   page.evaluate("document.querySelector('[data-testid=stMain]').scrollTop=0")
   page.evaluate('document.fonts.ready')
   page.screenshot(path=f'/tmp/stability-calculator-{width}.png',full_page=True)
   print(f'PASS {width}: stable DOM and values, fragment navigation, comparison/calculator PDF downloads',flush=True)
   page.close()
  browser.close()
finally:server.terminate();server.wait(timeout=10)
