import { useEffect, useRef } from 'react'
import { useChat } from './hooks/useChat'
import { MessageBubble } from './components/MessageBubble'
import { InputBar } from './components/InputBar'
import { BotMessageSquare, BarChart3, UtensilsCrossed, Banknote, PackageOpen, Sparkles, BrainCircuit, Zap } from 'lucide-react'
import type { Mode } from './types'

export default function App() {
  const { messages, mode, setMode, isLoading, sessionId, sendMessage, clearChat, stopGeneration } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-screen bg-[#050505] relative">
      {/* Ambient Orbs — isolated so they don't affect flex children */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-15%] left-[-10%] w-[50%] h-[50%] bg-orange-600/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-amber-500/10 rounded-full blur-[120px]" />
      </div>

      {/* Header */}
      <header className="px-4 sm:px-6 md:px-8 py-4 border-b border-white/5 bg-black/40 backdrop-blur-2xl shrink-0 shadow-sm flex justify-center w-full relative z-10">
        <div className="w-full max-w-4xl flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-orange-500/10 to-amber-500/5 border border-orange-500/20 flex items-center justify-center text-orange-500 shadow-[0_0_20px_rgba(249,115,22,0.15)] group">
              <BotMessageSquare size={22} className="group-hover:scale-110 transition-transform duration-300" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="font-bold text-2xl text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-500 tracking-tight leading-tight">
                Dhaba AI
              </h1>
              <p className="text-[10px] text-zinc-500 font-black tracking-[0.2em] uppercase mt-0.5">
                Business Intelligence
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 p-1 bg-black/40 rounded-[14px] border border-white/5 shadow-inner backdrop-blur-sm">
              {(['stream', 'agent'] as Mode[]).map(m => {
                const isActive = mode === m
                const Icon = m === 'stream' ? Zap : BrainCircuit
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[11px] font-bold uppercase tracking-wider transition-all duration-300 ${isActive
                      ? 'bg-orange-500/10 text-orange-400 shadow-[0_0_15px_rgba(249,115,22,0.15)] border border-orange-500/20'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5 border border-transparent'
                      }`}
                  >
                    <Icon size={14} strokeWidth={isActive ? 3 : 2} />
                    {m}
                  </button>
                )
              })}
            </div>

            <button
              onClick={clearChat}
              className="text-[11px] font-black uppercase tracking-wider text-zinc-500 hover:text-red-400 transition-colors px-4 py-2 rounded-xl hover:bg-red-500/10 border border-transparent hover:border-red-500/20"
            >
              Clear
            </button>
          </div>
        </div>
      </header>

      {/* Mode indicator */}
      <div className="px-4 sm:px-6 md:px-8 py-2.5 bg-black/30 backdrop-blur-md border-b border-white/5 shrink-0 relative z-10 shadow-sm flex justify-center w-full">
        <div className="w-full max-w-4xl flex items-center gap-3 text-[10px] font-black tracking-widest uppercase">
          {mode === 'agent' ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse" />
              <span className="text-zinc-400">LANGGRAPH AGENT <span className="text-zinc-600 mx-2">/</span> MULTI-STEP REASONING <span className="text-zinc-600 mx-2">/</span> MEMORY ENABLED</span>
              {sessionId && (
                <span className="ml-auto font-mono text-zinc-500 bg-white/5 px-2.5 py-1 rounded-md border border-white/5">
                  SESSION: {sessionId.slice(0, 8)}
                </span>
              )}
            </>
          ) : (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)] animate-pulse" />
              <span className="text-zinc-400">STREAMING MODE <span className="text-zinc-600 mx-2">/</span> LIVE TOKENS <span className="text-zinc-600 mx-2">/</span> NO MEMORY</span>
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 md:px-8 py-10 scrollbar-thin z-0 relative flex flex-col items-center w-full">
        {messages.length === 0 ? (
          <EmptyState onSend={sendMessage} />
        ) : (
          <div className="w-full max-w-4xl flex flex-col gap-5 pb-8">
            {messages.map(m => <MessageBubble key={m.id} message={m} />)}
          </div>
        )}
        <div ref={bottomRef} className="w-full max-w-4xl" />
      </div>

      {/* Input */}
      <div className="shrink-0 relative z-10 flex justify-center w-full px-4 sm:px-6 md:px-8 pb-8">
        <div className="w-full max-w-4xl">
          <InputBar
            onSend={sendMessage}
            onStop={stopGeneration}
            isLoading={isLoading}
            hasMessages={messages.length > 0}
          />
        </div>
      </div>
    </div>
  )
}

function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-10 w-full max-w-4xl animate-fade-in mx-auto mt-10">
      <div className="relative group cursor-default">
        <div className="absolute inset-0 bg-orange-500/20 blur-2xl rounded-full group-hover:bg-orange-500/30 transition-all duration-700" />
        <div className="w-28 h-28 bg-gradient-to-br from-zinc-900 to-black rounded-[2rem] border border-white/10 flex items-center justify-center text-orange-400 shadow-2xl relative z-10 group-hover:scale-105 transition-transform duration-500">
          <Sparkles size={48} strokeWidth={1.5} />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="font-bold text-3xl tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-white to-zinc-400">
          How can I help you today?
        </h2>
        <p className="text-zinc-500 text-[15px] max-w-lg mx-auto font-medium leading-relaxed">
          Ask about your menu performance, daily revenue, or request a comprehensive breakdown of your dhaba's operations.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mt-6 w-full max-w-3xl">
        {[
          { icon: <BarChart3 size={24} strokeWidth={2} />, title: 'Business Report', desc: 'Full performance & analytics overview', query: "Give me today's full business report" },
          { icon: <UtensilsCrossed size={24} strokeWidth={2} />, title: 'Menu Insights', desc: 'Find top-performing dishes & prices', query: 'What are the top 5 selling dishes overall?' },
          { icon: <Banknote size={24} strokeWidth={2} />, title: 'Revenue & KPIs', desc: 'Track daily earnings & profit margins', query: "What are today's revenue and KPIs?" },
          { icon: <PackageOpen size={24} strokeWidth={2} />, title: 'Orders & Expenses', desc: 'Monitor latest costs and stock levels', query: "Show me today's orders and expenses summary" },
        ].map(({ icon, title, desc, query }) => (
          <button
            key={title}
            onClick={() => onSend(query)}
            className="group relative overflow-hidden rounded-2xl p-6 flex items-start gap-5 border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-300 cursor-pointer text-left hover:border-orange-500/30 hover:shadow-[0_8px_30px_rgba(249,115,22,0.1)]"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

            <div className="h-14 w-14 rounded-[1.1rem] bg-black/40 border border-white/5 flex items-center justify-center shrink-0 text-orange-400 group-hover:text-orange-300 group-hover:scale-110 transition-all duration-300 shadow-inner">
              {icon}
            </div>

            <div className="flex-1 mt-1">
              <h3 className="text-[15px] font-bold text-zinc-200 tracking-wide group-hover:text-orange-50 transition-colors">
                {title}
              </h3>
              <p className="text-[13px] text-zinc-500 font-medium mt-1.5 leading-relaxed group-hover:text-zinc-400 transition-colors">
                {desc}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
