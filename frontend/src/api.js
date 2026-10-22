import { liberarSaida } from './components/protecaoSaida'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function _getToken() {
  return sessionStorage.getItem('mizan_token') || ''
}

// ── Sessão ───────────────────────────────────────────────────────────────────
// Token vencido ou recusado: apaga tudo o que o Mizan guardou na aba, avisa os
// contextos (evento 'mizan:logout'), solta a trava de alterações não salvas
// (senão o navegador pergunta "sair do site?") e volta ao login lembrando a
// tela de onde a pessoa saiu. Vários pedidos com 401 ao mesmo tempo saem uma
// vez só.
// Apaga todas as chaves mizan_* da aba (token, usuário, marca, análise...).
export function limparSessaoLocal() {
  try {
    const chaves = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      if (k && k.startsWith('mizan_')) chaves.push(k)
    }
    chaves.forEach(k => sessionStorage.removeItem(k))
  } catch { /* sem armazenamento */ }
}

let _encerrando = false
export function encerrarSessao() {
  if (_encerrando) return
  _encerrando = true
  limparSessaoLocal()
  window.dispatchEvent(new Event('mizan:logout'))
  liberarSaida()
  const { pathname, search } = window.location
  if (pathname.startsWith('/login')) { _encerrando = false; return }
  window.location.href = `/login?expired=1&de=${encodeURIComponent(pathname + search)}`
  // Se a navegação for interrompida, a próxima expiração ainda funciona.
  setTimeout(() => { _encerrando = false }, 3000)
}

// ── Mensagem de erro ─────────────────────────────────────────────────────────
// O FastAPI devolve `detail` como texto (regra de negócio, já em português) ou
// como lista (validação do corpo, em inglês). A lista vira uma frase curta.
const _PADRAO = {
  400: 'Confira os dados informados.',
  401: 'Sua sessão expirou. Entre de novo.',
  403: 'Você não tem acesso a isto.',
  404: 'Não encontrado.',
  409: 'Não foi possível concluir: os dados mudaram. Atualize a página.',
  413: 'O arquivo é grande demais.',
  422: 'Confira os dados informados.',
  429: 'Muitas tentativas seguidas. Aguarde um pouco e tente de novo.',
}

function _campo(loc) {
  if (!Array.isArray(loc)) return ''
  const partes = loc.filter(p => typeof p === 'string' && !['body', 'query', 'path'].includes(p))
  return partes.length ? partes[partes.length - 1].replace(/_/g, ' ') : ''
}

function _itemValidacao(d) {
  if (typeof d === 'string') return d
  const msg = String(d?.msg || '')
  if (/^Value error, /.test(msg)) return msg.replace(/^Value error, /, '')
  const campo = _campo(d?.loc)
  const tipo = String(d?.type || '')
  if (tipo === 'missing') return campo ? `Falta preencher: ${campo}.` : 'Falta preencher um campo.'
  if (tipo.includes('too_short')) return campo ? `${campo}: curto demais.` : 'Um campo está curto demais.'
  if (tipo.includes('too_long')) return campo ? `${campo}: longo demais.` : 'Um campo está longo demais.'
  if (/email/i.test(msg) || /email/i.test(campo)) return 'E-mail inválido.'
  return campo ? `Confira o campo ${campo}.` : ''
}

export function textoDoDetalhe(detail, status) {
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail)) {
    const frases = [...new Set(detail.map(_itemValidacao).filter(Boolean))]
    return frases.length ? frases.join(' ') : _PADRAO[422]
  }
  if (detail && typeof detail === 'object' && typeof detail.mensagem === 'string') return detail.mensagem
  if (_PADRAO[status]) return _PADRAO[status]
  if (status >= 500) return `O servidor teve um problema (código ${status}).`
  return `Não foi possível concluir (código ${status}).`
}

function _qs(params = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  return qs.toString()
}

/**
 * Pedido único ao servidor. Põe o token, manda JSON (`corpo`) ou arquivo
 * (`form`), trata 401 (encerra a sessão) e transforma o erro em Error com
 * `.status`, `.detail` e a mensagem em português.
 *
 * - `token`: usa este em vez do guardado na aba.
 * - `publico`: não manda token nem encerra sessão (telas antes do login).
 * - `sessao: false`: 401 não encerra a sessão (ex.: senha errada).
 */
