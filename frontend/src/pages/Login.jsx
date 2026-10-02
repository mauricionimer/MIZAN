import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
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

  useEffect(() => {
    fetch(`${BASE_API}/health`).catch(() => {})
    const empresaParam = searchParams.get('empresa')
    if (empresaParam) {
      getEmpresaConfigPublica(null, empresaParam)
        .then(cfg => { if (cfg?.empresa_id) setEmpresaBrand(cfg) })
        .catch(() => {})
    }
  }, [])

  // Sem consulta por e-mail: mostrar a marca conforme o que se digita revelaria
  // quem tem conta e de qual empresa. A marca vem só do link `?empresa=`.
  function handleEmailChange(value) {
    setEmail(value)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const user = await login(email, senha)
    if (!user) return
    if (user.role === 'comando') navigate('/comando')
    // Admin e operador caem direto na tela de trabalho: o menu intermediário
    // deixou de existir, e as opções dele estão lá dentro.
    else navigate('/')
  }

  const cor = empresaBrand?.cor_primaria

  // Antes do login o AuthContext ainda não tem empresaConfig, então a cor da
  // empresa precisa ser aplicada aqui para o branding valer já na entrada.
  // Sem empresa, a propriedade é removida: cravar um valor no <html> venceria
  // o --royal do tema escuro, que é mais claro que o do tema claro.
  useEffect(() => {
    const raiz = document.documentElement
    if (cor) raiz.style.setProperty('--royal', cor)
    else raiz.style.removeProperty('--royal')
  }, [cor])

  const nomEmpresa = empresaBrand?.nome_exibicao
  const fotoEmpresa = empresaBrand?.foto_url

  return (
    <div className="login-shell">
      <ThemeToggle className="fixed top-4 right-4 z-50" />

      <div className="login-stack">
        {/* Marca — grande à esquerda no desktop, no topo no mobile */}
        <div className="login-brand">
          {fotoEmpresa
            ? <img src={fotoEmpresa} alt={nomEmpresa} className="login-brand-foto" />
            : <LogoMark className="login-brand-mark" />}
          <span className="login-brand-word">{nomEmpresa || 'Mizan'}</span>
        </div>

        {/* Card do formulário */}
        <div className="login-card">
          <h1 className="login-title">Entrar</h1>

          <form onSubmit={handleSubmit} className="space-y-5 mt-7">
            {sessionExpirada && (
              <div className="p-3.5 rounded text-amber-300 text-sm text-center bg-amber-950 border border-amber-900">
                Sua sessão expirou. Faça login novamente.
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
              <div className="text-sm rounded px-4 py-3"
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
