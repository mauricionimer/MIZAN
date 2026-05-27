import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Phone, Tag, Zap, MessageSquare, Brain, Plus, ClipboardList, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import PriorityBadge from '../components/PriorityBadge'
import { buscarRecomendacao, registrarContato, listarContatos, buscarStatusFeedbacks, traduzirErroRede } from '../api'

const fmtBRL = (v) => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
  : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

function DataRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-50 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-semibold text-slate-800">{value ?? '—'}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-5">
      <p className="section-label mb-3">{title}</p>
      {children}
    </div>
  )
}

const CANAL_ICONS    = { whatsapp: '💬', telefone: '📞', carta: '✉️' }
const RESULTADO_CFG  = {
  contactado:     { label: 'Contactado',        color: 'text-blue-700',    bg: 'bg-blue-50 ring-1 ring-blue-200/60'    },
  sem_resposta:   { label: 'Sem resposta',       color: 'text-slate-500',   bg: 'bg-slate-100 ring-1 ring-slate-200/60'  },
  prometeu_pagar: { label: 'Prometeu pagar',     color: 'text-amber-700',   bg: 'bg-amber-50 ring-1 ring-amber-200/60'   },
  pagou:          { label: 'Pagou',              color: 'text-emerald-700', bg: 'bg-emerald-50 ring-1 ring-emerald-200/60' },
  nao_quis:       { label: 'Não quis negociar',  color: 'text-red-600',     bg: 'bg-red-50 ring-1 ring-red-200/60'     },
}

