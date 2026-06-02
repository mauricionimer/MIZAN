const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function _getToken() {
  return sessionStorage.getItem('mizan_token') || ''
}

function _handle401(res) {
  if (res.status === 401) {
    sessionStorage.removeItem('mizan_token')
    sessionStorage.removeItem('mizan_user')
    window.location.href = '/login?expired=1'
  }
}

export function traduzirErroRede(e) {
  if (e?.message === 'Failed to fetch' || e?.message?.includes('Failed to fetch')) {
    return 'Servidor temporariamente indisponível. Aguarde 30 segundos e tente novamente.'
  }
  return e?.message || 'Erro desconhecido.'
}

export async function analisarCarteira(file, empresaId = null) {
  const fd = new FormData()
  fd.append('file', file)
  if (empresaId) fd.append('empresa_id', empresaId)
  const token = _getToken()
  const res = await fetch(`${BASE}/analisar`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function listarCarteiras() {
  const token = _getToken()
  const res = await fetch(`${BASE}/carteiras`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  _handle401(res)
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function carregarCarteira(id) {
  const token = _getToken()
  const res = await fetch(`${BASE}/carteiras/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function buscarRecomendacao(cpf) {
  const token = _getToken()
  const res = await fetch(`${BASE}/recomendacao/${encodeURIComponent(cpf)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function testarDB(params) {
  const token = _getToken()
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  const res = await fetch(`${BASE}/testar-db`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function analisarDB(params) {
  const token = _getToken()
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  const res = await fetch(`${BASE}/analisar/db`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function listarTabelas(params) {
  const token = _getToken()
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  const res = await fetch(`${BASE}/listar-tabelas`, {
    method: 'POST', headers, body: JSON.stringify(params),
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function feedbackLote(file, token) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/feedback/lote`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

const _authHeader = (token) => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` })


export async function listarUsuarios(token) {
  const res = await fetch(`${BASE}/auth/usuarios`, { headers: _authHeader(token) })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function registrarUsuario(token, dados) {
  const res = await fetch(`${BASE}/auth/registrar`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify(dados),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function listarPermissoesConexao(token, conexaoId) {
  const res = await fetch(`${BASE}/conexoes/${conexaoId}/permissoes`, { headers: _authHeader(token) })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function concederPermissaoConexao(token, conexaoId, operadorId) {
  const res = await fetch(`${BASE}/conexoes/${conexaoId}/permissoes/${operadorId}`, {
    method: 'POST', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function revogarPermissaoConexao(token, conexaoId, operadorId) {
  const res = await fetch(`${BASE}/conexoes/${conexaoId}/permissoes/${operadorId}`, {
    method: 'DELETE', headers: _authHeader(token),
  })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function toggleUsuarioAtivo(token, id, ativo) {
  const res = await fetch(`${BASE}/auth/usuarios/${id}/ativo`, {
    method: 'PATCH', headers: _authHeader(token), body: JSON.stringify({ ativo }),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function listarConexoes() {
  const token = _getToken()
  if (!token) return []
  const res = await fetch(`${BASE}/conexoes`, { headers: _authHeader(token) })
  _handle401(res)
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function salvarConexao(dados) {
  const token = _getToken()
  const res = await fetch(`${BASE}/conexoes`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify(dados),
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function atualizarConexao(id, dados) {
  const token = _getToken()
  const res = await fetch(`${BASE}/conexoes/${id}`, {
    method: 'PATCH', headers: _authHeader(token), body: JSON.stringify(dados),
  })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function deletarConexao(id) {
  const token = _getToken()
  const res = await fetch(`${BASE}/conexoes/${id}`, {
    method: 'DELETE', headers: _authHeader(token),
  })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function buscarPagamentos() {
  const token = _getToken()
  const res = await fetch(`${BASE}/performance/pagamentos`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  _handle401(res)
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function confirmarPagamento(cpf, dados = {}) {
  const token = _getToken()
  const res = await fetch(`${BASE}/devedores/${encodeURIComponent(cpf)}/confirmar-pagamento`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(dados),
  })
  _handle401(res)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || `Erro HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

export async function buscarStatusFeedbacks() {
  const token = _getToken()
  const res = await fetch(`${BASE}/feedbacks/status`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  _handle401(res)
  if (!res.ok) return {}
  return res.json()
}

export async function sincronizarConexao(id) {
  const token = _getToken()
  const res = await fetch(`${BASE}/conexoes/${id}/sincronizar`, {
    method: 'POST', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function deletarConta() {
  const token = _getToken()
  const res = await fetch(`${BASE}/auth/me`, {
    method: 'DELETE', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function registrarContato(dados) {
  const token = _getToken()
  const res = await fetch(`${BASE}/contatos`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify(dados),
  })
  _handle401(res)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || body?.message || `Erro HTTP ${res.status}`
    console.error('[registrarContato] erro', res.status, body)
    throw new Error(detail)
  }
  return res.json()
}

export async function listarContatos(cpf) {
  const token = _getToken()
  const res = await fetch(`${BASE}/contatos/${encodeURIComponent(cpf)}`, { headers: _authHeader(token) })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function listarEmpresas(token) {
  const res = await fetch(`${BASE}/empresas`, { headers: _authHeader(token) })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function adicionarUsuarioEmpresa(token, empresaId, email) {
  const res = await fetch(`${BASE}/empresas/${encodeURIComponent(empresaId)}/usuarios`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ email }),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function removerUsuarioEmpresa(token, empresaId, usuarioId) {
  const res = await fetch(`${BASE}/empresas/${encodeURIComponent(empresaId)}/usuarios/${usuarioId}`, {
    method: 'DELETE', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function alterarRoleUsuario(token, id, role) {
  const res = await fetch(`${BASE}/auth/usuarios/${id}/role`, {
    method: 'PATCH', headers: _authHeader(token), body: JSON.stringify({ role }),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function refreshToken(token) {
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST', headers: _authHeader(token),
  })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function buscarAuditoria({ entidade, entidade_id, limit = 20 } = {}) {
  const token = _getToken()
  const params = new URLSearchParams({ limit })
  if (entidade) params.set('entidade', entidade)
  if (entidade_id) params.set('entidade_id', entidade_id)
  const res = await fetch(`${BASE}/auditoria?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  _handle401(res)
  if (!res.ok) return []
  return res.json()
}

export async function deletarEmpresa(token, empresaId) {
  const res = await fetch(`${BASE}/empresas/${encodeURIComponent(empresaId)}`, {
    method: 'DELETE', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function getEmpresaConfigPublica(email, empresaId) {
  const p = new URLSearchParams()
  if (email) p.set('email', email)
  if (empresaId) p.set('empresa_id', empresaId)
  const qs = p.toString() ? `?${p}` : ''
  const res = await fetch(`${BASE}/empresa/config-publica${qs}`)
  if (!res.ok) return null
  return res.json()
}

export async function getEmpresaConfig(token) {
  const res = await fetch(`${BASE}/empresa/config`, { headers: _authHeader(token) })
  if (!res.ok) return null
  return res.json()
}

export async function putEmpresaConfig(token, dados, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/empresa/config${qs}`, {
    method: 'PUT', headers: _authHeader(token), body: JSON.stringify(dados),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function uploadEmpresaFoto(token, file, empresaIdAlvo) {
  const fd = new FormData()
  fd.append('file', file)
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/empresa/foto${qs}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function getEmpresaDetalhe(token, empresaId) {
  const res = await fetch(`${BASE}/comando/empresa/${encodeURIComponent(empresaId)}`, {
    headers: _authHeader(token),
  })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}
