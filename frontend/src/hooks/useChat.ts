import { useState, useRef, useCallback } from 'react'
import type { Message, Mode } from '../types'

const TOON_SAVED_RE = /\[TOON_SAVED:(\d+)\]$/

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001'

function getAuthHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem('dhaba_auth')
    if (raw) {
      const { token } = JSON.parse(raw)
      return { Authorization: `Bearer ${token}` }
    }
  } catch {}
  const fallback = import.meta.env.VITE_API_KEY ?? ''
  return fallback ? { 'X-API-Key': fallback } : {}
}

function uid() {
  return Math.random().toString(36).slice(2)
}

const SESSION_KEY = 'dhaba_session_id'

function getOrCreateSessionId(): string {
  const saved = localStorage.getItem(SESSION_KEY)
  if (saved) return saved
  const fresh = crypto.randomUUID()
  localStorage.setItem(SESSION_KEY, fresh)
  return fresh
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [mode, setMode] = useState<Mode>('agent')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(getOrCreateSessionId)
  const [totalCharsSaved, setTotalCharsSaved] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: Message = { id: uid(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    if (mode === 'stream') {
      await sendStreaming(text)
    } else {
      await sendAgent(text)
    }

    setIsLoading(false)
  }, [mode, isLoading, sessionId])

  async function sendStreaming(text: string) {
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true }])

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ message: text }),
        signal: abortRef.current.signal,
      })

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const token = decoder.decode(value)
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + token } : m
        ))
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: 'Error: could not reach server.' } : m
        ))
      }
    }

    setMessages(prev => prev.map(m => {
      if (m.id !== assistantId) return m
      const match = m.content.match(TOON_SAVED_RE)
      if (match) {
        setTotalCharsSaved(s => s + parseInt(match[1]))
        return { ...m, content: m.content.replace(TOON_SAVED_RE, '').trimEnd(), isStreaming: false }
      }
      return { ...m, isStreaming: false }
    }))
  }

  async function sendAgent(text: string) {
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true }])

    const currentSessionId = sessionId

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ message: text, session_id: currentSessionId }),
        signal: abortRef.current.signal,
      })

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const token = decoder.decode(value)
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + token } : m
        ))
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: 'Error: could not reach server.', isStreaming: false } : m
        ))
      }
    }

    setMessages(prev => prev.map(m => {
      if (m.id !== assistantId) return m
      const match = m.content.match(TOON_SAVED_RE)
      if (match) {
        setTotalCharsSaved(s => s + parseInt(match[1]))
        return { ...m, content: m.content.replace(TOON_SAVED_RE, '').trimEnd(), isStreaming: false }
      }
      return { ...m, isStreaming: false }
    }))
  }

  function stopGeneration() {
    abortRef.current?.abort()
  }

  async function loadDailyReport() {
    setIsLoading(true)
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true }])
    try {
      const res = await fetch(`${API_BASE}/report/latest`, {
        headers: { ...getAuthHeaders() },
      })
      const data = await res.json()
      const content = data.report_date
        ? `**Daily Business Report — ${data.report_date}**\n\n${data.content}`
        : 'No daily report generated yet. Come back after 11 PM IST.'
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content, isStreaming: false } : m))
    } catch {
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: 'Could not load report.', isStreaming: false } : m))
    }
    setIsLoading(false)
  }

  function clearChat() {
    const fresh = crypto.randomUUID()
    localStorage.setItem(SESSION_KEY, fresh)
    setMessages([])
    setSessionId(fresh)
    setTotalCharsSaved(0)
    abortRef.current?.abort()
  }

  return { messages, mode, setMode, isLoading, sessionId, totalCharsSaved, sendMessage, clearChat, stopGeneration, loadDailyReport }
}
