from pathlib import Path
import subprocess,sys,time,socket,json
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/route_harness.py'),'--server.port=8517','--server.headless=true'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8517),timeout=.2):break
  except OSError:time.sleep(.2)
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page()
  for route in ('/calendar','/?view=mobile-calendar'):
   page.goto('http://127.0.0.1:8517'+route)
   expect(page.get_by_text('CALENDAR',exact=True)).to_be_visible()
   expect(page.get_by_text('view=mobile-calendar',exact=True)).to_be_visible()
   assert '/calendar' in page.url
  page.goto('http://127.0.0.1:8517/')
  expect(page.get_by_text('WORKSPACE',exact=True)).to_be_visible()
  expect(page.get_by_text('view=',exact=True)).to_be_visible()
  assert page.locator('link[rel="manifest"]').count()==0
  m=json.loads((ROOT/'static/calendar-manifest.json').read_text())
  assert m['scope']=='/calendar' and m['start_url']=='/calendar'
  assert not '/'.startswith(m['scope'])
  b.close()
 print('PASS calendar path, legacy redirect, workspace isolation and install scope')
finally:
 server.terminate();server.wait(timeout=10)
