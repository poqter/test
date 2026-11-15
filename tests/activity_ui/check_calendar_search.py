"""Calendar search: explicit submit, pages, cross-month focus, temporary filters and scope isolation."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]/'modules/activity/calendar_view'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('https://calendar.test/**',lambda route:route.fulfill(path=str(root/(route.request.url.split('/')[-1] or 'index.html'))))
    page.goto('https://calendar.test/index.html')
    page.evaluate('''() => {
      window.searchRequests=[];window.searchHold=false;window.searchResolve=null;window.failSearch=false;
      HwarangRealtime={RealtimeClient:class {channel(){return {on(){return this},subscribe(){return this}}}async removeAllChannels(){}async disconnect(){}}};
      const row={id:'target',owner:'owner',owner_label:'작성자',day:'2027-02-28',start_time:'14:00',kind:'AP',status:'완료',title:'고객 상담',readable:true,place:'삼전역',revision:1};
      window.fetch=async(url,options)=>{
        const args=JSON.parse(options.body);
        if(url.endsWith('sales_calendar_search')){
          searchRequests.push(args);
          if(searchHold)return new Promise(resolve=>searchResolve=resolve);
          if(failSearch)return {ok:false,status:500};
          const rows=args.p_offset?[{...row,id:'more',title:'추가 상담'}]:[row,...Array.from({length:19},(_,i)=>({...row,id:'other'+i,title:'상담 '+i}))];
          return {ok:true,json:async()=>({rows,hasMore:!args.p_offset})};
        }
        return {ok:true,json:async()=>({compact:true,rows:args.first_day<=row.day&&args.last_day>=row.day?[row]:[],branch:[{member:'owner',label:'작성자'}],unit:'u',stamp:'v1',versions:{}})};
      };
      receiveCalendar({boot:{access:'scope',uid:'owner',managed:true,fast:true,ready:false,day:'2026-11-15',today:'2026-11-15',mode:'월간',team:false,member:null,members:{owner:'작성자'},people:{owner:'작성자'},insurers:[],kinds:['AP'],events:[],roster:{},rangeStart:'2026-10-26',rangeEnd:'2026-12-06',syncUnit:'u',syncStamp:null},mobileSession:{url:'https://api.test',key:'fake',token:'fake',uid:'owner'}});
      prefs.showWeekends=false;prefs.showCompleted=false;
    }''')
    page.wait_for_function('!calendarLoading')
    page.get_by_role('button',name='일정 검색',exact=True).click()
    page.get_by_label('검색어',exact=True).fill('상담')
    assert page.evaluate('searchRequests.length')==0
    page.get_by_label('검색어',exact=True).press('Enter')
    expect(page.locator('.calendar-search-result')).to_have_count(20)
    page.get_by_role('button',name='20건 더 보기',exact=True).click()
    expect(page.locator('.calendar-search-result')).to_have_count(21)
    assert page.evaluate('searchRequests[1].p_offset')==20
    page.locator('.calendar-search-result').first.click()
    expect(page.locator('.calendar-search-highlight')).to_have_count(1)
    assert page.evaluate('selected')=='2027-02-28'
    assert page.evaluate('latest.mode')=='월간'
    assert page.evaluate('[prefs.showWeekends,prefs.showCompleted]')==[False,False]
    expect(page.get_by_text('검색한 일정은 숨김 설정과 관계없이 표시됩니다.',exact=True)).to_be_visible()
    page.get_by_role('button',name='‹ 검색 결과로',exact=True).click()
    expect(page.get_by_label('검색어',exact=True)).to_have_value('상담')
    expect(page.locator('.calendar-search-result')).to_have_count(21)
    page.evaluate('failSearch=true')
    page.get_by_role('button',name='검색',exact=True).click()
    expect(page.get_by_role('button',name='다시 검색',exact=True)).to_be_visible()
    page.evaluate('failSearch=false')
    page.get_by_role('button',name='다시 검색',exact=True).click()
    expect(page.locator('.calendar-search-result')).to_have_count(20)
    page.evaluate('searchHold=true')
    page.get_by_role('button',name='검색',exact=True).click()
    page.wait_for_function('searchResolve!==null')
    page.get_by_role('button',name='팝업 닫기',exact=True).click()
    page.get_by_role('button',name='지점 일정',exact=True).click()
    page.evaluate("searchResolve({ok:true,json:async()=>({rows:[{title:'STALE'}],hasMore:false})})")
    page.wait_for_function('calendarSearch===null')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='일정 검색',exact=True).click()
    expect(page.get_by_label('검색어',exact=True)).to_have_value('')
    assert not errors,errors
    browser.close()
print('PASS explicit search / pagination / cross-month weekend completed focus / saved preferences / results return / retry / stale scope / mobile')
