/**
 * Regressão do pedido central do api.js (sessão, erros, parâmetros novos).
 *
 *     node test_api.mjs
 *
 * O api.js usa import.meta.env (Vite): o teste empacota com o esbuild que já
 * vem com o Vite, com fetch, sessionStorage e window falsos.
 */
import { build } from 'esbuild'
import { writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'

let falhas = 0
const ok = (c, t, d = '') => { console.log(`${c ? 'ok  ' : 'FALHA'}  ${t}${d ? '  — ' + d : ''}`); if (!c) falhas++ }

const saida = await build({
  entryPoints: ['src/api.js'], bundle: true, write: false, format: 'esm', platform: 'node',
  define: { 'import.meta.env.VITE_API_URL': '"http://api.teste"' }, logLevel: 'silent',
})
const arquivo = join(tmpdir(), `mizan_api_${process.pid}.mjs`)
writeFileSync(arquivo, saida.outputFiles[0].text)

// ── Navegador falso ──
const guardado = new Map()
globalThis.sessionStorage = {
  get length() { return guardado.size },
  key: i => [...guardado.keys()][i] ?? null,
  getItem: k => (guardado.has(k) ? guardado.get(k) : null),
  setItem: (k, v) => guardado.set(k, String(v)),
  removeItem: k => guardado.delete(k),
}
const eventos = []
globalThis.window = {
  location: { pathname: '/agenda', search: '?x=1', href: '' },
  dispatchEvent: e => eventos.push(e.type),
  addEventListener() {}, removeEventListener() {},
  history: { state: null },
}
let pedidos = []
let resposta = () => ({ status: 200, corpo: {} })
globalThis.fetch = async (url, opcoes = {}) => {
  pedidos.push({ url, ...opcoes })
  const r = resposta(url, opcoes)
  if (r instanceof Error) throw r
  const texto = r.corpo === undefined ? '' : JSON.stringify(r.corpo)
  return {
    status: r.status, ok: r.status >= 200 && r.status < 300,
    json: async () => JSON.parse(texto),
    text: async () => texto,
  }
}

const api = await import(pathToFileURL(arquivo).href)
rmSync(arquivo, { force: true })

// ── detail do FastAPI vira frase ──
ok(api.textoDoDetalhe('Senha incorreta.', 401) === 'Senha incorreta.', 'detail em texto passa como está')
const lista = [
  { type: 'missing', loc: ['body', 'senha'], msg: 'Field required' },
  { type: 'value_error', loc: ['body', 'cpf'], msg: 'Value error, CPF inválido.' },
]
const frase = api.textoDoDetalhe(lista, 422)
ok(frase === 'Falta preencher: senha. CPF inválido.', 'detail em lista vira frase em português', frase)
ok(!/object/i.test(api.textoDoDetalhe([{}], 422)), 'lista estranha não vira [object Object]')
ok(api.textoDoDetalhe(undefined, 404) === 'Não encontrado.', 'sem detail: frase padrão pelo status')

// ── classificarErro ──
const s401 = api.classificarErro(Object.assign(new Error('x'), { status: 401 }))
ok(s401.tipo === 'sessao' && s401.podeTentar === false, '401 é sessão, sem "Tentar novamente"')
ok(api.classificarErro(new TypeError('Failed to fetch')).tipo === 'rede', 'falha de rede')
ok(api.classificarErro(Object.assign(new Error('A carteira tem 90.000 linhas'), { status: 413 })).mensagem.startsWith('A carteira tem'),
  '413 mostra o detail do servidor')

// ── deletarConta(senha): corpo com a senha; 401 = senha errada, não encerra a sessão ──
guardado.set('mizan_token', 'tok'); guardado.set('mizan_user', '{}'); guardado.set('outra_chave', '1')
pedidos = []
resposta = () => ({ status: 401, corpo: { detail: 'Senha incorreta.' } })
let erro = null
try { await api.deletarConta('minhaSenha1') } catch (e) { erro = e }
ok(pedidos[0]?.method === 'DELETE' && pedidos[0]?.url === 'http://api.teste/auth/me', 'DELETE /auth/me')
ok(pedidos[0]?.body === JSON.stringify({ senha: 'minhaSenha1' }), 'manda {senha} no corpo', pedidos[0]?.body)
ok(pedidos[0]?.headers?.Authorization === 'Bearer tok', 'leva o token')
ok(erro?.status === 401 && erro?.message === 'Senha incorreta.', 'erro com status e mensagem do servidor')
ok(guardado.has('mizan_token') && window.location.href === '', 'senha errada não derruba a sessão')

// ── empresaId opcional (COMANDO) ──
pedidos = []
resposta = () => ({ status: 200, corpo: { ok: true } })
await api.confirmarPagamento('123.456.789-00', { valor: 10 }, 'goias')
ok(pedidos[0].url === 'http://api.teste/devedores/123.456.789-00/confirmar-pagamento?empresa_id=goias', 'confirmarPagamento com empresa_id', pedidos[0].url)
ok(pedidos[0].body === JSON.stringify({ valor: 10 }), 'confirmarPagamento mantém o corpo')
await api.confirmarPagamento('123', { valor: 10 })
ok(pedidos[1].url === 'http://api.teste/devedores/123/confirmar-pagamento', 'sem empresa: URL igual à de antes', pedidos[1].url)
await api.feedbackLote(new Blob(['a']), 'outroTok', 'goias')
ok(pedidos[2].url === 'http://api.teste/feedback/lote?empresa_id=goias' && pedidos[2].headers.Authorization === 'Bearer outroTok',
  'feedbackLote com empresa_id e o token recebido', pedidos[2].url)
await api.feedbackLote(new Blob(['a']), 'outroTok')
ok(pedidos[3].url === 'http://api.teste/feedback/lote', 'feedbackLote sem empresa: igual')

// ── Retornos vazios mantidos ──
resposta = () => ({ status: 500, corpo: { detail: 'falhou' } })
ok(JSON.stringify(await api.buscarStatusFeedbacks()) === '{}', 'buscarStatusFeedbacks com erro devolve {}')
ok(Array.isArray(await api.buscarAuditoria()), 'buscarAuditoria com erro devolve []')
ok(await api.buscarAlcance('c1', 3) === null, 'buscarAlcance com erro devolve null')
resposta = () => new TypeError('Failed to fetch')
erro = null
try { await api.buscarStatusFeedbacks() } catch (e) { erro = e }
ok(erro instanceof TypeError, 'falha de rede continua sendo erro')

// ── 413 do /analisar chega com o detail ──
resposta = () => ({ status: 413, corpo: { detail: 'A carteira tem 90.000 linhas e o limite por análise é 50.000.' } })
erro = null
try { await api.analisarCarteira(new Blob(['a'])) } catch (e) { erro = e }
ok(erro?.status === 413 && erro.message.startsWith('A carteira tem 90.000 linhas'), '413 do /analisar com a frase do servidor')

// ── 401 numa rota comum encerra a sessão ──
resposta = () => ({ status: 401, corpo: { detail: 'Token expirado' } })
erro = null
try { await api.listarUsuarios('tok') } catch (e) { erro = e }
ok(erro?.status === 401, 'erro 401 chega ao chamador')
ok(!guardado.has('mizan_token') && !guardado.has('mizan_user'), 'apaga as chaves mizan_*')
ok(guardado.has('outra_chave'), 'não mexe em chave de fora')
ok(eventos.includes('mizan:logout'), "dispara 'mizan:logout'")
ok(window.location.href === '/login?expired=1&de=%2Fagenda%3Fx%3D1', 'vai ao login lembrando a tela', window.location.href)

// ── Lista de funções exportadas: nada sumiu ──
const exigidas = ['analisarCarteira', 'listarCarteiras', 'carregarCarteira', 'confirmarPagamento', 'feedbackLote', 'deletarConta',
  'listarUsuarios', 'gravarPremissas', 'marcaPorEmail', 'agenteControle', 'buscarRankingCompleto', 'traduzirErroRede', 'encerrarSessao']
ok(exigidas.every(n => typeof api[n] === 'function'), 'funções exportadas presentes')

console.log(falhas ? `\n${falhas} FALHA(S)` : '\nTudo certo.')
process.exit(falhas)
