const ACCENT_COLOR = {
  default: 'transparent',
  blue:    'var(--info)',
  emerald: 'var(--ok)',
  amber:   'var(--warn)',
  violet:  '#5B3FB8',
}

export default function StatCard({ label, value, sub, icon: Icon, accent = 'default' }) {
  const color = ACCENT_COLOR[accent] ?? 'transparent'

  return (
    <div className="px-6 py-5 flex flex-col gap-3"
      style={{
        background: 'rgba(22,32,60,0.02)',
        border: '1px solid rgba(22,32,60,0.04)',
        borderLeft: `2px solid ${color}`,
        borderRadius: '0.75rem',
      }}>
      <div className="flex items-center justify-between">
        <p style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-3)',
        }}>
          {label}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5" style={{ color: 'var(--text-muted)' }} />}
      </div>
      <div>
        <p className="text-[1.75rem] font-semibold tracking-tight leading-none" style={{ color: 'var(--text-1)' }}>
          {value}
        </p>
        {sub && (
          <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>{sub}</p>
        )}
      </div>
    </div>
  )
}
