export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
  const cls = `${base} rounded-full font-semibold inline-flex items-center gap-1`

  if (score >= 70) return (
    <span className={`${cls} bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/60`}>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
      Alta
    </span>
  )
  if (score >= 40) return (
    <span className={`${cls} bg-amber-50 text-amber-700 ring-1 ring-amber-200/60`}>
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
      Média
    </span>
  )
  return (
    <span className={`${cls} bg-slate-100 text-slate-500 ring-1 ring-slate-200/60`}>
      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block" />
      Baixa
    </span>
  )
}
