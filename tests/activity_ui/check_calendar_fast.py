"""Direct payload, stale-cache refresh and live changes without editor remounts."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]/'modules/activity/calendar_view'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1280,'height':900})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def asset(route):
  name=route.request.url.split('/')[-1] or 'index.html'
  route.fulfill(path=str(root/name))
 page.route('https://calendar.test/**',asset)
 page.goto('https://calendar.test/index.html')
 page.evaluate('''() => {
 window.testRequests=[];window.testPending=[];window.testSignals=[];window.testDisconnects=0;
 window.fetch=(url,options)=>{testRequests.push({url,options});return new Promise(resolve=>testPending.push(resolve))};
 HwarangRealtime={RealtimeClient:class {
  channel(){return {on(type,filter,callback){testSignals.push({filter,callback});return this},subscribe(callback){window.testSubscribe=callback;return this}}}
  async removeAllChannels(){} async disconnect(){testDisconnects++} async setAuth(){}
 }};
 receiveCalendar({boot:{access:'same-user-and-scope',uid:'owner',fast:true,ready:false,day:'2026-11-06',today:'2026-11-06',mode:'월간',team:true,member:null,members:{owner:'작성자'},people:{owner:'작성자',peer:'직원'},insurers:[],kinds:['미분류','AP'],events:[],roster:{},rangeStart:'2026-10-26',rangeEnd:'2026-12-06',syncUnit:'unit',syncStamp:null},mobileSession:{url:'https://api.test',key:'public-test',token:'user-token',uid:'owner'}});
 }''')
 expect(page.get_by_role('button',name='＋ 일정 등록',exact=True)).to_be_visible()
 assert page.evaluate('testRequests.length')==1
 request=page.evaluate('testRequests[0]');assert request['url'].endswith('/rpc/sales_calendar_payload');assert request['options']['headers']['Authorization']=='Bearer user-token'
 row=dict(id='event',owner='owner',day='2026-11-06',start_time=None,kind='AP',status='예정',companion=None,common=False,time_pending=True,title='처음 일정',help=False)
 bundle=dict(rows=[row],summary=[row],branch=[dict(member='owner',label='작성자')],unit='unit',stamp='v1')
 def resolve(data):page.evaluate('(data)=>testPending.shift()({ok:true,json:async()=>data})',data)
 resolve(bundle);expect(page.locator('.chip')).to_have_text('처음 일정 · 작성자')
 page.get_by_role('button',name='＋ 일정 등록',exact=True).click()
 page.wait_for_function("calendarFlight?.op==='support_recipients'")
 page.evaluate("receiveCalendar({boot:calendarBoot,mobileSession:latest.mobileSession,reply:{nonce:calendarFlight.nonce,ok:true,result:{}}})")
 expect(page.get_by_label('일정명',exact=True)).to_be_focused();page.get_by_label('일정명',exact=True).fill('작성 중 보존')
 # Subscription acknowledgment validates the visible range; same stamp does not reload.
 page.evaluate("testSubscribe('SUBSCRIBED')");page.wait_for_function('testPending.length===1');resolve('v1')
 page.wait_for_function('!syncBusy');assert page.evaluate('testRequests.length')==2
 page.evaluate('testSignals[0].callback()');page.wait_for_function('testPending.length===1');resolve('v2')
 page.wait_for_function('testPending.length===1');bundle['rows'][0]['title']='다른 화면 변경';bundle['stamp']='v2';resolve(bundle)
 expect(page.locator('.chip')).to_have_text('다른 화면 변경 · 작성자');expect(page.get_by_label('일정명',exact=True)).to_have_value('작성 중 보존')
 # Reentry paints the memory cache synchronously, then makes one freshness request.
 page.evaluate("() => {const args={boot:{...calendarBoot},mobileSession:latest.mobileSession};calendarPanel.remove();calendarPanel=null;calendarBoot=null;receiveCalendar(args)}")
 expect(page.locator('.chip')).to_have_text('다른 화면 변경 · 작성자');assert page.evaluate('testPending.length')==1
 resolve(bundle);page.wait_for_function('!calendarLoading')
 page.evaluate('parentVisible=false;configureRealtime(latest)');page.wait_for_function('testDisconnects===1');assert page.evaluate('realtimeClient===null')
 assert not errors,errors
 browser.close()
print('PASS one direct request; visible-range change detection; draft preserved; instant cached reentry; hidden connection cleanup')