// Prazo padrão para pedidos que a tela não controla com o próprio sinal
// (Login.jsx e EsqueciSenha.jsx já criam o AbortController deles). Sem isto,
// uma rede que nunca responde trava o `await fetch` para sempre e a tela
// fica presa sem nenhum jeito de "Tentar de novo".
// `__MIZAN_TEST_PRAZO_MS` existe só para test_api.mjs encurtar a espera.
const _PRAZO_PADRAO_MS = (typeof globalThis !== 'undefined' && globalThis.__MIZAN_TEST_PRAZO_MS) || 25000

function _sinalComPrazo(sinal) {
  if (sinal) return { sinal, limpar: () => {} }
  if (typeof AbortSignal === 'function' && typeof AbortSignal.timeout === 'function') {
    return { sinal: AbortSignal.timeout(_PRAZO_PADRAO_MS), limpar: () => {} }
  }
  if (typeof AbortController === 'function') {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), _PRAZO_PADRAO_MS)
    return { sinal: ctrl.signal, limpar: () => clearTimeout(t) }
  }
  return { sinal: undefined, limpar: () => {} }
}

async function pedir(caminho, { metodo = 'GET', corpo, form, token, query, sinal, publico = false, sessao = true } = {}) {
  const tok = publico ? '' : (token ?? _getToken())
  const headers = {}
  if (tok) headers.Authorization = `Bearer ${tok}`
  let body
  if (form) body = form
  else if (corpo !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(corpo) }
  const qs = query ? _qs(query) : ''
  const url = `${BASE}${caminho}${qs ? (caminho.includes('?') ? '&' : '?') + qs : ''}`
  const { sinal: sinalComPrazo, limpar } = _sinalComPrazo(sinal)
  let res
  try {
    res = await fetch(url, { method: metodo, headers, body, signal: sinalComPrazo })
  } finally {
    limpar()
  }
  if (res.status === 401 && sessao && !publico) encerrarSessao()
  if (!res.ok) {
    const dados = await res.json().catch(() => null)
    const detail = dados?.detail ?? dados?.message
    throw Object.assign(new Error(textoDoDetalhe(detail, res.status)), { status: res.status, detail })
  }
  const texto = await res.text()
  return texto ? JSON.parse(texto) : null
}

// Para as poucas rotas em que a tela prefere um valor vazio a um erro do
// servidor. Falha de rede continua sendo erro.
function _ouVazio(promessa, vazio) {
  return promessa.catch(e => { if (e?.status) return vazio; throw e })
}

const _id = v => encodeURIComponent(v)

// Tipos de erro que a tela distingue (mensagem e se vale "Tentar novamente").
// A mensagem do servidor (validação, regra de negócio, acesso) já vem em
// português e é mostrada como está; só o que é técnico ganha texto próprio.
// O mesmo aviso no banner do App e no erro de servidor acordando (Render grátis).
export const AVISO_CONECTANDO = 'Conectando ao servidor… pode levar até um minuto.'

const _RE_REDE = /failed to fetch|networkerror|load failed|network request failed|fetch failed/i
export function classificarErro(e) {
  if (!e) return { tipo: 'desconhecido', mensagem: 'Algo deu errado. Tente novamente.', podeTentar: true }
  const msg = typeof e === 'string' ? e : (e.message || '')
  const status = e.status ?? (Number((msg.match(/Erro HTTP (\d{3})/) || [])[1]) || null)
  const doServidor = msg && !/^Erro HTTP/.test(msg) ? msg : ''
  if (e.name === 'TypeError' || e.name === 'AbortError' || e.name === 'TimeoutError' || _RE_REDE.test(msg)) {
    return { tipo: 'rede', podeTentar: true,
      mensagem: 'Não foi possível falar com o servidor. Ele pode estar acordando (leva até um minuto) ou a sua conexão caiu. Tente novamente.' }
  }
  if (status === 401) return { tipo: 'sessao', podeTentar: false, mensagem: 'Sua sessão expirou. Entre de novo.' }
  if (status === 502 || status === 503 || status === 504) {
    return { tipo: 'acordando', podeTentar: true, mensagem: AVISO_CONECTANDO }
  }
  if (status >= 500) {
    return { tipo: 'servidor', podeTentar: true,
      mensagem: 'O servidor teve um problema ao processar o pedido. Tente novamente; se continuar, avise o suporte.' }
  }
  if (status === 403) return { tipo: 'autorizacao', podeTentar: false, mensagem: doServidor || 'Você não tem acesso a isto.' }
  if (status === 429) return { tipo: 'limite', podeTentar: true, mensagem: doServidor || _PADRAO[429] }
  if (status === 400 || status === 413 || status === 422) return { tipo: 'validacao', podeTentar: false, mensagem: doServidor || 'Confira os dados informados.' }
  if (status === 404 || status === 409) return { tipo: 'negocio', podeTentar: false, mensagem: doServidor || 'Não foi possível concluir.' }
  return { tipo: 'desconhecido', podeTentar: true, mensagem: doServidor || 'Algo deu errado. Tente novamente.' }
}

