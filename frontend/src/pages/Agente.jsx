// Agentes: a conversa de um caso (com o porquê de cada passo) e a Central de
// orquestração. Na demonstração, quem está na tela escreve como o devedor.
// Regras em backend/agente/ (docs/PLANO_EXECUCAO_AGENTES.md).
import { useEffect, useRef, useState } from 'react'
import { Bot, Send, Search, Loader2, Activity, ShieldCheck, AlertTriangle, Power, UserRound, Coins, ListChecks, Landmark, Clock, Shuffle, CalendarDays, Scale, Hand, Undo2, CalendarClock, Users, BookOpen, FlaskConical } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import ErroCarga from '../components/ErroCarga'
import EscritorioAgentes, { Retrato } from '../components/EscritorioAgentes'
import { useAuth } from '../context/AuthContext'
import { agenteDevedores, agenteCaso, agenteSimularMensagem, agenteSimularPagamento, agenteCentral, agenteRelogio, agentePlano, agenteAplicarPlano, agentePoliticas, agenteSalvarPolitica, agenteControle, agenteAgenda, agenteAtribuir, agenteLaboratorio, agenteAnalisar, agenteDecidirRecomendacao, agenteAgentes, listarEmpresas } from '../api'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)
const fmtUSD = (v) => `US$ ${Number(v || 0).toFixed(4)}`
const fmtData = (iso) => iso ? new Intl.DateTimeFormat('pt-BR').format(new Date(String(iso).slice(0, 10) + 'T12:00:00')) : '—'
const fmtHora = (iso) => iso ? new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date(iso)) : ''

const SITUACAO = {
  novo: 'Novo', so_lembrete: 'Só lembrete', em_contato: 'Em contato', negociando: 'Negociando',
  acordo_ativo: 'Acordo ativo', atrasado: 'Atrasado', pagamento_em_conferencia: 'Pagamento em conferência',
  contestado: 'Contestado', suspenso: 'Suspenso', com_pessoa: 'Com uma pessoa', quitado: 'Quitado', quebrado: 'Quebrado',
}
const COR_SIT = {
  acordo_ativo: 'var(--success)', quitado: 'var(--success)', contestado: 'var(--warning)', suspenso: 'var(--warning)',
  com_pessoa: 'var(--warning)', atrasado: 'var(--danger)', quebrado: 'var(--danger)',
}
const EVENTO = { mensagem_devedor: 'Mensagem do devedor', pagamento: 'Pagamento', vencimento: 'Data (relógio)',
  relogio: 'Relógio', contestacao: 'Contestação', pedido_parar: 'Pedido para parar' }
const SIT_EVENTO = { pendente: 'Na fila', processando: 'Em andamento', feito: 'Feito', falhou: 'Falhou' }
const COR_RES = { ok: 'var(--success)', bloqueado: 'var(--warning)', erro: 'var(--danger)' }
const NOME_NO = {
  receber: 'Recebeu a mensagem', triagem: 'Triagem: entendeu a intenção', negociar: 'Negociador', enviar: 'Enviou a resposta',
  auditor: 'Auditor', guardrails: 'Travas do texto', resposta_fixa: 'Resposta fixa (sem IA)', suspender: 'Suspendeu a cobrança',
  contestar: 'Abriu contestação', transferir: 'Passou para uma pessoa', avisar_equipe: 'Avisou a equipe', erro: 'Nó de erro',
  conferir: 'Acompanhamento: conferiu a data', decisao: 'Decisão do Acompanhamento', lembrar: 'Lembrete (mensagem pronta)',
  cobrar_atraso: 'Procurou pelo atraso', encerrar: 'Sem resposta: passou para uma pessoa', registrar: 'Pagamento registrado',
}
const nomeNo = (n) => NOME_NO[n] || (n?.startsWith('ferramenta:') ? `Ferramenta: ${n.slice(11).replaceAll('_', ' ')}` : n)

// Os agentes e o que cada um faz: a mesma cor no passo a passo e na legenda.
// [nome, cor, o que faz, grupo]. Grupo: 'ia' (agente com IA), 'codigo' (agente
// sem IA, de propósito) ou 'seguranca' (não é agente: aparece nos passos).
const AGENTES = [
  ['Triagem', '#a78bfa', 'Lê intenção, emoção, urgência e ironia. Pedido de parar, pessoa ou sofrimento: regra, sem IA.', 'ia'],
  ['Negociador', '#60a5fa', 'Conversa, confirma a identidade, simula acordos e tira dúvidas com a lei, usando 16 ferramentas.', 'ia'],
  ['Estrategista', '#22d3ee', 'Decide como abordar cada devedor (tom, oferta, adiar), com o bandit como conselheiro. Quem cobrar e o sorteio ficam em código.', 'ia'],
  ['Acompanhamento', '#fb923c', 'Em cada data decide lembrar, esperar, oferecer nova data ou chamar uma pessoa, e escreve a mensagem. Reserva: texto pronto.', 'ia'],
  ['Supervisor', '#e879f9', 'Resume o caso para a equipe e revisa o tom em conversas delicadas. Não libera nada.', 'ia'],
  ['Cientista', '#facc15', 'Compara agente e grupo sorteado e propõe o próximo passo. Contas e selo de evidência em código. Aba Laboratório.', 'ia'],
  ['Orquestrador', '#94a3b8', 'Recebe cada evento, põe na fila e chama o próximo agente.', 'codigo'],
  ['Auditor', '#f59e0b', 'Confere cada ação contra a política da empresa. A palavra final é dele: não pode ser IA, porque um devedor esperto poderia convencê-la.', 'codigo'],
  ['Travas', '#f472b6', 'Conferem o texto antes de sair: valor, lei, tom e se o que diz que fez foi mesmo feito.', 'seguranca'],
  ['Ferramenta', '#34d399', 'O que foi gravado de verdade: agenda, acordo, contestação, transferência.', 'seguranca'],
]
export const COR_AGENTE = { ...Object.fromEntries(AGENTES.map(([n, c]) => [n, c])), Supervisor: '#e879f9', Cientista: '#facc15', Equipe: '#e5e7eb' }
const OFERTA_NOME = { avista_10pct: '10% à vista', desconto_30pct: '30% à vista', parcelado_4x: 'até 4x', parcelado_12x: 'até 12x' }
const QUEM_CADERNO = { estrategista: 'Estrategista', triagem: 'Triagem', negociador: 'Negociador', acompanhamento: 'Acompanhamento',
  supervisor: 'Supervisor', cientista: 'Cientista', equipe: 'Equipe' }
