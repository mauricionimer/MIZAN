import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { FolderOpen, Loader2, Send, Sparkles, ThumbsUp, ThumbsDown, Compass, Info } from 'lucide-react'
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
  { id: 'resumo', rotulo: 'Resumo do cliente' },
  { id: 'conversa', rotulo: 'Conversa' },
  { id: 'fluxo', rotulo: 'Fluxo do devedor' },
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

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <CabecalhoPagina voltar={voltar} rotulo="Pasta do cliente" icone={FolderOpen} titulo={dev.nome || 'Devedor'}
          subtitulo={sem ? <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: PONTO[sem.cor] }} aria-hidden="true" />
            <strong className="font-semibold text-ink">{sem.rotulo}</strong><span>· {sem.motivo}</span>
          </span> : null}>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            {dev.rank != null && <div><dt className="text-xs text-ink-3">Posição na fila</dt><dd className="font-semibold tabular-nums text-ink">#{dev.rank}</dd></div>}
            {dev.dias_em_atraso != null && <div><dt className="text-xs text-ink-3">Em atraso</dt><dd className="font-semibold tabular-nums text-ink">{dev.dias_em_atraso} dias</dd></div>}
            {dev.valor_divida != null && <div><dt className="text-xs text-ink-3">Dívida</dt><dd className="font-semibold tabular-nums text-ink">{brl(dev.valor_divida)}</dd></div>}
          </dl>
        </CabecalhoPagina>

        <div className="mb-6 flex gap-1 overflow-x-auto border-b border-line" role="tablist" aria-label="Papéis da pasta">
          {ABAS.map(a => {
            const on = a.id === aba
            const meta = (perfil?.papeis || []).find(p => p.id === a.id)?.meta
            return (
              <button key={a.id} type="button" role="tab" aria-selected={on} onClick={() => irAba(a.id)}
                className={`relative -mb-px shrink-0 border-b-2 px-3 py-2 text-left text-sm transition-colors ${on ? 'border-[var(--royal)] text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
                <span className="block font-medium">{a.rotulo}</span>
                {meta && <span className="block text-[11px] text-ink-3">{meta}</span>}
              </button>
            )
          })}
        </div>

        <ErroCarga erro={erro} onTentar={carregar} className="mb-4" />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={aba} initial={reduzir ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            exit={reduzir ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.2 }} role="tabpanel">
            {aba === 'resumo' && <Resumo perfil={perfil} carregando={carregando} irAba={irAba} />}
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

/* ── Resumo: situação, próximo passo e perfil do cliente ─────────────────── */
function Resumo({ perfil, carregando, irAba }) {
  if (carregando && !perfil) return <Carregando texto="Lendo a pasta…" />
  if (!perfil) return null
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Perfil perfil={perfil} />
      <div className="flex flex-col gap-5">
        <Aparece className="rounded-2xl border border-line bg-surface p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-3">Situação</p>
          <p className="mt-2 text-lg font-semibold text-ink">{SITUACAO[perfil.situacao] || 'Sem atendimento ainda'}</p>
          <p className="mt-1 text-sm text-ink-2">{perfil.semaforo?.motivo}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => irAba('conversa')} className="btn-primary btn-sm">Abrir a conversa</button>
            <button type="button" onClick={() => irAba('fluxo')} className="btn-secondary btn-sm">Ver o fluxo</button>
          </div>
        </Aparece>
        <Aparece atraso={0.08} className="rounded-2xl border border-line bg-surface p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-3">Base do perfil</p>
          <ul className="mt-3 space-y-2 text-sm text-ink-2">
            <li className="flex justify-between"><span>Mensagens do cliente</span><Contador className="font-semibold text-ink" valor={perfil.base?.mensagens_do_cliente || 0} /></li>
            <li className="flex justify-between"><span>Leituras da Triagem</span><Contador className="font-semibold text-ink" valor={perfil.base?.leituras || 0} /></li>
            <li className="flex justify-between"><span>Propostas feitas</span><Contador className="font-semibold text-ink" valor={perfil.base?.propostas || 0} /></li>
          </ul>
        </Aparece>
      </div>
    </div>
  )
}

function Perfil({ perfil }) {
  const [aberto, setAberto] = useState(null)
  if (!perfil.pronto) {
    return (
      <Aparece className="rounded-2xl border border-dashed border-line bg-surface p-6">
        <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-accent-text"><Sparkles className="h-4 w-4" aria-hidden="true" />Perfil do cliente</p>
        <p className="mt-3 text-lg font-semibold text-ink">Ainda não dá para dizer como ele é.</p>
        <p className="mt-1 text-sm text-ink-2">{perfil.falta || 'O perfil aparece quando o cliente começar a responder.'} A leitura é feita pelas conversas e pelo histórico de pagamento.</p>
        <div className="mt-5 space-y-4 opacity-40" aria-hidden="true">
          {['Como está agora', 'Jeito de falar', 'Confiança'].map(n => (
            <div key={n}><p className="mb-1 text-sm text-ink-2">{n}</p><div className="h-1.5 rounded-full bg-raise-2" /></div>
          ))}
        </div>
        <p className="mt-5 flex items-start gap-1.5 text-xs text-ink-3"><Info className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />{perfil.aviso}</p>
      </Aparece>
    )
  }
  return (
    <Aparece className="rounded-2xl border border-line bg-surface p-6">
      <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-accent-text"><Sparkles className="h-4 w-4" aria-hidden="true" />Perfil do cliente</p>
      <p className="mt-3 text-xl font-semibold leading-snug text-ink">{perfil.frase}</p>
      <p className="mt-1 text-xs text-ink-3">○ antes · ● agora. Toque num traço para ver de onde veio.</p>
      <ul className="mt-5 space-y-4">
        {perfil.tracos.map((t, i) => (
          <li key={t.id}>
            <button type="button" onClick={() => setAberto(aberto === t.id ? null : t.id)} aria-expanded={aberto === t.id}
              className="w-full rounded-xl p-2 text-left transition-colors hover:bg-raise-1">
              <span className="mb-1.5 flex items-center justify-between text-sm"><span className="font-medium text-ink">{t.nome}</span>
                <span className="text-xs text-ink-3">{aberto === t.id ? 'fechar' : 'de onde veio'}</span></span>
              <Regua esquerda={t.esquerda} direita={t.direita} antes={t.antes} agora={t.agora} atraso={i * 0.08}
                rotulo={`${t.nome}: ${t.agora} de 100 entre ${t.esquerda} e ${t.direita}`} />
            </button>
            <AnimatePresence initial={false}>
              {aberto === t.id && (
                <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden px-2 text-xs text-ink-2">
                  {t.fontes.map(f => <li key={f} className="mt-1 flex gap-1.5"><span aria-hidden="true">·</span>{f}</li>)}
                </motion.ul>
              )}
            </AnimatePresence>
          </li>
        ))}
      </ul>
      <div className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
        <Lista icone={ThumbsUp} cor="var(--success)" titulo="O que funciona" itens={perfil.funciona} />
        <Lista icone={ThumbsDown} cor="var(--danger)" titulo="O que evitar" itens={perfil.evitar} />
        <Lista icone={Compass} cor="var(--accent-text)" titulo="O que move ele" itens={perfil.move} />
      </div>
      <p className="mt-5 flex items-start gap-1.5 text-xs text-ink-3"><Info className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />{perfil.aviso} Não usa dados de saúde, religião ou política.</p>
    </Aparece>
  )
}

function Lista({ icone: Icone, cor, titulo, itens }) {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold" style={{ color: cor }}><Icone className="h-3.5 w-3.5" aria-hidden="true" />{titulo}</p>
      {itens?.length ? <ul className="space-y-1.5 text-sm text-ink-2">{itens.map(x => <li key={x}>{x}</li>)}</ul>
        : <p className="text-sm text-ink-3">Nada ainda.</p>}
    </div>
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
const COR_QUEM = { agente: 'var(--royal)', equipe: 'var(--success)', cliente: 'var(--text-muted)' }
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
      <section className="rounded-2xl border border-line bg-surface p-5" aria-label="Tudo o que aconteceu">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">Tudo o que aconteceu</h2>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar">
            {FILTROS_FLUXO.map(f => (
              <button key={f.id} type="button" aria-pressed={filtro === f.id} onClick={() => setFiltro(f.id)}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${filtro === f.id ? 'border-[var(--royal)] bg-raise-2 text-ink' : 'border-line text-ink-2 hover:text-ink'}`}>{f.rotulo}</button>
            ))}
          </div>
        </div>
        <ErroCarga erro={erro} onTentar={carregar} compacto />
        {carregando && !dados && <Carregando texto="Montando a linha do tempo…" />}
        {dados && !visiveis.length && <p className="py-6 text-sm text-ink-2">Nada registrado {filtro === 'todos' ? 'ainda' : 'para este filtro'}.</p>}
        <ol className="relative ml-2 border-l border-line">
          {visiveis.slice(0, 60).map((i, k) => (
            <li key={`${i.quando}-${k}`} className="relative pb-4 pl-5">
              <Ponto atraso={Math.min(k, 12) * 0.03} className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full" style={{ background: COR_QUEM[i.quem] }} aria-hidden="true" />
              <p className="text-sm font-medium text-ink">{i.titulo}</p>
              {i.texto && <p className="mt-0.5 text-sm text-ink-2">{i.texto}</p>}
              <p className="mt-0.5 text-[11px] text-ink-3">{dataHora(i.quando)}</p>
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
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section className="rounded-2xl border border-line bg-surface p-5" aria-label="Anotações">
        <h2 className="text-base font-semibold text-ink">Anotações</h2>
        <p className="mt-1 text-xs text-ink-3">Mais recentes primeiro. <span style={{ color: 'var(--royal)' }}>Azul</span>: agentes · <span style={{ color: 'var(--success)' }}>verde</span>: equipe.</p>
        <ErroCarga erro={erro} onTentar={carregar} compacto className="mt-3" />
        {carregando && !dados && <Carregando texto="Abrindo o caderno…" />}
        {dados && !notas.length && <p className="py-6 text-sm text-ink-2">O caderno está vazio. Quando um agente decidir algo sobre este cliente, aparece aqui.</p>}
        <ul className="mt-4 space-y-3">
          {notas.map((n, i) => {
            const equipe = n.agente === 'equipe'
            return (
              <Aparece as="li" key={`${n.quando}-${i}`} atraso={Math.min(i, 8) * 0.04}
                className="rounded-r-xl border-l-[3px] bg-raise-1 px-4 py-3" style={{ borderColor: equipe ? 'var(--success)' : 'var(--royal)' }}>
                <p className="text-xs font-semibold" style={{ color: equipe ? 'var(--success)' : 'var(--accent-text)' }}>{QUEM[n.agente] || n.agente} · <span className="font-normal text-ink-3">{dataHora(n.quando)}</span></p>
                <p className="mt-1 text-sm font-medium text-ink">{n.decisao}</p>
                {n.motivo && <p className="mt-0.5 text-sm text-ink-2">{n.motivo}</p>}
              </Aparece>
            )
          })}
        </ul>
      </section>
      {!isComando && (
        <form onSubmit={anotar} className="h-fit rounded-2xl border border-line bg-surface p-5">
          <label htmlFor="nota" className="text-base font-semibold text-ink">Nova anotação</label>
          <p className="mt-1 text-xs text-ink-3">Os agentes leem o caderno antes de cada mensagem. Não escreva CPF nem telefone: eles são removidos.</p>
          <textarea id="nota" value={texto} onChange={e => setTexto(e.target.value)} maxLength={200} rows={4}
            placeholder="Ex.: prefere conversar depois das 18h"
            className="mt-3 w-full resize-none rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-xs tabular-nums text-ink-3">{texto.length}/200</span>
            <button type="submit" disabled={!texto.trim() || salvando} className="btn-primary btn-sm">
              {salvando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="h-4 w-4" aria-hidden="true" />}
              {salvando ? 'Salvando…' : 'Anotar no caderno'}
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
        <Aparece className="rounded-2xl border border-line bg-surface p-6">
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
        <Aparece className="rounded-2xl border border-line bg-surface p-6">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-3">Hoje: {propostas.length ? 'negociando' : 'sem acordo'}</p>
          <p className="mt-2 text-lg font-semibold text-ink">{propostas.length ? `${propostas.length} proposta${propostas.length > 1 ? 's' : ''} feita${propostas.length > 1 ? 's' : ''}, nenhum acordo fechado ainda.` : 'Nenhuma proposta foi feita a este cliente.'}</p>
          {divida != null && <p className="mt-1 text-sm text-ink-2">Dívida de {brl(divida)}.</p>}
        </Aparece>
      )}
      {!!propostas.length && (
        <section className="rounded-2xl border border-line bg-surface p-5" aria-label="Propostas">
          <h2 className="text-base font-semibold text-ink">Propostas e respostas</h2>
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
