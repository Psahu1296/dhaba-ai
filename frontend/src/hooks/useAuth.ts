import { useState, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001'
const AUTH_KEY = 'dhaba_auth'

interface AuthUser {
  token: string
  role: string
  name: string
}

function loadAuth(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(loadAuth)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail ?? 'Invalid credentials')
        return false
      }
      const data: AuthUser = await res.json()
      localStorage.setItem(AUTH_KEY, JSON.stringify(data))
      setUser(data)
      return true
    } catch {
      setError('Could not reach server')
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_KEY)
    setUser(null)
  }, [])

  return { user, error, isLoading, login, logout }
}
