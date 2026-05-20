import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts'
import {
  ArrowLeft, RefreshCw, Loader2, Zap, TrendingUp, Activity, Award, LogOut,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const CANAL_LABELS = { whatsapp: 'WhatsApp', telefone: 'Ligação', carta: 'Carta / E-mail' }
const OFERTA_LABELS = {
  avista_10pct:   '10% à vista',
  parcelado_4x:   '4x sem juros',
  desconto_30pct: '30% à vista',
  parcelado_12x:  '12x',
}
const CANAL_COLORS  = ['#25D366', '#3b82f6', '#f59e0b']
const OFERTA_COLORS = ['#10b981', '#6366f1', '#f97316', '#8b5cf6']
const FASE_META = {
  exploração_inicial: { label: 'Exploração inicial',  color: 'slate',   dot: 'bg-slate-400' },
  aprendendo:         { label: 'Aprendendo',           color: 'amber',   dot: 'bg-amber-400' },
  calibrado:          { label: 'Calibrado',            color: 'emerald', dot: 'bg-emerald-500' },
}

const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function StatCard({ label, value, sub, icon: Icon, accent = 'blue' }) {
  const colors = {
    blue:    'text-blue-600 bg-blue-50',
    emerald: 'text-emerald-600 bg-emerald-50',
    amber:   'text-amber-600 bg-amber-50',
    slate:   'text-slate-600 bg-slate-100',
  }
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex gap-4 items-start">
      <div className={`rounded-lg p-2.5 ${colors[accent]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
        <p className="text-xl font-bold text-slate-800 mt-0.5 leading-tight">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      <p className="text-slate-600">Taxa de recuperação: <span className="font-bold text-emerald-600">{fmtPct(payload[0].value / 100)}</span></p>
      {payload[0].payload.tentativas != null && (
        <p className="text-slate-400 mt-0.5">{payload[0].payload.tentativas} interações</p>
      )}
    </div>
  )
}

export default function BanditDashboard() {
  const navigate = useNavigate()
  const { token, usuario, logout } = useAuth()
  const [dados, setDados]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro]       = useState('')

  async function carregar() {
    setLoading(true)
    setErro('')
    try {
      const res = await fetch(`${API_URL}/admin/bandit/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setDados(await res.json())
    } catch (e) {
      setErro('Não foi possível carregar os dados do bandit. Verifique se o backend está rodando.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { carregar() }, [])

  // Agrega por canal
  const porCanal = useMemo(() => {
    if (!dados) return []
    const canais = {}
    for (const a of dados.acoes) {
      if (!canais[a.canal]) canais[a.canal] = { tentativas: 0, recompensa_total: 0, count_com_dados: 0 }
      canais[a.canal].tentativas += a.n_tentativas
      if (a.recompensa_media != null) {
        canais[a.canal].recompensa_total  += a.recompensa_media * a.n_tentativas
        canais[a.canal].count_com_dados   += a.n_tentativas
      }
    }
    return Object.entries(canais).map(([canal, v]) => ({
      label:      CANAL_LABELS[canal] ?? canal,
      taxa:       v.count_com_dados > 0 ? +(v.recompensa_total / v.count_com_dados * 100).toFixed(2) : null,
      tentativas: v.tentativas,
    }))
  }, [dados])

  // Agrega por oferta
  const porOferta = useMemo(() => {
    if (!dados) return []
    const ofertas = {}
    for (const a of dados.acoes) {
      if (!ofertas[a.oferta]) ofertas[a.oferta] = { tentativas: 0, recompensa_total: 0, count_com_dados: 0 }
      ofertas[a.oferta].tentativas += a.n_tentativas
      if (a.recompensa_media != null) {
        ofertas[a.oferta].recompensa_total  += a.recompensa_media * a.n_tentativas
        ofertas[a.oferta].count_com_dados   += a.n_tentativas
      }
    }
    return Object.entries(ofertas).map(([oferta, v]) => ({
      label:      OFERTA_LABELS[oferta] ?? oferta,
      taxa:       v.count_com_dados > 0 ? +(v.recompensa_total / v.count_com_dados * 100).toFixed(2) : null,
      tentativas: v.tentativas,
    }))
  }, [dados])

  // Ranking das 12 combinações
  const rankingAcoes = useMemo(() => {
    if (!dados) return []
    return [...dados.acoes].sort((a, b) => {
      if (a.recompensa_media == null && b.recompensa_media == null) return 0
      if (a.recompensa_media == null) return 1
      if (b.recompensa_media == null) return -1
      return b.recompensa_media - a.recompensa_media
    })
  }, [dados])

  const melhorCanal  = porCanal.reduce((m, c)  => (c.taxa ?? -1) > (m?.taxa ?? -1) ? c : m, null)
  const melhorOferta = porOferta.reduce((m, o) => (o.taxa ?? -1) > (m?.taxa ?? -1) ? o : m, null)
  const fase = dados ? (FASE_META[dados.fase] ?? FASE_META['aprendendo']) : null

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
          <span className="text-slate-500 text-sm">Performance do Bandit</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={carregar}
            disabled={loading}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Atualizar
          </button>
          <span className="text-xs text-slate-400 hidden sm:block">{usuario?.nome}</span>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Voltar
          </button>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-50"
          >
            <LogOut className="h-3.5 w-3.5" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* Loading */}
        {loading && !dados && (
          <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">Carregando dados do bandit...</p>
          </div>
        )}

        {/* Erro */}
        {erro && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            {erro}
          </div>
        )}

        {dados && (
          <>
            {/* Cabeçalho com fase */}
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-bold text-slate-800">Performance do Bandit LinUCB</h1>
                <p className="text-sm text-slate-500 mt-1">
                  Quais canais e ofertas estão gerando mais pagamentos
                </p>
              </div>
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium ${
                dados.fase === 'calibrado'         ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                dados.fase === 'aprendendo'        ? 'bg-amber-50 border-amber-200 text-amber-700' :
                                                     'bg-slate-100 border-slate-200 text-slate-600'
              }`}>
                <span className={`w-2 h-2 rounded-full ${fase?.dot}`} />
                {fase?.label}
              </div>
            </div>

            {/* Stat cards */}
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                label="Total de interações"
                value={dados.total_interacoes.toLocaleString('pt-BR')}
                sub="feedbacks registrados no bandit"
                icon={Activity}
                accent="blue"
              />
              <StatCard
                label="Ações disponíveis"
                value="12"
                sub="3 canais × 4 ofertas"
                icon={Zap}
                accent="slate"
              />
              <StatCard
                label="Melhor canal"
                value={melhorCanal?.taxa != null ? melhorCanal.label : '—'}
                sub={melhorCanal?.taxa != null ? `${fmtPct(melhorCanal.taxa / 100)} de recuperação` : 'sem dados ainda'}
                icon={TrendingUp}
                accent="emerald"
              />
              <StatCard
                label="Melhor oferta"
                value={melhorOferta?.taxa != null ? melhorOferta.label : '—'}
                sub={melhorOferta?.taxa != null ? `${fmtPct(melhorOferta.taxa / 100)} de recuperação` : 'sem dados ainda'}
                icon={Award}
                accent="amber"
              />
            </div>

            {/* Gráficos por canal e por oferta */}
            <div className="grid grid-cols-2 gap-6">

              {/* Por canal */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-5">
                  Taxa de recuperação por canal
                </h3>
                {porCanal.every(c => c.taxa == null) ? (
                  <div className="flex items-center justify-center h-40 text-slate-300 text-sm">
                    Sem dados — registre feedbacks para ver resultados
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={porCanal} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
                      <Bar dataKey="taxa" radius={[4, 4, 0, 0]} maxBarSize={56}>
                        {porCanal.map((_, i) => <Cell key={i} fill={CANAL_COLORS[i % CANAL_COLORS.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                <div className="flex flex-wrap gap-3 mt-3">
                  {porCanal.map((c, i) => (
                    <div key={c.label} className="flex items-center gap-1.5 text-xs text-slate-500">
                      <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CANAL_COLORS[i] }} />
                      {c.label}
                      <span className="text-slate-300">({c.tentativas} int.)</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Por oferta */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-5">
                  Taxa de recuperação por oferta
                </h3>
                {porOferta.every(o => o.taxa == null) ? (
                  <div className="flex items-center justify-center h-40 text-slate-300 text-sm">
                    Sem dados — registre feedbacks para ver resultados
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={porOferta} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
                      <Bar dataKey="taxa" radius={[4, 4, 0, 0]} maxBarSize={56}>
                        {porOferta.map((_, i) => <Cell key={i} fill={OFERTA_COLORS[i % OFERTA_COLORS.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                <div className="flex flex-wrap gap-3 mt-3">
                  {porOferta.map((o, i) => (
                    <div key={o.label} className="flex items-center gap-1.5 text-xs text-slate-500">
                      <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: OFERTA_COLORS[i] }} />
                      {o.label}
                      <span className="text-slate-300">({o.tentativas} int.)</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Ranking das 12 combinações */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Ranking das 12 combinações
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Ordenado por taxa de recuperação média</p>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    {['#', 'Canal', 'Oferta', 'Interações', 'Taxa de recuperação', 'Barra'].map((h, i) => (
                      <th key={h} className={`px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap ${i >= 3 ? 'text-right' : 'text-left'}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {rankingAcoes.map((a, i) => {
                    const pct = a.recompensa_media != null ? a.recompensa_media * 100 : null
                    const isTop = i === 0 && pct != null
                    return (
                      <tr key={a.id} className={isTop ? 'bg-emerald-50/50' : 'hover:bg-slate-50'}>
                        <td className="px-5 py-3 text-slate-400 font-mono text-xs w-8">{i + 1}</td>
                        <td className="px-5 py-3">
                          <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
                            a.canal === 'whatsapp' ? 'bg-green-100 text-green-700' :
                            a.canal === 'telefone' ? 'bg-blue-100 text-blue-700'  :
                                                     'bg-amber-100 text-amber-700'
                          }`}>
                            {CANAL_LABELS[a.canal] ?? a.canal}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-slate-600 text-sm">{OFERTA_LABELS[a.oferta] ?? a.oferta}</td>
                        <td className="px-5 py-3 text-right text-slate-500 font-mono text-xs">{a.n_tentativas}</td>
                        <td className="px-5 py-3 text-right">
                          <span className={`font-bold text-sm ${
                            pct == null          ? 'text-slate-300' :
                            pct >= 50            ? 'text-emerald-600' :
                            pct >= 25            ? 'text-amber-600'   : 'text-red-500'
                          }`}>
                            {pct != null ? `${pct.toFixed(1)}%` : '—'}
                          </span>
                        </td>
                        <td className="px-5 py-3 w-36">
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            {pct != null && (
                              <div
                                className={`h-full rounded-full transition-all ${
                                  pct >= 50 ? 'bg-emerald-500' : pct >= 25 ? 'bg-amber-400' : 'bg-red-400'
                                }`}
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Info */}
            {dados.total_interacoes < 50 && (
              <div className="bg-amber-50 border border-amber-100 rounded-xl px-5 py-4 text-sm text-amber-700">
                <span className="font-medium">O bandit ainda está aprendendo.</span>{' '}
                Com {dados.total_interacoes} interações, os dados ainda têm alta variância.
                Os resultados ficam mais confiáveis a partir de 50 feedbacks por ação.
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
