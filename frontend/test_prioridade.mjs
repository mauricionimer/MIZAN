/**
 * Regressão: a etiqueta de prioridade acompanha a fila.
 *
 *     node test_prioridade.mjs
 *
 * A fila é ordenada por valor esperado de recuperação. A etiqueta vinha de
 * faixas de score, então o primeiro colocado podia aparecer como "Baixa" —
 * quem deve muito e paga pouco rende mais que quem paga sempre e deve pouco,
 * e a tela contradizia a própria ordenação.
 */
import { prioridadePorRank, prioridadePorRankAscii } from './src/utils/prioridade.js'

let falhas = 0
const ok = (c, t, d='') => { console.log(`${c?'ok  ':'FALHA'}  ${t}${d?'  — '+d:''}`); if(!c) falhas++ }

const N = 1000
ok(prioridadePorRank(1, N) === 'Alta', 'o primeiro da fila é sempre Alta')
ok(prioridadePorRank(200, N) === 'Alta', 'o corte de 20% ainda é Alta')
ok(prioridadePorRank(201, N) === 'Média', 'logo depois vira Média')
ok(prioridadePorRank(500, N) === 'Média', 'o corte de 50% ainda é Média')
ok(prioridadePorRank(501, N) === 'Baixa', 'depois da metade, Baixa')
ok(prioridadePorRank(N, N) === 'Baixa', 'o último é Baixa')

// a regressão que motivou tudo: quem deve muito e paga pouco lidera a fila
// e não pode mais aparecer como Baixa
ok(prioridadePorRank(1, 5000) === 'Alta', 'rank 1 é Alta mesmo em carteira grande')

// entradas ruins não podem quebrar a tela
ok(prioridadePorRank(undefined, N) === 'Baixa', 'rank ausente não estoura')
ok(prioridadePorRank(1, 0) === 'Baixa', 'total zero não estoura')
ok(prioridadePorRank(1, undefined) === 'Baixa', 'total ausente não estoura')
ok(prioridadePorRank(null, null) === 'Baixa', 'tudo nulo não estoura')

// o PDF não embute fonte com acento
ok(prioridadePorRankAscii(300, N) === 'Media', 'versão do PDF sai sem acento',
   prioridadePorRankAscii(300, N))
ok(prioridadePorRankAscii(1, N) === 'Alta' && prioridadePorRankAscii(999, N) === 'Baixa',
   'e as outras duas seguem iguais')

// as faixas cobrem a fila inteira, sem buraco
const niveis = new Set()
for (let r = 1; r <= N; r++) niveis.add(prioridadePorRank(r, N))
ok(niveis.size === 3, 'as três faixas aparecem numa fila de 1000', [...niveis].join(', '))

console.log(falhas ? `\n${falhas} falha(s)` : '\nRESULTADO: tudo certo')
process.exit(falhas ? 1 : 0)
