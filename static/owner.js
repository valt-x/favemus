/**
 * Favemus Owner Console — dark dashboard
 */
const $ = (id) => document.getElementById(id);

function toast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + (type || 'success');
  setTimeout(() => (t.className = ''), 3000);
}

async function api(p, opt) {
  const ctl = new AbortController();
  const timeout = setTimeout(() => ctl.abort(), 15000);
  opt = { ...(opt || {}), signal: ctl.signal };
  let r;
  try {
    r = await fetch(p, opt);
  } catch (e) {
    toast('Timeout/network: ' + p, 'error');
    throw e;
  } finally {
    clearTimeout(timeout);
  }
  if (r.status === 401) {
    location.href = '/login';
    throw new Error('login');
  }
  if (!r.ok) throw new Error(p + ' -> ' + r.status);
  return r.json();
}

async function logout() {
  await fetch('/auth/logout', { method: 'POST' });
  location.href = '/login';
}

async function waTest(e) {
  e.preventDefault();
  const to = $('wa-to').value;
  const r = await api('/harness/whatsapp/test', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      to,
      message: $('wa-msg').value || 'Hello from Favemus AI Support!',
    }),
  });
  toast(r.ok ? 'WhatsApp sent!' : 'Not sent — check config', 'success');
}

async function addUser(e) {
  e.preventDefault();
  try {
    await api('/harness/users', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        email: $('nu-email').value,
        password: $('nu-pw').value,
        name: $('nu-name').value,
        role: $('nu-role').value,
      }),
    });
    toast('User created');
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
  load();
}

async function addOrder(e) {
  e.preventDefault();
  try {
    await api('/harness/orders', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        order_id: $('no-id').value,
        item: $('no-item').value || 'your order',
        amount: Number($('no-amount').value || 0),
        status: $('no-status').value || 'processing',
        eta: $('no-eta').value || null,
      }),
    });
    toast('Order saved');
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
  load();
}

async function addProduct(e) {
  e.preventDefault();
  try {
    await api('/harness/products', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        sku: $('np-sku').value,
        name: $('np-name').value,
        price: Number($('np-price').value || 0),
        sizes: $('np-sizes')
          .value.split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    });
    toast('Product saved');
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
  load();
}

async function toggle(u) {
  await api('/harness/users/' + u + '/toggle-active', { method: 'POST' });
  toast('User toggled');
  load();
}

async function del(u) {
  if (!confirm('Delete this user?')) return;
  await api('/harness/users/' + u, { method: 'DELETE' });
  toast('User deleted');
  load();
}

async function delO(o) {
  if (!confirm('Delete order ' + o + '?')) return;
  await api('/harness/orders/' + encodeURIComponent(o), { method: 'DELETE' });
  toast('Order deleted');
  load();
}

async function delP(s) {
  if (!confirm('Delete product ' + s + '?')) return;
  await api('/harness/products/' + encodeURIComponent(s), { method: 'DELETE' });
  toast('Product deleted');
  load();
}

async function closeT(t) {
  if (!confirm('Close ticket #' + t + '?')) return;
  await api('/harness/tickets/' + t + '/close', { method: 'POST' });
  toast('Ticket closed');
  load();
}

function stBadge(s) {
  return s === 'open'
    ? '<span class="badge amber">open</span>'
    : s === 'closed'
    ? '<span class="badge green">closed</span>'
    : '<span class="badge">' + s + '</span>';
}

