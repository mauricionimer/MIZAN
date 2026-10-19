import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LogoMark } from '../components/Logo'
import { getEmpresaConfigPublica, marcaPorEmail } from '../api'
import { aplicarCorDaMarca } from '../utils/marca'

const BASE_API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const sessionExpirada = searchParams.get('expired') === '1'
  const { login, loading, erro } = useAuth()
  const [email, setEmail]       = useState('')
  const [senha, setSenha]       = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [empresaBrand, setEmpresaBrand] = useState(null)

  useEffect(() => {
    fetch(`${BASE_API}/health`).catch(() => {})
    const empresaParam = searchParams.get('empresa')
    if (empresaParam) {
      getEmpresaConfigPublica(null, empresaParam)
        .then(cfg => { if (cfg?.empresa_id) setEmpresaBrand(cfg) })
        .catch(() => {})
    }
  }, [])

  const reduzir = useReducedMotion()
  const [marcaDoEmail, setMarcaDoEmail] = useState(null)

  // Marca pelo DOMÍNIO do e-mail ("Mizan & Goiás Bank"). O servidor responde
  // só pelo domínio cadastrado pelo COMANDO, nunca pela pessoa: o mesmo para
  // quem tem conta e para quem não tem (ver backend/marca.py).
  const dominio = (email.split('@')[1] || '').trim().toLowerCase()
  useEffect(() => {
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(dominio)) { setMarcaDoEmail(null); return }
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      marcaPorEmail(`x@${dominio}`, ctrl.signal).then(setMarcaDoEmail).catch(() => {})
    }, 350)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [dominio])

  function handleEmailChange(value) {
    setEmail(value)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const user = await login(email, senha)
    if (!user) return
    // Volta para a tela de onde a pessoa saiu (sessão expirada ou link direto).
    // Só caminho interno: "//site" ou URL completa levariam para fora.
    const de = searchParams.get('de')
    const from = location.state?.from
    const anterior = de || (from?.pathname ? `${from.pathname}${from.search || ''}` : '')
    if (anterior.startsWith('/') && !anterior.startsWith('//') && !anterior.startsWith('/login')) {
      navigate(anterior, { replace: true })
    } else {
      // Admin e operador caem direto na tela de trabalho.
      navigate(user.role === 'comando' ? '/comando' : '/', { replace: true })
    }
  }

  // O link `?empresa=` vale primeiro; sem ele, a marca do domínio digitado.
  const marca = empresaBrand || marcaDoEmail
  const cor = marca?.cor_primaria

  // Antes do login o AuthContext ainda não tem empresaConfig, então a cor da
  // empresa (com a tinta --on-brand certa) é aplicada aqui. Ao sair da tela,
  // volta a marca da sessão (se já entrou) ou nenhuma.
  useEffect(() => {
    aplicarCorDaMarca(cor)
  }, [cor])
  useEffect(() => () => {
    let daSessao = null
    try { daSessao = JSON.parse(sessionStorage.getItem('mizan_empresa_config'))?.cor_primaria } catch { /* sem marca */ }
    aplicarCorDaMarca(daSessao)
  }, [])

  const nomEmpresa = marca?.nome_exibicao
  const fotoEmpresa = marca?.foto_url
  const inicial = (nomEmpresa || '?').trim().charAt(0).toUpperCase()

  return (
    <div className="login-shell">
      <ThemeToggle className="fixed top-4 right-4 z-50" />

      <div className="login-stack">
        {/* Marca — grande à esquerda no desktop, no topo no mobile */}
        <div className="login-brand-bloco">
          <div className="login-brand">
            <LogoMark className="login-brand-mark" />
            <span className="login-brand-word">Mizan</span>
          </div>
          {/* "& Empresa": aparece quando o domínio do e-mail é de um cliente */}
          <AnimatePresence initial={false}>
            {nomEmpresa && (
              <motion.div key={nomEmpresa} className="login-cobrand" aria-live="polite"
                initial={reduzir ? { opacity: 0 } : { opacity: 0, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)', transitionEnd: { filter: 'none' } }}
                exit={reduzir ? { opacity: 0 } : { opacity: 0, y: -6, filter: 'blur(4px)' }}
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}>
                <span className="login-cobrand-e" aria-hidden="true">&amp;</span>
                {fotoEmpresa
                  ? <img src={fotoEmpresa} alt="" className="login-cobrand-foto" />
                  : <span className="login-cobrand-inicial" aria-hidden="true">{inicial}</span>}
                <span className="login-cobrand-nome">{nomEmpresa}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Card do formulário */}
        <div className="login-card">
          <h1 className="login-title">Entrar</h1>

          <form onSubmit={handleSubmit} className="space-y-5 mt-7">
            {sessionExpirada && (
              <div role="status" className="p-3.5 rounded text-sm text-center"
                style={{ color: 'var(--ink)', background: 'var(--warning-soft, var(--surface-2))', border: '1px solid var(--warning)' }}>
                Sua sessão expirou. Entre de novo para continuar.
              </div>
            )}

            <div>
              <label className="login-label" htmlFor="login-email">E-mail</label>
              <input
                id="login-email"
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
              <label className="login-label" htmlFor="login-senha">Senha</label>
              <div className="relative">
                <input
                  id="login-senha"
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
                  aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {mostrarSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div className="flex justify-end mt-1.5">
                <a href="/esqueci-senha" className="login-link">Esqueci minha senha</a>
              </div>
            </div>

            {erro && (
              <div role="alert" className="text-sm rounded px-4 py-3"
                style={{ color: 'var(--danger)', background: 'var(--danger-soft)', border: '1px solid var(--danger)' }}>
                {erro}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full py-3">
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                : 'Entrar'}
            </button>
          </form>

          <p className="mt-7 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
            <a href="/privacidade" className="underline hover:text-[var(--text-2)] transition-colors">
              Política de privacidade
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
