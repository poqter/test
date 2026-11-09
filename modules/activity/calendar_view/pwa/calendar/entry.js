// Installed shortcuts keep their existing URL and icon identity.
// The workspace owns the 30-day device session; do not copy tokens here.
if (window.parent === window) {
  document.documentElement.style.visibility = 'hidden';
  window.location.replace(new URL('/calendar',window.location.href).href);
}
