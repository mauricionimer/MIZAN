import { prioridadePorRank } from '../utils/prioridade'

// Badge de prioridade — cor + texto, nunca só cor (brief, seção 5).
// Recebe a posição na fila, não o score: a fila é ordenada por valor esperado
// e a etiqueta precisa dizer a mesma coisa que a ordem.
export default function PriorityBadge({ rank, total, large = false }) {
  const base = large ? 'px-2.5 py-1 text-sm' : ''
  const nivel = prioridadePorRank(rank, total)
  if (nivel === 'Alta')  return <span className={`badge badge-success ${base}`}>Alta</span>
  if (nivel === 'Média') return <span className={`badge badge-warning ${base}`}>Média</span>
  return <span className={`badge ${base}`} style={{ color: 'var(--text-2)', background: 'var(--raised)' }}>Baixa</span>
}
