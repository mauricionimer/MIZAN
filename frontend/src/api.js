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

// Tipos de erro que a tela distingue (mensagem e se vale "Tentar novamente").
// A mensagem do servidor (validação, regra de negócio, acesso) já vem em
// português e é mostrada como está; só o que é técnico ganha texto próprio.
const _RE_REDE = /failed to fetch|networkerror|load failed|network request failed|fetch failed/i
export function classificarErro(e) {
  if (!e) return { tipo: 'desconhecido', mensagem: 'Algo deu errado. Tente novamente.', podeTentar: true }
  const msg = typeof e === 'string' ? e : (e.message || '')
  const status = e.status ?? (Number((msg.match(/Erro HTTP (\d{3})/) || [])[1]) || null)
  if (e.name === 'TypeError' || _RE_REDE.test(msg)) {
    return { tipo: 'rede', podeTentar: true,
      mensagem: 'Não foi possível falar com o servidor. Ele pode estar acordando (leva até um minuto) ou a sua conexão caiu. Tente novamente.' }
  }
  if (status === 502 || status === 503 || status === 504) {
    return { tipo: 'acordando', podeTentar: true, mensagem: 'O servidor está acordando. Aguarde alguns segundos e tente novamente.' }
  }
  if (status >= 500) {
    return { tipo: 'servidor', podeTentar: true,
      mensagem: 'O servidor teve um problema ao processar o pedido. Tente novamente; se continuar, avise o suporte.' }
  }
  if (status === 403) return { tipo: 'autorizacao', podeTentar: false, mensagem: msg && !/^Erro HTTP/.test(msg) ? msg : 'Você não tem acesso a isto.' }
  if (status === 400 || status === 422) return { tipo: 'validacao', podeTentar: false, mensagem: msg || 'Confira os dados informados.' }
  if (status === 404 || status === 409) return { tipo: 'negocio', podeTentar: false, mensagem: msg || 'Não foi possível concluir.' }
  return { tipo: 'desconhecido', podeTentar: true, mensagem: msg || 'Algo deu errado. Tente novamente.' }
}

// Mantida para quem já usava: devolve só o texto.
export function traduzirErroRede(e) {
  return classificarErro(e).mensagem
}

