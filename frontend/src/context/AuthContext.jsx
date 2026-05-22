import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'mizan_token'
const USER_KEY  = 'mizan_user'
const BASE      = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export function AuthProvider({ children }) {
  const [token,   setToken]   = useState(() => localStorage.getItem(TOKEN_KEY) ?? null)
  const [usuario, setUsuario] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })
  const [loading, setLoading] = useState(false)
  const [erro,    setErro]    = useState('')

  async function login(email, senha) {
    setLoading(true); setErro('')
    try {
      const res = await fetch(`${BASE}/auth/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, senha }),
      })
      const data = await res.json()
      if (!res.ok) { setErro(data.detail ?? 'Erro ao fazer login'); return false }
      localStorage.setItem(TOKEN_KEY, data.token)
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
      setToken(data.token)
      setUsuario(data.usuario)
      return true
    } catch {
      setErro('Não foi possível conectar ao servidor.')
      return false
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUsuario(null)
  }

  const isAdmin    = usuario?.role === 'admin'
  const isComando  = usuario?.role === 'comando'
  const isOperador = usuario?.role === 'operador'

  return (
    <AuthContext.Provider value={{ token, usuario, login, logout, loading, erro, isAdmin, isComando, isOperador, autenticado: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
