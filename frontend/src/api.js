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
  entidade, entidade_id, usuario_email, acao, data_inicio, data_fim, limit = 20, offset = 0,
} = {}) {
  const token = _getToken()
  const params = new URLSearchParams({ limit, offset })
  if (entidade) params.set('entidade', entidade)
  if (entidade_id) params.set('entidade_id', entidade_id)
  if (usuario_email) params.set('usuario_email', usuario_email)
  if (acao) params.set('acao', acao)
  if (data_inicio) params.set('data_inicio', data_inicio)
  if (data_fim) params.set('data_fim', data_fim)
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
    throw new Error(detail)
  }
  return res.json()
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

export async function estadoTreino(token, id) {
  return _jsonOuErro(await fetch(`${BASE}/comando/treino/${encodeURIComponent(id)}`, { headers: _authHeader(token) }))
}

export async function listarModelosEmpresa(token, empresaId) {
  return _jsonOuErro(await fetch(`${BASE}/comando/modelos?empresa_id=${encodeURIComponent(empresaId)}`, { headers: _authHeader(token) }))
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
