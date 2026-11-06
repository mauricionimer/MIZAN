import test from 'node:test'
import assert from 'node:assert/strict'
import {
  tempoRelativo, secoes, linkInterno, tituloDaAba, rotuloDoSino, novasQueTocam, urgenteParaAvisar,
  categoriasDoPapel, CATEGORIAS, porDia,
} from '../src/lib/notificacoes.js'

// 14:00 de Brasília (17:00 UTC) de sexta, 06/11/2026.
const AGORA = new Date('2026-11-06T17:00:00Z')
const iso = (minutosAtras) => new Date(AGORA.getTime() - minutosAtras * 60_000).toISOString()

test('tempo relativo em Brasília', () => {
  assert.equal(tempoRelativo(iso(0.2), AGORA), 'agora')
  assert.equal(tempoRelativo(iso(5), AGORA), 'há 5 min')
  assert.equal(tempoRelativo(iso(130), AGORA), 'há 2 h')
  assert.equal(tempoRelativo('2026-11-05T17:30:00Z', AGORA), 'ontem às 14:30')
  assert.equal(tempoRelativo('2026-11-03T12:05:00Z', AGORA), '03/11 às 09:05')
  assert.equal(tempoRelativo('não é data', AGORA), '')
})

test('a meia-noite de Brasília separa hoje de ontem (não a de UTC)', () => {
  // 01:30 UTC de 07/11 ainda é 22:30 de 06/11 em Brasília
  const noite = new Date('2026-11-07T01:30:00Z')
  assert.equal(tempoRelativo('2026-11-06T23:00:00Z', noite), 'há 2 h')
})

test('seções Agora, Hoje e Antes, mais novas primeiro e sem seção vazia', () => {
  const s = secoes([{ id: 'a', atualizado_em: iso(300) }, { id: 'b', atualizado_em: iso(2) },
    { id: 'c', atualizado_em: '2026-11-04T12:00:00Z' }, { id: 'd', atualizado_em: iso(30) }], AGORA)
  assert.deepEqual(s.map(x => x.id), ['agora', 'hoje', 'antes'])
  assert.deepEqual(s[0].itens.map(i => i.id), ['b', 'd'])
  assert.deepEqual(s[1].itens.map(i => i.id), ['a'])
  assert.deepEqual(secoes([{ id: 'x', atualizado_em: iso(1) }], AGORA).map(x => x.id), ['agora'])
  assert.deepEqual(secoes([], AGORA), [])
})

test('página: agrupa por dia de Brasília, do mais novo para o mais antigo', () => {
  const g = porDia([
    { id: 'a', atualizado_em: '2026-11-03T15:00:00Z' },        // terça, 03/11
    { id: 'b', atualizado_em: iso(10) },                        // hoje
    { id: 'c', atualizado_em: '2026-11-05T20:00:00Z' },        // ontem
    { id: 'd', atualizado_em: '2026-11-06T02:30:00Z' },        // 23:30 de 05/11 em Brasília: ontem
    { id: 'e', atualizado_em: '2026-11-03T12:00:00Z' },
  ], AGORA)
  assert.deepEqual(g.map(x => x.titulo), ['Hoje', 'Ontem', 'Terça-feira, 03/11'])
  assert.deepEqual(g[1].itens.map(i => i.id), ['d', 'c'])
  assert.deepEqual(g[2].itens.map(i => i.id), ['a', 'e'])
  assert.deepEqual(porDia([], AGORA), [])
})

test('link só para telas internas', () => {
  assert.equal(linkInterno('/pasta/1?aba=conversa'), '/pasta/1?aba=conversa')
  for (const ruim of ['https://golpe.example', '//golpe.example', 'javascript:alert(1)', '/\\golpe', '', null, '/javascript:x']) {
    assert.equal(linkInterno(ruim), '/inicio', String(ruim))
  }
})

test('número na aba do navegador', () => {
  assert.equal(tituloDaAba('Mizan — Análise', 3), '(3) Mizan — Análise')
  assert.equal(tituloDaAba('(3) Mizan — Análise', 0), 'Mizan — Análise')
  assert.equal(tituloDaAba('(3) Mizan', 120), '(99+) Mizan')
})

test('nome acessível do sino', () => {
  assert.equal(rotuloDoSino(0, 0), 'Notificações: nenhuma nova')
  assert.equal(rotuloDoSino(1, 0), 'Notificações: 1 nova')
  assert.equal(rotuloDoSino(4, 1), 'Notificações: 4 novas, 1 urgente')
})

test('o que toca: só o que o servidor marcou, não lido, e uma vez por aba', () => {
  const itens = [
    { id: '1', toca: true, prioridade: 'urgente', atualizado_em: iso(1) },
    { id: '2', toca: true, prioridade: 'alta', atualizado_em: iso(2) },
    { id: '3', toca: false, prioridade: 'normal', atualizado_em: iso(3) },
    { id: '4', toca: true, prioridade: 'urgente', lida: true, atualizado_em: iso(4) },
    { id: '5', toca: true, prioridade: 'urgente', resolvida: true, atualizado_em: iso(5) },
  ]
  assert.deepEqual(novasQueTocam(itens, new Set()).map(i => i.id), ['1', '2'])
  assert.deepEqual(novasQueTocam(itens, ['1']).map(i => i.id), ['2'])
  assert.equal(urgenteParaAvisar(itens, new Set())?.id, '1')
  assert.equal(urgenteParaAvisar(itens, new Set(['1'])), null)
})

test('categorias de cada papel nas preferências', () => {
  assert.equal(categoriasDoPapel(true).length, CATEGORIAS.length)
  assert.ok(!categoriasDoPapel(false).some(c => c.id === 'sistema'))
})