const TIPO_AGENDA = { atendimento: 'Atendimento com pessoa', transferencia: 'Transferido', conferencia: 'Conferir pagamento',
  retorno: 'Retorno do agente', promessa: 'Promessa de pagamento' }

function Selo({ situacao }) {
  if (!situacao) return null
  const cor = COR_SIT[situacao] || 'var(--ink-2)'
  return <span className="rounded-full border px-2 py-0.5 text-xs font-semibold" style={{ color: cor, borderColor: cor }}>{SITUACAO[situacao] || situacao}</span>
}

function Passos({ passos }) {
  if (!passos?.length) return <p className="text-xs text-ink-2">Os passos da última resposta aparecem aqui.</p>
  const custo = passos.reduce((s, p) => s + Number(p.custo_usd || 0), 0)
  const tokens = passos.reduce((s, p) => s + (p.tokens_entrada || 0) + (p.tokens_saida || 0), 0)
  return (
    <div className="space-y-2">
      <ol className="space-y-1">
        {passos.map((p, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded-lg px-2 py-1.5 text-xs hover:bg-raise-1">
            <span className="h-2 w-2 shrink-0 translate-y-[-1px] rounded-full" style={{ background: COR_RES[p.resultado] || 'var(--ink-3)' }} />
            {p.quem && <span className="rounded px-1.5 py-px text-[11px] font-semibold" style={{ color: COR_AGENTE[p.quem] || 'var(--ink-2)', background: 'color-mix(in srgb, currentColor 14%, transparent)' }}>{p.quem}</span>}
            <span className="font-medium text-ink">{p.explicacao || nomeNo(p.no)}</span>
            {p.regra && <span className="rounded bg-raise-2 px-1.5 py-px font-mono text-[11px] text-ink-2">{p.regra}{p.versao_politica ? ` · v${p.versao_politica}` : ''}</span>}
            {p.detalhe?.fontes?.map((f) => (
              <span key={f} className="rounded border border-line px-1.5 py-px text-[11px] text-ink" title="Fonte consultada na base de conhecimento">Fonte: {f}</span>
            ))}
            {p.detalhe?.certeza === false && <span style={{ color: 'var(--warning)' }}>sem resposta segura na base</span>}
            {p.resultado === 'bloqueado' && !p.explicacao && <span style={{ color: 'var(--warning)' }}>bloqueado</span>}
            {p.resultado === 'erro' && <span style={{ color: 'var(--danger)' }}>erro{p.detalhe?.erro ? `: ${p.detalhe.erro}` : ''}</span>}
            <span className="ml-auto tabular-nums text-ink-3">{p.duracao_ms} ms{p.tokens_entrada ? ` · ${p.tokens_entrada + p.tokens_saida} tokens` : ''}</span>
          </li>
        ))}
      </ol>
      <p className="border-t border-line pt-2 text-xs text-ink-2">{passos.length} passos · {tokens} tokens · {fmtUSD(custo)}</p>
    </div>
  )
}

