import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart,
} from 'recharts'
import {
  LayoutDashboard, Wallet, Banknote, ShieldCheck, Settings,
  Bell, TrendingUp, TrendingDown, FileText, ArrowUpRight, ArrowDownRight,
  Search, LogOut,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

/* ───────────────────────── Formatters ───────────────────────── */
const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtBRLk = (v) => {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1).replace('.', ',')}M`
  if (v >= 1_000) return `R$ ${Math.round(v / 1_000)}k`
  return fmtBRL(v)
}

/* ───────────────────────── Mock data ───────────────────────── */
const EVOLUCAO = [
  { mes: 'Jan', valor: 3_120_000 },
  { mes: 'Fev', valor: 3_340_000 },
  { mes: 'Mar', valor: 3_180_000 },
  { mes: 'Abr', valor: 3_620_000 },
  { mes: 'Mai', valor: 3_910_000 },
  { mes: 'Jun', valor: 4_280_000 },
]

const CONTRATOS = [
  { cliente: 'Marina Albuquerque', valor: 18_400, status: 'em_dia',   venc: '12/06/2026' },
  { cliente: 'Rodrigo Tavares',    valor: 42_900, status: 'atrasado', venc: '02/06/2026' },
  { cliente: 'Construtora Onix',   valor: 128_500, status: 'em_dia',  venc: '20/06/2026' },
  { cliente: 'Helena Costa',       valor: 7_250,  status: 'quitado',  venc: '28/05/2026' },
  { cliente: 'Paulo Menezes',      valor: 33_700, status: 'atrasado', venc: '30/05/2026' },
  { cliente: 'Verde Logística',    valor: 96_120, status: 'em_dia',   venc: '15/06/2026' },
  { cliente: 'Camila Ferraz',      valor: 12_800, status: 'quitado',  venc: '22/05/2026' },
  { cliente: 'Atlas Comércio',     valor: 54_300, status: 'em_dia',   venc: '18/06/2026' },
]

const NAV = [
  { id: 'dashboard',  label: 'Dashboard',     icon: LayoutDashboard },
  { id: 'carteira',   label: 'Carteira',      icon: Wallet },
  { id: 'pagamentos', label: 'Pagamentos',    icon: Banknote },
  { id: 'auditoria',  label: 'Auditoria',     icon: ShieldCheck },
  { id: 'config',     label: 'Configurações', icon: Settings },
]

/* ───────────────────────── Status badge ───────────────────────── */
function StatusBadge({ status }) {
  const cfg = {
    em_dia:   { label: 'Em dia',   cls: 'bg-blue-500/10 text-blue-300 border-blue-500/30' },
    atrasado: { label: 'Atrasado', cls: 'bg-red-500/10 text-red-300 border-red-500/30' },
    quitado:  { label: 'Quitado',  cls: 'bg-slate-500/10 text-slate-300 border-slate-500/30' },
  }[status]
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-md border ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

/* ───────────────────────── KPI card ───────────────────────── */
function KpiCard({ label, value, delta, deltaDir = 'up', danger = false, icon: Icon }) {
  const positive = deltaDir === 'up'
  const DeltaIcon = positive ? ArrowUpRight : ArrowDownRight
  return (
    <div className="group relative rounded-xl border border-white/[0.07] bg-[#111827] p-5 transition-all duration-200 hover:border-blue-500/50 hover:shadow-[0_0_0_1px_rgba(59,130,246,0.25),0_8px_28px_-8px_rgba(59,130,246,0.35)]">
      <div className="flex items-start justify-between">
        <p className="text-[13px] font-light text-slate-400">{label}</p>
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.04] text-slate-400 transition-colors group-hover:text-blue-400">
          <Icon className="h-[18px] w-[18px]" />
        </div>
      </div>
      <p className={`mt-3 text-2xl font-bold tracking-tight ${danger ? 'text-red-400' : 'text-white'}`}>
        {value}
      </p>
      {delta && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${positive ? 'text-blue-400' : 'text-red-400'}`}>
            <DeltaIcon className="h-3.5 w-3.5" />
            {delta}
          </span>
          <span className="text-xs font-light text-slate-500">vs. mês anterior</span>
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Chart tooltip ───────────────────────── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-white/10 bg-[#0a0f1e] px-3.5 py-2.5 shadow-xl">
      <p className="text-xs font-light text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-white">{fmtBRL(payload[0].value)}</p>
    </div>
  )
}

