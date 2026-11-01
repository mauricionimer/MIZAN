/** Ciclo supervisionado, histórico e layout móvel, sem serviços externos. */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.MIZAN_PLAYWRIGHT_MODULE || 'playwright')
const root = fileURLToPath(new URL('../', import.meta.url))
process.env.VITE_API_URL = 'http://127.0.0.1:8001'
const server = await createServer({ root, server: { host: '127.0.0.1', port: 0 } })
await server.listen()
const origin = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const usuario = { id: 'qa', role: 'admin', empresa_id: 'a', nome: 'QA' }
  const erros = [], chamadas = []
  let acoes = []
  const acao = { id: 'proposta-1', tipo: 'retreino_score', status: 'proposta', criado_em: '2026-10-31T12:00:00Z', dados: {
    o_que_mudou: '320 resultados maduros.', o_que_fazer: 'Treinar candidato inativo.', por_que: 'Critérios satisfeitos.',
    coorte: { elegiveis: 320, pagaram: 160, nao_pagaram: 160, novos: 40, minimos: { total: 300, novos: 30, maturidade_dias: 30 }, faltas: [], excluidos: {}, sha256: 'a'.repeat(64) },
  } }
  page.on('pageerror', e => erros.push(e.message))
  await page.route('**/*', async route => {
    const u = new URL(route.request().url())
    if (u.origin === origin) return route.continue()
    if (u.origin !== 'http://127.0.0.1:8001') return route.abort()
    chamadas.push(u.pathname)
    let json = {}
    if (u.pathname === '/auth/refresh') json = { token: 'qa', usuario }
    else if (u.pathname === '/agente/laboratorio') json = { recomendacoes: [] }
    else if (u.pathname === '/agente/aprendizado') json = { acoes, versao_ativa: null }
    else if (u.pathname === '/agente/aprendizado/avaliar') { acoes = [structuredClone(acao)]; json = acoes[0] }
    else if (u.pathname.endsWith('/decidir')) { acoes[0].status = 'aprovada'; json = acoes[0] }
    else if (u.pathname.endsWith('/executar')) {
      acoes[0].status = 'concluida'; acoes[0].dados.relatorio_execucao = 'Modelo treinado e mantido inativo.'
      json = { aceito: true, mensagem: 'Execução solicitada.' }
    } else if (u.pathname.endsWith('/historico')) json = [{ id: 1, evento: 'aprovada', ator: 'admin@teste', criado_em: acao.criado_em, motivo: 'Decisão humana registrada', dados: acao }]
    return route.fulfill({ status: 200, json })
  })
  await page.addInitScript(usuario => {
    sessionStorage.setItem('mizan_token', 'qa'); sessionStorage.setItem('mizan_user', JSON.stringify(usuario))
  }, usuario)
  await page.goto(origin + '/laboratorio', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Avaliar dados para retreino' }).click()
  await page.getByText('320/300 pessoas', { exact: false }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Executar ação aprovada' }).count(), 0)
  await page.getByRole('button', { name: 'Aprovar proposta' }).click()
  await page.getByRole('button', { name: 'Executar ação aprovada' }).click()
  await page.getByText('Modelo treinado e mantido inativo.', { exact: false }).first().waitFor()
  await page.getByRole('button', { name: 'Ver auditoria' }).click()
  await page.getByText('Decisão humana registrada').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true)
  assert.deepEqual(erros, [])
  assert.equal(chamadas.filter(p => p.endsWith('/executar')).length, 1)
  console.log('OK: avaliação, aprovação antes da execução, modelo inativo, auditoria e mobile')
} finally { await browser.close(); await server.close() }
