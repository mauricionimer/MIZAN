export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-2.5 py-1 text-sm' : 'px-2 py-0.5 text-xs'
  const cls = `${base} rounded-md font-medium inline-flex items-center gap-1.5 border`

  if (score >= 70) return (
    <span className={`${cls} bg-emerald-500/8 text-emerald-300 border-emerald-500/20`}>
      <span className="w-1 h-1 rounded-full bg-emerald-400 inline-block shrink-0" />
      Alta
    </span>
  )
  if (score >= 40) return (
    <span className={`${cls} bg-amber-500/8 text-amber-300 border-amber-500/20`}>
      <span className="w-1 h-1 rounded-full bg-amber-400 inline-block shrink-0" />
      Média
    </span>
  )
  return (
    <span className={`${cls} border-line`} style={{ background: 'var(--raise-1)', color: 'var(--ink-2)' }}>
      <span className="w-1 h-1 rounded-full inline-block shrink-0" style={{ background: 'var(--ink-4)' }} />
      Baixa
    </span>
  )
}
