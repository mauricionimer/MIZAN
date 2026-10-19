import { motion } from 'framer-motion'
import { lista, item } from '../lib/motion'
import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell,
} from 'recharts'
import {
  buscarPagamentos, buscarStatusFeedbacks, confirmarPagamento,
  buscarPaginaRanking, buscarRankingCompleto,
  estadoDoModelo, buscarDistribuicao,
} from '../api'
import { useDebounce } from '../hooks/useDebounce'
import {
  Users, TrendingDown, BarChart2, Star,
  Download, Search, Loader2,
  Tag, Percent, ArrowUpRight, Banknote, FileSpreadsheet,
  CheckCircle2, XCircle, TrendingUp, X, AlertTriangle, Shuffle, ChevronDown, SlidersHorizontal,
} from 'lucide-react'
import PriorityBadge from '../components/PriorityBadge'
import { prioridadePorRank, CORTE_ALTA } from '../utils/prioridade'
import { useAnalysis } from '../context/AnalysisContext'
import { useAuth } from '../context/AuthContext'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import DistribuirFila from '../components/DistribuirFila'
import useModal from '../components/useModal'
import { NIVEL_CFG, seloFila } from '../utils/agenda'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

const AGING_ORDER = ['0-30 dias', '31-60 dias', '61-90 dias', '91-180 dias', '181+ dias']
// Gráficos usam --chart-1..5 (brief, seção 5): os tokens invertem por tema,
// então as séries seguem legíveis no claro e no escuro.
const AGING_COLORS   = ['var(--chart-2)', 'var(--chart-1)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']
const CLUSTER_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum  = (v) => new Intl.NumberFormat('pt-BR').format(v)
const fmtPct  = (v) => `${v.toFixed(1)}%`

function getStatus(cpf, statusMap) {
  const fb = statusMap[String(cpf ?? '')]
  if (!fb) return 'pendente'
  return fb.pagou ? 'pago' : 'nao_pago'
}

