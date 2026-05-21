export default function StatCard({ label, value, sub, icon: Icon, accent = 'default' }) {
  const iconCls = {
    default: 'text-slate-400 bg-slate-50',
    blue:    'text-blue-500 bg-blue-50',
    emerald: 'text-emerald-500 bg-emerald-50',
    amber:   'text-amber-500 bg-amber-50',
    violet:  'text-violet-500 bg-violet-50',
  }[accent] ?? 'text-slate-400 bg-slate-50'

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_1px_4px_rgba(15,23,42,0.06)] p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">{label}</p>
        {Icon && (
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconCls}`}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-800 leading-none tracking-tight">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-1.5">{sub}</p>}
      </div>
    </div>
  )
}
