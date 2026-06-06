import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Phone, Tag, Zap, MessageSquare, Brain, Plus, ClipboardList, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import PriorityBadge from '../components/PriorityBadge'
import { buscarRecomendacao, registrarContato, listarContatos, buscarStatusFeedbacks, traduzirErroRede } from '../api'

const fmtBRL = (v) => v != null ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v) : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

const CARD = {
  background: '#0d1628',
  border: '1px solid rgba(255,255,255,0.07)',
  boxShadow: '0 8px 32px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30)',
}
const DIVIDER = { borderColor: 'rgba(255,255,255,0.06)' }
const INP = { background: '#0a1220', border: '1px solid rgba(255,255,255,0.10)', color: 'white' }

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 2px 8px rgba(29,106,255,0.30)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

function DataRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b last:border-0" style={DIVIDER}>
      <span className="text-sm" style={{ color: '#8fa3c8' }}>{label}</span>
      <span className="text-sm font-semibold text-white">{value ?? '—'}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="rounded-2xl p-5" style={CARD}>
      <p className="section-label mb-3">{title}</p>
      {children}
    </div>
  )
}

const CANAL_ICONS = { whatsapp: '💬', telefone: '📞', carta: '✉️' }
const RESULTADO_CFG = {
  contactado:     { label: 'Contactado',       color: 'text-blue-400',    bg: 'rgba(29,106,255,0.10)',   border: 'rgba(29,106,255,0.20)'  },
  sem_resposta:   { label: 'Sem resposta',      color: 'text-[#8fa3c8]',  bg: 'rgba(255,255,255,0.06)', border: 'rgba(255,255,255,0.12)' },
  prometeu_pagar: { label: 'Prometeu pagar',    color: 'text-amber-400',   bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.20)'  },
  pagou:          { label: 'Pagou',             color: 'text-emerald-400', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.20)'  },
  nao_quis:       { label: 'Não quis negociar', color: 'text-red-400',     bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.18)'   },
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
    listarContatos(cpf).then(setContatos).catch(() => {}).finally(() => setLoading(false))
  }, [cpf])

  async function salvar() {
    setSalvando(true); setErro(null)
    const payload = { cpf, canal: form.canal, resultado: form.resultado, data_contato: form.data_contato, observacao: form.observacao }
    if (rec?.acao_id != null) payload.acao_bandit_id = rec.acao_id
    if (form.valor_recuperado) payload.valor_recuperado = parseFloat(form.valor_recuperado)
    if (form.desconto_oferecido_pct) payload.desconto_oferecido_pct = parseFloat(form.desconto_oferecido_pct)

    const _aguardar = async (segundos) => {
      for (let s = segundos; s > 0; s--) {
        setErro(`Servidor acordando... aguarde ${s}s`)
        await new Promise(r => setTimeout(r, 1000))
      }
      setErro(null)
    }

    const _tentar = async (tentativa) => {
      try {
        const res = await registrarContato(payload)
        setContatos(prev => [res.contato, ...prev])
        setFormAberto(false)
        setForm({ canal: 'whatsapp', resultado: 'contactado', data_contato: new Date().toISOString().slice(0, 10), observacao: '', valor_recuperado: '', desconto_oferecido_pct: '' })
      } catch (e) {
        const isRede = e?.message === 'Failed to fetch' || e?.message?.includes('Failed to fetch')
        const esperas = [35, 20]
        if (isRede && tentativa <= esperas.length) { await _aguardar(esperas[tentativa - 1]); return _tentar(tentativa + 1) }
        setErro(traduzirErroRede(e))
      }
    }

    try { await _tentar(1) } finally { setSalvando(false) }
  }

  const fmtData = (iso) => iso
    ? new Intl.DateTimeFormat('pt-BR').format(new Date(iso.includes('T') ? iso : iso + 'T12:00:00'))
    : '—'

  const selectStyle = { background: '#0a1220', border: '1px solid rgba(255,255,255,0.10)', color: 'white', borderRadius: '0.75rem', padding: '0.5rem 0.75rem', fontSize: '0.875rem', width: '100%', outline: 'none' }
  const inputStyle  = { ...selectStyle }
  const taStyle     = { ...selectStyle, resize: 'none' }

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className="px-5 py-4 border-b flex items-center justify-between" style={DIVIDER}>
        <div className="flex items-center gap-2">
          <ClipboardList className="h-3.5 w-3.5" style={{ color: '#5a7499' }} />
          <p className="section-label">Histórico de Contatos{contatos.length > 0 && ` (${contatos.length})`}</p>
        </div>
        <button onClick={() => setFormAberto(o => !o)}
          className="flex items-center gap-1.5 text-xs font-semibold text-blue-400 px-3 py-1.5 rounded-lg transition-colors"
          style={{ background: 'rgba(29,106,255,0.10)', border: '1px solid rgba(29,106,255,0.20)' }}
          onMouseOver={e => e.currentTarget.style.background = 'rgba(29,106,255,0.18)'}
          onMouseOut={e => e.currentTarget.style.background = 'rgba(29,106,255,0.10)'}>
          <Plus className="h-3.5 w-3.5" /> Registrar contato
        </button>
      </div>

      {formAberto && (
        <div className="px-5 py-4 border-b space-y-3" style={{ ...DIVIDER, background: 'rgba(255,255,255,0.02)' }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Canal</label>
              <select value={form.canal} onChange={e => set('canal', e.target.value)} style={selectStyle}>
                <option value="whatsapp">WhatsApp</option>
                <option value="telefone">Ligação Telefônica</option>
                <option value="carta">Carta / E-mail</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Data</label>
              <input type="date" value={form.data_contato} onChange={e => set('data_contato', e.target.value)} style={inputStyle} />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Resultado</label>
            <select value={form.resultado} onChange={e => set('resultado', e.target.value)} style={selectStyle}>
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
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Valor Recuperado (R$)</label>
                <input type="number" min="0" step="0.01" value={form.valor_recuperado} onChange={e => set('valor_recuperado', e.target.value)} placeholder="0,00" style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>
                  Desconto Oferecido (%){rec?.oferta_label && <span className="text-blue-400 ml-1 font-normal">· IA: {rec.oferta_label}</span>}
                </label>
                <input type="number" min="0" max="100" step="1" value={form.desconto_oferecido_pct} onChange={e => set('desconto_oferecido_pct', e.target.value)} placeholder="Ex: 30" style={inputStyle} />
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Observação (opcional)</label>
            <textarea value={form.observacao} onChange={e => set('observacao', e.target.value)} rows={2} placeholder="Detalhes do contato..." style={taStyle} />
          </div>
          {erro && <p className="text-xs text-red-400 rounded-xl px-3 py-2" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)' }}>{erro}</p>}
          <div className="flex gap-2">
            <button onClick={salvar} disabled={salvando} className="btn-primary py-1.5 disabled:opacity-50">
              {salvando ? 'Salvando...' : 'Salvar'}
            </button>
            <button onClick={() => { setFormAberto(false); setErro(null) }}
              className="px-4 py-1.5 rounded-xl text-sm font-medium transition-colors"
              style={{ color: '#8fa3c8' }}
              onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div>
        {loading && (
          <div className="flex items-center justify-center py-8 text-xs gap-2" style={{ color: '#5a7499' }}>
            <div className="h-3.5 w-3.5 border-2 border-t-blue-400 rounded-full animate-spin" style={{ borderColor: 'rgba(255,255,255,0.10)', borderTopColor: '#1d6aff' }} />
            Carregando...
          </div>
        )}
        {!loading && contatos.length === 0 && (
          <p className="text-xs text-center py-8" style={{ color: '#5a7499' }}>Nenhum contato registrado ainda.</p>
        )}
        {contatos.map(c => {
          const res = RESULTADO_CFG[c.resultado] ?? { label: c.resultado, color: 'text-[#8fa3c8]', bg: 'rgba(255,255,255,0.06)', border: 'rgba(255,255,255,0.12)' }
          return (
            <div key={c.id} className="px-5 py-3.5 flex items-start gap-3 border-b" style={DIVIDER}>
              <span className="text-base shrink-0 mt-0.5">{CANAL_ICONS[c.canal] ?? '📋'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${res.color}`}
                    style={{ background: res.bg, border: `1px solid ${res.border}` }}>
                    {res.label}
                  </span>
                  <span className="text-xs" style={{ color: '#5a7499' }}>{fmtData(c.data_contato || c.created_at)}</span>
                  {c.usuario_nome && <span className="text-xs" style={{ color: '#3d5270' }}>por {c.usuario_nome}</span>}
                </div>
                {c.observacao && <p className="text-xs mt-1 leading-relaxed" style={{ color: '#8fa3c8' }}>{c.observacao}</p>}
                {c.valor_recuperado > 0 && <p className="text-xs text-emerald-400 font-semibold mt-0.5">{fmtBRL(c.valor_recuperado)} recuperados</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const URGENCIA_CONFIG = {
  Alta:  { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.20)'  },
  Média: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.20)' },
  Baixa: { color: '#10b981', bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.20)' },
}

const MODO_CONFIG = {
  exploração_inicial: { label: 'Explorando', color: 'text-amber-400',   bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.20)'  },
  aprendendo:         { label: 'Aprendendo', color: 'text-blue-400',    bg: 'rgba(29,106,255,0.10)',  border: 'rgba(29,106,255,0.20)'  },
  calibrado:          { label: 'Calibrado',  color: 'text-emerald-400', bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.20)'  },
}

function ApproachRecommendation({ devedor, rec, loading, erro }) {
  const score = devedor.score_recuperabilidade ?? 0
  const urgencia = score >= 70 ? 'Alta' : score >= 40 ? 'Média' : 'Baixa'
  const urgCfg = URGENCIA_CONFIG[urgencia]
  const modoCfg = rec ? (MODO_CONFIG[rec.modo] ?? MODO_CONFIG.aprendendo) : null

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className="px-5 py-4 border-b flex items-center justify-between" style={DIVIDER}>
        <p className="section-label">Recomendação de Abordagem</p>
        {modoCfg && (
          <span className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ${modoCfg.color}`}
            style={{ background: modoCfg.bg, border: `1px solid ${modoCfg.border}` }}>
            <Brain className="h-3 w-3" /> IA · {modoCfg.label}
          </span>
        )}
      </div>
      <div className="p-5 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-sm gap-2" style={{ color: '#5a7499' }}>
            <div className="h-4 w-4 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(255,255,255,0.10)', borderTopColor: '#1d6aff' }} />
            Consultando IA...
          </div>
        )}
        {erro && <p className="text-sm text-red-400 text-center py-4">{erro}</p>}
        {rec && !loading && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: urgCfg.bg, border: `1px solid ${urgCfg.border}` }}>
                <Zap className="h-4 w-4" style={{ color: urgCfg.color }} />
                <p className="text-xs font-medium" style={{ color: '#8fa3c8' }}>Urgência</p>
                <span className="text-sm font-bold" style={{ color: urgCfg.color }}>{urgencia}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: 'rgba(29,106,255,0.10)', border: '1px solid rgba(29,106,255,0.20)' }}>
                <Phone className="h-4 w-4 text-blue-400" />
                <p className="text-xs font-medium" style={{ color: '#8fa3c8' }}>Canal</p>
                <span className="text-sm font-bold text-blue-400 text-center leading-tight">{rec.canal_label}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: 'rgba(16,185,129,0.10)', border: '1px solid rgba(16,185,129,0.20)' }}>
                <Tag className="h-4 w-4 text-emerald-400" />
                <p className="text-xs font-medium" style={{ color: '#8fa3c8' }}>Oferta</p>
                <span className="text-sm font-bold text-emerald-400 text-center leading-tight">{rec.oferta_label}</span>
              </div>
            </div>
            <div className="flex gap-3 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" style={{ color: '#5a7499' }} />
              <p className="text-sm leading-relaxed" style={{ color: '#8fa3c8' }}>{rec.justificativa}</p>
            </div>
            {rec.total_interacoes > 0 && (
              <p className="text-xs text-right" style={{ color: '#5a7499' }}>
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
    buscarRecomendacao(d.cpf).then(setRec).catch(e => setRecErro(e.message)).finally(() => setRecLoading(false))
    buscarStatusFeedbacks().then(map => setStatusPag(map[String(d.cpf)] ?? null)).catch(() => {})
  }, [d?.cpf])

  if (!result || !d) return null

  const score = d.score_recuperabilidade
  const scoreColor = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#8fa3c8'
  const circumference = 2 * Math.PI * 38
  const dash = (score / 100) * circumference

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center gap-3">
        <button onClick={() => navigate('/dashboard')} className="p-1 rounded-lg transition-colors hover:bg-white/5" style={{ color: '#5a7499' }}>
          <ArrowLeft className="h-4 w-4" />
        </button>
        <Logo />
        <span className="font-bold text-white text-sm">Mizan</span>
        <span className="text-white/20 text-sm">/</span>
        <button onClick={() => navigate('/dashboard')} className="text-sm transition-colors hover:text-white" style={{ color: '#5a7499' }}>Dashboard</button>
        <span className="text-white/20 text-sm">/</span>
        <span className="text-sm font-medium text-white truncate max-w-xs">{d.nome}</span>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-start justify-between mb-7">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">{d.nome}</h1>
            <p className="font-mono text-sm mt-1" style={{ color: '#5a7499' }}>{d.cpf}</p>
            <p className="text-sm mt-1 capitalize" style={{ color: '#8fa3c8' }}>{d.produto} · {d.uf} · Rank #{d.rank}</p>
            <div className="mt-3">
              {statusPag === null && (
                <span className="inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1 rounded-full"
                  style={{ background: 'rgba(255,255,255,0.06)', color: '#8fa3c8', border: '1px solid rgba(255,255,255,0.10)' }}>
                  <Clock className="h-3.5 w-3.5" /> Pendente
                </span>
              )}
              {statusPag?.pagou === true && (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-400 px-3 py-1 rounded-full"
                  style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)' }}>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Pago
                  {statusPag.data_pagamento && <span className="font-normal text-emerald-500/70 text-xs">· {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento.substring(0, 10) + 'T12:00:00'))}</span>}
                  {statusPag.valor_recuperado > 0 && <span className="font-normal text-emerald-500/70 text-xs">· {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(statusPag.valor_recuperado)}</span>}
                </span>
              )}
              {statusPag?.pagou === false && (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-red-400 px-3 py-1 rounded-full"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
                  <XCircle className="h-3.5 w-3.5" /> Não pago
                  {statusPag.data_pagamento && <span className="font-normal text-red-400/60 text-xs">· atualizado em {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento.substring(0, 10) + 'T12:00:00'))}</span>}
                </span>
              )}
            </div>
          </div>
          <PriorityBadge score={score} large />
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 flex flex-col gap-5">
            {/* Score ring */}
            <div className="rounded-2xl p-6 flex flex-col items-center" style={CARD}>
              <p className="section-label mb-5 text-center">Score de Recuperabilidade</p>
              <div className="relative w-36 h-36">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="8" />
                  <circle cx="50" cy="50" r="38" fill="none" stroke={scoreColor} strokeWidth="8" strokeLinecap="round"
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    style={{ transition: 'stroke-dasharray 0.8s ease', filter: `drop-shadow(0 0 8px ${scoreColor}60)` }} />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-white">{score}</span>
                  <span className="text-xs mt-0.5" style={{ color: '#5a7499' }}>/ 100</span>
                </div>
              </div>
              <div className="w-full mt-5">
                <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${score}%`, backgroundColor: scoreColor }} />
                </div>
                <div className="flex justify-between text-xs mt-1.5" style={{ color: '#5a7499' }}>
                  <span>0</span><span>100</span>
                </div>
              </div>
            </div>

            {/* Perfil IA */}
            <div className="rounded-2xl p-5" style={CARD}>
              <p className="section-label mb-3">Perfil IA</p>
              <div className="text-center py-3 rounded-xl text-sm font-semibold"
                style={{ backgroundColor: `${scoreColor}18`, color: scoreColor }}>
                {d.perfil_cluster}
              </div>
              <p className="text-xs mt-3 text-center leading-relaxed" style={{ color: '#5a7499' }}>
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
              <DataRow label="Valor Esperado de Recuperação" value={<span className="text-emerald-400 font-bold">{fmtBRL(d.valor_esperado_recuperacao)}</span>} />
              <DataRow label="Renda Estimada" value={fmtBRL(d.renda_estimada)} />
              <DataRow label="Dias em Atraso" value={fmtNum(d.dias_em_atraso)} />
              {d.comprometimento_renda != null && <DataRow label="Comprometimento de Renda" value={fmtPct(d.comprometimento_renda)} />}
            </Section>

            {(d.tentativas_contato != null || d.promessa_quebrada != null) && (
              <Section title="Dados de Cobrança">
                {d.tentativas_contato != null && <DataRow label="Tentativas de Contato" value={fmtNum(d.tentativas_contato)} />}
                {d.promessa_quebrada != null && (
                  <DataRow label="Promessa Quebrada" value={
                    <span className={d.promessa_quebrada ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
                      {d.promessa_quebrada ? 'Sim' : 'Não'}
                    </span>
                  } />
                )}
              </Section>
            )}

            {(d.desconto_sugerido_pct != null || d.estrategia_oferta) && (
              <Section title="Precificação Sugerida">
                {d.desconto_sugerido_pct != null && <DataRow label="Desconto Sugerido" value={`${d.desconto_sugerido_pct}%`} />}
                {d.valor_proposta != null && <DataRow label="Valor da Proposta" value={fmtBRL(d.valor_proposta)} />}
                {d.parcelas_max != null && <DataRow label="Parcelas Máx." value={String(d.parcelas_max)} />}
                {d.estrategia_oferta && <DataRow label="Estratégia" value={d.estrategia_oferta} />}
              </Section>
            )}

            <ApproachRecommendation devedor={d} rec={rec} loading={recLoading} erro={recErro} />
            <HistoricoContatos cpf={d.cpf} rec={rec} />
          </div>
        </div>
      </main>
    </div>
  )
}
