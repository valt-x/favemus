import { Link } from 'react-router-dom'
import { MessageSquare, Shield, Zap, Globe, ArrowRight, Check } from 'lucide-react'

export function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      {/* Nav */}
      <nav className="border-b border-gray-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-xs">F</div>
            <span className="font-bold text-lg tracking-tight">Favemus</span>
          </div>
          <div className="flex gap-3 items-center">
            <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900">Login</Link>
            <Link to="/client" className="text-sm font-medium bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition">
              Try it free →
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 py-16 md:py-24 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-sm font-medium mb-6">
          <Zap size={14} /> AI-powered customer support
        </div>
        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-4">
          Support that answers<br />
          <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">instantly.</span>
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-8">
          Favemus is a self-hosted AI customer service platform. No per-message fees.
          No external AI APIs. Your data, your server, your rules.
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link to="/client" className="inline-flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-indigo-700 transition shadow-lg shadow-indigo-200">
            Start chatting <ArrowRight size={18} />
          </Link>
          <Link to="/owner" className="inline-flex items-center gap-2 bg-white text-gray-700 px-6 py-3 rounded-xl font-semibold border border-gray-200 hover:bg-gray-50 transition">
            Admin console
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-12">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: <MessageSquare />, title: 'Multi-channel', desc: 'Web chat, WhatsApp, and Telegram — one AI brain for all channels.' },
            { icon: <Shield />, title: 'Self-hosted', desc: 'Your data never leaves your server. SQLite, no external DB.' },
            { icon: <Zap />, title: 'Fast', desc: 'Local Laya model — ~1.4s average response time.' },
            { icon: <Globe />, title: 'Multi-tenant', desc: 'Run multiple businesses on one instance with data isolation.' },
            { icon: <Check />, title: 'Zero per-message fees', desc: 'No per-conversation charges. No API fees for AI inference.' },
            { icon: <Check />, title: 'Open source', desc: 'MIT licensed. Fork, modify, deploy freely.' },
          ].map((f, i) => (
            <div key={i} className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm hover:shadow-md transition">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
                {f.icon}
              </div>
              <h3 className="font-bold text-lg mb-1">{f.title}</h3>
              <p className="text-gray-600 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-16 py-8 text-center text-sm text-gray-500">
        <p>Favemus — AI Customer Support · MIT License · Built with FastAPI + React</p>
      </footer>
    </div>
  )
}
