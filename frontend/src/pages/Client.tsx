import { useState, useRef, useEffect } from 'react'
import { Send, Package, RefreshCw, Search, User } from 'lucide-react'

interface Message {
  role: 'user' | 'bot'
  text: string
}

export function Client() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Hi! I\'m your AI support assistant. Ask me about orders, returns, products, or refunds — or send "human" anytime.' },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sid, setSid] = useState(() => {
    const stored = localStorage.getItem('favemus_sid')
    if (stored) return stored
    const id = 'web-' + Math.random().toString(36).slice(2, 12)
    localStorage.setItem('favemus_sid', id)
    return id
  })
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const t = input.trim()
    if (!t || sending) return
    setInput('')
    setSending(true)
    setMessages(prev => [...prev, { role: 'user', text: t }])
    setMessages(prev => [...prev, { role: 'bot', text: 'typing' }])

    try {
      const r = await fetch('/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: t, session_id: sid, channel: 'web' }),
      })
      const d = await r.json()
      setSid(d.session_id)
      localStorage.setItem('favemus_sid', d.session_id)
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = { role: 'bot', text: d.reply || 'Sorry, I could not answer that.' }
        return next
      })
    } catch (err) {
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = { role: 'bot', text: 'Network error. Please try again.' }
        return next
      })
    } finally {
      setSending(false)
    }
  }

  const quick = (t: string) => {
    setInput(t)
  }

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm relative">
            AI
            <span className="absolute -bottom-1 -right-1 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full"></span>
          </div>
          <div>
            <div className="font-bold text-gray-900">Favemus Assistant</div>
            <div className="text-xs text-gray-500 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full inline-block"></span>
              Online · 143ms avg · same AI on WhatsApp
            </div>
          </div>
        </div>

        {/* Messages */}
        <div ref={logRef} className="h-[400px] overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[78%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-md'
                    : 'bg-gray-100 text-gray-900 rounded-bl-md'
                }`}
              >
                {m.text === 'typing' ? (
                  <span className="flex gap-1.5 items-center">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Quick actions */}
        <div className="px-4 pb-3 flex gap-2 flex-wrap">
          {[
            { label: 'Find my order', icon: <Package size={14} />, msg: 'Where is my order FAV-1042?' },
            { label: 'Start a return', icon: <RefreshCw size={14} />, msg: 'I want to return FAV-2231, the dress is torn.' },
            { label: 'Browse products', icon: <Search size={14} />, msg: 'Show green wrap dresses' },
            { label: 'Talk to human', icon: <User size={14} />, msg: 'human' },
          ].map((q, i) => (
            <button
              key={i}
              type="button"
              onClick={() => quick(q.msg)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-gray-200 bg-white text-xs font-medium text-gray-600 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50 transition"
            >
              {q.icon} {q.label}
            </button>
          ))}
        </div>

        {/* Input */}
        <form onSubmit={send} className="p-3 border-t border-gray-200 flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about orders, returns, products..."
            className="flex-1 px-4 py-2.5 rounded-full border border-gray-200 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 text-sm"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="px-5 py-2.5 rounded-full bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <Send size={16} />
          </button>
        </form>
      </div>

      {/* My data */}
      <div className="mt-6 bg-white rounded-2xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Your activity</h2>
        <p className="text-sm text-gray-500">Log in to see your conversations and tickets.</p>
      </div>
    </div>
  )
}
