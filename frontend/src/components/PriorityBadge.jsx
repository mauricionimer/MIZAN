export default function PriorityBadge({ score, large = false }) {
  const base = large ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
  const cls = `${base} rounded-full font-semibold inline-flex items-center gap-1`

  if (score >= 70) return (
    <span className={`${cls} bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20`}>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
      Alta
    </span>
  )
  if (score >= 40) return (
    <span className={`${cls} bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20`}>
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
      Média
    </span>
  )
  return (
    <span className={`${cls} bg-white/5 text-[#8fa3c8] ring-1 ring-white/10`}>
      <span className="w-1.5 h-1.5 rounded-full bg-[#5a7499] inline-block" />
      Baixa
    </span>
  )
}