// Mantida para quem já usava: devolve só o texto.
export function traduzirErroRede(e) {
  return classificarErro(e).mensagem
}

// ── Carteira e análise ───────────────────────────────────────────────────────
// Carteira acima do limite volta 413 com o detail do servidor ("A carteira tem
// N linhas e o limite por análise é X..."), que chega à tela como está.
export async function analisarCarteira(file, empresaId = null) {
  const fd = new FormData()
  fd.append('file', file)
  if (empresaId) fd.append('empresa_id', empresaId)
  // Sem a fila na resposta: ela vem paginada depois.
  return pedir('/analisar?incluir_ranking=false', { metodo: 'POST', form: fd })
}

export async function listarCarteiras(opcoes = {}) {
  // `meus`: só as que a própria pessoa analisou; `limite`: quantas trazer;
  // `empresaId`: o comando escolhe a empresa.
  const query = {}
  if (opcoes.meus) query.meus = true
  if (opcoes.limite) query.limite = opcoes.limite
  if (opcoes.empresaId) query.empresa_id = opcoes.empresaId
  return pedir('/carteiras', Object.keys(query).length ? { query } : undefined)
}

export async function carregarCarteira(id) {
  // Sem a fila: a tela busca as 50 linhas visíveis em /ranking.
  return pedir(`/carteiras/${id}?incluir_ranking=false`)
}

export async function buscarRecomendacao(cpf) {
  return pedir(`/recomendacao/${_id(cpf)}`)
}

export async function buscarExplicacaoScore(cpf) {
  return pedir(`/predicoes/${_id(cpf)}/explicacao`)
}

export async function buscarPropostas(cpf, despesasMensais = null) {
  const query = despesasMensais != null && despesasMensais !== '' ? { despesas_mensais: despesasMensais } : undefined
  return pedir(`/predicoes/${_id(cpf)}/propostas`, { query })
}

export async function rodarBacktest(file) {
  const fd = new FormData()
  fd.append('file', file)
  return pedir('/backtest', { metodo: 'POST', form: fd })
}

export async function testarDB(params) {
  return pedir('/testar-db', { metodo: 'POST', corpo: params })
}

export async function analisarDB(params) {
  return pedir('/analisar/db?incluir_ranking=false', { metodo: 'POST', corpo: params })
}

export async function listarTabelas(params) {
  return pedir('/listar-tabelas', { metodo: 'POST', corpo: params })
}

// empresaId: obrigatório para o COMANDO (o servidor responde 400 sem ele);
// os outros papéis usam a própria empresa e não precisam passar.
export async function feedbackLote(file, token, empresaId) {
  const fd = new FormData()
  fd.append('file', file)
  return pedir('/feedback/lote', { metodo: 'POST', form: fd, token, query: { empresa_id: empresaId } })
}

// ── Usuários e empresas ──────────────────────────────────────────────────────
export async function listarUsuarios(token) {
  return pedir('/auth/usuarios', { token })
}

export async function registrarUsuario(token, dados) {
  return pedir('/auth/registrar', { metodo: 'POST', token, corpo: dados })
}

export async function listarPermissoesConexao(token, conexaoId) {
  return pedir(`/conexoes/${conexaoId}/permissoes`, { token })
}

export async function concederPermissaoConexao(token, conexaoId, operadorId) {
  return pedir(`/conexoes/${conexaoId}/permissoes/${operadorId}`, { metodo: 'POST', token })
}

export async function revogarPermissaoConexao(token, conexaoId, operadorId) {
  return pedir(`/conexoes/${conexaoId}/permissoes/${operadorId}`, { metodo: 'DELETE', token })
}

export async function toggleUsuarioAtivo(token, id, ativo) {
  return pedir(`/auth/usuarios/${id}/ativo`, { metodo: 'PATCH', token, corpo: { ativo } })
}

// ── Conexões com banco ───────────────────────────────────────────────────────
export async function listarConexoes() {
  if (!_getToken()) return []
  return pedir('/conexoes')
}

export async function salvarConexao(dados) {
  return pedir('/conexoes', { metodo: 'POST', corpo: dados })
}

export async function atualizarConexao(id, dados) {
  return pedir(`/conexoes/${id}`, { metodo: 'PATCH', corpo: dados })
}

