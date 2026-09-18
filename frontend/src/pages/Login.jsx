import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Check } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LogoMark } from '../components/Logo'
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

  const cor = empresaBrand?.cor_primaria || '#2563eb'

  // Antes do login o AuthContext ainda não tem empresaConfig, então a cor da
  // empresa precisa ser aplicada aqui para o branding valer já na tela de entrada.
  useEffect(() => {
    document.documentElement.style.setProperty('--brand', cor)
  }, [cor])
  const nomEmpresa = empresaBrand?.nome_exibicao
  const fotoEmpresa = empresaBrand?.foto_url

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden p-4"
      style={{ background: '#09090f' }}>

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
        <div className="hidden lg:flex flex-1 flex-col gap-10">
          <div className="flex items-center gap-2.5">
            {fotoEmpresa ? (
              <img src={fotoEmpresa} alt={nomEmpresa}
                className="w-9 h-9 rounded-md object-cover border border-white/10" />
            ) : (
              <LogoMark className="h-5 w-5" />
            )}
            <span className="text-white text-lg font-semibold tracking-tight">
              {nomEmpresa || 'Mizan'}
            </span>
            {nomEmpresa && <span className="text-[#6d84ab] text-sm">via Mizan</span>}
          </div>

          <div>
            <h2 className="text-4xl font-semibold text-white leading-[1.15] tracking-tight mb-4">
              {nomEmpresa
                ? <>Recuperação de crédito<br />da {nomEmpresa}.</>
                : <>Priorize quem tem<br />mais chance de pagar.</>}
            </h2>
            <p className="text-[#8fa3c8] text-base leading-relaxed max-w-md">
              Ordene a carteira por probabilidade de recuperação, registre cada contato
              e acompanhe o que realmente converteu em pagamento.
            </p>
          </div>

          {!nomEmpresa && (
            <ul className="space-y-2.5 max-w-md">
              {[
                'Score de recuperabilidade por devedor, com o motivo de cada nota',
                'Recomendação de canal e oferta calibrada pelos resultados reais',
                'Trilha de auditoria completa e exportável',
              ].map(item => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-[#8fa3c8]">
                  <Check className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--brand)' }} />
                  {item}
                </li>
              ))}
            </ul>
          )}

          <p className="text-[#6d84ab] text-xs">© 2026 Mizan</p>
        </div>

        {/* Lado direito — card do formulário */}
        <div className="w-full lg:w-[400px] shrink-0">
          <div className="panel p-8">

            <div className="flex items-center gap-2.5 mb-8 lg:hidden">
              {fotoEmpresa ? (
                <img src={fotoEmpresa} alt={nomEmpresa}
                  className="w-8 h-8 rounded-md object-cover border border-white/10 shrink-0" />
              ) : (
                <LogoMark className="h-5 w-5 shrink-0" />
              )}
              <div>
                <span className="text-white text-base font-semibold tracking-tight leading-none block">
                  {nomEmpresa || 'Mizan'}
                </span>
                {nomEmpresa && <span className="text-[#7c93bd] text-xs">via Mizan</span>}
              </div>
            </div>

            <div className="mb-7">
              <h1 className="text-xl font-semibold text-white tracking-tight">Entrar</h1>
              <p className="text-[#8fa3c8] text-sm mt-1.5">Acesso restrito a usuários cadastrados.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {sessionExpirada && (
                <div className="p-3.5 rounded-md text-amber-400 text-sm text-center"
                  style={{ background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.20)' }}>
                  Sua sessão expirou. Faça login novamente.
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>E-mail</label>
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
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Senha</label>
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
                    style={{ color: '#7c93bd' }}
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
                <div className="text-sm text-red-300 px-4 py-3"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 'var(--r-control)' }}>
                  {erro}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full py-2.5"
              >
                {loading
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                  : 'Entrar'}
              </button>
            </form>

            <p className="mt-7 text-center text-xs" style={{ color: '#6d84ab' }}>
              <a href="/privacidade" className="underline hover:text-[#8fa3c8] transition-colors">Política de privacidade</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
