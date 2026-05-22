import type { ReactNode } from 'react'
import type { Message } from '../types'
import { BotMessageSquare, User } from 'lucide-react'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex w-full mb-4 sm:mb-6 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      {!isUser && (
        <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-zinc-800 to-black border border-orange-500/20 flex items-center justify-center text-orange-500 mr-2 sm:mr-4 shrink-0 shadow-[0_0_15px_rgba(249,115,22,0.1)] mt-1">
          <BotMessageSquare size={18} strokeWidth={2.5} className="w-4 h-4 sm:w-[18px] sm:h-[18px]" />
        </div>
      )}

      <div
        className={`max-w-[92%] sm:max-w-[85%] rounded-2xl px-4 sm:px-6 py-4 sm:py-5 text-[14px] sm:text-[15px] leading-relaxed ${
          isUser
            ? 'bg-gradient-to-br from-orange-500 to-amber-600 text-white rounded-tr-sm shadow-[0_8px_20px_rgba(249,115,22,0.25)] border border-orange-400/30'
            : 'bg-white/[0.03] backdrop-blur-3xl border border-white/10 text-zinc-100 rounded-tl-sm shadow-[0_8px_30px_rgba(0,0,0,0.5)]'
        }`}
      >
        <FormattedContent content={message.content} isStreaming={message.isStreaming} />
      </div>

      {isUser && (
        <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-zinc-700 to-zinc-900 border border-white/10 flex items-center justify-center text-zinc-400 ml-2 sm:ml-4 shrink-0 shadow-inner mt-1">
          <User size={18} strokeWidth={2.5} className="w-4 h-4 sm:w-[18px] sm:h-[18px]" />
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

  // Split on fenced code blocks first so line parser doesn't see their contents
  const segments: Array<{ type: 'text' | 'code'; content: string; lang?: string }> = []
  const codeBlockRe = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = codeBlockRe.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    }
    segments.push({ type: 'code', lang: match[1], content: match[2] })
    lastIndex = codeBlockRe.lastIndex
  }
  if (lastIndex < content.length) {
    segments.push({ type: 'text', content: content.slice(lastIndex) })
  }

  return (
    <div className="flex flex-col">
      {segments.map((seg, i) =>
        seg.type === 'code'
          ? <CodeBlock key={i} lang={seg.lang ?? ''} code={seg.content} />
          : <TextSegment key={i} text={seg.content} />
      )}
      {isStreaming && (
        <span className="inline-block w-2 h-5 bg-amber-400 rounded-[1px] animate-pulse ml-1 mt-2 align-middle shadow-[0_0_10px_rgba(251,191,36,0.6)]" />
      )}
    </div>
  )
}

function isSeparatorRow(line: string): boolean {
  const cells = line.split('|').slice(1, -1)
  return cells.length > 0 && cells.every(c => /^:?-+:?$/.test(c.trim()))
}

function TextSegment({ text }: { text: string }) {
  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Table: collect all consecutive | lines
    if (line.startsWith('|')) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i].startsWith('|')) {
        tableLines.push(lines[i])
        i++
      }
      blocks.push(<MarkdownTable key={blocks.length} lines={tableLines} />)
      continue
    }

    // List: collect consecutive bullet/numbered items
    if (line.startsWith('- ') || line.startsWith('* ') || /^\d+\.\s/.test(line)) {
      const items: string[] = []
      while (
        i < lines.length &&
        (lines[i].startsWith('- ') || lines[i].startsWith('* ') || /^\d+\.\s/.test(lines[i]))
      ) {
        items.push(lines[i])
        i++
      }
      blocks.push(
        <div key={blocks.length} className="flex flex-col gap-2.5 my-3">
          {items.map((item, j) => {
            const num = item.match(/^(\d+)\.\s(.*)/)
            if (num) {
              return (
                <div key={j} className="flex gap-3 items-start">
                  <span className="text-amber-500 shrink-0 w-[18px] font-mono text-xs mt-[5px] opacity-80">{num[1]}.</span>
                  <span className="text-zinc-200">{renderInline(num[2])}</span>
                </div>
              )
            }
            return (
              <div key={j} className="flex gap-3.5 items-start">
                <span className="text-amber-500 shrink-0 mt-[4px] opacity-80 text-lg leading-none">•</span>
                <span className="text-zinc-200">{renderInline(item.slice(2))}</span>
              </div>
            )
          })}
        </div>
      )
      continue
    }

    if (line.startsWith('### ')) {
      blocks.push(<h4 key={blocks.length} className="font-semibold text-zinc-300 mt-4 mb-1.5 text-[13px] uppercase tracking-wider">{line.slice(4)}</h4>)
    } else if (line.startsWith('## ')) {
      blocks.push(<h3 key={blocks.length} className="font-semibold text-amber-400 mt-6 mb-3 tracking-wide uppercase text-xs">{line.slice(3)}</h3>)
    } else if (line.startsWith('# ')) {
      blocks.push(<h2 key={blocks.length} className="font-bold text-amber-300 text-xl mt-6 mb-3 tracking-tight">{line.slice(2)}</h2>)
    } else if (line.startsWith('---')) {
      blocks.push(<hr key={blocks.length} className="border-white/10 my-6 shadow-[0_1px_0_rgba(255,255,255,0.05)]" />)
    } else if (!line.trim()) {
      // empty lines — spacing handled by margins
    } else {
      blocks.push(<p key={blocks.length} className="my-2 text-zinc-200 text-[15px]">{renderInline(line)}</p>)
    }

    i++
  }

  return <>{blocks}</>
}

function MarkdownTable({ lines }: { lines: string[] }) {
  const dataRows = lines.filter(l => !isSeparatorRow(l))
  const rows = dataRows.map(l =>
    l.split('|').slice(1, -1).map(cell => cell.trim())
  )
  if (rows.length === 0) return null

  const [header, ...body] = rows

  return (
    <div className="overflow-x-auto my-4 rounded-xl border border-white/10">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 bg-white/[0.03]">
            {header.map((cell, i) => (
              <th key={i} className="px-4 py-3 text-left text-amber-400 font-semibold text-xs uppercase tracking-wide whitespace-nowrap">
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
              {row.map((cell, ci) => (
                <td key={ci} className="px-4 py-3 text-zinc-300 text-[14px]">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  return (
    <div className="my-4 rounded-xl overflow-hidden border border-white/10">
      {lang && (
        <div className="px-4 py-2 bg-white/[0.04] border-b border-white/5 text-[11px] font-mono text-zinc-500 uppercase tracking-widest">
          {lang}
        </div>
      )}
      <pre className="bg-black/60 p-4 overflow-x-auto text-[13px] leading-relaxed">
        <code className="text-zinc-300 font-mono">{code.trim()}</code>
      </pre>
    </div>
  )
}

function renderInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="text-white font-semibold bg-white/[0.04] px-1.5 py-0.5 rounded-[4px] border border-white/10">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={i} className="font-mono text-[13px] text-amber-300 bg-white/[0.06] px-1.5 py-0.5 rounded-[4px] border border-white/5">
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}
