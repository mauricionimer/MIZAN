/** Sino de notificações (docs/NOTIFICACOES.md) num navegador real, com a API simulada.
 *
 *    node tests/notificacoes.ui.mjs            (MIZAN_FOTOS=<pasta> guarda as fotos)
 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.MIZAN_PLAYWRIGHT_MODULE || 'playwright')
const root = fileURLToPath(new URL('../', import.meta.url))
process.chdir(root); process.env.VITE_API_URL = 'http://127.0.0.1:8001'
const server = await createServer({ root, server: { host: '127.0.0.1', port: 0 } })
await server.listen()
const address = `http://127.0.0.1:${server.httpServer.address().port}`
const fotos = process.env.MIZAN_FOTOS
const browser = await chromium.launch({ headless: true })

const agora = Date.now()
const iso = (min) => new Date(agora - min * 60_000).toISOString()
const base = () => ([
  { id: '00000000-0000-0000-0000-000000000001', tipo: 'N03', categoria: 'conversas', prioridade: 'urgente',
    titulo: 'Atenção: Maria mostrou sinais de sofrimento grave', texto: 'Atender com prioridade, para acolher, não para cobrar.',
    link: '/pasta/p1?aba=conversa', acao: 'Abrir conversa', externo: 'Atendimento urgente', toca: true, lida: false,
    resolvida: false, agrupadas: 1, criado_em: iso(2), atualizado_em: iso(2) },
  { id: '00000000-0000-0000-0000-000000000002', tipo: 'N07', categoria: 'reunioes', prioridade: 'alta',
    titulo: 'Reunião com João atribuída a você', texto: 'Hoje às 16:30. O lembrete chega 30 e 5 minutos antes.',
    link: '/agenda', acao: 'Ver na agenda', externo: 'Reunião atribuída a você', toca: true, lida: false, resolvida: false,
    agrupadas: 1, criado_em: iso(20), atualizado_em: iso(20) },
  { id: '00000000-0000-0000-0000-000000000003', tipo: 'N26', categoria: 'equipe', prioridade: 'normal',
    titulo: 'Devedores novos na sua fila: 25', texto: 'Eles já aparecem nas suas pastas.', link: 'https://golpe.example',
    acao: 'Abrir pastas', externo: 'Devedores novos na sua fila', toca: false, lida: false, resolvida: false, agrupadas: 25,
    criado_em: iso(200), atualizado_em: iso(200) },
])

async function cenario({ largura, tema, papel = 'operador', foto, inicio = '/alterar-senha' }) {
  const page = await browser.newPage({ viewport: { width: largura, height: 900 }, reducedMotion: 'reduce' })
  const erros = []; page.on('pageerror', e => erros.push(e.message))
  const usuario = { id: 'op1', role: papel, empresa_id: papel === 'comando' ? '' : 'emp', nome: 'Ana Lima', email: 'ana@x' }
  let itens = base(), lidas = [], todas = 0, prefsSalvas = null, versao = 1
  const pedidos = []
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()); if (url.origin === address) return route.continue()
    if (url.origin !== 'http://127.0.0.1:8001') return route.abort()
    const metodo = route.request().method()
    let json = {}
    if (url.pathname === '/auth/refresh') json = { token: 'qa', usuario }
    else if (url.pathname === '/empresa/config') json = { nome_exibicao: 'Banco QA' }
    else if (url.pathname === '/agenda/resumo') json = { alto: 0, medio: 0 }
    else if (url.pathname === '/mudancas') json = { agenda: 'a:1', casos: 'a:1', notificacoes: `a:${versao}` }
    else if (url.pathname === '/notificacoes' && papel === 'comando') json = { ativo: false, itens: [], nao_lidas: 0, urgentes: 0 }
    else if (url.pathname === '/notificacoes') {
      pedidos.push(Object.fromEntries(url.searchParams))
      const pend = url.searchParams.get('filtro') !== 'todas'
      const cat = url.searchParams.get('categoria'), pri = url.searchParams.get('prioridade')
      const lista = (pend ? itens.filter(i => !i.lida) : itens)
        .filter(i => (!cat || i.categoria === cat) && (!pri || i.prioridade === pri))
      const por_categoria = { conversas: 0, reunioes: 0, retornos: 0, pedidos: 0, equipe: 0, sistema: 0 }
      itens.filter(i => !i.lida).forEach(i => { por_categoria[i.categoria]++ })
      json = { ativo: true, itens: lista, mais: false, nao_lidas: itens.filter(i => !i.lida).length, por_categoria,
        urgentes: itens.filter(i => !i.lida && i.prioridade === 'urgente').length,
        preferencias: prefsSalvas || { navegador: false, email_resumo: false, silencio_ligado: true, silencio_inicio: 20,
          silencio_fim: 8, desligadas: [] } }
    } else if (/^\/notificacoes\/[^/]+\/lida$/.test(url.pathname)) {
      const id = url.pathname.split('/')[2]; lidas.push(id); itens = itens.map(i => i.id === id ? { ...i, lida: true } : i)
      json = { ok: true }
    } else if (url.pathname === '/notificacoes/lidas') { todas++; itens = itens.map(i => ({ ...i, lida: true })); json = { ok: true } }
    else if (url.pathname === '/notificacoes/preferencias' && metodo === 'PUT') {
      prefsSalvas = JSON.parse(route.request().postData() || '{}'); json = { ...prefsSalvas, ativo: true }
    }
    return route.fulfill({ status: 200, json })
  })
  await page.addInitScript(([u, t]) => {
    sessionStorage.setItem('mizan_token', 'qa'); sessionStorage.setItem('mizan_user', JSON.stringify(u))
    localStorage.setItem('mizan_tema', t)
  }, [usuario, tema])
  await page.goto(address + inicio, { waitUntil: 'domcontentloaded' })
  return { page, erros, estado: () => ({ lidas, todas, prefsSalvas, pedidos }), mudar: () => { versao++ } }
}

const semRolagemLateral = (page) => page.evaluate(() => document.scrollingElement.scrollWidth <= window.innerWidth + 1)

try {
  // ── operador no computador, tema claro ──
  {
    const { page, erros, estado } = await cenario({ largura: 1280, tema: 'light' })
    const sino = page.getByRole('button', { name: /^Notificações:/ })
    await sino.waitFor()
    assert.equal(await sino.getAttribute('aria-label'), 'Notificações: 3 novas, 1 urgente', 'o sino diz quantas e se há urgente')
    const aviso = page.getByRole('alert').filter({ hasText: 'sofrimento grave' })
    await aviso.waitFor()
    await page.waitForFunction(() => document.title.startsWith('(3) '))
    if (fotos) await page.screenshot({ path: `${fotos}/sino-1280-claro-aviso.png` })
    await aviso.getByRole('button', { name: 'Fechar aviso urgente' }).click()
    assert.equal(estado().lidas.length, 0, 'fechar o aviso de urgente não marca como lida')
    await sino.click()
    const painel = page.getByRole('dialog', { name: 'Notificações' })
    await painel.waitFor()
    await painel.getByRole('heading', { name: 'Agora' }).waitFor()
    await painel.getByRole('heading', { name: 'Hoje' }).or(painel.getByRole('heading', { name: 'Antes' })).first().waitFor()
    assert.equal(await painel.getByText('Urgente', { exact: true }).count(), 1, 'o urgente tem o rótulo em texto, não só a cor')
    if (fotos) await page.screenshot({ path: `${fotos}/painel-1280-claro.png` })
    await painel.getByRole('listitem').filter({ hasText: 'Reunião com João' }).getByRole('button', { name: 'Marcar como lida' }).click()
    await page.waitForFunction(() => document.title.startsWith('(2) '))
    assert.deepEqual(estado().lidas, ['00000000-0000-0000-0000-000000000002'])
    // link de fora vira o Início
    await painel.getByRole('listitem').filter({ hasText: 'Devedores novos' }).getByRole('button', { name: 'Abrir pastas' }).click()
    await page.waitForURL(u => new URL(u).pathname === '/inicio')
    assert.equal(await page.getByRole('dialog', { name: 'Notificações' }).count(), 0, 'abrir um aviso fecha o painel')
    await sino.click()
    await page.getByRole('dialog', { name: 'Notificações' }).getByRole('button', { name: 'Abrir conversa' }).click()
    await page.waitForURL(u => new URL(u).pathname === '/pasta/p1' && new URL(u).searchParams.get('aba') === 'conversa')
    assert.equal(await page.title().then(t => t.startsWith('(')), false, 'tudo lido: a aba volta ao título normal')
    assert.deepEqual(erros, [], 'sem erro de página')
    await page.close()
  }
  // ── preferências e "marcar todas" no celular, tema escuro ──
  {
    const { page, erros, estado } = await cenario({ largura: 390, tema: 'dark' })
    const sino = page.getByRole('button', { name: /^Notificações:/ })
    await sino.waitFor()
    await page.getByRole('alert').filter({ hasText: 'sofrimento grave' }).waitFor()
    assert.ok(await semRolagemLateral(page), 'nada rola na horizontal em 390 px (com o aviso)')
    if (fotos) await page.screenshot({ path: `${fotos}/aviso-390-escuro.png` })
    await page.getByRole('alert').getByRole('button', { name: 'Fechar aviso urgente' }).click()
    await sino.click()
    const painel = page.getByRole('dialog', { name: 'Notificações' })
    await painel.waitFor()
    const caixa = await painel.boundingBox()
    assert.ok(caixa && caixa.width >= 389, 'no celular o painel ocupa a tela toda')
    assert.ok(await semRolagemLateral(page), 'nada rola na horizontal em 390 px (painel aberto)')
    if (fotos) await page.screenshot({ path: `${fotos}/painel-390-escuro.png` })
    await painel.getByRole('button', { name: 'Preferências de notificação' }).click()
    const prefs = page.getByRole('dialog', { name: 'Preferências de notificação' })
    await prefs.waitFor()
    await prefs.getByLabel(/Resumo por e-mail/).check()
    await prefs.getByLabel(/^Equipe/).uncheck()
    await prefs.getByLabel('Das', { exact: true }).selectOption('21')
    assert.equal(await prefs.getByLabel(/^Sistema/).count(), 0, 'o operador não vê a categoria de sistema')
    if (fotos) await page.screenshot({ path: `${fotos}/preferencias-390-escuro.png`, fullPage: false })
    await prefs.getByRole('button', { name: 'Salvar preferências' }).click()
    await prefs.getByText('Preferências salvas.').waitFor()
    const salvas = estado().prefsSalvas
    assert.equal(salvas.email_resumo, true); assert.equal(salvas.silencio_inicio, 21); assert.deepEqual(salvas.desligadas, ['equipe'])
    await prefs.getByRole('button', { name: 'Voltar aos avisos' }).click()
    await page.getByRole('dialog', { name: 'Notificações' }).getByRole('button', { name: 'Marcar todas como lidas' }).click()
    await page.getByText('Tudo lido por aqui').waitFor()
    assert.equal(estado().todas, 1, 'marcar todas: um pedido só')
    await page.keyboard.press('Escape')
    await page.getByRole('dialog', { name: 'Notificações' }).waitFor({ state: 'detached' })
    assert.equal(await sino.getAttribute('aria-label'), 'Notificações: nenhuma nova')
    assert.deepEqual(erros, [], 'sem erro de página')
    await page.close()
  }
  // ── administrador escuro no computador e COMANDO sem sino ──
  {
    const { page, erros } = await cenario({ largura: 1280, tema: 'dark', papel: 'admin' })
    await page.getByRole('button', { name: /^Notificações:/ }).click()
    const painel = page.getByRole('dialog', { name: 'Notificações' })
    await painel.getByRole('button', { name: 'Preferências de notificação' }).click()
    await page.getByRole('dialog', { name: 'Preferências de notificação' }).getByLabel(/^Sistema/).waitFor()
    await page.getByRole('dialog', { name: 'Preferências de notificação' }).getByRole('button', { name: 'Voltar aos avisos' }).click()
    if (fotos) await page.screenshot({ path: `${fotos}/painel-1280-escuro-admin.png` })
    assert.deepEqual(erros, [])
    await page.close()
  }
  // ── a página Notificações: menu, filtros, marcar como lida (o sino acompanha) ──
  {
    const { page, erros, estado } = await cenario({ largura: 1280, tema: 'light' })
    await page.getByRole('alert').filter({ hasText: 'sofrimento grave' }).getByRole('button', { name: 'Fechar aviso urgente' }).click()
    await page.getByRole('button', { name: 'Abrir menu' }).click()
    const item = page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: /^Notificações/ })
    assert.match(await item.innerText(), /3/, 'o menu mostra quantas não lidas')
    await item.click()
    await page.waitForURL(u => new URL(u).pathname === '/notificacoes')
    await page.getByRole('heading', { level: 1, name: 'Notificações' }).waitFor()
    // Perto da meia-noite de Brasília, um aviso de minutos atrás já é de "Ontem": o grupo depende da hora.
    await page.getByRole('heading', { level: 2, name: /^(Hoje|Ontem)$/ }).first().waitFor()
    const resumo = page.getByText('3 não lidas', { exact: true })
    await resumo.waitFor()
    await page.getByRole('button', { name: /^Reuniões/ }).click()
    await page.getByRole('listitem').filter({ hasText: 'sofrimento grave' }).waitFor({ state: 'detached' })
    await page.getByRole('listitem').filter({ hasText: 'Reunião com João' }).waitFor()
    assert.equal(estado().pedidos.at(-1).categoria, 'reunioes', 'o filtro vai para o servidor')
    await page.getByRole('button', { name: /^Reuniões/ }).click()
    await page.getByLabel('Só urgentes').check()
    await page.getByRole('listitem').filter({ hasText: 'Reunião com João' }).waitFor({ state: 'detached' })
    await page.getByRole('listitem').filter({ hasText: 'sofrimento grave' }).waitFor()
    await page.getByLabel('Só urgentes').uncheck()
    if (fotos) await page.screenshot({ path: `${fotos}/pagina-1280-claro.png`, fullPage: true })
    await page.getByRole('listitem').filter({ hasText: 'Reunião com João' }).getByRole('button', { name: 'Marcar como lida' }).click()
    await page.getByText('2 não lidas', { exact: true }).waitFor()
    assert.equal(await page.getByRole('listitem').filter({ hasText: 'Reunião com João' }).count(), 0, 'lida sai de "Não lidas"')
    assert.equal(await page.getByRole('button', { name: /^Notificações:/ }).getAttribute('aria-label'), 'Notificações: 2 novas, 1 urgente',
      'o sino acompanha a página na hora')
    await page.getByRole('tab', { name: 'Todas' }).click()
    await page.getByRole('listitem').filter({ hasText: 'Reunião com João' }).getByText('· Lida').waitFor()
    await page.getByRole('button', { name: 'Marcar todas como lidas' }).click()
    await page.getByText('Tudo lido', { exact: true }).waitFor()
    assert.equal(estado().todas, 1)
    await page.getByRole('tab', { name: /^Não lidas/ }).click()
    await page.getByText('Tudo lido por aqui').waitFor()
    await page.getByRole('button', { name: 'Ver todas' }).click()
    await page.getByRole('tab', { name: 'Todas', selected: true }).waitFor()
    assert.deepEqual(erros, [], 'sem erro de página')
    await page.close()
  }
  {
    const { page, erros } = await cenario({ largura: 390, tema: 'dark', inicio: '/notificacoes' })
    await page.getByRole('heading', { level: 1, name: 'Notificações' }).waitFor()
    await page.getByRole('alert').filter({ hasText: 'sofrimento grave' }).getByRole('button', { name: 'Fechar aviso urgente' }).click()
    await page.getByRole('listitem').filter({ hasText: 'Devedores novos' }).waitFor()
    assert.ok(await semRolagemLateral(page), 'página: nada rola na horizontal em 390 px')
    if (fotos) await page.screenshot({ path: `${fotos}/pagina-390-escuro.png`, fullPage: true })
    await page.getByRole('button', { name: 'Preferências', exact: true }).click()
    await page.getByRole('dialog', { name: 'Preferências de notificação' }).waitFor()
    await page.keyboard.press('Escape')
    // o painel do sino leva à página
    await page.getByRole('button', { name: /^Notificações:/ }).click()
    await page.getByRole('dialog', { name: 'Notificações' }).getByRole('button', { name: 'Ver todas as notificações' }).waitFor()
    assert.deepEqual(erros, [])
    await page.close()
  }
  {
    const { page, erros } = await cenario({ largura: 1280, tema: 'light', papel: 'comando', inicio: '/notificacoes' })
    await page.getByText('O COMANDO não tem sino').waitFor()
    await page.getByRole('button', { name: 'Abrir menu' }).click()
    assert.equal(await page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: /^Notificações/ }).count(), 0,
      'o COMANDO não tem o item no menu')
    assert.deepEqual(erros, [])
    await page.close()
  }
  {
    const { page, erros } = await cenario({ largura: 1280, tema: 'light', papel: 'comando' })
    await page.getByRole('button', { name: 'Abrir menu' }).waitFor()
    await page.waitForTimeout(800)
    assert.equal(await page.getByRole('button', { name: /^Notificações:/ }).count(), 0, 'o COMANDO não tem sino')
    assert.deepEqual(erros, [])
    await page.close()
  }
  console.log(JSON.stringify({ ok: true, cenarios: ['operador 1280 claro', 'operador 390 escuro', 'admin 1280 escuro',
    'página: menu, filtros e marcar', 'página 390 escuro', 'página do COMANDO', 'comando sem sino'] }))
} finally { await browser.close(); await server.close() }
