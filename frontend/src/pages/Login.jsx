import ThemeToggle from '../components/ThemeToggle'
import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getEmpresaConfigPublica } from '../api'

const BASE_API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionExpirada = searchParams.get('expired') === '1'
  const { login, loading, erro } = useAuth()
  const [email, setEmail]       = useState('')
  const [senha, setSenha]       = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [empresaBrand, setEmpresaBrand] = useState(null)
  const debounceRef = useRef(null)
  const lastFetchedRef = useRef('')

  useEffect(() => {
    fetch(`${BASE_API}/health`).catch(() => {})
    const empresaParam = searchParams.get('empresa')
    if (empresaParam) {
      getEmpresaConfigPublica(null, empresaParam)
        .then(cfg => { if (cfg?.empresa_id) setEmpresaBrand(cfg) })
        .catch(() => {})
    }
  }, [])

  function handleEmailChange(value) {
    setEmail(value)
    const e = value.trim().toLowerCase()
    if (!e || !e.includes('@')) {
      setEmpresaBrand(null)
      lastFetchedRef.current = ''
      clearTimeout(debounceRef.current)
      return
    }
    const [, domain = ''] = e.split('@')
    if (!domain.includes('.')) return
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      if (e === lastFetchedRef.current) return
      lastFetchedRef.current = e
      try {
        const cfg = await getEmpresaConfigPublica(e)
        if (e === lastFetchedRef.current) setEmpresaBrand(cfg?.empresa_id ? cfg : null)
      } catch { /* silencioso */ }
    }, 600)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const user = await login(email, senha)
    if (!user) return
    if (user.role === 'comando') navigate('/comando')
    else if (user.role === 'admin') navigate('/admin')
    else navigate('/operador')
  }

  const cor = empresaBrand?.cor_primaria || '#1d6aff'
  const nomEmpresa = empresaBrand?.nome_exibicao
  const fotoEmpresa = empresaBrand?.foto_url

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden p-4"
      style={{ background: '#080d1e' }}>
      <ThemeToggle className="fixed top-4 right-4 z-50" />

      {/* Glow de fundo */}
      <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full blur-3xl opacity-10 pointer-events-none"
        style={{ background: 'radial-gradient(circle,#1d6aff,transparent 70%)' }} />
      <div className="absolute bottom-[-15%] right-[-5%] w-[500px] h-[500px] rounded-full blur-3xl opacity-8 pointer-events-none"
        style={{ background: 'radial-gradient(circle,#8b5cf6,transparent 70%)' }} />

      {/* Foto de capa da empresa */}
      {fotoEmpresa && (
        <div className="absolute inset-0 z-0">
          <img src={fotoEmpresa} alt="" className="w-full h-full object-cover" />
          <div className="absolute inset-0" style={{ background: 'rgba(8,13,30,0.88)' }} />
        </div>
      )}

      {/* Layout split */}
      <div className="relative z-10 w-full max-w-5xl flex items-center gap-16">

        {/* Lado esquerdo */}
        <div className="hidden lg:flex flex-1 flex-col gap-8">
          <div className="flex items-center gap-3">
            {fotoEmpresa ? (
              <img src={fotoEmpresa} alt={nomEmpresa}
                className="w-12 h-12 rounded-2xl object-cover border border-line-2 shadow-xl" />
            ) : (
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(29,106,255,0.15)', border: '1px solid rgba(29,106,255,0.30)', boxShadow: '0 8px 32px rgba(29,106,255,0.15)' }}>
                <span className="text-ink text-xl font-bold">⚖</span>
              </div>
            )}
            <span className="text-ink text-2xl font-extrabold tracking-tight">
              {nomEmpresa || 'Mizan'}
            </span>
            {nomEmpresa && <span className="text-ink-4 text-sm font-medium">· via Mizan</span>}
          </div>

          <div>
            <p className="text-blue-400 text-xs font-bold uppercase tracking-[0.2em] mb-4">
              Recuperação de crédito com IA
            </p>
            <h2 className="text-5xl font-extrabold text-ink leading-[1.1] tracking-tight mb-5">
              {nomEmpresa ? (
                <>Bem-vindo à<br /><span style={{ color: cor }}>{nomEmpresa}</span></>
              ) : (
                <>Recupere mais.<br /><span className="text-blue-400">Aprenda com</span><br />cada resultado.</>
              )}
            </h2>
            <p className="text-ink-2 text-base leading-relaxed max-w-sm">
              Analise carteiras, priorize devedores e receba recomendações que evoluem com cada contato registrado.
            </p>
          </div>

          {!nomEmpresa && (
            <div className="grid grid-cols-3 gap-3">
              {[
                { n: '98%', l: 'Precisão ML',  icon: '🎯' },
                { n: '<1s',  l: 'Por devedor', icon: '⚡' },
                { n: '12',   l: 'Estratégias', icon: '🧠' },
              ].map(({ n, l, icon }) => (
                <div key={l} className="rounded-2xl p-4"
                  style={{ background: 'var(--raise-2)', border: '1px solid var(--line)' }}>
                  <p className="text-xl mb-2">{icon}</p>
                  <p className="text-2xl font-extrabold text-ink tracking-tight">{n}</p>
                  <p className="text-blue-400 text-xs mt-1 font-semibold">{l}</p>
                </div>
              ))}
            </div>
          )}

          <p className="text-ink-4 text-xs">© 2026 Mizan · Todos os direitos reservados</p>
        </div>

        {/* Lado direito — card do formulário */}
        <div className="w-full lg:w-[400px] shrink-0">
          <div className="rounded-3xl p-8"
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--line)',
              boxShadow: '0 32px 80px rgba(0,0,0,0.60), 0 8px 24px rgba(0,0,0,0.40)',
            }}>

            <div className="flex items-center gap-2.5 mb-8">
              {fotoEmpresa ? (
                <img src={fotoEmpresa} alt={nomEmpresa}
                  className="w-9 h-9 rounded-xl object-cover border border-line shrink-0" />
              ) : (
                <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg shrink-0"
                  style={{ background: `linear-gradient(135deg,${cor},${cor}cc)` }}>
                  <span className="text-brand-ink font-bold text-sm">⚖</span>
                </div>
              )}
              <div>
                <span className="text-ink text-base font-bold tracking-tight leading-none block">
                  {nomEmpresa || 'Mizan'}
                </span>
                {nomEmpresa && <span className="text-ink-3 text-xs">via Mizan</span>}
              </div>
            </div>

            <div className="mb-7">
              <h1 className="text-2xl font-extrabold text-ink tracking-tight">Bem-vindo de volta</h1>
              <p className="text-ink-2 text-sm mt-1.5">Entre com suas credenciais para acessar</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {sessionExpirada && (
                <div className="p-3.5 rounded-xl text-amber-400 text-sm text-center"
                  style={{ background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.20)' }}>
                  Sua sessão expirou. Faça login novamente.
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>E-mail</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => handleEmailChange(e.target.value)}
                  placeholder="seu@email.com"
                  required
                  autoFocus
                  className="input-base"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Senha</label>
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
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: 'var(--ink-3)' }}
                  >
                    {mostrarSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <div className="flex justify-end mt-1.5">
                  <a href="/esqueci-senha" className="text-xs text-blue-400 hover:text-blue-300 transition-colors font-semibold">
                    Esqueci minha senha
                  </a>
                </div>
              </div>

              {erro && (
                <div className="text-sm text-red-400 rounded-xl px-4 py-3"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
                  {erro}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl font-bold text-ink text-base disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                style={{
                  background: `linear-gradient(135deg,${cor},${cor}cc)`,
                  boxShadow: `0 4px 16px ${cor}40`,
                }}
              >
                {loading
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                  : 'Entrar'}
              </button>
            </form>

            <p className="mt-7 text-center text-xs" style={{ color: 'var(--ink-4)' }}>
              Acesso restrito a usuários cadastrados.{' '}
              <a href="/privacidade" className="underline hover:text-ink-2 transition-colors">Privacidade</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
