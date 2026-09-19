import ThemeToggle from '../components/ThemeToggle'
import { motion } from 'framer-motion'
import { lista, item } from '../lib/motion'
import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell,
} from 'recharts'
import { buscarPagamentos, buscarStatusFeedbacks, confirmarPagamento } from '../api'
import {
  Users, TrendingDown, BarChart2, Star,
  Download, RefreshCw, Search, Loader2,
  Tag, Percent, ArrowUpRight, Banknote, ClipboardList, FileSpreadsheet, Zap, LogOut, ShieldCheck, KeyRound,
  CheckCircle2, XCircle, TrendingUp, Home, Clock, X,
  LayoutDashboard,
} from 'lucide-react'
import * as XLSX from 'xlsx'
import { gerarRelatorioPDF } from '../utils/gerarPDF'
import { useAnalysis } from '../context/AnalysisContext'
import { useAuth } from '../context/AuthContext'
import { LogoMark } from '../components/Logo'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

const AGING_ORDER = ['0-29 dias', '30-59 dias', '60-89 dias', '90-179 dias', '180+ dias']
const AGING_COLORS  = ['#10b981', '#3b82f6', '#f59e0b', '#f97316', '#ef4444']
const CLUSTER_COLORS = ['#3b82f6', '#60a5fa', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#14b8a6']

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum  = (v) => new Intl.NumberFormat('pt-BR').format(v)
const fmtPct  = (v) => `${v.toFixed(1)}%`

function prioLabel(score) {
  if (score >= 70) return 'Alta'
  if (score >= 40) return 'Média'
  return 'Baixa'
}

function getStatus(cpf, statusMap) {
  const fb = statusMap[String(cpf ?? '')]
  if (!fb) return 'pendente'
  return fb.pagou ? 'pago' : 'nao_pago'
}

/* ───────────────────────── Priority badge (dark) ───────────────────────── */
function PriorityBadge({ score }) {
  const cfg = score >= 70
    ? { label: 'Alta',  cls: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' }
    : score >= 40
      ? { label: 'Média', cls: 'bg-amber-500/10 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' }
      : { label: 'Baixa', cls: 'bg-slate-500/10 text-ink-2 border-slate-500/30', dot: 'bg-slate-400' }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${cfg.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

/* ───────────────────────── Status badge (dark) ───────────────────────── */
function StatusBadge({ cpf, statusMap }) {
  const s = getStatus(cpf, statusMap)
  const fb = statusMap[String(cpf ?? '')]
  const quem = fb?.registrado_por ? `por ${fb.registrado_por}` : ''
  const quando = fb?.registrado_em ? ` em ${new Date(fb.registrado_em).toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })}` : ''
  const title = quem || quando ? `Registrado ${quem}${quando}` : undefined

  if (s === 'pago') return (
    <div className="flex flex-col items-center gap-0.5">
      <span title={title} className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300 whitespace-nowrap cursor-default">
        <CheckCircle2 className="h-3 w-3" /> Pago
      </span>
      {quem && <span className="text-[10px] text-ink-2">{quem}{quando}</span>}
    </div>
  )
  if (s === 'nao_pago') return (
    <div className="flex flex-col items-center gap-0.5">
      <span title={title} className="inline-flex items-center gap-1 rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-300 whitespace-nowrap cursor-default">
        <XCircle className="h-3 w-3" /> Não pago
      </span>
      {quem && <span className="text-[10px] text-ink-2">{quem}{quando}</span>}
    </div>
  )
  return <span className="text-xs text-ink-2 whitespace-nowrap">Pendente</span>
}

/* ───────────────────────── KPI card (chic minimal) ───────────────────────── */
function KpiCard({ label, value, sub, danger = false, icon: Icon, accent }) {
  const accentColor = { blue: '#3b82f6', amber: '#f59e0b', violet: '#8b5cf6', emerald: '#10b981' }[accent] ?? 'var(--raise-3)'
  return (
    <div className="px-6 py-5 flex flex-col gap-3 rounded-xl transition-colors"
      style={{
        background: 'var(--raise-1)',
        border: '1px solid var(--line)',
        borderLeft: `2px solid ${accentColor}`,
      }}>
      <div className="flex items-center justify-between">
        <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>
          {label}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5" style={{ color: 'var(--ink-4)' }} />}
      </div>
      <div>
        <p className="text-[1.75rem] font-semibold tracking-tight leading-none" style={{ color: danger ? '#f87171' : 'var(--ink)' }}>
          {value}
        </p>
        {sub && <p className="text-xs mt-1.5" style={{ color: 'var(--ink-4)' }}>{sub}</p>}
      </div>
    </div>
  )
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
    <div className="rounded-lg border border-line bg-surface-2 px-3.5 py-2.5 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-ink">{label}</p>
      <p className="text-ink-2">Devedores: <span className="font-bold text-blue-300">{fmtNum(payload[0].value)}</span></p>
    </div>
  )
}

function Slider({ label, hint, value, min, max, step, onChange, color = 'blue' }) {
  const pct = ((value - min) / (max - min)) * 100
  const trackColor = color === 'emerald' ? '#10b981' : '#3b82f6'
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs text-ink-2">{label}</span>
        <span className="text-sm font-bold text-ink">{value}%</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full"
        style={{ background: `linear-gradient(to right, ${trackColor} ${pct}%, var(--raise-3) ${pct}%)` }}
      />
      <p className="mt-1 text-xs text-ink-2">{hint}</p>
    </div>
  )
}

function PricingCard({ label, value, sub, highlight = false, accent = null, icon: Icon }) {
  const lucroCard = accent === 'emerald'
  const box = highlight
    ? 'border-blue-500/40 bg-blue-600/15 shadow-[0_0_0_1px_rgba(59,130,246,0.25),0_8px_28px_-8px_rgba(59,130,246,0.4)]'
    : lucroCard
      ? 'border-emerald-500/30 bg-emerald-500/[0.08]'
      : 'border-line bg-raise-1'
  const head  = highlight ? 'text-blue-300'     : lucroCard ? 'text-emerald-300'    : 'text-ink-2'
  const val   = highlight ? 'text-ink'        : lucroCard ? 'text-emerald-200'    : 'text-ink'
  const subCl = highlight ? 'text-blue-200/80'  : lucroCard ? 'text-emerald-300/70' : 'text-ink-2'
  return (
    <div className={`flex flex-col gap-1 rounded-xl border p-4 ${box}`}>
      <div className="flex items-center justify-between">
        <p className={`text-xs font-semibold uppercase tracking-wide ${head}`}>
          {label}
        </p>
        {Icon && <Icon className={`h-4 w-4 ${head}`} />}
      </div>
      <p className={`mt-1 text-xl font-bold leading-none ${val}`}>{value}</p>
      {sub && <p className={`mt-0.5 text-xs ${subCl}`}>{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const { result } = useAnalysis()
  const { token, usuario, logout, isAdmin, isComando, isOperador, empresaConfig } = useAuth()
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
    const lucro           = liquido - preco
    const retorno         = preco > 0 ? (lucro / preco) * 100 : 0
    const desconto        = face  > 0 ? ((face - preco) / face) * 100 : 0
    const taxaRecuperacao = face  > 0 ? (ver / face) * 100 : 0
    return { ver, face, liquido, preco, lucro, retorno, desconto, taxaRecuperacao }
  }, [result, custoCobranca, retornoAlvo])

  const [perf, setPerf]                   = useState(null)
  const [loadingPerf, setLoadingPerf]     = useState(true)
  const [pagamentos, setPagamentos]       = useState([])
  const [searchPag, setSearchPag]         = useState('')
  const [statusMap, setStatusMap]         = useState({})
  const [filtroStatus, setFiltroStatus]   = useState('todos')
  const [confirmarModal, setConfirmarModal] = useState(null)
  const [confirmando, setConfirmando]       = useState(false)
  const [confirmarForm, setConfirmarForm]   = useState({ valor_recuperado: '', data_pagamento: '' })
  const [confirmarErro, setConfirmarErro]   = useState('')
  const [navAtiva, setNavAtiva]             = useState('dashboard')

  // carteira_id vem dentro de resumo na resposta do backend
  const carteiraId = result?.resumo?.carteira_id ?? result?.carteira_id ?? null

  function refetchPerf() {
    const perfUrl = carteiraId
      ? `${BASE}/performance?carteira_id=${encodeURIComponent(carteiraId)}`
      : `${BASE}/performance`
    fetch(perfUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(p => { if (p) setPerf(p) })
      .catch(() => {})
  }

  // Carrega dados iniciais + polling periódico de status a cada 15s
  useEffect(() => {
    if (!token) return

    const perfUrl = carteiraId
      ? `${BASE}/performance?carteira_id=${encodeURIComponent(carteiraId)}`
      : `${BASE}/performance`
    fetch(perfUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(setPerf)
      .catch(() => {})
      .finally(() => setLoadingPerf(false))

    buscarPagamentos(carteiraId).then(setPagamentos).catch(() => {})
    buscarStatusFeedbacks(carteiraId).then(setStatusMap).catch(() => {})

    // Polling a cada 15s — para após 3 erros consecutivos para não sobrecarregar servidor em outage
    let errosConsecutivos = 0
    const intervalo = setInterval(() => {
      Promise.all([
        buscarStatusFeedbacks(carteiraId).then(setStatusMap),
        buscarPagamentos(carteiraId).then(setPagamentos),
      ])
        .then(() => { errosConsecutivos = 0 })
        .catch(() => {
          errosConsecutivos++
          if (errosConsecutivos >= 3) clearInterval(intervalo)
        })
    }, 15000)

    return () => clearInterval(intervalo)
  }, [token, carteiraId])

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
    if (filtroStatus !== 'todos')
      list = list.filter(d => getStatus(d.cpf, statusMap) === filtroStatus)
    return list
  }, [result, search, filtroPrio, filtroProduto, filtroUF, filtroStatus, statusMap])

  useEffect(() => { setPage(1) }, [search, filtroPrio, filtroProduto, filtroUF, filtroStatus])

  async function handleConfirmarPagamento(e) {
    e.preventDefault()
    if (!confirmarModal || confirmando) return
    setConfirmando(true)
    setConfirmarErro('')
    try {
      const dados = {}
      if (confirmarForm.valor_recuperado) dados.valor_recuperado = parseFloat(confirmarForm.valor_recuperado.replace(',', '.'))
      if (confirmarForm.data_pagamento) dados.data_pagamento = confirmarForm.data_pagamento
      const res = await confirmarPagamento(confirmarModal.cpf, dados)
      const cpfKey = String(confirmarModal.cpf)
      // Atualização local imediata para feedback visual instantâneo
      setStatusMap(prev => ({
        ...prev,
        [cpfKey]: {
          pagou: true,
          valor_recuperado: dados.valor_recuperado || 0,
          data_pagamento: confirmarForm.data_pagamento || null,
          registrado_por: res.registrado_por || '',
          registrado_em: res.registrado_em || new Date().toISOString(),
        },
      }))
      setConfirmarModal(null)
      setConfirmarForm({ valor_recuperado: '', data_pagamento: '' })
      // Refetch imediato para confirmar com dados reais do servidor
      buscarStatusFeedbacks(carteiraId).then(setStatusMap).catch(() => {})
      buscarPagamentos(carteiraId).then(setPagamentos).catch(() => {})
      refetchPerf()
    } catch (err) {
      if (err.status === 409) {
        // Pagamento já existe — fecha modal e sincroniza status real do servidor
        setConfirmarModal(null)
        setConfirmarForm({ valor_recuperado: '', data_pagamento: '' })
        buscarStatusFeedbacks(carteiraId).then(setStatusMap).catch(() => {})
        buscarPagamentos(carteiraId).then(setPagamentos).catch(() => {})
      } else {
        setConfirmarErro(err.message || 'Erro ao confirmar pagamento.')
      }
    } finally {
      setConfirmando(false)
    }
  }

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

  const nomeEmpresa = empresaConfig?.nome_exibicao || 'Mizan'
  const nomeUser    = usuario?.nome || 'Operador'
  const iniciais    = nomeUser.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  // Itens da sidebar — ações de navegação por papel preservadas
  const navItems = [
    { id: 'dashboard', label: 'Dashboard',   icon: LayoutDashboard, onClick: () => setNavAtiva('dashboard') },
    { id: 'analise',   label: 'Nova análise', icon: RefreshCw,      onClick: () => navigate('/') },
    { id: 'pagamentos',label: 'Pagamentos',   icon: ClipboardList,  onClick: () => navigate('/feedback') },
    ...(isComando ? [{ id: 'comando', label: 'Comando',       icon: ShieldCheck, onClick: () => navigate('/comando') }] : []),
    ...(isComando ? [{ id: 'bandit',  label: 'Performance IA', icon: Zap,        onClick: () => navigate('/bandit') }] : []),
    ...((isAdmin || isComando) ? [{ id: 'usuarios', label: 'Usuários', icon: Users, onClick: () => navigate('/admin/usuarios') }] : []),
    ...(isAdmin    ? [{ id: 'inicio', label: 'Início', icon: Home, onClick: () => navigate('/admin') }] : []),
    ...(isOperador ? [{ id: 'inicio', label: 'Início', icon: Home, onClick: () => navigate('/operador') }] : []),
    { id: 'senha', label: 'Alterar senha', icon: KeyRound, onClick: () => navigate('/alterar-senha') },
  ]

  return (
    <div className="flex min-h-screen bg-surface-2 font-sans text-ink">

      {/* ───── Modal de confirmação de pagamento ───── */}
      {confirmarModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-5 rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-base font-bold text-ink">Confirmar pagamento</h2>
                <p className="mt-0.5 text-xs text-ink-2">
                  <span className="font-semibold text-ink">{confirmarModal.nome}</span>
                  {' · '}<span className="tabular-nums">{confirmarModal.cpf}</span>
                </p>
              </div>
              <button onClick={() => { setConfirmarModal(null); setConfirmarErro('') }}
                className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-raise-3 hover:text-ink">
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleConfirmarPagamento} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-2">
                  Valor recuperado <span className="font-normal text-ink-2">(opcional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-2">R$</span>
                  <input
                    type="number" min="0" step="0.01" placeholder="0,00"
                    value={confirmarForm.valor_recuperado}
                    onChange={e => setConfirmarForm(f => ({ ...f, valor_recuperado: e.target.value }))}
                    className="h-10 w-full rounded-lg border border-line bg-surface-2 pl-9 pr-3 text-sm text-ink placeholder-ink-4 transition-colors focus:border-blue-500/50 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-2">
                  Data do pagamento <span className="font-normal text-ink-2">(opcional)</span>
                </label>
                <input
                  type="date"
                  max={new Date().toISOString().split('T')[0]}
                  value={confirmarForm.data_pagamento}
                  onChange={e => setConfirmarForm(f => ({ ...f, data_pagamento: e.target.value }))}
                  className="h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm text-ink transition-colors focus:border-blue-500/50 focus:outline-none [color-scheme:dark]"
                />
              </div>

              {confirmarErro && (
                <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                  <p className="text-sm text-red-300">{confirmarErro}</p>
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <button type="button"
                  onClick={() => { setConfirmarModal(null); setConfirmarErro('') }}
                  className="flex-1 rounded-lg border border-line px-4 py-2.5 text-sm font-medium text-ink-2 transition-colors hover:bg-raise-2">
                  Cancelar
                </button>
                <button type="submit" disabled={confirmando}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-brand-ink transition-colors hover:bg-emerald-700 disabled:opacity-60">
                  {confirmando
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Confirmando...</>
                    : <><CheckCircle2 className="h-4 w-4" /> Confirmar pagamento</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ───── Sidebar ───── */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-line bg-surface-2">
        <div className="flex h-16 items-center gap-2.5 px-5">
          {/* Empresa cliente mantém a própria inicial; sem white-label, a marca. */}
          {empresaConfig?.nome_exibicao ? (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg shadow-md"
              style={{ background: 'var(--brand)' }}>
              <span className="text-sm font-bold text-brand-ink">{nomeEmpresa.charAt(0).toUpperCase()}</span>
            </div>
          ) : (
            <LogoMark className="h-5 w-5 shrink-0" />
          )}
          <span className="truncate text-[15px] font-bold tracking-tight text-ink">{nomeEmpresa}</span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-4">
          {navItems.map(({ id, label, icon: Icon, onClick }) => {
            const isActive = navAtiva === id && id === 'dashboard'
            return (
              <button
                key={id}
                onClick={onClick}
                className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-raise-2 text-ink'
                    : 'text-ink-2 hover:bg-raise-1 hover:text-ink'
                }`}
              >
                {isActive && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-blue-500" />}
                <Icon className={`h-[18px] w-[18px] ${isActive ? 'text-blue-400' : ''}`} />
                {label}
              </button>
            )
          })}
        </nav>

        <div className="border-t border-line p-3">
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-2 transition-colors hover:bg-red-500/10 hover:text-red-400"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Sair
          </button>
        </div>
      </aside>

      {/* ───── Coluna principal ───── */}
      <div className="flex flex-1 flex-col pl-60">

        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-surface-2/80 px-8 backdrop-blur-xl">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-ink">{nomeEmpresa}</span>
            <span className="text-ink-4">/</span>
            <span className="font-light text-ink-2">Visão da carteira</span>
          </div>

          <div className="flex items-center gap-2">
            {/* Exports */}
            <button
              onClick={() => exportCSV(ranking_completo)}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-2 transition-colors hover:border-emerald-500/50 hover:text-ink"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" /> CSV
            </button>
            <button
              onClick={() => exportExcel(ranking_completo, resumo)}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-2 transition-colors hover:border-emerald-500/50 hover:text-ink"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" /> Excel
            </button>
            <button
              onClick={exportPDF}
              disabled={exporting}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-brand-ink transition-colors hover:bg-blue-700 disabled:opacity-50"
            >
              {exporting
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Exportando...</>
                : <><Download className="h-3.5 w-3.5" /> PDF</>}
            </button>

            <ThemeToggle />
              <div className="ml-2 flex items-center gap-2.5 border-l border-line pl-4">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight text-ink">{nomeUser}</p>
                <p className="text-xs font-light text-ink-2">{usuario?.email || 'usuario@mizan.app'}</p>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-brand-ink">
                {iniciais}
              </div>
            </div>
          </div>
        </header>

        {/* Conteúdo */}
        <main className="flex-1 px-8 py-8">

          <div className="mb-7">
            <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-4)' }}>Análise de Carteira</p>
            <h1 className="text-2xl font-semibold tracking-tight mt-1" style={{ color: 'var(--ink)' }}>Dashboard</h1>
            {resumo?.criado_por && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-ink-2">
                <Clock className="h-3 w-3 shrink-0" />
                <span>
                  Análise por <span className="font-medium text-ink-2">{resumo.criado_por}</span>
                  {resumo.criado_em && (
                    <> · {new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(resumo.criado_em))}</>
                  )}
                </span>
              </div>
            )}
          </div>

          {/* ── KPIs ── */}
          <motion.div variants={lista} initial="inicial" animate="entra"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <motion.div variants={item}><KpiCard label="Total de Devedores"     value={fmtNum(resumo.total_devedores)}  icon={Users}       accent="blue"    /></motion.div>
            <motion.div variants={item}><KpiCard label="Valor de Face"           value={fmtBRL(resumo.total_em_risco)}   sub="valor nominal da carteira"   icon={TrendingDown} accent="amber"   /></motion.div>
            <motion.div variants={item}><KpiCard label="Score Médio"             value={resumo.score_medio.toFixed(1)}   sub="recuperabilidade (0–100)"    icon={BarChart2}    accent="violet"  /></motion.div>
            <motion.div variants={item}><KpiCard label="Devedores Prioritários" value={fmtNum(prioritarios)}             sub="score ≥ 70"                  icon={Star}         accent="emerald" /></motion.div>
          </motion.div>

          {/* ── Precificação ── */}
          {!isOperador && (
            <section className="mt-6 rounded-xl border border-line bg-surface p-6">
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Precificação</p>
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Carteira de Crédito</h3>
                </div>
                <p className="text-xs" style={{ color: 'var(--ink-2)' }}>Ajuste custo e retorno para simular cenários</p>
              </div>

              <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-5">
                <div className="space-y-5 rounded-xl border border-line bg-raise-1 p-4 lg:col-span-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-ink-2">Parâmetros</p>
                  <Slider label="Custo de Cobrança" hint="Despesas operacionais e comissões"
                    value={custoCobranca} min={5} max={50} step={1} onChange={setCustoCobranca} color="blue" />
                  <Slider label="Retorno Alvo" hint="ROI mínimo desejado na operação"
                    value={retornoAlvo} min={10} max={80} step={1} onChange={setRetornoAlvo} color="emerald" />
                </div>

                <motion.div variants={lista} initial="inicial" animate="entra"
                  className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5 lg:col-span-4">
                  <motion.div variants={item}><PricingCard label="Valor Esperado de Recuperação" value={fmtBRL(pricing.ver)}
                    sub={resumo.taxa_recuperacao_esperada != null ? `${fmtPct(resumo.taxa_recuperacao_esperada)} do valor de face` : 'do valor de face'}
                    icon={ArrowUpRight} /></motion.div>
                  <motion.div variants={item}><PricingCard label="Valor Líquido (após custos)" value={fmtBRL(pricing.liquido)}
                    sub={`custos estimados: ${fmtBRL(pricing.ver - pricing.liquido)}`} icon={Percent} /></motion.div>
                  <motion.div variants={item}><PricingCard label="Preço Sugerido de Compra" value={fmtBRL(pricing.preco)}
                    sub={`${fmtPct(pricing.desconto)} de desconto sobre o face`} highlight icon={Tag} /></motion.div>
                  <motion.div variants={item}><PricingCard label="Lucro Final (líquido)" value={fmtBRL(pricing.lucro)}
                    sub={`retorno de ${pricing.retorno.toFixed(1)}% sobre o preço pago`} accent="emerald" icon={Banknote} /></motion.div>
                  <motion.div variants={item}><PricingCard label="Taxa de Recuperação Estimada" value={`${pricing.taxaRecuperacao.toFixed(1)}%`}
                    sub="do valor de face" icon={TrendingUp} /></motion.div>
                </motion.div>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-4 text-xs text-ink-2">
                {resumo?.precificacao_ml ? (
                  <>
                    <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                      ✦ ML ativo
                    </span>
                    <span><span className="font-medium text-ink-2">VER</span> = Σ (valor_dívida × <span className="font-medium text-emerald-400">taxa_ML</span>)</span>
                  </>
                ) : (
                  <span><span className="font-medium text-ink-2">VER</span> = Σ (valor_dívida × score/100)</span>
                )}
                <span className="text-ink-4">›</span>
                <span><span className="font-medium text-ink-2">Líquido</span> = VER × (1 − {custoCobranca}%)</span>
                <span className="text-ink-4">›</span>
                <span><span className="font-medium text-ink-2">Preço</span> = Líquido ÷ (1 + {retornoAlvo}%)</span>
                <span className="text-ink-4">›</span>
                <span><span className="font-medium text-emerald-400">Lucro</span> = Líquido − Preço</span>
                <span className="text-ink-4">›</span>
                <span><span className="font-medium text-ink-2">Retorno</span> = Lucro ÷ Preço</span>
              </div>
            </section>
          )}

          {/* ── Charts ── */}
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">

            {/* Aging Bar Chart */}
            <div className="rounded-xl border border-line bg-surface p-6 lg:col-span-3">
              <div className="mb-5">
                <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Distribuição</p>
                <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Aging da Carteira</h3>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={agingData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,141,166,0.28)" vertical={false} />
                  <XAxis dataKey="aging" tick={{ fontSize: 11, fill: 'var(--ink-2)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--ink-2)' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomBarTooltip />} cursor={{ fill: 'rgba(128,141,166,0.12)' }} />
                  <Bar dataKey="total_devedores" radius={[4, 4, 0, 0]} maxBarSize={48}>
                    {agingData.map((_, i) => <Cell key={i} fill={AGING_COLORS[i % AGING_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-4 flex flex-wrap gap-3">
                {agingData.map((d, i) => (
                  <div key={d.aging} className="flex items-center gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: AGING_COLORS[i] }} />
                    <span className="text-xs text-ink-2">{d.aging}</span>
                    <span className="text-xs text-ink-2">({fmtNum(d.total_devedores)})</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Cluster Pie */}
            <div className="rounded-xl border border-line bg-surface p-6 lg:col-span-2">
              <div className="mb-5">
                <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Segmentação</p>
                <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Perfis de Devedores</h3>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={distribuicao_cluster} dataKey="total_devedores" nameKey="perfil_cluster"
                    cx="50%" cy="50%" outerRadius={80} innerRadius={40} paddingAngle={2}
                  >
                    {distribuicao_cluster.map((_, i) => (
                      <Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} stroke="var(--surface)" strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: '1px solid var(--line)', background: 'var(--surface-2)', fontSize: 11, color: 'var(--ink)' }}
                    formatter={(v, _, { payload }) => [fmtNum(v), payload.perfil_cluster]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-1.5">
                {distribuicao_cluster.map((d, i) => (
                  <div key={d.perfil_cluster} className="flex items-center justify-between text-xs">
                    <div className="flex min-w-0 items-center gap-1.5">
                      <div className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: CLUSTER_COLORS[i] }} />
                      <span className="truncate text-ink-2">{d.perfil_cluster}</span>
                    </div>
                    <span className="ml-2 shrink-0 text-ink-2">{fmtNum(d.total_devedores)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Resultados Reais ── */}
          {!isOperador && !loadingPerf && perf && perf.total_feedbacks > 0 && (
            <section className="mt-6 overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex items-center justify-between border-b border-line px-6 py-4">
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Resultados Reais</p>
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Quem Pagou</h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ink-2)' }}>{perf.total_feedbacks} feedbacks registrados</p>
                </div>
                {perf.acuracia_geral != null && (
                  <span className="rounded-md border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-300">
                    Acurácia do modelo: {perf.acuracia_geral}%
                  </span>
                )}
              </div>
              <div className="overflow-x-auto p-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      {['Faixa de Score', 'Feedbacks', 'Pagaram', 'Não Pagaram', 'Taxa de Pagamento', ''].map(h => (
                        <th key={h} className="px-4 pb-3 text-left text-xs font-medium uppercase tracking-wider text-ink-2 first:pl-0">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {perf.metricas_por_faixa.map(f => {
                      const taxa = f.taxa_pagamento ?? 0
                      const barColor = taxa >= 60 ? '#10b981' : taxa >= 30 ? '#f59e0b' : '#ef4444'
                      return (
                        <tr key={f.faixa} className="border-b border-line transition-colors last:border-0 hover:bg-raise-1">
                          <td className="py-3 pl-0 pr-4 text-sm font-medium text-ink">{f.faixa}</td>
                          <td className="px-4 py-3 tabular-nums text-ink-2">{f.total_feedbacks}</td>
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-1 font-medium text-emerald-400">
                              <CheckCircle2 className="h-3.5 w-3.5" />{f.pagaram}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-1 font-medium text-red-400">
                              <XCircle className="h-3.5 w-3.5" />{f.nao_pagaram}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-sm font-bold" style={{ color: barColor }}>{taxa.toFixed(1)}%</span>
                          </td>
                          <td className="w-32 px-4 py-3">
                            <div className="h-1.5 overflow-hidden rounded-full bg-raise-3">
                              <div className="h-full rounded-full" style={{ width: `${Math.min(taxa, 100)}%`, backgroundColor: barColor }} />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* ── Pagamentos individuais ── */}
          {pagamentos.length > 0 && (
            <section className="mt-6 overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Histórico</p>
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Pagamentos Registrados</h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ink-2)' }}>{pagamentos.filter(p => p.pagou).length} pagamentos · {pagamentos.filter(p => !p.pagou).length} não pagaram</p>
                </div>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-2" />
                  <input
                    value={searchPag}
                    onChange={e => setSearchPag(e.target.value)}
                    placeholder="Buscar por nome ou CPF..."
                    className="h-9 w-52 rounded-lg border border-line bg-surface-2 pl-9 pr-3 text-xs text-ink placeholder-ink-4 transition-colors focus:border-blue-500/50 focus:outline-none"
                  />
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      {['Nome', 'CPF', 'Dívida', 'Score', 'Situação', 'Valor Recuperado', 'Data', 'Registrado por'].map(h => (
                        <th key={h} className="whitespace-nowrap px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-ink-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pagamentos
                      .filter(p => {
                        if (!searchPag) return true
                        const q = searchPag.toLowerCase()
                        return (p.nome || '').toLowerCase().includes(q) || (p.cpf || '').includes(q)
                      })
                      .slice(0, 100)
                      .map((p, i) => (
                        <tr key={i} className="border-b border-line transition-colors last:border-0 hover:bg-raise-1">
                          <td className="max-w-[160px] truncate px-4 py-3 font-medium text-ink">{p.nome || '—'}</td>
                          <td className="px-4 py-3 tabular-nums text-xs text-ink-2">{p.cpf || '—'}</td>
                          <td className="px-4 py-3 text-ink-2">{p.valor_divida != null ? fmtBRL(p.valor_divida) : '—'}</td>
                          <td className="px-4 py-3">
                            {p.score != null ? (
                              <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${p.score >= 70 ? 'bg-emerald-500/10 text-emerald-300' : p.score >= 40 ? 'bg-amber-500/10 text-amber-300' : 'bg-red-500/10 text-red-300'}`}>
                                {p.score}
                              </span>
                            ) : '—'}
                          </td>
                          <td className="px-4 py-3">
                            {p.pagou
                              ? <span className="flex items-center gap-1 text-xs font-medium text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" />Pagou</span>
                              : <span className="flex items-center gap-1 text-xs font-medium text-red-400"><XCircle className="h-3.5 w-3.5" />Não pagou</span>}
                          </td>
                          <td className="px-4 py-3 font-semibold text-emerald-400">
                            {p.pagou && p.valor_recuperado > 0 ? fmtBRL(p.valor_recuperado) : p.pagou ? '—' : <span className="text-ink-4">—</span>}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-xs text-ink-2">
                            {p.data_pagamento ? new Intl.DateTimeFormat('pt-BR').format(new Date(p.data_pagamento.substring(0, 10) + 'T12:00:00')) : '—'}
                          </td>
                          <td className="px-4 py-3 text-xs text-ink-2">
                            {p.registrado_por || <span className="text-ink-4">—</span>}
                            {p.registrado_em && <div className="text-[10px] text-ink-4">{new Date(p.registrado_em).toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })}</div>}
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
                  <p className="py-8 text-center text-sm text-ink-2">Nenhum resultado encontrado.</p>
                )}
              </div>
            </section>
          )}

          {/* ── Ranking ── */}
          <section className="mt-6 overflow-hidden rounded-xl border border-line bg-surface">
            <div className="space-y-3 border-b border-line px-6 py-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Ranking</p>
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Recuperabilidade</h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ink-2)' }}>
                    {fmtNum(filtered.length)} devedores{search || filtroPrio !== 'todos' || filtroProduto !== 'todos' || filtroUF !== 'todas' ? ' filtrados' : ''}
                    {totalPages > 1 && ` · página ${page} de ${totalPages}`}
                  </p>
                </div>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-2" />
                  <input
                    type="text"
                    placeholder="Buscar por nome ou CPF..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="h-9 w-56 rounded-lg border border-line bg-surface-2 pl-9 pr-3 text-sm text-ink placeholder-ink-4 transition-colors focus:border-blue-500/50 focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex gap-1.5">
                  {[
                    { k: 'todos', label: 'Todos',  cls: 'bg-blue-500/15 text-blue-300 border-blue-500/30'       },
                    { k: 'Alta',  label: 'Alta',   cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
                    { k: 'Média', label: 'Média',  cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30'     },
                    { k: 'Baixa', label: 'Baixa',  cls: 'bg-slate-500/15 text-ink-2 border-slate-500/30'     },
                  ].map(({ k, label, cls }) => (
                    <button key={k} onClick={() => setFiltroPrio(k)}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        filtroPrio === k ? cls : 'border-line bg-raise-1 text-ink-2 hover:text-ink'
                      }`}>
                      {label}
                    </button>
                  ))}
                </div>
                {produtos.length > 1 && (
                  <select value={filtroProduto} onChange={e => setFiltroProduto(e.target.value)}
                    className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink-2 transition-colors focus:border-blue-500/50 focus:outline-none [color-scheme:dark]">
                    <option value="todos">Todos produtos</option>
                    {produtos.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                )}
                {ufs.length > 1 && (
                  <select value={filtroUF} onChange={e => setFiltroUF(e.target.value)}
                    className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink-2 transition-colors focus:border-blue-500/50 focus:outline-none [color-scheme:dark]">
                    <option value="todas">Todos estados</option>
                    {ufs.map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                )}
                <div className="flex gap-1.5">
                  {[
                    { k: 'todos',    label: 'Todos',     cls: 'bg-slate-500/15 text-ink-2 border-slate-500/30'      },
                    { k: 'pendente', label: 'Pendente',  cls: 'bg-slate-500/15 text-ink-2 border-slate-500/30'      },
                    { k: 'pago',     label: 'Pago',      cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'  },
                    { k: 'nao_pago', label: 'Não pago',  cls: 'bg-red-500/15 text-red-300 border-red-500/30'          },
                  ].map(({ k, label, cls }) => (
                    <button key={k} onClick={() => setFiltroStatus(k)}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        filtroStatus === k ? cls : 'border-line bg-raise-1 text-ink-2 hover:text-ink'
                      }`}>
                      {label}
                    </button>
                  ))}
                </div>
                {(filtroPrio !== 'todos' || filtroProduto !== 'todos' || filtroUF !== 'todas' || filtroStatus !== 'todos' || search) && (
                  <button onClick={() => { setFiltroPrio('todos'); setFiltroProduto('todos'); setFiltroUF('todas'); setFiltroStatus('todos'); setSearch('') }}
                    className="text-xs text-ink-2 underline transition-colors hover:text-ink-2">
                    Limpar filtros
                  </button>
                )}
              </div>
            </div>

            <div className="max-h-[520px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 border-b border-line bg-surface-2">
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
                      { label: 'Status',         align: 'center' },
                    ].map(({ label, align }) => (
                      <th key={label} className={`whitespace-nowrap px-4 py-3 text-xs font-medium uppercase tracking-wider text-ink-2 text-${align}`}>
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((d) => (
                    <tr
                      key={d.rank}
                      onClick={() => navigate(`/devedor/${d.rank}`)}
                      className="group cursor-pointer border-b border-line transition-colors last:border-0 hover:bg-blue-500/[0.06]"
                    >
                      <td className="w-10 px-4 py-3 tabular-nums text-xs text-ink-2">{d.rank}</td>
                      <td className="px-4 py-3 font-medium text-ink transition-colors group-hover:text-blue-300">{d.nome}</td>
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums text-xs text-ink-2">{d.cpf}</td>
                      <td className="px-4 py-3 capitalize text-ink-2">{d.produto}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-xs text-ink-2">{fmtBRL(d.valor_divida)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-xs">
                        <span className={(d.valor_esperado_recuperacao ?? 0) > 0 ? 'font-semibold text-emerald-400' : 'text-ink-2'}>
                          {d.valor_esperado_recuperacao != null ? fmtBRL(d.valor_esperado_recuperacao) : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-xs text-ink-2">{fmtNum(d.dias_em_atraso)}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={`text-sm font-bold ${
                          d.score_recuperabilidade >= 70 ? 'text-emerald-400' :
                          d.score_recuperabilidade >= 40 ? 'text-amber-400' : 'text-ink-2'
                        }`}>
                          {d.score_recuperabilidade}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <PriorityBadge score={d.score_recuperabilidade} />
                      </td>
                      <td className="px-4 py-3 text-center" onClick={e => e.stopPropagation()}>
                        <div className="flex flex-col items-center gap-1">
                          <StatusBadge cpf={d.cpf} statusMap={statusMap} />
                          {(isAdmin || isComando) && getStatus(d.cpf, statusMap) !== 'pago' && (
                            <button
                              onClick={() => {
                                setConfirmarModal({ cpf: d.cpf, nome: d.nome })
                                setConfirmarForm({ valor_recuperado: '', data_pagamento: '' })
                                setConfirmarErro('')
                              }}
                              className="whitespace-nowrap rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/20"
                            >
                              + Confirmar pagamento
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-line bg-surface-2 px-6 py-3">
                <span className="text-xs text-ink-2">
                  {fmtNum((page - 1) * PAGE_SIZE + 1)}–{fmtNum(Math.min(page * PAGE_SIZE, filtered.length))} de {fmtNum(filtered.length)}
                </span>
                <div className="flex items-center gap-2">
                  <button onClick={() => setPage(p => p - 1)} disabled={page === 1}
                    className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-2 transition-colors hover:bg-raise-2 disabled:opacity-40">
                    ← Anterior
                  </button>
                  <span className="px-1 text-xs font-medium text-ink-2">{page} / {totalPages}</span>
                  <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages}
                    className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-2 transition-colors hover:bg-raise-2 disabled:opacity-40">
                    Próxima →
                  </button>
                </div>
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
