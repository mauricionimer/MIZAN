import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts'
import {
  ArrowLeft, RefreshCw, Loader2, Zap, TrendingUp, Activity, Award, LogOut, AlertTriangle, CheckCircle2,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LogoMark } from '../components/Logo'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
const MUTED = 'var(--ink-3)'
const MUTED_LIGHT = 'var(--ink-2)'
const LABEL = 'var(--ink-2)'

const CANAL_LABELS = { whatsapp: 'WhatsApp', telefone: 'Ligação', carta: 'Carta / E-mail' }
const OFERTA_LABELS = {
  avista_10pct:   '10% à vista',
  parcelado_4x:   '4x sem juros',
  desconto_30pct: '30% à vista',
  parcelado_12x:  '12x',
}
const CANAL_COLORS  = ['#25D366', 'var(--royal)', 'var(--warning)']
const OFERTA_COLORS = ['var(--success)', 'var(--royal)', 'var(--warning)', 'var(--lilac)']
const FASE_META = {
  exploração_inicial: { label: 'Exploração inicial', dot: 'bg-slate-400',  bg: 'var(--raise-3)', border: 'var(--line)', cor: MUTED_LIGHT },
  aprendendo:         { label: 'Aprendendo',          dot: 'bg-amber-400', bg: 'rgb(var(--c-warning) / 0.10)', border: 'rgb(var(--c-warning) / 0.25)', cor: 'var(--warning)' },
  calibrado:          { label: 'Calibrado',           dot: 'bg-emerald-500', bg: 'rgb(var(--c-success) / 0.10)', border: 'rgb(var(--c-success) / 0.25)', cor: 'var(--success)' },
}

const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function Logo() {
  return <LogoMark className="h-5 w-5 shrink-0" />
}

function LocalStatCard({ label, value, sub, icon: Icon, accent = 'blue' }) {
  const colors = {
    blue:    { bg: 'rgb(var(--c-royal) / 0.15)', cor: 'rgb(var(--c-royal))' },
    emerald: { bg: 'rgb(var(--c-success) / 0.15)', cor: 'var(--success)' },
    amber:   { bg: 'rgb(var(--c-warning) / 0.15)', cor: 'var(--warning)' },
    slate:   { bg: 'var(--raise-3)', cor: MUTED_LIGHT },
  }[accent]
  return (
    <div className="rounded-2xl p-5 flex gap-4 items-start" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
      <div className="rounded-xl p-2.5 shrink-0" style={{ background: colors.bg, color: colors.cor }}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="section-label">{label}</p>
        <p className="text-xl font-bold text-ink mt-1 leading-tight">{value}</p>
        {sub && <p className="text-xs mt-0.5" style={{ color: MUTED }}>{sub}</p>}
      </div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl shadow-lg p-3 text-xs" style={{ background: 'var(--raised)', border: '1px solid var(--line)' }}>
      <p className="font-semibold text-ink mb-1">{label}</p>
      <p style={{ color: MUTED_LIGHT }}>Taxa de recuperação: <span className="font-bold text-emerald-300">{fmtPct(payload[0].value / 100)}</span></p>
      {payload[0].payload.tentativas != null && (
        <p className="mt-0.5" style={{ color: MUTED }}>{payload[0].payload.tentativas} interações</p>
      )}
    </div>
  )
}

