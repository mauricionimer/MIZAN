// Até onde a equipe chega na fila neste ciclo, e quanto isso vale.
//
// A fila vem ordenada por valor esperado de recuperação, então o alcance de
// uma capacidade é a soma acumulada dos N primeiros. É o número que o gerente
// de cobrança leva para a reunião — vale ter teste.
export function calcularAlcance(ranking, capacidade, valorEsperadoTotal) {
  const lista = Array.isArray(ranking) ? ranking : []
  const n = Math.max(0, Math.min(lista.length, parseInt(capacidade, 10) || 0))
  if (!n) return null

  let soma = 0
  for (let i = 0; i < n; i++) soma += lista[i]?.valor_esperado_recuperacao ?? 0

  const total = Number(valorEsperadoTotal) || 0
  return {
    n,
    ate: lista[n - 1]?.rank ?? n,
    valor: soma,
    // Sem o total da carteira não dá para dizer que fração é essa; devolver
    // 0 seria inventar um número, então o campo fica nulo e a tela decide.
    pct: total > 0 ? (soma / total) * 100 : null,
    pctBase: lista.length > 0 ? (n / lista.length) * 100 : 0,
    restam: lista.length - n,
  }
}
