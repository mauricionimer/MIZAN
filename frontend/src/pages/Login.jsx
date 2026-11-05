import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Mail, Lock, ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LogoCompleto } from '../components/Logo'
import { GlassFold } from '../components/ui/glass-fold'
import { FormInput } from '../components/ui/glass-form'
import { getEmpresaConfigPublica, marcaPorEmail } from '../api'
import { aplicarCorDaMarca } from '../utils/marca'
import { useTheme } from '../context/ThemeContext'

const BASE_API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { claro } = useTheme()
  const [searchParams] = useSearchParams()
  const sessionExpirada = searchParams.get('expired') === '1'
  const { login, confirmarCodigo, loading, erro, setErro } = useAuth()
  const [email, setEmail]       = useState('')
  const [senha, setSenha]       = useState('')
  // Segunda etapa (2FA): o desafio que o servidor devolveu depois da senha certa.
  const [desafio, setDesafio]   = useState(null)
  const [codigo, setCodigo]     = useState('')
  const [recuperacao, setRecuperacao] = useState(false)
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
    if (user.etapa === '2fa') { setDesafio(user.desafio); setCodigo(''); return }
    entrar()
  }

  async function enviarCodigo(e) {
    e.preventDefault()
    const user = await confirmarCodigo(desafio, codigo)
    if (!user) return
    entrar()
  }

  function voltarParaSenha() {
    setDesafio(null); setCodigo(''); setRecuperacao(false); setSenha(''); setErro('')
  }

  function entrar() {
    // Todo login começa no Início, inclusive após expiração da sessão
    // ou quando a pessoa chega por um link de outra área. O Início oferece
    // "Continuar de onde parou" com a tela que ela tinha aberta.
    const de = searchParams.get('de') ?? (location.state?.from ? location.state.from.pathname + location.state.from.search : null)
    const retomar = de && de.startsWith('/') && !de.startsWith('//') && !/^\/(login|inicio)\b/.test(de) ? de : null
    navigate('/inicio', { replace: true, state: retomar ? { retomar } : undefined })
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
      {/* Fundo animado (WebGL) nas cores da marca; fica parado com "reduzir movimento" */}
      <GlassFold
        className="login-fundo"
        light={claro}
        color1={claro ? '#a9b4f5' : '#5966d9'}
        color2={claro ? '#f1eeff' : '#1a0033'}
        color3={claro ? '#ffffff' : '#b8c0ee'}
        speed={0.35}
        noise={0.1}
      />
      <ThemeToggle className="fixed top-4 right-4 z-50" />

      <div className="login-stack">
        {/* Marca — grande à esquerda no desktop, no topo no mobile */}
        <div className="login-brand-bloco">
          <div className="login-brand">
            <LogoCompleto className="login-brand-logo" />
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
          <h1 className="login-title">{desafio ? 'Verificação em duas etapas' : 'Entrar'}</h1>

          {desafio ? (
            <form onSubmit={enviarCodigo} className="space-y-5 mt-7">
              <p className="text-sm text-center" style={{ color: 'var(--glass-muted)' }}>
                {recuperacao
                  ? 'Digite um dos seus códigos de recuperação (cada um vale uma vez).'
                  : 'Abra o app autenticador no celular e digite o código de 6 dígitos do Mizan.'}
              </p>
              <FormInput
                id="login-codigo"
                type="text"
                icon={<ShieldCheck size={18} />}
                value={codigo}
                onChange={e => setCodigo(recuperacao ? e.target.value : e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder={recuperacao ? 'xxxxx-xxxxx' : '000000'}
                aria-label={recuperacao ? 'Código de recuperação' : 'Código de 6 dígitos'}
                inputMode={recuperacao ? 'text' : 'numeric'}
                autoComplete="one-time-code"
                required
                autoFocus
              />
              {erro && (
                <div role="alert" className="text-sm rounded px-4 py-3"
                  style={{ color: 'var(--danger)', background: 'var(--danger-soft)', border: '1px solid var(--danger)' }}>
                  {erro}
                </div>
              )}
              <button type="submit" disabled={loading || (!recuperacao && codigo.length !== 6)}
                className="btn-primary login-enviar w-full py-3">
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Conferindo...</> : 'Confirmar'}
              </button>
              <div className="flex justify-between text-xs">
                <button type="button" className="login-link" onClick={() => { setRecuperacao(r => !r); setCodigo(''); setErro('') }}>
                  {recuperacao ? 'Usar o código do app' : 'Perdi o celular: usar código de recuperação'}
                </button>
                <button type="button" className="login-link" onClick={voltarParaSenha}>Voltar</button>
              </div>
            </form>
          ) : (
          <form onSubmit={handleSubmit} className="space-y-5 mt-7">
            {sessionExpirada && (
              <div role="status" className="p-3.5 rounded text-sm text-center"
                style={{ color: 'var(--ink)', background: 'var(--warning-soft, var(--surface-2))', border: '1px solid var(--warning)' }}>
                Sua sessão expirou. Entre de novo para continuar.
              </div>
            )}

            <FormInput
              id="login-email"
              type="email"
              icon={<Mail size={18} />}
              value={email}
              onChange={e => handleEmailChange(e.target.value)}
              placeholder="E-mail"
              aria-label="E-mail"
              required
              autoFocus
            />

            <div>
              <FormInput
                id="login-senha"
                type={mostrarSenha ? 'text' : 'password'}
                icon={<Lock size={18} />}
                value={senha}
                onChange={e => setSenha(e.target.value)}
                placeholder="Senha"
                aria-label="Senha"
                required
                trailing={
                  <button
                    type="button"
                    onClick={() => setMostrarSenha(v => !v)}
                    aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                    className="glass-input-icon absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                  >
                    {mostrarSenha ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />
              <div className="flex justify-end mt-2">
                <a href="/esqueci-senha" className="login-link">Esqueci minha senha</a>
              </div>
            </div>

            {erro && (
              <div role="alert" className="text-sm rounded px-4 py-3"
                style={{ color: 'var(--danger)', background: 'var(--danger-soft)', border: '1px solid var(--danger)' }}>
                {erro}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary login-enviar w-full py-3">
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Entrando...</>
                : 'Entrar'}
            </button>
          </form>
          )}

          <p className="mt-7 text-center text-xs" style={{ color: 'var(--glass-muted)' }}>
            <a href="/privacidade" className="underline hover:text-[var(--glass-ink)] transition-colors">
              Política de privacidade
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