/* ───────────────────────── Priority badge (dark) ───────────────────────── */
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
function KpiCard({ label, value, danger = false, icon: Icon, accent, ajuda }) {
  const cor = {
    blue: 'var(--royal)', amber: 'var(--warning)',
    violet: 'var(--accent-text)', emerald: 'var(--success)',
  }[accent] ?? 'var(--text-muted)'
  return (
    <div className="card px-6 py-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-muted)' }}>
          {label}{ajuda && <DicaAjuda id={ajuda} />}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5" style={{ color: cor }} />}
      </div>
      <p className="tnum text-[1.75rem] font-semibold tracking-tight leading-none"
        style={{ color: danger ? 'var(--danger)' : 'var(--text)' }}>
        {value}
      </p>
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
    prioridadePorRank(d.rank, ranking.length),
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

// O SheetJS sozinho pesa mais que o resto da tela inteira, e o gerador de PDF
// carrega jspdf + html2canvas. Nenhum dos dois é usado até alguém clicar em
// exportar, então entram por import dinâmico em vez de no carregamento da página.
async function exportExcel(ranking, resumo) {
  const XLSX = await import('xlsx')
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
    'Prioridade':              prioridadePorRank(d.rank, ranking.length),
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
  const trackColor = color === 'emerald' ? 'var(--success)' : 'var(--royal)'
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

function PricingCard({ label, value, sub, highlight = false, accent = null, icon: Icon, ajuda, grande = false }) {
  const lucroCard = accent === 'emerald'
  const box = highlight
    ? 'border-blue-500/40 bg-blue-600/15 shadow-[0_0_0_1px_rgb(var(--c-royal) / 0.25),0_8px_28px_-8px_rgb(var(--c-royal) / 0.4)]'
    : lucroCard
      ? 'border-emerald-500/30 bg-emerald-500/[0.08]'
      : 'border-line bg-raise-1'
  const head  = highlight ? 'text-blue-300'     : lucroCard ? 'text-emerald-300'    : 'text-ink-2'
  const val   = highlight ? 'text-ink'        : lucroCard ? 'text-emerald-200'    : 'text-ink'
  const subCl = highlight ? 'text-blue-200/80'  : lucroCard ? 'text-emerald-300/70' : 'text-ink-2'
  return (
    <div className={`flex h-full flex-col justify-between gap-3 rounded-xl border p-5 ${box}`}>
      <div className="flex items-start justify-between gap-2">
        <p className={`text-xs font-semibold uppercase tracking-wide ${head}`}>
          {label}{ajuda && <DicaAjuda id={ajuda} />}
        </p>
        {Icon && <Icon className={`h-4 w-4 shrink-0 ${head}`} />}
      </div>
      <p className={`font-bold leading-none tabular-nums tracking-tight ${grande ? 'text-3xl sm:text-4xl' : 'text-2xl sm:text-3xl'} ${val}`}>{value}</p>
      {sub && <p className={`mt-0.5 text-xs ${subCl}`}>{sub}</p>}
    </div>
  )
}

export default function Dashboard({ onIrPara }) {
  const { result, setResult, setVista, setAviso } = useAnalysis()
  const { token, isAdmin, isComando, isOperador } = useAuth()
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
  const [estadoModelo, setEstadoModelo]   = useState(null)
  const [loadingPerf, setLoadingPerf]     = useState(true)
  const [pagamentos, setPagamentos]       = useState([])
  const [searchPag, setSearchPag]         = useState('')
  const [statusMap, setStatusMap]         = useState({})
  const [filtroStatus, setFiltroStatus]   = useState('todos')
  const [confirmarModal, setConfirmarModal] = useState(null)
  const [confirmando, setConfirmando]       = useState(false)
  const [confirmarForm, setConfirmarForm]   = useState({ valor_recuperado: '', data_pagamento: '' })
  const [confirmarErro, setConfirmarErro]   = useState('')
  const caixaConfirmar = useModal(!!confirmarModal, () => { setConfirmarModal(null); setConfirmarErro('') })

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

  useEffect(() => {
    if (token) estadoDoModelo(token).then(setEstadoModelo).catch(() => {})
  }, [token])

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

  // Os seletores vêm prontos do servidor. Montá-los percorrendo o ranking só
  // funcionava porque o ranking inteiro estava no navegador — que é
  // exatamente o que deixou de estar.
  const produtos = useMemo(
    () => result?.resumo?.produtos
      ?? [...new Set((result?.ranking_completo ?? []).map(d => d.produto).filter(Boolean))].sort(),
    [result])

  const ufs = useMemo(
    () => result?.resumo?.ufs
      ?? [...new Set((result?.ranking_completo ?? []).map(d => d.uf).filter(Boolean))].sort(),
    [result])

  // A página da tabela: buscada no servidor quando a carteira está gravada,
  // recortada em memória quando não está (backtest, ou análise que ainda não
  // virou carteira).
  const [pagina, setPagina]         = useState({ itens: [], filtrado: 0 })
  const [carregandoPag, setCarrPag] = useState(false)
  const [erroPagina, setErroPagina] = useState('')
  const [tentativa, setTentativa]   = useState(0)
  const PAGE_SIZE = 50

  const buscaAdiada = useDebounce(search, 350)

  // F1 — divisão da fila. `distrib` é o resumo de quem tem quantos devedores;
  // `filtroResp`: 'todos' | 'me' | 'sem' | id de um operador.
  const [distrib, setDistrib]               = useState(null)
  const [filtroResp, setFiltroResp]         = useState('todos')
  const [abrirDistribuir, setAbrirDistribuir] = useState(false)
  // Ajustes que se usam pouco ficam fechados: parâmetros da simulação e filtros da fila.
  const [verParametros, setVerParametros] = useState(false)
  const [verFiltros, setVerFiltros] = useState(false)
  const [avisoFila, setAvisoFila]           = useState('')
  const [versaoDistrib, setVersaoDistrib]   = useState(0)
  // O operador espera o resumo antes de buscar a página: senão via a carteira
  // inteira por um instante e só depois a fila dele.
  const [distribPronto, setDistribPronto]   = useState(false)
  const podeDistribuir = isAdmin || isComando

  useEffect(() => {
    setDistrib(null); setFiltroResp('todos'); setDistribPronto(false)
    if (!carteiraId) return
    let cancelado = false
    buscarDistribuicao(carteiraId)
      .then(d => {
        if (cancelado) return
        setDistrib(d)
        // O operador abre na fila dele quando a fila já foi dividida.
        if (isOperador && d.ativo && d.meus > 0) setFiltroResp('me')
      })
      .catch(() => { if (!cancelado) setDistrib(null) })
      .finally(() => { if (!cancelado) setDistribPronto(true) })
    return () => { cancelado = true }
  }, [carteiraId, isOperador])

  function recarregarDistribuicao() {
    if (!carteiraId) return
    buscarDistribuicao(carteiraId).then(setDistrib).catch(() => {})
  }

  useEffect(() => { setPage(1) }, [buscaAdiada, filtroPrio, filtroProduto, filtroUF, filtroStatus, filtroResp])

  useEffect(() => {
    if (!carteiraId) return
    if (isOperador && !distribPronto) return
    let cancelado = false
    setCarrPag(true); setErroPagina('')
    buscarPaginaRanking(carteiraId, {
      offset: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
      busca: buscaAdiada || undefined,
      produto: filtroProduto !== 'todos' ? filtroProduto : undefined,
      uf: filtroUF !== 'todas' ? filtroUF : undefined,
      prioridade: filtroPrio !== 'todos' ? filtroPrio : undefined,
      status: filtroStatus !== 'todos' ? filtroStatus : undefined,
      responsavel: filtroResp !== 'todos' ? filtroResp : undefined,
    })
      .then(d => { if (!cancelado) setPagina({ itens: d.itens, filtrado: d.filtrado }) })
      .catch(e => {
        if (cancelado) return
        // A análise aberta veio guardada no navegador, mas o servidor diz que
        // ela não é desta empresa ou não existe mais (ex.: o usuário mudou de
        // empresa). Mostrar meia tela com dados que ele não pode ver é pior do
        // que fechar: volta para a lista, com o motivo.
        if (e.status === 403 || e.status === 404) {
          setAviso('A análise que estava aberta não está disponível para a sua empresa. Abra uma da lista ou carregue o arquivo de novo.')
          setResult(null); setVista('analise')
          return
        }
        setErroPagina(e.message)
      })
      .finally(() => { if (!cancelado) setCarrPag(false) })
    return () => { cancelado = true }
  }, [carteiraId, page, buscaAdiada, filtroProduto, filtroUF, filtroPrio, filtroStatus, filtroResp, tentativa, versaoDistrib, distribPronto])

  // Sem carteira gravada não há o que paginar no servidor: filtra o que está
  // em memória, como antes.
  const filtradoLocal = useMemo(() => {
    if (carteiraId) return null
    const lista = result?.ranking_completo ?? []
    let list = buscaAdiada
      ? lista.filter(d =>
          d.nome?.toLowerCase().includes(buscaAdiada.toLowerCase()) ||
          d.cpf?.includes(buscaAdiada)
        )
      : lista
    // Relativa à fila inteira, não à lista já filtrada: senão filtrar por
    // produto reclassificaria a prioridade de quem sobrou.
    if (filtroPrio !== 'todos')
      list = list.filter(d => prioridadePorRank(d.rank, lista.length) === filtroPrio)
    if (filtroProduto !== 'todos')
      list = list.filter(d => d.produto === filtroProduto)
    if (filtroUF !== 'todas')
      list = list.filter(d => d.uf === filtroUF)
    if (filtroStatus !== 'todos')
      list = list.filter(d => getStatus(d.cpf, statusMap) === filtroStatus)
    return list
  }, [carteiraId, result, buscaAdiada, filtroPrio, filtroProduto, filtroUF, filtroStatus, statusMap])

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

  const { resumo, distribuicao_aging, distribuicao_cluster } = result
  const ranking_completo = result.ranking_completo ?? []
  const totalFila = resumo.total_devedores ?? ranking_completo.length

  const agingData    = [...distribuicao_aging].sort(
    (a, b) => AGING_ORDER.indexOf(a.aging) - AGING_ORDER.indexOf(b.aging)
  )
  // Prioritário é quem está no topo da fila, não quem tem score alto: a fila
  // é ordenada por valor esperado, e contar por score daria um número que não
  // corresponde a nenhuma etiqueta da tabela. Como "Alta" é o primeiro quinto
  // por definição, o número é o tamanho dessa faixa — não precisa da lista.
  // Mesma aritmética inteira que o backend usa para recortar a faixa, para as
  // duas contas não discordarem na fronteira.
  const prioritarios = Math.floor((totalFila * Math.round(CORTE_ALTA * 100)) / 100)

  const totalFiltrado = filtradoLocal ? filtradoLocal.length : pagina.filtrado
  const totalPages    = Math.max(1, Math.ceil(totalFiltrado / PAGE_SIZE))
  const respPadrao    = isOperador && distrib?.ativo && distrib?.meus > 0 ? 'me' : 'todos'
  const nFiltros      = [filtroResp !== respPadrao, filtroPrio !== 'todos', filtroProduto !== 'todos', filtroUF !== 'todas', filtroStatus !== 'todos'].filter(Boolean).length
  const paginated     = filtradoLocal
    ? filtradoLocal.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
    : pagina.itens

  // Exportar precisa da fila inteira, que não está mais no navegador: busca em
  // páginas grandes, mostrando o progresso porque para carteira de banco isso
  // leva alguns segundos e um botão mudo pareceria travado.
  const [exportando, setExportando] = useState(null)   // {feito, total} | null

  async function filaInteira() {
    if (!carteiraId) return ranking_completo
    setExportando({ feito: 0, total: totalFila })
    try {
      return await buscarRankingCompleto(carteiraId, (feito, total) => setExportando({ feito, total }))
    } finally {
      setExportando(null)
    }
  }

  async function baixarCSV()   { exportCSV(await filaInteira()) }
  async function baixarExcel() { exportExcel(await filaInteira(), resumo) }

  async function exportPDF() {
    setExporting(true)
    try {
      const { gerarRelatorioPDF } = await import('../utils/gerarPDF')
      const fila = await filaInteira()
      await gerarRelatorioPDF({ ...result, ranking_completo: fila },
                              pricing, custoCobranca, retornoAlvo)
    } finally {
      setExporting(false)
    }
  }

  // Exportações da carteira: ficam na barra de cima da casca, ao lado do
  // usuário, porque pertencem à vista e não à navegação.
  const acoesTopo = (
    <>
      <button onClick={baixarCSV} className="btn-secondary btn-sm">
        <FileSpreadsheet className="h-3.5 w-3.5" /> CSV
      </button>
      <button onClick={baixarExcel} className="btn-secondary btn-sm">
        <FileSpreadsheet className="h-3.5 w-3.5" /> Excel
      </button>
      <button onClick={exportPDF} disabled={exporting} className="btn-primary btn-sm">
        {exporting
          ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Exportando...</>
          : <><Download className="h-3.5 w-3.5" /> PDF</>}
      </button>
    </>
  )

  return (
    <AppShell secao="dashboard" onIrPara={onIrPara} temResultado
      titulo="Visão da carteira" acoes={acoesTopo}>

      {/* ───── Modal de confirmação de pagamento ───── */}
      {abrirDistribuir && (
        <DistribuirFila
          carteiraId={carteiraId}
          resumo={distrib}
          onFechar={() => setAbrirDistribuir(false)}
          onFeito={r => {
            setAbrirDistribuir(false)
            setAvisoFila(`Fila distribuída: ${r.por_operador.map(o => `${(o.nome || 'Operador').split(' ')[0]} recebeu ${fmtNum(o.devedores)}`).join(' · ')}.`)
            recarregarDistribuicao()
            setVersaoDistrib(v => v + 1)
          }}
        />
      )}
      {confirmarModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => { setConfirmarModal(null); setConfirmarErro('') }}>
          <div ref={caixaConfirmar} role="dialog" aria-modal="true" aria-labelledby="confirmar-pag-titulo"
            onClick={e => e.stopPropagation()}
            className="w-full max-w-md space-y-5 rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 id="confirmar-pag-titulo" className="text-base font-bold text-ink">Confirmar pagamento</h2>
                <p className="mt-0.5 text-xs text-ink-2">
                  <span className="font-semibold text-ink">{confirmarModal.nome}</span>
                  {' · '}<span className="tabular-nums">{confirmarModal.cpf}</span>
                </p>
              </div>
              <button onClick={() => { setConfirmarModal(null); setConfirmarErro('') }} aria-label="Fechar"
                className="-m-1.5 rounded-lg p-2.5 text-ink-2 transition-colors hover:bg-raise-3 hover:text-ink">
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
                  className="btn-secondary flex-1">
                  Cancelar
                </button>
                <button type="submit" disabled={confirmando} className="btn-primary flex-1">
                  {confirmando
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Confirmando...</>
                    : <><CheckCircle2 className="h-4 w-4" /> Confirmar pagamento</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


          <div className="mb-7">
            <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-4)' }}>Análise de Carteira</p>
            <h1 className="text-2xl font-semibold tracking-tight mt-1" style={{ color: 'var(--ink)' }}>Painel da carteira</h1>
          </div>

          {/* Em que dados o score se apoia: o número mais importante para não
              superestimar o que a tela mostra. Some quando o modelo é de dados reais. */}
          {estadoModelo && estadoModelo.nivel !== 'ok' && (
            <div className="mb-4 flex items-start gap-2.5 rounded-xl p-3"
              style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)' }}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--warning)' }} />
              <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                {estadoModelo.aviso}<DicaAjuda id="estado-do-modelo" />
              </p>
            </div>
          )}

          {/* ── KPIs ── */}
          <motion.div variants={lista} initial="inicial" animate="entra"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <motion.div variants={item}><KpiCard label="Total de Devedores"     value={fmtNum(resumo.total_devedores)}  icon={Users}       accent="blue"    /></motion.div>
            <motion.div variants={item}><KpiCard ajuda="valor-de-face" label="Valor de Face"           value={fmtBRL(resumo.total_em_risco)}   icon={TrendingDown} accent="amber"   /></motion.div>
            <motion.div variants={item}><KpiCard ajuda="score-recuperabilidade" label="Score Médio"             value={resumo.score_medio.toFixed(1)}    icon={BarChart2}    accent="violet"  /></motion.div>
            <motion.div variants={item}><KpiCard ajuda="devedores-prioritarios" label="Devedores Prioritários" value={fmtNum(prioritarios)}                  icon={Star}         accent="emerald" /></motion.div>
          </motion.div>

          {/* ── Ciclo de cobrança ──
              As fases não são só faixas de tempo: cada uma tem economia
              própria. Entre 31 e 360 dias a cobrança é terceirizada e cobra
              comissão; acima de 360 a alternativa passa a ser vender. */}
          {!isOperador && resumo.ciclo_cobranca?.length > 0 && (
            <section className="mt-6 rounded-xl border border-line bg-surface p-6">
              <p className="section-label">Ciclo de cobrança<DicaAjuda id="fases-do-ciclo" /></p>
              <h3 className="text-sm font-semibold mt-0.5 mb-5" style={{ color: 'var(--ink)' }}>
                Em que regime cada parte da carteira está
              </h3>

              {/* Uma fase por cartão, lado a lado: o valor esperado em destaque e,
                  embaixo, quanto da carteira (valor de face) está naquela fase. */}
              <div className={`grid grid-cols-1 gap-4 ${resumo.ciclo_cobranca.length >= 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
                {resumo.ciclo_cobranca.map((f, i, todas) => {
                  const totalFace = todas.reduce((a, x) => a + (x.valor_face || 0), 0) || 1
                  const fatia = ((f.valor_face || 0) / totalFace) * 100
                  // Escala sequencial: a fase mais adiantada do ciclo vem mais
                  // forte. Não é juízo de valor, é posição no tempo.
                  const intensidade = 0.35 + (0.6 * i) / Math.max(1, todas.length - 1)
                  return (
                    <div key={f.fase} className="flex flex-col gap-3 rounded-xl border border-line bg-raise-1 p-5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="h-2.5 w-2.5 rounded-sm shrink-0"
                            style={{ background: `rgb(var(--c-royal) / ${intensidade})` }} />
                          <span className="text-sm font-semibold truncate" style={{ color: 'var(--ink)' }}>{f.rotulo}</span>
                        </div>
                        {f.tem_comissao && (
                          <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded shrink-0"
                            style={{ background: 'rgb(var(--c-warning) / 0.14)', color: 'var(--warning)' }}>
                            paga comissão
                          </span>
                        )}
                      </div>
                      <div>
                        <p className="text-2xl font-bold tabular-nums tracking-tight" style={{ color: 'var(--ink)' }}>
                          {fmtBRL(f.valor_esperado_liquido)}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>
                          valor esperado<DicaAjuda id="valor-esperado-liquido" /> · {fmtNum(f.devedores)} devedores
                        </p>
                      </div>
                      <div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: 'var(--raise-3)' }}>
                          <div className="h-full rounded-full"
                            style={{ width: `${fatia}%`, background: `rgb(var(--c-royal) / ${intensidade})` }} />
                        </div>
                        <p className="text-xs mt-1.5 tabular-nums" style={{ color: 'var(--ink-2)' }}>
                          {fatia.toFixed(0)}% da carteira · {fmtBRL(f.valor_face)} de face
                        </p>
                      </div>
                      <p className="text-[11px] leading-snug mt-auto" style={{ color: 'var(--ink-3)' }}>{f.descricao}</p>
                    </div>
                  )
                })}
              </div>

              {/* Acima de 360 dias: cobrar ou vender */}
              {resumo.write_off && (
                <div className="mt-5 rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
                  <p className="section-label mb-2">Acima de 360 dias: cobrar ou vender?<DicaAjuda id="cessao-e-write-off" /></p>
                  <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
                    <div>
                      <p className="text-xs" style={{ color: 'var(--ink-3)' }}>Cobrando</p>
                      <p className="text-xl font-semibold tabular-nums" style={{ color: 'var(--ink)' }}>
                        {fmtBRL(resumo.write_off.esperado_cobrando)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs" style={{ color: 'var(--ink-3)' }}>Cedendo a fundo de NPL</p>
                      <p className="text-xl font-semibold tabular-nums" style={{ color: 'var(--ink)' }}>
                        {fmtBRL(resumo.write_off.valor_se_vendida)}
                      </p>
                    </div>
                  </div>
                  <p className="text-sm mt-3 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                    {resumo.write_off.vale_mais_vender
                      ? 'Nesta faixa, vender a carteira rende mais do que continuar cobrando — cobrar estaria destruindo valor.'
                      : `Nesta faixa, continuar cobrando rende mais do que ceder, considerando os ${fmtNum(resumo.write_off.devedores)} devedores acima de 360 dias.`}
                  </p>
                </div>
              )}

              {/* O único aviso do ciclo hoje é a comissão não informada: curto, com
                  o caminho para resolver, em vez do parágrafo técnico do servidor. */}
              {resumo.aviso_ciclo && (
                <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl px-4 py-3"
                  style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)' }}>
                  <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--warning)' }} />
                  <p className="text-xs flex-1 min-w-[12rem]" style={{ color: 'var(--ink-2)' }}>
                    Comissão do escritório não informada: o valor da fase especializada está sem o desconto dela.
                    <DicaAjuda id="comissao-de-cobranca" />
                  </p>
                  <button onClick={() => navigate('/premissas')}
                    className="text-xs font-semibold shrink-0 rounded-md px-2.5 py-1 hover:bg-raise-2"
                    style={{ color: 'var(--accent-text)' }}>
                    Informar em Premissas →
                  </button>
                </div>
              )}
            </section>
          )}

          {resumo.salvamento_incompleto && (
            <div className="flex items-start gap-2.5 rounded-xl p-3"
              style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)' }}>
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
              <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                A análise foi calculada, mas não foi possível gravá-la por completo no banco. Ela vale
                para esta sessão e não ficará salva: reenvie o arquivo para tentar de novo.
              </p>
            </div>
          )}

          {/* ── Precificação ── */}
          {!isOperador && (
            <section className="mt-6 rounded-xl border border-line bg-surface p-6">
              <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Precificação</p>
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Carteira de Crédito<DicaAjuda id="precificacao-simulador" /></h3>
                </div>
                <button type="button" onClick={() => setVerParametros(v => !v)} aria-expanded={verParametros}
                  className="btn-secondary btn-sm">
                  <SlidersHorizontal className="h-3.5 w-3.5" /> Parâmetros
                  <span className="font-normal text-ink-2">· custo {custoCobranca}% · retorno {retornoAlvo}%</span>
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${verParametros ? 'rotate-180' : ''}`} />
                </button>
              </div>

              {verParametros && (
                <div className="mb-6 grid gap-5 rounded-xl border border-line bg-raise-1 p-4 sm:grid-cols-2">
                  <Slider label="Custo de Cobrança" hint="Despesas operacionais e comissões"
                    value={custoCobranca} min={5} max={50} step={1} onChange={setCustoCobranca} color="blue" />
                  <Slider label="Retorno Alvo" hint="ROI mínimo desejado na operação"
                    value={retornoAlvo} min={10} max={80} step={1} onChange={setRetornoAlvo} color="emerald" />
                </div>
              )}

              <div className="grid grid-cols-1 items-stretch gap-6">

                {/* Duas linhas que ocupam a altura dos parâmetros: em cima os números
                    de base, embaixo (maiores) os dois que decidem a compra. */}
                <motion.div variants={lista} initial="inicial" animate="entra"
                  className="grid grid-cols-1 gap-4 sm:grid-cols-6 sm:auto-rows-fr">
                  <motion.div variants={item} className="sm:col-span-2"><PricingCard ajuda="valor-esperado" label="Valor Esperado de Recuperação" value={fmtBRL(pricing.ver)}
                    icon={ArrowUpRight} /></motion.div>
                  <motion.div variants={item} className="sm:col-span-2"><PricingCard label="Após o custo simulado" value={fmtBRL(pricing.liquido)} icon={Percent} /></motion.div>
                  <motion.div variants={item} className="sm:col-span-2"><PricingCard ajuda="taxa-de-recuperacao" label="Taxa de Recuperação Estimada" value={`${pricing.taxaRecuperacao.toFixed(1)}%`} icon={TrendingUp} /></motion.div>
                  <motion.div variants={item} className="sm:col-span-3"><PricingCard label="Preço Sugerido de Compra" value={fmtBRL(pricing.preco)} highlight grande icon={Tag} /></motion.div>
                  <motion.div variants={item} className="sm:col-span-3"><PricingCard label="Lucro Final (simulado)" value={fmtBRL(pricing.lucro)} accent="emerald" grande icon={Banknote} /></motion.div>
                </motion.div>
              </div>

            </section>
          )}

          {/* ── Charts ── */}
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">

            {/* Aging Bar Chart */}
            <div className="rounded-xl border border-line bg-surface p-6 lg:col-span-3">
              <div className="mb-5">
                <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-2)' }}>Distribuição</p>
                <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Aging da Carteira<DicaAjuda id="aging" /></h3>
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
                <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Perfis de Devedores<DicaAjuda id="perfil-cluster" /></h3>
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
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Quem Pagou<DicaAjuda id="quem-pagou" /></h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ink-2)' }}>{perf.total_feedbacks} feedbacks registrados</p>
                </div>
                {perf.acuracia_geral != null && (
                  <span className="rounded-md border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-300">
                    Acurácia do modelo: {perf.acuracia_geral}%<DicaAjuda id="acuracia-geral" />
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
                      const barColor = taxa >= 60 ? 'var(--success)' : taxa >= 30 ? 'var(--warning)' : 'var(--danger)'
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
                  <h3 className="text-sm font-semibold mt-0.5" style={{ color: 'var(--ink)' }}>Pagamentos Registrados<DicaAjuda id="pagamentos-registrados" /></h3>
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
                  <h3 className="text-lg font-semibold" style={{ color: 'var(--ink)' }}>Recuperabilidade<DicaAjuda id="fila-ordem" /></h3>
                  {estadoModelo?.nivel === 'sintetico' && (
                    <p className="text-xs mt-0.5" style={{ color: 'var(--warning)' }}>
                      O score desta fila vem de um modelo treinado com dados simulados: ordena por premissas declaradas, não pelo histórico desta carteira.
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                {podeDistribuir && carteiraId && distrib?.ativo && (
                  <button onClick={() => setAbrirDistribuir(true)}
                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 text-xs font-semibold text-blue-300 transition-colors hover:bg-blue-500/20">
                    <Shuffle className="h-3.5 w-3.5" /> Distribuir fila
                  </button>
                )}
                <button type="button" onClick={() => setVerFiltros(v => !v)} aria-expanded={verFiltros}
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 text-xs font-semibold text-ink-2 transition-colors hover:text-ink">
                  Responsável e filtros
                  {nFiltros > 0 && <span className="rounded-full bg-blue-500/20 px-1.5 text-[11px] font-bold text-blue-300">{nFiltros}</span>}
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${verFiltros ? 'rotate-180' : ''}`} />
                </button>
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
              </div>
              {avisoFila && (
                <p className="flex items-center gap-1.5 text-xs text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> {avisoFila}
                </p>
              )}
              {verFiltros && (
              <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-3">
              {carteiraId && distrib?.ativo && (podeDistribuir || distrib.meus > 0 || (distrib.por_operador?.length ?? 0) > 0) && (
                <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-2">
                    Responsável<DicaAjuda id="divisao-da-fila" />
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      ...(isOperador ? [{ k: 'me', label: `Minha fila${distrib.meus ? ` · ${fmtNum(distrib.meus)}` : ''}` }] : []),
                      { k: 'todos', label: 'Toda a carteira' },
                      { k: 'sem', label: `Sem responsável · ${fmtNum(distrib.sem_responsavel?.devedores ?? 0)}` },
                    ].map(({ k, label }) => (
                      <button key={k} onClick={() => setFiltroResp(k)}
                        className={`min-h-[40px] md:min-h-[32px] rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                          filtroResp === k ? 'border-blue-500/30 bg-blue-500/15 text-blue-300' : 'border-line bg-raise-1 text-ink-2 hover:text-ink'
                        }`}>
                        {label}
                      </button>
                    ))}
                  </div>
                  {podeDistribuir && (distrib.por_operador?.length ?? 0) > 0 && (
                    <select value={['todos', 'me', 'sem'].includes(filtroResp) ? '' : filtroResp}
                      onChange={e => setFiltroResp(e.target.value || 'todos')}
                      aria-label="Ver a fila de um operador"
                      className="rounded-lg border border-line bg-surface px-2 py-1 text-xs text-ink-2 focus:border-blue-500/50 focus:outline-none [color-scheme:dark]">
                      <option value="">Fila de um operador…</option>
                      {distrib.por_operador.map(g => (
                        <option key={g.operador_id} value={g.operador_id}>{g.nome || 'Operador'} · {fmtNum(g.devedores)}</option>
                      ))}
                    </select>
                  )}
                  {podeDistribuir && (
                    <span className="ml-auto text-xs text-ink-2">
                      {(distrib.por_operador ?? []).length === 0
                        ? 'A fila ainda não foi dividida.'
                        : (distrib.por_operador ?? []).map(g => `${(g.nome || 'Operador').split(' ')[0]} ${fmtNum(g.devedores)}`).join(' · ')
                          + ` · sem responsável ${fmtNum(distrib.sem_responsavel?.devedores ?? 0)}`}
                    </span>
                  )}
                </div>
              )}
              {carteiraId && podeDistribuir && distrib && distrib.ativo === false && (
                <p className="text-xs text-ink-2">
                  Divisão da fila entre operadores: falta rodar <code>sql/migracao_operador.sql</code> no Supabase.
                </p>
              )}
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
              )}
            </div>

            <div className="max-h-[520px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 border-b border-line bg-surface-2">
                  <tr>
                    {[
                      { label: '#',              align: 'left'   },
                      { label: 'Nome',           align: 'left'   },
                      ...(carteiraId && distrib?.ativo ? [{ label: 'Responsável', align: 'left' }] : []),
                      { label: 'CPF',            align: 'left'   },
                      { label: 'Produto',        align: 'left'   },
                      { label: 'Valor Face',     align: 'right'  },
                      { label: 'Valor Esperado', align: 'right', ajuda: 'valor-esperado' },
                      { label: 'Dias Atraso',    align: 'right'  },
                      { label: 'Score',          align: 'right', ajuda: 'score-recuperabilidade' },
                      { label: 'Prioridade',     align: 'center', ajuda: 'prioridade-alta-media-baixa' },
                      { label: 'Status',         align: 'center', ajuda: 'filtros-da-fila' },
                    ].map(({ label, align, ajuda }) => (
                      <th key={label} className={`whitespace-nowrap px-4 py-3 text-xs font-medium uppercase tracking-wider text-ink-2 text-${align}`}>
                        {label}{ajuda && <DicaAjuda id={ajuda} />}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Antes o erro ficava escondido e a tabela só dizia "0 devedores". */}
                  {erroPagina && !carregandoPag && (
                    <tr><td colSpan={20} className="px-6 py-8 text-center text-sm">
                      <span style={{ color: 'var(--danger)' }}>Não foi possível carregar os devedores: {erroPagina}</span>
                      <button onClick={() => setTentativa(t => t + 1)}
                        className="ml-3 rounded-md border border-line bg-raise-1 px-2.5 py-1 text-xs text-ink-2 hover:text-ink">
                        Tentar de novo
                      </button>
                    </td></tr>
                  )}
                  {paginated.map((d) => (
                    <tr
                      key={d.rank}
                      onClick={() => navigate(`/devedor/${d.rank}`)}
                      className="group cursor-pointer border-b border-line transition-colors last:border-0 hover:bg-blue-500/[0.06]"
                    >
                      <td className="w-10 px-4 py-3 tabular-nums text-xs text-ink-2">
                        {d.rank}
                      </td>
                      <td className="px-4 py-3 font-medium text-ink transition-colors group-hover:text-blue-300">
                        {d.nome}
                        {d.agenda && (() => {
                          const cfg = NIVEL_CFG[d.agenda.nivel] ?? NIVEL_CFG.safe
                          return (
                            <span className="ml-2 inline-flex items-center whitespace-nowrap rounded-full px-1.5 py-px align-middle text-[10px] font-semibold"
                              title={d.agenda.operador_nome ? `Agendado por ${d.agenda.operador_nome}` : undefined}
                              style={{ background: cfg.fundo, color: cfg.cor, border: `1px solid ${cfg.borda}` }}>
                              {seloFila(d.agenda)}
                            </span>
                          )
                        })()}
                        {d.dados_incompletos && (
                          <AlertTriangle className="ml-1.5 inline h-3.5 w-3.5 align-text-bottom" style={{ color: 'var(--warning)' }}
                            aria-label={`Dados incompletos: ${d.aviso_dados || ''}`} title={`Dados incompletos: ${d.aviso_dados || ''}`} />
                        )}
                      </td>
                      {carteiraId && distrib?.ativo && (
                        <td className="whitespace-nowrap px-4 py-3 text-xs">
                          {d.responsavel_nome
                            ? <span className="text-ink-2">{d.responsavel_nome}</span>
                            : <span className="text-ink-2 opacity-50">—</span>}
                        </td>
                      )}
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
                        <PriorityBadge rank={d.rank} total={totalFila} />
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
                  {fmtNum((page - 1) * PAGE_SIZE + 1)}–{fmtNum(Math.min(page * PAGE_SIZE, totalFiltrado))} de {fmtNum(totalFiltrado)}
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
    </AppShell>
  )
}
