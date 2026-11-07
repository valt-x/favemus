/**
 * Favemus Auth — Login / Register
 */
async function submitAuth(endpoint, body, btnId) {
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.textContent = 'Please wait…';
  const r = await fetch(endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const errEl = document.getElementById('e');
    errEl.textContent = d.detail || 'Failed — try again';
    btn.disabled = false;
    btn.textContent = btn.dataset.label || 'Submit';
    return false;
  }
  location.href = '/owner';
  return false;
}
