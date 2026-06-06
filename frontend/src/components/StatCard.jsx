const ACCENT = {
  default: { bar: '#475569', iconBg: 'rgba(255,255,255,0.06)',  iconTx: 'text-slate-400'   },
  blue:    { bar: '#1d6aff', iconBg: 'rgba(29,106,255,0.12)',   iconTx: 'text-blue-400'    },
  emerald: { bar: '#10b981', iconBg: 'rgba(16,185,129,0.12)',   iconTx: 'text-emerald-400' },
  amber:   { bar: '#f59e0b', iconBg: 'rgba(245,158,11,0.12)',   iconTx: 'text-amber-400'   },
  violet:  { bar: '#8b5cf6', iconBg: 'rgba(139,92,246,0.12)',   iconTx: 'text-violet-400'  },
}

export default function StatCard({ label, value, sub, icon: Icon, accent = 'default' }) {
  const { bar, iconBg, iconTx } = ACCENT[accent] ?? ACCENT.default

  return (
    <div className="relative rounded-2xl overflow-hidden"
      style={{
        background: '#0d1628',
        border: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30)',
      }}>
      <div className="absolute top-0 left-0 right-0 h-[2px]" style={{ backgroundColor: bar }} />
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-widest leading-tight" style={{ color: '#5a7499' }}>
            {label}
          </p>
          {Icon && (
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: iconBg }}>
              <Icon className={`h-5 w-5 ${iconTx}`} />
            </div>
          )}
        </div>
        <div>
          <p className="text-2xl font-extrabold text-white leading-none tracking-tight">{value}</p>
          {sub && <p className="text-xs mt-1.5 leading-snug" style={{ color: '#5a7499' }}>{sub}</p>}
        </div>
      </div>
    </div>
  )
}
