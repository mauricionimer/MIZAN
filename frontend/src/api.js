const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function _getToken() {
  return localStorage.getItem('mizan_token') || ''
}

export async function analisarCarteira(file) {
  const fd = new FormData()
  fd.append('file', file)
  const token = _getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE}/analisar`, { method: 'POST', headers, body: fd })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function listarCarteiras() {
  const token = _getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE}/carteiras`, { headers })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function carregarCarteira(id) {
  const res = await fetch(`${BASE}/carteiras/${id}`)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function buscarRecomendacao(cpf) {
  const res = await fetch(`${BASE}/recomendacao/${encodeURIComponent(cpf)}`)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function testarDB(params) {
  const res = await fetch(`${BASE}/testar-db`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
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
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

const _authHeader = (token) => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` })

export async function getDBSyncConfig(token) {
  const res = await fetch(`${BASE}/admin/db-sync/config`, { headers: _authHeader(token) })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function saveDBSyncConfig(token, params) {
  const res = await fetch(`${BASE}/admin/db-sync/config`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify(params),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function executarDBSync(token) {
  const res = await fetch(`${BASE}/admin/db-sync/executar`, {
    method: 'POST', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

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
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
  return res.json()
}

export async function salvarConexao(dados) {
  const token = _getToken()
  const res = await fetch(`${BASE}/conexoes`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify(dados),
  })
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
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE}/performance/pagamentos`, { headers })
  if (!res.ok) throw new Error(`Erro HTTP ${res.status}`)
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
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
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