export default function BanditDashboard() {
  const navigate = useNavigate()
  const { token, usuario, logout } = useAuth()
  const [dados, setDados]     = useState(null)
  const [drift, setDrift]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro]       = useState('')

  async function carregar() {
    setLoading(true)
    setErro('')
    try {
      const [resBandit, resDrift] = await Promise.all([
        fetch(`${API_URL}/admin/bandit/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_URL}/admin/drift`,         { headers: { Authorization: `Bearer ${token}` } }),
      ])
      if (!resBandit.ok) throw new Error(`HTTP ${resBandit.status}`)
      setDados(await resBandit.json())
      if (resDrift.ok) setDrift(await resDrift.json())
    } catch (e) {
      setErro('Não foi possível carregar os dados do bandit. Verifique se o backend está rodando.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { carregar() }, [])

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
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/comando')} className="p-1 rounded-lg transition-colors hover:bg-raise-2" style={{ color: MUTED }}>
            <ArrowLeft className="h-4 w-4" />
          </button>
          <Logo />
          <span className="font-bold text-ink text-sm">Mizan</span>
          <span className="text-ink-4 text-sm">/</span>
          <span className="text-sm" style={{ color: MUTED_LIGHT }}>Bandit LinUCB</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={carregar}
            disabled={loading}
            className="nav-link disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Atualizar
          </button>
          <span className="text-sm hidden sm:block" style={{ color: MUTED }}>{usuario?.nome}</span>
          <ThemeToggle />
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-6">
        {loading && !dados && (
          <div className="flex flex-col items-center justify-center py-28 gap-3" style={{ color: MUTED }}>
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">Carregando dados do bandit...</p>
          </div>
        )}

        {erro && (
          <div className="rounded-2xl px-5 py-4 text-sm text-red-300" style={{ background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.25)' }}>
            {erro}
          </div>
        )}

        {drift && (
          drift.drift_detectado ? (
            <div className="flex items-start gap-3 rounded-2xl px-5 py-4 text-sm text-amber-300" style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.25)' }}>
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Possível drift do modelo detectado</p>
                <p className="opacity-90 mt-0.5">
                  Média dos scores nos últimos 30 dias: <strong>{drift.media_recente_30d?.toFixed(1)}</strong> vs. histórico: <strong>{drift.media_historica?.toFixed(1)}</strong> (diferença: {drift.diferenca?.toFixed(1)} pontos).
                  Considere re-treinar o modelo.
                </p>
              </div>
            </div>
          ) : drift.media_recente_30d != null ? (
            <div className="flex items-center gap-3 rounded-2xl px-5 py-3.5 text-sm text-emerald-300" style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.25)' }}>
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                Modelo estável — média recente: <strong>{drift.media_recente_30d?.toFixed(1)}</strong>, histórica: <strong>{drift.media_historica?.toFixed(1)}</strong> (diferença: {drift.diferenca?.toFixed(1)} pontos).
              </span>
            </div>
          ) : null
        )}

        {dados && (
          <>
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-bold text-ink tracking-tight">Performance do Bandit LinUCB</h1>
                <p className="text-sm mt-1" style={{ color: MUTED_LIGHT }}>Quais canais e ofertas estão gerando mais pagamentos</p>
              </div>
              {fase && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-semibold" style={{ background: fase.bg, borderColor: fase.border, color: fase.cor }}>
                  <span className={`w-2 h-2 rounded-full ${fase.dot}`} />
                  {fase.label}
                </div>
              )}
            </div>

            <div className="grid grid-cols-4 gap-4">
              <LocalStatCard
                label="Total de interações"
                value={dados.total_interacoes.toLocaleString('pt-BR')}
                sub="feedbacks registrados no bandit"
                icon={Activity}
                accent="blue"
              />
              <LocalStatCard
                label="Ações disponíveis"
                value="12"
                sub="3 canais × 4 ofertas"
                icon={Zap}
                accent="slate"
              />
              <LocalStatCard
                label="Melhor canal"
                value={melhorCanal?.taxa != null ? melhorCanal.label : '—'}
                sub={melhorCanal?.taxa != null ? `${fmtPct(melhorCanal.taxa / 100)} de recuperação` : 'sem dados ainda'}
                icon={TrendingUp}
                accent="emerald"
              />
              <LocalStatCard
                label="Melhor oferta"
                value={melhorOferta?.taxa != null ? melhorOferta.label : '—'}
                sub={melhorOferta?.taxa != null ? `${fmtPct(melhorOferta.taxa / 100)} de recuperação` : 'sem dados ainda'}
                icon={Award}
                accent="amber"
              />
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="rounded-2xl p-6" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                <p className="section-label mb-5">Taxa de recuperação por canal</p>
                {porCanal.every(c => c.taxa == null) ? (
                  <div className="flex items-center justify-center h-40 text-sm" style={{ color: MUTED }}>
                    Sem dados — registre feedbacks para ver resultados
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={porCanal} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,141,166,0.28)" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: LABEL }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: LABEL }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(128,141,166,0.14)' }} />
                      <Bar dataKey="taxa" radius={[4, 4, 0, 0]} maxBarSize={56}>
                        {porCanal.map((_, i) => <Cell key={i} fill={CANAL_COLORS[i % CANAL_COLORS.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                <div className="flex flex-wrap gap-3 mt-3">
                  {porCanal.map((c, i) => (
                    <div key={c.label} className="flex items-center gap-1.5 text-xs" style={{ color: MUTED }}>
                      <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CANAL_COLORS[i] }} />
                      {c.label}
                      <span style={{ color: 'var(--ink-4)' }}>({c.tentativas} int.)</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl p-6" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                <p className="section-label mb-5">Taxa de recuperação por oferta</p>
                {porOferta.every(o => o.taxa == null) ? (
                  <div className="flex items-center justify-center h-40 text-sm" style={{ color: MUTED }}>
                    Sem dados — registre feedbacks para ver resultados
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={porOferta} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,141,166,0.28)" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 10, fill: LABEL }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: LABEL }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(128,141,166,0.14)' }} />
                      <Bar dataKey="taxa" radius={[4, 4, 0, 0]} maxBarSize={56}>
                        {porOferta.map((_, i) => <Cell key={i} fill={OFERTA_COLORS[i % OFERTA_COLORS.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                <div className="flex flex-wrap gap-3 mt-3">
                  {porOferta.map((o, i) => (
                    <div key={o.label} className="flex items-center gap-1.5 text-xs" style={{ color: MUTED }}>
                      <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: OFERTA_COLORS[i] }} />
                      {o.label}
                      <span style={{ color: 'var(--ink-4)' }}>({o.tentativas} int.)</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
                <p className="section-label">Ranking das 12 combinações</p>
                <p className="text-xs mt-0.5" style={{ color: MUTED }}>Ordenado por taxa de recuperação média</p>
              </div>
              <table className="w-full text-sm">
                <thead style={{ background: 'var(--raise-1)', borderBottom: '1px solid var(--line)' }}>
                  <tr>
                    {['#', 'Canal', 'Oferta', 'Interações', 'Taxa de recuperação', 'Barra'].map((h, i) => (
                      <th key={h} className={`px-5 py-3.5 text-xs font-semibold uppercase tracking-wide whitespace-nowrap ${i >= 3 ? 'text-right' : 'text-left'}`} style={{ color: LABEL }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                  {rankingAcoes.map((a, i) => {
                    const pct = a.recompensa_media != null ? a.recompensa_media * 100 : null
                    const isTop = i === 0 && pct != null
                    return (
                      <tr key={a.id} style={isTop ? { background: 'rgb(var(--c-success) / 0.06)' } : undefined}>
                        <td className="px-5 py-3 tabular-nums text-xs w-8" style={{ color: MUTED }}>{i + 1}</td>
                        <td className="px-5 py-3">
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full"
                            style={
                              a.canal === 'whatsapp' ? { background: 'rgba(37,197,94,0.12)', color: 'rgb(var(--c-success))' } :
                              a.canal === 'telefone' ? { background: 'rgb(var(--c-royal) / 0.12)', color: 'rgb(var(--c-royal))' } :
                                                        { background: 'rgb(var(--c-warning) / 0.12)', color: 'rgb(var(--c-warning))' }
                            }>
                            {CANAL_LABELS[a.canal] ?? a.canal}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-sm" style={{ color: MUTED_LIGHT }}>{OFERTA_LABELS[a.oferta] ?? a.oferta}</td>
                        <td className="px-5 py-3 text-right tabular-nums text-xs" style={{ color: MUTED }}>{a.n_tentativas}</td>
                        <td className="px-5 py-3 text-right">
                          <span className={`font-bold text-sm ${
                            pct == null ? '' :
                            pct >= 50   ? 'text-emerald-300' :
                            pct >= 25   ? 'text-amber-300' : 'text-red-300'
                          }`} style={pct == null ? { color: MUTED } : undefined}>
                            {pct != null ? `${pct.toFixed(1)}%` : '—'}
                          </span>
                        </td>
                        <td className="px-5 py-3 w-36">
                          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--raise-3)' }}>
                            {pct != null && (
                              <div
                                className="h-full rounded-full transition-all"
                                style={{
                                  width: `${Math.min(pct, 100)}%`,
                                  background: pct >= 50 ? 'var(--success)' : pct >= 25 ? 'var(--warning)' : 'var(--danger)',
                                }}
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

            {dados.total_interacoes < 50 && (
              <div className="rounded-2xl px-5 py-4 text-sm text-amber-300" style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.25)' }}>
                <span className="font-semibold">O bandit ainda está aprendendo.</span>{' '}
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
