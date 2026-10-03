// Até onde a equipe chega na fila neste ciclo, e quanto isso vale.
//
// A fila vem ordenada pelo valor esperado LÍQUIDO (o que sobra para o banco
// depois da comissão da fase), então o alcance de uma capacidade é a soma
// acumulada do líquido dos N primeiros, contra o líquido da carteira inteira.
// Devedor sem líquido gravado (análise antiga) entra pelo bruto. É o número que
// o gerente de cobrança leva para a reunião — vale ter teste.
const valorDe = (d) => d?.valor_esperado_liquido ?? d?.valor_esperado_recuperacao ?? 0

export function calcularAlcance(ranking, capacidade, valorEsperadoTotal) {
  const lista = Array.isArray(ranking) ? ranking : []
  const n = Math.max(0, Math.min(lista.length, parseInt(capacidade, 10) || 0))
  if (!n) return null

  let soma = 0
  for (let i = 0; i < n; i++) soma += valorDe(lista[i])

  const temLiquido = lista.some(d => d?.valor_esperado_liquido != null)
  // com o líquido, o total é o da própria fila; sem ele, o total bruto informado
  const total = temLiquido ? lista.reduce((t, d) => t + valorDe(d), 0) : (Number(valorEsperadoTotal) || 0)
  return {
    n,
    ate: lista[n - 1]?.rank ?? n,
    valor: soma,
    total,
    base: temLiquido ? 'liquido' : 'bruto',
    // Sem o total da carteira não dá para dizer que fração é essa; devolver
    // 0 seria inventar um número, então o campo fica nulo e a tela decide.
    pct: total > 0 ? (soma / total) * 100 : null,
    pctBase: lista.length > 0 ? (n / lista.length) * 100 : 0,
    restam: lista.length - n,
  }
}