function HistoricoContatos({ cpf, rec }) {
  const [contatos, setContatos]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [formAberto, setFormAberto] = useState(false)
  const [salvando, setSalvando]     = useState(false)
  const [erro, setErro]             = useState(null)
  const [form, setForm] = useState({
    canal: 'whatsapp', resultado: 'contactado',
    data_contato: new Date().toISOString().slice(0, 10), observacao: '',
    valor_recuperado: '', desconto_oferecido_pct: '',
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  useEffect(() => {
    listarContatos(cpf)
      .then(setContatos)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [cpf])

  async function salvar() {
    setSalvando(true); setErro(null)
    const payload = { cpf, canal: form.canal, resultado: form.resultado, data_contato: form.data_contato, observacao: form.observacao }
    if (rec?.acao_id != null) payload.acao_bandit_id = rec.acao_id
    if (form.valor_recuperado) payload.valor_recuperado = parseFloat(form.valor_recuperado)
    if (form.desconto_oferecido_pct) payload.desconto_oferecido_pct = parseFloat(form.desconto_oferecido_pct)

    const _tentar = async (tentativa) => {
      try {
        const res = await registrarContato(payload)
        setContatos(prev => [res.contato, ...prev])
        setFormAberto(false)
        setForm({ canal: 'whatsapp', resultado: 'contactado', data_contato: new Date().toISOString().slice(0, 10), observacao: '', valor_recuperado: '', desconto_oferecido_pct: '' })
      } catch (e) {
        const isRede = e?.message === 'Failed to fetch' || e?.message?.includes('Failed to fetch')
        if (isRede && tentativa < 2) {
          setErro('Servidor acordando... tentando novamente em 5s')
          await new Promise(r => setTimeout(r, 5000))
          setErro(null)
          return _tentar(tentativa + 1)
        }
        setErro(traduzirErroRede(e))
      }
    }

    try { await _tentar(1) }
    finally { setSalvando(false) }
  }

  const fmtData = (iso) => iso
    ? new Intl.DateTimeFormat('pt-BR').format(new Date(iso.includes('T') ? iso : iso + 'T12:00:00'))
    : '—'

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-3.5 w-3.5 text-slate-400" />
          <p className="section-label">
            Histórico de Contatos{contatos.length > 0 && ` (${contatos.length})`}
          </p>
        </div>
        <button onClick={() => setFormAberto(o => !o)}
          className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors">
          <Plus className="h-3.5 w-3.5" /> Registrar contato
        </button>
      </div>

      {formAberto && (
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Canal</label>
              <select value={form.canal} onChange={e => set('canal', e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition">
                <option value="whatsapp">WhatsApp</option>
                <option value="telefone">Ligação Telefônica</option>
                <option value="carta">Carta / E-mail</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Data</label>
              <input type="date" value={form.data_contato} onChange={e => set('data_contato', e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Resultado</label>
            <select value={form.resultado} onChange={e => set('resultado', e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition">
              <option value="contactado">Contactado</option>
              <option value="sem_resposta">Sem resposta</option>
              <option value="prometeu_pagar">Prometeu pagar</option>
              <option value="pagou">Pagou</option>
              <option value="nao_quis">Não quis negociar</option>
            </select>
          </div>
          {(form.resultado === 'pagou' || form.resultado === 'prometeu_pagar') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Valor Recuperado (R$)</label>
                <input type="number" min="0" step="0.01" value={form.valor_recuperado}
                  onChange={e => set('valor_recuperado', e.target.value)}
                  placeholder="0,00"
                  className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                  Desconto Oferecido (%)
                  {rec?.oferta_label && <span className="text-blue-400 ml-1 font-normal">· IA: {rec.oferta_label}</span>}
                </label>
                <input type="number" min="0" max="100" step="1" value={form.desconto_oferecido_pct}
                  onChange={e => set('desconto_oferecido_pct', e.target.value)}
                  placeholder="Ex: 30"
                  className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition" />
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Observação (opcional)</label>
            <textarea value={form.observacao} onChange={e => set('observacao', e.target.value)}
              rows={2} placeholder="Detalhes do contato..."
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white transition resize-none" />
          </div>
          {erro && <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{erro}</p>}
          <div className="flex gap-2">
            <button onClick={salvar} disabled={salvando}
              className="btn-primary py-1.5 disabled:opacity-50">
              {salvando ? 'Salvando...' : 'Salvar'}
            </button>
            <button onClick={() => { setFormAberto(false); setErro(null) }}
              className="px-4 py-1.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-slate-100 transition-colors">
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-slate-50">
        {loading && (
          <div className="flex items-center justify-center py-8 text-slate-400 text-xs gap-2">
            <div className="h-3.5 w-3.5 border-2 border-slate-200 border-t-blue-400 rounded-full animate-spin" />
            Carregando...
          </div>
        )}
        {!loading && contatos.length === 0 && (
          <p className="text-xs text-slate-400 text-center py-8">Nenhum contato registrado ainda.</p>
        )}
        {contatos.map(c => {
          const res = RESULTADO_CFG[c.resultado] ?? { label: c.resultado, color: 'text-slate-500', bg: 'bg-slate-100' }
          return (
            <div key={c.id} className="px-5 py-3.5 flex items-start gap-3">
              <span className="text-base shrink-0 mt-0.5">{CANAL_ICONS[c.canal] ?? '📋'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${res.bg} ${res.color}`}>
                    {res.label}
                  </span>
                  <span className="text-xs text-slate-400">{fmtData(c.data_contato || c.created_at)}</span>
                  {c.usuario_nome && (
                    <span className="text-xs text-slate-300">por {c.usuario_nome}</span>
                  )}
                </div>
                {c.observacao && (
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{c.observacao}</p>
                )}
                {c.valor_recuperado > 0 && (
                  <p className="text-xs text-emerald-600 font-semibold mt-0.5">{fmtBRL(c.valor_recuperado)} recuperados</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const URGENCIA_CONFIG = {
  Alta:  { color: '#ef4444', bg: '#fef2f2', ring: '#fecaca' },
  Média: { color: '#f59e0b', bg: '#fffbeb', ring: '#fde68a' },
  Baixa: { color: '#10b981', bg: '#f0fdf4', ring: '#a7f3d0' },
}

const MODO_CONFIG = {
  exploração_inicial: { label: 'Explorando', color: 'text-amber-600',   bg: 'bg-amber-50',   ring: 'ring-amber-200'   },
  aprendendo:         { label: 'Aprendendo', color: 'text-blue-600',    bg: 'bg-blue-50',    ring: 'ring-blue-200'    },
  calibrado:          { label: 'Calibrado',  color: 'text-emerald-600', bg: 'bg-emerald-50', ring: 'ring-emerald-200' },
}

function ApproachRecommendation({ devedor, rec, loading, erro }) {
  const score = devedor.score_recuperabilidade ?? 0
  const urgencia = score >= 70 ? 'Alta' : score >= 40 ? 'Média' : 'Baixa'
  const urgCfg = URGENCIA_CONFIG[urgencia]
  const modoCfg = rec ? (MODO_CONFIG[rec.modo] ?? MODO_CONFIG.aprendendo) : null

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <p className="section-label">Recomendação de Abordagem</p>
        {modoCfg && (
          <span className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ring-1 ${modoCfg.color} ${modoCfg.bg} ${modoCfg.ring}`}>
            <Brain className="h-3 w-3" />
            IA · {modoCfg.label}
          </span>
        )}
      </div>

      <div className="p-5 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-slate-400 text-sm gap-2">
            <div className="h-4 w-4 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
            Consultando IA...
          </div>
        )}

        {erro && (
          <p className="text-sm text-red-500 text-center py-4">{erro}</p>
        )}

        {rec && !loading && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div
                className="flex flex-col items-center gap-1.5 rounded-xl p-3 ring-1"
                style={{ backgroundColor: urgCfg.bg, ringColor: urgCfg.ring }}
              >
                <Zap className="h-4 w-4" style={{ color: urgCfg.color }} />
                <p className="text-xs text-slate-500 font-medium">Urgência</p>
                <span className="text-sm font-bold" style={{ color: urgCfg.color }}>{urgencia}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3 bg-blue-50 ring-1 ring-blue-100">
                <Phone className="h-4 w-4 text-blue-500" />
                <p className="text-xs text-slate-500 font-medium">Canal</p>
                <span className="text-sm font-bold text-blue-700 text-center leading-tight">{rec.canal_label}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3 bg-emerald-50 ring-1 ring-emerald-100">
                <Tag className="h-4 w-4 text-emerald-500" />
                <p className="text-xs text-slate-500 font-medium">Oferta</p>
                <span className="text-sm font-bold text-emerald-700 text-center leading-tight">{rec.oferta_label}</span>
              </div>
            </div>

            <div className="flex gap-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
              <MessageSquare className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
              <p className="text-sm text-slate-600 leading-relaxed">{rec.justificativa}</p>
            </div>

            {rec.total_interacoes > 0 && (
              <p className="text-xs text-slate-400 text-right">
                {rec.total_interacoes} interações registradas · esta ação usada {rec.n_tentativas_acao}×
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function DebtorDetail() {
  const { rank } = useParams()
  const navigate = useNavigate()
  const { result } = useAnalysis()

  const d = result?.ranking_completo.find(x => x.rank === Number(rank)) ?? null

  const [rec, setRec]               = useState(null)
  const [recLoading, setRecLoading] = useState(true)
  const [recErro, setRecErro]       = useState(null)
  const [statusPag, setStatusPag]   = useState(null)

  useEffect(() => {
    if (!result) { navigate('/'); return }
    if (!d) navigate('/dashboard')
  }, [result, d, navigate])

  useEffect(() => {
    if (!d?.cpf) return
    setRecLoading(true)
    buscarRecomendacao(d.cpf)
      .then(setRec)
      .catch(e => setRecErro(e.message))
      .finally(() => setRecLoading(false))
    buscarStatusFeedbacks()
      .then(map => setStatusPag(map[String(d.cpf)] ?? null))
      .catch(() => {})
  }, [d?.cpf])

  if (!result || !d) return null

  const score = d.score_recuperabilidade
  const scoreColor = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#94a3b8'
  const circumference = 2 * Math.PI * 38
  const dash = (score / 100) * circumference

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-lg hover:bg-slate-100"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <Logo />
        <span className="font-bold text-slate-800 text-sm">Mizan</span>
        <span className="text-slate-200 text-sm">/</span>
        <button onClick={() => navigate('/dashboard')} className="text-slate-400 hover:text-slate-600 text-sm transition-colors">Dashboard</button>
        <span className="text-slate-200 text-sm">/</span>
        <span className="text-slate-700 text-sm font-medium truncate max-w-xs">{d.nome}</span>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-start justify-between mb-7">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{d.nome}</h1>
            <p className="text-slate-400 font-mono text-sm mt-1">{d.cpf}</p>
            <p className="text-slate-500 text-sm mt-1 capitalize">{d.produto} · {d.uf} · Rank #{d.rank}</p>
            <div className="mt-3">
              {statusPag === null && (
                <span className="inline-flex items-center gap-1.5 text-slate-400 text-sm font-medium bg-slate-100 border border-slate-200 px-3 py-1 rounded-full">
                  <Clock className="h-3.5 w-3.5" /> Pendente
                </span>
              )}
              {statusPag?.pagou === true && (
                <span className="inline-flex items-center gap-1.5 text-emerald-700 text-sm font-semibold bg-emerald-50 border border-emerald-300 px-3 py-1 rounded-full">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Pago
                  {statusPag.data_pagamento && (
                    <span className="font-normal text-emerald-500 text-xs">
                      · {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento + 'T12:00:00'))}
                    </span>
                  )}
                  {statusPag.valor_recuperado > 0 && (
                    <span className="font-normal text-emerald-500 text-xs">
                      · {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(statusPag.valor_recuperado)}
                    </span>
                  )}
                </span>
              )}
              {statusPag?.pagou === false && (
                <span className="inline-flex items-center gap-1.5 text-red-600 text-sm font-semibold bg-red-50 border border-red-300 px-3 py-1 rounded-full">
                  <XCircle className="h-3.5 w-3.5" /> Não pago
                  {statusPag.data_pagamento && (
                    <span className="font-normal text-red-400 text-xs">
                      · atualizado em {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento + 'T12:00:00'))}
                    </span>
                  )}
                </span>
              )}
            </div>
          </div>
          <PriorityBadge score={score} large />
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 flex flex-col gap-5">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-6 flex flex-col items-center">
              <p className="section-label mb-5 text-center">Score de Recuperabilidade</p>

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
            </div>

            <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-5">
              <p className="section-label mb-3">Perfil IA</p>
              <div
                className="text-center py-3 rounded-xl text-sm font-semibold"
                style={{ backgroundColor: `${scoreColor}15`, color: scoreColor }}
              >
                {d.perfil_cluster}
              </div>
              <p className="text-xs text-slate-400 mt-3 text-center leading-relaxed">
                Cluster #{d.cluster_id ?? '—'} identificado por machine learning
              </p>
            </div>
          </div>

          <div className="col-span-2 flex flex-col gap-4">
            <Section title="Dados Cadastrais">
              <DataRow label="Nome completo" value={d.nome} />
              <DataRow label="CPF" value={d.cpf} />
              <DataRow label="Produto" value={d.produto} />
              <DataRow label="Status" value={d.status} />
              <DataRow label="UF" value={d.uf} />
            </Section>

            <Section title="Dados Financeiros">
              <DataRow label="Valor da Dívida (face)" value={fmtBRL(d.valor_divida)} />
              <DataRow
                label="Valor Esperado de Recuperação"
                value={<span className="text-emerald-600 font-bold">{fmtBRL(d.valor_esperado_recuperacao)}</span>}
              />
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

            <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] p-5">
              <p className="section-label mb-4">Faixas de Recuperabilidade</p>
              <div className="space-y-2">
                {[
                  { label: 'Alta (≥ 70)', min: 70, max: 100, color: '#10b981' },
                  { label: 'Média (40–69)', min: 40, max: 69, color: '#f59e0b' },
                  { label: 'Baixa (< 40)', min: 0, max: 39, color: '#94a3b8' },
                ].map(({ label, min, max, color }) => {
                  const active = score >= min && score <= max
                  return (
                    <div key={label} className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${active ? 'bg-slate-50 ring-1 ring-slate-200' : ''}`}>
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

            <ApproachRecommendation devedor={d} rec={rec} loading={recLoading} erro={recErro} />

            {d.desconto_sugerido_pct != null && (
              <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100">
                  <p className="section-label">Oferta Sugerida</p>
                </div>
                <div className="p-5 space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3 text-center">
                      <p className="text-xs text-slate-400 mb-1">Desconto</p>
                      <p className="text-xl font-bold text-slate-800">{d.desconto_sugerido_pct}%</p>
                    </div>
                    <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-3 text-center">
                      <p className="text-xs text-emerald-600 mb-1">Valor Proposta</p>
                      <p className="text-lg font-bold text-emerald-700">{fmtBRL(d.valor_proposta)}</p>
                    </div>
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3 text-center">
                      <p className="text-xs text-slate-400 mb-1">Até</p>
                      <p className="text-xl font-bold text-slate-800">{d.parcelas_max}x</p>
                    </div>
                  </div>
                  <p className="text-sm text-slate-600 bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 leading-relaxed">
                    {d.estrategia_oferta}
                  </p>
                  {d.desconto_sugerido_pct > 0 && (
                    <p className="text-xs text-slate-400">
                      Economia de {fmtBRL((d.valor_divida ?? 0) - (d.valor_proposta ?? 0))} em relação ao valor original.
                    </p>
                  )}
                </div>
              </div>
            )}

            {d.cpf && <HistoricoContatos cpf={d.cpf} rec={rec} />}
          </div>
        </div>
      </main>
    </div>
  )
}
