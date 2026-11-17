// Apply the saved theme before first paint to avoid a flash. Dark is the default.
// This is a separate file (not inline) so a strict Content-Security-Policy can forbid inline scripts.
try {
  var t = localStorage.getItem('gp-theme')
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t
} catch (e) {
  /* storage unavailable: keep the default theme */
}
