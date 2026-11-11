"""The retained search input must reflect the selected calendar scope."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]/'modules/activity/calendar_view'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 for width in (390,1280):
  page=browser.new_page(viewport={'width':width,'height':900})
  page.route('https://calendar.test/**',lambda r:r.fulfill(path=str(root/r.request.url.rsplit('/',1)[-1])))
  page.goto('https://calendar.test/index.html')
  page.evaluate('''() => {
   window.loads=[];
   rpc=async(op,args)=>{loads.push(args);return {events:[],rangeStart:args.first,rangeEnd:args.last}};
   receiveCalendar({bootFresh:true,boot:{uid:'owner',access:'scope',ready:true,day:'2026-11-06',today:'2026-11-06',mode:'월간',managed:true,team:false,member:null,members:{owner:'Owner One',peer:'Peer Two'},people:{},events:[],roster:{},rangeStart:'2026-10-26',rangeEnd:'2026-12-06'},mobileSession:{}});
   window.retainedInput=document.querySelector('.member-search input');
  }''')
  search=page.get_by_label('구성원 검색',exact=True)
  for label in ('Peer Two','Owner One'):
   search.fill(label.split()[0])
   page.evaluate('calendarLoading=true;render(latest);calendarLoading=false;render(latest)')
   expect(search).to_have_value(label.split()[0])
   page.get_by_role('button',name=label+' 일정 보기',exact=True).click()
   expect(search).to_have_value(label)
   page.wait_for_function('!calendarLoading')
   assert page.evaluate('retainedInput===document.querySelector(".member-search input")')
   assert page.evaluate('calendarBoot.member')==('peer' if label=='Peer Two' else 'owner')
   page.get_by_role('button',name='내 일정',exact=True).click()
   expect(search).to_have_value('')
   page.wait_for_function('!calendarLoading')
   assert page.evaluate('calendarBoot.member===null && calendarBoot.team===false')
  search.fill('Peer')
  page.evaluate("calendarBoot.members={owner:'Owner One'};calendarBoot.access='reduced';render({...latest,scopeLabel:'reduced'})")
  expect(page.get_by_role('button',name='Peer Two 일정 보기',exact=True)).to_have_count(0)
  assert page.evaluate('retainedInput!==document.querySelector(\".member-search input\")')
  page.close()
 browser.close()
print('PASS selected-member label, reset to own scope, repeated search and retained input on mobile/desktop')
