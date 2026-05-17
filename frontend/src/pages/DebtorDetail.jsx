import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import PriorityBadge from '../components/PriorityBadge'

const fmtBRL = (v) => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
  : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function DataRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-800">{value ?? '—'}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">{title}</h3>
      {children}
    </div>
  )
}

export default function DebtorDetail() {
  const { rank } = useParams()
  const navigate = useNavigate()
  const { result } = useAnalysis()

  if (!result) { navigate('/'); return null }

  const d = result.ranking_completo.find(x => x.rank === Number(rank))
  if (!d) { navigate('/dashboard'); return null }

  const score = d.score_recuperabilidade
  const scoreColor = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#94a3b8'
  const circumference = 2 * Math.PI * 38  // r=38 in a 100x100 viewBox
  const dash = (score / 100) * circumference

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center gap-3 sticky top-0 z-20">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors px-2 py-1.5 rounded-lg hover:bg-slate-100"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </button>
        <span className="text-slate-200">|</span>
        <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center">
          <span className="text-white text-xs font-bold">⚖</span>
        </div>
        <span className="font-bold text-slate-800 text-sm">Mizan</span>
        <span className="text-slate-300 text-sm">/</span>
        <span className="text-slate-400 text-sm truncate max-w-xs">Dashboard</span>
        <span className="text-slate-300 text-sm">/</span>
        <span className="text-slate-600 text-sm font-medium truncate">{d.nome}</span>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">{d.nome}</h1>
            <p className="text-slate-400 font-mono text-sm mt-1">{d.cpf}</p>
            <p className="text-slate-500 text-sm mt-1 capitalize">{d.produto} · {d.uf} · Rank #{d.rank}</p>
          </div>
          <PriorityBadge score={score} large />
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Score visual — col 1 */}
          <div className="col-span-1 flex flex-col gap-6">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col items-center">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-5 text-center">
                Score de Recuperabilidade
              </p>

              {/* Circular progress */}
              <div className="relative w-36 h-36">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle cx="50" cy="50" r="38" fill="none" stroke="#f1f5f9" strokeWidth="8" />
                  <circle
                    cx="50" cy="50" r="38"
                    fill="none"
                    stroke={scoreColor}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    style={{ transition: 'stroke-dasharray 0.8s ease' }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-slate-800">{score}</span>
                  <span className="text-xs text-slate-400 mt-0.5">/ 100</span>
                </div>
              </div>

              {/* Score bar */}
              <div className="w-full mt-5">
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${score}%`, backgroundColor: scoreColor }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                  <span>0</span>
                  <span>100</span>
                </div>
              </div>

              <p className="text-xs text-slate-500 mt-4 text-center leading-relaxed">
                {d.perfil_cluster}
              </p>
            </div>

            {/* Cluster info */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Perfil IA</h3>
              <div
                className="text-center py-3 rounded-lg text-sm font-medium"
                style={{ backgroundColor: `${scoreColor}15`, color: scoreColor }}
              >
                {d.perfil_cluster}
              </div>
              <p className="text-xs text-slate-400 mt-3 text-center">
                Cluster #{d.cluster_id ?? '—'} identificado por machine learning
              </p>
            </div>
          </div>

          {/* Data columns — col 2-3 */}
          <div className="col-span-2 flex flex-col gap-4">
            <Section title="Dados Cadastrais">
              <DataRow label="Nome completo" value={d.nome} />
              <DataRow label="CPF" value={d.cpf} />
              <DataRow label="Produto" value={d.produto} />
              <DataRow label="Status" value={d.status} />
              <DataRow label="UF" value={d.uf} />
            </Section>

            <Section title="Dados Financeiros">
              <DataRow label="Valor da Dívida" value={fmtBRL(d.valor_divida)} />
              <DataRow label="Renda Estimada" value={fmtBRL(d.renda_estimada)} />
              <DataRow label="Dias em Atraso" value={fmtNum(d.dias_em_atraso)} />
              {d.comprometimento_renda != null && (
                <DataRow label="Comprometimento de Renda" value={fmtPct(d.comprometimento_renda)} />
              )}
            </Section>

            {(d.tentativas_contato != null || d.promessa_quebrada != null) && (
              <Section title="Dados de Cobrança">
                {d.tentativas_contato != null && (
                  <DataRow label="Tentativas de Contato" value={fmtNum(d.tentativas_contato)} />
                )}
                {d.promessa_quebrada != null && (
                  <DataRow
                    label="Promessa Quebrada"
                    value={
                      <span className={String(d.promessa_quebrada).toLowerCase() === 'true' || d.promessa_quebrada === true
                        ? 'text-red-500' : 'text-emerald-600'}>
                        {String(d.promessa_quebrada).toLowerCase() === 'true' || d.promessa_quebrada === true ? 'Sim' : 'Não'}
                      </span>
                    }
                  />
                )}
              </Section>
            )}

            {/* Score bar detail */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-4">
                Faixas de Recuperabilidade
              </h3>
              <div className="space-y-2.5">
                {[
                  { label: 'Alta (≥ 70)', min: 70, max: 100, color: '#10b981' },
                  { label: 'Média (40–69)', min: 40, max: 69, color: '#f59e0b' },
                  { label: 'Baixa (< 40)', min: 0, max: 39, color: '#94a3b8' },
                ].map(({ label, min, max, color }) => {
                  const active = score >= min && score <= max
                  return (
                    <div key={label} className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${active ? 'bg-slate-50 ring-1 ring-slate-200' : ''}`}>
                      <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                      <span className={`text-sm ${active ? 'font-semibold text-slate-800' : 'text-slate-400'}`}>
                        {label}
                      </span>
                      {active && (
                        <span className="ml-auto text-xs font-bold" style={{ color }}>{score}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
