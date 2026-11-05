import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { Loader2, Send } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import ErroCarga from '../components/ErroCarga'
import FluxoDevedor from '../components/FluxoDevedor'
import { Aparece, BarraH, Contador, Ponto, Regua } from '../components/graficos'
import { useAuth } from '../context/AuthContext'
import { agenteAnotarCaderno, agenteCaso, agentePerfilCliente, listarAcordos } from '../api'
import { Conversa } from './Agente'
import { NOME_FAMILIA } from '../utils/ofertas'

/**
 * A pasta do cliente: os cinco papéis da pasta viram as cinco abas desta tela.
 *   Resumo · Conversa · Fluxo do devedor · Caderno do caso · Acordo e pagamentos
 * A aba mora na URL (?aba=), então cada papel tem um endereço próprio.
 */

export const ABAS = [
  { id: 'resumo', rotulo: 'Resumo' },
  { id: 'conversa', rotulo: 'Conversa' },
  { id: 'fluxo', rotulo: 'Fluxo' },
  { id: 'caderno', rotulo: 'Caderno do caso' },
  { id: 'acordo', rotulo: 'Acordo e pagamentos' },
]
const PONTO = { branco: 'var(--text-muted)', amarelo: 'var(--warning)', vermelho: 'var(--danger)' }
const QUEM = { estrategista: 'Estrategista', triagem: 'Triagem', negociador: 'Negociador', acompanhamento: 'Acompanhamento',
  supervisor: 'Supervisor', cientista: 'Cientista', equipe: 'Equipe' }
const SITUACAO = { novo: 'Não iniciado', em_contato: 'Em contato', negociando: 'Negociando', acordo_ativo: 'Acordo ativo',
  com_pessoa: 'Com a equipe', quitado: 'Quitado', quebrado: 'Acordo quebrado', pausado: 'Pausado' }
