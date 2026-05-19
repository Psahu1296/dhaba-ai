import type { Message } from '../types'
import { BotMessageSquare, User } from 'lucide-react'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      {!isUser && (
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-zinc-800 to-black border border-orange-500/20 flex items-center justify-center text-orange-500 mr-4 shrink-0 shadow-[0_0_15px_rgba(249,115,22,0.1)] mt-1">
          <BotMessageSquare size={18} strokeWidth={2.5} />
        </div>
      )}

      <div
        className={`max-w-[85%] rounded-2xl px-6 py-5 text-[15px] leading-relaxed ${
          isUser
            ? 'bg-gradient-to-br from-orange-500 to-amber-600 text-white rounded-tr-sm shadow-[0_8px_20px_rgba(249,115,22,0.25)] border border-orange-400/30'
            : 'bg-white/[0.03] backdrop-blur-3xl border border-white/10 text-zinc-100 rounded-tl-sm shadow-[0_8px_30px_rgba(0,0,0,0.5)]'
        }`}
      >
        <FormattedContent content={message.content} isStreaming={message.isStreaming} />
      </div>

      {isUser && (
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-zinc-700 to-zinc-900 border border-white/10 flex items-center justify-center text-zinc-400 ml-4 shrink-0 shadow-inner mt-1">
          <User size={18} strokeWidth={2.5} />
        </div>
      )}
    </div>
  )
}

function FormattedContent({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  if (!content && isStreaming) {
    return (
      <span className="flex gap-2 items-center py-2 px-1">
        <span className="w-2.5 h-2.5 bg-amber-400/80 rounded-full animate-bounce shadow-[0_0_10px_rgba(251,191,36,0.6)] [animation-delay:0ms]" />
        <span className="w-2.5 h-2.5 bg-amber-400/80 rounded-full animate-bounce shadow-[0_0_10px_rgba(251,191,36,0.6)] [animation-delay:150ms]" />
        <span className="w-2.5 h-2.5 bg-amber-400/80 rounded-full animate-bounce shadow-[0_0_10px_rgba(251,191,36,0.6)] [animation-delay:300ms]" />
      </span>
    )
  }

  const lines = content.split('\n')
  const blocks: React.ReactNode[] = []
  
  let currentList: React.ReactNode[] = []
  
  const pushList = () => {
    if (currentList.length > 0) {
      blocks.push(<div key={`list-${blocks.length}`} className="flex flex-col gap-2.5 my-3">{currentList}</div>)
      currentList = []
    }
  }

  lines.forEach((line, i) => {
    // Check if not a list, push any pending list
    if (!line.startsWith('- ') && !line.startsWith('* ') && !/^\d+\.\s/.test(line)) {
      pushList()
    }

    // Bold headers (## or **)
    if (line.startsWith('## ')) {
      blocks.push(<h3 key={i} className="font-semibold text-amber-400 mt-6 mb-3 tracking-wide uppercase text-xs">{line.slice(3)}</h3>)
    }
    else if (line.startsWith('# ')) {
      blocks.push(<h2 key={i} className="font-bold text-amber-300 text-xl mt-6 mb-3 tracking-tight">{line.slice(2)}</h2>)
    }
    // Bullet points
    else if (line.startsWith('- ') || line.startsWith('* ')) {
      currentList.push(
        <div key={i} className="flex gap-3.5 items-start">
          <span className="text-amber-500 shrink-0 mt-[4px] opacity-80 text-lg leading-none">•</span>
          <span className="text-zinc-200">{renderInline(line.slice(2))}</span>
        </div>
      )
    }
    // Numbered list
    else if (/^\d+\.\s/.test(line)) {
      const num = line.match(/^(\d+)\.\s(.*)/)
      currentList.push(
        <div key={i} className="flex gap-3 items-start">
          <span className="text-amber-500 shrink-0 w-[18px] font-mono text-xs mt-[5px] opacity-80">{num?.[1]}.</span>
          <span className="text-zinc-200">{renderInline(num?.[2] || '')}</span>
        </div>
      )
    }
    // Table rows
    else if (line.startsWith('|')) {
      blocks.push(<p key={i} className="font-mono text-[13px] text-zinc-400 my-2 bg-black/40 p-2.5 rounded-lg border border-white/5 overflow-x-auto whitespace-pre leading-normal">{line}</p>)
    }
    // Horizontal rule
    else if (line.startsWith('---')) {
      blocks.push(<hr key={i} className="border-white/10 my-6 shadow-[0_1px_0_rgba(255,255,255,0.05)]" />)
    }
    // Empty line
    else if (!line.trim()) {
      // Just let spacing handle it
    }
    else {
      blocks.push(<p key={i} className="my-2 text-zinc-200 text-[15px]">{renderInline(line)}</p>)
    }
  })
  
  pushList()

  return (
    <div className="flex flex-col">
      {blocks}
      {isStreaming && <span className="inline-block w-2 h-5 bg-amber-400 rounded-[1px] animate-pulse ml-1 mt-2 align-middle shadow-[0_0_10px_rgba(251,191,36,0.6)]" />}
    </div>
  )
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-white font-semibold bg-white/[0.04] px-1.5 py-0.5 rounded-[4px] border border-white/10">{part.slice(2, -2)}</strong>
    }
    return part
  })
}