/* ───────────────────────── Page ───────────────────────── */
export default function PainelCarteira() {
  const navigate = useNavigate()
  const { usuario, empresaConfig, logout } = useAuth()
  const [ativo, setAtivo] = useState('dashboard')

  const nomeEmpresa = empresaConfig?.nome_exibicao || 'Mizan'
  const nomeUser = usuario?.nome || 'Operador'
  const iniciais = nomeUser.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  return (
    <div className="flex min-h-screen bg-[#0a0f1e] font-sans text-slate-200">
      {/* ───── Sidebar ───── */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-white/[0.07] bg-[#0a0f1e]">
        <div className="flex h-16 items-center gap-2.5 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <span className="text-sm font-bold text-white">M</span>
          </div>
          <span className="text-[15px] font-bold tracking-tight text-white">{nomeEmpresa}</span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-3 py-4">
          {NAV.map(({ id, label, icon: Icon }) => {
            const isActive = ativo === id
            return (
              <button
                key={id}
                onClick={() => setAtivo(id)}
                className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-white/[0.04] text-white'
                    : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-blue-500" />
                )}
                <Icon className={`h-[18px] w-[18px] ${isActive ? 'text-blue-400' : ''}`} />
                {label}
              </button>
            )
          })}
        </nav>

        <div className="border-t border-white/[0.07] p-3">
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Sair
          </button>
        </div>
      </aside>

      {/* ───── Main column ───── */}
      <div className="flex flex-1 flex-col pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-white/[0.07] bg-[#0a0f1e]/80 px-8 backdrop-blur-xl">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-white">{nomeEmpresa}</span>
            <span className="text-slate-600">/</span>
            <span className="font-light text-slate-400">Visão da carteira</span>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                placeholder="Buscar contrato..."
                className="h-9 w-64 rounded-lg border border-white/[0.07] bg-[#111827] pl-9 pr-3 text-sm text-slate-200 placeholder-slate-500 transition-colors focus:border-blue-500/50 focus:outline-none"
              />
            </div>

            <button className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-[#111827] text-slate-400 transition-colors hover:text-white">
              <Bell className="h-[18px] w-[18px]" />
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-blue-500" />
            </button>

            <div className="flex items-center gap-2.5 border-l border-white/[0.07] pl-4">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight text-white">{nomeUser}</p>
                <p className="text-xs font-light text-slate-500">{usuario?.email || 'usuario@mizan.app'}</p>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                {iniciais}
              </div>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 px-8 py-8">
          <div className="mb-7">
            <h1 className="text-xl font-bold tracking-tight text-white">Dashboard</h1>
            <p className="mt-1 text-sm font-light text-slate-400">
              Resumo da carteira de crédito e recuperação no período atual
            </p>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Total em Carteira" value={fmtBRL(4_280_000)} delta="9,4%" deltaDir="up" icon={Wallet} />
            <KpiCard label="Inadimplência" value="12,8%" delta="1,2%" deltaDir="up" danger icon={TrendingDown} />
            <KpiCard label="Pagamentos Confirmados" value={fmtBRL(842_300)} delta="6,1%" deltaDir="up" icon={Banknote} />
            <KpiCard label="Contratos Ativos" value="1.284" delta="3,8%" deltaDir="up" icon={FileText} />
          </div>

          {/* Line chart */}
          <section className="mt-6 rounded-xl border border-white/[0.07] bg-[#111827] p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">Evolução da Carteira</h2>
                <p className="mt-0.5 text-xs font-light text-slate-400">Valor total nos últimos 6 meses</p>
              </div>
              <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-300">
                <TrendingUp className="h-3.5 w-3.5" /> +37,2% no período
              </span>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={EVOLUCAO} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="fillCarteira" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis
                    dataKey="mes"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#64748b', fontSize: 12 }}
                    dy={8}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#64748b', fontSize: 12 }}
                    tickFormatter={fmtBRLk}
                    width={64}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(59,130,246,0.3)', strokeWidth: 1 }} />
                  <Area
                    type="monotone"
                    dataKey="valor"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fill="url(#fillCarteira)"
                    dot={false}
                    activeDot={{ r: 5, fill: '#3b82f6', stroke: '#0a0f1e', strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Recent contracts table */}
          <section className="mt-6 overflow-hidden rounded-xl border border-white/[0.07] bg-[#111827]">
            <div className="flex items-center justify-between border-b border-white/[0.07] px-6 py-4">
              <div>
                <h2 className="text-sm font-semibold text-white">Contratos Recentes</h2>
                <p className="mt-0.5 text-xs font-light text-slate-400">Últimos contratos movimentados na carteira</p>
              </div>
              <button className="rounded-md border border-white/[0.07] px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-blue-500/50 hover:text-white">
                Ver todos
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.07] text-left">
                    <th className="px-6 py-3 text-xs font-medium uppercase tracking-wider text-slate-500">Cliente</th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">Valor</th>
                    <th className="px-6 py-3 text-xs font-medium uppercase tracking-wider text-slate-500">Status</th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">Vencimento</th>
                  </tr>
                </thead>
                <tbody>
                  {CONTRATOS.map((c, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/[0.04] transition-colors last:border-0 hover:bg-white/[0.025]"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/[0.05] text-[11px] font-semibold text-slate-300">
                            {c.cliente.split(' ').map(p => p[0]).slice(0, 2).join('')}
                          </div>
                          <span className="font-medium text-slate-100">{c.cliente}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right font-medium tabular-nums text-slate-200">{fmtBRL(c.valor)}</td>
                      <td className="px-6 py-4"><StatusBadge status={c.status} /></td>
                      <td className="px-6 py-4 text-right font-light tabular-nums text-slate-400">{c.venc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
