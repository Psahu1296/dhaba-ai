import { useState } from 'react'
import { BotMessageSquare } from 'lucide-react'

interface Props {
  onLogin: (email: string, password: string) => Promise<boolean>
  error: string | null
  isLoading: boolean
}

export function LoginPage({ onLogin, error, isLoading }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  async function handleSubmit(e: any) {
    e.preventDefault()
    await onLogin(email, password)
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#050505] relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-15%] left-[-10%] w-[50%] h-[50%] bg-orange-600/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-amber-500/10 rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 w-full max-w-sm px-6 flex flex-col items-center gap-8">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/10 to-amber-500/5 border border-orange-500/20 flex items-center justify-center text-orange-500 shadow-[0_0_30px_rgba(249,115,22,0.2)]">
            <BotMessageSquare size={28} strokeWidth={2.5} />
          </div>
          <div className="text-center">
            <h1 className="font-bold text-2xl text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-500 tracking-tight">
              Dhaba AI
            </h1>
            <p className="text-zinc-500 text-xs font-black tracking-[0.2em] uppercase mt-1">
              Business Intelligence
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-zinc-200 placeholder-zinc-600 text-sm outline-none focus:border-orange-500/40 focus:bg-white/[0.07] transition-all"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-zinc-200 placeholder-zinc-600 text-sm outline-none focus:border-orange-500/40 focus:bg-white/[0.07] transition-all"
          />

          {error && (
            <p className="text-red-400 text-xs text-center font-medium">{error}</p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 rounded-xl bg-orange-500/10 border border-orange-500/20 text-orange-400 font-bold text-sm uppercase tracking-wider hover:bg-orange-500/20 hover:border-orange-500/40 transition-all disabled:opacity-40 disabled:cursor-not-allowed mt-1"
          >
            {isLoading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="text-zinc-600 text-[11px] text-center">
          Use your Bill-App credentials to sign in.
        </p>
      </div>
    </div>
  )
}
