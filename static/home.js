/**
 * Favemus Home / Raw Chat UI
 */
let sid = localStorage.getItem('favemus_sid');
if (!sid) {
  sid = 'web-' + Math.random().toString(36).slice(2, 12);
  localStorage.setItem('favemus_sid', sid);
}
const log = document.getElementById('log');
const trace = document.getElementById('trace');

function add(t, c) {
  const d = document.createElement('div');
  d.className = 'msg ' + c;
  d.textContent = t;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function reset() {
  localStorage.removeItem('favemus_sid');
  location.reload();
}

async function send(e) {
  e.preventDefault();
  const i = document.getElementById('msg');
  const t = i.value.trim();
  if (!t || i.disabled) return;
  i.value = '';
  i.disabled = true;
  add(t, 'user');
  add('Favemus is typing…', 'bot');
  trace.textContent = 'Thinking… (AI takes 2–5s)';
  const ctl = new AbortController();
  const to = setTimeout(() => ctl.abort(), 60000);
  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      signal: ctl.signal,
      body: JSON.stringify({ message: t, session_id: sid, channel: 'web' }),
    });
    const d = await r.json();
    sid = d.session_id;
    localStorage.setItem('favemus_sid', sid);
    log.lastChild.textContent = d.reply;
    trace.innerHTML = '';
    const b = document.createElement('span');
    b.className = 'badge';
    b.textContent = 'action=' + d.action + ' state=' + d.state + ' session=' + d.session_id;
    trace.appendChild(b);
    trace.appendChild(
      document.createTextNode('\n\n' + JSON.stringify({ analysis: d.analysis, tool_call: d.tool_call, routing: d.routing }, null, 2))
    );
  } catch (err) {
    log.lastChild.textContent = err.name === 'AbortError' ? 'Timed out — AI is busy. Try again.' : 'Error: ' + err;
    trace.textContent = String(err);
  } finally {
    clearTimeout(to);
    i.disabled = false;
    i.focus();
  }
}

add('Hi! Try: "Where is my order FAV-1042?" or "I want to return FAV-2231, the dress is torn."', 'sys');