async function load() {
  const me = await api('/auth/me');
  $('who').textContent = me.user.email + ' · ' + me.user.role;

  try {
    const w = await api('/whatsapp/status');
    $('wa-status').innerHTML = w.configured
      ? '<span style="color:var(--green)">● Configured</span> (' + w.api_version + ')'
      : '<span style="color:var(--amber)">● Not configured</span> — set WHATSAPP tokens in favemus.env';
  } catch (e) {
    $('wa-status').textContent = 'WhatsApp status unavailable';
  }

  try {
    const m = await api('/harness/metrics');
    $('st-dec').textContent = m.decisions;
    $('st-tick').textContent = m.open_tickets;
    $('st-hand').textContent = Math.round(m.handoff_rate * 100) + '%';
    $('st-lat').textContent = m.avg_latency_ms + 'ms';
  } catch (e) {}

  try {
    const s = await api('/harness/sessions');
    $('sessions-t').innerHTML =
      '<tr><th>Session</th><th>User</th><th>Channel</th><th>State</th><th>Updated</th></tr>' +
      (s.sessions || [])
        .map(
          (x) =>
            '<tr><td><code>' +
            x.id +
            '</code></td><td>' +
            (x.user_id || 'anonymous') +
            '</td><td>' +
            (x.channel || '') +
            '</td><td>' +
            (x.state || '') +
            '</td><td>' +
            (x.updated_at || '') +
            '</td></tr>'
        )
        .join('') ||
      '<tr><td colspan="5"><div class="empty"><strong>No conversations yet</strong>Messages from WhatsApp, Telegram, and web will appear here.</div></td></tr>';
  } catch (e) {}

  try {
    const t = await api('/harness/tickets');
    $('tickets-t').innerHTML =
      '<tr><th>#</th><th>Kind</th><th>Status</th><th></th></tr>' +
      (t.tickets || [])
        .map(
          (x) =>
            '<tr><td>#' +
            x.id +
            '</td><td>' +
            (x.kind || '') +
            '</td><td>' +
            stBadge(x.status) +
            '</td><td>' +
            (x.status === 'open'
              ? '<button class="small btn-ghost" onclick="closeT(' + x.id + ')">Close</button>'
              : '') +
            '</td></tr>'
        )
        .join('') ||
      '<tr><td colspan="4"><div class="empty"><strong>No tickets yet</strong>Customer escalations will appear here.</div></td></tr>';
  } catch (e) {}

  try {
    const o = await api('/harness/orders');
    $('orders-t').innerHTML =
      '<tr><th>Order</th><th>Item</th><th>Status</th><th></th></tr>' +
      (o.orders || [])
        .map(
          (x) =>
            '<tr><td><code>' +
            x.order_id +
            '</code></td><td>' +
            (x.item || '') +
            '</td><td>' +
            (x.status || '') +
            '</td><td><button class="small btn-ghost" onclick="delO(\'' +
            x.order_id +
            '\')">Delete</button></td></tr>'
        )
        .join('');
  } catch (e) {}

  try {
    const pr = await api('/harness/products');
    $('products-t').innerHTML =
      '<tr><th>SKU</th><th>Name</th><th>Price</th><th></th></tr>' +
      (pr.products || [])
        .map(
          (x) =>
            '<tr><td><code>' +
            x.sku +
            '</code></td><td>' +
            (x.name || '') +
            '</td><td>' +
            (x.price || '') +
            '</td><td><button class="small btn-ghost" onclick="delP(\'' +
            x.sku +
            '\')">Delete</button></td></tr>'
        )
        .join('');
  } catch (e) {}

  try {
    const u = await api('/harness/users');
    $('users-t').innerHTML =
      '<tr><th>ID</th><th>Email</th><th>Role</th><th>Active</th><th></th></tr>' +
      u.users
        .map(
          (x) =>
            '<tr><td>' +
            x.id +
            '</td><td>' +
            x.email +
            '</td><td><span class="badge' +
            (x.role === 'admin' ? ' accent' : '') +
            '">' +
            x.role +
            '</span></td><td>' +
            (x.is_active ? 'yes' : 'no') +
            '</td><td><button class="small btn-ghost" onclick="toggle(' +
            x.id +
            ')">Toggle</button> <button class="small btn-ghost" onclick="del(' +
            x.id +
            ')">Delete</button></td></tr>'
        )
        .join('');
  } catch (e) {
    $('users-t').textContent = 'Admin only';
  }
}

load().catch((e) => {
  if (String(e) !== 'login') toast(e.message, 'error');
});
