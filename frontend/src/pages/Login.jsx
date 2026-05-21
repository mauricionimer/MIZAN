import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function Logo({ size = 'md' }) {
  const sz = size === 'lg' ? 'w-11 h-11 text-lg' : 'w-8 h-8 text-sm'
  return (
    <div className={`${sz} rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25 shrink-0`}
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold">⚖</span>
    </div>
  )
}

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionExpirada = searchParams.get('expired') === '1'
  const { login, loading, erro } = useAuth()
  const [email, setEmail]       = useState('')
  const [senha, setSenha]       = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const ok = await login(email, senha)
    if (ok) navigate('/')
  }

  return (
    <div className="min-h-screen flex">
      {/* Painel esquerdo */}
      <div className="hidden lg:flex lg:w-[52%] flex-col justify-between p-14 relative overflow-hidden"
        style={{ background: 'linear-gradient(150deg,#0f172a 0%,#1e3a8a 50%,#1d4ed8 100%)' }}>
        {/* Decoração de fundo */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />
        <div className="absolute bottom-0 right-0 w-96 h-96 rounded-full opacity-10 blur-3xl"
          style={{ background: 'radial-gradient(circle,#60a5fa,transparent)' }} />

        <div className="flex items-center gap-3 relative">
          <Logo size="lg" />
          <span className="text-white text-xl font-bold tracking-tight">Mizan</span>
        </div>

        <div className="relative">
          <p className="text-blue-300 text-xs font-semibold uppercase tracking-widest mb-5">Recuperação de crédito com IA</p>
          <h2 className="text-4xl font-extrabold text-white leading-[1.15] tracking-tight mb-6">
            Recupere mais.<br />Aprenda com cada resultado.
          </h2>
          <p className="text-blue-200/80 text-base leading-relaxed max-w-sm">
            Analise carteiras, priorize devedores e receba recomendações que evoluem com cada contato registrado.
          </p>

          <div className="mt-10 grid grid-cols-3 gap-3">
            {[
              { n: '98%',  l: 'Precisão ML' },
              { n: '<1s',  l: 'Por devedor' },
              { n: '12',   l: 'Estratégias' },
            ].map(({ n, l }) => (
              <div key={l} className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm p-4">
                <p className="text-2xl font-extrabold text-white tracking-tight">{n}</p>
                <p className="text-blue-300 text-xs mt-1 font-medium">{l}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-blue-400/60 text-xs relative">© 2026 Mizan · Todos os direitos reservados</p>
      </div>

      {/* Painel direito — formulário */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-white">
        <div className="lg:hidden flex items-center gap-2.5 mb-10">
          <Logo />
          <span className="text-slate-800 text-xl font-bold tracking-tight">Mizan</span>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Bem-vindo de volta</h1>
            <p className="text-slate-500 text-sm mt-1.5">Entre com suas credenciais para acessar</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {sessionExpirada && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-100 text-amber-700 text-sm text-center">
                Sua sessão expirou. Faça login novamente.
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">E-mail</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="seu@email.com"
                required
                autoFocus
                className="input-base"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Senha</label>
              <div className="relative">
                <input
                  type={mostrarSenha ? 'text' : 'password'}
                  value={senha}
                  onChange={e => setSenha(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="input-base pr-11"
                />
                <button
                  type="button"
                  onClick={() => setMostrarSenha(v => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {mostrarSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div className="flex justify-end mt-1.5">
                <a href="/esqueci-senha" className="text-xs text-blue-600 hover:text-blue-800 transition-colors font-medium">
                  Esqueci minha senha
                </a>
              </div>
            </div>

            {erro && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                {erro}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 disabled:opacity-50"
            >
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                : 'Entrar'}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-slate-400">
            Acesso restrito a usuários cadastrados.{' '}
            <a href="/privacidade" className="underline hover:text-slate-600 transition-colors">Privacidade</a>
          </p>
        </div>
      </div>
    </div>
  )
}
