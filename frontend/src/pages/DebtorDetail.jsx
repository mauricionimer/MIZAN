import ThemeToggle from '../components/ThemeToggle'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Phone, Tag, Zap, MessageSquare, Brain, Plus, ClipboardList, CheckCircle2, XCircle, Clock, Wallet, AlertTriangle } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import { buscarPaginaRanking } from '../api'
import PriorityBadge from '../components/PriorityBadge'
import { buscarRecomendacao, registrarContato, listarContatos, buscarStatusFeedbacks, buscarExplicacaoScore, buscarPropostas, traduzirErroRede } from '../api'
import { LogoMark } from '../components/Logo'
import DicaAjuda from '../components/DicaAjuda'

const fmtBRL = (v) => v != null ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v) : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

const CARD = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  boxShadow: '0 8px 32px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30)',
}
const DIVIDER = { borderColor: 'var(--line)' }
const INP = { background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }

function Logo() {
  return <LogoMark className="h-5 w-5 shrink-0" />
}

function DataRow({ label, value, ajuda }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b last:border-0" style={DIVIDER}>
      <span className="text-sm" style={{ color: 'var(--ink-2)' }}>{label}{ajuda && <DicaAjuda id={ajuda} />}</span>
      <span className="text-sm font-semibold text-ink">{value ?? '—'}</span>
    </div>
  )
}

const VARIAVEL_LABEL = {
  valor_divida: 'Valor da dívida', renda_estimada: 'Renda estimada', dias_em_atraso: 'Dias em atraso',
  score_bureau: 'Score de bureau', tentativas_contato: 'Tentativas de contato', promessa_quebrada: 'Promessa quebrada',
  mes_analise: 'Mês da análise', produto: 'Produto', status: 'Status', uf: 'Estado (UF)',
}
function labelVariavel(v) {
  return VARIAVEL_LABEL[v] || v.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}
function fmtValorExplicacao(v) {
  if (v == null) return 'não informado'
  if (typeof v === 'boolean') return v ? 'sim' : 'não'
  if (typeof v === 'number') return Number.isInteger(v) ? fmtNum(v) : v.toFixed(1)
  return String(v)
}

