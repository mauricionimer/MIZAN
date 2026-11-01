import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { aplicarCorDaMarca } from '../utils/marca'
import { limparSessaoLocal, textoDoDetalhe, encerrarSessao } from '../api'

const AuthContext = createContext(null)

const TOKEN_KEY  = 'mizan_token'
const USER_KEY   = 'mizan_user'
const BRAND_KEY  = 'mizan_empresa_config'
const PRECISA_2FA_KEY = 'mizan_precisa_2fa'
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
  // Administrador sem a verificação em duas etapas: a tela mostra só a configuração.
  const [precisa2fa, setPrecisa2faEstado] = useState(() => sessionStorage.getItem(PRECISA_2FA_KEY) === '1')
  const setPrecisa2fa = useCallback((sim) => {
    if (sim) sessionStorage.setItem(PRECISA_2FA_KEY, '1'); else sessionStorage.removeItem(PRECISA_2FA_KEY)
    setPrecisa2faEstado(!!sim)
  }, [])
  useEffect(() => {
    const abrir = () => setPrecisa2fa(true)
    window.addEventListener('mizan:2fa-obrigatorio', abrir)
    return () => window.removeEventListener('mizan:2fa-obrigatorio', abrir)
  }, [setPrecisa2fa])

  // Cor da empresa nos botões principais, com a tinta (--on-brand) certa
  // para ela (ver utils/marca.js).
  useEffect(() => {
    aplicarCorDaMarca(empresaConfig?.cor_primaria)
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
      .then(r => {
        // 401 aqui é sessão vencida (30 dias desde o último login com senha):
        // vai para o login, em vez de seguir com um token que logo cai.
        if (r.status === 401) { encerrarSessao(); return null }
        return r.ok ? r.json() : null
      })
      .then(data => {
        if (!data) return
        sessionStorage.setItem(TOKEN_KEY, data.token)
        sessionStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
        setToken(data.token)
        setUsuario(data.usuario)
        setPrecisa2fa(!!data.configurar_2fa)
        _loadEmpresaConfig(data.token)
      })
      .catch(() => {})
  }, [_loadEmpresaConfig, setPrecisa2fa])

  function _entrou(data) {
    sessionStorage.setItem(TOKEN_KEY, data.token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(data.usuario))
    setToken(data.token)
    setUsuario(data.usuario)
    setPrecisa2fa(!!data.configurar_2fa)
    _loadEmpresaConfig(data.token)
  }

  async function login(email, senha) {
    setLoading(true); setErro('')
    try {
      const res = await fetch(`${BASE}/auth/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, senha }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) { setErro(textoDoDetalhe(data.detail, res.status)); return null }
      // Senha certa e 2FA ligado: falta o código do app (segunda etapa, na mesma tela).
      if (data.requer_2fa) return { etapa: '2fa', desafio: data.desafio }
      _entrou(data)
      return data.usuario
    } catch {
      setErro('Não foi possível conectar ao servidor.')
      return null
    } finally {
      setLoading(false)
    }
  }

  // Segunda etapa: o código de 6 dígitos do app (ou um código de recuperação).
  async function confirmarCodigo(desafio, codigo) {
    setLoading(true); setErro('')
    try {
      const res = await fetch(`${BASE}/auth/login/2fa`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ desafio, codigo }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) { setErro(textoDoDetalhe(data.detail, res.status)); return null }
      _entrou(data)
      return data.usuario
    } catch {
      setErro('Não foi possível conectar ao servidor.')
      return null
    } finally {
      setLoading(false)
    }
  }

  // Ao concluir a configuração do 2FA: o token novo vale como sessão com o código.
  function concluir2fa(novoToken) {
    if (novoToken) {
      sessionStorage.setItem(TOKEN_KEY, novoToken)
      setToken(novoToken)
    }
    setPrecisa2fa(false)
  }

  function logout() {
    limparSessaoLocal()        // token, usuário, marca e o que mais for mizan_*
    setToken(null)
    setUsuario(null)
    setEmpresaConfig(null)
    setPrecisa2fa(false)
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
      token, usuario, login, logout, loading, erro, setErro,
      confirmarCodigo, precisa2fa, concluir2fa,
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
