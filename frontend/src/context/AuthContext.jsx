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
  const [token,        setToken]        = useState(() => localStorage.getItem(TOKEN_KEY) ?? null)
  const [usuario,      setUsuario]      = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })
  const [empresaConfig, setEmpresaConfig] = useState(() => {
    try { return JSON.parse(localStorage.getItem(BRAND_KEY)) } catch { return null }
  })
  const [loading, setLoading] = useState(false)
  const [erro,    setErro]    = useState('')

  const _loadEmpresaConfig = useCallback(async (tok) => {
    const cfg = await _fetchEmpresaConfig(tok)
    if (cfg) {
      setEmpresaConfig(cfg)
      localStorage.setItem(BRAND_KEY, JSON.stringify(cfg))
    }
  }, [])

  // Atualiza silenciosamente o token, dados do usuário e branding da empresa.
  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY)
    if (!t) return
    fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        localStorage.setItem(TOKEN_KEY, data.token)
        localStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
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
      localStorage.setItem(TOKEN_KEY, data.token)
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
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
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(BRAND_KEY)
    setToken(null)
    setUsuario(null)
    setEmpresaConfig(null)
  }

  function refreshEmpresaConfig() {
    const t = localStorage.getItem(TOKEN_KEY)
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
      empresaConfig, refreshEmpresaConfig,
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
