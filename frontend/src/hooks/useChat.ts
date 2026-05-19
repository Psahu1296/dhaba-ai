import { useState, useRef, useCallback } from 'react'
import type { Message, Mode } from '../types'

const API_BASE = 'http://localhost:8001'
const API_KEY = 'dhaba-secret-key-2024'

function uid() {
  return Math.random().toString(36).slice(2)
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [mode, setMode] = useState<Mode>('agent')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
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
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
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

    setMessages(prev => prev.map(m =>
      m.id === assistantId ? { ...m, isStreaming: false } : m
    ))
  }

  async function sendAgent(text: string) {
    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true }])

    const currentSessionId = sessionId || crypto.randomUUID()
    if (!sessionId) setSessionId(currentSessionId)

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
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

    setMessages(prev => prev.map(m =>
      m.id === assistantId ? { ...m, isStreaming: false } : m
    ))
  }

  function clearChat() {
    setMessages([])
    setSessionId(null)
    abortRef.current?.abort()
  }

  return { messages, mode, setMode, isLoading, sessionId, sendMessage, clearChat }
}