export async function deletarConexao(id) {
  return pedir(`/conexoes/${id}`, { metodo: 'DELETE' })
}

export async function sincronizarConexao(id) {
  return pedir(`/conexoes/${id}/sincronizar`, { metodo: 'POST' })
}

// ── Pagamentos ───────────────────────────────────────────────────────────────
export async function buscarPagamentos(carteiraId = null) {
  return pedir('/performance/pagamentos', { query: { carteira_id: carteiraId } })
}

// empresaId: obrigatório para o COMANDO (o servidor responde 400 sem ele);
// os outros papéis usam a própria empresa e não precisam passar.
export async function confirmarPagamento(cpf, dados = {}, empresaId) {
  return pedir(`/devedores/${_id(cpf)}/confirmar-pagamento`, {
    metodo: 'POST', corpo: dados, query: { empresa_id: empresaId },
  })
}

export async function buscarStatusFeedbacks(carteiraId = null) {
  return _ouVazio(pedir('/feedbacks/status', { query: { carteira_id: carteiraId } }), {})
}

// ── Conta ────────────────────────────────────────────────────────────────────
// O servidor pede a senha de novo. Senha errada volta 401 com "Senha
// incorreta.": aqui isso não encerra a sessão.
export async function deletarConta(senha) {
  return pedir('/auth/me', { metodo: 'DELETE', corpo: { senha: senha || '' }, sessao: false })
}

// Devolve { token } novo: as outras sessões abertas caem, esta continua.
export async function alterarSenha(senhaAtual, novaSenha) {
  return pedir('/auth/alterar-senha', { metodo: 'POST', corpo: { senha_atual: senhaAtual, nova_senha: novaSenha } })
}

// ── Contatos ─────────────────────────────────────────────────────────────────
export async function registrarContato(dados) {
  try {
    return await pedir('/contatos', { metodo: 'POST', corpo: dados })
  } catch (e) {
    console.error('[registrarContato] erro', e.status, e.detail)
    throw e
  }
}

export async function listarContatos(cpf) {
  return pedir(`/contatos/${_id(cpf)}`)
}

export async function listarEmpresas(token) {
  return pedir('/empresas', { token })
}

export async function adicionarUsuarioEmpresa(token, empresaId, email) {
  return pedir(`/empresas/${_id(empresaId)}/usuarios`, { metodo: 'POST', token, corpo: { email } })
}

export async function removerUsuarioEmpresa(token, empresaId, usuarioId) {
  return pedir(`/empresas/${_id(empresaId)}/usuarios/${usuarioId}`, { metodo: 'DELETE', token })
}

export async function alterarRoleUsuario(token, id, role) {
  return pedir(`/auth/usuarios/${id}/role`, { metodo: 'PATCH', token, corpo: { role } })
}

// Quem chama decide o que fazer com o 401 (não encerra a sessão aqui).
export async function refreshToken(token) {
  return pedir('/auth/refresh', { metodo: 'POST', token, sessao: false })
}

export async function buscarAuditoria({
  entidade, entidade_id, usuario_email, acao, data_inicio, data_fim, empresa_id, limit = 20, offset = 0,
} = {}) {
  const query = { limit, offset, entidade, entidade_id, usuario_email, acao, data_inicio, data_fim, empresa_id }
  return _ouVazio(pedir('/auditoria', { query }), [])
}

export async function deletarEmpresa(token, empresaId) {
  return pedir(`/empresas/${_id(empresaId)}`, { metodo: 'DELETE', token })
}

export async function getEmpresaConfigPublica(_legado, empresaId) {
  // O primeiro argumento (e-mail) não é mais enviado: o servidor não responde
  // por e-mail, para não revelar quem tem conta. Mantido só por compatibilidade.
  return _ouVazio(pedir('/empresa/config-publica', { publico: true, query: { empresa_id: empresaId } }), null)
}

export async function getEmpresaConfig(token) {
  return _ouVazio(pedir('/empresa/config', { token }), null)
}

export async function putEmpresaConfig(token, dados, empresaIdAlvo) {
  return pedir('/empresa/config', { metodo: 'PUT', token, corpo: dados, query: { empresa_id_alvo: empresaIdAlvo } })
}

export async function uploadEmpresaFoto(token, file, empresaIdAlvo) {
  const fd = new FormData()
  fd.append('file', file)
  return pedir('/empresa/foto', { metodo: 'POST', token, form: fd, query: { empresa_id_alvo: empresaIdAlvo } })
}

export async function getEmpresaDetalhe(token, empresaId) {
  return pedir(`/comando/empresa/${_id(empresaId)}`, { token })
}

