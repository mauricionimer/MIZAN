const ACCENT = {
  default: { grad: 'from-slate-50 to-white',    top: 'bg-slate-300',    iconBg: 'bg-slate-100',    iconTx: 'text-slate-500'   },
  blue:    { grad: 'from-blue-50 to-white',     top: 'bg-blue-500',     iconBg: 'bg-blue-100',     iconTx: 'text-blue-600'    },
  emerald: { grad: 'from-emerald-50 to-white',  top: 'bg-emerald-500',  iconBg: 'bg-emerald-100',  iconTx: 'text-emerald-600' },
  amber:   { grad: 'from-amber-50 to-white',    top: 'bg-amber-400',    iconBg: 'bg-amber-100',    iconTx: 'text-amber-600'   },
  violet:  { grad: 'from-violet-50 to-white',   top: 'bg-violet-500',   iconBg: 'bg-violet-100',   iconTx: 'text-violet-600'  },
}

export default function StatCard({ label, value, sub, icon: Icon, accent = 'default' }) {
  const { grad, top, iconBg, iconTx } = ACCENT[accent] ?? ACCENT.default

  return (
    <div className={`relative bg-gradient-to-b ${grad} rounded-2xl border border-slate-100 overflow-hidden`}
      style={{ boxShadow: '0 2px 8px rgba(15,23,42,0.07), 0 1px 2px rgba(15,23,42,0.04)' }}>
      <div className={`absolute top-0 left-0 right-0 h-[3px] ${top}`} />
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest leading-tight">{label}</p>
          {Icon && (
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
              <Icon className={`h-5 w-5 ${iconTx}`} />
            </div>
          )}
        </div>
        <div>
          <p className="text-2xl font-extrabold text-slate-900 leading-none tracking-tight">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1.5 leading-snug">{sub}</p>}
        </div>
      </div>
    </div>
  )
}
