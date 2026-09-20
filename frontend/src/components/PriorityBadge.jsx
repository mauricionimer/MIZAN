// Badge de prioridade — cor + texto, nunca só cor (brief, seção 5).
export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-2.5 py-1 text-sm' : ''
  if (score >= 70) return <span className={`badge badge-success ${base}`}>Alta</span>
  if (score >= 40) return <span className={`badge badge-warning ${base}`}>Média</span>
  return <span className={`badge ${base}`} style={{ color: 'var(--text-2)', background: 'var(--raised)' }}>Baixa</span>
}
