"""Exercise permanent delete confirmation in the existing separate calendar entry using fake API."""
from pathlib import Path
import json
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]/'modules/activity/calendar_view/pwa/calendar'
row=dict(id='event',owner='owner',unit='unit',day='2026-11-06',title='삭제 확인 일정',kind='AP',status='예정',start_time=None,end_time=None,companion=None,common=False,revision=1,time_pending=True)
deleted=False
with sync_playwright() as p:
    b=p.chromium.launch();page=b.new_page()
    def route(r):
        global deleted
        path=urlsplit(r.request.url).path
        if path.startswith('/rest/v1/'):
            if path.endswith('sales_delete_event'):
                body=r.request.post_data_json
                assert body['p_id']==row['id'] and body['p_revision']==row['revision']
                assert body['p_future'] is False
                deleted=True;data=1
            elif path.endswith('sales_branch_members'):data=[dict(member='owner',label='본인')]
            elif path.endswith('sales_members'):data=[dict(member='owner',label='본인',managed=False)]
            elif path.endswith('sales_calendar_days'):data=[] if deleted else [row]
            elif path.endswith('sales_events'):
                data=[] if deleted else [row]
            else:data=[]
            r.fulfill(json=data);return
        f=root/('index.html' if path=='/' else path.lstrip('/'))
        if f.name=='entry.js':r.fulfill(body='// Test the retained embedded editor separately from the shortcut redirect.')
        elif f.exists():r.fulfill(path=str(f))
        else:r.fulfill(status=404)
    page.route('https://calendar.test/**',route);page.goto('https://calendar.test/')
    page.evaluate("s=>start(s)",dict(uid='owner',unit='unit',url='https://calendar.test',key='fake',token='fake'))
    page.evaluate('r=>openForm(r.day,r)',row)
    expect(page.get_by_role('button',name='일정 삭제',exact=True)).to_be_visible()
    page.once('dialog',lambda d:d.dismiss())
    page.get_by_role('button',name='일정 삭제',exact=True).click()
    expect(page.locator('#sheet')).to_be_visible()
    assert not deleted
    page.once('dialog',lambda d:d.accept())
    page.get_by_role('button',name='일정 삭제',exact=True).click()
    expect(page.locator('#sheet')).not_to_be_visible()
    assert deleted
    expect(page.get_by_role('button',name='삭제한 일정',exact=True)).to_have_count(0)
    expect(page.get_by_role('button',name='복구',exact=True)).to_have_count(0)
    b.close()
print('PASS retained calendar editor: cancel preserves event; confirmed deletion removes it without restore')
