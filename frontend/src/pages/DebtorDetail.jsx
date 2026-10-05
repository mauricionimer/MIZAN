import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Phone, Tag, Zap, MessageSquare, Brain, Plus, ClipboardList, CheckCircle2, XCircle, Clock, Wallet, AlertTriangle, ChevronDown, CalendarClock } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import { buscarPaginaRanking, buscarDistribuicao, atribuirResponsavel, listarAgenda, mudarAgenda, listarRoteiros } from '../api'
import { CANAIS, OFERTA_LABEL, CANAL_DA_RECOMENDACAO, dadosParaRoteiro, preencher, linkWhatsApp } from '../utils/roteiros'
import { NIVEL_CFG, TIPO_LABEL, quando, hojeISO, somarDias, avisarAgendaMudou } from '../utils/agenda'
import { useAuth } from '../context/AuthContext'
import PriorityBadge from '../components/PriorityBadge'
import { buscarRecomendacao, registrarContato, listarContatos, listarOfertasFeitas, buscarStatusFeedbacks, buscarExplicacaoScore, buscarPropostas, traduzirErroRede } from '../api'
import { LogoMark } from '../components/Logo'
import DicaAjuda from '../components/DicaAjuda'
import AppShell from '../components/AppShell'
import FazerOferta from '../components/FazerOferta'
import ErroCarga from '../components/ErroCarga'
import AvisoDesfazer from '../components/AvisoDesfazer'
import RegistroRapido from '../components/RegistroRapido'
import TituloRecolhivel from '../components/TituloRecolhivel'
import ProximoDevedor from '../components/ProximoDevedor'
import { resumoConta } from '../utils/ofertas'

