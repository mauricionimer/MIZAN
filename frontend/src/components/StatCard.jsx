// KPI conforme o brief (seção 5): card, rótulo em maiúsculas pequeno, número
// grande com tabular-nums e ícone tingido no canto. Sem legenda descritiva
// embaixo do número — a seção 7 do brief pede a remoção dessas frases.
const ACCENT = {
  default: 'var(--text-muted)',
  blue:    'var(--royal)',
  emerald: 'var(--success)',
  amber:   'var(--warning)',
  violet:  'var(--accent-text)',
}

export default function StatCard({ label, value, icon: Icon, accent = 'default' }) {
  const cor = ACCENT[accent] ?? ACCENT.default

  return (
    <div className="card px-6 py-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-muted)',
        }}>
          {label}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5" style={{ color: cor }} />}
      </div>
      <p className="tnum text-[1.75rem] font-semibold tracking-tight leading-none"
        style={{ color: 'var(--text)' }}>
        {value}
      </p>
    </div>
  )
}
