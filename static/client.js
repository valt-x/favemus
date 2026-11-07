/**
 * Favemus Client Layer — chat UI
 */
let sid = localStorage.getItem('favemus_sid');
if (!sid) {
  sid = 'web-' + Math.random().toString(36).slice(2, 12);
  localStorage.setItem('favemus_sid', sid);
}
const log = document.getElementById('log');

function add(t, c) {
  const d = document.createElement('div');
  d.className = 'msg ' + c;
  d.textContent = t;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function typing(on) {
  const old = document.querySelector('.typing');
  if (on && !old) {
    const d = document.createElement('div');
    d.className = 'msg bot typing';
    d.innerHTML = '<i></i><i></i><i></i>';
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  if (!on && old) old.remove();
}

function quick(t) {
  const msg = document.getElementById('msg');
  msg.value = t;
  msg.dispatchEvent(new Event('submit', { cancelable: true }));
  send(new Event('submit', { cancelable: true }));
}

let sending = false;
async function send(e) {
  e.preventDefault();
  const i = document.getElementById('msg');
  const t = i.value.trim();
  if (!t || sending) return;
  sending = true;
  i.disabled = true;
  document.getElementById('sendBtn').disabled = true;
  i.value = '';
  add(t, 'user');
  typing(true);
  const ctl = new AbortController();
  const timeout = setTimeout(() => ctl.abort(), 60000);
  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      signal: ctl.signal,
      body: JSON.stringify({ message: t, session_id: sid, channel: 'web' })
    });
    const d = await r.json();
    sid = d.session_id;
    localStorage.setItem('favemus_sid', sid);
    typing(false);
    add(d.reply || 'Sorry, I could not answer that.', 'bot');
  } catch (err) {
    typing(false);
    add(
      err.name === 'AbortError'
        ? 'Timed out — the AI is busy. Please try again.'
        : 'Network error. Please try again.',
      'bot'
    );
  } finally {
    clearTimeout(timeout);
    sending = false;
    i.disabled = false;
    document.getElementById('sendBtn').disabled = false;
    i.focus();
  }
  loadMine();
}

async function logout() {
  await fetch('/auth/logout', { method: 'POST' });
  location.reload();
}

async function loadMine() {
  const m = await fetch('/auth/me');
  if (!m.ok) return;
  const j = await m.json();
  document.getElementById('who').textContent = j.user.email;
  document.getElementById('mine').textContent = '';

  const s = await (await fetch('/harness/my/sessions')).json();
  const st = document.getElementById('sessions');
  st.innerHTML =
    '<tr><th>Session</th><th>State</th></tr>' +
    (s.sessions || [])
      .map(x => '<tr><td><code>' + x.id + '</code></td><td>' + (x.state || '') + '</td></tr>')
      .join('');
  st.style.display = 'table';

  const t = await (await fetch('/harness/my/tickets')).json();
  const tk = document.getElementById('tickets');
  tk.innerHTML =
    '<tr><th>Ticket</th><th>Kind</th><th>Status</th></tr>' +
    (t.tickets || [])
      .map(
        x =>
          '<tr><td>#' +
          x.id +
          '</td><td>' +
          (x.kind || '') +
          '</td><td><span class="badge ' +
          (x.status || '') +
          '">closed' +
          x.status +
          '</span></td></tr>'
      )
      .join('');
  tk.style.display = 'table';
}

add(
  'Hi! I\'m your AI support assistant. Ask me about orders, returns, products, or refunds — or send “human” anytime.',
  'bot'
);
loadMine();