// F1 — quem cuida deste devedor. Admin troca na hora; os demais só veem.
function Responsavel({ carteiraId, devedor, podeTrocar }) {
  const [resumo, setResumo] = useState(null)
  const [atual, setAtual]   = useState(devedor.responsavel_id || '')
  const [nome, setNome]     = useState(devedor.responsavel_nome || '')
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg]       = useState('')

  useEffect(() => {
    setAtual(devedor.responsavel_id || ''); setNome(devedor.responsavel_nome || ''); setMsg('')
  }, [devedor.cpf, devedor.responsavel_id, devedor.responsavel_nome])
  useEffect(() => {
    if (!carteiraId) return
    buscarDistribuicao(carteiraId).then(setResumo).catch(() => setResumo(null))
  }, [carteiraId])

  if (!carteiraId || !resumo?.ativo) return null
  if (!podeTrocar) {
    return nome ? (
      <p className="mt-2 text-xs" style={{ color: 'var(--ink-2)' }}>
        Responsável: <span className="font-medium text-ink">{nome}</span><DicaAjuda id="divisao-da-fila" />
      </p>
    ) : null
  }

  async function trocar(id) {
    const anterior = atual
    setAtual(id); setSalvando(true); setMsg('')
    try {
      const r = await atribuirResponsavel(carteiraId, [devedor.cpf], id || null)
      setNome(r.responsavel_nome || '')
      setMsg('Salvo')
    } catch (e) {
      setAtual(anterior); setMsg(e.message)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs" style={{ color: 'var(--ink-2)' }}>
      <label htmlFor="resp-devedor">Responsável<DicaAjuda id="divisao-da-fila" /></label>
      <select id="resp-devedor" value={atual} disabled={salvando} onChange={e => trocar(e.target.value)}
        className="rounded-lg border border-line bg-surface-2 px-2 py-1 text-xs text-ink focus:border-blue-500/50 focus:outline-none [color-scheme:dark]">
        <option value="">Sem responsável</option>
        {(resumo.operadores ?? []).map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
        {atual && !(resumo.operadores ?? []).some(o => o.id === atual) && <option value={atual}>{nome || 'Operador inativo'}</option>}
      </select>
      {msg && <span style={{ color: msg === 'Salvo' ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
    </div>
  )
}

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

function Propostas({ dados, loading, erro, despesas, setDespesas, onRecalcular, onSimular }) {
  if (loading) return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Montando propostas...</p>
  if (erro)    return <ErroCarga erro={erro} onTentar={onRecalcular} compacto />
  if (!dados || !Array.isArray(dados.propostas)) return null

  const margem = dados.margem
  const teto   = dados.parcela_maxima
  const recomendadaLabel = dados.recomendada?.rotulo
  const alternativaLabel = dados.alternativa_a_vista?.rotulo
  // Duas propostas bastam para a conversa: a sugerida e a alternativa à vista
  // (sem elas, as duas primeiras da lista).
  const duas = []
  for (const p of [dados.propostas.find(x => x.rotulo === recomendadaLabel), dados.propostas.find(x => x.rotulo === alternativaLabel), ...dados.propostas]) {
    if (p && duas.length < 2 && !duas.includes(p)) duas.push(p)
  }

  return (
    <div>
      {/* Margem livre: fechada; é ela que decide quais propostas cabem no bolso. */}
      <details className="group mb-4 rounded-xl" style={{ background: 'var(--raise-2)' }}>
        <summary className="flex min-h-[44px] cursor-pointer list-none items-center gap-2 px-4 py-2.5 [&::-webkit-details-marker]:hidden">
          <Wallet className="h-4 w-4 shrink-0" style={{ color: 'var(--c-royal)' }} />
          <span className="section-label">Margem livre mensal</span>
          <span className="truncate text-xs" style={{ color: 'var(--ink-3)' }}>{margem?.valor != null ? `${fmtBRL(margem.valor)} por mês` : 'não calculada'}</span>
          <ChevronDown className="ml-auto h-4 w-4 shrink-0 transition-transform group-open:rotate-180" style={{ color: 'var(--ink-3)' }} aria-hidden="true" />
        </summary>
        <div className="px-4 pb-4">
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
            placeholder="Gastos mensais do devedor (R$)"
            className="flex-1 rounded-lg px-3 py-2 text-sm"
            style={{ background: 'var(--raise-3)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          />
          <button onClick={onRecalcular} className="btn-secondary text-sm px-3 py-2">Recalcular</button>
        </div>
        </div>
      </details>

      {dados.aviso && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl p-3"
          style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)' }}>
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
          <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>{dados.aviso}</p>
        </div>
      )}

      <div className="space-y-2.5">
        {duas.map((p) => {
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
                      <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                        style={{ background: 'rgb(var(--c-success) / 0.16)', color: 'var(--success)' }}>Sugerida</span>
                    )}
                    {alternativa && (
                      <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                        style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>Alternativa</span>
                    )}
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--ink-2)' }}>
                    {p.n_parcelas > 1
                      ? `${p.entrada > 0 ? `${fmtBRL(p.entrada)} de entrada + ` : ''}${p.n_parcelas}x de ${fmtBRL(p.parcela)}`
                      : `À vista: ${fmtBRL(p.valor_cobrado)}`}
                    {p.desconto_pct > 0 && ` · ${Number(p.desconto_pct).toFixed(0)}% de desconto`}
                    {p.juros_mensal_pct > 0 && ` · ${String(p.juros_mensal_pct).replace('.', ',')}% a.m.`}
                  </p>
                  <p className="text-xs mt-1 leading-relaxed" style={{ color: naoCabe ? 'var(--danger)' : 'var(--ink-3)' }}>
                    {p.observacao}
                  </p>
                  {onSimular && p.id && (
                    <button type="button" onClick={() => onSimular(p.id)}
                      className="min-h-[40px] md:min-h-[32px] mt-1 inline-flex items-center text-xs font-semibold text-blue-400 hover:text-blue-300">
                      Ajustar e oferecer →
                    </button>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Valor esperado</p>
                  <p className="text-sm font-semibold tabular-nums" style={{ color: 'var(--ink)' }}>
                    {fmtBRL(p.valor_esperado)}
                  </p>
                  {p.pop != null && (
                    <>
                      <p className="text-xs tabular-nums" style={{ color: 'var(--ink-3)' }}>
                        {fmtPct(p.pop)} de chance<DicaAjuda id="chance-de-pagamento-por-oferta" />
                      </p>
                      {/* 65% do modelo e 65% de vinte renegociações reais não
                          valem o mesmo — a origem precisa estar à vista. */}
                      <p className="text-xs" style={{ color: 'var(--ink-3)', opacity: 0.8 }}>
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

function ExplicacaoScore({ explicacao, loading, erro, onTentar }) {
  if (loading) {
    return <p className="text-sm" style={{ color: 'var(--ink-3)' }}>Calculando explicação do score...</p>
  }
  if (erro) {
    return <ErroCarga erro={erro} onTentar={onTentar} compacto />
  }
  if (!explicacao) return null

  const relevantes = (explicacao.contribuicoes ?? []).filter(c => Math.abs(c.impacto_pontos) >= 0.1).slice(0, 6)
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
                <p className="text-xs mt-1" style={{ color: 'var(--ink-3)' }}>
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

// Informação de consulta (não de atendimento): fica recolhida até ser pedida.
function SecaoRecolhivel({ title, children, ajuda, aberta = false }) {
  return (
    <details className="group rounded-2xl" style={CARD} open={aberta}>
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-2 px-5 py-3 [&::-webkit-details-marker]:hidden">
        <span className="section-label">
          {title}
          {/* O "?" abre a ajuda sem abrir/fechar a seção. */}
          {ajuda && <span onClick={e => e.preventDefault()}><DicaAjuda id={ajuda} /></span>}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" style={{ color: 'var(--ink-3)' }} aria-hidden="true" />
      </summary>
      <div className="px-5 pb-5">{children}</div>
    </details>
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

// F4 — mensagem pronta: o roteiro do canal e da oferta recomendados,
// preenchido com os dados deste devedor e da proposta correspondente.
function MensagemSugerida({ devedor, rec, propostas, simulada }) {
  const { usuario, empresaConfig, isComando } = useAuth()
  const canalRec = CANAL_DA_RECOMENDACAO[rec?.canal] || 'whatsapp'
  // Com uma oferta montada em "Fazer oferta", a mensagem usa ela (família e valores).
  const ofertaRec = simulada?.familia || propostas?.recomendada?.oferta || rec?.oferta || ''
  const [canal, setCanal] = useState(canalRec)
  const [aberto, setAberto] = useState(false)
  const [lista, setLista] = useState(null)
  const [escolhido, setEscolhido] = useState('')
  const [copiado, setCopiado] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => { setCanal(canalRec) }, [canalRec])
  useEffect(() => {
    if (isComando) return
    setLista(null); setErro('')
    listarRoteiros({ canal })
      .then(r => setLista([...r.roteiros, ...r.padroes]))
      .catch(e => { setErro(e.message); setLista([]) })
  }, [canal, isComando])

  // Escolha automática: da oferta recomendada, preferindo os da empresa e os
  // pessoais aos modelos do Mizan; senão um "qualquer oferta"; senão o primeiro.
  useEffect(() => {
    if (!lista?.length) { setEscolhido(''); return }
    const ordem = (r) => (r.padrao ? 2 : r.dono_id ? 1 : 0)
    const porOrdem = [...lista].sort((a, b) => ordem(a) - ordem(b))
    const r = porOrdem.find(x => x.oferta === ofertaRec) || porOrdem.find(x => !x.oferta) || porOrdem[0]
    setEscolhido(r.id)
  }, [lista, ofertaRec])

  if (isComando) return null
  const roteiro = lista?.find(r => r.id === escolhido)
  const todas = propostas?.propostas ?? []
  const daSimulacao = simulada?.conta ? {
    valor_cobrado: simulada.conta.valor_negociado, parcela: simulada.conta.parcela,
    n_parcelas: simulada.condicoes?.n_parcelas, desconto_pct: simulada.condicoes?.desconto_pct, oferta: simulada.familia,
  } : null
  const proposta = daSimulacao || (roteiro?.oferta && todas.find(p => p.oferta === roteiro.oferta)) || propostas?.recomendada || todas[0] || null
  const { texto, faltando } = roteiro
    ? preencher(roteiro.texto, dadosParaRoteiro({ devedor, proposta, empresa: empresaConfig?.nome_exibicao, operador: usuario?.nome }))
    : { texto: '', faltando: [] }

  async function copiar() {
    try { await navigator.clipboard.writeText(texto); setCopiado(true); setTimeout(() => setCopiado(false), 1800) }
    catch { setErro('Não foi possível copiar: selecione o texto e copie.') }
  }

  const sel = { background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)', borderRadius: '0.6rem', padding: '0.35rem 0.6rem', fontSize: '0.8rem' }

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className={`px-5 py-3 flex flex-wrap items-center justify-between gap-2 ${aberto ? 'border-b' : ''}`} style={DIVIDER}>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <TituloRecolhivel aberto={aberto} onAlternar={() => setAberto(a => !a)}>
            <span className="section-label">Mensagem sugerida</span>
          </TituloRecolhivel>
          <DicaAjuda id="roteiros-de-abordagem" />
        </div>
        {aberto && <div className="flex flex-wrap gap-2">
          <select aria-label="Canal da mensagem" value={canal} onChange={e => setCanal(e.target.value)} style={sel}>
            {CANAIS.map(c => <option key={c.k} value={c.k}>{c.label}{c.k === canalRec ? ' (recomendado)' : ''}</option>)}
          </select>
          {lista?.length > 0 && (
            <select aria-label="Roteiro" value={escolhido} onChange={e => setEscolhido(e.target.value)} style={{ ...sel, maxWidth: '16rem' }}>
              {lista.map(r => (
                <option key={r.id} value={r.id}>
                  {r.titulo}{r.oferta ? ` · ${OFERTA_LABEL[r.oferta]}` : ''}{r.padrao ? ' (Mizan)' : r.dono_id ? ' (meu)' : ''}
                </option>
              ))}
            </select>
          )}
        </div>}
      </div>
      {aberto && <div className="px-5 py-4 space-y-3">
        {lista === null && <p className="text-xs" style={{ color: 'var(--ink-3)' }}>Carregando roteiros…</p>}
        {roteiro && (
          <>
            <div className="whitespace-pre-wrap rounded-xl px-4 py-3 text-sm leading-relaxed"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }}>
              {texto}
            </div>
            {daSimulacao && (
              <p className="text-xs" style={{ color: 'var(--ink-3)' }}>Valores da oferta montada em “Fazer oferta”.</p>
            )}
            {proposta && roteiro.oferta && proposta.oferta !== roteiro.oferta && (
              <p className="text-xs" style={{ color: 'var(--warning)' }}>
                {daSimulacao ? 'Este roteiro foi escrito para outro tipo de oferta: confira se o texto combina com a oferta montada.'
                  : 'Os valores vêm da proposta recomendada: esta oferta não está entre as propostas deste devedor.'}
              </p>
            )}
            {faltando.length > 0 && (
              <p className="text-xs" style={{ color: 'var(--warning)' }}>Complete antes de enviar: {faltando.join(', ').replace(/_/g, ' ')}.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button onClick={copiar}
                className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-blue-400"
                style={{ background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
                {copiado ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ClipboardList className="h-3.5 w-3.5" />} {copiado ? 'Copiado' : 'Copiar'}
              </button>
              {(canal === 'whatsapp' || canal === 'sms') && (
                <a href={linkWhatsApp(texto)} target="_blank" rel="noopener noreferrer"
                  className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-400"
                  style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
                  <MessageSquare className="h-3.5 w-3.5" /> Abrir no WhatsApp
                </a>
              )}
              {canal === 'email' && (
                <a href={`mailto:?body=${encodeURIComponent(texto)}`}
                  className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-2"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }}>
                  Abrir no e-mail
                </a>
              )}
            </div>
            {(canal === 'whatsapp' || canal === 'sms') && (
              <p className="text-xs" style={{ color: 'var(--ink-3)' }}>A base não tem o telefone do devedor: o WhatsApp abre com o texto pronto e você escolhe o contato.</p>
            )}
          </>
        )}
        <ErroCarga erro={erro} compacto />
      </div>}
    </div>
  )
}

// F2 — compromissos pendentes deste devedor (retornos e promessas).
function CompromissosDevedor({ cpf, versao }) {
  const [itens, setItens] = useState(null)
  const [erro, setErro] = useState(null)
  const [desfazer, setDesfazer] = useState(null)
  useEffect(() => {
    listarAgenda({ cpf, escopo: 'equipe', situacao: 'pendente' })
      .then(r => setItens(r.ativo ? r.itens : null))
      .catch(() => setItens(null))
  }, [cpf, versao])

  async function agir(item, acao) {
    setErro(null)
    try {
      const r = await mudarAgenda(item.id, acao)
      setItens(l => l.filter(i => i.id !== item.id))
      avisarAgendaMudou()
      const texto = acao === 'quebrar' ? 'Promessa marcada como não paga.'
        : item.tipo === 'promessa' ? 'Promessa cumprida. Registre o pagamento em Pagamentos.' : 'Retorno feito.'
      setDesfazer({
        id: `${item.id}-${Date.now()}`, texto, desfeito: 'Desfeito. O compromisso voltou para a lista.',
        desfazer: async () => {
          const v = await mudarAgenda(item.id, 'reabrir', { situacao_esperada: r.item.situacao })
          setItens(l => [...(l || []).filter(i => i.id !== item.id), { ...item, ...v.item }]
            .sort((a, b) => String(a.data).localeCompare(String(b.data))))
          avisarAgendaMudou()
        },
      })
    } catch (e) { setErro(e) }
  }

  // O aviso de desfazer fica montado mesmo quando a lista esvazia: é
  // justamente depois de resolver o último compromisso que ele mais importa.
  const aviso = <AvisoDesfazer aviso={desfazer} onFechar={() => setDesfazer(null)} />
  if (!itens || itens.length === 0) return aviso

  return (
    <div className="px-5 py-3 border-b space-y-2" style={DIVIDER}>
      {aviso}
      <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>
        Compromissos pendentes<DicaAjuda id="agenda-de-retorno" />
      </p>
      {itens.map(i => {
        const cfg = NIVEL_CFG[i.nivel] ?? NIVEL_CFG.safe
        return (
          <div key={i.id} className="flex flex-wrap items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: cfg.fundo, border: `1px solid ${cfg.borda}` }}>
            <span className="text-xs font-semibold" style={{ color: cfg.cor }}>{TIPO_LABEL[i.tipo]}</span>
            <span className="text-xs text-ink">{quando(i.data, i.hora)}</span>
            {i.valor > 0 && <span className="text-xs font-semibold tabular-nums text-ink">{fmtBRL(i.valor)}</span>}
            {i.operador_nome && <span className="text-xs" style={{ color: 'var(--ink-3)' }}>· {i.operador_nome}</span>}
            <span className="ml-auto flex gap-1">
              <button onClick={() => agir(i, 'cumprir')} title={i.tipo === 'promessa' ? "Marca a promessa como cumprida. O pagamento só entra nos resultados quando for registrado em Pagamentos." : undefined}
                className="min-h-[40px] md:min-h-[32px] rounded px-2 py-0.5 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/10">
                {i.tipo === 'promessa' ? 'Cumpriu' : 'Feito'}
              </button>
              {i.tipo === 'promessa' && (
                <button onClick={() => agir(i, 'quebrar')} className="min-h-[40px] md:min-h-[32px] rounded px-2 py-0.5 text-xs font-semibold text-red-400 hover:bg-red-500/10">Não pagou</button>
              )}
            </span>
          </div>
        )
      })}
      <ErroCarga erro={erro} compacto />
    </div>
  )
}

function HistoricoContatos({ cpf, rec, propostas, versao = 0, onRegistrado }) {
  const [contatos, setContatos]     = useState([])
  const [versaoAgenda, setVersaoAgenda] = useState(0)
  const [avisoAgenda, setAvisoAgenda]   = useState('')
  const [loading, setLoading]       = useState(true)
  const [formAberto, setFormAberto] = useState(false)
  const [aberto, setAberto] = useState(false)
  const [salvando, setSalvando]     = useState(false)
  const [erro, setErro]             = useState(null)
  const [form, setForm] = useState({
    canal: 'whatsapp', resultado: 'contactado', oferta: '',
    data_contato: new Date().toISOString().slice(0, 10), observacao: '',
    valor_recuperado: '', desconto_oferecido_pct: '',
    data_prometida: '', valor_prometido: '', agendar_retorno: false,
    data_retorno: somarDias(hojeISO(), 1), hora_retorno: '',
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  useEffect(() => {
    listarContatos(cpf).then(c => setContatos(Array.isArray(c) ? c : [])).catch(() => {}).finally(() => setLoading(false))
  }, [cpf, versao])

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
    // F2: a promessa (ou o retorno) vai junto e cai na Agenda.
    if (form.resultado === 'prometeu_pagar') {
      if (!form.data_prometida) { setErro('Informe a data prometida: é ela que entra na Agenda.'); setSalvando(false); return }
      payload.agenda = { tipo: 'promessa', data: form.data_prometida }
      if (form.valor_prometido) payload.agenda.valor = parseFloat(form.valor_prometido)
    } else if (form.agendar_retorno && form.resultado !== 'pagou') {
      if (!form.data_retorno) { setErro('Informe a data do retorno.'); setSalvando(false); return }
      payload.agenda = { tipo: 'retorno', data: form.data_retorno }
      if (form.hora_retorno) payload.agenda.hora = form.hora_retorno
    }

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
        setForm({ canal: 'whatsapp', resultado: 'contactado', oferta: '', data_contato: new Date().toISOString().slice(0, 10), observacao: '', valor_recuperado: '', desconto_oferecido_pct: '',
                  data_prometida: '', valor_prometido: '', agendar_retorno: false, data_retorno: somarDias(hojeISO(), 1), hora_retorno: '' })
        if (res.agenda) {
          setAvisoAgenda(`${res.agenda.tipo === 'promessa' ? 'Promessa' : 'Retorno'} na Agenda: ${quando(res.agenda.data, res.agenda.hora).toLowerCase()}.`)
          setVersaoAgenda(v => v + 1); avisarAgendaMudou()
        } else if (res.agenda_erro) {
          setAvisoAgenda(`Contato salvo, mas não entrou na Agenda: ${res.agenda_erro}`)
        } else setAvisoAgenda('')
        onRegistrado?.()
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
      <div className={`px-5 py-3 flex items-center justify-between gap-2 ${aberto ? 'border-b' : ''}`} style={DIVIDER}>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <TituloRecolhivel aberto={aberto} onAlternar={() => setAberto(a => !a)}>
            <ClipboardList className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--ink-3)' }} />
            <span className="section-label">Histórico de Contatos{contatos.length > 0 && ` (${contatos.length})`}</span>
          </TituloRecolhivel>
          <DicaAjuda id="registrar-contato" />
        </div>
        <button onClick={() => { setAberto(true); setFormAberto(o => !o) }}
          className="min-h-[40px] md:min-h-[32px] flex items-center gap-1.5 text-xs font-semibold text-blue-400 px-3 py-1.5 rounded-lg transition-colors"
          style={{ background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}
          onMouseOver={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.18)'}
          onMouseOut={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.10)'}>
          <Plus className="h-3.5 w-3.5" /> Registrar contato
        </button>
      </div>

      {aberto && formAberto && (
        <div className="px-5 py-4 border-b space-y-3" style={{ ...DIVIDER, background: 'var(--raise-1)' }}>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-3)' }}>
            Fez uma proposta de acordo? Use “Fazer oferta” e confirme por lá: a oferta fica completa no histórico e a Agenda é preenchida junto.
            Aqui é para os demais contatos (sem resposta, recado, conversa sem proposta).
          </p>
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
            <p className="text-xs mt-1.5" style={{ color: 'var(--ink-3)' }}>
              Registrar a oferta é o que ensina o sistema qual funciona nesta carteira.
            </p>
          </div>
          {form.resultado === 'pagou' && (
            <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-3)' }}>
              Isto registra o que o devedor disse; não confirma o pagamento. A confirmação vem da baixa em Pagamentos
              (administrador) ou da integração com o banco, e é ela que ensina o sistema, creditada à oferta registrada aqui.
            </p>
          )}
          {form.resultado === 'prometeu_pagar' && (
            <div className="grid grid-cols-2 gap-3 rounded-xl p-3" style={{ background: 'rgb(var(--c-warning) / 0.06)', border: '1px solid rgb(var(--c-warning) / 0.20)' }}>
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Data prometida *</label>
                <input type="date" required min={hojeISO()} value={form.data_prometida} onChange={e => set('data_prometida', e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Valor prometido (R$)</label>
                <input type="number" min="0" step="0.01" value={form.valor_prometido} onChange={e => set('valor_prometido', e.target.value)} placeholder="0,00" style={inputStyle} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                  Desconto oferecido (%){rec?.oferta_label && <span className="text-blue-400 ml-1 font-normal">· IA: {rec.oferta_label}</span>}
                </label>
                <input type="number" min="0" max="100" step="1" value={form.desconto_oferecido_pct} onChange={e => set('desconto_oferecido_pct', e.target.value)} placeholder="Ex: 30" style={inputStyle} />
              </div>
              <p className="col-span-2 text-xs" style={{ color: 'var(--ink-3)' }}>
                A promessa entra na Agenda e vira “paga” sozinha quando o pagamento for confirmado.
              </p>
            </div>
          )}
          {form.resultado !== 'prometeu_pagar' && form.resultado !== 'pagou' && (
            <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }}>
              <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer" style={{ color: 'var(--ink-2)' }}>
                <input type="checkbox" checked={form.agendar_retorno} onChange={e => set('agendar_retorno', e.target.checked)} className="h-3.5 w-3.5 accent-blue-500" />
                Agendar retorno
              </label>
              {form.agendar_retorno && (
                <div className="mt-2.5 grid grid-cols-2 gap-3">
                  <input type="date" aria-label="Data do retorno" min={hojeISO()} value={form.data_retorno} onChange={e => set('data_retorno', e.target.value)} style={inputStyle} />
                  <input type="time" aria-label="Hora do retorno" value={form.hora_retorno} onChange={e => set('hora_retorno', e.target.value)} style={inputStyle} />
                </div>
              )}
            </div>
          )}
          {form.resultado === 'pagou' && (
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
          <ErroCarga erro={erro} compacto />
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

      {avisoAgenda && (
        <p className="px-5 py-2.5 text-xs border-b" style={{ ...DIVIDER, color: avisoAgenda.startsWith('Contato salvo') ? 'var(--warning)' : 'var(--success)' }}>
          {avisoAgenda}
        </p>
      )}
      {aberto && <CompromissosDevedor cpf={cpf} versao={versaoAgenda + versao} />}

      {aberto && <div>
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
      </div>}
    </div>
  )
}

const MODO_CONFIG = {
  exploração_inicial: { label: 'Explorando', color: 'text-amber-400',   bg: 'rgb(var(--c-warning) / 0.10)',  border: 'rgb(var(--c-warning) / 0.20)'  },
  aprendendo:         { label: 'Aprendendo', color: 'text-blue-400',    bg: 'rgb(var(--c-royal) / 0.10)',  border: 'rgb(var(--c-royal) / 0.20)'  },
  calibrado:          { label: 'Calibrado',  color: 'text-emerald-400', bg: 'rgb(var(--c-success) / 0.10)', border: 'rgb(var(--c-success) / 0.20)'  },
}

function ApproachRecommendation({ devedor, rec, loading, erro, onTentar }) {
  const [aberto, setAberto] = useState(false)
  // Antes havia aqui uma "Urgência" Alta/Média/Baixa tirada só do score (≥70,
  // ≥40), um terceiro critério que podia contradizer a Prioridade da fila
  // (achado D8). Quem decide a ordem é a fila; aqui fica só o número.
  const score = devedor.score_recuperabilidade
  const modoCfg = rec ? (MODO_CONFIG[rec.modo] ?? MODO_CONFIG.aprendendo) : null

  return (
    <div className="rounded-2xl overflow-hidden" style={CARD}>
      <div className={`px-5 py-3 flex items-center justify-between gap-2 ${aberto ? 'border-b' : ''}`} style={DIVIDER}>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <TituloRecolhivel aberto={aberto} onAlternar={() => setAberto(a => !a)}
            resumo={rec?.canal_label && rec?.oferta_label ? `${rec.canal_label} · ${rec.oferta_label}` : null}>
            <span className="section-label">Recomendação de Abordagem</span>
          </TituloRecolhivel>
          <DicaAjuda id="recomendacao-de-abordagem" />
        </div>
        {aberto && modoCfg && (
          <span className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ${modoCfg.color}`}
            style={{ background: modoCfg.bg, border: `1px solid ${modoCfg.border}` }}>
            <Brain className="h-3 w-3" /> IA · {modoCfg.label}
          </span>
        )}
      </div>
      {aberto && <div className="p-5 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-sm gap-2" style={{ color: 'var(--ink-3)' }}>
            <div className="h-4 w-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--line)', borderTopColor: 'var(--royal)' }} />
            Consultando IA...
          </div>
        )}
        {erro && !loading && <ErroCarga erro={erro} onTentar={onTentar} compacto />}
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
      </div>}
    </div>
  )
}

// Veio da Agenda ("Ligar agora"): mostra o compromisso e, quando existe, a
// oferta combinada (já carregada em "Fazer oferta").
function ContextoAgenda({ item, oferta }) {
  const cfg = NIVEL_CFG[item.nivel] ?? NIVEL_CFG.safe
  const promessa = item.tipo === 'promessa'
  return (
    <section aria-label="Compromisso da Agenda" className="mb-5 rounded-xl p-4"
      style={{ background: cfg.fundo, border: `1px solid ${cfg.borda}` }}>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold" style={{ color: cfg.cor }}>
        <CalendarClock className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>Da Agenda · {TIPO_LABEL[item.tipo]} {quando(item.data, item.hora).toLowerCase()}</span>
        {promessa && item.valor > 0 && <span className="tabular-nums" style={{ color: 'var(--ink)' }}>{fmtBRL(item.valor)}</span>}
      </p>
      {item.observacao && <p className="mt-1.5 text-sm" style={{ color: 'var(--ink-2)' }}>{item.observacao}</p>}
      {oferta && (
        <p className="mt-1.5 text-sm" style={{ color: 'var(--ink-2)' }}>
          Oferta combinada: <strong className="font-semibold" style={{ color: 'var(--ink)' }}>{resumoConta(oferta, oferta.n_parcelas, oferta.desconto_pct)}</strong>.{' '}
          Já está em “Fazer oferta”.{' '}
          <button type="button" className="font-semibold underline underline-offset-2" style={{ color: 'var(--ink)' }}
            onClick={() => document.getElementById('fazer-oferta')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
            Ir para a oferta
          </button>
        </p>
      )}
    </section>
  )
}

// A ficha é de um devedor só: trocar o número da posição recomeça a tela
// (despesas, simulador e formulários não passam de um devedor para o outro).
export default function DebtorDetail() {
  const { rank } = useParams()
  return <FichaDoDevedor key={rank} />
}

function FichaDoDevedor() {
  const { rank } = useParams()
  const navigate = useNavigate()
  const deAgenda = useLocation().state?.deAgenda ?? null
  const { result, setVista } = useAnalysis()
  const { isAdmin, isComando } = useAuth()
  // O3: oferta registrada cria um contato; a lista de contatos recarrega.
  const [versaoContatos, setVersaoContatos] = useState(0)
  // A oferta montada no simulador alimenta a Mensagem sugerida; "Ajustar e
  // oferecer" numa proposta carrega ela no simulador.
  const [pedidoOferta, setPedidoOferta] = useState(null)
  const [ofertaSimulada, setOfertaSimulada] = useState(null)
  // Registrou um atendimento: oferece o próximo da fila (ProximoDevedor).
  const [registro, setRegistro] = useState(null)
  const pagos = useRef(null)                    // CPFs já pagos, para não oferecer como "próximo"
  const [ofertaCombinada, setOfertaCombinada] = useState(null)
  // A tela inicial é uma só: dizer "Dashboard" é escolher a vista dela.
  const voltarAoDashboard = () => { setVista('dashboard'); navigate('/') }

  // O devedor vinha do ranking inteiro em memória. Sem ele, a posição é
  // buscada no servidor: a fila está ordenada por rank, então a posição N é a
  // linha N — offset e limite resolvem, sem varrer nada.
  const carteiraId = result?.resumo?.carteira_id ?? result?.carteira_id ?? null
  const emMemoria = result?.ranking_completo?.find(x => x.rank === Number(rank)) ?? null
  const [buscado, setBuscado]   = useState(null)
  // Começa "procurando" quando vai buscar no servidor. Começar em false fazia
  // o efeito de "não achei, volta ao início" rodar antes da busca existir: todo
  // clique num devedor que não estava em memória voltava para a tela inicial.
  const [procurando, setProcurando] = useState(() => !emMemoria && !!carteiraId)
  const [buscou, setBuscou] = useState(false)
  // Falha de rede/servidor ao buscar o devedor. Antes a tela voltava sozinha
  // para o início, sem dizer nada — parecia que o detalhe tinha sumido.
  const [erroBusca, setErroBusca] = useState('')
  const [tentativa, setTentativa] = useState(0)
  const d = emMemoria ?? buscado

  useEffect(() => {
    if (emMemoria || !carteiraId) return
    const posicao = Number(rank)
    if (!posicao || posicao < 1) return
    let cancelado = false
    setProcurando(true); setErroBusca('')
    buscarPaginaRanking(carteiraId, { offset: posicao - 1, limit: 1 })
      .then(p => { if (!cancelado) setBuscado(p.itens?.[0] ?? null) })
      .catch(e => { if (!cancelado) { setBuscado(null); setErroBusca(e.message || 'Erro ao buscar o devedor.') } })
      .finally(() => { if (!cancelado) { setProcurando(false); setBuscou(true) } })
    return () => { cancelado = true }
  }, [carteiraId, rank, emMemoria, tentativa])

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
    else if (!d && buscou && !procurando && !erroBusca && buscado === null && carteiraId && !emMemoria) {
      // buscou e não achou: a posição não existe nesta carteira
      navigate('/')
    }
  }, [result, d, navigate, erroBusca, buscou, procurando])

  // Veio de um compromisso criado por "Fazer oferta": a oferta combinada
  // (ligada pelo contato) já entra no simulador, sem rolar a tela.
  useEffect(() => {
    if (!deAgenda?.contato_id || !d?.cpf) return
    let vivo = true
    listarOfertasFeitas(d.cpf).then(r => {
      const o = r?.ativo ? (r.itens ?? []).find(x => x.contato_id === deAgenda.contato_id) : null
      if (!vivo || !o) return
      setOfertaCombinada(o)
      setPedidoOferta({ n: Date.now(), silencioso: true, base_id: o.base_id,
        valores: { desconto_pct: o.desconto_pct, entrada_pct: o.entrada_pct, n_parcelas: o.n_parcelas, juros_mensal_pct: o.juros_mensal_pct } })
    }).catch(() => {})
    return () => { vivo = false }
  }, [deAgenda?.contato_id, d?.cpf])

  // "Tentar novamente" na recomendação ou na explicação refaz as consultas do devedor.
  const [recarga, setRecarga] = useState(0)
  useEffect(() => {
    if (!d?.cpf) return
    setRecLoading(true); setRecErro(null); setExplicacaoErro(null)
    buscarRecomendacao(d.cpf).then(setRec).catch(e => setRecErro(e.message)).finally(() => setRecLoading(false))
    buscarStatusFeedbacks(carteiraId).then(map => {
      setStatusPag(map[String(d.cpf)] ?? null)
      pagos.current = new Set(Object.entries(map).filter(([, v]) => v?.pagou === true).map(([k]) => String(k)))
    }).catch(() => {})
    setExplicacaoLoading(true)
    buscarExplicacaoScore(d.cpf).then(setExplicacao).catch(e => setExplicacaoErro(e.message)).finally(() => setExplicacaoLoading(false))
    setPropostasLoading(true)
    setPropostasErro(null)
    buscarPropostas(d.cpf).then(setPropostas).catch(e => setPropostasErro(e.message)).finally(() => setPropostasLoading(false))
  }, [d?.cpf, carteiraId, recarga])

  // O operador informa a despesa que o devedor declarou na ligação e a
  // margem é refeita na hora — sem isso o teste de capacidade não roda.
  // Despesas: uma fonte só (este estado), usada pelas Propostas e pelo simulador.
  // Mudou (em qualquer um dos dois campos), as Propostas se refazem sozinhas.
  const despesasUsadas = useRef('')
  useEffect(() => {
    if (!d?.cpf || despesas === despesasUsadas.current) return
    const t = setTimeout(() => { despesasUsadas.current = despesas; recalcularPropostas() }, 700)
    return () => clearTimeout(t)
  }, [despesas, d?.cpf])          // eslint-disable-line react-hooks/exhaustive-deps

  function recalcularPropostas() {
    if (!d?.cpf) return
    setPropostasLoading(true)
    setPropostasErro(null)
    buscarPropostas(d.cpf, despesas === '' ? null : despesas)
      .then(setPropostas)
      .catch(e => setPropostasErro(e.message))
      .finally(() => setPropostasLoading(false))
  }

  if (result && !d && erroBusca && !procurando) {
    return (
      <AppShell>
        <div className="w-full max-w-5xl mx-auto">
          <button onClick={voltarAoDashboard}
            className="mb-4 inline-flex min-h-[40px] items-center gap-1.5 rounded-lg px-2 py-1 -ml-2 text-sm text-ink-2 transition-colors hover:bg-raise-1 hover:text-ink">
            <ArrowLeft className="h-4 w-4" /> Voltar à fila
          </button>
          <ErroCarga erro={erroBusca} ocupado={procurando} onTentar={() => setTentativa(t => t + 1)} />
        </div>
      </AppShell>
    )
  }

  if (!result || !d) return null

  const score = d.score_recuperabilidade
  const scoreColor = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--ink-2)'
  const circumference = 2 * Math.PI * 38
  const dash = (score / 100) * circumference

  return (
    <AppShell titulo="Devedor">
      <div className="w-full max-w-5xl mx-auto">
        <button onClick={voltarAoDashboard}
          className="mb-4 inline-flex min-h-[40px] items-center gap-1.5 rounded-lg px-2 py-1 -ml-2 text-sm text-ink-2 transition-colors hover:bg-raise-1 hover:text-ink">
          <ArrowLeft className="h-4 w-4" /> Voltar à fila
        </button>
        {/* Cabeçalho: só quem é, a posição na fila e o responsável. O resto está nos cartões abaixo. */}
        <div className="mb-7">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="text-2xl font-bold text-ink tracking-tight">{d.nome}</h1>
            <span className="rounded-full px-2.5 py-0.5 text-sm font-semibold tabular-nums text-blue-300"
              style={{ background: 'rgb(var(--c-royal) / 0.12)' }}>Rank #{d.rank}</span>
          </div>
          <Responsavel carteiraId={carteiraId} devedor={d} podeTrocar={isAdmin || isComando} />
        </div>

        {deAgenda && <ContextoAgenda item={deAgenda} oferta={ofertaCombinada} />}

        {/* Resumo: o essencial para entender o caso antes de agir. */}
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['Dívida', fmtBRL(d.valor_divida)],
            ['Em atraso', `${fmtNum(d.dias_em_atraso)} dias`],
            ['Valor esperado', fmtBRL(d.valor_esperado_recuperacao)],
            ['Score', <span key="s" style={{ color: scoreColor }}>{score}<span className="text-xs font-normal" style={{ color: 'var(--ink-3)' }}> / 100</span></span>],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl px-4 py-3" style={CARD}>
              <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{k}</p>
              <p className="mt-0.5 text-lg font-bold tabular-nums" style={{ color: 'var(--ink)' }}>{v}</p>
            </div>
          ))}
        </div>
        {d.dados_incompletos && (
          <div className="mb-5 flex items-start gap-2 rounded-xl p-3 text-sm"
            style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.18)', color: 'var(--ink-2)' }}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--warning)' }} />
            <span>Dados incompletos: {d.aviso_dados || 'faltam informações deste devedor'}. O score é uma estimativa com esse dado faltando.<DicaAjuda id="dados-incompletos" /></span>
          </div>
        )}

        <div>
          {/* Atendimento: entender → decidir → oferecer → comunicar → registrar.
              A recomendação define o canal (simulador e mensagem); as propostas
              definem a oferta inicial do simulador; a oferta montada vira a
              mensagem; confirmar a oferta recarrega os contatos. */}
          <section className="flex flex-col gap-4" aria-labelledby="titulo-atendimento">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="titulo-atendimento" className="text-base font-bold" style={{ color: 'var(--ink)' }}>Atendimento</h2>
            </div>

            {!isComando && (
              <RegistroRapido cpf={d.cpf} canalPadrao={rec?.canal}
                onRegistrado={() => { setVersaoContatos(v => v + 1); setRegistro({ n: Date.now() }) }} />
            )}

            <ApproachRecommendation devedor={d} rec={rec} loading={recLoading} erro={recErro} onTentar={() => setRecarga(n => n + 1)} />

            <SecaoRecolhivel title="Propostas de renegociação" ajuda="propostas-de-renegociacao">
              <Propostas
                dados={propostas} loading={propostasLoading} erro={propostasErro}
                despesas={despesas} setDespesas={setDespesas}
                onRecalcular={recalcularPropostas}
                onSimular={id => setPedidoOferta({ id, n: Date.now() })}
              />
            </SecaoRecolhivel>

            <FazerOferta cpf={d.cpf} despesas={despesas} setDespesas={setDespesas} canalPadrao={rec?.canal} confirmavel={!isComando}
              sugeridaId={propostas?.recomendada?.id || propostas?.alternativa_a_vista?.id}
              pedido={pedidoOferta} onSimulado={setOfertaSimulada}
              onRegistrada={() => { setVersaoContatos(v => v + 1); setRegistro({ n: Date.now() }) }}
              onDesfeita={() => { setVersaoContatos(v => v + 1); setRegistro(null) }} />

            <MensagemSugerida devedor={d} rec={rec} propostas={propostas} simulada={ofertaSimulada} />
            <HistoricoContatos cpf={d.cpf} rec={rec} propostas={propostas} versao={versaoContatos}
              onRegistrado={() => setRegistro({ n: Date.now() })} />
            {/* Detalhes de consulta: fechados, sem repetir os cartões do topo. */}
            <details className="group rounded-2xl" style={CARD}>
              <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-2 px-5 py-3 [&::-webkit-details-marker]:hidden">
                <span className="section-label">Mais detalhes do devedor</span>
                <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" style={{ color: 'var(--ink-3)' }} aria-hidden="true" />
              </summary>
              <div className="flex flex-col gap-3 px-3 pb-3">
            <SecaoRecolhivel title="Por que esse score?" ajuda="por-que-esse-score">
              <ExplicacaoScore explicacao={explicacao} loading={explicacaoLoading} erro={explicacaoErro} onTentar={() => setRecarga(n => n + 1)} />
            </SecaoRecolhivel>

            <SecaoRecolhivel title="Dados financeiros" ajuda="variaveis-do-modelo">
              <DataRow label="Valor da Dívida (face)" value={fmtBRL(d.valor_divida)} />
              <DataRow ajuda="valor-esperado" label="Valor Esperado de Recuperação" value={<span className="text-emerald-400 font-bold">{fmtBRL(d.valor_esperado_recuperacao)}</span>} />
              <DataRow label="Renda Estimada" value={d.renda_estimada > 0 ? fmtBRL(d.renda_estimada) : 'Não informada'} />
              <DataRow label="Dias em Atraso" value={fmtNum(d.dias_em_atraso)} />
              {d.comprometimento_renda != null && <DataRow ajuda="comprometimento-de-renda" label="Comprometimento de Renda" value={fmtPct(d.comprometimento_renda)} />}
            </SecaoRecolhivel>

            {(d.tentativas_contato != null || d.promessa_quebrada != null) && (
              <SecaoRecolhivel title="Dados de cobrança">
                {d.tentativas_contato != null && <DataRow label="Tentativas de Contato" value={fmtNum(d.tentativas_contato)} />}
                {d.promessa_quebrada != null && (
                  <DataRow label="Promessa Quebrada" value={
                    <span className={d.promessa_quebrada ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
                      {d.promessa_quebrada ? 'Sim' : 'Não'}
                    </span>
                  } />
                )}
              </SecaoRecolhivel>
            )}

            {(d.desconto_sugerido_pct != null || d.estrategia_oferta) && (
              <SecaoRecolhivel title="Precificação da planilha" ajuda="oferta-na-planilha">
                {d.desconto_sugerido_pct != null && <DataRow label="Desconto Sugerido" value={`${d.desconto_sugerido_pct}%`} />}
                {d.valor_proposta != null && <DataRow label="Valor da Proposta" value={fmtBRL(d.valor_proposta)} />}
                {d.parcelas_max != null && <DataRow label="Parcelas Máx." value={String(d.parcelas_max)} />}
                {d.estrategia_oferta && <DataRow label="Estratégia" value={d.estrategia_oferta} />}
              </SecaoRecolhivel>
            )}
              </div>
            </details>
          </section>

        </div>

        {registro && carteiraId && (
          <ProximoDevedor key={registro.n} carteiraId={carteiraId} rankAtual={d.rank} doOperador={!isAdmin && !isComando}
            pagos={pagos.current} onIr={r => navigate(`/devedor/${r}`)} onVoltar={voltarAoDashboard} onFechar={() => setRegistro(null)} />
        )}
      </div>
    </AppShell>
  )
}
