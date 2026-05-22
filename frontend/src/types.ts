export type Role = 'user' | 'assistant' | 'tool-call'

export interface Message {
  id: string
  role: Role
  content: string
  isStreaming?: boolean
  lastTokenAt?: number
}

export type Mode = 'stream' | 'agent'
