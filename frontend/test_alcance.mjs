/**
 * Regressão: o alcance da operação.
 *
 *     node test_alcance.mjs
 *
 * É o número que o gerente de cobrança leva para a reunião: "com a equipe que
 * eu tenho, chego até a posição N e isso vale R$ X". Erro de um a mais ou um a
 * menos aqui vira número errado numa proposta comercial.
 */
import { calcularAlcance } from './src/utils/alcance.js'

let falhas = 0
const ok = (c, t, d = '') => { console.log(`${c ? 'ok  ' : 'FALHA'}  ${t}${d ? '  — ' + d : ''}`); if (!c) falhas++ }

// fila ordenada por valor esperado, como o backend entrega
const fila = [
  { rank: 1, valor_esperado_recuperacao: 1000 },
  { rank: 2, valor_esperado_recuperacao: 600 },
  { rank: 3, valor_esperado_recuperacao: 300 },
  { rank: 4, valor_esperado_recuperacao: 100 },
]
const TOTAL = 2000

const a2 = calcularAlcance(fila, 2, TOTAL)
ok(a2.valor === 1600, 'soma o valor esperado dos N primeiros', `R$ ${a2.valor}`)
ok(a2.ate === 2, 'e diz até que posição a fila alcança', `#${a2.ate}`)
ok(a2.pct === 80, 'a fração do recuperável sai certa', `${a2.pct}%`)
ok(a2.pctBase === 50, 'e a fração da base também', `${a2.pctBase}%`)
ok(a2.restam === 2, 'quantos ficam para o próximo ciclo', String(a2.restam))

// a concentração é o argumento de venda: metade da base traz 80% do valor
ok(a2.pct > a2.pctBase, 'metade dos contatos traz mais da metade do valor',
  `${a2.pct}% do valor em ${a2.pctBase}% da base`)

// bordas
ok(calcularAlcance(fila, 1, TOTAL).valor === 1000, 'capacidade 1 pega só o primeiro')
const tudo = calcularAlcance(fila, 4, TOTAL)
ok(tudo.valor === 2000 && tudo.restam === 0, 'capacidade igual à fila pega tudo')
const alem = calcularAlcance(fila, 999, TOTAL)
ok(alem.n === 4 && alem.restam === 0, 'capacidade maior que a fila não estoura',
  `n=${alem.n}`)
ok(calcularAlcance(fila, 0, TOTAL) === null, 'capacidade zero devolve nada')
ok(calcularAlcance(fila, '', TOTAL) === null, 'campo vazio devolve nada')
ok(calcularAlcance(fila, 'abc', TOTAL) === null, 'texto inválido devolve nada')
ok(calcularAlcance(null, 2, TOTAL) === null, 'sem fila, devolve nada')
ok(calcularAlcance([], 2, TOTAL) === null, 'fila vazia devolve nada')

// linha sem valor esperado não pode virar NaN e contaminar a soma
const comBuraco = [{ rank: 1, valor_esperado_recuperacao: 500 }, { rank: 2 }]
ok(calcularAlcance(comBuraco, 2, 500).valor === 500,
  'devedor sem valor esperado conta como zero, não como NaN',
  String(calcularAlcance(comBuraco, 2, 500).valor))

// sem o total da carteira, a fração é desconhecida — não zero
const semTotal = calcularAlcance(fila, 2, 0)
ok(semTotal.pct === null, 'sem o total, a fração vem nula em vez de inventada')
ok(semTotal.valor === 1600, 'mas o valor somado continua certo')

// D5: a fila é ordenada pelo líquido; o alcance soma o líquido contra o líquido total
const liq = [
  { rank: 1, valor_esperado_recuperacao: 1000, valor_esperado_liquido: 800 },
  { rank: 2, valor_esperado_recuperacao: 900,  valor_esperado_liquido: 700 },
  { rank: 3, valor_esperado_recuperacao: 100,  valor_esperado_liquido: 100 },
]
const aL = calcularAlcance(liq, 2, 2000)
ok(aL.valor === 1500 && aL.base === 'liquido', 'com líquido, soma o líquido dos N primeiros', `R$ ${aL.valor}`)
ok(aL.total === 1600 && Math.abs(aL.pct - 93.75) < 1e-9, 'e a fração é sobre o líquido da carteira, não o bruto', `${aL.pct}%`)
const mista = [{ rank: 1, valor_esperado_liquido: 300 }, { rank: 2, valor_esperado_recuperacao: 200 }]
ok(calcularAlcance(mista, 2, 0).valor === 500, 'devedor sem líquido gravado entra pelo bruto')
ok(calcularAlcance(fila, 2, TOTAL).base === 'bruto', 'análise antiga, sem líquido: base bruta, como antes')

console.log(falhas ? `\n${falhas} falha(s)` : '\nRESULTADO: tudo certo')
process.exit(falhas ? 1 : 0)
