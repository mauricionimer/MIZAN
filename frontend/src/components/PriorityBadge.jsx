export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'
  const cls = `${base} rounded-full font-semibold inline-block`

  if (score >= 70) return <span className={`${cls} bg-emerald-100 text-emerald-700`}>Alta</span>
  if (score >= 40) return <span className={`${cls} bg-amber-100 text-amber-700`}>Média</span>
  return <span className={`${cls} bg-slate-100 text-slate-500`}>Baixa</span>
}
