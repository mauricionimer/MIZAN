import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Shield, AlertTriangle, TrendingUp, Users, DollarSign,
  ChevronDown, ChevronRight, RefreshCw, Loader2, LogOut,
  Building2, CheckCircle2, Activity, Eye, ArrowLeft,
} from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const fmtBRL = v => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
  : '—'
const fmtNum = v => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtPct = v => v != null ? `${Number(v).toFixed(1)}%` : '—'
const fmtData = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  : '—'

function KpiCard({ label, value, sub, icon: Icon, accent = 'indigo' }) {
  const cfg = {
    indigo:  { wrap: 'border-indigo-800/40 bg-indigo-950/40',  icon: 'bg-indigo-900/60 text-indigo-300',  val: 'text-indigo-100' },
    emerald: { wrap: 'border-emerald-800/40 bg-emerald-950/40', icon: 'bg-emerald-900/60 text-emerald-300', val: 'text-emerald-100' },
    amber:   { wrap: 'border-amber-800/40 bg-amber-950/40',    icon: 'bg-amber-900/60 text-amber-300',    val: 'text-amber-100' },
    red:     { wrap: 'border-red-800/40 bg-red-950/40',        icon: 'bg-red-900/60 text-red-300',        val: 'text-red-100' },
  }[accent]
  return (
    <div className={`rounded-2xl border p-5 flex gap-4 items-start ${cfg.wrap}`}>
      <div className={`rounded-xl p-2.5 shrink-0 ${cfg.icon}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest">{label}</p>
        <p className={`text-2xl font-bold mt-1 leading-tight ${cfg.val}`}>{value}</p>
        {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function StatusBadge({ suspeita, taxaFeedback }) {
  if (suspeita) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-red-900/40 text-red-400 border border-red-800/50">
        <AlertTriangle className="h-3 w-3" /> Suspeita
      </span>
    )
  }
  if (taxaFeedback >= 20) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-900/40 text-emerald-400 border border-emerald-800/50">
        <CheckCircle2 className="h-3 w-3" /> Ativa
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
      <Activity className="h-3 w-3" /> Normal
    </span>
  )
}

function CarteirasEmpresa({ carteiras, loading }) {
  if (loading) {
    return (
      <tr>
        <td colSpan={9} className="px-6 py-4 text-center">
          <div className="flex items-center justify-center gap-2 text-slate-500 text-xs">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando carteiras...
          </div>
        </td>
      </tr>
    )
  }
  if (!carteiras.length) {
    return (
      <tr>
        <td colSpan={9} className="px-6 py-3 text-xs text-slate-600 text-center italic">
          Nenhuma carteira encontrada.
        </td>
      </tr>
    )
  }
  return carteiras.map(c => (
    <tr key={c.id} className="bg-slate-900/50 border-t border-slate-800/30">
      <td className="pl-14 pr-4 py-2.5 text-xs text-slate-500 font-mono">↳ {c.nome_arquivo || c.id.slice(0, 8)}</td>
      <td className="px-4 py-2.5 text-xs text-slate-500 text-right">{fmtNum(c.total_devedores)}</td>
      <td className="px-4 py-2.5 text-xs text-slate-500 text-right">{fmtBRL(c.valor_face)}</td>
      <td className="px-4 py-2.5 text-xs text-slate-500 text-right">{fmtBRL(c.valor_esperado)}</td>
      <td className="px-4 py-2.5 text-xs text-slate-500 text-right">{c.score_medio?.toFixed(1) ?? '—'}</td>
      <td className="px-4 py-2.5" />
      <td className="px-4 py-2.5" />
      <td className="px-4 py-2.5 text-xs text-slate-600 text-right">{fmtData(c.created_at)}</td>
      <td className="px-4 py-2.5" />
    </tr>
  ))
}

export default function ComandoDashboard() {
  const navigate  = useNavigate()
  const { token, usuario, logout, isComando } = useAuth()

  const [dados,      setDados]      = useState(null)
  const [carteiras,  setCarteiras]  = useState([])
  const [expandido,  setExpandido]  = useState(null)
  const [loadingMain, setLoadingMain] = useState(true)
  const [loadingCart, setLoadingCart] = useState(false)
  const [erro,       setErro]       = useState('')

  useEffect(() => { if (!isComando) navigate('/') }, [isComando])

  async function carregar() {
    setLoadingMain(true); setErro('')
    try {
      const res = await fetch(`${BASE}/comando/visao-geral`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setDados(await res.json())
    } catch (e) {
      setErro('Erro ao carregar dados do COMANDO: ' + e.message)
    } finally {
      setLoadingMain(false)
    }
  }

  async function expandirEmpresa(empresa_id) {
    if (expandido === empresa_id) { setExpandido(null); return }
    setExpandido(empresa_id)
    setLoadingCart(true)
    try {
      const res = await fetch(
        `${BASE}/comando/carteiras?empresa_id=${encodeURIComponent(empresa_id)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setCarteiras((await res.json()) || [])
    } catch {
      setCarteiras([])
    } finally {
      setLoadingCart(false)
    }
  }

  useEffect(() => { if (isComando) carregar() }, [])

  const t = dados?.totais
  const suspeitas = dados?.empresas?.filter(e => e.flag_suspeita) || []

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-3.5 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-900/50 shrink-0">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="font-bold text-white tracking-wide text-sm">COMANDO</span>
            <span className="ml-2 text-xs text-slate-500">Visão geral do ecossistema</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={carregar} disabled={loadingMain}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-40 font-medium">
            <RefreshCw className={`h-3.5 w-3.5 ${loadingMain ? 'animate-spin' : ''}`} /> Atualizar
          </button>
          <span className="text-xs text-slate-600 hidden sm:block">{usuario?.nome}</span>
          <button onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <ArrowLeft className="h-3.5 w-3.5" /> Voltar
          </button>
          <button onClick={() => { logout(); navigate('/login') }}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-400 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-950/40 font-medium">
            <LogOut className="h-3.5 w-3.5" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10 space-y-6">
        {loadingMain && !dados && (
          <div className="flex flex-col items-center justify-center py-32 gap-3 text-slate-600">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
            <p className="text-sm">Carregando dados do ecossistema...</p>
          </div>
        )}

        {erro && (
          <div className="bg-red-950/40 border border-red-800/50 rounded-2xl px-5 py-4 text-sm text-red-400">
            {erro}
          </div>
        )}

        {dados && (
          <>
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Painel COMANDO</h1>
                <p className="text-sm text-slate-500 mt-1">
                  Visibilidade total sobre todos os clientes e carteiras analisadas na plataforma
                </p>
              </div>
              <div className="text-xs text-slate-600 font-mono">
                {t?.total_empresas} empresa{t?.total_empresas !== 1 ? 's' : ''} ativas
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <KpiCard
                label="Empresas na plataforma"
                value={fmtNum(t?.total_empresas)}
                sub={`${t?.n_suspeitas || 0} com atividade suspeita`}
                icon={Building2}
                accent="indigo"
              />
              <KpiCard
                label="Devedores analisados"
                value={fmtNum(t?.total_devedores)}
                sub="total acumulado"
                icon={Users}
                accent="indigo"
              />
              <KpiCard
                label="Valor face total"
                value={fmtBRL(t?.valor_face_total)}
                sub="carteiras analisadas"
                icon={DollarSign}
                accent="emerald"
              />
              <KpiCard
                label="Valor recuperado real"
                value={fmtBRL(t?.valor_recuperado_real)}
                sub={t?.valor_face_total > 0
                  ? `${((t.valor_recuperado_real / t.valor_face_total) * 100).toFixed(1)}% do valor face`
                  : 'via feedbacks registrados'}
                icon={TrendingUp}
                accent={t?.valor_recuperado_real > 0 ? 'emerald' : 'amber'}
              />
            </div>

            {suspeitas.length > 0 && (
              <div className="flex items-start gap-3 bg-red-950/30 border border-red-800/50 rounded-2xl px-5 py-4">
                <AlertTriangle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-red-300">
                    {suspeitas.length} empresa{suspeitas.length > 1 ? 's' : ''} com comportamento suspeito
                  </p>
                  <p className="text-xs text-red-400/70 mt-1 leading-relaxed">
                    Essas empresas analisaram mais de 50 devedores mas registraram menos de 5% de feedback —
                    podem estar usando a plataforma sem reportar os resultados reais.
                    {' '}<span className="font-medium">{suspeitas.map(e => e.usuario_email || e.empresa_id).join(', ')}</span>
                  </p>
                </div>
              </div>
            )}

            <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Empresas clientes</h2>
                  <p className="text-xs text-slate-600 mt-0.5">Clique em uma linha para ver as carteiras individuais</p>
                </div>
                <Eye className="h-4 w-4 text-slate-700" />
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50">
                    <tr>
                      {[
                        ['', 'w-8'],
                        ['Empresa', 'text-left'],
                        ['Devedores', 'text-right'],
                        ['Valor face', 'text-right'],
                        ['Valor esperado', 'text-right'],
                        ['Score médio', 'text-right'],
                        ['Feedbacks', 'text-right'],
                        ['Última atividade', 'text-right'],
                        ['Status', 'text-right'],
                      ].map(([h, cls = '']) => (
                        <th key={h} className={`px-4 py-3.5 text-[11px] font-semibold text-slate-500 uppercase tracking-widest whitespace-nowrap ${cls}`}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50">
                    {dados.empresas.map(e => {
                      const isOpen = expandido === e.empresa_id
                      const isSusp = e.flag_suspeita
                      return [
                        <tr
                          key={e.empresa_id}
                          onClick={() => expandirEmpresa(e.empresa_id)}
                          className={`cursor-pointer transition-colors ${
                            isSusp
                              ? 'bg-red-950/10 hover:bg-red-950/20'
                              : 'hover:bg-slate-800/40'
                          }`}
                        >
                          <td className="pl-4 pr-2 py-4 text-slate-600">
                            {isOpen
                              ? <ChevronDown className="h-3.5 w-3.5 text-indigo-400" />
                              : <ChevronRight className="h-3.5 w-3.5" />
                            }
                          </td>
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2">
                              <Building2 className={`h-3.5 w-3.5 shrink-0 ${isSusp ? 'text-red-500' : 'text-slate-600'}`} />
                              <div>
                                <p className={`text-sm font-medium leading-tight ${isSusp ? 'text-red-300' : 'text-slate-200'}`}>
                                  {e.usuario_email || e.empresa_id}
                                </p>
                                <p className="text-xs text-slate-600 font-mono">{e.total_carteiras} carteira{e.total_carteiras !== 1 ? 's' : ''}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-4 text-right text-slate-300 font-mono text-sm">{fmtNum(e.total_devedores)}</td>
                          <td className="px-4 py-4 text-right text-slate-300 font-mono text-sm">{fmtBRL(e.valor_face_total)}</td>
                          <td className="px-4 py-4 text-right text-slate-400 font-mono text-sm">{fmtBRL(e.valor_esperado_total)}</td>
                          <td className="px-4 py-4 text-right">
                            <span className={`text-sm font-bold ${
                              e.score_medio == null ? 'text-slate-600' :
                              e.score_medio >= 60   ? 'text-emerald-400' :
                              e.score_medio >= 40   ? 'text-amber-400' : 'text-red-400'
                            }`}>
                              {e.score_medio?.toFixed(1) ?? '—'}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-right">
                            <div className="flex flex-col items-end gap-0.5">
                              <span className="text-sm text-slate-300 font-mono">{fmtNum(e.n_feedbacks)}</span>
                              <span className={`text-xs font-mono ${e.flag_suspeita ? 'text-red-500' : 'text-slate-600'}`}>
                                {fmtPct(e.taxa_feedback)} dos devedores
                              </span>
                              {e.valor_recuperado_real > 0 && (
                                <span className="text-xs text-emerald-500 font-mono">{fmtBRL(e.valor_recuperado_real)}</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-4 text-right text-xs text-slate-500 font-mono whitespace-nowrap">
                            {fmtData(e.ultima_atividade)}
                          </td>
                          <td className="px-4 py-4 text-right">
                            <StatusBadge suspeita={e.flag_suspeita} taxaFeedback={e.taxa_feedback} />
                          </td>
                        </tr>,

                        isOpen && (
                          <CarteirasEmpresa
                            key={`${e.empresa_id}_cart`}
                            carteiras={carteiras}
                            loading={loadingCart}
                          />
                        ),
                      ]
                    })}
                  </tbody>
                </table>
              </div>

              {dados.empresas.length === 0 && (
                <div className="py-16 text-center text-slate-600 text-sm">
                  Nenhuma empresa com análises registradas ainda.
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-5 text-xs text-slate-600">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" /> Ativa — taxa de feedback ≥ 20%
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-500" /> Normal — taxa de feedback &lt; 20%
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500" /> Suspeita — +50 devedores analisados com &lt; 5% de feedback
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
