// Prioridade é posição na fila, não faixa de score.
//
// A fila é ordenada por valor esperado de recuperação (probabilidade × dívida),
// porque é isso que o banco quer maximizar. Derivar a etiqueta do score puro
// fazia o primeiro colocado aparecer como "Baixa" — quem deve muito e paga
// pouco rende mais que quem paga sempre e deve pouco, e a tela contradizia a
// própria ordenação.
//
// Os cortes acompanham a capacidade real de uma operação de cobrança: num
// ciclo dá para trabalhar algo como um quinto da carteira. "Alta" é o topo
// que cabe nesse ciclo; "Média" é o que entra se sobrar fôlego.
export const CORTE_ALTA  = 0.20
export const CORTE_MEDIA = 0.50

export function prioridadePorRank(rank, total) {
  const n = Number(total) || 0
  const r = Number(rank) || 0
  if (n <= 0 || r <= 0) return 'Baixa'
  const posicao = r / n
  if (posicao <= CORTE_ALTA)  return 'Alta'
  if (posicao <= CORTE_MEDIA) return 'Média'
  return 'Baixa'
}

// Sem acento, para o gerador de PDF que não embute fonte com acentuação.
export function prioridadePorRankAscii(rank, total) {
  return prioridadePorRank(rank, total).replace('é', 'e')
}
