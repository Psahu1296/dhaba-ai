import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { SendHorizontal } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  isLoading: boolean
}

const SUGGESTIONS = [
  'Give me today\'s business report',
  'What veg dishes are under ₹50?',
  'What are the top 3 dishes?',
  'How much did we earn this month?',
]

export function InputBar({ onSend, isLoading }: Props) {
  const [value, setValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(true)

  function handleSend() {
    if (!value.trim() || isLoading) return
    setShowSuggestions(false)
    onSend(value.trim())
    setValue('')
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSuggestion(s: string) {
    setShowSuggestions(false)
    onSend(s)
  }

  return (
    <div className="w-full flex flex-col gap-4">
      {showSuggestions && (
        <div className="flex flex-wrap gap-2.5 w-full">
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => handleSuggestion(s)}
              className="text-[13px] font-medium px-4 py-2.5 rounded-[1.25rem] border border-white/10 bg-white/[0.03] text-zinc-300 hover:border-orange-500/50 hover:text-white hover:bg-orange-500/10 hover:shadow-[0_0_15px_rgba(249,115,22,0.2)] transition-all duration-300"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="w-full flex gap-3 items-end bg-black/60 backdrop-blur-3xl border border-white/10 rounded-[1.5rem] p-2.5 shadow-[0_15px_50px_rgba(0,0,0,0.9)] relative group focus-within:border-orange-500/30 transition-all duration-500">
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about your dhaba..."
          rows={1}
          className="flex-1 bg-transparent text-white placeholder-zinc-500 px-4 py-3.5 text-[15px] resize-none outline-none min-h-[56px] max-h-[160px] leading-relaxed"
          style={{ height: 'auto' }}
          onInput={e => {
            const el = e.currentTarget
            el.style.height = 'auto'
            el.style.height = Math.min(el.scrollHeight, 160) + 'px'
          }}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !value.trim()}
          className="w-14 h-14 rounded-[1.1rem] bg-gradient-to-br from-orange-500 to-amber-600 disabled:from-zinc-800 disabled:to-zinc-900 disabled:text-zinc-600 text-white disabled:cursor-not-allowed disabled:shadow-none hover:shadow-[0_8px_20px_rgba(249,115,22,0.4)] transition-all duration-300 flex items-center justify-center shrink-0 disabled:opacity-50"
        >
          {isLoading ? (
            <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          ) : (
            <SendHorizontal size={22} strokeWidth={2.5} className="ml-1" />
          )}
        </button>
      </div>
    </div>
  )
}