// ── Retenção de dados ────────────────────────────────────────────────────
// O prazo em si é gravado por putEmpresaConfig, em extra.retencao — o backend
// valida lá, e recusa prazo fora dos limites na gravação.

export async function diagnosticoBanco(token) {
  return pedir('/comando/diagnostico-banco', { token })
}

export async function buscarRetencao(token, empresaIdAlvo) {
  return pedir('/retencao', { token, query: { empresa_id_alvo: empresaIdAlvo } })
}

export async function executarRetencao(token, empresaIdAlvo) {
  return pedir('/retencao/executar', { metodo: 'POST', token, query: { empresa_id_alvo: empresaIdAlvo } })
}

export async function eliminarTitular(token, cpf, empresaIdAlvo) {
  return pedir('/retencao/titular', { metodo: 'POST', token, corpo: { cpf }, query: { empresa_id_alvo: empresaIdAlvo } })
}

// ── Fila paginada ────────────────────────────────────────────────────────
// A tabela mostra 50 por vez; trazer a carteira inteira custa 581 bytes por
// devedor em JSON. Estas rotas entregam só o que está na tela.

export async function buscarPaginaRanking(carteiraId, params = {}) {
  return pedir(`/carteiras/${_id(carteiraId)}/ranking`, { query: params })
}

// ── F1: divisão da fila ──────────────────────────────────────────────────────
export async function buscarDistribuicao(carteiraId) {
  return pedir(`/carteiras/${_id(carteiraId)}/distribuicao`)
}

export async function distribuirFila(carteiraId, operadores, somenteSemResponsavel) {
  return pedir(`/carteiras/${_id(carteiraId)}/distribuir`, {
    metodo: 'POST', corpo: { operadores, somente_sem_responsavel: !!somenteSemResponsavel },
  })
}

export async function atribuirResponsavel(carteiraId, cpfs, operadorId) {
  return pedir(`/carteiras/${_id(carteiraId)}/responsavel`, {
    metodo: 'POST', corpo: { cpfs, operador_id: operadorId || null },
  })
}

// ── F2: agenda de retornos e promessas ───────────────────────────────────────
export async function listarAgenda(params = {}) {
  return pedir('/agenda', { query: params })
}

export async function listarEquipeAgenda(params = {}) {
  return pedir('/agenda/equipe', { query: params })
}

export async function listarTarefasAdministrativas(params = {}) {
  return pedir('/agenda/administracao/tarefas', { query: params })
}
export async function criarTarefaAdministrativa(dados) {
  return pedir('/agenda/administracao/tarefas', { metodo: 'POST', corpo: dados })
}
export async function mudarTarefaAdministrativa(id, concluir) {
  return pedir(`/agenda/administracao/tarefas/${_id(id)}`, { metodo: 'PATCH', corpo: { concluir } })
}

export async function resumoAgenda(params = {}) {
  return pedir('/agenda/resumo', { query: params })
}

export async function criarAgenda(dados) {
  return pedir('/agenda', { metodo: 'POST', corpo: dados })
}

export async function mudarAgenda(id, acao, extra = {}) {
  return pedir(`/agenda/${_id(id)}`, { metodo: 'PATCH', corpo: { acao, ...extra } })
}

// ── F3: painel do operador ───────────────────────────────────────────────────
export async function buscarPainelOperador(periodo) {
  return pedir('/painel/operador', { query: { periodo } })
}

export async function buscarPainelEquipe(periodo, empresaId) {
  return pedir('/painel/equipe', { query: { periodo, empresa_id: empresaId } })
}

export async function buscarPainelDeUmOperador(operadorId, periodo, empresaId) {
  return pedir(`/painel/operador/${_id(operadorId)}`, { query: { periodo, empresa_id: empresaId } })
}

// ── A1: painel de resultados ─────────────────────────────────────────────────
export async function buscarResultados(periodo, empresaId) {
  return pedir('/resultados', { query: { periodo, empresa_id: empresaId } })
}

// ── A4: acordos em andamento ─────────────────────────────────────────────────
export async function listarAcordos(empresaId) {
  return pedir('/acordos', { query: { empresa_id: empresaId } })
}

export async function mudarParcela(id, acao) {
  return pedir(`/acordos/parcelas/${_id(id)}`, { metodo: 'PATCH', corpo: { acao } })
}

// ── O1: catálogo de ofertas ──────────────────────────────────────────────────
export async function buscarOfertas(empresaId) {
  return pedir('/empresa/ofertas', { query: { empresa_id_alvo: empresaId } })
}

