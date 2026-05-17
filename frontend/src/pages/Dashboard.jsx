import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import {
  Users, TrendingDown, BarChart2, Star,
  Download, RefreshCw, Search, Loader2,
} from 'lucide-react'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
import { useAnalysis } from '../context/AnalysisContext'
import StatCard from '../components/StatCard'
import PriorityBadge from '../components/PriorityBadge'

const AGING_ORDER = ['0-29 dias', '30-59 dias', '60-89 dias', '90-179 dias', '180+ dias']
const AGING_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#f97316', '#ef4444']
const CLUSTER_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#14b8a6']

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v)

const CustomBarTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      <p className="text-slate-600">Devedores: <span className="font-bold">{fmtNum(payload[0].value)}</span></p>
      {payload[1] && <p className="text-slate-600">Valor: <span className="font-bold">{fmtBRL(payload[1].value)}</span></p>}
    </div>
  )
}

export default function Dashboard() {
  const { result } = useAnalysis()
  const navigate = useNavigate()
  const dashRef = useRef()
  const [search, setSearch] = useState('')
  const [exporting, setExporting] = useState(false)

  if (!result) { navigate('/'); return null }

  const { resumo, distribuicao_aging, distribuicao_cluster, ranking_completo } = result

  const agingData = [...distribuicao_aging].sort(
    (a, b) => AGING_ORDER.indexOf(a.aging) - AGING_ORDER.indexOf(b.aging)
  )

  const prioritarios = ranking_completo.filter(d => d.score_recuperabilidade >= 70).length

  const filtered = search
    ? ranking_completo.filter(d =>
        d.nome?.toLowerCase().includes(search.toLowerCase()) ||
        d.cpf?.includes(search)
      )
    : ranking_completo

  const exportPDF = async () => {
    setExporting(true)
    try {
      const el = dashRef.current
      const canvas = await html2canvas(el, { scale: 1.5, useCORS: true, backgroundColor: '#f8fafc' })
      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF('l', 'mm', 'a4')
      const w = pdf.internal.pageSize.getWidth()
      const h = (canvas.height * w) / canvas.width
      const pageH = pdf.internal.pageSize.getHeight()

      if (h <= pageH) {
        pdf.addImage(imgData, 'PNG', 0, 0, w, h)
      } else {
        // multi-page: split at page height boundaries
        let yOffset = 0
        while (yOffset < h) {
          if (yOffset > 0) pdf.addPage()
          pdf.addImage(imgData, 'PNG', 0, -yOffset, w, h)
          yOffset += pageH
        }
      }
      pdf.save('mizan-relatorio.pdf')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">⚖</span>
          </div>
          <span className="font-bold text-slate-800">Mizan</span>
          <span className="text-slate-300 mx-1">/</span>
          <span className="text-slate-500 text-sm">Dashboard</span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Nova análise
          </button>
          <button
            onClick={exportPDF}
            disabled={exporting}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {exporting
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Exportando...</>
              : <><Download className="h-4 w-4" /> Exportar PDF</>}
          </button>
        </div>
      </header>

      {/* Content captured for PDF */}
      <main ref={dashRef} className="max-w-7xl mx-auto px-6 py-8">
        {/* Stat Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Total de Devedores"
            value={fmtNum(resumo.total_devedores)}
            icon={Users}
          />
          <StatCard
            label="Total em Risco"
            value={fmtBRL(resumo.total_em_risco)}
            sub="valor total da carteira"
            icon={TrendingDown}
          />
          <StatCard
            label="Score Médio"
            value={resumo.score_medio.toFixed(1)}
            sub="recuperabilidade (0–100)"
            icon={BarChart2}
          />
          <StatCard
            label="Devedores Prioritários"
            value={fmtNum(prioritarios)}
            sub="score ≥ 70"
            icon={Star}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-5 gap-6 mb-8">
          {/* Aging Bar Chart — 3/5 */}
          <div className="col-span-3 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-5">
              Distribuição por Aging
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={agingData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="aging"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomBarTooltip />} cursor={{ fill: '#f8fafc' }} />
                <Bar dataKey="total_devedores" radius={[4, 4, 0, 0]} maxBarSize={48}>
                  {agingData.map((_, i) => (
                    <Cell key={i} fill={AGING_COLORS[i % AGING_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 mt-4">
              {agingData.map((d, i) => (
                <div key={d.aging} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: AGING_COLORS[i] }} />
                  <span className="text-xs text-slate-500">{d.aging}</span>
                  <span className="text-xs text-slate-400">({fmtNum(d.total_devedores)})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Cluster Pie Chart — 2/5 */}
          <div className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-5">
              Perfis de Devedores
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={distribuicao_cluster}
                  dataKey="total_devedores"
                  nameKey="perfil_cluster"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  innerRadius={40}
                  paddingAngle={2}
                >
                  {distribuicao_cluster.map((_, i) => (
                    <Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 11 }}
                  formatter={(v, _, { payload }) => [fmtNum(v), payload.perfil_cluster]}
                />
              </PieChart>
            </ResponsiveContainer>

            {/* Legend manual */}
            <div className="mt-1 space-y-1.5">
              {distribuicao_cluster.map((d, i) => (
                <div key={d.perfil_cluster} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: CLUSTER_COLORS[i] }} />
                    <span className="text-slate-500 truncate">{d.perfil_cluster}</span>
                  </div>
                  <span className="text-slate-400 ml-2 shrink-0">{fmtNum(d.total_devedores)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Ranking de Recuperabilidade
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {fmtNum(filtered.length)} devedores{search ? ' encontrados' : ''}
              </p>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar por nome ou CPF..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="text-sm border border-slate-200 rounded-lg pl-9 pr-3 py-2 w-60 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div className="overflow-auto max-h-[480px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
                <tr>
                  {['#', 'Nome', 'CPF', 'Produto', 'Valor Dívida', 'Dias Atraso', 'Score', 'Prioridade'].map(col => (
                    <th
                      key={col}
                      className={`px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap
                        ${['Valor Dívida', 'Dias Atraso', 'Score'].includes(col) ? 'text-right' : 'text-left'}
                        ${col === 'Prioridade' ? 'text-center' : ''}`}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map((d) => (
                  <tr
                    key={d.rank}
                    onClick={() => navigate(`/devedor/${d.rank}`)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs w-10">{d.rank}</td>
                    <td className="px-4 py-3 font-medium text-slate-800 group-hover:text-blue-700 transition-colors">
                      {d.nome}
                    </td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs whitespace-nowrap">{d.cpf}</td>
                    <td className="px-4 py-3">
                      <span className="capitalize text-slate-600">{d.produto}</span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 whitespace-nowrap font-mono text-xs">
                      {fmtBRL(d.valor_divida)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">
                      {fmtNum(d.dias_em_atraso)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-bold text-sm ${
                        d.score_recuperabilidade >= 70 ? 'text-emerald-600' :
                        d.score_recuperabilidade >= 40 ? 'text-amber-600' : 'text-slate-400'
                      }`}>
                        {d.score_recuperabilidade}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <PriorityBadge score={d.score_recuperabilidade} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}
