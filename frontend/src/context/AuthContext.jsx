import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY  = 'mizan_token'
const USER_KEY   = 'mizan_user'
const BRAND_KEY  = 'mizan_empresa_config'
const BASE       = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

async function _fetchEmpresaConfig(token) {
  try {
    const res = await fetch(`${BASE}/empresa/config`, {
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    })
    return res.ok ? res.json() : null
  } catch { return null }
}

export function AuthProvider({ children }) {
  const [token,        setToken]        = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? null)
  const [usuario,      setUsuario]      = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(USER_KEY)) } catch { return null }
  })
  const [empresaConfig, setEmpresaConfig] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(BRAND_KEY)) } catch { return null }
  })
  const [loading, setLoading] = useState(false)
  const [erro,    setErro]    = useState('')

  // Aplica a cor da empresa como superfície da marca (--royal: preenchimento
  // de botão primário e afins). Duas regras que não dá para ignorar:
  //
  // 1. A tinta por cima (--on-brand) é escolhida pela luminância da cor da
  //    empresa. Cravar branco deixa texto ilegível sobre uma marca clara, e
  //    cravar escuro faz o mesmo sobre uma marca escura.
  // 2. --accent-text fica de fora de propósito. É o tom usado em ícone, link
  //    e texto sobre fundo neutro, e precisa contrastar com a superfície, não
  //    com a marca. Uma empresa de azul escuro sumia no tema escuro quando
  //    essa cor era aplicada aqui.
  useEffect(() => {
    const raiz = document.documentElement
    const cor = empresaConfig?.cor_primaria
    if (!cor || !/^#[0-9a-f]{6}$/i.test(cor)) {
      for (const v of ['--royal', '--royal-hover', '--royal-pressed', '--on-brand']) {
        raiz.style.removeProperty(v)
      }
      return
    }
    raiz.style.setProperty('--royal', cor)

    const [r, g, b] = [1, 3, 5].map(i => parseInt(cor.slice(i, i + 2), 16) / 255)
    const lin = v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))
    const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    const contraste = claro => {
      const [a, z] = claro ? [1.0, L] : [L, 0.0]
      return (Math.max(a, z) + 0.05) / (Math.min(a, z) + 0.05)
    }
    const tintaClara = contraste(true) >= contraste(false)
    raiz.style.setProperty('--on-brand', tintaClara ? '#ffffff' : '#0b1020')

    // Hover e pressed precisam sair da mesma cor, senão o estado herda o azul
    // do tema e a tinta escolhida acima deixa de contrastar. Com tinta clara
    // o botão escurece ao interagir; com tinta escura, clareia.
    const mover = f => {
      const alvo = tintaClara ? 0 : 255
      const canal = i => Math.round(parseInt(cor.slice(i, i + 2), 16) * (1 - f) + alvo * f)
      return `#${[1, 3, 5].map(i => canal(i).toString(16).padStart(2, '0')).join('')}`
    }
    raiz.style.setProperty('--royal-hover', mover(0.14))
    raiz.style.setProperty('--royal-pressed', mover(0.26))
  }, [empresaConfig?.cor_primaria])

  const _loadEmpresaConfig = useCallback(async (tok) => {
    const cfg = await _fetchEmpresaConfig(tok)
    if (cfg) {
      setEmpresaConfig(cfg)
      sessionStorage.setItem(BRAND_KEY, JSON.stringify(cfg))
    }
  }, [])

  // Atualiza silenciosamente o token, dados do usuário e branding da empresa.
  useEffect(() => {
    const t = sessionStorage.getItem(TOKEN_KEY)
    if (!t) return
    fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        sessionStorage.setItem(TOKEN_KEY, data.token)
        sessionStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
        setToken(data.token)
        setUsuario(data.usuario)
        _loadEmpresaConfig(data.token)
      })
      .catch(() => {})
  }, [_loadEmpresaConfig])

  async function login(email, senha) {
    setLoading(true); setErro('')
    try {
      const res = await fetch(`${BASE}/auth/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, senha }),
      })
      const data = await res.json()
      if (!res.ok) { setErro(data.detail ?? 'Erro ao fazer login'); return null }
      sessionStorage.setItem(TOKEN_KEY, data.token)
      sessionStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
      setToken(data.token)
      setUsuario(data.usuario)
      _loadEmpresaConfig(data.token)
      return data.usuario
    } catch {
      setErro('Não foi possível conectar ao servidor.')
      return null
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    sessionStorage.removeItem(BRAND_KEY)
    setToken(null)
    setUsuario(null)
    setEmpresaConfig(null)
    window.dispatchEvent(new Event('mizan:logout'))
  }

  // Depois de trocar a senha o token antigo deixa de valer: guarda o novo.
  function trocarToken(novo) {
    if (!novo) return
    sessionStorage.setItem(TOKEN_KEY, novo)
    setToken(novo)
  }

  function refreshEmpresaConfig() {
    const t = sessionStorage.getItem(TOKEN_KEY)
    if (t) _loadEmpresaConfig(t)
  }

  const isAdmin    = usuario?.role === 'admin'
  const isComando  = usuario?.role === 'comando'
  const isOperador = usuario?.role === 'operador'
  const empresaId  = usuario?.empresa_id || ''

  return (
    <AuthContext.Provider value={{
      token, usuario, login, logout, loading, erro,
      isAdmin, isComando, isOperador, autenticado: !!token,
      empresaConfig, refreshEmpresaConfig, trocarToken,
      empresaId,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