export async function salvarOfertas(dados, empresaId) {
  return pedir('/empresa/ofertas', { metodo: 'PUT', corpo: dados, query: { empresa_id_alvo: empresaId } })
}

// ── O2: simulador de oferta ──────────────────────────────────────────────────
export async function simularOferta(cpf, dados) {
  return pedir(`/predicoes/${_id(cpf)}/simular-oferta`, { metodo: 'POST', corpo: dados })
}

// ── O3: ofertas feitas ───────────────────────────────────────────────────────
export async function registrarOferta(dados) {
  return pedir('/ofertas', { metodo: 'POST', corpo: dados })
}

export async function desfazerOferta(id) {
  return pedir(`/ofertas/${_id(id)}`, { metodo: 'DELETE' })
}

export async function listarOfertasFeitas(cpf) {
  return pedir('/ofertas', { query: { cpf } })
}

// ── F4: roteiros de abordagem ────────────────────────────────────────────────
export async function listarRoteiros(params = {}) {
  return pedir('/roteiros', { query: params })
}

export async function salvarRoteiro(dados, id = null) {
  return pedir(`/roteiros${id ? `/${_id(id)}` : ''}`, { metodo: id ? 'PUT' : 'POST', corpo: dados })
}

export async function apagarRoteiro(id) {
  return pedir(`/roteiros/${_id(id)}`, { metodo: 'DELETE' })
}

