import { useState, useRef, useCallback } from 'react'
import type { Message, Mode } from '../types'

const TOON_SAVED_RE = /\[TOON_SAVED:(\d+)\]$/

const IMPLICIT_NEGATIVE = [
  'wrong', 'incorrect', 'galat', 'sahi nahi', 'check again', 'dobara check',
  'values are wrong', 'numbers are wrong', "that's not right", 'yeh galat hai',
  'woh sahi nahi', 'dobara dekho', 'phir se check', 'mistake', 'not right',
  'wrong values', 'wrong data', 'wrong answer', 'incorrect data',
]

function isImplicitNegative(text: string): boolean {
  const lower = text.toLowerCase()
  return IMPLICIT_NEGATIVE.some(p => lower.includes(p))
}

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

  const sendFeedback = useCallback(async (messageId: string, rating: 1 | -1, correction?: string) => {
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: rating } : m))
    const msg = messages.find(m => m.id === messageId)
    if (!msg) return
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          session_id: sessionId,
          query: msg.query ?? '',
          response: msg.content,
          rating,
          source: 'explicit',
          correction: correction ?? null,
        }),
      })
    } catch {}
  }, [messages, sessionId])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    if (isImplicitNegative(text)) {
      const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant' && m.feedback === undefined)
      if (lastAssistant) {
        setMessages(prev => prev.map(m => m.id === lastAssistant.id ? { ...m, feedback: -1 } : m))
        fetch(`${API_BASE}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            session_id: sessionId,
            query: lastAssistant.query ?? '',
            response: lastAssistant.content,
            rating: -1,
            source: 'implicit',
            correction: null,
          }),
        }).catch(() => {})
      }
    }

    const userMsg: Message = { id: uid(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'stream') {
        await sendStreaming(text)
      } else {
        await sendAgent(text)
      }
    } finally {
      setIsLoading(false)
    }
  }, [mode, isLoading, sessionId, messages])

  async function sendStreaming(text: string) {
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true, query: text }])

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ message: text }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        let detail = `Server error ${res.status}`
        try { detail = JSON.parse(errText).detail ?? detail } catch {}
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: `Error: ${detail}`, isStreaming: false } : m
        ))
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const token = decoder.decode(value)
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + token, lastTokenAt: Date.now() } : m
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

  async function sendAgent(text: string) {
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true, query: text }])

    const currentSessionId = sessionId

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ message: text, session_id: currentSessionId }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        let detail = `Server error ${res.status}`
        try { detail = JSON.parse(errText).detail ?? detail } catch {}
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: `Error: ${detail}`, isStreaming: false } : m
        ))
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let received = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const token = decoder.decode(value)
        if (token) received = true
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + token, lastTokenAt: Date.now() } : m
        ))
      }

      if (!received) {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: 'No response — server may be busy, try again.', isStreaming: false } : m
        ))
        return
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

  return { messages, mode, setMode, isLoading, sessionId, totalCharsSaved, sendMessage, sendFeedback, clearChat, stopGeneration, loadDailyReport }
}
