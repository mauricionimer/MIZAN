import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Shield, AlertTriangle, TrendingUp, Users, DollarSign,
  RefreshCw, Loader2, LogOut, Building2, CheckCircle2, Activity,
  Eye, Upload, Zap, UserCog, X, Database, FileText, User,
  ChevronRight, Brain,
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
const fmtDataCurta = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' }).format(new Date(iso))
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

function RoleBadge({ role }) {
  const m = {
    comando:  'bg-indigo-900/50 text-indigo-300 border-indigo-700/50',
    admin:    'bg-amber-900/40 text-amber-300 border-amber-700/50',
    operador: 'bg-slate-800 text-slate-400 border-slate-700',
  }[role] || 'bg-slate-800 text-slate-400 border-slate-700'
  return (
    <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wide ${m}`}>
      {role}
    </span>
  )
}

function EmpresaDetalhePanel({ empresa, token, onClose }) {
  const [dados, setDados]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!empresa) return
    setLoading(true)
    fetch(`${BASE}/comando/empresa/${encodeURIComponent(empresa.empresa_id)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setDados(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [empresa?.empresa_id])

  const cfg       = dados?.config || {}
  const usuarios  = dados?.usuarios || []
  const conexoes  = dados?.conexoes || []
  const carteiras = dados?.carteiras || []

  const admins    = usuarios.filter(u => u.role === 'admin')
  const operadores = usuarios.filter(u => u.role === 'operador')

  const totalFace = carteiras.reduce((s, c) => s + (c.valor_face || 0), 0)
  const totalDev  = carteiras.reduce((s, c) => s + (c.total_devedores || 0), 0)

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-800 flex items-start gap-4 shrink-0">
          {empresa?.foto_url
            ? <img src={empresa.foto_url} alt={empresa.nome_exibicao} className="h-14 w-14 rounded-2xl object-cover border border-slate-700 shrink-0" />
            : <div className="h-14 w-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                <Building2 className="h-7 w-7 text-slate-500" />
              </div>
          }
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold text-white leading-tight truncate">
              {empresa?.nome_exibicao || empresa?.empresa_id}
            </h2>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{empresa?.empresa_id}</p>
            <div className="flex items-center gap-2 mt-2">
              <StatusBadge suspeita={empresa?.flag_suspeita} taxaFeedback={empresa?.taxa_feedback || 0} />
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-white transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-16 gap-2 text-slate-500">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Carregando...</span>
            </div>
          ) : (
            <>
              {/* KPIs */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-800/60 rounded-xl p-3 text-center border border-slate-700/50">
                  <p className="text-lg font-bold text-slate-100">{carteiras.length}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">Carteiras</p>
                </div>
                <div className="bg-slate-800/60 rounded-xl p-3 text-center border border-slate-700/50">
                  <p className="text-lg font-bold text-slate-100">{fmtNum(totalDev)}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">Devedores</p>
                </div>
                <div className="bg-slate-800/60 rounded-xl p-3 text-center border border-slate-700/50">
                  <p className="text-sm font-bold text-emerald-400">{fmtBRL(totalFace)}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">Valor face</p>
                </div>
              </div>

              {/* Usuários */}
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5" /> Equipe ({usuarios.length})
                </h3>
                {usuarios.length === 0 ? (
                  <p className="text-xs text-slate-600 italic">Nenhum usuário cadastrado</p>
                ) : (
                  <div className="space-y-2">
                    {[...admins, ...operadores].map(u => (
                      <div key={u.id} className="flex items-center justify-between gap-3 bg-slate-800/40 rounded-xl px-3.5 py-2.5 border border-slate-700/30">
                        <div className="min-w-0">
                          <p className="text-sm text-slate-200 font-medium truncate">{u.nome}</p>
                          <p className="text-xs text-slate-500 truncate">{u.email}</p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {!u.ativo && (
                            <span className="text-[10px] text-red-400 bg-red-900/30 px-1.5 py-0.5 rounded-full border border-red-800/40">inativo</span>
                          )}
                          <RoleBadge role={u.role} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Conexões */}
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5" /> Bancos de dados ({conexoes.length})
                </h3>
                {conexoes.length === 0 ? (
                  <p className="text-xs text-slate-600 italic">Nenhuma conexão configurada</p>
                ) : (
                  <div className="space-y-2">
                    {conexoes.map(cx => (
                      <div key={cx.id} className="bg-slate-800/40 rounded-xl px-3.5 py-2.5 border border-slate-700/30">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm text-slate-200 font-medium truncate">{cx.nome || cx.id}</p>
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-700 text-slate-400 uppercase shrink-0">
                            {cx.tipo || 'DB'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">
                          {cx.host}{cx.database ? ` / ${cx.database}` : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Carteiras */}
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" /> Carteiras ({carteiras.length})
                </h3>
                {carteiras.length === 0 ? (
                  <p className="text-xs text-slate-600 italic">Nenhuma carteira analisada ainda</p>
                ) : (
                  <div className="space-y-2">
                    {carteiras.map(c => (
                      <div key={c.id} className="bg-slate-800/40 rounded-xl px-3.5 py-2.5 border border-slate-700/30">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm text-slate-300 font-mono truncate">{c.nome_arquivo || c.id.slice(0, 16)}</p>
                          <p className="text-xs text-slate-500 shrink-0">{fmtDataCurta(c.created_at)}</p>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 font-mono">
                          <span>{fmtNum(c.total_devedores)} dev.</span>
                          <span>{fmtBRL(c.valor_face)}</span>
                          {c.score_medio != null && (
                            <span className={
                              c.score_medio >= 60 ? 'text-emerald-500' :
                              c.score_medio >= 40 ? 'text-amber-500' : 'text-red-500'
                            }>score {c.score_medio.toFixed(1)}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ComandoDashboard() {
  const navigate  = useNavigate()
  const { token, usuario, logout } = useAuth()

  const [dados,        setDados]        = useState(null)
  const [loadingMain,  setLoadingMain]  = useState(true)
  const [erro,         setErro]         = useState('')
  const [empresaSel,   setEmpresaSel]   = useState(null)

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

  useEffect(() => { carregar() }, [])

  const t        = dados?.totais
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
        <div className="flex items-center gap-1.5">
          <button onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <Upload className="h-3.5 w-3.5" /> Análise
          </button>
          <button onClick={() => navigate('/admin/usuarios')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <UserCog className="h-3.5 w-3.5" /> Usuários
          </button>
          <button onClick={() => navigate('/auditoria')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <Shield className="h-3.5 w-3.5" /> Auditoria
          </button>
          <button onClick={() => navigate('/aprendizado')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <Brain className="h-3.5 w-3.5" /> Aprendizado
          </button>
          <button onClick={() => navigate('/bandit')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 font-medium">
            <Zap className="h-3.5 w-3.5" /> Performance IA
          </button>
          <button onClick={carregar} disabled={loadingMain}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-40 font-medium">
            <RefreshCw className={`h-3.5 w-3.5 ${loadingMain ? 'animate-spin' : ''}`} /> Atualizar
          </button>
          <span className="text-xs text-slate-600 hidden md:block">{usuario?.nome}</span>
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
                    Essas empresas analisaram mais de 50 devedores mas registraram menos de 5% de feedback.
                    {' '}<span className="font-medium">{suspeitas.map(e => e.nome_exibicao || e.empresa_id).join(', ')}</span>
                  </p>
                </div>
              </div>
            )}

            <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Empresas clientes</h2>
                  <p className="text-xs text-slate-600 mt-0.5">Clique em uma linha para ver o dashboard da empresa</p>
                </div>
                <Eye className="h-4 w-4 text-slate-700" />
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50">
                    <tr>
                      {[
                        ['Empresa', 'text-left'],
                        ['Devedores', 'text-right'],
                        ['Valor face', 'text-right'],
                        ['Valor esperado', 'text-right'],
                        ['Score médio', 'text-right'],
                        ['Feedbacks', 'text-right'],
                        ['Última atividade', 'text-right'],
                        ['Status', 'text-right'],
                        ['', 'w-8'],
                      ].map(([h, cls = '']) => (
                        <th key={h} className={`px-4 py-3.5 text-[11px] font-semibold text-slate-500 uppercase tracking-widest whitespace-nowrap ${cls}`}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50">
                    {dados.empresas.map(e => {
                      const isSusp = e.flag_suspeita
                      const isSel  = empresaSel?.empresa_id === e.empresa_id
                      return (
                        <tr
                          key={e.empresa_id}
                          onClick={() => setEmpresaSel(isSel ? null : e)}
                          className={`cursor-pointer transition-colors ${
                            isSel
                              ? 'bg-indigo-950/30 ring-1 ring-indigo-700/40 ring-inset'
                              : isSusp
                                ? 'bg-red-950/10 hover:bg-red-950/20'
                                : 'hover:bg-slate-800/40'
                          }`}
                        >
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2.5">
                              {e.foto_url
                                ? <img src={e.foto_url} alt={e.nome_exibicao} className="h-7 w-7 rounded-lg object-cover border border-slate-700 shrink-0" />
                                : <Building2 className={`h-3.5 w-3.5 shrink-0 ${isSusp ? 'text-red-500' : 'text-slate-600'}`} />
                              }
                              <div>
                                <p className={`text-sm font-medium leading-tight ${isSusp ? 'text-red-300' : 'text-slate-200'}`}>
                                  {e.nome_exibicao || e.empresa_id}
                                </p>
                                <p className="text-xs text-slate-600 font-mono">
                                  {e.empresa_id !== e.nome_exibicao && <span className="text-slate-700">{e.empresa_id} · </span>}
                                  {e.total_carteiras} carteira{e.total_carteiras !== 1 ? 's' : ''}
                                </p>
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
                          <td className="px-4 py-4 text-slate-600">
                            <ChevronRight className={`h-3.5 w-3.5 transition-transform ${isSel ? 'rotate-90 text-indigo-400' : ''}`} />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {dados.empresas.length === 0 && (
                <div className="py-16 text-center text-slate-600 text-sm">
                  Nenhuma empresa registrada ainda.
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

      {empresaSel && (
        <EmpresaDetalhePanel
          empresa={empresaSel}
          token={token}
          onClose={() => setEmpresaSel(null)}
        />
      )}
    </div>
  )
}
