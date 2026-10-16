// Agentes: a conversa de um caso (com o porquê de cada passo) e a Central de
// orquestração. Na demonstração, quem está na tela escreve como o devedor.
// Regras em backend/agente/ (docs/PLANO_EXECUCAO_AGENTES.md).
import { useEffect, useRef, useState } from 'react'
import { Bot, Send, Search, Loader2, Activity, ShieldCheck, AlertTriangle, Power, UserRound, Coins, ListChecks, Landmark, Clock } from 'lucide-react'
import AppShell from '../components/AppShell'
import ErroCarga from '../components/ErroCarga'
import { useAuth } from '../context/AuthContext'
import { agenteDevedores, agenteCaso, agenteSimularMensagem, agenteSimularPagamento, agenteCentral, agenteRelogio, listarEmpresas } from '../api'

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
            <span className="font-medium text-ink">{nomeNo(p.no)}</span>
            {p.regra && <span className="rounded bg-raise-2 px-1.5 py-px font-mono text-[11px] text-ink-2">{p.regra}{p.versao_politica ? ` · v${p.versao_politica}` : ''}</span>}
            {p.resultado === 'bloqueado' && <span style={{ color: 'var(--warning)' }}>bloqueado</span>}
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

export default function Agente() {
  const { token, isComando } = useAuth()
  const [aba, setAba] = useState('conversa')
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  useEffect(() => {
    if (isComando) listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])
  const empresa = isComando ? alvo : undefined
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink"><Bot className="h-5 w-5 text-blue-400" /> Agente</h1>
            <p className="mt-1 text-sm text-ink-2">O Mizan decide, mede e prova; o agente executa dentro das regras da empresa. Na demonstração, você escreve como o devedor.</p>
          </div>
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </div>
        <div className="flex gap-1.5" role="tablist">
          {[['conversa', 'Conversa', Bot], ['central', 'Central de orquestração', Activity]].map(([k, l, I]) => (
            <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium ${aba === k ? 'border-blue-500/30 bg-blue-500/15 text-blue-300' : 'border-line bg-raise-1 text-ink-2 hover:text-ink'}`}>
              <I className="h-4 w-4" /> {l}
            </button>
          ))}
        </div>
        {isComando && !alvo ? (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa.</div>
        ) : aba === 'conversa' ? <Conversa empresa={empresa} /> : <Central empresa={empresa} />}
      </div>
    </AppShell>
  )
}
