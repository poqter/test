export default function({data, parentElement, setTriggerValue}) {
  const status = parentElement.querySelector('[role="status"]');
  // Window references survive the source app's rerun after a click.
  const pending = window.__hwCalcLaunches || (window.__hwCalcLaunches = new Map());
  const notify = message => { status.textContent = message; };
  const handle = event => {
    const button = event.target.closest('button[data-hw-calculator-launch]');
    if (!button) return;
    event.preventDefault();
    const name = button.dataset.hwCalculatorLaunch;
    if (!data.allowed.includes(name)) return;
    const child = window.open('about:blank', '_blank');
    if (!child) { notify('새 탭이 차단되었습니다. 브라우저에서 이 사이트의 팝업을 허용해주세요.'); return; }
    child.document.title = '화랑 계산기 준비 중';
    child.document.body.textContent = '계산기를 준비하고 있습니다…';
    const id = crypto.randomUUID();
    const url = new URL(window.location.href);
    url.search = ''; url.hash = '';
    url.searchParams.set('calc_view', name);
    url.searchParams.set('calc_tab', id);
    const timeout = window.setTimeout(() => {
      const item = pending.get(id);
      if (item) {
        try { if (!item.child.closed) item.child.document.body.textContent = '연결 시간이 초과되었습니다. 이 탭을 닫고 원래 화면에서 다시 열어주세요.'; } catch (_) {}
        pending.delete(id);
      }
    }, 60000);
    pending.set(id, {child, url:url.href, timeout});
    notify('계산기 전용 탭을 열고 있습니다.');
    setTriggerValue('request', {calculator:name, tab:id});
  };
  document.addEventListener('click', handle);
  const response = data.response;
  if (response && pending.has(response.tab)) {
    const item = pending.get(response.tab);
    pending.delete(response.tab);
    window.clearTimeout(item.timeout);
    try {
      if (item.child.closed) throw new Error('closed');
      if (!response.token) throw new Error('denied');
      // about:blank inherits our origin. Credentials go directly into this tab's
      // sessionStorage, never into a URL, cookie, localStorage or broadcast.
      item.child.sessionStorage.setItem('hw.calc.'+response.tab, JSON.stringify({grant:response.token}));
      item.child.opener = null;
      item.child.location.replace(item.url);
      notify('계산기 전용 탭을 열었습니다.');
    } catch (_) {
      try { if (!item.child.closed) item.child.document.body.textContent = '계산기를 열지 못했습니다. 이 탭을 닫고 원래 화면에서 다시 열어주세요.'; } catch (_) {}
      notify('새 탭 연결을 완료하지 못했습니다. 다시 열어주세요.');
    }
  }
  return () => document.removeEventListener('click', handle);
}