const brl = (v) => (v == null ? '—' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }))
const brl2 = (v) => (v == null ? '—' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }))
const dataHora = (iso) => { try { return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) } catch { return '' } }
const dataCurta = (iso) => { try { return new Date(String(iso).length <= 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('pt-BR') } catch { return '' } }

export default function PastaCliente() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const { state } = useLocation()
  const { isComando } = useAuth()
  const empresa = isComando ? (params.get('empresa') || undefined) : undefined
  const aba = ABAS.some(a => a.id === params.get('aba')) ? params.get('aba') : 'resumo'
  const reduzir = useReducedMotion()

  const [perfil, setPerfil] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const carregar = useCallback(async () => {
    setCarregando(true); setErro(null)
    try { setPerfil(await agentePerfilCliente(id)) } catch (e) { setErro(e) } finally { setCarregando(false) }
  }, [id])
  useEffect(() => { carregar() }, [carregar])

  // Nome e cor chegam antes pela pasta clicada; o servidor confirma em seguida.
  const dev = perfil?.devedor || state?.devedor || {}
  const sem = perfil?.semaforo || state?.devedor?.semaforo
  const voltar = { to: state?.de || '/pastas', rotulo: 'Pastas' }
  const irAba = (nova) => setParams(p => { const n = new URLSearchParams(p); n.set('aba', nova); return n }, { replace: true })
  const linhaInfo = [
    dev.dias_em_atraso != null && `${dev.dias_em_atraso} dias em atraso`,
    dev.valor_divida != null && `dívida de ${brl(dev.valor_divida)}`,
    perfil && SITUACAO[perfil.situacao],
  ].filter(Boolean).join(' · ')

  return (
    <AppShell>
      <div className="mx-auto max-w-[1180px]">
        <CabecalhoPagina voltar={voltar} className="mb-5"
          rotulo={<>Pasta do devedor{sem && <SeloCor sem={sem} />}</>}
          titulo={dev.nome || 'Devedor'}
          selo={dev.rank != null && <span className="rounded-full bg-[var(--royal-soft)] px-2.5 py-0.5 text-[13px] font-semibold tabular-nums text-accent-text">#{dev.rank} da fila</span>}
          subtitulo={linhaInfo || null}>
          <button type="button" onClick={() => irAba('caderno')} className="btn-secondary">Registrar contato</button>
          <button type="button" onClick={() => irAba('conversa')} className="btn-primary">Abrir conversa</button>
        </CabecalhoPagina>

        <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-line text-sm" role="tablist" aria-label="Arquivos da pasta">
          {ABAS.map(a => {
            const on = a.id === aba
            const meta = (perfil?.papeis || []).find(p => p.id === a.id)?.meta
            return (
              <button key={a.id} type="button" role="tab" aria-selected={on} onClick={() => irAba(a.id)} title={meta || undefined}
                className={`-mb-px shrink-0 border-b-2 px-3 py-2.5 transition-colors ${on ? 'border-[var(--royal)] font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
                {a.rotulo}
              </button>
            )
          })}
        </nav>

        <ErroCarga erro={erro} onTentar={carregar} className="mb-4" />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={aba} initial={reduzir ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            exit={reduzir ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.2 }} role="tabpanel">
            {aba === 'resumo' && <Resumo id={id} empresa={empresa} perfil={perfil} dev={dev} carregando={carregando} irAba={irAba} />}
            {aba === 'conversa' && <Conversa empresa={empresa} fixo={{ id, nome: dev.nome || 'Devedor' }} />}
            {aba === 'fluxo' && <Fluxo id={id} empresa={empresa} />}
            {aba === 'caderno' && <Caderno id={id} empresa={empresa} />}
            {aba === 'acordo' && <Acordo id={id} empresa={empresa} divida={dev.valor_divida} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </AppShell>
  )
}

/* Pílula da cor da pasta, ao lado do rótulo: "● Vermelha · pediu uma pessoa". */
const COR_SELO = {
  branco: 'bg-[var(--raised)] text-ink-2',
  amarelo: 'bg-[var(--warning-soft)] text-[var(--warning)]',
  vermelho: 'bg-[var(--danger-soft)] text-[var(--danger)]',
}
function SeloCor({ sem }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 normal-case tracking-[0.04em] ${COR_SELO[sem.cor] || COR_SELO.branco}`}>
      ● {sem.rotulo}{sem.motivo ? ` · ${sem.motivo}` : ''}
    </span>
  )
}

/* ── Resumo: números da dívida, situação, perfil e últimos contatos ───────── */
function Resumo({ id, empresa, perfil, dev, carregando, irAba }) {
  const { dados } = useCaso(id, empresa)
  if (carregando && !perfil) return <Carregando texto="Lendo a pasta…" />
  if (!perfil) return null
  const score = dev.score != null ? Math.round(Number(dev.score)) : null
  const contatos = (dados?.mensagens || []).slice(-4).reverse()
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <Numero rotulo="Dívida" valor={brl(dev.valor_divida)} />
        <Numero rotulo="Em atraso" valor={dev.dias_em_atraso != null ? `${dev.dias_em_atraso} dias` : '—'} />
        <Numero rotulo="Posição na fila" valor={dev.rank != null ? `#${dev.rank}` : '—'} />
        <Numero rotulo="Chance de pagar" valor={score != null
          ? <><span style={{ color: score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--danger)' }}>{score}</span> <span className="text-sm font-medium text-ink-3">de 100</span></>
          : '—'} />
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(300px,1fr)]">
        <div className="flex flex-col gap-3.5">
          <Aparece className="flex flex-col gap-2.5 rounded-2xl border border-line bg-surface px-6 py-[22px]">
            <span className="section-label">Situação agora</span>
            <p className="text-base leading-relaxed text-ink">
              <b>{SITUACAO[perfil.situacao] || 'Sem atendimento ainda'}.</b> {perfil.semaforo?.motivo}
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              <button type="button" onClick={() => irAba('conversa')} className="btn-primary btn-sm">Abrir conversa</button>
              <button type="button" onClick={() => irAba('fluxo')} className="btn-secondary btn-sm">Ver o fluxo</button>
            </div>
          </Aparece>
          <Perfil perfil={perfil} irAba={irAba} />
        </div>

        <aside className="flex flex-col gap-3.5">
          <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface px-[22px] py-5">
            <div className="flex items-center justify-between gap-3">
              <span className="section-label">Últimos contatos</span>
              <button type="button" onClick={() => irAba('fluxo')} className="text-[13px] text-accent-text hover:underline">Ver fluxo ↗</button>
            </div>
            {!dados && <p className="text-sm text-ink-3">Carregando…</p>}
            {dados && !contatos.length && <p className="text-sm text-ink-2">Nenhum contato ainda.</p>}
            {contatos.map((m, i) => {
              const cliente = m.direcao === 'entrada'
              const equipe = m.trace_id === 'pessoa'
              return (
                <div key={i} className="flex items-start gap-3">
                  <span className="mt-[5px] h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: cliente ? 'var(--text-2)' : equipe ? 'var(--success)' : 'var(--royal)' }} aria-hidden="true" />
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="line-clamp-2 text-sm text-ink">{cliente ? 'Cliente: ' : equipe ? 'Equipe: ' : 'Agente: '}{m.texto}</span>
                    <span className="text-xs text-ink-3">{dataHora(m.criado_em)}</span>
                  </div>
                </div>
              )
            })}
          </section>
          <section className="flex flex-col gap-2.5 rounded-2xl border border-line bg-surface px-[22px] py-5">
            <span className="section-label">Base do perfil</span>
            <LinhaNum rotulo="Mensagens do cliente" valor={perfil.base?.mensagens_do_cliente || 0} />
            <LinhaNum rotulo="Leituras da Triagem" valor={perfil.base?.leituras || 0} />
            <LinhaNum rotulo="Propostas feitas" valor={perfil.base?.propostas || 0} />
          </section>
          <details className="rounded-2xl border border-line bg-surface px-[22px] py-[18px]">
            <summary className="cursor-pointer text-sm font-semibold text-ink">Não conseguiu falar com ele?</summary>
            <p className="mt-2.5 text-sm leading-relaxed text-ink-2">Anote a tentativa no caderno do caso. Os agentes leem o caderno antes de cada mensagem.</p>
            <button type="button" onClick={() => irAba('caderno')} className="btn-secondary btn-sm mt-3">Abrir o caderno</button>
          </details>
        </aside>
      </div>
    </div>
  )
}

function Numero({ rotulo, valor }) {
  return (
    <Aparece className="flex flex-col gap-1 rounded-[18px] border border-line bg-surface px-[18px] py-4">
      <span className="text-[13px] text-ink-3">{rotulo}</span>
      <b className="text-2xl tabular-nums text-ink">{valor}</b>
    </Aparece>
  )
}

function LinhaNum({ rotulo, valor }) {
  return <div className="flex justify-between text-sm"><span className="text-ink-2">{rotulo}</span><Contador className="font-semibold text-ink" valor={valor} /></div>
}

function Perfil({ perfil, irAba }) {
  const [sel, setSel] = useState(0)
  const aviso = 'É uma leitura de comportamento para orientar a conversa, não um diagnóstico. Não usa saúde, religião, política nem outros dados sensíveis. Cada ponto mostra de onde veio.'
  if (!perfil.pronto) {
    return (
      <Aparece as="section" aria-label="Perfil do cliente" className="flex flex-col gap-3.5 rounded-2xl border border-line bg-surface px-6 py-[22px]">
        <span className="section-label">Perfil do cliente · leitura da IA</span>
        <b className="text-xl leading-snug text-ink">Ainda é cedo para ler o perfil dele.</b>
        <span className="text-sm leading-relaxed text-ink-2">{perfil.falta || 'O perfil aparece quando o cliente começar a responder.'}</span>
        <div className="space-y-4 opacity-40" aria-hidden="true">
          {['Como está agora', 'Jeito de falar', 'Confiança na empresa'].map(n => (
            <div key={n} className="grid grid-cols-[150px_minmax(0,1fr)] items-center gap-4"><span className="text-sm font-semibold text-ink">{n}</span><div className="h-1.5 rounded-full bg-[var(--raised)]" /></div>
          ))}
        </div>
        <span className="border-t border-line pt-3 text-xs leading-relaxed text-ink-3">{aviso}</span>
      </Aparece>
    )
  }
  const t = perfil.tracos[sel] || perfil.tracos[0]
  const base = perfil.base || {}
  const baseadoEm = [base.mensagens_do_cliente && `${base.mensagens_do_cliente} mensagens`, base.leituras && `${base.leituras} leituras`, base.propostas && `${base.propostas} propostas`].filter(Boolean).join(', ')
  return (
    <Aparece as="section" aria-label="Perfil do cliente" className="flex flex-col gap-4 rounded-2xl border border-line bg-surface px-6 py-[22px]">
      <span className="section-label">Perfil do cliente · leitura da IA</span>
      <div className="flex flex-col gap-1.5">
        <b className="text-xl leading-snug text-ink">{perfil.frase}</b>
        {baseadoEm && <span className="text-[13px] text-ink-2">Baseado em {baseadoEm}</span>}
      </div>
      <div role="list" className="flex flex-col gap-1">
        {perfil.tracos.map((x, k) => (
          <button key={x.id} type="button" role="listitem" onClick={() => setSel(k)} aria-pressed={k === sel}
            className={`grid grid-cols-1 items-center gap-x-4 gap-y-1 rounded-[14px] px-3 py-2.5 text-left sm:grid-cols-[180px_minmax(0,1fr)] ${k === sel ? 'bg-[var(--raised)]' : 'hover:bg-raise-1'}`}>
            <span className="text-sm font-semibold text-ink">{x.nome}</span>
            <Regua esquerda={x.esquerda} direita={x.direita} antes={x.antes} agora={x.agora} atraso={k * 0.08}
              rotulo={`${x.nome}: ${x.agora} de 100 entre ${x.esquerda} e ${x.direita}`} />
          </button>
        ))}
      </div>
      {t && (
        <div className="flex flex-col gap-1 rounded-2xl border border-[var(--border)] bg-canvas px-3.5 py-3">
          <span className="text-sm font-semibold text-ink">{t.nome}</span>
          <span className="text-xs leading-relaxed text-ink-3">De onde veio: {t.fontes?.length ? t.fontes.join(' · ') : 'sem fonte registrada'} · <button type="button" onClick={() => irAba('conversa')} className="text-accent-text hover:underline">ver na conversa ↗</button></span>
        </div>
      )}
      <span className="flex items-center gap-3.5 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-[var(--royal)]" aria-hidden="true" />agora</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-[9px] w-[9px] rounded-full border-[1.5px] border-[var(--text-muted)]" aria-hidden="true" />no primeiro contato</span>
      </span>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-2 rounded-2xl border border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)] px-4 py-3.5">
          <b className="text-[13px] text-[var(--success)]">Funciona com ele</b>
          {perfil.funciona?.length ? perfil.funciona.map(x => <span key={x} className="text-[13px] leading-relaxed text-ink">✓ {x}</span>) : <span className="text-[13px] text-ink-2">Nada ainda.</span>}
        </div>
        <div className="flex flex-col gap-2 rounded-2xl border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3.5">
          <b className="text-[13px] text-[var(--danger)]">Evitar</b>
          {perfil.evitar?.length ? perfil.evitar.map(x => <span key={x} className="text-[13px] leading-relaxed text-ink">✕ {x}</span>) : <span className="text-[13px] text-ink-2">Nada ainda.</span>}
        </div>
      </div>
      {!!perfil.move?.length && <span className="text-sm leading-relaxed text-ink"><b>O que move ele:</b> {perfil.move.map(x => x.replace(/\.+$/, '')).join('; ')}.</span>}
      <span className="border-t border-line pt-3 text-xs leading-relaxed text-ink-3">{perfil.aviso ? `${perfil.aviso} ` : ''}{aviso}</span>
    </Aparece>
  )
}

function Carregando({ texto }) {
  return <p className="flex items-center gap-2 py-10 text-sm text-ink-2" role="status"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{texto}</p>
}

/* Leitura do caso (mensagens, caderno, negociação) compartilhada por três abas. */
function useCaso(id, empresa) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const carregar = useCallback(async () => {
    setCarregando(true); setErro(null)
    try { setDados(await agenteCaso(id, empresa)) } catch (e) { setErro(e) } finally { setCarregando(false) }
  }, [id, empresa])
  useEffect(() => { carregar() }, [carregar])
  return { dados, setDados, erro, carregando, carregar }
}

/* ── Fluxo: as fases reais + tudo o que aconteceu ─────────────────────────── */
const FILTROS_FLUXO = [{ id: 'todos', rotulo: 'Tudo' }, { id: 'agente', rotulo: 'Agentes' }, { id: 'equipe', rotulo: 'Equipe' }, { id: 'cliente', rotulo: 'Cliente' }]
const COR_QUEM = { agente: 'var(--royal)', equipe: 'var(--success)', cliente: 'var(--text-2)' }
const NOME_EVENTO = { oferta_apresentada: 'Proposta apresentada', acordo_aceito: 'Acordo aceito', primeiro_pagamento_confirmado: 'Primeiro pagamento confirmado',
  acordo_quebrado: 'Acordo quebrado', retorno_cumprido: 'Retorno cumprido', transferencia_humana: 'Passou para a equipe' }

function Fluxo({ id, empresa }) {
  const { dados, erro, carregando, carregar } = useCaso(id, empresa)
  const [filtro, setFiltro] = useState('todos')
  const linha = useMemo(() => {
    if (!dados) return []
    const itens = []
    for (const m of dados.mensagens || []) {
      const quem = m.direcao === 'entrada' ? 'cliente' : m.trace_id === 'pessoa' ? 'equipe' : 'agente'
      itens.push({ quem, quando: m.criado_em, titulo: quem === 'cliente' ? 'Mensagem do cliente' : quem === 'equipe' ? 'Resposta da equipe' : 'Mensagem do agente',
        texto: m.texto?.length > 140 ? `${m.texto.slice(0, 140)}…` : m.texto })
    }
    for (const n of dados.caderno || []) {
      itens.push({ quem: n.agente === 'equipe' ? 'equipe' : 'agente', quando: n.quando, titulo: `${QUEM[n.agente] || n.agente}: ${n.decisao}`, texto: n.motivo })
    }
    for (const e of dados.caso?.negociacao?.eventos || []) {
      itens.push({ quem: e.tipo === 'transferencia_humana' ? 'equipe' : 'agente', quando: e.em, titulo: NOME_EVENTO[e.tipo] || e.tipo.replaceAll('_', ' '),
        texto: e.valor_total ? `Total ${brl2(e.valor_total)}` : e.valor ? brl2(e.valor) : '' })
    }
    return itens.filter(i => i.quando).sort((a, b) => String(b.quando).localeCompare(String(a.quando)))
  }, [dados])
  const visiveis = filtro === 'todos' ? linha : linha.filter(i => i.quem === filtro)
  return (
    <div className="flex flex-col gap-5">
      <FluxoDevedor predicaoId={id} />
      <section className="rounded-2xl border border-line bg-surface px-6 py-[22px]" aria-label="Tudo o que aconteceu">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="section-label">Tudo o que aconteceu</h2>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar">
            {FILTROS_FLUXO.map(f => (
              <button key={f.id} type="button" aria-pressed={filtro === f.id} onClick={() => setFiltro(f.id)}
                className={`h-8 rounded-full border px-3 text-[13px] ${filtro === f.id ? 'border-[var(--royal)] bg-[var(--royal-soft)] font-semibold text-ink' : 'border-line text-ink-2 hover:text-ink'}`}>{f.rotulo}</button>
            ))}
          </div>
        </div>
        <ErroCarga erro={erro} onTentar={carregar} compacto />
        {carregando && !dados && <Carregando texto="Montando a linha do tempo…" />}
        {dados && !visiveis.length && <p className="py-6 text-sm text-ink-2">Nada registrado {filtro === 'todos' ? 'ainda' : 'para este filtro'}.</p>}
        <ol className="flex flex-col">
          {visiveis.slice(0, 60).map((i, k) => (
            <li key={`${i.quando}-${k}`} className="grid grid-cols-[84px_22px_minmax(0,1fr)] gap-3 sm:grid-cols-[110px_22px_minmax(0,1fr)]">
              <span className="pt-[3px] text-right text-xs tabular-nums text-ink-3">{dataHora(i.quando)}</span>
              <span className="flex flex-col items-center">
                <Ponto atraso={Math.min(k, 12) * 0.03} className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: COR_QUEM[i.quem] }} aria-hidden="true" />
                <span className="mt-1 w-0.5 flex-1 bg-line" aria-hidden="true" />
              </span>
              <div className="flex min-w-0 flex-col gap-0.5 pb-4">
                <span className="text-sm text-ink">{i.titulo}</span>
                {i.texto && <span className="text-sm text-ink-2">{i.texto}</span>}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

/* ── Caderno: anotações dos agentes e da equipe ──────────────────────────── */
function Caderno({ id, empresa }) {
  const { dados, setDados, erro, carregando, carregar } = useCaso(id, empresa)
  const { isComando } = useAuth()
  const [texto, setTexto] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroNota, setErroNota] = useState(null)
  const notas = dados?.caderno || []
  async function anotar(e) {
    e.preventDefault()
    if (!texto.trim() || salvando) return
    setSalvando(true); setErroNota(null)
    try {
      const r = await agenteAnotarCaderno(id, texto.trim(), empresa)
      setDados(d => ({ ...(d || {}), caderno: r.caderno })); setTexto('')
    } catch (err) { setErroNota(err) } finally { setSalvando(false) }
  }
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="rounded-2xl border border-line bg-surface px-6 py-[22px]" aria-label="Anotações">
        <div className="flex items-center justify-between gap-3"><span className="section-label">{notas.length} {notas.length === 1 ? 'anotação' : 'anotações'}</span><span className="text-xs text-ink-3">mais recentes primeiro</span></div>
        <p className="mt-1 text-xs text-ink-3"><span style={{ color: 'var(--success)' }}>Verde</span>: equipe (pessoas) · escuro: agentes.</p>
        <ErroCarga erro={erro} onTentar={carregar} compacto className="mt-3" />
        {carregando && !dados && <Carregando texto="Abrindo o caderno…" />}
        {dados && !notas.length && <p className="py-6 text-sm text-ink-2">O caderno está vazio. Quando um agente decidir algo sobre este cliente, aparece aqui.</p>}
        <ul className="mt-4 space-y-3">
          {notas.map((n, i) => {
            const equipe = n.agente === 'equipe'
            return (
              <Aparece as="li" key={`${n.quando}-${i}`} atraso={Math.min(i, 8) * 0.04}
                className={`rounded-2xl border px-4 py-3.5 ${equipe ? 'border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)]' : 'border-line bg-canvas'}`}>
                <p className="text-xs font-semibold" style={{ color: equipe ? 'var(--success)' : 'var(--accent-text)' }}>{QUEM[n.agente] || n.agente} · <span className="font-normal text-ink-3">{dataHora(n.quando)}</span></p>
                <p className="mt-1 text-sm font-medium text-ink">{n.decisao}</p>
                {n.motivo && <p className="mt-0.5 text-sm text-ink-2">{n.motivo}</p>}
              </Aparece>
            )
          })}
        </ul>
      </section>
      {!isComando && (
        <form onSubmit={anotar} className="h-fit rounded-2xl border border-line bg-surface px-6 py-[22px]">
          <label htmlFor="nota" className="section-label">Nova anotação</label>
          <p className="mt-1 text-xs text-ink-3">Os agentes leem o caderno antes de cada mensagem. Não escreva CPF nem telefone: eles são removidos.</p>
          <textarea id="nota" value={texto} onChange={e => setTexto(e.target.value)} maxLength={200} rows={4}
            placeholder="O que o próximo a atender precisa saber?"
            className="mt-3 min-h-[110px] w-full resize-y rounded-[14px] border border-[var(--border)] bg-canvas px-3.5 py-3 text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-xs tabular-nums text-ink-3">{texto.length}/200</span>
            <button type="submit" disabled={!texto.trim() || salvando} className="btn-primary btn-sm">
              {salvando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="h-4 w-4" aria-hidden="true" />}
              {salvando ? 'Guardando…' : 'Guardar no caderno'}
            </button>
          </div>
          <ErroCarga erro={erroNota} compacto className="mt-3" />
        </form>
      )}
    </div>
  )
}

/* ── Acordo e pagamentos ─────────────────────────────────────────────────── */
const COR_PARCELA = { paga: 'var(--success)', atrasada: 'var(--danger)', aberta: 'var(--royal)' }

function Acordo({ id, empresa, divida }) {
  const { dados, erro, carregando, carregar } = useCaso(id, empresa)
  const [acordos, setAcordos] = useState(null)
  const [erroAc, setErroAc] = useState(null)
  const carregarAcordos = useCallback(() => {
    setErroAc(null)
    return listarAcordos(empresa, id).then(r => setAcordos(r.acordos || [])).catch(setErroAc)
  }, [empresa, id])
  useEffect(() => { carregarAcordos() }, [carregarAcordos])
  const eventos = dados?.caso?.negociacao?.eventos || []
  const propostas = eventos.filter(e => e.tipo === 'oferta_apresentada' || e.tipo === 'acordo_aceito')
  const acordo = acordos?.[0]
  const parcelas = acordo?.parcelas || []
  const pagas = parcelas.filter(p => p.situacao === 'paga')
  const entrou = pagas.reduce((s, p) => s + Number(p.valor || 0), 0)
  const total = parcelas.reduce((s, p) => s + Number(p.valor || 0), 0)
  const proxima = parcelas.find(p => p.situacao !== 'paga')
  return (
    <div className="flex flex-col gap-5">
      <ErroCarga erro={erro || erroAc} onTentar={() => { carregar(); carregarAcordos() }} />
      {(carregando && !dados) || acordos === null ? <Carregando texto="Buscando propostas e parcelas…" /> : null}
      {acordo ? (
        <Aparece className="rounded-2xl border border-line bg-surface px-6 py-[22px]">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-3">Hoje: acordo {acordo.situacao === 'quebrado' ? 'quebrado' : 'ativo'}</p>
          <div className="mt-3 grid gap-4 sm:grid-cols-3">
            <div><p className="text-xs text-ink-3">Já entrou</p><p className="text-2xl font-bold tabular-nums" style={{ color: 'var(--success)' }}><Contador valor={entrou} formatar={brl} /></p></div>
            <div><p className="text-xs text-ink-3">Falta</p><p className="text-2xl font-bold tabular-nums text-ink"><Contador valor={Math.max(0, total - entrou)} formatar={brl} /></p></div>
            <div><p className="text-xs text-ink-3">Próxima parcela</p><p className="text-2xl font-bold tabular-nums text-ink">{proxima ? dataCurta(proxima.vencimento) : '—'}</p>
              {proxima && <p className="text-xs text-ink-2">{brl2(proxima.valor)}</p>}</div>
          </div>
          <div className="mt-5 flex flex-wrap gap-1.5" role="img" aria-label={`${pagas.length} de ${parcelas.length} parcelas pagas`}>
            {parcelas.map((p, i) => {
              const cor = COR_PARCELA[p.situacao] || 'var(--royal)'
              const cheia = p.situacao === 'paga' || p.situacao === 'atrasada'
              const borda = p === proxima || cheia ? cor : `color-mix(in srgb, ${cor} 40%, transparent)`
              return <Ponto key={p.id} atraso={i * 0.05} title={`Parcela ${p.numero}: ${p.situacao} · ${dataCurta(p.vencimento)}`}
                className="h-3 min-w-[28px] flex-1 rounded-full" style={{ background: cheia ? cor : 'transparent', boxShadow: `inset 0 0 0 2px ${borda}` }} />
            })}
          </div>
          <p className="mt-2 text-xs text-ink-3">Verde: paga · contorno forte: a próxima · vermelho: atrasada.</p>
        </Aparece>
      ) : acordos !== null && (
        <Aparece className="rounded-2xl border border-line bg-surface px-6 py-[22px]">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-3">Hoje: {propostas.length ? 'negociando' : 'sem acordo'}</p>
          <p className="mt-2 text-lg font-semibold text-ink">{propostas.length ? `${propostas.length} proposta${propostas.length > 1 ? 's' : ''} feita${propostas.length > 1 ? 's' : ''}, nenhum acordo fechado ainda.` : 'Nenhuma proposta foi feita a este cliente.'}</p>
          {divida != null && <p className="mt-1 text-sm text-ink-2">Dívida de {brl(divida)}.</p>}
        </Aparece>
      )}
      {!!propostas.length && (
        <section className="rounded-2xl border border-line bg-surface px-6 py-[22px]" aria-label="Propostas">
          <h2 className="section-label">Propostas e respostas</h2>
          <ul className="mt-4 space-y-3">
            {propostas.slice().reverse().map((e, i) => (
              <li key={e.chave || i} className="flex flex-wrap items-center gap-3">
                <span className="w-44 shrink-0 text-sm text-ink">{e.tipo === 'acordo_aceito' ? 'Aceitou' : 'Proposta'}{e.familia ? ` · ${NOME_FAMILIA[e.familia] || e.familia.replaceAll('_', ' ')}` : ''}</span>
                <div className="min-w-[120px] flex-1"><BarraH valor={e.valor_total || 0} max={divida || e.valor_total || 1} atraso={i * 0.06}
                  cor={e.tipo === 'acordo_aceito' ? 'var(--success)' : 'var(--royal)'} rotulo={brl2(e.valor_total)} /></div>
                <span className="w-28 shrink-0 text-right text-sm tabular-nums text-ink-2">{e.valor_total ? brl2(e.valor_total) : '—'}</span>
                <span className="w-24 shrink-0 text-right text-xs text-ink-3">{dataCurta(e.em)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-xs text-ink-3">Para baixar parcelas e ver todos os acordos da empresa, use <Link to="/acordos" className="text-accent-text underline">Acordos</Link>.</p>
    </div>
  )
}
