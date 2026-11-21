// This component serves the same versioned schema that the widget reads from main.
(async () => {
  try {
    const response = await fetch('./widget-style.json', {cache: 'no-cache'});
    if (!response.ok) return;
    const style = await response.json();
    if (style.schema !== 1) return;
    const names = {TA:'ta', AP:'ap', PC:'pc', CS:'cs', '상담':'consult', '활동':'activity', '기타':'other', common:'common'};
    for (const [kind, name] of Object.entries(names)) {
      for (const [field, suffix] of [['palette',''], ['webInk','-ink'], ['webFill','-fill']]) {
        const color = style[field]?.[kind];
        if (/^#[0-9a-f]{6}$/i.test(color)) document.documentElement.style.setProperty('--calendar-' + name + suffix, color);
      }
    }
  } catch { /* The built-in palette remains available offline. */ }
})();
