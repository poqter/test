"""Exercise delete/restore in the existing separate calendar entry using fake API."""
from pathlib import Path
import json
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]/'modules/activity/calendar_view/pwa/calendar'
row=dict(id='event',owner='owner',unit='unit',day='2026-11-06',title='삭제 확인 일정',kind='AP',status='예정',start_time=None,end_time=None,companion=None,common=False,revision=1,time_pending=True)
with sync_playwright() as p:
    b=p.chromium.launch();page=b.new_page()
    def route(r):
        path=urlsplit(r.request.url).path
        if path.startswith('/rest/v1/'):
            if path.endswith('sales_archive_event'):
                body=r.request.post_data_json
                assert body['p_id']==row['id'] and body['p_revision']==row['revision']
                row['deleted_at']=None if body['p_restore'] else '2026-11-06T00:00:00Z';row['revision']+=1;data=1
            elif path.endswith('sales_branch_members'):data=[dict(member='owner',label='본인')]
            elif path.endswith('sales_members'):data=[dict(member='owner',label='본인',managed=False)]
            elif path.endswith('sales_calendar_days'):data=[] if row.get('deleted_at') else [row]
            elif path.endswith('sales_events'):
                trash='deleted_at=gte.' in r.request.url
                data=[row] if bool(row.get('deleted_at'))==trash else []
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
    page.on('dialog',lambda d:d.accept())
    page.get_by_role('button',name='일정 삭제',exact=True).click()
    expect(page.locator('#sheet')).not_to_be_visible()
    assert row['deleted_at']
    page.get_by_role('button',name='삭제한 일정',exact=True).click()
    page.get_by_role('button',name='2026-11-06 · 삭제 확인 일정 · 복구',exact=True).click()
    expect(page.get_by_role('button',name='2026-11-06 · 삭제 확인 일정 · 복구',exact=True)).to_have_count(0)
    assert row['deleted_at'] is None
    b.close()
print('PASS separate calendar delete confirmation and restore')
