/**
 * Regressões da auditoria de UX (perfil Admin). Cada teste conta o sintoma original.
 * Leem o código-fonte: o que quebrava só aparecia no navegador (histórico, aviso, trava).
 * Rodar: node --test tests/ux-auditoria.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const fonte = (arquivo) => readFileSync(new URL(`../src/${arquivo}`, import.meta.url), 'utf8')

test('regressão U1: Agenda > Operadores > operador não entrava no histórico (voltar saía da Agenda)', () => {
  const s = fonte('pages/Agenda.jsx')
  assert.match(s, /useSearchParams\(\)/, 'área e operador precisam morar na URL')
  assert.doesNotMatch(s, /useState\(null\)\s*\/\/\s*\{id, nome\}/, 'operador voltou a ser estado interno')
  assert.doesNotMatch(s, /\bset(Operador|AreaEquipe|Escopo)\(/, 'nível da Agenda mudado sem passar pela URL')
})

test('regressão U2: ficha aberta pela Agenda dizia "Voltar à fila" e ia para o Painel da carteira', () => {
  const agenda = fonte('pages/Agenda.jsx')
  assert.match(agenda, /navigate\(`\/devedor\/\$\{rank\}`,[^\n]*voltar: \{ para:[^\n]*'Voltar à agenda'/)
  const ficha = fonte('pages/DebtorDetail.jsx')
  assert.match(ficha, /location\.state\?\.voltar/)
  assert.doesNotMatch(ficha, /onClick=\{voltarAoDashboard\}/, 'botão de voltar ignora a origem')
  assert.doesNotMatch(ficha, /<ArrowLeft[^>]*\/> Voltar à fila/, 'rótulo fixo no botão de voltar')
})

test('regressão U3: confirmar pagamento não mostrava o que foi registrado', () => {
  const s = fonte('pages/Dashboard.jsx')
  assert.match(s, /setAvisoPagamento\(\{/)
  assert.match(s, /<AvisoDesfazer aviso=\{avisoPagamento\}/)
  assert.match(s, /Sem valor, o pagamento entra como R\$ 0/, 'falta avisar que vazio vira R$ 0')
  const aviso = fonte('components/AvisoDesfazer.jsx')
  assert.match(aviso, /aviso\.desfazer && \(estado === 'aberto'/, 'sem desfazer, o botão Desfazer não pode aparecer')
})

test('regressão U4: Premissas descartava a edição em silêncio ao trocar de aba', () => {
  const s = fonte('pages/Premissas.jsx')
  assert.match(s, /useProtegerSaida\(alteradas\.length > 0/)
})

test('regressão U5: depois de expirar a sessão, o login esquecia a tela em que a pessoa estava', () => {
  const login = fonte('pages/Login.jsx')
  assert.match(login, /searchParams\.get\('de'\)/)
  assert.match(login, /state: retomar \? \{ retomar \}/)
  assert.match(login, /!de\.startsWith\('\/\/'\)/, 'sem a trava, ?de=//site-externo vira redirecionamento aberto')
  assert.match(fonte('pages/Inicio.jsx'), /useState\(estado\?\.retomar/)
})

test('regressão U6: Equipe > operador não entrava no histórico (voltar saía do Painel)', () => {
  const s = fonte('pages/PainelOperador.jsx')
  assert.match(s, /params\.get\('op'\)/)
  assert.doesNotMatch(s, /setOpSel|useState\('hoje'\)/, 'operador ou período voltaram a ser estado interno')
})

test('regressão U7: Pastas perdia carteira, busca e filtro ao voltar do caso', () => {
  const s = fonte('pages/PastasDevedores.jsx')
  for (const k of ['carteira', 'q', 'cor']) assert.ok(s.includes(`params.get('${k}')`), `${k} fora da URL`)
  assert.doesNotMatch(s, /setCor\(|setCarteiraId\(|setBuscaAplicada\(/)
})

test('regressão U8: Pastas com erro dizia "Ainda não há carteira" e o Tentar de novo não fazia nada', () => {
  const s = fonte('pages/PastasDevedores.jsx')
  assert.match(s, /<ErroCarga erro=\{erroCarteiras\} onTentar=/)
  assert.match(s, /!carregandoCarteiras && !erroCarteiras && \(/, 'estado vazio aparece junto com o erro')
})

test('regressão U9: voltar do devedor zerava busca, filtros, página e rolagem da fila', () => {
  const s = fonte('pages/Dashboard.jsx')
  assert.match(s, /onClick=\{\(\) => abrirDevedor\(d\.rank\)\}/)
  assert.match(s, /state: \{ \.\.\.location\.state, fila \}/)
  assert.match(s, /useState\(filaSalva\?\.page \?\? 1\)/)
  assert.match(s, /tabelaRef\.current\.scrollTop = filaSalva\.tabela/)
})

test('regressão U10/U20: pasta exigia dois cliques sem pista e o leitor de tela falava inglês', () => {
  assert.match(fonte('pages/PastasDevedores.jsx'), /Ver fluxo <ArrowRight/)
  const pasta = fonte('components/ui/glass-folder-cards.tsx')
  assert.doesNotMatch(pasta, /"Open "|"Close "|" contents"|"More options for "/)
})

test('regressão U11: "Cumpriu" mandava registrar o pagamento em outra tela, sem atalho', () => {
  const agenda = fonte('pages/Agenda.jsx')
  assert.match(agenda, /rotulo: 'Registrar pagamento'/)
  const feedback = fonte('pages/Feedback.jsx')
  assert.match(feedback, /useState\(registrar\?\.devedor \?\? null\)/)
})

test('regressão U12: o admin procurava um botão de novo usuário que só o Comando tem', () => {
  assert.match(fonte('pages/AdminUsuarios.jsx'), /Para incluir alguém, peça ao Comando/)
  assert.match(fonte('pages/Ajuda.jsx'), /useState\(!!location\.state\?\.pedir\)/)
})

test('regressão U14: o menu dizia "Política de cobrança" e a página "Premissas" (idem Simulação histórica)', () => {
  assert.match(fonte('pages/Premissas.jsx'), /<h1[^>]*>Política de cobrança</)
  assert.match(fonte('pages/Backtest.jsx'), /<h1[^>]*>Simulação histórica</)
  assert.match(fonte('pages/Agenda.jsx'), /<p className="section-label">Hoje<\/p>/)
})

test('regressão U15/U16: botão da Agenda só apagava, e o erro da ação aparecia longe do devedor', () => {
  const s = fonte('pages/Agenda.jsx')
  assert.match(s, /ocupado === acao \? <Loader2/, 'o botão clicado precisa mostrar que está trabalhando')
  assert.match(s, /\{erro && <FalhaNoCartao erro=\{erro\} \/>\}/)
  assert.match(s, /Não foi possível \{erro\.oque\}/)
})

test('regressão U17: endereço inexistente caía no Início sem explicar', () => {
  assert.match(fonte('App.jsx'), /path="\*" element=\{<RotaInexistente \/>\}/)
  assert.match(fonte('pages/Inicio.jsx'), /não existe mais\. Você está no Início\./)
})

test('regressão U18: "10% à vista" continuava com esse nome depois de virar 15%', async () => {
  const s = fonte('pages/Ofertas.jsx')
  const ini = s.indexOf('const numero ='), fim = s.indexOf('const NOVA =')
  const { trocarNoNome } = await import('data:text/javascript,' + encodeURIComponent(s.slice(ini, fim) + '\nexport { trocarNoNome }'))
  assert.equal(trocarNoNome('10% à vista', 10, '15', '%'), '15% à vista')
  assert.equal(trocarNoNome('Parcelado em 6x', 6, 12, 'x'), 'Parcelado em 12x')
  assert.equal(trocarNoNome('110% x', 10, 15, '%'), '110% x', 'trocou o 10 de dentro do 110')
  assert.equal(trocarNoNome('Campanha Natal', 10, 20, '%'), 'Campanha Natal')
})

test('regressão U19: Auditoria mostrava códigos como oferta_desfeita', () => {
  const s = fonte('pages/Auditoria.jsx')
  assert.match(s, /\{nomeDaAcao\(l\.acao\)\}/)
  for (const k of ['ofertas_atualizadas', 'premissas_atualizadas', 'fila_distribuida', 'parcela_paga']) assert.ok(s.includes(`  ${k}:`), `${k} sem nome`)
})
