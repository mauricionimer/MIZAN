import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell,
} from 'recharts'
import { buscarPagamentos } from '../api'
import {
  Users, TrendingDown, BarChart2, Star,
  Download, RefreshCw, Search, Loader2,
  Tag, Percent, ArrowUpRight, Banknote, ClipboardList, FileSpreadsheet, Zap, LogOut, ShieldCheck, KeyRound,
  CheckCircle2, XCircle, TrendingUp, Home,
} from 'lucide-react'
import * as XLSX from 'xlsx'
import { gerarRelatorioPDF } from '../utils/gerarPDF'
import { useAnalysis } from '../context/AnalysisContext'
import { useAuth } from '../context/AuthContext'
import StatCard from '../components/StatCard'
import PriorityBadge from '../components/PriorityBadge'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

const AGING_ORDER = ['0-29 dias', '30-59 dias', '60-89 dias', '90-179 dias', '180+ dias']
const AGING_COLORS  = ['#10b981', '#3b82f6', '#f59e0b', '#f97316', '#ef4444']
const CLUSTER_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#14b8a6']

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum  = (v) => new Intl.NumberFormat('pt-BR').format(v)
const fmtPct  = (v) => `${v.toFixed(1)}%`

function prioLabel(score) {
  if (score >= 70) return 'Alta'
  if (score >= 40) return 'Média'
  return 'Baixa'
}

function exportCSV(ranking) {
  const headers = ['Rank','Nome','CPF','Produto','UF','Valor Face (R$)','Valor Esperado (R$)','Dias em Atraso','Score','Prioridade','Desconto Sugerido (%)','Valor Proposta (R$)','Parcelas Máx.','Estratégia de Oferta']
  const rows = ranking.map(d => [
    d.rank,
    d.nome ?? '',
    d.cpf  ?? '',
    d.produto ?? '',
    d.uf ?? '',
    (d.valor_divida ?? 0).toFixed(2).replace('.', ','),
    (d.valor_esperado_recuperacao ?? 0).toFixed(2).replace('.', ','),
    d.dias_em_atraso ?? 0,
    d.score_recuperabilidade ?? 0,
    prioLabel(d.score_recuperabilidade ?? 0),
    d.desconto_sugerido_pct ?? 0,
    (d.valor_proposta ?? 0).toFixed(2).replace('.', ','),
    d.parcelas_max ?? '',
    d.estrategia_oferta ?? '',
  ])

  const escape = (v) => {
    const s = String(v)
    return s.includes(';') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [headers, ...rows].map(r => r.map(escape).join(';')).join('\r\n')
  const bom  = '﻿'  // BOM para Excel reconhecer UTF-8
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `mizan-ranking-${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function exportExcel(ranking, resumo) {
  const dados = ranking.map(d => ({
    'Rank':                    d.rank,
    'Nome':                    d.nome ?? '',
    'CPF':                     d.cpf ?? '',
    'Produto':                 d.produto ?? '',
    'UF':                      d.uf ?? '',
    'Valor Face (R$)':         d.valor_divida ?? 0,
    'Valor Esperado (R$)':     d.valor_esperado_recuperacao ?? 0,
    'Dias em Atraso':          d.dias_em_atraso ?? 0,
    'Score':                   d.score_recuperabilidade ?? 0,
    'Prioridade':              prioLabel(d.score_recuperabilidade ?? 0),
    'Desconto Sugerido (%)':   d.desconto_sugerido_pct ?? 0,
    'Valor Proposta (R$)':     d.valor_proposta ?? 0,
    'Parcelas Máx.':           d.parcelas_max ?? '',
    'Estratégia de Oferta':    d.estrategia_oferta ?? '',
    'Aging':                   d.aging ?? '',
    'Cluster':                 d.perfil_cluster ?? '',
  }))

  const wsRanking = XLSX.utils.json_to_sheet(dados)
  const colWidths = [6, 30, 16, 12, 6, 18, 20, 14, 8, 12, 20, 20, 14, 36, 14, 28]
  wsRanking['!cols'] = colWidths.map(w => ({ wch: w }))

  const resumoSheet = [
    { 'Métrica': 'Total de Devedores',           'Valor': resumo.total_devedores },
    { 'Métrica': 'Valor de Face (R$)',            'Valor': resumo.total_em_risco },
    { 'Métrica': 'Score Médio',                   'Valor': resumo.score_medio },
    { 'Métrica': 'Taxa de Recuperação Esperada',  'Valor': `${(resumo.taxa_recuperacao_esperada ?? 0).toFixed(1)}%` },
    { 'Métrica': 'Valor Esperado Total (R$)',     'Valor': resumo.valor_esperado_recuperacao_total },
  ]
  const wsResumo = XLSX.utils.json_to_sheet(resumoSheet)
  wsResumo['!cols'] = [{ wch: 36 }, { wch: 20 }]

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, wsResumo,  'Resumo')
  XLSX.utils.book_append_sheet(wb, wsRanking, 'Ranking')

  const data = new Date().toISOString().slice(0, 10)
  XLSX.writeFile(wb, `mizan-carteira-${data}.xlsx`)
}

const CustomBarTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-100 rounded-xl shadow-[0_4px_16px_rgba(15,23,42,0.10)] p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      <p className="text-slate-600">Devedores: <span className="font-bold">{fmtNum(payload[0].value)}</span></p>
    </div>
  )
}

function Slider({ label, hint, value, min, max, step, onChange, color = 'blue' }) {
  const pct = ((value - min) / (max - min)) * 100
  const trackColor = color === 'emerald' ? '#10b981' : '#3b82f6'
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-slate-500">{label}</span>
        <span className="text-sm font-bold text-slate-800">{value}%</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, ${trackColor} ${pct}%, #e2e8f0 ${pct}%)`,
        }}
      />
      <p className="text-xs text-slate-400 mt-1">{hint}</p>
    </div>
  )
}