function Conversa({ empresa }) {
  const [busca, setBusca] = useState('')
  const [devedores, setDevedores] = useState([])
  const [escolhido, setEscolhido] = useState(null)
  const [dados, setDados] = useState(null)
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [valorPago, setValorPago] = useState('')
  const fim = useRef(null)

  async function controlar(acao) {
    setEnviando(true); setErro(null)
    try { setDados(await agenteControle(escolhido.id, acao, empresa)) } catch (err) { setErro(err) } finally { setEnviando(false) }
  }

  async function pagar(e) {
    e.preventDefault()
    const v = Number(String(valorPago).replace(/\./g, '').replace(',', '.'))
    if (!v || enviando) return
    setEnviando(true); setErro(null)
    try { setDados(await agenteSimularPagamento(escolhido.id, v, empresa)); setValorPago('') }
    catch (err) { setErro(err) } finally { setEnviando(false) }
  }

  useEffect(() => {
    const t = setTimeout(() => {
      agenteDevedores(busca, empresa).then(d => setDevedores(d.devedores || [])).catch(setErro)
    }, 300)
    return () => clearTimeout(t)
  }, [busca, empresa])

  useEffect(() => {
    if (!escolhido) return
    setDados(null); setErro(null)
    agenteCaso(escolhido.id, empresa).then(setDados).catch(setErro)
  }, [escolhido, empresa])

  useEffect(() => { fim.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [dados?.mensagens?.length])

  async function enviar(e) {
    e.preventDefault()
    if (!texto.trim() || enviando) return
    setEnviando(true); setErro(null)
    const mensagem = texto
    setTexto('')
    try {
      setDados(await agenteSimularMensagem(escolhido.id, mensagem, empresa))
    } catch (err) { setErro(err); setTexto(mensagem) } finally { setEnviando(false) }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
      <section className="rounded-xl border border-line bg-surface p-3">
        <label className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-2.5 py-1.5">
          <Search className="h-4 w-4 text-ink-3" />
          <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar devedor…" aria-label="Buscar devedor"
            className="w-full bg-transparent text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
        </label>
        <ul className="mt-2 max-h-[60vh] space-y-0.5 overflow-y-auto">
          {devedores.map(d => (
            <li key={d.id}>
              <button onClick={() => setEscolhido(d)}
                className={`w-full rounded-lg px-2.5 py-2 text-left transition-colors ${escolhido?.id === d.id ? 'bg-blue-500/15' : 'hover:bg-raise-1'}`}>
                <p className="truncate text-sm font-medium text-ink">{d.nome}</p>
                <p className="text-xs text-ink-2">{fmtBRL(d.valor_divida)} · {d.dias_em_atraso} dias</p>
              </button>
            </li>
          ))}
          {!devedores.length && <li className="px-2 py-6 text-center text-xs text-ink-2">Nenhum devedor na carteira mais recente.</li>}
        </ul>
      </section>

      <section className="flex min-h-[60vh] flex-col rounded-xl border border-line bg-surface">
        {!escolhido ? (
          <div className="m-auto max-w-sm p-6 text-center text-sm text-ink-2">
            <Bot className="mx-auto mb-3 h-8 w-8 opacity-60" />
            Escolha um devedor e escreva como se fosse ele. O agente responde pelas regras da empresa, e cada passo aparece ao lado.
          </div>
        ) : (
          <>
            <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
              <UserRound className="h-4 w-4 text-ink-2" />
              <p className="text-sm font-semibold text-ink">{escolhido.nome}</p>
              <Selo situacao={dados?.caso?.situacao} />
              {dados?.caso?.identidade_confirmada && <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--success)' }}><ShieldCheck className="h-3.5 w-3.5" /> identidade confirmada</span>}
              {dados?.caso && (dados.caso.situacao === 'com_pessoa'
                ? <button onClick={() => controlar('devolver')} disabled={enviando} className="ml-auto flex items-center gap-1 rounded-md border border-line bg-raise-1 px-2 py-1 text-xs font-medium text-ink hover:bg-raise-2"><Undo2 className="h-3.5 w-3.5" /> Devolver ao agente</button>
                : <button onClick={() => controlar('assumir')} disabled={enviando} className="ml-auto flex items-center gap-1 rounded-md border border-line bg-raise-1 px-2 py-1 text-xs font-medium text-ink hover:bg-raise-2"><Hand className="h-3.5 w-3.5" /> Assumir o caso</button>)}
            </header>
            <div className="flex-1 space-y-2 overflow-y-auto p-4">
              {(dados?.mensagens || []).map((m, i) => (
                <div key={i} className={`flex ${m.direcao === 'entrada' ? 'justify-start' : 'justify-end'}`}>
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm ${m.direcao === 'entrada' ? 'rounded-bl-sm bg-raise-2 text-ink' : 'rounded-br-sm bg-blue-600 text-white'}`}>
                    <p className="whitespace-pre-wrap">{m.texto}</p>
                    <p className={`mt-1 text-[10px] ${m.direcao === 'entrada' ? 'text-ink-3' : 'text-blue-100'}`}>{m.direcao === 'entrada' ? 'Devedor' : 'Assistente'} · {fmtHora(m.criado_em)}</p>
                  </div>
                </div>
              ))}
              {!enviando && dados?.silencio && (
                <div className="flex justify-center">
                  <p className="flex max-w-[90%] items-start gap-1.5 rounded-lg border px-3 py-1.5 text-xs" style={{ color: 'var(--warning)', borderColor: 'var(--warning)' }}>
                    <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> O agente não respondeu. {dados.silencio}
                  </p>
                </div>
              )}
              {enviando && <div className="flex justify-end"><span className="flex items-center gap-2 rounded-2xl bg-raise-2 px-3 py-2 text-xs text-ink-2"><Loader2 className="h-3.5 w-3.5 animate-spin" /> o agente está respondendo…</span></div>}
              <div ref={fim} />
            </div>
            <ErroCarga erro={erro} compacto className="mx-4 mb-2" />
            {dados?.caso && (
              <form onSubmit={pagar} className="flex flex-wrap items-center gap-2 border-t border-line px-3 pt-3 text-xs text-ink-2">
                <Landmark className="h-4 w-4" /> Simular o banco confirmando um pagamento de R$
                <input value={valorPago} onChange={e => setValorPago(e.target.value)} inputMode="decimal" placeholder="270,00" aria-label="Valor pago"
                  className="w-24 rounded-md border border-line bg-surface-2 px-2 py-1 text-sm text-ink focus:outline-none" />
                <button type="submit" disabled={enviando || !valorPago} className="rounded-md border border-line bg-raise-1 px-2.5 py-1 font-medium text-ink hover:bg-raise-2 disabled:opacity-50">Confirmar pagamento</button>
              </form>
            )}
            <form onSubmit={enviar} className="flex gap-2 border-t border-line p-3">
              <input value={texto} onChange={e => setTexto(e.target.value)} maxLength={2000} disabled={enviando}
                placeholder="Escreva como o devedor…" aria-label="Mensagem do devedor"
                className="flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
              <button type="submit" disabled={enviando || !texto.trim()} className="btn-primary flex items-center gap-1.5 disabled:opacity-50">
                <Send className="h-4 w-4" /> Enviar
              </button>
            </form>
          </>
        )}
      </section>

      <section className="rounded-xl border border-line bg-surface p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"><ListChecks className="h-4 w-4 text-blue-400" /> Por que o agente fez isso</h2>
        <Passos passos={dados?.passos} />
        {dados?.caderno?.length > 0 && (
          <div className="mt-4 border-t border-line pt-3">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink"><BookOpen className="h-3.5 w-3.5 text-blue-400" /> Caderno do caso</h3>
            <p className="mb-2 text-[11px] text-ink-3">O que cada agente decidiu; o próximo lê antes de agir.</p>
            <ol className="space-y-1.5">
              {dados.caderno.map((n, i) => {
                const quem = QUEM_CADERNO[n.agente] || n.agente
                return (
                  <li key={i} className="text-xs">
                    <span className="mr-1.5 rounded px-1.5 py-px text-[11px] font-semibold" style={{ color: COR_AGENTE[quem] || 'var(--ink-2)', background: 'color-mix(in srgb, currentColor 14%, transparent)' }}>{quem}</span>
                    <span className="font-medium text-ink">{n.decisao}</span>
                    {n.motivo && <span className="text-ink-2"> — {n.motivo}</span>}
                    <span className="ml-1 text-[10px] text-ink-3">{fmtHora(n.quando)}</span>
                  </li>
                )
              })}
            </ol>
          </div>
        )}
        {dados?.atendimento && (
          <div className="mt-4 rounded-lg border border-line bg-surface-2 p-3 text-xs text-ink-2">
            <p className="flex items-center gap-1.5 font-semibold text-ink"><CalendarClock className="h-3.5 w-3.5" /> Atendimento com pessoa marcado</p>
            <p className="mt-1">{fmtData(dados.atendimento.data)} às {dados.atendimento.hora} · {dados.atendimento.atendente || 'o administrador escolhe quem atende (aba Agenda)'}.</p>
          </div>
        )}
        {dados?.caso?.acordo && (
          <div className="mt-4 rounded-lg border border-line bg-surface-2 p-3 text-xs text-ink-2">
            <p className="font-semibold text-ink">Acordo registrado</p>
            <p className="mt-1">Primeiro pagamento de {fmtBRL(dados.caso.acordo.primeiro_pagamento)} em {fmtData(dados.caso.acordo.data)}.</p>
          </div>
        )}
      </section>
    </div>
  )
}

function Cartao({ icone: Icone, rotulo, valor, nota, cor }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between"><p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">{rotulo}</p><Icone className="h-4 w-4" style={{ color: cor }} /></div>
      <p className="mt-2 text-xl font-bold tabular-nums text-ink">{valor}</p>
      {nota && <p className="mt-1 text-xs text-ink-2">{nota}</p>}
    </div>
  )
}

function Central({ empresa }) {
  const [c, setC] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [rodando, setRodando] = useState(false)
  const [avisoRelogio, setAvisoRelogio] = useState('')
  function carregar() {
    setCarregando(true); setErro(null)
    return agenteCentral(empresa).then(setC).catch(setErro).finally(() => setCarregando(false))
  }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  if (carregando && !c) return <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
  if (!c) return <ErroCarga erro={erro} onTentar={carregar} />
  const ev = c.eventos || {}
  async function relogio() {
    setRodando(true); setErro(null)
    try { const r = await agenteRelogio(empresa); setAvisoRelogio(`${r.eventos_criados} evento(s) de data criados, ${r.processados} processado(s).`); await carregar() }
    catch (e) { setErro(e) } finally { setRodando(false) }
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={relogio} disabled={rodando} className="flex items-center gap-1.5 rounded-md border border-line bg-raise-1 px-3 py-1.5 text-sm font-medium text-ink hover:bg-raise-2 disabled:opacity-50">
          {rodando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clock className="h-4 w-4" />} Rodar o relógio agora
        </button>
        <span className="text-xs text-ink-2">{avisoRelogio || 'O servidor roda sozinho a cada 10 minutos: lembretes, atrasos e pagamentos.'}</span>
      </div>
      <ErroCarga erro={erro} onTentar={carregar} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Cartao icone={Power} rotulo="Agente" valor={c.ligado ? 'Ligado' : 'Desligado'} cor={c.ligado ? 'var(--success)' : 'var(--ink-3)'}
          nota={`IA: ${c.cliente} · triagem ${c.modelos.triagem} · conversa ${c.modelos.negociador}`} />
        <Cartao icone={Coins} rotulo="Custo hoje" valor={fmtUSD(c.custo_hoje_usd)} cor="var(--ink-2)" nota={`teto do dia: US$ ${c.teto_dia_usd.toFixed(2)}`} />
        <Cartao icone={ShieldCheck} rotulo="Política" valor={c.politica.versao ? `Versão ${c.politica.versao}` : 'Sem política'}
          cor={c.politica.versao ? 'var(--success)' : 'var(--warning)'}
          nota={c.politica.regras ? `desconto até ${c.politica.regras.desconto_max_pct}% · até ${c.politica.regras.parcelas_max}x` : 'sem política, só ações de segurança passam'} />
        <Cartao icone={AlertTriangle} rotulo="Falharam" valor={ev.falhou || 0} cor={ev.falhou ? 'var(--danger)' : 'var(--ink-3)'}
          nota={`${ev.pendente || 0} na fila · ${ev.processando || 0} em andamento · ${ev.feito || 0} feitos`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink">Casos por situação</h2>
          {Object.keys(c.casos).length === 0 ? <p className="text-xs text-ink-2">Nenhum caso ainda.</p> : (
            <ul className="space-y-1.5">
              {Object.entries(c.casos).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <li key={s} className="flex items-center justify-between text-sm"><Selo situacao={s} /><span className="tabular-nums text-ink">{n}</span></li>
              ))}
            </ul>
          )}
        </section>
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink">Eventos que falharam</h2>
          {c.falhas.length === 0 ? <p className="text-xs text-ink-2">Nenhuma falha. Evento que falha duas vezes aparece aqui para uma pessoa olhar.</p> : (
            <ul className="space-y-1.5 text-xs">
              {c.falhas.map(f => (
                <li key={f.id} className="flex flex-wrap gap-x-3 text-ink-2"><span className="font-medium text-ink">{EVENTO[f.tipo] || f.tipo}</span><span style={{ color: 'var(--danger)' }}>{f.erro}</span><span>{f.tentativas} tentativas</span></li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <section className="rounded-xl border border-line bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-ink">Últimos eventos</h2>
        {c.recentes.length === 0 ? <p className="text-xs text-ink-2">Nenhum evento ainda.</p> : (
          <ul className="divide-y divide-line text-xs">
            {c.recentes.map((e, i) => (
              <li key={i} className="flex flex-wrap gap-x-3 py-1.5 text-ink-2">
                <span className="w-40 text-ink">{EVENTO[e.tipo] || e.tipo}</span><span className="w-24">{SIT_EVENTO[e.situacao] || e.situacao}</span><span>{e.origem === 'tela' ? 'demonstração' : e.origem === 'relogio' ? 'relógio' : e.origem}</span>
                {e.erro && <span style={{ color: 'var(--warning)' }}>{e.erro}</span>}
                <span className="ml-auto tabular-nums">{fmtHora(e.criado_em)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

const CAMPOS_POLITICA = [
  ['desconto_max_pct', 'Desconto máximo (%)'], ['parcelas_max', 'Parcelas máximas'], ['parcela_min', 'Parcela mínima (R$)'],
  ['entrada_min_pct', 'Entrada mínima no parcelado (%)'], ['hora_inicio', 'Contato a partir de (h)'], ['hora_fim', 'Contato até (h)'],
  ['contatos_semana_max', 'Contatos por semana'], ['prazo_max_dias', 'Prazo máximo de promessa (dias)'],
  ['remarcacoes_max', 'Remarcações pelo agente'], ['prazo_confirmacao_dias', 'Prazo de confirmação do banco (dias úteis)'],
  ['dias_sem_resposta', 'Espera de resposta no atraso (dias úteis)'], ['percentual_controle', 'Grupo sorteado (%)'],
]
const DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']

function Politica({ empresa }) {
  const [d, setD] = useState(null)
  const [form, setForm] = useState(null)
  const [erro, setErro] = useState(null)
  const [aviso, setAviso] = useState('')
  const [salvando, setSalvando] = useState(false)
  function carregar() {
    setErro(null)
    return agentePoliticas(empresa).then(r => { setD(r); setForm({ ...(r.versoes.find(v => v.ativa)?.regras || r.demonstracao) }) }).catch(setErro)
  }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  async function salvar(e) {
    e.preventDefault(); setSalvando(true); setErro(null); setAviso('')
    try {
      const regras = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === 'dias_semana' ? v : Number(v)]))
      const r = await agenteSalvarPolitica(regras, empresa)
      setAviso(`Versão ${r.versao} ativa. O agente obedece a partir da próxima mensagem.`); await carregar()
    } catch (err) { setErro(err) } finally { setSalvando(false) }
  }
  if (!d || !form) return erro ? <ErroCarga erro={erro} onTentar={carregar} /> : <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
  const ativa = d.versoes.find(v => v.ativa)
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
      <form onSubmit={salvar} className="space-y-4 rounded-xl border border-line bg-surface p-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">{ativa ? `Política vigente: versão ${ativa.versao}` : 'Sem política: o agente só pode parar contato, registrar contestação e chamar uma pessoa'}</h2>
          <p className="mt-1 text-xs text-ink-2">O Auditor confere cada ação do agente contra estes limites e registra a regra e a versão. Salvar cria uma versão nova; as anteriores ficam guardadas.{!ativa && ' Os valores abaixo são de demonstração (fictícios).'}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {CAMPOS_POLITICA.map(([k, rot]) => (
            <label key={k} className="text-xs text-ink-2">{rot}
              <input value={form[k] ?? ''} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} inputMode="decimal"
                className="mt-1 w-full rounded-md border border-line bg-surface-2 px-2.5 py-1.5 text-sm text-ink focus:outline-none" />
            </label>
          ))}
        </div>
        <div className="text-xs text-ink-2">Dias de contato
          <div className="mt-1 flex flex-wrap gap-1.5">
            {DIAS.map((nome, i) => {
              const on = (form.dias_semana || []).includes(i)
              return <button type="button" key={i} onClick={() => setForm(f => ({ ...f, dias_semana: on ? f.dias_semana.filter(x => x !== i) : [...(f.dias_semana || []), i].sort() }))}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium ${on ? 'border-blue-500/30 bg-blue-500/15 text-blue-300' : 'border-line bg-raise-1 text-ink-2'}`}>{nome}</button>
            })}
          </div>
        </div>
        <ErroCarga erro={erro} compacto />
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={salvando} className="btn-primary flex items-center gap-1.5 disabled:opacity-50">{salvando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scale className="h-4 w-4" />} Salvar versão nova</button>
          {aviso && <span className="text-xs" style={{ color: 'var(--success)' }}>{aviso}</span>}
        </div>
      </form>
      <section className="rounded-xl border border-line bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-ink">Versões</h2>
        {d.versoes.length === 0 ? <p className="text-xs text-ink-2">Nenhuma ainda.</p> : (
          <ul className="space-y-2 text-xs">
            {d.versoes.map(v => (
              <li key={v.versao} className="rounded-lg border border-line p-2.5">
                <p className="font-semibold text-ink">Versão {v.versao}{v.ativa && <span className="ml-2" style={{ color: 'var(--success)' }}>vigente</span>}</p>
                <p className="mt-0.5 text-ink-2">desconto até {v.regras.desconto_max_pct}% · até {v.regras.parcelas_max}x · {v.regras.hora_inicio}h–{v.regras.hora_fim}h{v.criado_em ? ` · ${fmtHora(v.criado_em)}` : ''}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

const GRUPO = {
  contato:     { titulo: 'Precisa de contato', nota: 'Paga se for procurado: o agente manda a primeira mensagem e negocia.', cor: 'var(--accent-text, #60a5fa)' },
  so_lembrete: { titulo: 'Só lembrete', nota: 'Tende a pagar sozinho, ou já tem acordo: só lembrete de data.', cor: 'var(--success)' },
  nao_adianta: { titulo: 'Não adianta agora', nota: 'Chance muito baixa ou acordo quebrado há pouco: aguarda revisão.', cor: 'var(--ink-3)' },
  pessoa:      { titulo: 'Com uma pessoa', nota: 'Contestação, suspensão ou caso com a equipe.', cor: 'var(--warning)' },
}

function Plano({ empresa }) {
  const [p, setP] = useState(null)
  const [erro, setErro] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState('')
  function carregar() { setErro(null); return agentePlano(empresa).then(setP).catch(setErro) }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  async function aplicar() {
    setOcupado(true); setErro(null)
    try { const r = await agenteAplicarPlano(empresa); setAviso(`Plano aplicado: ${r.contagem.contato} na fila de contato, ${r.contagem.controle} no grupo sorteado.`); await carregar() }
    catch (e) { setErro(e) } finally { setOcupado(false) }
  }
  if (!p) return erro ? <ErroCarga erro={erro} onTentar={carregar} /> : <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={aplicar} disabled={ocupado} className="btn-primary flex items-center gap-1.5 disabled:opacity-50">
          {ocupado ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />} Aplicar o plano
        </button>
        <span className="text-xs text-ink-2">{aviso || 'Grava os grupos e manda a primeira mensagem (pronta, sem IA) para quem precisa de contato, dentro do horário da política.'}</span>
      </div>
      <ErroCarga erro={erro} onTentar={carregar} />
      <div className="rounded-xl border border-line bg-surface p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink"><Shuffle className="h-4 w-4 text-blue-400" /> Grupo sorteado: {p.contagem.controle} devedores ({p.percentual_controle}% da carteira)</p>
        <p className="mt-1 text-xs text-ink-2">Seguem no processo normal, sem o agente. Comparar quanto entrou em cada grupo, por real de dívida, mostra o efeito do agente na carteira da própria empresa. O sorteio é fixo por devedor.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Object.entries(GRUPO).map(([g, c]) => (
          <section key={g} className="rounded-xl border border-line bg-surface p-4" style={{ borderLeft: `3px solid ${c.cor}` }}>
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink">{c.titulo}</h2>
              <span className="text-lg font-bold tabular-nums text-ink">{p.contagem[g]}</span>
            </div>
            <p className="mt-0.5 text-xs text-ink-2">{c.nota}</p>
            <ul className="mt-3 space-y-1.5">
              {p.grupos[g].slice(0, 6).map(it => (
                <li key={it.id} className="text-xs"><span className="font-medium text-ink">{it.nome}</span> <span className="text-ink-2">· {fmtBRL(it.valor_divida)} · {it.motivo}</span>
                  {it.estrategia?.raciocinio && (
                    <p className="mt-0.5 pl-2 text-[11px] text-ink-2" style={{ borderLeft: `2px solid ${COR_AGENTE.Estrategista}` }}>
                      <span className="font-semibold" style={{ color: COR_AGENTE.Estrategista }}>IA</span>
                      {it.estrategia.oferta_inicial && <> · começa por {OFERTA_NOME[it.estrategia.oferta_inicial] || it.estrategia.oferta_inicial}</>}
                      {it.estrategia.concorda_bandit === false && <> · discorda do bandit</>} · {it.estrategia.raciocinio}
                    </p>
                  )}
                </li>
              ))}
              {p.grupos[g].length > 6 && <li className="text-xs text-ink-3">e mais {p.grupos[g].length - 6}</li>}
            </ul>
          </section>
        ))}
      </div>
      <p className="text-xs text-ink-3">Limiares de chance (70% e 5%) são escolha de projeto para a demonstração; entram na política quando houver dado de um piloto.</p>
    </div>
  )
}


const SELO_COR = { 'evidência': 'var(--success)', 'indício': '#f59e0b', 'sem evidência': '#94a3b8' }
const STATUS_REC = { proposta: 'proposta, esperando decisão', aprovada: 'aprovada: orienta o Estrategista', recusada: 'recusada' }
const pct = x => (x == null ? '—' : `${(x * 100).toFixed(1).replace('.', ',')}%`)
const pp = x => (x == null ? '—' : `${(x * 100).toFixed(1).replace('.', ',')} p.p.`)

function SeloEvidencia({ s }) {
  return <span className="rounded px-1.5 py-0.5 text-[11px] font-semibold" style={{ color: SELO_COR[s], border: `1px solid ${SELO_COR[s]}` }}>{s}</span>
}

export function Laboratorio({ empresa }) {
  const { isAdmin } = useAuth()
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [ocupado, setOcupado] = useState('')
  function carregar() { setErro(null); return agenteLaboratorio(empresa).then(setD).catch(setErro) }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  async function agir(fn, chave) {
    setOcupado(chave); setErro(null)
    try { await fn(); await carregar() } catch (err) { setErro(err) } finally { setOcupado('') }
  }
  if (erro && !d) return <ErroCarga erro={erro} />
  if (!d) return <div className="flex items-center gap-2 p-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> carregando…</div>
  const [atual, ...antigas] = d.recomendacoes
  const c = atual?.resultados?.comparacao
  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><FlaskConical className="h-4 w-4" style={{ color: COR_AGENTE.Cientista }} /> Laboratório: o Agente Cientista</h2>
            <p className="mt-1 max-w-3xl text-xs text-ink-2">Compara quem o agente procurou com o grupo sorteado que não foi procurado. As contas e o selo de evidência são feitos em código; a IA só interpreta e propõe. Uma recomendação só orienta o Estrategista depois que o administrador aprova, e nunca muda a política.</p>
          </div>
          {isAdmin && <button onClick={() => agir(() => agenteAnalisar(empresa), 'analisar')} disabled={!!ocupado}
            className="flex items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/15 px-3 py-1.5 text-sm font-medium text-blue-300 disabled:opacity-50">
            {ocupado === 'analisar' ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />} Gerar análise</button>}
        </div>
        <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">Na demonstração, a carteira e os pagamentos são fictícios: os números servem para mostrar o método, não como resultado.</p>
        {d.erro && <p className="mt-3 text-xs text-red-300">{d.erro}</p>}
        <ErroCarga erro={erro} compacto className="mt-3" />
        {!atual && !d.erro && <p className="mt-6 text-center text-sm text-ink-2">Nenhuma análise ainda.{isAdmin ? ' Clique em Gerar análise.' : ''}</p>}
      </div>
      {atual && (
        <div className="rounded-xl border border-line bg-surface p-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-2">
            <span className="font-semibold text-ink">Versão {atual.versao}</span> <SeloEvidencia s={atual.selo} />
            <span>· {STATUS_REC[atual.status]}</span><span>· {atual.origem === 'ia' ? 'texto da IA' : 'texto em código (sem IA)'}</span>
          </div>
          <p className="mt-2 text-sm text-ink">{atual.relatorio?.resumo}</p>
          {c && (
            <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
              <div className="rounded-md border border-line bg-raise-1 p-2"><p className="text-ink-3">Casos</p><p className="text-ink">agente {c.n.agente} · sorteado {c.n.sorteado}</p></div>
              <div className="rounded-md border border-line bg-raise-1 p-2"><p className="text-ink-3">Taxa de pagamento</p><p className="text-ink">{pct(c.taxa_pagamento.agente)} vs {pct(c.taxa_pagamento.sorteado)}</p><p className="text-ink-3">diferença {pp(c.taxa_pagamento.diferenca)} (IC 95%: {pp(c.taxa_pagamento.ic95[0])} a {pp(c.taxa_pagamento.ic95[1])})</p></div>
              <div className="rounded-md border border-line bg-raise-1 p-2"><p className="text-ink-3">Grupos comparáveis?</p><p className="text-ink">{c.composicao.comparaveis ? 'sim' : 'não: a composição difere'}</p></div>
            </div>
          )}
          <ol className="mt-3 space-y-2">
            {(atual.relatorio?.hipoteses || []).map((h, i) => (
              <li key={i} className="rounded-md border border-line p-2 text-xs">
                <p className="flex flex-wrap items-center gap-2 font-medium text-ink">{i + 1}. {h.hipotese} <SeloEvidencia s={h.selo} /></p>
                <p className="mt-1 text-ink-2">{h.resultado}</p>
                {h.condicoes && <p className="mt-0.5 text-ink-3">Vale para: {h.condicoes}</p>}
                {h.proximo_experimento && <p className="mt-0.5 text-ink-3">Próximo experimento: {h.proximo_experimento}</p>}
              </li>
            ))}
          </ol>
          <div className="mt-3 rounded-md p-3 text-sm" style={{ borderLeft: `3px solid ${COR_AGENTE.Cientista}`, background: 'rgba(250,204,21,0.06)' }}>
            <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: COR_AGENTE.Cientista }}>Recomendação para o Estrategista</p>
            <p className="mt-1 text-ink">{atual.texto}</p>
          </div>
          {isAdmin && atual.status === 'proposta' && (
            <div className="mt-3 flex gap-2">
              <button onClick={() => agir(() => agenteDecidirRecomendacao(atual.id, 'aprovada', empresa), 'aprovar')} disabled={!!ocupado}
                className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3 py-1.5 text-sm font-medium text-emerald-300 disabled:opacity-50">Aprovar</button>
              <button onClick={() => agir(() => agenteDecidirRecomendacao(atual.id, 'recusada', empresa), 'recusar')} disabled={!!ocupado}
                className="rounded-md border border-line bg-raise-1 px-3 py-1.5 text-sm font-medium text-ink-2 disabled:opacity-50">Recusar</button>
            </div>
          )}
        </div>
      )}
      {!!antigas.length && (
        <div className="rounded-xl border border-line bg-surface p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">Versões anteriores</p>
          <ul className="mt-2 space-y-1 text-xs">
            {antigas.map(r => <li key={r.id} className="flex flex-wrap items-center gap-2 text-ink-2"><span className="text-ink">v{r.versao}</span> <SeloEvidencia s={r.selo} /> {STATUS_REC[r.status]} · {r.texto}</li>)}
          </ul>
        </div>
      )}
    </section>
  )
}

function Agenda({ empresa }) {
  const { isAdmin } = useAuth()
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [escolha, setEscolha] = useState({})
  const [salvando, setSalvando] = useState('')
  const [aviso, setAviso] = useState('')
  function carregar() { setErro(null); return agenteAgenda(empresa).then(setD).catch(setErro) }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps

  async function atribuir(item) {
    const op = escolha[item.id]
    if (!op) return
    setSalvando(item.id); setErro(null); setAviso('')
    try {
      const r = await agenteAtribuir(item.id, op, empresa)
      setAviso(`${item.nome || 'Atendimento'}: agora com ${r.operador.nome}. Aparece na Agenda dele.`)
      await carregar()
    } catch (err) { setErro(err) } finally { setSalvando('') }
  }

  if (erro && !d) return <ErroCarga erro={erro} />
  if (!d) return <div className="flex items-center gap-2 p-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> carregando…</div>
  const porDia = {}
  for (const i of d.itens) (porDia[i.data] ||= []).push(i)
  return (
    <section className="rounded-xl border border-line bg-surface p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><CalendarClock className="h-4 w-4 text-blue-400" /> Agenda dos agentes</h2>
      <p className="mt-1 text-xs text-ink-2">Retornos, atendimentos com pessoa e conferências marcados pelos agentes. Atendimento de devedor sem responsável fica aqui até o administrador escolher quem atende.</p>
      {aviso && <p className="mt-3 text-xs" style={{ color: 'var(--success)' }}>{aviso}</p>}
      <ErroCarga erro={erro} compacto className="mt-3" />
      {!d.itens.length && <p className="mt-6 text-center text-sm text-ink-2">Nada marcado pelos agentes ainda.</p>}
      <div className="mt-4 space-y-4">
        {Object.entries(porDia).map(([dia, itens]) => (
          <div key={dia}>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-2">{fmtData(dia)}</p>
            <ul className="space-y-1.5">
              {itens.map(i => (
                <li key={i.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
                  <span className="w-12 tabular-nums text-ink-2">{i.hora || '—'}</span>
                  <span className="font-medium text-ink">{i.nome || 'Devedor'}</span>
                  <span className="rounded border border-line px-1.5 py-px text-[11px] text-ink-2">{TIPO_AGENDA[i.tipo] || i.tipo}</span>
                  <span className="min-w-0 flex-1 truncate text-xs text-ink-2" title={i.observacao}>{i.observacao}</span>
                  {i.a_definir ? (
                    isAdmin ? (
                      <span className="flex items-center gap-1.5">
                        <select value={escolha[i.id] || ''} onChange={e => setEscolha(s => ({ ...s, [i.id]: e.target.value }))} aria-label="Operador"
                          className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink focus:outline-none [color-scheme:dark]">
                          <option value="">Quem atende?</option>
                          {d.operadores.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
                        </select>
                        <button onClick={() => atribuir(i)} disabled={!escolha[i.id] || salvando === i.id}
                          className="rounded-md border border-line bg-raise-1 px-2 py-1 text-xs font-medium text-ink hover:bg-raise-2 disabled:opacity-50">Atribuir</button>
                      </span>
                    ) : <span className="text-xs" style={{ color: 'var(--warning)' }}>esperando o administrador</span>
                  ) : <span className="text-xs text-ink-2">{i.operador_nome}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {isAdmin && !d.operadores.length && d.itens.some(i => i.a_definir) && (
        <p className="mt-3 text-xs" style={{ color: 'var(--warning)' }}>Nenhum operador ativo nesta empresa: cadastre em Usuários para poder atribuir.</p>
      )}
    </section>
  )
}

const NOMES_AGENTES = ['Triagem', 'Negociador', 'Supervisor', 'Estrategista', 'Cientista', 'Acompanhamento', 'Orquestrador', 'Auditor']

function Numero({ rotulo, valor, detalhe, barra }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-xs font-medium text-ink-2">{rotulo}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-ink">{valor}</p>
      {barra != null && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-raise-2"><div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(100, barra * 100)}%` }} /></div>}
      {detalhe && <p className="mt-1 text-xs text-ink-3">{detalhe}</p>}
    </div>
  )
}

function AoVivo({ empresa }) {
  const navigate = useNavigate()
  const { empresaConfig } = useAuth()
  const [r, setR] = useState(null)
  useEffect(() => {
    let vivo = true
    const carregar = () => agenteAgentes(empresa).then(x => vivo && setR(x)).catch(() => {})
    carregar()
    const t = setInterval(() => { if (!document.hidden) carregar() }, 15000)
    return () => { vivo = false; clearInterval(t) }
  }, [empresa])
  const n = r?.numeros
  const usd = v => `US$ ${Number(v || 0).toFixed(2).replace('.', ',')}`
  const abrir = nome => navigate(`/agente/${encodeURIComponent(nome)}`)
  const porNome = Object.fromEntries((r?.agentes || []).map(a => [a.nome, a]))
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Numero rotulo="Conversas (24 h)" valor={n ? n.conversas : '—'} detalhe={n ? `${n.respostas} respostas` : null} />
        <Numero rotulo="Acordos (24 h)" valor={n ? n.acordos : '—'} />
        <Numero rotulo="Bloqueios (24 h)" valor={n ? n.bloqueios : '—'} detalhe="Auditor e travas" />
        <Numero rotulo="Gasto de IA hoje" valor={n ? usd(n.custo_hoje_usd) : '—'} detalhe={n ? `teto ${usd(n.teto_dia_usd)}` : null}
          barra={n && n.teto_dia_usd ? n.custo_hoje_usd / n.teto_dia_usd : null} />
      </div>
      <EscritorioAgentes empresa={empresa} cores={COR_AGENTE} nomeEmpresa={empresaConfig?.nome_exibicao} resumos={r?.agentes} onPerfil={abrir} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {NOMES_AGENTES.map(nome => {
          const a = porNome[nome]
          const cor = COR_AGENTE[nome]
          const estado = a?.papel ? (a.ia_ligada ? 'IA' : 'IA desligada') : 'Código'
          return (
            <button key={nome} onClick={() => abrir(nome)}
              className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left transition-colors hover:border-blue-500/40">
              <div className="shrink-0 rounded-lg bg-raise-1 px-1 pt-1"><Retrato nome={nome} cor={cor} tamanho={30} /></div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold" style={{ color: cor }}>{nome}</p>
                <p className="text-xs text-ink-2">{a ? `${a.acoes} ações` : '—'} · <span className="text-ink-3">{estado}</span></p>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function Regras({ empresa }) {
  return (
    <div className="space-y-5">
      <Politica empresa={empresa} />
      <Plano empresa={empresa} />
      <Central empresa={empresa} />
    </div>
  )
}

export default function Agente() {
  const { token, isComando } = useAuth()
  const [params, setParams] = useSearchParams()
  const aba = params.get('aba') || 'aovivo'
  const setAba = k => setParams(k === 'aovivo' ? {} : { aba: k }, { replace: true })
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  useEffect(() => {
    if (isComando) listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])
  const empresa = isComando ? alvo : undefined
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink"><Bot className="h-5 w-5 text-blue-400" /> Agentes</h1>
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </div>
        <div className="flex flex-wrap gap-1 border-b border-line" role="tablist">
          {[['aovivo', 'Ao vivo'], ['conversas', 'Conversas'], ['agenda', 'Agenda'], ['regras', 'Regras']].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${aba === k ? 'border-blue-500 text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
              {l}
            </button>
          ))}
        </div>
        {isComando && !alvo ? (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa.</div>
        ) : aba === 'conversas' ? <Conversa empresa={empresa} />
          : aba === 'agenda' ? <Agenda empresa={empresa} />
          : aba === 'regras' ? <Regras empresa={empresa} />
          : <AoVivo empresa={empresa} />}
      </div>
    </AppShell>
  )
}
