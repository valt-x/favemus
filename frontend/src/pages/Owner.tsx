import { useState, useEffect } from 'react'
import { Users, MessageSquare, Ticket, Zap } from 'lucide-react'

interface Stats {
  decisions: number
  open_tickets: number
  handoff_rate: number
  avg_latency_ms: number
}

export function Owner() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [users, setUsers] = useState<any[]>([])
  const [orders, setOrders] = useState<any[]>([])
  const [products, setProducts] = useState<any[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [tickets, setTickets] = useState<any[]>([])
  const [waStatus, setWaStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      const [m, u, o, p, s, t, w] = await Promise.all([
        fetch('/harness/metrics').then(r => r.json()),
        fetch('/harness/users').then(r => r.json()),
        fetch('/harness/orders').then(r => r.json()),
        fetch('/harness/products').then(r => r.json()),
        fetch('/harness/sessions').then(r => r.json()),
        fetch('/harness/tickets').then(r => r.json()),
        fetch('/whatsapp/status').then(r => r.json()),
      ])
      setStats(m)
      setUsers(u.users || [])
      setOrders(o.orders || [])
      setProducts(p.products || [])
      setSessions(s.sessions || [])
      setTickets(t.tickets || [])
      setWaStatus(w)
    } catch (e) {
      console.error('Failed to load', e)
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    { label: 'AI decisions', value: stats?.decisions ?? '—', icon: <MessageSquare size={20} />, color: 'indigo' },
    { label: 'Open tickets', value: stats?.open_tickets ?? '—', icon: <Ticket size={20} />, color: 'amber' },
    { label: 'Handoff rate', value: stats ? Math.round(stats.handoff_rate * 100) + '%' : '—', icon: <Users size={20} />, color: 'rose' },
    { label: 'Avg latency', value: stats ? stats.avg_latency_ms + 'ms' : '—', icon: <Zap size={20} />, color: 'emerald' },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Owner Console</h1>
          <p className="text-sm text-gray-500 mt-1">Manage users, orders, products, and monitor AI performance</p>
        </div>
        <button onClick={() => window.location.href = '/client'} className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50">
          Client layer →
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{s.label}</span>
              <span className={`w-9 h-9 rounded-lg bg-${s.color}-50 text-${s.color}-600 flex items-center justify-center`}>
                {s.icon}
              </span>
            </div>
            <div className="text-3xl font-extrabold tracking-tight">{s.value}</div>
          </div>
        ))}
      </div>

      {/* WhatsApp */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">WhatsApp</h2>
        <div className="text-sm text-gray-600 mb-3">
          Status: {waStatus?.configured ? (
            <span className="text-emerald-600 font-medium">● Configured ({waStatus.api_version})</span>
          ) : (
            <span className="text-amber-600 font-medium">● Not configured</span>
          )}
        </div>
        <div className="flex gap-2">
          <input placeholder="Phone e.g. 919876543210" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          <input placeholder="Test message" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Send test</button>
        </div>
      </div>

      {/* Users */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Manual users</h2>
        <div className="flex gap-2 mb-4 flex-wrap">
          <input placeholder="email" className="flex-1 min-w-[200px] px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          <input placeholder="password (8+)" type="password" className="w-40 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          <input placeholder="name" className="w-32 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          <select className="w-28 px-3 py-2 border border-gray-200 rounded-lg text-sm">
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
          <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Create</button>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-gray-500 text-xs uppercase"><th className="pb-2">ID</th><th className="pb-2">Email</th><th className="pb-2">Role</th><th className="pb-2">Active</th><th className="pb-2">Actions</th></tr></thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-gray-100">
                <td className="py-2 text-gray-500">{u.id}</td>
                <td className="py-2 font-medium">{u.email}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.role === 'admin' ? 'bg-indigo-50 text-indigo-700' : 'bg-gray-100 text-gray-600'}`}>{u.role}</span>
                </td>
                <td className="py-2">{u.is_active ? 'yes' : 'no'}</td>
                <td className="py-2 space-x-2">
                  <button className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200">Toggle</button>
                  <button className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs font-medium hover:bg-red-100">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Orders */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Manual orders</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-gray-500 text-xs uppercase"><th className="pb-2">Order</th><th className="pb-2">Item</th><th className="pb-2">Status</th><th className="pb-2">Actions</th></tr></thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.order_id} className="border-t border-gray-100">
                <td className="py-2 font-mono text-xs">{o.order_id}</td>
                <td className="py-2">{o.item}</td>
                <td className="py-2">
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700">{o.status}</span>
                </td>
                <td className="py-2">
                  <button className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs font-medium hover:bg-red-100">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Products */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Products</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-gray-500 text-xs uppercase"><th className="pb-2">SKU</th><th className="pb-2">Name</th><th className="pb-2">Price</th><th className="pb-2">Actions</th></tr></thead>
          <tbody>
            {products.map(p => (
              <tr key={p.sku} className="border-t border-gray-100">
                <td className="py-2 font-mono text-xs">{p.sku}</td>
                <td className="py-2">{p.name}</td>
                <td className="py-2">{p.price}</td>
                <td className="py-2">
                  <button className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs font-medium hover:bg-red-100">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Conversations */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Conversations</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-gray-500 text-xs uppercase"><th className="pb-2">Session</th><th className="pb-2">User</th><th className="pb-2">Channel</th><th className="pb-2">State</th><th className="pb-2">Updated</th></tr></thead>
          <tbody>
            {sessions.map(s => (
              <tr key={s.id} className="border-t border-gray-100">
                <td className="py-2 font-mono text-xs">{s.id}</td>
                <td className="py-2">{s.user_id || 'anonymous'}</td>
                <td className="py-2">{s.channel || ''}</td>
                <td className="py-2">{s.state || ''}</td>
                <td className="py-2 text-gray-500">{s.updated_at || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tickets */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Tickets</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-gray-500 text-xs uppercase"><th className="pb-2">#</th><th className="pb-2">Kind</th><th className="pb-2">Status</th><th className="pb-2"></th></tr></thead>
          <tbody>
            {tickets.map(t => (
              <tr key={t.id} className="border-t border-gray-100">
                <td className="py-2">#{t.id}</td>
                <td className="py-2">{t.kind || ''}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${t.status === 'open' ? 'bg-amber-50 text-amber-700' : 'bg-green-50 text-green-700'}`}>{t.status}</span>
                </td>
                <td className="py-2">
                  {t.status === 'open' && <button className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200">Close</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