export async function buscarAlcance(carteiraId, capacidade) {
  return _ouVazio(pedir(`/carteiras/${_id(carteiraId)}/alcance`, { query: { capacidade: Number(capacidade) || 0 } }), null)
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
export async function treinarModeloEmpresa(token, empresaId, arquivo) {
  const fd = new FormData()
  fd.append('file', arquivo)
  fd.append('empresa_id', empresaId)
  return pedir('/comando/treino', { metodo: 'POST', token, form: fd })
}

export async function treinarComPagamentos(token, empresaId) {
  return pedir('/comando/treino/feedbacks', { metodo: 'POST', token, corpo: { empresa_id: empresaId } })
}

export async function estadoTreino(token, id) {
  return pedir(`/comando/treino/${_id(id)}`, { token })
}

export async function listarModelosEmpresa(token, empresaId) {
  return pedir('/comando/modelos', { token, query: { empresa_id: empresaId } })
}

export async function ativarModeloEmpresa(token, empresaId, versao, forcar = false) {
  return pedir('/comando/modelos/ativar', { metodo: 'POST', token, corpo: { empresa_id: empresaId, versao, forcar } })
}

export async function desativarModeloEmpresa(token, empresaId) {
  return pedir('/comando/modelos/desativar', { metodo: 'POST', token, corpo: { empresa_id: empresaId } })
}


// ── Central de Ajuda ─────────────────────────────────────────────────────────
export async function buscarAjuda(token, pergunta) {
  return pedir('/ajuda/buscar', { metodo: 'POST', token, corpo: { pergunta } })
}

export async function indiceDaAjuda(token) {
  return pedir('/ajuda/indice', { token })
}

export async function entradaDaAjuda(token, id) {
  return pedir(`/ajuda/entradas/${_id(id)}`, { token })
}

export async function estadoDoModelo(token) {
  return pedir('/ajuda/estado-do-modelo', { token })
}


// ── Premissas da empresa ─────────────────────────────────────────────────────
export async function buscarPremissas(token, empresaIdAlvo) {
  return pedir('/empresa/premissas', { token, query: { empresa_id_alvo: empresaIdAlvo } })
}

export async function gravarPremissas(token, valores, empresaIdAlvo) {
  try {
    return await pedir('/empresa/premissas', {
      metodo: 'PUT', token, corpo: { valores }, query: { empresa_id_alvo: empresaIdAlvo },
    })
  } catch (e) {
    // 422 com detail = { mensagem, erros: { chave: texto } }: a tela mostra
    // cada erro no seu campo.
    if (e.status === 422) {
      const d = e.detail && typeof e.detail === 'object' && !Array.isArray(e.detail) ? e.detail : {}
      e.message = d.mensagem || (Array.isArray(e.detail) ? e.message : 'Há valores inválidos.')
      e.erros = d.erros || {}
    }
    throw e
  }
}


// ── Dúvidas ao COMANDO ───────────────────────────────────────────────────────
export async function enviarDuvida(token, { pergunta, tela, buscou }) {
  return pedir('/ajuda/duvidas', { metodo: 'POST', token, corpo: { pergunta, tela, buscou } })
}
export async function minhasDuvidas(token) {
  return pedir('/ajuda/duvidas/minhas', { token })
}
export async function novidadesDeDuvidas(token) {
  return pedir('/ajuda/duvidas/novidades', { token })
}
export async function marcarDuvidasVistas(token) {
  return pedir('/ajuda/duvidas/vistas', { metodo: 'POST', token })
}
export async function duvidasDaEquipe(token) {
  return pedir('/ajuda/duvidas/equipe', { token })
}
export async function listarDuvidasComando(token, { estado = 'aberta', limite = 20, offset = 0 } = {}) {
  return pedir('/comando/duvidas', { token, query: { estado, limite, offset } })
}
export async function responderDuvida(token, id, resposta) {
  return pedir(`/comando/duvidas/${_id(id)}/responder`, { metodo: 'POST', token, corpo: { resposta } })
}
export async function sugerirDuvida(token, id, sugerir, titulo) {
  return pedir(`/comando/duvidas/${_id(id)}/sugerir`, { metodo: 'POST', token, corpo: { sugerir, titulo } })
}
export async function revisarSugestao(token, id, estado) {
  return pedir(`/comando/duvidas/${_id(id)}/sugestao`, { metodo: 'POST', token, corpo: { estado } })
}


// ── Buscas sem resposta (lacunas da Central) ─────────────────────────────────
export async function naoResolveu(token, { pergunta, entrada_id }) {
  return pedir('/ajuda/nao-resolveu', { metodo: 'POST', token, corpo: { pergunta, entrada_id } })
}
export async function listarLacunas(token, { estado = 'pendentes', dias = 90, limite = 50 } = {}) {
  return pedir('/comando/ajuda/lacunas', { token, query: { estado, dias, limite } })
}
export async function tratarLacuna(token, chave, tratada) {
  return pedir('/comando/ajuda/lacunas/tratar', { metodo: 'POST', token, corpo: { chave, tratada } })
}
export async function limparLacunas(token, dias) {
  return pedir('/comando/ajuda/lacunas/limpar', { metodo: 'POST', token, corpo: { dias } })
}


// ── Chaves de API (COMANDO) ──────────────────────────────────────────────────
export async function listarChavesApi(token, empresaId) {
  return pedir('/comando/api-keys', { token, query: { empresa_id: empresaId } })
}
export async function criarChaveApi(token, empresaId, rotulo) {
  return pedir('/comando/api-keys', { metodo: 'POST', token, corpo: { empresa_id: empresaId, rotulo } })
}
export async function revogarChaveApi(token, id) {
  return pedir(`/comando/api-keys/${_id(id)}/revogar`, { metodo: 'POST', token })
}


// ── Marca no login pelo domínio do e-mail ────────────────────────────────────
export async function marcaPorEmail(email, sinal) {
  const r = await _ouVazio(pedir('/empresa/marca', { publico: true, query: { email }, sinal }), null)
  return r ? r.empresa : null
}
export async function verDominios(token, empresaId) {
  return pedir(`/comando/empresas/${_id(empresaId)}/dominios`, { token })
}
export async function gravarDominios(token, empresaId, dominios) {
  return pedir(`/comando/empresas/${_id(empresaId)}/dominios`, { metodo: 'PUT', token, corpo: { dominios } })
}

// Devedores da empresa por nome ou CPF (para ligar um pagamento à carteira certa).
export async function buscarDevedores(q, empresaAlvo) {
  return pedir('/devedores/buscar', { query: { q, empresa_id_alvo: empresaAlvo } })
}

// ── FAQ (perguntas frequentes publicadas pelo COMANDO) ───────────────────────
export async function buscarFaq(token) {
  return pedir('/ajuda/faq', { token })
}
export async function publicarNoFaq(token, id, publicar, titulo) {
  return pedir(`/comando/duvidas/${_id(id)}/faq`, { metodo: 'POST', token, corpo: { publicar, titulo } })
}

// ── Agentes (docs/PLANO_EXECUCAO_AGENTES.md) ─────────────────────────────────
export async function agenteDevedores(busca, empresaId) {
  return pedir('/agente/devedores', { query: { busca, empresa_id: empresaId } })
}

// Pastas de devedores: cada uma traz a cor do semáforo (branco, amarelo, vermelho).
export async function agentePastas({ carteiraId, busca, cor, limit = 24, offset = 0, empresaId } = {}) {
  return pedir('/agente/pastas', { query: { carteira_id: carteiraId, busca, cor, limit, offset, empresa_id: empresaId } })
}

export async function agenteCaso(predicaoId, empresaId) {
  return pedir(`/agente/casos/${_id(predicaoId)}`, { query: { empresa_id: empresaId } })
}

export async function agenteFluxoDevedor(predicaoId) {
  return pedir(`/agente/casos/${_id(predicaoId)}/fluxo`)
}

export async function definirFaseDevedor(predicaoId, fase) {
  return pedir(`/agente/casos/${_id(predicaoId)}/fluxo/fase`, { metodo: 'POST', corpo: { fase } })
}

export async function agenteSimularMensagem(predicaoId, texto, empresaId) {
  return pedir(`/agente/casos/${_id(predicaoId)}/mensagem`, { metodo: 'POST', corpo: { texto, empresa_id: empresaId || null } })
}

export async function agenteCentral(empresaId) {
  return pedir('/agente/central', { query: { empresa_id: empresaId } })
}

export async function agenteSimularPagamento(predicaoId, valor, empresaId) {
  return pedir(`/agente/casos/${_id(predicaoId)}/pagamento`, { metodo: 'POST', corpo: { valor, empresa_id: empresaId || null } })
}

export async function agenteRelogio(empresaId) {
  return pedir('/agente/relogio', { metodo: 'POST', query: { empresa_id: empresaId } })
}

export async function agentePlano(empresaId) {
  return pedir('/agente/plano', { query: { empresa_id: empresaId } })
}

export async function agenteAplicarPlano(empresaId) {
  return pedir('/agente/plano', { metodo: 'POST', query: { empresa_id: empresaId } })
}

export async function agentePoliticas(empresaId) {
  return pedir('/agente/politica', { query: { empresa_id: empresaId } })
}

export async function agenteSalvarPolitica(regras, empresaId) {
  return pedir('/agente/politica', { metodo: 'POST', corpo: { regras, empresa_id: empresaId || null } })
}

export async function agenteAgenda(empresaId) {
  return pedir('/agente/agenda', { query: { empresa_id: empresaId } })
}

export async function agentePassagemRetorno(predicaoId, ajudou, comentario, empresaId) {
  return pedir(`/agente/passagem/${_id(predicaoId)}/retorno`, {
    metodo: 'POST', corpo: { ajudou, comentario: comentario || undefined, empresa_id: empresaId || undefined },
  })
}

export async function agenteAgentes(empresaId) {
  return pedir('/agente/agentes', { query: { empresa_id: empresaId } })
}

export async function agentePerfil(nome, empresaId) {
  return pedir(`/agente/agentes/${_id(nome)}`, { query: { empresa_id: empresaId } })
}

export async function agenteEstacao(empresaId) {
  return pedir('/agente/estacao', { query: { empresa_id: empresaId } })
}

export async function agenteLaboratorio(empresaId) {
  return pedir('/agente/laboratorio', { query: { empresa_id: empresaId } })
}

export async function agenteAnalisar(empresaId) {
  return pedir('/agente/laboratorio/analisar', { metodo: 'POST', query: { empresa_id: empresaId } })
}

export async function agenteDecidirRecomendacao(recId, status, empresaId) {
  return pedir(`/agente/laboratorio/${_id(recId)}/decidir`, { metodo: 'POST', corpo: { status, empresa_id: empresaId || null } })
}

export async function agenteAtribuir(itemId, operadorId, empresaId) {
  return pedir(`/agente/agenda/${_id(itemId)}/atribuir`, { metodo: 'POST', corpo: { operador_id: operadorId, empresa_id: empresaId || null } })
}

export async function agenteControle(predicaoId, acao, empresaId) {
  return pedir(`/agente/casos/${_id(predicaoId)}/controle`, { metodo: 'POST', corpo: { acao, empresa_id: empresaId || null } })
}

// ── Disponibilidade do operador (docs/PLANO_DISPONIBILIDADE_OPERADOR.md) ─────
// { faixas: [{id, usuario_id, dia_semana, hora_inicio, hora_fim, ativo}], operadores: [{id, nome}] }
export async function listarDisponibilidade(token, empresaId) {
  return pedir('/agente/disponibilidade', { token, query: { empresa_id: empresaId } })
}

export async function criarDisponibilidade(token, dados, empresaId) {
  return pedir('/agente/disponibilidade', { metodo: 'POST', token, corpo: { ...dados, empresa_id: empresaId || null } })
}

export async function removerDisponibilidade(token, itemId, empresaId) {
  return pedir(`/agente/disponibilidade/${_id(itemId)}`, { metodo: 'DELETE', token, query: { empresa_id: empresaId } })
}
