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
    // Acorda o backend enquanto o usuário lê a página
    fetch(`${BASE_API}/health`).catch(() => {})

    // URL param ?empresa=sicoob → branding correto sem precisar do email
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

    // Limpa o branding se o campo for apagado
    if (!e || !e.includes('@')) {
      setEmpresaBrand(null)
      lastFetchedRef.current = ''
      clearTimeout(debounceRef.current)
      return
    }

    // Só busca quando há domínio completo (ex: user@gmail.com)
    const [, domain = ''] = e.split('@')
    if (!domain.includes('.')) return

    // Debounce — espera 600ms após parar de digitar
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      if (e === lastFetchedRef.current) return
      lastFetchedRef.current = e
      try {
        const cfg = await getEmpresaConfigPublica(e)
        // Só aplica se o email ainda é o mesmo (usuário não mudou)
        if (e === lastFetchedRef.current) {
          setEmpresaBrand(cfg?.empresa_id ? cfg : null)
        }
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

  const cor = empresaBrand?.cor_primaria || '#1d4ed8'
  const nomEmpresa = empresaBrand?.nome_exibicao
  const fotoEmpresa = empresaBrand?.foto_url

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden p-4"
      style={{ background: fotoEmpresa
        ? `linear-gradient(150deg,rgba(2,11,31,0.92) 0%,rgba(15,37,89,0.85) 40%,rgba(29,78,216,0.7) 100%)`
        : 'linear-gradient(150deg,#020b1f 0%,#0f2559 35%,#1a3a9e 65%,#1d4ed8 100%)' }}>

      {/* Foto de capa da empresa */}
      {fotoEmpresa && (
        <div className="absolute inset-0 z-0">
          <img src={fotoEmpresa} alt="" className="w-full h-full object-cover" />
          <div className="absolute inset-0"
            style={{ background: 'linear-gradient(150deg,rgba(2,11,31,0.88) 0%,rgba(15,37,89,0.82) 40%,rgba(29,78,216,0.65) 100%)' }} />
        </div>
      )}

      {/* Decorações de fundo (só sem foto) */}
      {!fotoEmpresa && <>
        <div className="absolute inset-0 opacity-[0.035]"
          style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.8) 1px, transparent 0)', backgroundSize: '28px 28px' }} />
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full blur-3xl opacity-20"
          style={{ background: 'radial-gradient(circle,#60a5fa,transparent 70%)' }} />
        <div className="absolute bottom-[-15%] right-[-5%] w-[500px] h-[500px] rounded-full blur-3xl opacity-15"
          style={{ background: 'radial-gradient(circle,#818cf8,transparent 70%)' }} />
      </>}

      {/* Layout split */}
      <div className="relative z-10 w-full max-w-5xl flex items-center gap-16">

        {/* Lado esquerdo */}
        <div className="hidden lg:flex flex-1 flex-col gap-8">

          {/* Logo / marca */}
          <div className="flex items-center gap-3">
            {fotoEmpresa ? (
              <img src={fotoEmpresa} alt={nomEmpresa}
                className="w-12 h-12 rounded-2xl object-cover border-2 border-white/30 shadow-xl" />
            ) : (
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.2)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
                <span className="text-white text-xl font-bold">⚖</span>
              </div>
            )}
            <span className="text-white text-2xl font-extrabold tracking-tight">
              {nomEmpresa || 'Mizan'}
            </span>
            {nomEmpresa && (
              <span className="text-white/40 text-sm font-medium">· via Mizan</span>
            )}
          </div>

          {/* Tagline */}
          <div>
            <p className="text-blue-300 text-xs font-bold uppercase tracking-[0.2em] mb-4">
              Recuperação de crédito com IA
            </p>
            <h2 className="text-5xl font-extrabold text-white leading-[1.1] tracking-tight mb-5">
              {nomEmpresa ? (
                <>Bem-vindo à<br /><span style={{ color: cor === '#1d4ed8' ? '#93c5fd' : cor }}>{nomEmpresa}</span></>
              ) : (
                <>Recupere mais.<br /><span className="text-blue-300">Aprenda com</span><br />cada resultado.</>
              )}
            </h2>
            <p className="text-blue-200/70 text-base leading-relaxed max-w-sm">
              Analise carteiras, priorize devedores e receba recomendações que evoluem com cada contato registrado.
            </p>
          </div>

          {/* Stats (só sem empresa) */}
          {!nomEmpresa && (
            <div className="grid grid-cols-3 gap-3">
              {[
                { n: '98%', l: 'Precisão ML',  icon: '🎯' },
                { n: '<1s',  l: 'Por devedor', icon: '⚡' },
                { n: '12',   l: 'Estratégias', icon: '🧠' },
              ].map(({ n, l, icon }) => (
                <div key={l} className="rounded-2xl p-4"
                  style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', backdropFilter: 'blur(8px)' }}>
                  <p className="text-xl mb-2">{icon}</p>
                  <p className="text-2xl font-extrabold text-white tracking-tight">{n}</p>
                  <p className="text-blue-300 text-xs mt-1 font-semibold">{l}</p>
                </div>
              ))}
            </div>
          )}

          <p className="text-blue-400/50 text-xs">© 2026 Mizan · Todos os direitos reservados</p>
        </div>

        {/* Lado direito — card do formulário */}
        <div className="w-full lg:w-[400px] shrink-0">
          <div className="bg-white rounded-3xl p-8"
            style={{ boxShadow: '0 32px 80px rgba(0,0,0,0.5), 0 8px 24px rgba(0,0,0,0.3)' }}>

            {/* Cabeçalho mobile / empresa */}
            <div className="flex items-center gap-2.5 mb-8">
              {fotoEmpresa ? (
                <img src={fotoEmpresa} alt={nomEmpresa}
                  className="w-9 h-9 rounded-xl object-cover border border-slate-100 shrink-0" />
              ) : (
                <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg shrink-0"
                  style={{ background: `linear-gradient(135deg,${cor},${cor}cc)` }}>
                  <span className="text-white font-bold text-sm">⚖</span>
                </div>
              )}
              <div>
                <span className="text-slate-800 text-base font-bold tracking-tight leading-none block">
                  {nomEmpresa || 'Mizan'}
                </span>
                {nomEmpresa && (
                  <span className="text-slate-400 text-xs">via Mizan</span>
                )}
              </div>
            </div>

            <div className="mb-7">
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
                  onChange={e => handleEmailChange(e.target.value)}
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
                  <a href="/esqueci-senha" className="text-xs text-blue-600 hover:text-blue-800 transition-colors font-semibold">
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
                className="w-full py-3 rounded-xl font-bold text-white text-base disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                style={{ background: `linear-gradient(135deg,${cor},${cor}cc)`,
                  boxShadow: `0 4px 16px ${cor}40` }}
              >
                {loading
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                  : 'Entrar'}
              </button>
            </form>

            <p className="mt-7 text-center text-xs text-slate-400">
              Acesso restrito a usuários cadastrados.{' '}
              <a href="/privacidade" className="underline hover:text-slate-600 transition-colors">Privacidade</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
