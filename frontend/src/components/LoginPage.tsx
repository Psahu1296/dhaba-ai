import { useState } from 'react'

interface Props {
  onLogin: (email: string, password: string) => Promise<boolean>
  onGuest: () => void
  error: string | null
  isLoading: boolean
}

export function LoginPage({ onLogin, onGuest, error, isLoading }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  async function handleSubmit(e: any) {
    e.preventDefault()
    await onLogin(email, password)
  }

  return (
    <div className="flex flex-col items-center justify-center h-[100dvh] bg-[#050505] relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-15%] left-[-10%] w-[50%] h-[50%] bg-orange-600/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-amber-500/10 rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 w-full max-w-sm px-6 flex flex-col items-center gap-8">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl overflow-hidden bg-gradient-to-br from-orange-500/10 to-amber-500/5 border border-orange-500/20 flex items-center justify-center shadow-[0_0_30px_rgba(249,115,22,0.2)]">
            <img src="/dhaba_logo.png" alt="Dhaba AI Logo" className="w-full h-full object-cover" />
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

        <div className="w-full flex items-center gap-3 text-zinc-700 text-[10px] uppercase tracking-[0.2em]">
          <span className="h-px flex-1 bg-white/10" /> or <span className="h-px flex-1 bg-white/10" />
        </div>

        <button
          type="button"
          onClick={onGuest}
          className="w-full py-3 rounded-xl bg-white/5 border border-white/10 text-zinc-200 font-bold text-sm uppercase tracking-wider hover:bg-white/10 hover:border-orange-500/30 transition-all"
        >
          Try the demo
        </button>
        <p className="text-zinc-600 text-[11px] text-center -mt-5">
          Live restaurant data · customer details hidden
        </p>
      </div>
    </div>
  )
}