function PricingCard({ label, value, sub, highlight = false, icon: Icon }) {
  return (
    <div className={`rounded-2xl border p-4 flex flex-col gap-1 ${
      highlight
        ? 'bg-blue-600 border-blue-500 text-white shadow-[0_8px_32px_rgba(29,78,216,0.5),0_4px_12px_rgba(29,78,216,0.3)]'
        : 'bg-white border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)]'
    }`}>
      <div className="flex items-center justify-between">
        <p className={`text-xs font-semibold uppercase tracking-wide ${highlight ? 'text-blue-200' : 'text-slate-500'}`}>
          {label}
        </p>
        {Icon && <Icon className={`h-4 w-4 ${highlight ? 'text-blue-300' : 'text-slate-300'}`} />}
      </div>
      <p className={`text-xl font-bold leading-none mt-1 ${highlight ? 'text-white' : 'text-slate-800'}`}>{value}</p>
      {sub && <p className={`text-xs mt-0.5 ${highlight ? 'text-blue-200' : 'text-slate-400'}`}>{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const { result } = useAnalysis()
  const { token, usuario, logout, isAdmin, isComando, isOperador } = useAuth()
  const navigate    = useNavigate()
  const [search, setSearch]               = useState('')
  const [exporting, setExporting]         = useState(false)
  const [custoCobranca, setCustoCobranca] = useState(25)
  const [retornoAlvo, setRetornoAlvo]     = useState(30)
  const [filtroPrio, setFiltroPrio]       = useState('todos')
  const [filtroProduto, setFiltroProduto] = useState('todos')
  const [filtroUF, setFiltroUF]           = useState('todas')
  const [page, setPage]                   = useState(1)

  // useMemo deve ficar ANTES de qualquer return condicional (regra dos hooks)
  const pricing = useMemo(() => {
    if (!result) return null
    const ver             = result.resumo.valor_esperado_recuperacao_total ?? 0
    const face            = result.resumo.total_em_risco ?? 0
    const cc              = custoCobranca / 100
    const ra              = retornoAlvo   / 100
    const liquido         = ver * (1 - cc)
    const preco           = liquido / (1 + ra)
    const retorno         = preco > 0 ? ((liquido - preco) / preco) * 100 : 0
    const desconto        = face  > 0 ? ((face - preco) / face) * 100 : 0
    const taxaRecuperacao = face  > 0 ? (ver / face) * 100 : 0
    return { ver, face, liquido, preco, retorno, desconto, taxaRecuperacao }
  }, [result, custoCobranca, retornoAlvo])

  const [perf, setPerf]                   = useState(null)
  const [loadingPerf, setLoadingPerf]     = useState(true)
  const [pagamentos, setPagamentos]       = useState([])
  const [searchPag, setSearchPag]         = useState('')

  useEffect(() => {
    if (!token) return
    fetch(`${BASE}/performance`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(setPerf)
      .catch(() => {})
      .finally(() => setLoadingPerf(false))
    buscarPagamentos().then(setPagamentos).catch(() => {})
  }, [token])

  useEffect(() => {
    if (!result) navigate('/')
  }, [result, navigate])

  const produtos = useMemo(() => {
    const u = [...new Set((result?.ranking_completo ?? []).map(d => d.produto).filter(Boolean))].sort()
    return u
  }, [result])

  const ufs = useMemo(() => {
    const u = [...new Set((result?.ranking_completo ?? []).map(d => d.uf).filter(Boolean))].sort()
    return u
  }, [result])

  const filtered = useMemo(() => {
    const lista = result?.ranking_completo ?? []
    let list = search
      ? lista.filter(d =>
          d.nome?.toLowerCase().includes(search.toLowerCase()) ||
          d.cpf?.includes(search)
        )
      : lista
    if (filtroPrio !== 'todos')
      list = list.filter(d => prioLabel(d.score_recuperabilidade ?? 0) === filtroPrio)
    if (filtroProduto !== 'todos')
      list = list.filter(d => d.produto === filtroProduto)
    if (filtroUF !== 'todas')
      list = list.filter(d => d.uf === filtroUF)
    return list
  }, [result, search, filtroPrio, filtroProduto, filtroUF])

  useEffect(() => { setPage(1) }, [search, filtroPrio, filtroProduto, filtroUF])

  if (!result) return null

  const { resumo, distribuicao_aging, distribuicao_cluster, ranking_completo } = result

  const agingData    = [...distribuicao_aging].sort(
    (a, b) => AGING_ORDER.indexOf(a.aging) - AGING_ORDER.indexOf(b.aging)
  )
  const prioritarios = ranking_completo.filter(d => d.score_recuperabilidade >= 70).length

  const PAGE_SIZE  = 50
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated  = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function exportPDF() {
    setExporting(true)
    try {
      gerarRelatorioPDF(result, pricing, custoCobranca, retornoAlvo)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="min-h-screen">

      {/* Navbar */}
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20 shrink-0"
            style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
            <span className="text-white font-bold text-xs">⚖</span>
          </div>
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          <span className="text-slate-200 text-sm">/</span>
          <span className="text-slate-500 text-sm">Dashboard</span>
        </div>
        <div className="flex items-center gap-1.5">
          {isComando && (
            <button
              onClick={() => navigate('/comando')}
              className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 transition-colors px-3 py-1.5 rounded-xl hover:bg-indigo-50 font-semibold"
            >
              <ShieldCheck className="h-3.5 w-3.5" /> COMANDO
            </button>
          )}
          {isAdmin && (
            <button onClick={() => navigate('/admin')} className="nav-link">
              <Home className="h-3.5 w-3.5" /> Início
            </button>
          )}
          {isOperador && (
            <button onClick={() => navigate('/operador')} className="nav-link">
              <Home className="h-3.5 w-3.5" /> Início
            </button>
          )}
          {(isAdmin || isComando) && (
            <button
              onClick={() => navigate('/admin/usuarios')}
              className="flex items-center gap-1.5 text-sm text-violet-600 hover:text-violet-800 transition-colors px-3 py-1.5 rounded-xl hover:bg-violet-50 font-semibold"
            >
              <ShieldCheck className="h-3.5 w-3.5" /> Usuários
            </button>
          )}
          {isComando && (
            <button onClick={() => navigate('/bandit')} className="nav-link">
              <Zap className="h-3.5 w-3.5" /> Performance IA
            </button>
          )}
          <button onClick={() => navigate('/feedback')} className="nav-link">
            <ClipboardList className="h-3.5 w-3.5" /> Registrar pagamento
          </button>
          <button onClick={() => navigate('/alterar-senha')} className="nav-link" title="Alterar senha">
            <KeyRound className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{usuario?.nome}</span>
          </button>
          <button onClick={() => navigate('/')} className="nav-link">
            <RefreshCw className="h-3.5 w-3.5" /> Nova análise
          </button>
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="h-3.5 w-3.5" /> Sair
          </button>
          <div className="w-px h-5 bg-slate-200 mx-1" />
          <button
            onClick={() => exportCSV(ranking_completo)}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-1.5 rounded-xl transition-colors"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" /> CSV
          </button>
          <button
            onClick={() => exportExcel(ranking_completo, resumo)}
            className="flex items-center gap-1.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold px-3 py-1.5 rounded-xl transition-colors"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" /> Excel
          </button>
          <button
            onClick={exportPDF}
            disabled={exporting}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-300 text-white text-xs font-semibold px-3 py-1.5 rounded-xl transition-colors"
          >
            {exporting
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Exportando...</>
              : <><Download className="h-3.5 w-3.5" /> PDF</>}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* ── Stat Cards ── */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Total de Devedores"     value={fmtNum(resumo.total_devedores)}  icon={Users}       accent="blue" />
          <StatCard label="Valor de Face"           value={fmtBRL(resumo.total_em_risco)}   sub="valor nominal da carteira"       icon={TrendingDown} accent="amber" />
          <StatCard label="Score Médio"             value={resumo.score_medio.toFixed(1)}   sub="recuperabilidade (0–100)"        icon={BarChart2}   accent="violet" />
          <StatCard label="Devedores Prioritários" value={fmtNum(prioritarios)}             sub="score ≥ 70"                      icon={Star}        accent="emerald" />
        </div>

        {/* ── Precificação ── */}
        {!isOperador && <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center shrink-0">
              <Banknote className="h-4.5 w-4.5 text-blue-600" style={{ width: '1.125rem', height: '1.125rem' }} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800 tracking-tight">Precificação da Carteira</h3>
              <p className="text-xs text-slate-400 mt-0.5">Ajuste os parâmetros para simular cenários de compra</p>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-6 items-start">

            {/* Sliders */}
            <div className="col-span-1 space-y-5 bg-slate-50 rounded-xl p-4 border border-slate-100">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Parâmetros</p>
              <Slider
                label="Custo de Cobrança"
                hint="Despesas operacionais e comissões"
                value={custoCobranca}
                min={5} max={50} step={1}
                onChange={setCustoCobranca}
                color="blue"
              />
              <Slider
                label="Retorno Alvo"
                hint="ROI mínimo desejado na operação"
                value={retornoAlvo}
                min={10} max={80} step={1}
                onChange={setRetornoAlvo}
                color="emerald"
              />
            </div>

            {/* Metric cards */}
            <div className="col-span-4 grid grid-cols-4 gap-4">
              <PricingCard
                label="Valor Esperado de Recuperação"
                value={fmtBRL(pricing.ver)}
                sub={resumo.taxa_recuperacao_esperada != null ? `${fmtPct(resumo.taxa_recuperacao_esperada)} do valor de face` : 'do valor de face'}
                icon={ArrowUpRight}
              />
              <PricingCard
                label="Valor Líquido (após custos)"
                value={fmtBRL(pricing.liquido)}
                sub={`custos estimados: ${fmtBRL(pricing.ver - pricing.liquido)}`}
                icon={Percent}
              />
              <PricingCard
                label="Preço Sugerido de Compra"
                value={fmtBRL(pricing.preco)}
                sub={`${fmtPct(pricing.desconto)} de desconto sobre o face`}
                highlight
                icon={Tag}
              />
              <PricingCard
                label="Taxa de Recuperação Estimada"
                value={`${pricing.taxaRecuperacao.toFixed(1)}%`}
                sub={`do valor de face · lucro: ${fmtBRL(pricing.liquido - pricing.preco)}`}
                icon={TrendingUp}
              />
            </div>
          </div>

          {/* Formula explainer */}
          <div className="mt-5 pt-4 border-t border-slate-100 flex items-center gap-6 text-xs text-slate-400 flex-wrap">
            <span><span className="font-medium text-slate-500">VER</span> = Σ (valor_dívida × score/100)</span>
            <span className="text-slate-200">›</span>
            <span><span className="font-medium text-slate-500">Líquido</span> = VER × (1 − {custoCobranca}%)</span>
            <span className="text-slate-200">›</span>
            <span><span className="font-medium text-slate-500">Preço</span> = Líquido ÷ (1 + {retornoAlvo}%)</span>
            <span className="text-slate-200">›</span>
            <span><span className="font-medium text-slate-500">Retorno</span> = (Líquido − Preço) ÷ Preço</span>
          </div>
        </div>}

        {/* ── Charts ── */}
        <div className="grid grid-cols-5 gap-6">

          {/* Aging Bar Chart */}
          <div className="col-span-3 bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-6">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
                <BarChart2 className="h-4 w-4 text-blue-500" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 tracking-tight">Distribuição por Aging</h3>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={agingData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="aging" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomBarTooltip />} cursor={{ fill: '#f8fafc' }} />
                <Bar dataKey="total_devedores" radius={[4, 4, 0, 0]} maxBarSize={48}>
                  {agingData.map((_, i) => <Cell key={i} fill={AGING_COLORS[i % AGING_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
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

          {/* Cluster Pie */}
          <div className="col-span-2 bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-6">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-8 h-8 rounded-xl bg-violet-50 flex items-center justify-center shrink-0">
                <Users className="h-4 w-4 text-violet-500" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 tracking-tight">Perfis de Devedores</h3>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={distribuicao_cluster} dataKey="total_devedores" nameKey="perfil_cluster"
                  cx="50%" cy="50%" outerRadius={80} innerRadius={40} paddingAngle={2}
                >
                  {distribuicao_cluster.map((_, i) => (
                    <Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #f1f5f9', fontSize: 11, boxShadow: '0 4px 16px rgba(15,23,42,0.10)' }}
                  formatter={(v, _, { payload }) => [fmtNum(v), payload.perfil_cluster]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 space-y-1.5">
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

        {/* ── Resultados Reais ── */}
        {!isOperador && !loadingPerf && perf && perf.total_feedbacks > 0 && (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                  <TrendingUp className="h-4.5 w-4.5 text-emerald-600" style={{ width: '1.125rem', height: '1.125rem' }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 tracking-tight">Resultados Reais — Quem Pagou</h3>
                  <p className="text-xs text-slate-400 mt-0.5">{perf.total_feedbacks} feedbacks registrados</p>
                </div>
              </div>
              {perf.acuracia_geral != null && (
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-50 text-blue-600 border border-blue-100">
                  Acurácia do modelo: {perf.acuracia_geral}%
                </span>
              )}
            </div>
            <div className="p-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100">
                      {['Faixa de Score', 'Feedbacks', 'Pagaram', 'Não Pagaram', 'Taxa de Pagamento', ''].map(h => (
                        <th key={h} className="pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-left first:pl-0 px-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {perf.metricas_por_faixa.map(f => {
                      const taxa = f.taxa_pagamento ?? 0
                      const barColor = taxa >= 60 ? '#10b981' : taxa >= 30 ? '#f59e0b' : '#ef4444'
                      return (
                        <tr key={f.faixa} className="hover:bg-slate-50">
                          <td className="py-3 pl-0 pr-4 text-sm font-medium text-slate-700">{f.faixa}</td>
                          <td className="py-3 px-4 text-slate-500 font-mono">{f.total_feedbacks}</td>
                          <td className="py-3 px-4">
                            <span className="flex items-center gap-1 text-emerald-600 font-medium">
                              <CheckCircle2 className="h-3.5 w-3.5" />{f.pagaram}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="flex items-center gap-1 text-red-400 font-medium">
                              <XCircle className="h-3.5 w-3.5" />{f.nao_pagaram}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-bold text-sm" style={{ color: barColor }}>{taxa.toFixed(1)}%</span>
                          </td>
                          <td className="py-3 px-4 w-32">
                            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full rounded-full" style={{ width: `${Math.min(taxa, 100)}%`, backgroundColor: barColor }} />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── Pagamentos individuais ── */}
        {pagamentos.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                  <Banknote className="h-4.5 w-4.5 text-emerald-600" style={{ width: '1.125rem', height: '1.125rem' }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 tracking-tight">Pagamentos Registrados</h3>
                  <p className="text-xs text-slate-400 mt-0.5">{pagamentos.filter(p => p.pagou).length} pagamentos · {pagamentos.filter(p => !p.pagou).length} não pagaram</p>
                </div>
              </div>
              <input
                value={searchPag}
                onChange={e => setSearchPag(e.target.value)}
                placeholder="Buscar por nome ou CPF..."
                className="border border-slate-200 rounded-xl px-3 py-1.5 text-xs focus:outline-none focus:border-blue-400 transition-all w-48 bg-white"
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    {['Nome', 'CPF', 'Dívida', 'Score', 'Situação', 'Valor Recuperado', 'Data'].map(h => (
                      <th key={h} className="py-2.5 px-4 text-xs font-semibold text-slate-500 uppercase tracking-wide text-left whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {pagamentos
                    .filter(p => {
                      if (!searchPag) return true
                      const q = searchPag.toLowerCase()
                      return (p.nome || '').toLowerCase().includes(q) || (p.cpf || '').includes(q)
                    })
                    .slice(0, 100)
                    .map((p, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-4 font-medium text-slate-700 max-w-[160px] truncate">{p.nome || '—'}</td>
                        <td className="py-3 px-4 font-mono text-slate-500 text-xs">{p.cpf || '—'}</td>
                        <td className="py-3 px-4 text-slate-600">{p.valor_divida != null ? fmtBRL(p.valor_divida) : '—'}</td>
                        <td className="py-3 px-4">
                          {p.score != null ? (
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${p.score >= 70 ? 'bg-emerald-50 text-emerald-700' : p.score >= 40 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-600'}`}>
                              {p.score}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="py-3 px-4">
                          {p.pagou
                            ? <span className="flex items-center gap-1 text-emerald-600 font-medium text-xs"><CheckCircle2 className="h-3.5 w-3.5" />Pagou</span>
                            : <span className="flex items-center gap-1 text-red-400 font-medium text-xs"><XCircle className="h-3.5 w-3.5" />Não pagou</span>}
                        </td>
                        <td className="py-3 px-4 font-semibold text-emerald-700">
                          {p.pagou && p.valor_recuperado > 0 ? fmtBRL(p.valor_recuperado) : p.pagou ? '—' : <span className="text-slate-300">—</span>}
                        </td>
                        <td className="py-3 px-4 text-slate-400 text-xs whitespace-nowrap">
                          {p.data_pagamento ? new Intl.DateTimeFormat('pt-BR').format(new Date(p.data_pagamento + 'T12:00:00')) : '—'}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              {pagamentos.filter(p => {
                if (!searchPag) return true
                const q = searchPag.toLowerCase()
                return (p.nome || '').toLowerCase().includes(q) || (p.cpf || '').includes(q)
              }).length === 0 && (
                <p className="text-center text-slate-400 text-sm py-8">Nenhum resultado encontrado.</p>
              )}
            </div>
          </div>
        )}

        {/* ── Tabela ── */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 space-y-3">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center shrink-0">
                  <Star className="h-4.5 w-4.5 text-blue-600" style={{ width: '1.125rem', height: '1.125rem' }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 tracking-tight">Ranking de Recuperabilidade</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {fmtNum(filtered.length)} devedores{search || filtroPrio !== 'todos' || filtroProduto !== 'todos' || filtroUF !== 'todas' ? ' filtrados' : ''}
                    {totalPages > 1 && ` · página ${page} de ${totalPages}`}
                  </p>
                </div>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Buscar por nome ou CPF..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="text-sm border border-slate-200 rounded-xl pl-9 pr-3 py-2 w-56 focus:outline-none focus:border-blue-400 transition-all bg-white"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex gap-1.5">
                {[
                  { k: 'todos', label: 'Todos',  cls: 'bg-blue-100 text-blue-700'       },
                  { k: 'Alta',  label: 'Alta',   cls: 'bg-emerald-100 text-emerald-700' },
                  { k: 'Média', label: 'Média',  cls: 'bg-amber-100 text-amber-700'     },
                  { k: 'Baixa', label: 'Baixa',  cls: 'bg-slate-200 text-slate-600'     },
                ].map(({ k, label, cls }) => (
                  <button key={k} onClick={() => setFiltroPrio(k)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                      filtroPrio === k ? cls : 'bg-slate-50 text-slate-400 hover:bg-slate-100 border border-slate-200'
                    }`}>
                    {label}
                  </button>
                ))}
              </div>
              {produtos.length > 1 && (
                <select value={filtroProduto} onChange={e => setFiltroProduto(e.target.value)}
                  className="text-xs border border-slate-200 rounded-xl px-2 py-1.5 focus:outline-none focus:border-blue-400 transition-all text-slate-600 bg-white">
                  <option value="todos">Todos produtos</option>
                  {produtos.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              )}
              {ufs.length > 1 && (
                <select value={filtroUF} onChange={e => setFiltroUF(e.target.value)}
                  className="text-xs border border-slate-200 rounded-xl px-2 py-1.5 focus:outline-none focus:border-blue-400 transition-all text-slate-600 bg-white">
                  <option value="todas">Todos estados</option>
                  {ufs.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              )}
              {(filtroPrio !== 'todos' || filtroProduto !== 'todos' || filtroUF !== 'todas' || search) && (
                <button onClick={() => { setFiltroPrio('todos'); setFiltroProduto('todos'); setFiltroUF('todas'); setSearch('') }}
                  className="text-xs text-slate-400 hover:text-slate-600 underline">
                  Limpar filtros
                </button>
              )}
            </div>
          </div>

          <div className="overflow-auto max-h-[520px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
                <tr>
                  {[
                    { label: '#',              align: 'left'   },
                    { label: 'Nome',           align: 'left'   },
                    { label: 'CPF',            align: 'left'   },
                    { label: 'Produto',        align: 'left'   },
                    { label: 'Valor Face',     align: 'right'  },
                    { label: 'Valor Esperado', align: 'right'  },
                    { label: 'Dias Atraso',    align: 'right'  },
                    { label: 'Score',          align: 'right'  },
                    { label: 'Prioridade',     align: 'center' },
                  ].map(({ label, align }) => (
                    <th key={label} className={`px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap text-${align}`}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {paginated.map((d) => (
                  <tr
                    key={d.rank}
                    onClick={() => navigate(`/devedor/${d.rank}`)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs w-10">{d.rank}</td>
                    <td className="px-4 py-3 font-medium text-slate-800 group-hover:text-blue-700 transition-colors">{d.nome}</td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs whitespace-nowrap">{d.cpf}</td>
                    <td className="px-4 py-3 capitalize text-slate-600">{d.produto}</td>
                    <td className="px-4 py-3 text-right text-slate-700 font-mono text-xs whitespace-nowrap">{fmtBRL(d.valor_divida)}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap">
                      <span className={(d.valor_esperado_recuperacao ?? 0) > 0 ? 'text-emerald-600 font-semibold' : 'text-slate-400'}>
                        {d.valor_esperado_recuperacao != null ? fmtBRL(d.valor_esperado_recuperacao) : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">{fmtNum(d.dias_em_atraso)}</td>
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
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 bg-slate-50">
              <span className="text-xs text-slate-400">
                {fmtNum((page - 1) * PAGE_SIZE + 1)}–{fmtNum(Math.min(page * PAGE_SIZE, filtered.length))} de {fmtNum(filtered.length)}
              </span>
              <div className="flex items-center gap-2">
                <button onClick={() => setPage(p => p - 1)} disabled={page === 1}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 transition-colors">
                  ← Anterior
                </button>
                <span className="text-xs text-slate-500 font-medium px-1">{page} / {totalPages}</span>
                <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 transition-colors">
                  Próxima →
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