function Propostas({ dados, loading, erro, despesas, setDespesas, onRecalcular }) {
  if (loading) return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Montando propostas...</p>
  if (erro)    return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Propostas indisponíveis: {erro}</p>
  if (!dados || !Array.isArray(dados.propostas)) return null

  const margem = dados.margem
  const teto   = dados.parcela_maxima
  const recomendadaLabel = dados.recomendada?.rotulo
  const alternativaLabel = dados.alternativa_a_vista?.rotulo

  return (
    <div>
      {/* Margem livre primeiro: é ela que decide quais propostas sobram. */}
      <div className="mb-4 rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
        <div className="flex items-start gap-2.5">
          <Wallet className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--c-royal)' }} />
          <div className="flex-1">
            <p className="section-label mb-1">Margem livre mensal<DicaAjuda id="margem-livre" /></p>
            {margem?.valor != null ? (
              <p className="text-sm" style={{ color: 'var(--ink)' }}>
                {fmtBRL(margem.valor)} por mês
                {teto != null && <span style={{ color: 'var(--ink-3)' }}> · parcela máxima {fmtBRL(teto)}<DicaAjuda id="parcela-maxima" /></span>}
              </p>
            ) : (
              <p className="text-sm" style={{ color: 'var(--ink-2)' }}>{margem?.motivo || 'Não calculada.'}</p>
            )}
          </div>
        </div>

        {/* O operador costuma descobrir a despesa na própria ligação. */}
        <div className="mt-3 flex items-center gap-2">
          <input
            type="number" min="0" step="50" value={despesas}
            onChange={e => setDespesas(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') onRecalcular() }}
            placeholder="Despesas mensais informadas"
            className="flex-1 rounded-lg px-3 py-2 text-sm"
            style={{ background: 'var(--raise-3)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          />
          <button onClick={onRecalcular} className="btn-secondary text-sm px-3 py-2">Recalcular</button>
        </div>
      </div>

      {dados.aviso && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl p-3"
          style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)' }}>
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
          <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>{dados.aviso}</p>
        </div>
      )}

      <div className="space-y-2.5">
        {dados.propostas.map((p) => {
          const recomendada = p.rotulo === recomendadaLabel
          const alternativa = p.rotulo === alternativaLabel && !recomendada
          const naoCabe     = p.cabe_no_bolso === false
          return (
            <div key={p.rotulo} className="rounded-xl p-3.5"
              style={{
                background: recomendada ? 'rgb(var(--c-success) / 0.07)' : 'var(--raise-2)',
                border: recomendada ? '1px solid rgb(var(--c-success) / 0.28)' : '1px solid var(--line)',
                opacity: naoCabe ? 0.62 : 1,
              }}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>{p.rotulo}</span>
                    {recomendada && (
                      <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                        style={{ background: 'rgb(var(--c-success) / 0.16)', color: 'var(--success)' }}>Sugerida</span>
                    )}
                    {alternativa && (
                      <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                        style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>Alternativa</span>
                    )}
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--ink-2)' }}>
                    {p.n_parcelas > 1 ? `${p.n_parcelas}x de ${fmtBRL(p.parcela)}` : `À vista: ${fmtBRL(p.valor_cobrado)}`}
                    {p.desconto_pct > 0 && ` · ${Number(p.desconto_pct).toFixed(0)}% de desconto`}
                  </p>
                  <p className="text-[11px] mt-1 leading-relaxed" style={{ color: naoCabe ? 'var(--danger)' : 'var(--ink-3)' }}>
                    {p.observacao}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Valor esperado</p>
                  <p className="text-sm font-semibold tabular-nums" style={{ color: 'var(--ink)' }}>
                    {fmtBRL(p.valor_esperado)}
                  </p>
                  {p.pop != null && (
                    <>
                      <p className="text-[11px] tabular-nums" style={{ color: 'var(--ink-3)' }}>
                        {fmtPct(p.pop)} de chance<DicaAjuda id="chance-de-pagamento-por-oferta" />
                      </p>
                      {/* 65% do modelo e 65% de vinte renegociações reais não
                          valem o mesmo — a origem precisa estar à vista. */}
                      <p className="text-[10px]" style={{ color: 'var(--ink-3)', opacity: 0.8 }}>
                        {p.origem_pop === 'bandit'
                          ? (p.pop_observacoes === 1 ? '1 caso real' : `${p.pop_observacoes} casos reais`)
                          : 'estimativa do modelo'}
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ExplicacaoScore({ explicacao, loading, erro }) {
  if (loading) {
    return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Calculando explicação do score...</p>
  }
  if (erro) {
    return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Explicação indisponível: {erro}</p>
  }
  if (!explicacao) return null

  const relevantes = explicacao.contribuicoes.filter(c => Math.abs(c.impacto_pontos) >= 0.1).slice(0, 6)
  const maiorImpacto = Math.max(1, ...relevantes.map(c => Math.abs(c.impacto_pontos)))

  const rc = explicacao.reason_codes

  return (
    <div>
      {/* Reason codes: a leitura em linguagem de negócio, antes do detalhe
          numérico. É o que vai para o operador, para o devedor e, se
          precisar, para o regulador — sem expor peso de modelo. */}
      {rc && (rc.desfavoraveis?.length > 0 || rc.favoraveis?.length > 0 || rc.motivo) && (
        <div className="mb-5 rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
          <p className="section-label mb-3">Principais motivos<DicaAjuda id="por-que-esse-score" /></p>
          {rc.motivo ? (
            <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-3)' }}>{rc.motivo}</p>
          ) : (
            <div className="space-y-2.5">
              {rc.desfavoraveis?.map(m => (
                <div key={`d-${m.variavel}`} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: 'var(--danger)' }} />
                  <span className="text-sm" style={{ color: 'var(--ink)' }}>{m.motivo}</span>
                </div>
              ))}
              {rc.favoraveis?.map(m => (
                <div key={`f-${m.variavel}`} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: 'var(--success)' }} />
                  <span className="text-sm" style={{ color: 'var(--ink)' }}>{m.motivo}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <p className="text-xs mb-4 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
        Comparação com o devedor médio da base de treino — o que empurrou este score para cima ou para baixo.
      </p>
      {relevantes.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Nenhuma variável individual teve impacto relevante — este é um caso próximo da média da base.</p>
      ) : (
        <div className="space-y-3">
          {relevantes.map(c => {
            const positivo = c.impacto_pontos > 0
            const largura = Math.min(Math.abs(c.impacto_pontos) / maiorImpacto * 100, 100)
            return (
              <div key={c.variavel}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-ink">{labelVariavel(c.variavel)}</span>
                  <span style={{ color: positivo ? 'var(--success)' : 'var(--danger)' }} className="font-bold">
                    {positivo ? '+' : ''}{c.impacto_pontos.toFixed(1)} pts
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden flex" style={{ background: 'var(--raise-3)' }}>
                  <div className="h-full rounded-full" style={{
                    width: `${largura}%`,
                    backgroundColor: positivo ? 'var(--success)' : 'var(--danger)',
                  }} />
                </div>
                <p className="text-[11px] mt-1" style={{ color: 'var(--ink-3)' }}>
                  Valor real: <strong>{fmtValorExplicacao(c.valor_real)}</strong> · Referência da base: {fmtValorExplicacao(c.valor_referencia)}
                  {' — '}{positivo ? 'melhora' : 'piora'} o score em relação à média.
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Section({ title, children, ajuda }) {
  return (
    <div className="rounded-2xl p-5" style={CARD}>
      <p className="section-label mb-3">{title}{ajuda && <DicaAjuda id={ajuda} />}</p>
      {children}
    </div>
  )
}

const CANAL_ICONS = { whatsapp: '💬', telefone: '📞', carta: '✉️' }
const RESULTADO_CFG = {
  contactado:     { label: 'Contactado',       color: 'text-blue-400',    bg: 'rgb(var(--c-royal) / 0.10)',   border: 'rgb(var(--c-royal) / 0.20)'  },
  sem_resposta:   { label: 'Sem resposta',      color: 'text-ink-2',  bg: 'var(--raise-3)', border: 'var(--line)' },
  prometeu_pagar: { label: 'Prometeu pagar',    color: 'text-amber-400',   bg: 'rgb(var(--c-warning) / 0.10)',  border: 'rgb(var(--c-warning) / 0.20)'  },
  pagou:          { label: 'Disse que pagou',             color: 'text-emerald-400', bg: 'rgb(var(--c-success) / 0.10)',  border: 'rgb(var(--c-success) / 0.20)'  },
  nao_quis:       { label: 'Não quis negociar', color: 'text-red-400',     bg: 'rgb(var(--c-danger) / 0.10)',   border: 'rgb(var(--c-danger) / 0.18)'   },
}

function HistoricoContatos({ cpf, rec, propostas }) {
  const [contatos, setContatos]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [formAberto, setFormAberto] = useState(false)
  const [salvando, setSalvando]     = useState(false)
  const [erro, setErro]             = useState(null)
  const [form, setForm] = useState({
    canal: 'whatsapp', resultado: 'contactado', oferta: '',
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
    // A oferta que o operador apresentou é o que o bandit precisa aprender.
    // acao_bandit_id continua indo como retaguarda, para o caso de o contato
    // ter saído da recomendação do próprio bandit, sem escolha na tela.
    if (form.oferta) payload.oferta = form.oferta
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
        setForm({ canal: 'whatsapp', resultado: 'contactado', oferta: '', data_contato: new Date().toISOString().slice(0, 10), observacao: '', valor_recuperado: '', desconto_oferecido_pct: '' })
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

  const selectStyle = { background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)', borderRadius: '0.75rem', padding: '0.5rem 0.75rem', fontSize: '0.875rem', width: '100%', outline: 'none' }
  const inputStyle  = { ...selectStyle }
  const taStyle     = { ...selectStyle, resize: 'none' }

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className="px-5 py-4 border-b flex items-center justify-between" style={DIVIDER}>
        <div className="flex items-center gap-2">
          <ClipboardList className="h-3.5 w-3.5" style={{ color: 'var(--ink-3)' }} />
          <p className="section-label">Histórico de Contatos{contatos.length > 0 && ` (${contatos.length})`}<DicaAjuda id="registrar-contato" /></p>
        </div>
        <button onClick={() => setFormAberto(o => !o)}
          className="flex items-center gap-1.5 text-xs font-semibold text-blue-400 px-3 py-1.5 rounded-lg transition-colors"
          style={{ background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}
          onMouseOver={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.18)'}
          onMouseOut={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.10)'}>
          <Plus className="h-3.5 w-3.5" /> Registrar contato
        </button>
      </div>

      {formAberto && (
        <div className="px-5 py-4 border-b space-y-3" style={{ ...DIVIDER, background: 'var(--raise-1)' }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Canal</label>
              <select value={form.canal} onChange={e => set('canal', e.target.value)} style={selectStyle}>
                <option value="whatsapp">WhatsApp</option>
                <option value="telefone">Ligação Telefônica</option>
                <option value="carta">Carta / E-mail</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Data</label>
              <input type="date" value={form.data_contato} onChange={e => set('data_contato', e.target.value)} style={inputStyle} />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Resultado</label>
            <select value={form.resultado} onChange={e => set('resultado', e.target.value)} style={selectStyle}>
              <option value="contactado">Contactado</option>
              <option value="sem_resposta">Sem resposta</option>
              <option value="prometeu_pagar">Prometeu pagar</option>
              <option value="pagou">Disse que pagou (a confirmar)</option>
              <option value="nao_quis">Não quis negociar</option>
            </select>
          </div>
          {/* Sem isto o sistema não sabe QUAL oferta foi negociada, e a chance
              de pagamento por tipo de oferta nunca sai da estimativa do modelo.
              A lista vem das propostas que esta mesma tela calculou. */}
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
              Oferta apresentada
            </label>
            <select value={form.oferta} onChange={e => set('oferta', e.target.value)} style={selectStyle}>
              <option value="">Nenhuma / outra</option>
              {(propostas?.propostas ?? []).filter(p => p.oferta).map(p => (
                <option key={p.oferta} value={p.oferta}>{p.rotulo}</option>
              ))}
            </select>
            <p className="text-[11px] mt-1.5" style={{ color: 'var(--ink-3)' }}>
              Registrar a oferta é o que ensina o sistema qual funciona nesta carteira.
            </p>
          </div>
          {form.resultado === 'pagou' && (
            <p className="text-[11px] leading-relaxed" style={{ color: 'var(--ink-3)' }}>
              Isto registra o que o devedor disse; não confirma o pagamento. A confirmação vem da baixa em Pagamentos
              (administrador) ou da integração com o banco, e é ela que ensina o sistema, creditada à oferta registrada aqui.
            </p>
          )}
          {(form.resultado === 'pagou' || form.resultado === 'prometeu_pagar') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Valor Recuperado (R$)</label>
                <input type="number" min="0" step="0.01" value={form.valor_recuperado} onChange={e => set('valor_recuperado', e.target.value)} placeholder="0,00" style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                  Desconto Oferecido (%){rec?.oferta_label && <span className="text-blue-400 ml-1 font-normal">· IA: {rec.oferta_label}</span>}
                </label>
                <input type="number" min="0" max="100" step="1" value={form.desconto_oferecido_pct} onChange={e => set('desconto_oferecido_pct', e.target.value)} placeholder="Ex: 30" style={inputStyle} />
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Observação (opcional)</label>
            <textarea value={form.observacao} onChange={e => set('observacao', e.target.value)} rows={2} placeholder="Detalhes do contato..." style={taStyle} />
          </div>
          {erro && <p className="text-xs text-red-400 rounded-xl px-3 py-2" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>{erro}</p>}
          <div className="flex gap-2">
            <button onClick={salvar} disabled={salvando} className="btn-primary py-1.5 disabled:opacity-50">
              {salvando ? 'Salvando...' : 'Salvar'}
            </button>
            <button onClick={() => { setFormAberto(false); setErro(null) }}
              className="px-4 py-1.5 rounded-xl text-sm font-medium transition-colors"
              style={{ color: 'var(--ink-2)' }}
              onMouseOver={e => e.currentTarget.style.background = 'var(--raise-2)'}
              onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div>
        {loading && (
          <div className="flex items-center justify-center py-8 text-xs gap-2" style={{ color: 'var(--ink-3)' }}>
            <div className="h-3.5 w-3.5 border-2 border-t-blue-400 rounded-full animate-spin" style={{ borderColor: 'var(--line)', borderTopColor: 'var(--royal)' }} />
            Carregando...
          </div>
        )}
        {!loading && contatos.length === 0 && (
          <p className="text-xs text-center py-8" style={{ color: 'var(--ink-3)' }}>Nenhum contato registrado ainda.</p>
        )}
        {contatos.map(c => {
          const res = RESULTADO_CFG[c.resultado] ?? { label: c.resultado, color: 'text-ink-2', bg: 'var(--raise-3)', border: 'var(--line)' }
          return (
            <div key={c.id} className="px-5 py-3.5 flex items-start gap-3 border-b" style={DIVIDER}>
              <span className="text-base shrink-0 mt-0.5">{CANAL_ICONS[c.canal] ?? '📋'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${res.color}`}
                    style={{ background: res.bg, border: `1px solid ${res.border}` }}>
                    {res.label}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--ink-3)' }}>{fmtData(c.data_contato || c.created_at)}</span>
                  {c.usuario_nome && <span className="text-xs" style={{ color: 'var(--ink-4)' }}>por {c.usuario_nome}</span>}
                </div>
                {c.observacao && <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--ink-2)' }}>{c.observacao}</p>}
                {c.valor_recuperado > 0 && <p className="text-xs text-emerald-400 font-semibold mt-0.5">{fmtBRL(c.valor_recuperado)} recuperados</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const MODO_CONFIG = {
  exploração_inicial: { label: 'Explorando', color: 'text-amber-400',   bg: 'rgb(var(--c-warning) / 0.10)',  border: 'rgb(var(--c-warning) / 0.20)'  },
  aprendendo:         { label: 'Aprendendo', color: 'text-blue-400',    bg: 'rgb(var(--c-royal) / 0.10)',  border: 'rgb(var(--c-royal) / 0.20)'  },
  calibrado:          { label: 'Calibrado',  color: 'text-emerald-400', bg: 'rgb(var(--c-success) / 0.10)', border: 'rgb(var(--c-success) / 0.20)'  },
}

function ApproachRecommendation({ devedor, rec, loading, erro }) {
  // Antes havia aqui uma "Urgência" Alta/Média/Baixa tirada só do score (≥70,
  // ≥40), um terceiro critério que podia contradizer a Prioridade da fila
  // (achado D8). Quem decide a ordem é a fila; aqui fica só o número.
  const score = devedor.score_recuperabilidade
  const modoCfg = rec ? (MODO_CONFIG[rec.modo] ?? MODO_CONFIG.aprendendo) : null

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className="px-5 py-4 border-b flex items-center justify-between" style={DIVIDER}>
        <p className="section-label">Recomendação de Abordagem<DicaAjuda id="recomendacao-de-abordagem" /></p>
        {modoCfg && (
          <span className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ${modoCfg.color}`}
            style={{ background: modoCfg.bg, border: `1px solid ${modoCfg.border}` }}>
            <Brain className="h-3 w-3" /> IA · {modoCfg.label}
          </span>
        )}
      </div>
      <div className="p-5 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-sm gap-2" style={{ color: 'var(--ink-3)' }}>
            <div className="h-4 w-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--line)', borderTopColor: 'var(--royal)' }} />
            Consultando IA...
          </div>
        )}
        {erro && <p className="text-sm text-red-400 text-center py-4">{erro}</p>}
        {rec && !loading && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: 'var(--raise-1)', border: '1px solid var(--line)' }}>
                <Zap className="h-4 w-4" style={{ color: 'var(--ink-3)' }} />
                <p className="text-xs font-medium" style={{ color: 'var(--ink-2)' }}>Chance de pagar<DicaAjuda id="urgencia-do-devedor" /></p>
                <span className="text-sm font-bold tabular-nums text-ink">{score == null ? '—' : `${Math.round(score)}%`}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
                <Phone className="h-4 w-4 text-blue-400" />
                <p className="text-xs font-medium" style={{ color: 'var(--ink-2)' }}>Canal</p>
                <span className="text-sm font-bold text-blue-400 text-center leading-tight">{rec.canal_label}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 rounded-xl p-3"
                style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
                <Tag className="h-4 w-4 text-emerald-400" />
                <p className="text-xs font-medium" style={{ color: 'var(--ink-2)' }}>Oferta</p>
                <span className="text-sm font-bold text-emerald-400 text-center leading-tight">{rec.oferta_label}</span>
              </div>
            </div>
            <div className="flex gap-3 p-4 rounded-xl" style={{ background: 'var(--raise-1)', border: '1px solid var(--line)' }}>
              <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--ink-3)' }} />
              <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>{rec.justificativa}</p>
            </div>
            {rec.total_interacoes > 0 && (
              <p className="text-xs text-right" style={{ color: 'var(--ink-3)' }}>
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
  const { result, setVista } = useAnalysis()
  // A tela inicial é uma só: dizer "Dashboard" é escolher a vista dela.
  const voltarAoDashboard = () => { setVista('dashboard'); navigate('/') }

  // O devedor vinha do ranking inteiro em memória. Sem ele, a posição é
  // buscada no servidor: a fila está ordenada por rank, então a posição N é a
  // linha N — offset e limite resolvem, sem varrer nada.
  const carteiraId = result?.resumo?.carteira_id ?? result?.carteira_id ?? null
  const emMemoria = result?.ranking_completo?.find(x => x.rank === Number(rank)) ?? null
  const [buscado, setBuscado]   = useState(null)
  const [procurando, setProcurando] = useState(false)
  const d = emMemoria ?? buscado

  useEffect(() => {
    if (emMemoria || !carteiraId) return
    const posicao = Number(rank)
    if (!posicao || posicao < 1) return
    let cancelado = false
    setProcurando(true)
    buscarPaginaRanking(carteiraId, { offset: posicao - 1, limit: 1 })
      .then(p => { if (!cancelado) setBuscado(p.itens?.[0] ?? null) })
      .catch(() => { if (!cancelado) setBuscado(null) })
      .finally(() => { if (!cancelado) setProcurando(false) })
    return () => { cancelado = true }
  }, [carteiraId, rank, emMemoria])

  const [rec, setRec]               = useState(null)
  const [recLoading, setRecLoading] = useState(true)
  const [recErro, setRecErro]       = useState(null)
  const [statusPag, setStatusPag]   = useState(null)
  const [explicacao, setExplicacao]           = useState(null)
  const [explicacaoLoading, setExplicacaoLoading] = useState(true)
  const [explicacaoErro, setExplicacaoErro]       = useState(null)
  const [propostas, setPropostas]             = useState(null)
  const [propostasLoading, setPropostasLoading] = useState(true)
  const [propostasErro, setPropostasErro]       = useState(null)
  const [despesas, setDespesas]                 = useState('')

  useEffect(() => {
    if (!result) { navigate('/'); return }
    // Só desiste depois da busca: sair antes mandaria o usuário para a tela
    // inicial no meio de um clique que ia funcionar.
    if (!d && !procurando && !carteiraId) navigate('/')
    else if (!d && !procurando && buscado === null && carteiraId && !emMemoria) {
      // buscou e não achou: a posição não existe nesta carteira
      navigate('/')
    }
  }, [result, d, navigate])

  useEffect(() => {
    if (!d?.cpf) return
    setRecLoading(true)
    buscarRecomendacao(d.cpf).then(setRec).catch(e => setRecErro(e.message)).finally(() => setRecLoading(false))
    buscarStatusFeedbacks(carteiraId).then(map => setStatusPag(map[String(d.cpf)] ?? null)).catch(() => {})
    setExplicacaoLoading(true)
    buscarExplicacaoScore(d.cpf).then(setExplicacao).catch(e => setExplicacaoErro(e.message)).finally(() => setExplicacaoLoading(false))
    setPropostasLoading(true)
    setPropostasErro(null)
    buscarPropostas(d.cpf).then(setPropostas).catch(e => setPropostasErro(e.message)).finally(() => setPropostasLoading(false))
  }, [d?.cpf, carteiraId])

  // O operador informa a despesa que o devedor declarou na ligação e a
  // margem é refeita na hora — sem isso o teste de capacidade não roda.
  function recalcularPropostas() {
    if (!d?.cpf) return
    setPropostasLoading(true)
    setPropostasErro(null)
    buscarPropostas(d.cpf, despesas === '' ? null : despesas)
      .then(setPropostas)
      .catch(e => setPropostasErro(e.message))
      .finally(() => setPropostasLoading(false))
  }

  if (!result || !d) return null

  const score = d.score_recuperabilidade
  const scoreColor = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--ink-2)'
  const circumference = 2 * Math.PI * 38
  const dash = (score / 100) * circumference

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center gap-3">
        <button onClick={voltarAoDashboard} className="p-1 rounded-lg transition-colors hover:bg-raise-2" style={{ color: 'var(--ink-3)' }}>
          <ArrowLeft className="h-4 w-4" />
        </button>
        <Logo />
        <span className="font-bold text-ink text-sm">Mizan</span>
        <span className="text-ink-4 text-sm">/</span>
        <button onClick={voltarAoDashboard} className="text-sm transition-colors hover:text-ink" style={{ color: 'var(--ink-3)' }}>Dashboard</button>
        <span className="text-ink-4 text-sm">/</span>
        <span className="text-sm font-medium text-ink truncate max-w-xs">{d.nome}</span>
        <ThemeToggle className="ml-auto" />
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-start justify-between mb-7">
          <div>
            <h1 className="text-2xl font-bold text-ink tracking-tight">{d.nome}</h1>
            <p className="tabular-nums text-sm mt-1" style={{ color: 'var(--ink-3)' }}>{d.cpf}</p>
            <p className="text-sm mt-1 capitalize" style={{ color: 'var(--ink-2)' }}>{d.produto} · {d.uf} · Rank #{d.rank}</p>
            <div className="mt-3">
              {statusPag === null && (
                <span className="inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1 rounded-full"
                  style={{ background: 'var(--raise-3)', color: 'var(--ink-2)', border: '1px solid var(--line)' }}>
                  <Clock className="h-3.5 w-3.5" /> Pendente
                </span>
              )}
              {statusPag?.pagou === true && (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-400 px-3 py-1 rounded-full"
                  style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.25)' }}>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Pago
                  {statusPag.data_pagamento && <span className="font-normal text-emerald-500/70 text-xs">· {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento.substring(0, 10) + 'T12:00:00'))}</span>}
                  {statusPag.valor_recuperado > 0 && <span className="font-normal text-emerald-500/70 text-xs">· {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(statusPag.valor_recuperado)}</span>}
                </span>
              )}
              {statusPag?.pagou === false && (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-red-400 px-3 py-1 rounded-full"
                  style={{ background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
                  <XCircle className="h-3.5 w-3.5" /> Não pago
                  {statusPag.data_pagamento && <span className="font-normal text-red-400/60 text-xs">· atualizado em {new Intl.DateTimeFormat('pt-BR').format(new Date(statusPag.data_pagamento.substring(0, 10) + 'T12:00:00'))}</span>}
                </span>
              )}
            </div>
          </div>
          <PriorityBadge rank={d.rank} total={result?.resumo?.total_devedores ?? result?.ranking_completo?.length ?? 0} large />
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 flex flex-col gap-5">
            {/* Score ring */}
            <div className="rounded-2xl p-6 flex flex-col items-center" style={CARD}>
              <p className="section-label mb-5 text-center">Score de Recuperabilidade<DicaAjuda id="score-recuperabilidade" /></p>
              <div className="relative w-36 h-36">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(128,141,166,0.25)" strokeWidth="8" />
                  <circle cx="50" cy="50" r="38" fill="none" stroke={scoreColor} strokeWidth="8" strokeLinecap="round"
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    style={{ transition: 'stroke-dasharray 0.8s ease', filter: `drop-shadow(0 0 8px ${scoreColor}60)` }} />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-ink">{score}</span>
                  <span className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>/ 100</span>
                </div>
              </div>
              <div className="w-full mt-5">
                <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--raise-3)' }}>
                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${score}%`, backgroundColor: scoreColor }} />
                </div>
                <div className="flex justify-between text-xs mt-1.5" style={{ color: 'var(--ink-3)' }}>
                  <span>0</span><span>100</span>
                </div>
              </div>
            </div>

            {/* Perfil IA */}
            <div className="rounded-2xl p-5" style={CARD}>
              <p className="section-label mb-3">Perfil IA<DicaAjuda id="perfil-cluster" /></p>
              <div className="text-center py-3 rounded-xl text-sm font-semibold"
                style={{ backgroundColor: `${scoreColor}18`, color: scoreColor }}>
                {d.perfil_cluster}
              </div>
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

            <Section title="Propostas de renegociação" ajuda="propostas-de-renegociacao">
              <Propostas
                dados={propostas} loading={propostasLoading} erro={propostasErro}
                despesas={despesas} setDespesas={setDespesas}
                onRecalcular={recalcularPropostas}
              />
            </Section>

            <Section title="Por que esse score?" ajuda="por-que-esse-score">
              <ExplicacaoScore explicacao={explicacao} loading={explicacaoLoading} erro={explicacaoErro} />
            </Section>

            <Section title="Dados Financeiros">
              {d.dados_incompletos && (
                <div className="mb-3 flex items-start gap-2 rounded-xl p-3 text-xs"
                  style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)', color: 'var(--ink-2)' }}>
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: 'var(--warning)' }} />
                  <span>Dados incompletos: {d.aviso_dados || 'faltam informações deste devedor'}. O score é uma estimativa com esse dado faltando.<DicaAjuda id="dados-incompletos" /></span>
                </div>
              )}
              <DataRow label="Valor da Dívida (face)" value={fmtBRL(d.valor_divida)} />
              <DataRow ajuda="valor-esperado" label="Valor Esperado de Recuperação" value={<span className="text-emerald-400 font-bold">{fmtBRL(d.valor_esperado_recuperacao)}</span>} />
              <DataRow label="Renda Estimada" value={d.renda_estimada > 0 ? fmtBRL(d.renda_estimada) : 'Não informada'} />
              <DataRow label="Dias em Atraso" value={fmtNum(d.dias_em_atraso)} />
              {d.comprometimento_renda != null && <DataRow ajuda="comprometimento-de-renda" label="Comprometimento de Renda" value={fmtPct(d.comprometimento_renda)} />}
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
              <Section title="Precificação Sugerida" ajuda="oferta-na-planilha">
                {d.desconto_sugerido_pct != null && <DataRow label="Desconto Sugerido" value={`${d.desconto_sugerido_pct}%`} />}
                {d.valor_proposta != null && <DataRow label="Valor da Proposta" value={fmtBRL(d.valor_proposta)} />}
                {d.parcelas_max != null && <DataRow label="Parcelas Máx." value={String(d.parcelas_max)} />}
                {d.estrategia_oferta && <DataRow label="Estratégia" value={d.estrategia_oferta} />}
              </Section>
            )}

            <ApproachRecommendation devedor={d} rec={rec} loading={recLoading} erro={recErro} />
            <HistoricoContatos cpf={d.cpf} rec={rec} propostas={propostas} />
          </div>
        </div>
      </main>
    </div>
  )
}
