export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-2.5 py-1 text-sm' : 'px-2 py-0.5 text-xs'
  const cls = `${base} rounded-md font-medium inline-flex items-center gap-1.5 border`

  if (score >= 70) return (
    <span className={`${cls} bg-[var(--ok)]/8 text-[var(--ok)] border-emerald-500/20`}>
      <span className="w-1 h-1 rounded-full bg-[var(--ok)] inline-block shrink-0" />
      Alta
    </span>
  )
  if (score >= 40) return (
    <span className={`${cls} bg-amber-500/8 text-[var(--warn)] border-amber-500/20`}>
      <span className="w-1 h-1 rounded-full bg-[var(--warn)] inline-block shrink-0" />
      Média
    </span>
  )
  return (
    <span className={`${cls} border-white/8`} style={{ background: 'rgba(22,32,60,0.03)', color: 'var(--text-3)' }}>
      <span className="w-1 h-1 rounded-full inline-block shrink-0" style={{ background: 'var(--text-muted)' }} />
      Baixa
    </span>
  )
}