export async function analisarCarteira(file, empresaId = null) {
  const fd = new FormData()
  fd.append('file', file)
  if (empresaId) fd.append('empresa_id', empresaId)
  const token = _getToken()
  // Sem a fila na resposta: ela vem paginada depois.
  const res = await fetch(`${BASE}/analisar?incluir_ranking=false`, {
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
  // Sem a fila: a tela busca as 50 linhas visíveis em /ranking.
  const res = await fetch(`${BASE}/carteiras/${id}?incluir_ranking=false`, {
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

export async function buscarExplicacaoScore(cpf) {
  const token = _getToken()
  const res = await fetch(`${BASE}/predicoes/${encodeURIComponent(cpf)}/explicacao`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function buscarPropostas(cpf, despesasMensais = null) {
  const token = _getToken()
  const qs = despesasMensais != null && despesasMensais !== ''
    ? `?despesas_mensais=${encodeURIComponent(despesasMensais)}`
    : ''
  const res = await fetch(`${BASE}/predicoes/${encodeURIComponent(cpf)}/propostas${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function rodarBacktest(file) {
  const token = _getToken()
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/backtest`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
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
  const res = await fetch(`${BASE}/analisar/db?incluir_ranking=false`, {
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

export async function buscarPagamentos(carteiraId = null) {
  const token = _getToken()
  const url = carteiraId
    ? `${BASE}/performance/pagamentos?carteira_id=${encodeURIComponent(carteiraId)}`
    : `${BASE}/performance/pagamentos`
  const res = await fetch(url, {
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

export async function buscarStatusFeedbacks(carteiraId = null) {
  const token = _getToken()
  const url = carteiraId
    ? `${BASE}/feedbacks/status?carteira_id=${encodeURIComponent(carteiraId)}`
    : `${BASE}/feedbacks/status`
  const res = await fetch(url, {
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

export async function buscarAuditoria({
  entidade, entidade_id, usuario_email, acao, data_inicio, data_fim, empresa_id, limit = 20, offset = 0,
} = {}) {
  const token = _getToken()
  const params = new URLSearchParams({ limit, offset })
  if (entidade) params.set('entidade', entidade)
  if (entidade_id) params.set('entidade_id', entidade_id)
  if (usuario_email) params.set('usuario_email', usuario_email)
  if (acao) params.set('acao', acao)
  if (data_inicio) params.set('data_inicio', data_inicio)
  if (data_fim) params.set('data_fim', data_fim)
  if (empresa_id) params.set('empresa_id', empresa_id)
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

export async function getEmpresaConfigPublica(_legado, empresaId) {
  // O primeiro argumento (e-mail) não é mais enviado: o servidor não responde
  // por e-mail, para não revelar quem tem conta. Mantido só por compatibilidade.
  const qs = empresaId ? `?empresa_id=${encodeURIComponent(empresaId)}` : ''
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

// ── Retenção de dados ────────────────────────────────────────────────────
// O prazo em si é gravado por putEmpresaConfig, em extra.retencao — o backend
// valida lá, e recusa prazo fora dos limites na gravação.

export async function diagnosticoBanco(token) {
  const res = await fetch(`${BASE}/comando/diagnostico-banco`, { headers: _authHeader(token) })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function buscarRetencao(token, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/retencao${qs}`, { headers: _authHeader(token) })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function executarRetencao(token, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/retencao/executar${qs}`, {
    method: 'POST', headers: _authHeader(token),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

export async function eliminarTitular(token, cpf, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/retencao/titular${qs}`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ cpf }),
  })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

// ── Fila paginada ────────────────────────────────────────────────────────
// A tabela mostra 50 por vez; trazer a carteira inteira custa 581 bytes por
// devedor em JSON. Estas rotas entregam só o que está na tela.

export async function buscarPaginaRanking(carteiraId, params = {}) {
  const token = _getToken()
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  }
  const res = await fetch(`${BASE}/carteiras/${encodeURIComponent(carteiraId)}/ranking?${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw Object.assign(new Error(detail), { status: res.status })
  }
  return res.json()
}

// ── F1: divisão da fila ──────────────────────────────────────────────────────
async function _jsonOuErroFila(res) {
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    const msg = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(d => String(d.msg || '').replace(/^Value error, /, '')).filter(Boolean).join(' ') || 'Dados inválidos.'
      : 'Dados inválidos.'
    throw Object.assign(new Error(msg), { status: res.status })
  }
  return res.json()
}

export async function buscarDistribuicao(carteiraId) {
  const res = await fetch(`${BASE}/carteiras/${encodeURIComponent(carteiraId)}/distribuicao`, {
    headers: { Authorization: `Bearer ${_getToken()}` },
  })
  return _jsonOuErroFila(res)
}

export async function distribuirFila(carteiraId, operadores, somenteSemResponsavel) {
  const res = await fetch(`${BASE}/carteiras/${encodeURIComponent(carteiraId)}/distribuir`, {
    method: 'POST', headers: _authHeader(_getToken()),
    body: JSON.stringify({ operadores, somente_sem_responsavel: !!somenteSemResponsavel }),
  })
  return _jsonOuErroFila(res)
}

export async function atribuirResponsavel(carteiraId, cpfs, operadorId) {
  const res = await fetch(`${BASE}/carteiras/${encodeURIComponent(carteiraId)}/responsavel`, {
    method: 'POST', headers: _authHeader(_getToken()),
    body: JSON.stringify({ cpfs, operador_id: operadorId || null }),
  })
  return _jsonOuErroFila(res)
}

// ── F2: agenda de retornos e promessas ───────────────────────────────────────
function _qs(params = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  return qs.toString()
}

export async function listarAgenda(params = {}) {
  const res = await fetch(`${BASE}/agenda?${_qs(params)}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function listarEquipeAgenda(params = {}) {
  const res = await fetch(`${BASE}/agenda/equipe?${_qs(params)}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function resumoAgenda(params = {}) {
  const res = await fetch(`${BASE}/agenda/resumo?${_qs(params)}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function criarAgenda(dados) {
  const res = await fetch(`${BASE}/agenda`, { method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify(dados) })
  return _jsonOuErroFila(res)
}

export async function mudarAgenda(id, acao, extra = {}) {
  const res = await fetch(`${BASE}/agenda/${encodeURIComponent(id)}`, {
    method: 'PATCH', headers: _authHeader(_getToken()), body: JSON.stringify({ acao, ...extra }),
  })
  return _jsonOuErroFila(res)
}

// ── F3: painel do operador ───────────────────────────────────────────────────
export async function buscarPainelOperador(periodo) {
  const res = await fetch(`${BASE}/painel/operador?${_qs({ periodo })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function buscarPainelEquipe(periodo, empresaId) {
  const res = await fetch(`${BASE}/painel/equipe?${_qs({ periodo, empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function buscarPainelDeUmOperador(operadorId, periodo, empresaId) {
  const res = await fetch(`${BASE}/painel/operador/${encodeURIComponent(operadorId)}?${_qs({ periodo, empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

// ── A1: painel de resultados ─────────────────────────────────────────────────
export async function buscarResultados(periodo, empresaId) {
  const res = await fetch(`${BASE}/resultados?${_qs({ periodo, empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

// ── A4: acordos em andamento ─────────────────────────────────────────────────
export async function listarAcordos(empresaId) {
  const res = await fetch(`${BASE}/acordos?${_qs({ empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function mudarParcela(id, acao) {
  const res = await fetch(`${BASE}/acordos/parcelas/${encodeURIComponent(id)}`, {
    method: 'PATCH', headers: _authHeader(_getToken()), body: JSON.stringify({ acao }),
  })
  return _jsonOuErroFila(res)
}

// ── O1: catálogo de ofertas ──────────────────────────────────────────────────
export async function buscarOfertas(empresaId) {
  const res = await fetch(`${BASE}/empresa/ofertas?${_qs({ empresa_id_alvo: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function salvarOfertas(dados, empresaId) {
  const res = await fetch(`${BASE}/empresa/ofertas?${_qs({ empresa_id_alvo: empresaId })}`, {
    method: 'PUT', headers: _authHeader(_getToken()), body: JSON.stringify(dados),
  })
  return _jsonOuErroFila(res)
}

// ── O2: simulador de oferta ──────────────────────────────────────────────────
export async function simularOferta(cpf, dados) {
  const res = await fetch(`${BASE}/predicoes/${encodeURIComponent(cpf)}/simular-oferta`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify(dados),
  })
  return _jsonOuErroFila(res)
}

// ── O3: ofertas feitas ───────────────────────────────────────────────────────
export async function registrarOferta(dados) {
  const res = await fetch(`${BASE}/ofertas`, { method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify(dados) })
  return _jsonOuErroFila(res)
}

export async function desfazerOferta(id) {
  const res = await fetch(`${BASE}/ofertas/${encodeURIComponent(id)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function listarOfertasFeitas(cpf) {
  const res = await fetch(`${BASE}/ofertas?${_qs({ cpf })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

// ── F4: roteiros de abordagem ────────────────────────────────────────────────
export async function listarRoteiros(params = {}) {
  const res = await fetch(`${BASE}/roteiros?${_qs(params)}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function salvarRoteiro(dados, id = null) {
  const res = await fetch(`${BASE}/roteiros${id ? `/${encodeURIComponent(id)}` : ''}`, {
    method: id ? 'PUT' : 'POST', headers: _authHeader(_getToken()), body: JSON.stringify(dados),
  })
  return _jsonOuErroFila(res)
}

export async function apagarRoteiro(id) {
  const res = await fetch(`${BASE}/roteiros/${encodeURIComponent(id)}`, {
    method: 'DELETE', headers: { Authorization: `Bearer ${_getToken()}` },
  })
  return _jsonOuErroFila(res)
}

export async function buscarAlcance(carteiraId, capacidade) {
  const token = _getToken()
  const res = await fetch(
    `${BASE}/carteiras/${encodeURIComponent(carteiraId)}/alcance?capacidade=${Number(capacidade) || 0}`,
    { headers: { Authorization: `Bearer ${token}` } })
  _handle401(res)
  if (!res.ok) return null
  return res.json()
}

// Exportações e PDF precisam da fila inteira. Vem em páginas grandes para não
// depender de uma resposta única gigante, e o chamador acompanha o progresso.
export async function buscarRankingCompleto(carteiraId, aoProgredir) {
  const PASSO = 500
  const tudo = []
  let total = null
  for (let offset = 0; ; offset += PASSO) {
    const p = await buscarPaginaRanking(carteiraId, { offset, limit: PASSO })
    tudo.push(...p.itens)
    total = p.filtrado ?? p.total
    aoProgredir?.(tudo.length, total)
    if (tudo.length >= total || p.itens.length === 0) break
  }
  return tudo
}


// ── Modelo por empresa (COMANDO) ─────────────────────────────────────────────
async function _jsonOuErro(res) {
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    const e = new Error(typeof detail === 'string' ? detail : `Erro HTTP ${res.status}`)
    e.status = res.status
    throw e
  }
  return res.json()
}

export async function treinarModeloEmpresa(token, empresaId, arquivo) {
  const fd = new FormData()
  fd.append('file', arquivo)
  fd.append('empresa_id', empresaId)
  const res = await fetch(`${BASE}/comando/treino`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
  })
  return _jsonOuErro(res)
}

export async function treinarComPagamentos(token, empresaId) {
  return _jsonOuErro(await fetch(`${BASE}/comando/treino/feedbacks`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ empresa_id: empresaId }),
  }))
}

export async function estadoTreino(token, id) {
  return _jsonOuErro(await fetch(`${BASE}/comando/treino/${encodeURIComponent(id)}`, { headers: _authHeader(token) }))
}

export async function listarModelosEmpresa(token, empresaId) {
  const qs = empresaId ? `?empresa_id=${encodeURIComponent(empresaId)}` : ''
  return _jsonOuErro(await fetch(`${BASE}/comando/modelos${qs}`, { headers: _authHeader(token) }))
}

export async function ativarModeloEmpresa(token, empresaId, versao, forcar = false) {
  return _jsonOuErro(await fetch(`${BASE}/comando/modelos/ativar`, {
    method: 'POST', headers: _authHeader(token),
    body: JSON.stringify({ empresa_id: empresaId, versao, forcar }),
  }))
}

export async function desativarModeloEmpresa(token, empresaId) {
  return _jsonOuErro(await fetch(`${BASE}/comando/modelos/desativar`, {
    method: 'POST', headers: _authHeader(token),
    body: JSON.stringify({ empresa_id: empresaId }),
  }))
}


// ── Central de Ajuda ─────────────────────────────────────────────────────────
export async function buscarAjuda(token, pergunta) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/buscar`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ pergunta }),
  }))
}

export async function indiceDaAjuda(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/indice`, { headers: _authHeader(token) }))
}

export async function entradaDaAjuda(token, id) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/entradas/${encodeURIComponent(id)}`, { headers: _authHeader(token) }))
}

export async function estadoDoModelo(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/estado-do-modelo`, { headers: _authHeader(token) }))
}


// ── Premissas da empresa ─────────────────────────────────────────────────────
export async function buscarPremissas(token, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  return _jsonOuErro(await fetch(`${BASE}/empresa/premissas${qs}`, { headers: _authHeader(token) }))
}

export async function gravarPremissas(token, valores, empresaIdAlvo) {
  const qs = empresaIdAlvo ? `?empresa_id_alvo=${encodeURIComponent(empresaIdAlvo)}` : ''
  const res = await fetch(`${BASE}/empresa/premissas${qs}`, {
    method: 'PUT', headers: _authHeader(token), body: JSON.stringify({ valores }),
  })
  if (res.status === 422) {
    // detail = { mensagem, erros: { chave: texto } }: a tela mostra cada erro no seu campo
    const { detail } = await res.json().catch(() => ({}))
    const e = new Error(detail?.mensagem || 'Há valores inválidos.')
    e.erros = detail?.erros || {}
    throw e
  }
  return _jsonOuErro(res)
}


// ── Dúvidas ao COMANDO ───────────────────────────────────────────────────────
export async function enviarDuvida(token, { pergunta, tela, buscou }) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/duvidas`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ pergunta, tela, buscou }),
  }))
}
export async function minhasDuvidas(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/duvidas/minhas`, { headers: _authHeader(token) }))
}
export async function novidadesDeDuvidas(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/duvidas/novidades`, { headers: _authHeader(token) }))
}
export async function marcarDuvidasVistas(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/duvidas/vistas`, { method: 'POST', headers: _authHeader(token) }))
}
export async function duvidasDaEquipe(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/duvidas/equipe`, { headers: _authHeader(token) }))
}
export async function listarDuvidasComando(token, { estado = 'aberta', limite = 20, offset = 0 } = {}) {
  const qs = new URLSearchParams({ estado, limite, offset })
  return _jsonOuErro(await fetch(`${BASE}/comando/duvidas?${qs}`, { headers: _authHeader(token) }))
}
export async function responderDuvida(token, id, resposta) {
  return _jsonOuErro(await fetch(`${BASE}/comando/duvidas/${encodeURIComponent(id)}/responder`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ resposta }),
  }))
}
export async function sugerirDuvida(token, id, sugerir, titulo) {
  return _jsonOuErro(await fetch(`${BASE}/comando/duvidas/${encodeURIComponent(id)}/sugerir`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ sugerir, titulo }),
  }))
}
export async function revisarSugestao(token, id, estado) {
  return _jsonOuErro(await fetch(`${BASE}/comando/duvidas/${encodeURIComponent(id)}/sugestao`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ estado }),
  }))
}


// ── Buscas sem resposta (lacunas da Central) ─────────────────────────────────
export async function naoResolveu(token, { pergunta, entrada_id }) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/nao-resolveu`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ pergunta, entrada_id }),
  }))
}
export async function listarLacunas(token, { estado = 'pendentes', dias = 90, limite = 50 } = {}) {
  const qs = new URLSearchParams({ estado, dias, limite })
  return _jsonOuErro(await fetch(`${BASE}/comando/ajuda/lacunas?${qs}`, { headers: _authHeader(token) }))
}
export async function tratarLacuna(token, chave, tratada) {
  return _jsonOuErro(await fetch(`${BASE}/comando/ajuda/lacunas/tratar`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ chave, tratada }),
  }))
}
export async function limparLacunas(token, dias) {
  return _jsonOuErro(await fetch(`${BASE}/comando/ajuda/lacunas/limpar`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ dias }),
  }))
}


// ── Chaves de API (COMANDO) ──────────────────────────────────────────────────
export async function listarChavesApi(token, empresaId) {
  const qs = empresaId ? `?empresa_id=${encodeURIComponent(empresaId)}` : ''
  return _jsonOuErro(await fetch(`${BASE}/comando/api-keys${qs}`, { headers: _authHeader(token) }))
}
export async function criarChaveApi(token, empresaId, rotulo) {
  return _jsonOuErro(await fetch(`${BASE}/comando/api-keys`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ empresa_id: empresaId, rotulo }),
  }))
}
export async function revogarChaveApi(token, id) {
  return _jsonOuErro(await fetch(`${BASE}/comando/api-keys/${encodeURIComponent(id)}/revogar`, {
    method: 'POST', headers: _authHeader(token),
  }))
}


// ── Marca no login pelo domínio do e-mail ────────────────────────────────────
export async function marcaPorEmail(email, sinal) {
  const res = await fetch(`${BASE}/empresa/marca?email=${encodeURIComponent(email)}`, { signal: sinal })
  if (!res.ok) return null
  return (await res.json()).empresa
}
export async function verDominios(token, empresaId) {
  return _jsonOuErro(await fetch(`${BASE}/comando/empresas/${encodeURIComponent(empresaId)}/dominios`, { headers: _authHeader(token) }))
}
export async function gravarDominios(token, empresaId, dominios) {
  return _jsonOuErro(await fetch(`${BASE}/comando/empresas/${encodeURIComponent(empresaId)}/dominios`, {
    method: 'PUT', headers: _authHeader(token), body: JSON.stringify({ dominios }),
  }))
}

// Devedores da empresa por nome ou CPF (para ligar um pagamento à carteira certa).
export async function buscarDevedores(q, empresaAlvo) {
  const token = _getToken()
  const qs = new URLSearchParams({ q })
  if (empresaAlvo) qs.set('empresa_id_alvo', empresaAlvo)
  const res = await fetch(`${BASE}/devedores/buscar?${qs}`, { headers: { Authorization: `Bearer ${token}` } })
  _handle401(res)
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

// ── FAQ (perguntas frequentes publicadas pelo COMANDO) ───────────────────────
export async function buscarFaq(token) {
  return _jsonOuErro(await fetch(`${BASE}/ajuda/faq`, { headers: _authHeader(token) }))
}
export async function publicarNoFaq(token, id, publicar, titulo) {
  return _jsonOuErro(await fetch(`${BASE}/comando/duvidas/${encodeURIComponent(id)}/faq`, {
    method: 'POST', headers: _authHeader(token), body: JSON.stringify({ publicar, titulo }),
  }))
}

// ── Agentes (docs/PLANO_EXECUCAO_AGENTES.md) ─────────────────────────────────
export async function agenteDevedores(busca, empresaId) {
  const res = await fetch(`${BASE}/agente/devedores?${_qs({ busca, empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function agenteCaso(predicaoId, empresaId) {
  const res = await fetch(`${BASE}/agente/casos/${encodeURIComponent(predicaoId)}?${_qs({ empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function agenteSimularMensagem(predicaoId, texto, empresaId) {
  const res = await fetch(`${BASE}/agente/casos/${encodeURIComponent(predicaoId)}/mensagem`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ texto, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}

export async function agenteCentral(empresaId) {
  const res = await fetch(`${BASE}/agente/central?${_qs({ empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function agenteSimularPagamento(predicaoId, valor, empresaId) {
  const res = await fetch(`${BASE}/agente/casos/${encodeURIComponent(predicaoId)}/pagamento`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ valor, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}

export async function agenteRelogio(empresaId) {
  const res = await fetch(`${BASE}/agente/relogio?${_qs({ empresa_id: empresaId })}`, {
    method: 'POST', headers: _authHeader(_getToken()),
  })
  return _jsonOuErroFila(res)
}

export async function agentePlano(empresaId) {
  const res = await fetch(`${BASE}/agente/plano?${_qs({ empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function agenteAplicarPlano(empresaId) {
  const res = await fetch(`${BASE}/agente/plano?${_qs({ empresa_id: empresaId })}`, { method: 'POST', headers: _authHeader(_getToken()) })
  return _jsonOuErroFila(res)
}

export async function agentePoliticas(empresaId) {
  const res = await fetch(`${BASE}/agente/politica?${_qs({ empresa_id: empresaId })}`, { headers: { Authorization: `Bearer ${_getToken()}` } })
  return _jsonOuErroFila(res)
}

export async function agenteSalvarPolitica(regras, empresaId) {
  const res = await fetch(`${BASE}/agente/politica`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ regras, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}

export async function agenteAgenda(empresaId) {
  const res = await fetch(`${BASE}/agente/agenda?${_qs({ empresa_id: empresaId })}`, { headers: _authHeader(_getToken()) })
  return _jsonOuErroFila(res)
}

export async function agenteEstacao(empresaId) {
  const res = await fetch(`${BASE}/agente/estacao?${_qs({ empresa_id: empresaId })}`, { headers: _authHeader(_getToken()) })
  return _jsonOuErroFila(res)
}

export async function agenteLaboratorio(empresaId) {
  const res = await fetch(`${BASE}/agente/laboratorio?${_qs({ empresa_id: empresaId })}`, { headers: _authHeader(_getToken()) })
  return _jsonOuErroFila(res)
}

export async function agenteAnalisar(empresaId) {
  const res = await fetch(`${BASE}/agente/laboratorio/analisar?${_qs({ empresa_id: empresaId })}`, {
    method: 'POST', headers: _authHeader(_getToken()),
  })
  return _jsonOuErroFila(res)
}

export async function agenteDecidirRecomendacao(recId, status, empresaId) {
  const res = await fetch(`${BASE}/agente/laboratorio/${encodeURIComponent(recId)}/decidir`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ status, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}

export async function agenteAtribuir(itemId, operadorId, empresaId) {
  const res = await fetch(`${BASE}/agente/agenda/${encodeURIComponent(itemId)}/atribuir`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ operador_id: operadorId, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}

export async function agenteControle(predicaoId, acao, empresaId) {
  const res = await fetch(`${BASE}/agente/casos/${encodeURIComponent(predicaoId)}/controle`, {
    method: 'POST', headers: _authHeader(_getToken()), body: JSON.stringify({ acao, empresa_id: empresaId || null }),
  })
  return _jsonOuErroFila(res)
}
