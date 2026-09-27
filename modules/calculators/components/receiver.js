export default function({data, parentElement, setTriggerValue}) {
  const output = parentElement.querySelector('[role="status"]');
  const key = 'hw.calc.'+data.tab;
  const sent = window.__hwCalcReceiverSent || (window.__hwCalcReceiverSent = new Set());
  if (data.denied) {
    try { sessionStorage.removeItem(key); } catch (_) {}
    output.textContent = '이 탭의 이용 권한이 없거나 만료되었습니다.';
    return;
  }
  if (data.lease) {
    try { sessionStorage.setItem(key, JSON.stringify({lease:data.lease})); }
    catch (_) { output.textContent='이 브라우저에서는 새로고침 후 연결을 유지할 수 없습니다.'; }
    return;
  }
  let stored;
  try { stored = JSON.parse(sessionStorage.getItem(key)); } catch (_) {}
  const token = stored && (stored.lease || stored.grant);
  if (!token) { output.textContent='원래 워크스페이스에서 ‘새 탭으로 열기’를 눌러주세요.'; return; }
  // Changing phase (grant -> lease) can safely resend after a page reload.
  const attempt = data.attempt+':'+token;
  if (!sent.has(attempt)) {
    sent.add(attempt);
    setTriggerValue('credential', {kind:stored.lease?'lease':'grant', token});
  }
  output.textContent = '계산기 이용 권한을 확인하고 있습니다…';
}
