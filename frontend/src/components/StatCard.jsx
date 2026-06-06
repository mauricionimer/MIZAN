const ACCENT_COLOR = {
  default: 'transparent',
  blue:    '#3b82f6',
  emerald: '#10b981',
  amber:   '#f59e0b',
  violet:  '#8b5cf6',
}

export default function StatCard({ label, value, sub, icon: Icon, accent = 'default' }) {
  const color = ACCENT_COLOR[accent] ?? 'transparent'

  return (
    <div className="px-6 py-5 flex flex-col gap-3"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.05)',
        borderLeft: `2px solid ${color}`,
        borderRadius: '0.75rem',
      }}>
      <div className="flex items-center justify-between">
        <p style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: '#4b5563',
        }}>
          {label}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5" style={{ color: '#374151' }} />}
      </div>
      <div>
        <p className="text-[1.75rem] font-semibold tracking-tight leading-none" style={{ color: '#f0f0f5' }}>
          {value}
        </p>
        {sub && (
          <p className="text-xs mt-1.5" style={{ color: '#374151' }}>{sub}</p>
        )}
      </div>
    </div>
  )
}
