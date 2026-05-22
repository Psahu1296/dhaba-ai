export type Role = 'user' | 'assistant' | 'tool-call'

export interface Message {
  id: string
  role: Role
  content: string
  isStreaming?: boolean
  lastTokenAt?: number
  feedback?: 1 | -1
  query?: string   // the user message that triggered this assistant response
}

export type Mode = 'stream' | 'agent'
