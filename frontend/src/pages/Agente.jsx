// Agentes: a conversa de um caso (com o porquê de cada passo) e a Central de
// orquestração. Na demonstração, quem está na tela escreve como o devedor.
// Regras em backend/agente/ (docs/PLANO_EXECUCAO_AGENTES.md).
import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { useAoMudarNoServidor } from '../components/useMudancasDoServidor'
import { Bot, Send, Search, Loader2, Activity, ShieldCheck, AlertTriangle, Power, UserRound, Coins, Landmark, Clock, Shuffle, CalendarDays, Scale, Hand, Undo2, CalendarClock, BookOpen, FlaskConical, Headset, Unlink } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import ErroCarga from '../components/ErroCarga'
import AprendizadoCientista from '../components/AprendizadoCientista'
import StatCard from '../components/StatCard'
import { KpiBento } from '../components/ui/stats-bento'
import EscritorioAgentes from '../components/EscritorioAgentes'
import useEscritorio from '../components/escritorio/useEscritorio'
import FichaPassagem, { SeloPrioridade } from '../components/FichaPassagem'
import { useAuth } from '../context/AuthContext'
import { agenteDevedores, agenteCaso, agenteSimularMensagem, agenteRetomar, agenteSimularPagamento, agenteCentral, agenteRelogio, agentePlano, agenteAplicarPlano, agentePoliticas, agenteSalvarPolitica, agenteControle, agenteTelegramConvite, agenteTelegramDesligar, agenteAtendimentos, agenteResponderComoPessoa, agenteSinal, agenteAgenda, agenteAtribuir, agenteLaboratorio, agenteAnalisar, agenteDecidirRecomendacao, listarEmpresas } from '../api'

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
const NOME_LOG_AGENTE = { triagem: 'Triagem', negociador: 'Negociador', estrategista: 'Estrategista',
  acompanhamento: 'Acompanhamento', supervisor: 'Supervisor', cientista: 'Cientista', auditor: 'Auditor',
  orquestrador: 'Orquestrador', codigo: 'Travas', ferramenta: 'Ferramenta' }
const NOME_NO = {
  receber: 'Recebeu a mensagem', triagem: 'Triagem: entendeu a intenção', negociar: 'Negociador', enviar: 'Enviou a resposta',
  auditor: 'Auditor', guardrails: 'Travas do texto', resposta_fixa: 'Resposta fixa (sem IA)', suspender: 'Suspendeu a cobrança',
  contestar: 'Abriu contestação', transferir: 'Passou para uma pessoa', avisar_equipe: 'Avisou a equipe', erro: 'Nó de erro',
  conferir: 'Acompanhamento: conferiu a data', decisao: 'Decisão do Acompanhamento', lembrar: 'Lembrete (mensagem pronta)',
  cobrar_atraso: 'Procurou pelo atraso', encerrar: 'Sem resposta: passou para uma pessoa', registrar: 'Pagamento registrado',
  consulta_juridica: 'Consulta jurídica interna', pedido_titular: 'Pedido sobre os dados pessoais',
  transcrever_audio: 'Transcreveu o áudio do devedor',
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
        {passos.map((p, i) => {
          // Também protege a leitura de registros antigos, quando IaOcupada
          // ainda era persistido como erro antes de a nova tentativa.
          const aguardandoNovaTentativa = p.resultado === 'aguardando' || p.detalhe?.codigo === 'ia_ocupada' || p.detalhe?.erro === 'IaOcupada'
          const resultado = aguardandoNovaTentativa ? 'aguardando' : p.resultado
          return (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded-lg px-2 py-1.5 text-xs hover:bg-raise-1">
            <span className="h-2 w-2 shrink-0 translate-y-[-1px] rounded-full" style={{ background: resultado === 'aguardando' ? 'var(--warning)' : COR_RES[resultado] || 'var(--ink-3)' }} />
            {p.quem && <span className="rounded px-1.5 py-px text-[11px] font-semibold" style={{ color: COR_AGENTE[p.quem] || 'var(--ink-2)', background: 'color-mix(in srgb, currentColor 14%, transparent)' }}>{p.quem}</span>}
            <span className="font-medium text-ink">{aguardandoNovaTentativa ? 'A resposta será tentada novamente' : p.explicacao || nomeNo(p.no)}</span>
            {p.regra && <span className="rounded bg-raise-2 px-1.5 py-px font-mono text-[11px] text-ink-2">{p.regra}{p.versao_politica ? ` · v${p.versao_politica}` : ''}</span>}
            {p.detalhe?.fontes?.map((f) => (
              <span key={f} className="rounded border border-line px-1.5 py-px text-[11px] text-ink" title="Fonte consultada na base de conhecimento">Fonte: {f}</span>
            ))}
            {p.detalhe?.certeza === false && <span style={{ color: 'var(--warning)' }}>sem resposta segura na base</span>}
            {p.resultado === 'bloqueado' && !p.explicacao && <span style={{ color: 'var(--warning)' }}>bloqueado</span>}
            {resultado === 'aguardando' && <span style={{ color: 'var(--warning)' }}>nova tentativa agendada</span>}
            {resultado === 'erro' && <span style={{ color: 'var(--danger)' }}>erro{p.detalhe?.erro ? `: ${p.detalhe.erro}` : ''}</span>}
            <span className="ml-auto tabular-nums text-ink-3">{p.duracao_ms} ms{p.tokens_entrada ? ` · ${p.tokens_entrada + p.tokens_saida} tokens` : ''}</span>
          </li>
          )
        })}
      </ol>
      <p className="border-t border-line pt-2 text-xs text-ink-2">{passos.length} passos · {tokens} tokens · {fmtUSD(custo)}</p>
    </div>
  )
}

// O que aconteceu com uma mensagem da equipe (ou um aviso) a caminho do Telegram do devedor.
const ENTREGA = {
  entregue: ['ok', 'Entregue no Telegram do devedor.'],
  sem_telegram: ['info', 'Registrado no caso. O devedor não tem Telegram ligado: gere um convite para ele receber.'],
  nao_configurado: ['aviso', 'Registrado no caso, mas o Telegram não está configurado no servidor.'],
  falhou: ['aviso', 'Registrado no caso, mas não chegou ao Telegram (falha de rede). Tente enviar de novo.'],
  bloqueado: ['aviso', 'O devedor bloqueou o bot: a mensagem ficou só no caso. Quando ele voltar a escrever, o canal reabre.'],
}

const fmtDiaHora = v => (v ? new Date(v).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '')

// Estado do Telegram do caso, num selo só.
function SeloTelegram({ tg }) {
  if (!tg?.configurado) return null
  const [cor, texto, dica] = tg.bloqueado
    ? ['var(--warning)', 'Telegram: bloqueou o bot', 'O devedor bloqueou o bot. Nada é enviado até ele voltar a escrever.']
    : tg.ligado
      ? ['var(--success)', 'Telegram ligado', `Ligado desde ${fmtDiaHora(tg.desde)}`]
      : tg.convite_pendente_ate
        ? ['var(--ink-2)', `Convite enviado (vale até ${new Date(tg.convite_pendente_ate).toLocaleDateString('pt-BR')})`, 'O devedor ainda não abriu o link.']
        : ['var(--ink-3)', 'Sem Telegram', 'Gere um convite para o devedor conversar pelo Telegram.']
  return <span title={dica} className="rounded-full border px-2 py-0.5 text-xs font-medium" style={{ color: cor, borderColor: cor }}>{texto}</span>
}

// Casos com a equipe, quem espera resposta primeiro. Atualiza sozinho.
function Atendimentos({ empresa, escolhido, onEscolher }) {
  const [itens, setItens] = useState([])
  useEffect(() => {
    let vivo = true
    const ler = () => { if (!document.hidden) agenteAtendimentos(empresa).then(d => vivo && setItens(d.itens || [])).catch(() => {}) }
    ler()
    const t = setInterval(ler, 4000)
    return () => { vivo = false; clearInterval(t) }
  }, [empresa])
  if (!itens.length) return null
  const esperando = itens.filter(i => i.esperando).length
  return (
    <div className="mb-3 rounded-lg border border-line bg-raise-1 p-2">
      <p className="mb-1 flex items-center gap-1.5 px-1 text-xs font-semibold text-ink">
        <Headset className="h-3.5 w-3.5 text-accent-text" /> Com a equipe
        {esperando > 0 && <span className="ml-auto rounded-full px-1.5 text-[11px] font-bold" style={{ color: 'var(--warning)', border: '1px solid var(--warning)' }}>{esperando} esperando</span>}
      </p>
      <ul className="max-h-40 space-y-0.5 overflow-y-auto">
        {itens.map(i => (
          <li key={i.predicao_id}>
            <button onClick={() => onEscolher({ id: i.predicao_id, nome: i.nome })}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${escolhido?.id === i.predicao_id ? 'bg-blue-500/15' : 'hover:bg-raise-2'}`}>
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: i.esperando ? 'var(--warning)' : 'var(--ink-4)' }} />
              <span className="min-w-0 flex-1 truncate text-ink">{i.nome}</span>
              <span className="shrink-0 text-[11px] text-ink-3" title={i.esperando ? 'Esperando resposta da equipe desde este horário' : 'A equipe já respondeu'}>{i.esperando ? fmtHora(i.desde) : 'respondido'}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

// `fixo` ({ id, nome }): a conversa de um devedor só, dentro da pasta do cliente
// (sem a lista de devedores ao lado).
export function Conversa({ empresa, fixo = null }) {
  const [params] = useSearchParams()
  const [busca, setBusca] = useState('')
  const [devedores, setDevedores] = useState([])
  // Vindo de uma pasta de devedor (?caso=<id>&nome=<nome>): abre direto no caso.
  const [escolhido, setEscolhido] = useState(() => fixo ? fixo : params.get('caso') ? { id: params.get('caso'), nome: params.get('nome') || 'Devedor' } : null)
  // Na pasta, o nome chega depois (o servidor confirma): acompanha o devedor fixo.
  useEffect(() => { if (fixo) setEscolhido(fixo) }, [fixo?.id, fixo?.nome]) // eslint-disable-line react-hooks/exhaustive-deps
  const [dados, setDados] = useState(null)
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [valorPago, setValorPago] = useState('')
  const [mostrarTodas, setMostrarTodas] = useState(false)
  const fim = useRef(null)
  const aguardando = ['pendente', 'processando'].includes(dados?.evento?.situacao)
  const quandoRetomar = dados?.evento?.situacao === 'pendente' ? Date.parse(dados.evento.disponivel_em || '') : NaN

  const [convite, setConvite] = useState(null)
  const [entrega, setEntrega] = useState(null)       // [tipo, texto] da última mensagem da equipe
  const [copiado, setCopiado] = useState(false)
  useEffect(() => { setConvite(null); setEntrega(null) }, [escolhido])
  const tg = dados?.telegram
  async function gerarConvite() {
    // Um link vale para UM Telegram. Gerar outro desliga o anterior: confirma antes.
    if (tg?.ligado && !window.confirm('Este caso já tem um Telegram ligado. Um novo convite liga o caso ao Telegram de quem abrir o link, e o atual deixa de receber. Gerar mesmo assim?')) return
    if (!tg?.ligado && tg?.convite_pendente_ate && !window.confirm('Já existe um convite que o devedor ainda não abriu. O novo link substitui o anterior, que deixa de funcionar. Gerar outro?')) return
    setEnviando(true); setErro(null); setCopiado(false)
    try {
      setConvite(await agenteTelegramConvite(escolhido.id, empresa))
      setDados(await agenteCaso(escolhido.id, empresa))
    } catch (err) { setErro(err) } finally { setEnviando(false) }
  }

  async function desligarTelegram() {
    if (!window.confirm('Desligar o Telegram deste caso? O devedor para de receber mensagens por lá e o link deixa de valer.')) return
    setEnviando(true); setErro(null)
    try { setDados(await agenteTelegramDesligar(escolhido.id, empresa)); setConvite(null) } catch (err) { setErro(err) } finally { setEnviando(false) }
  }

  async function controlar(acao) {
    setEnviando(true); setErro(null); setEntrega(null)
    try {
      const r = await agenteControle(escolhido.id, acao, empresa)
      setDados(r)
      if (r.entrega && r.entrega !== 'sem_telegram') {
        const [tipo, txt] = ENTREGA[r.entrega] || ['info', '']
        setEntrega([tipo, r.entrega === 'entregue'
          ? (acao === 'assumir' ? 'O devedor foi avisado no Telegram de que agora fala com uma pessoa.' : 'O devedor foi avisado no Telegram de que o assistente voltou.')
          : `Aviso ao devedor: ${txt}`])
      }
    } catch (err) { setErro(err) } finally { setEnviando(false) }
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
    let vivo = true
    setDados(null); setErro(null)
    agenteCaso(escolhido.id, empresa).then(d => vivo && setDados(d)).catch(e => vivo && setErro(e))
    return () => { vivo = false }
  }, [escolhido, empresa])

  useEffect(() => {
    if (!escolhido || !aguardando) return
    let vivo = true, ocupado = false
    const atualizar = async () => {
      if (ocupado || document.hidden) return
      ocupado = true
      try {
        // Se a fila já liberou o evento, a própria conversa o retoma. Assim a
        // resposta não espera o próximo ciclo do servidor para aparecer.
        const d = Number.isFinite(quandoRetomar) && Date.now() >= quandoRetomar
          ? await agenteRetomar(escolhido.id, empresa)
          : await agenteCaso(escolhido.id, empresa)
        if (vivo) { setDados(d); setErro(null) }
      } catch (e) { if (vivo) setErro(e) }
      finally { ocupado = false }
    }
    const t = setInterval(atualizar, 5000)
    return () => { vivo = false; clearInterval(t) }
  }, [escolhido, empresa, aguardando, quandoRetomar])

  // O devedor pode escrever pelo Telegram a qualquer hora: a cada 1 segundo a tela pergunta, de forma
  // barata, se o caso mudou, e só então recarrega a conversa. Parada com a aba escondida ou enviando.
  const sinalVisto = useRef(null)
  useEffect(() => { sinalVisto.current = null }, [escolhido])
  useEffect(() => {
    if (!escolhido) return
    let vivo = true
    const t = setInterval(async () => {
      if (document.hidden || enviando) return
      try {
        let sinal
        try {
          sinal = (await agenteSinal(escolhido.id, empresa)).sinal
        } catch {
          // Servidor ainda sem a rota leve (versão antiga): cai no caso inteiro, que também mostra o que chegou.
          const inteiro = await agenteCaso(escolhido.id, empresa)
          if (!vivo) return
          const ms = inteiro.mensagens || []
          sinal = `${ms.length}:${ms.length ? ms[ms.length - 1].criado_em : ''}:${inteiro.caso?.situacao}`
          if (sinalVisto.current !== null && sinal !== sinalVisto.current) setDados(inteiro)
          sinalVisto.current = sinalVisto.current === null ? sinal : sinal
          return
        }
        if (!vivo) return
        if (sinalVisto.current === null) { sinalVisto.current = sinal; return }
        if (sinal && sinal !== sinalVisto.current) {
          sinalVisto.current = sinal
          const novo = await agenteCaso(escolhido.id, empresa)
          if (vivo) setDados(novo)
        }
      } catch { /* a próxima volta tenta de novo */ }
    }, 1000)
    return () => { vivo = false; clearInterval(t) }
  }, [escolhido, empresa, enviando])

  useEffect(() => { fim.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [dados?.mensagens?.length])

  const comPessoa = dados?.caso?.situacao === 'com_pessoa'
  // Com o devedor no Telegram, a tela só acompanha: escrever por ele aqui criaria outra conversa.
  const soAcompanha = !comPessoa && !!dados?.telegram?.ligado
  const desde = Date.parse(dados?.caso?.conversa_desde || '')
  const iRecomeco = Number.isFinite(desde) ? (dados?.mensagens || []).findIndex(m => Date.parse(m.criado_em) >= desde) : -1

  async function enviar(e) {
    e.preventDefault()
    if (!texto.trim() || enviando) return
    setEnviando(true); setErro(null)
    const mensagem = texto
    setTexto('')
    try {
      // Com o caso na mão da equipe, quem escreve é a pessoa (e chega no Telegram do devedor).
      setEntrega(null)
      if (comPessoa) {
        const r = await agenteResponderComoPessoa(escolhido.id, mensagem, empresa)
        setDados(r)
        setEntrega(ENTREGA[r.entrega] || null)
        if (r.entrega === 'falhou') setTexto(mensagem)          // fica na caixa para tentar de novo
      } else setDados(await agenteSimularMensagem(escolhido.id, mensagem, empresa))
    } catch (err) { setErro(err); setTexto(mensagem) } finally { setEnviando(false) }
  }

  const mensagens = dados?.mensagens || []
  const ultimaDoAgente = (() => { for (let i = mensagens.length - 1; i >= 0; i--) { const m = mensagens[i]; if (m.direcao !== 'entrada' && m.trace_id !== 'pessoa' && m.trace_id !== 'aviso') return i } return -1 })()
  const ofertas = (dados?.caso?.negociacao?.eventos || []).filter(e => e.tipo === 'oferta_apresentada').length
  const nomeCliente = (escolhido?.nome || 'o cliente').split(' ')[0]
  const inicio = mostrarTodas ? 0 : Math.max(0, mensagens.length - LIMITE_MENSAGENS)

  return (
    <div className={`grid items-start gap-5 ${fixo ? 'lg:grid-cols-[minmax(0,1fr)_300px]' : 'lg:grid-cols-[280px_minmax(0,1fr)_300px]'}`}>
      {!fixo && <section className="rounded-2xl border border-line bg-surface p-3">
        <Atendimentos empresa={empresa} escolhido={escolhido} onEscolher={setEscolhido} />
        <label className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2">
          <Search className="h-4 w-4 text-ink-3" />
          <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar devedor…" aria-label="Buscar devedor"
            className="w-full bg-transparent text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
        </label>
        <ul className="mt-2 max-h-[60vh] space-y-0.5 overflow-y-auto">
          {devedores.map(d => (
            <li key={d.id}>
              <button onClick={() => setEscolhido(d)}
                className={`w-full rounded-xl px-3 py-2 text-left transition-colors ${escolhido?.id === d.id ? 'bg-[var(--royal-soft)]' : 'hover:bg-raise-1'}`}>
                <p className="truncate text-sm font-medium text-ink">{d.nome}</p>
                <p className="text-xs text-ink-2">{fmtBRL(d.valor_divida)} · {d.dias_em_atraso} dias</p>
              </button>
            </li>
          ))}
          {!devedores.length && <li className="px-2 py-6 text-center text-xs text-ink-2">Nenhum devedor na carteira mais recente.</li>}
        </ul>
      </section>}

      <section aria-label="Mensagens" className="flex h-[760px] max-h-[82vh] min-h-[480px] flex-col overflow-hidden rounded-2xl border border-line bg-surface">
        {!escolhido ? (
          <div className="m-auto max-w-sm p-6 text-center text-sm text-ink-2">
            <Bot className="mx-auto mb-3 h-8 w-8 opacity-60" />
            Escolha um devedor e escreva como se fosse ele. O agente responde pelas regras da empresa, e cada passo aparece ao lado.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-line px-5 py-3 text-[13px] text-ink-2">
              <span className="flex flex-wrap items-center gap-x-3.5 gap-y-1" aria-label="Legenda das cores">
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[4px] border border-[var(--border)] bg-[var(--raised)]" aria-hidden="true" />Cliente</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[4px] border border-[var(--border-strong)] bg-[var(--royal-soft)]" aria-hidden="true" />Agente</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[4px] border border-[var(--success)] bg-[var(--success-soft)]" aria-hidden="true" />Consultor da equipe (humano)</span>
              </span>
              <span className="tabular-nums">{mensagens.length} {mensagens.length === 1 ? 'mensagem' : 'mensagens'}{inicio > 0 ? ` · mostrando as últimas ${mensagens.length - inicio}` : ''}</span>
            </div>
            {!fixo && (
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-2">
                <UserRound className="h-4 w-4 text-ink-2" aria-hidden="true" />
                <p className="text-sm font-semibold text-ink">{escolhido.nome}</p>
                <Selo situacao={dados?.caso?.situacao} />
              </div>
            )}
            {convite && (
              <div className="flex flex-wrap items-center gap-2 border-b border-line bg-raise-1 px-5 py-2 text-xs text-ink-2" role="status">
                {convite.configurado && convite.link ? (
                  <>
                    <span>Envie este link só a este devedor. Ele liga um Telegram (o primeiro que abrir) e vale até {new Date(convite.expira_em).toLocaleDateString('pt-BR')}:</span>
                    <input readOnly value={convite.link} onFocus={e => e.target.select()} aria-label="Link do convite"
                      className="min-w-[16rem] flex-1 rounded-lg border border-line bg-surface-2 px-2 py-1 text-ink" />
                    <button onClick={() => { navigator.clipboard?.writeText(convite.link); setCopiado(true) }} className="btn-secondary btn-sm">{copiado ? 'Copiado' : 'Copiar'}</button>
                  </>
                ) : <span>O Telegram ainda não está configurado no servidor (variáveis TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET e TELEGRAM_BOT_USERNAME).</span>}
              </div>
            )}
            {!enviando && aguardando && <p role="status" className="border-b border-line px-5 py-2 text-xs text-ink-2">
              {dados.evento.situacao === 'processando' ? 'O agente está processando a mensagem.' : 'O agente tentará responder novamente automaticamente. A mensagem permanece na fila.'}
            </p>}
            {tg?.tentativa_outro_chat_em && (
              <p role="status" className="flex items-start gap-1.5 border-b border-line px-5 py-2 text-xs" style={{ color: 'var(--warning)' }}>
                <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />
                Em {fmtDiaHora(tg.tentativa_outro_chat_em)} alguém tentou abrir o link deste caso em outro Telegram e não conseguiu. Cada pessoa precisa do próprio link.
              </p>
            )}
            <div role="log" aria-label="Histórico da conversa" className="flex flex-1 flex-col gap-3.5 overflow-y-auto px-5 pb-5 pt-4 sm:px-7">
              {inicio > 0 && (
                <button type="button" onClick={() => setMostrarTodas(true)}
                  className="self-center rounded-full border border-line px-3.5 py-1.5 text-[13px] font-semibold text-accent-text hover:border-[var(--border-strong)]">
                  ↑ Carregar {inicio} {inicio === 1 ? 'mensagem anterior' : 'mensagens anteriores'}
                </button>
              )}
              {dados && !mensagens.length && <p className="m-auto text-sm text-ink-2">Nenhuma mensagem ainda.</p>}
              {mensagens.map((m, i) => {
                if (i < inicio) return null
                const quem = m.direcao === 'entrada' ? 'devedor' : m.trace_id === 'pessoa' ? 'atendente' : m.trace_id === 'aviso' ? 'aviso' : 'assistente'
                const bolha = {
                  devedor: 'rounded-[18px_18px_18px_6px] border border-[var(--border)] bg-[var(--raised)] text-ink',
                  atendente: 'rounded-[18px_18px_6px_18px] border border-[var(--success)] bg-[var(--success-soft)] text-ink',
                  aviso: 'rounded-[18px_18px_6px_18px] border border-dashed border-line text-ink-2',
                  assistente: 'rounded-[18px_18px_6px_18px] border border-[var(--border-strong)] bg-[var(--royal-soft)] text-ink',
                }[quem]
                const autor = { devedor: nomeCliente, atendente: '● Consultor da equipe', aviso: 'Aviso automático', assistente: 'Agente' }[quem]
                const dia = diaDe(m.criado_em)
                const diaAnt = i > inicio ? diaDe(mensagens[i - 1].criado_em) : null
                return (
                  <Fragment key={i}>
                    {dia && dia !== diaAnt && <span className="my-1 self-center rounded-full bg-[var(--raised)] px-3 py-1 text-xs text-ink-2">{dia}</span>}
                    {i === iRecomeco && i > 0 && (
                      <div className="flex items-center gap-2 py-1 text-[11px] text-ink-3" role="separator">
                        <span className="h-px flex-1 bg-line" /> Telegram ligado: a conversa com o devedor recomeça aqui <span className="h-px flex-1 bg-line" />
                      </div>
                    )}
                    <div className={`flex flex-col gap-1 ${quem === 'devedor' ? 'items-start' : 'items-end'}`}>
                      <span className="text-xs text-ink-3">{autor} · {fmtHora(m.criado_em)}</span>
                      <div className={`max-w-[min(560px,88%)] px-3.5 py-3 text-[15px] leading-relaxed ${bolha}`}>
                        <p className="whitespace-pre-wrap break-words">{m.texto}</p>
                      </div>
                      {i === ultimaDoAgente && dados?.passos?.length > 0 && <PorQue passos={dados.passos} />}
                    </div>
                  </Fragment>
                )
              })}
              {!enviando && !aguardando && !comPessoa && dados?.silencio && (
                <div className="flex justify-center">
                  <p className="flex max-w-[90%] items-start gap-1.5 rounded-xl border px-3 py-1.5 text-xs" style={{ color: 'var(--warning)', borderColor: 'var(--warning)' }}>
                    <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> O agente não respondeu. {dados.silencio}
                  </p>
                </div>
              )}
              {enviando && <div className="flex justify-end"><span className="flex items-center gap-2 rounded-full bg-raise-2 px-3 py-2 text-xs text-ink-2"><Loader2 className="h-3.5 w-3.5 animate-spin" /> o agente está respondendo…</span></div>}
              <div ref={fim} />
            </div>
            <ErroCarga erro={erro} compacto className="mx-5 mb-2" />
            {entrega && (
              <p role="status" className="mx-5 mb-2 flex items-start gap-1.5 text-xs"
                style={{ color: entrega[0] === 'ok' ? 'var(--success)' : entrega[0] === 'aviso' ? 'var(--warning)' : 'var(--ink-2)' }}>
                {entrega[0] === 'aviso' ? <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> : <Send className="mt-px h-3.5 w-3.5 shrink-0" />} {entrega[1]}
              </p>
            )}
            <form onSubmit={enviar} className="flex flex-col gap-2.5 border-t border-line bg-[var(--sunken)] px-5 py-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={`inline-flex h-8 items-center rounded-full border px-3 text-[13px] ${comPessoa ? 'border-[var(--royal)] bg-[var(--royal-soft)] font-semibold text-ink' : 'border-line text-ink-2'}`}>Responder ao cliente</span>
                <span className={`inline-flex h-8 items-center rounded-full border px-3 text-[13px] ${!comPessoa ? 'border-[var(--royal)] bg-[var(--royal-soft)] font-semibold text-ink' : 'border-line text-ink-2'}`}>Testar o agente</span>
                <span className="text-xs text-ink-3">{comPessoa ? 'Você está na conversa: o agente não responde.' : 'Para responder você mesmo, assuma a conversa.'}</span>
              </div>
              <div className="flex items-center gap-2.5">
                <input value={texto} onChange={e => setTexto(e.target.value)} maxLength={2000} disabled={enviando || soAcompanha}
                  placeholder={comPessoa ? `Escreva para ${nomeCliente}…`
                    : soAcompanha ? 'Cliente no Telegram: assuma a conversa para responder você'
                    : `Escreva como se fosse ${nomeCliente}, para ver o que o agente responderia…`}
                  aria-label={comPessoa ? 'Resposta ao cliente' : 'Mensagem de teste'}
                  className="h-[46px] min-w-0 flex-1 rounded-[14px] border border-[var(--border)] bg-canvas px-3.5 text-[15px] text-ink placeholder:text-ink-3 focus:border-[var(--focus)] focus:outline-none" />
                <button type="submit" disabled={enviando || soAcompanha || !texto.trim()} className="btn-primary h-[46px] rounded-[14px] px-5">Enviar</button>
              </div>
            </form>
          </>
        )}
      </section>

      <aside className="flex flex-col gap-3.5">
        {escolhido && (
          <section className="flex flex-col gap-2.5 rounded-2xl border border-line bg-surface px-5 py-[18px]">
            <span className="section-label">Nesta conversa</span>
            <LinhaInfo rotulo="Mensagens" valor={mensagens.length} />
            <LinhaInfo rotulo="Ofertas feitas" valor={ofertas} />
            <LinhaInfo rotulo="Canal" valor={tg?.ligado ? 'Telegram' : 'Simulação'} />
            <LinhaInfo rotulo="Quem conduz" valor={comPessoa ? 'Equipe' : 'Agente'} />
            {dados?.caso?.negociacao?.etapa && <LinhaInfo rotulo="Etapa" valor={dados.caso.negociacao.etapa} />}
            {dados?.caso?.identidade_confirmada && <span className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--success)' }}><ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> identidade confirmada</span>}
          </section>
        )}
        {escolhido && (
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border-strong)] bg-[var(--royal-soft)] px-5 py-[18px]">
            <span className="text-xs font-bold uppercase tracking-[0.14em] text-accent-text">Próximo passo</span>
            {dados?.atendimento ? (
              <>
                <b className="text-base text-ink">Atendimento {fmtData(dados.atendimento.data)}, {dados.atendimento.hora}</b>
                <span className="text-sm leading-relaxed text-ink-2">{dados.atendimento.atendente ? `Com ${dados.atendimento.atendente}.` : 'O administrador escolhe quem atende.'}</span>
                <a href="/agenda" className="mt-1 text-sm font-semibold text-accent-text">Ver na agenda ↗</a>
              </>
            ) : dados?.caso?.acordo ? (
              <>
                <b className="text-base text-ink">Acompanhar o acordo</b>
                <span className="text-sm leading-relaxed text-ink-2">Primeiro pagamento de {fmtBRL(dados.caso.acordo.primeiro_pagamento)} em {fmtData(dados.caso.acordo.data)}.</span>
              </>
            ) : comPessoa ? (
              <>
                <b className="text-base text-ink">Responder o cliente</b>
                <span className="text-sm leading-relaxed text-ink-2">A conversa está com a equipe. Quando terminar, devolva para o agente.</span>
              </>
            ) : (
              <>
                <b className="text-base text-ink">O agente conduz</b>
                <span className="text-sm leading-relaxed text-ink-2">Nada pede você agora. Se o cliente pedir uma pessoa, a pasta fica vermelha e entra na agenda.</span>
              </>
            )}
          </section>
        )}
        {dados?.caso && (comPessoa
          ? <button type="button" onClick={() => controlar('devolver')} disabled={enviando} className="btn-secondary w-full rounded-[14px]"><Undo2 className="h-4 w-4" aria-hidden="true" /> Devolver para o agente</button>
          : <button type="button" onClick={() => controlar('assumir')} disabled={enviando} className="btn-secondary w-full rounded-[14px]"><Hand className="h-4 w-4" aria-hidden="true" /> Assumir a conversa</button>)}
        {dados?.caso && (
          <details className="rounded-2xl border border-line bg-surface px-5 py-4">
            <summary className="cursor-pointer text-sm font-semibold text-ink">Telegram e testes</summary>
            <div className="mt-3 flex flex-col gap-2.5">
              <SeloTelegram tg={tg} />
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={gerarConvite} disabled={enviando} className="btn-secondary btn-sm"><Send className="h-3.5 w-3.5" aria-hidden="true" /> {tg?.ligado || tg?.convite_pendente_ate ? 'Novo convite' : 'Convite Telegram'}</button>
                {(tg?.ligado || tg?.convite_pendente_ate) && <button type="button" onClick={desligarTelegram} disabled={enviando} className="btn-secondary btn-sm"><Unlink className="h-3.5 w-3.5" aria-hidden="true" /> Desligar</button>}
              </div>
              <form onSubmit={pagar} className="flex flex-col gap-2 border-t border-line pt-3 text-xs text-ink-2">
                <span className="flex items-center gap-1.5"><Landmark className="h-4 w-4" aria-hidden="true" /> Simular o banco confirmando um pagamento</span>
                <div className="flex gap-2">
                  <input value={valorPago} onChange={e => setValorPago(e.target.value)} inputMode="decimal" placeholder="R$ 270,00" aria-label="Valor pago"
                    className="min-w-0 flex-1 rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-ink focus:outline-none" />
                  <button type="submit" disabled={enviando || !valorPago} className="btn-secondary btn-sm">Confirmar</button>
                </div>
              </form>
            </div>
          </details>
        )}
        {!fixo && dados?.caderno?.length > 0 && (
          <section className="rounded-2xl border border-line bg-surface px-5 py-4">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink"><BookOpen className="h-3.5 w-3.5 text-accent-text" /> Caderno do caso</h3>
            <ol className="space-y-1.5">
              {dados.caderno.map((n, i) => (
                <li key={i} className="text-xs"><span className="font-medium text-ink">{QUEM_CADERNO[n.agente] || n.agente}: {n.decisao}</span>{n.motivo && <span className="text-ink-2"> — {n.motivo}</span>}</li>
              ))}
            </ol>
          </section>
        )}
        {!!dados?.caso?.negociacao?.eventos?.length && (
          <details className="rounded-2xl border border-line bg-surface px-5 py-4 text-xs text-ink-2">
            <summary className="cursor-pointer text-sm font-semibold text-ink">Trilha técnica da negociação</summary>
            <p className="mt-2 break-all">Negociação: {dados.caso.negociacao.id}</p>
            <ol className="mt-2 space-y-1">
              {dados.caso.negociacao.eventos.slice(-20).map(e => <li key={e.chave} className="break-all">
                {e.tipo.replaceAll('_', ' ')} · {e.em ? new Date(e.em).toLocaleString('pt-BR') : '—'}
                {e.decisao_id && <> · decisão {e.decisao_id}</>}
                {e.simulacao_id && <> · simulação {e.simulacao_id}</>}
                {e.compromisso_id && <> · compromisso {e.compromisso_id}</>}
              </li>)}
            </ol>
          </details>
        )}
      </aside>
    </div>
  )
}

const LIMITE_MENSAGENS = 40

function LinhaInfo({ rotulo, valor }) {
  return <div className="flex justify-between gap-3 text-sm"><span className="text-ink-2">{rotulo}</span><b className="text-right text-ink">{valor}</b></div>
}

/* "Por que o agente disse isso?": os passos da última resposta, logo embaixo dela. */
function PorQue({ passos }) {
  const [aberto, setAberto] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setAberto(a => !a)} aria-expanded={aberto}
        className="py-0.5 text-[13px] font-semibold text-accent-text hover:underline">
        {aberto ? 'Esconder o porquê' : 'Por que o agente disse isso?'}
      </button>
      {aberto && (
        <div className="w-full max-w-[560px] rounded-[14px] border border-[var(--border)] bg-canvas px-3.5 py-3">
          <Passos passos={passos} />
        </div>
      )}
    </>
  )
}

/* Separador de dia da conversa: "Hoje, 4 de novembro", "Ontem, …", "Segunda, 2 de novembro". */
function diaDe(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const hoje = new Date()
  const ontem = new Date(); ontem.setDate(hoje.getDate() - 1)
  const longo = d.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })
  if (d.toDateString() === hoje.toDateString()) return `Hoje, ${longo}`
  if (d.toDateString() === ontem.toDateString()) return `Ontem, ${longo}`
  const s = d.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' }).replace('-feira', '')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function Cartao({ icone: Icone, rotulo, valor, nota, cor }) {
  return <StatCard icon={Icone} label={rotulo} value={valor} nota={nota} cor={cor} />
}

function Central({ empresa }) {
  const { isComando } = useAuth()
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
  const monitoramento = c.monitoramento || { disponivel: false, ocorrencias: 0, logs: [], por_agente: {} }
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
<KpiBento>
        <Cartao icone={Power} rotulo="Agente" valor={c.ligado ? 'Ligado' : 'Desligado'} cor={c.ligado ? 'var(--success)' : 'var(--ink-3)'}
          nota={isComando ? `IA: ${c.cliente} · triagem ${c.modelos.triagem} · conversa ${c.modelos.negociador}` : undefined} />
        {isComando && (
          <Cartao icone={Coins} rotulo="Custo hoje" valor={fmtUSD(c.custo_hoje_usd)} cor="var(--ink-2)" nota={`teto do dia: US$ ${c.teto_dia_usd.toFixed(2)}`} />
        )}
        <Cartao icone={ShieldCheck} rotulo="Política" valor={c.politica.versao ? `Versão ${c.politica.versao}` : 'Sem política'}
          cor={c.politica.versao ? 'var(--success)' : 'var(--warning)'}
          nota={c.politica.regras ? `desconto até ${c.politica.regras.desconto_max_pct}% · até ${c.politica.regras.parcelas_max}x` : 'sem política, só ações de segurança passam'} />
        <Cartao icone={AlertTriangle} rotulo="Falhas finais" valor={ev.falhou || 0} cor={ev.falhou ? 'var(--danger)' : 'var(--ink-3)'}
          nota={`${ev.pendente || 0} na fila · ${ev.processando || 0} em andamento · ${ev.feito || 0} feitos`} />
        <Cartao icone={Activity} rotulo="Monitoramento" valor={monitoramento.ocorrencias || 'Sem ocorrências'}
          cor={monitoramento.ocorrencias ? 'var(--warning)' : 'var(--success)'}
          nota={monitoramento.disponivel ? 'Falhas, esperas e encaminhamentos registrados.' : 'Aguardando instalar os logs operacionais.'} />
      </KpiBento>
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
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <div><h2 className="text-sm font-semibold text-ink">Monitoramento dos agentes</h2>
            <p className="mt-1 text-xs text-ink-2">Registra cada falha técnica, nova tentativa, espera da IA e encaminhamento para a equipe. Não inclui conteúdo de conversas.</p></div>
          <span className="text-xs text-ink-3">{monitoramento.disponivel ? 'Últimas 100 ocorrências' : 'Migration pendente'}</span>
        </div>
        {monitoramento.logs?.length === 0 ? <p className="text-xs text-ink-2">Nenhuma ocorrência operacional registrada.</p> : (
          <ul className="divide-y divide-line text-xs">
            {monitoramento.logs.map(log => (
              <li key={log.id || `${log.criado_em}-${log.categoria}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-ink-2">
                <span className="font-medium text-ink">{NOME_LOG_AGENTE[log.agente] || log.agente}</span>
                <span style={{ color: log.nivel === 'erro' || log.nivel === 'critico' ? 'var(--danger)' : 'var(--warning)' }}>{log.mensagem}</span>
                {log.tentativa && <span>{log.tentativa}ª tentativa</span>}
                <span className="ml-auto tabular-nums text-ink-3">{fmtHora(log.criado_em)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
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
  ['remarcacoes_max', 'Remarcações de promessa pelo agente'], ['prazo_confirmacao_dias', 'Prazo de confirmação do banco (dias úteis)'],
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
  const [revisao, setRevisao] = useState(null)
  function carregar() { setErro(null); return agentePlano(empresa).then(setP).catch(setErro) }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  async function aplicar() {
    setOcupado(true); setErro(null)
    try {
      const r = await agenteAplicarPlano(empresa)
      if (r.aplicado === false) { setRevisao(r.revisao_juridica || []); setAviso(r.mensagem); return }
      setRevisao(null)
      setAviso(`Plano aplicado: ${r.contagem.contato} na fila de contato, ${r.contagem.controle} no grupo sorteado.`); await carregar()
    }
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
      {revisao?.length > 0 && (
        <div className="rounded-xl border p-4" style={{ borderColor: 'var(--warning)' }}>
          <p className="text-sm font-semibold text-ink">Revisão humana antes de aplicar</p>
          <p className="mt-1 text-xs text-ink-2">A análise jurídica interna pediu revisão da equipe. Ajuste a política ou peça a avaliação de quem cuida da parte jurídica. O registro completo fica com os administradores.</p>
          <ul className="mt-2 space-y-1.5">
            {revisao.map((d) => (
              <li key={d.acao} className="text-xs text-ink"><span className="font-medium">{d.acao_descricao || d.acao}:</span> {d.justificativa}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="rounded-xl border border-line bg-surface p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink"><Shuffle className="h-4 w-4 text-accent-text" /> Grupo sorteado: {p.contagem.controle} devedores ({p.percentual_controle}% da carteira)</p>
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

// Laboratório (desenho do canvas): cabeçalho com "Gerar análise", aviso de
// demonstração, "Como funciona" ao lado das propostas do Cientista, a resposta
// "A cobrança fez diferença?" com a faixa de confiança, e o funil das negociações.
// As contas vêm prontas do servidor (feitas em código); aqui só se apresenta.
const MIN_RESULTADOS_PROPOSTA = 50

function FezDiferenca({ c, hipoteses }) {
  const t = c.taxa_pagamento
  const [lo, hi] = t.ic95 || [null, null]
  const pontos = (x) => Math.round(Math.abs(x) * 100)
  const frase = lo == null ? 'Ainda sem dados para comparar.'
    : lo > 0 ? `Sim: quem o agente procurou pagou ${pontos(t.diferenca)} pontos a mais.`
      : hi < 0 ? `Não: quem o agente procurou pagou ${pontos(t.diferenca)} pontos a menos.`
        : 'Ainda não dá para dizer: a diferença pode ser zero.'
  // Escala da faixa: de 0 até o maior valor absoluto envolvido, com folga.
  const max = Math.max(0.05, Math.abs(lo ?? 0), Math.abs(hi ?? 0), Math.abs(t.diferenca ?? 0)) * 1.25
  const x = (v) => `${50 + (v / max) * 50}%`
  const cor = lo > 0 ? 'var(--success)' : hi < 0 ? 'var(--danger)' : 'var(--warning)'
  return (
    <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="lab-dif">
      <p className="section-label">A cobrança fez diferença?</p>
      <h3 id="lab-dif" className="mt-1.5 text-[19px] font-semibold leading-snug text-ink">{frase}</h3>
      <p className="mt-1 text-[13px] text-ink-2">
        Comparação com um grupo parecido que não foi procurado.{lo != null && ` A diferença real fica entre ${pp(lo)} e ${pp(hi)} (95% de confiança).`} A conta é feita em código, não pela IA.
        {!c.composicao?.comparaveis && ' Atenção: a composição dos grupos difere, então compare com cuidado.'}
      </p>
      <ul className="mt-5 flex flex-col gap-3">
        {[['Procurados pelo agente', c.n?.agente, t.agente, 'var(--chart-1)'], ['Grupo sem contato', c.n?.sorteado, t.sorteado, 'var(--border-strong)']].map(([r, n, v, cr]) => (
          <li key={r} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[200px_minmax(0,1fr)_64px]">
            <span><span className="block text-sm text-ink">{r}</span><span className="block text-[11px] text-ink-3">{(n ?? 0).toLocaleString('pt-BR')} devedores</span></span>
            <span className="order-last col-span-2 h-3 overflow-hidden rounded-full bg-[var(--raised)] sm:order-none sm:col-span-1" aria-hidden="true">
              <span className="block h-full rounded-full" style={{ width: `${Math.max(1.5, (v || 0) * 100)}%`, background: cr }} />
            </span>
            <b className="text-right text-sm tabular-nums text-ink">{pct(v)}</b>
          </li>
        ))}
        {lo != null && (
          <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[200px_minmax(0,1fr)_64px]">
            <span className="text-sm text-ink">Diferença</span>
            <span className="relative order-last col-span-2 h-5 sm:order-none sm:col-span-1" role="img"
              aria-label={`Diferença de ${pp(t.diferenca)}, entre ${pp(lo)} e ${pp(hi)}`}>
              <span className="absolute inset-x-0 top-1/2 h-px bg-[var(--border-strong)]" />
              <span className="absolute inset-y-0 w-px bg-[var(--text-muted)]" style={{ left: x(0) }} />
              <span className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full border"
                style={{ left: x(Math.min(lo, hi)), width: `calc(${x(Math.max(lo, hi))} - ${x(Math.min(lo, hi))})`, background: `color-mix(in srgb, ${cor} 25%, transparent)`, borderColor: cor }} />
              <span className="absolute inset-y-0 w-0.5 rounded" style={{ left: x(t.diferenca), background: cor }} />
            </span>
            <b className="text-right text-sm tabular-nums" style={{ color: cor }}>{t.diferenca > 0 ? '+' : ''}{pontos(t.diferenca) * Math.sign(t.diferenca || 0)}</b>
          </li>
        )}
      </ul>
      {lo != null && <p className="mt-2 text-[11px] text-ink-3 sm:pl-[216px]">a faixa colorida é onde a diferença real deve estar · a linha fina é o zero (nenhum efeito)</p>}
      {!!hipoteses?.length && (
        <details className="mt-4 rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink">O que o Cientista testou ({hipoteses.length})</summary>
          <ol className="mt-3 flex flex-col gap-3">
            {hipoteses.map((h, i) => (
              <li key={i} className="text-[13px]">
                <p className="flex flex-wrap items-center gap-2 font-medium text-ink">{i + 1}. {h.hipotese} <SeloEvidencia s={h.selo} /></p>
                <p className="mt-0.5 text-ink-2">{h.resultado}</p>
                {h.condicoes && <p className="mt-0.5 text-ink-3">Vale para: {h.condicoes}</p>}
                {h.proximo_experimento && <p className="mt-0.5 text-ink-3">Próximo experimento: {h.proximo_experimento}</p>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}

function Funil({ f }) {
  const etapas = [['Propostas feitas', f.ofertas_apresentadas], ['Acordos aceitos', f.acordos_aceitos], ['Primeiro pagamento', f.primeiro_pagamento_confirmado]]
  const topo = etapas[0][1] || 0
  const umEm = topo && f.primeiro_pagamento_confirmado ? Math.round(topo / f.primeiro_pagamento_confirmado) : null
  return (
    <section className="flex flex-col rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="lab-funil">
      <p className="section-label">Resultado das negociações</p>
      <h3 id="lab-funil" className="mt-1.5 text-[19px] font-semibold leading-snug text-ink">
        {umEm ? `De cada ${umEm} propostas, 1 chega ao primeiro pagamento.` : topo ? 'Nenhuma proposta chegou ao primeiro pagamento ainda.' : 'Nenhuma proposta feita ainda.'}
      </h3>
      <p className="mt-1 text-[13px] text-ink-2">Proposta, aceite e pagamento contam separado. O pagamento usa a baixa registrada, nunca só a promessa.</p>
      <ul className="mt-5 flex flex-col gap-3">
        {etapas.map(([r, v], i) => {
          const ant = i ? etapas[i - 1][1] : null
          return (
            <li key={r} className="grid grid-cols-[150px_minmax(0,1fr)_auto] items-center gap-4">
              <span className="text-sm text-ink-2">{r}</span>
              <span className="flex justify-center" aria-hidden="true">
                <span className="h-3 rounded-full" style={{ width: `${topo ? Math.max(4, ((v || 0) / topo) * 100) : 4}%`, background: i === etapas.length - 1 ? 'var(--chart-1)' : 'var(--border-strong)' }} />
              </span>
              <span className="text-right">
                <b className="block text-sm tabular-nums text-ink">{(v || 0).toLocaleString('pt-BR')}</b>
                <span className="block text-[11px] text-ink-3">{i === 0 ? 'desde o início' : ant ? `${Math.round(((v || 0) / ant) * 100)}% da etapa anterior` : '—'}</span>
              </span>
            </li>
          )
        })}
      </ul>
      <p className="mt-auto pt-5 text-[13px] text-ink-2">
        {f.acordos_quebrados || 0} {f.acordos_quebrados === 1 ? 'acordo quebrado' : 'acordos quebrados'} · {f.retornos_cumpridos || 0} retornos cumpridos · {f.transferencias_humanas || 0} passados para a equipe · primeiro pagamento somou {fmtBRL(f.valor_primeiro_pagamento_confirmado)}
      </p>
    </section>
  )
}

export function Laboratorio({ empresa }) {
  const { isAdmin, isComando } = useAuth()
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [ocupado, setOcupado] = useState('')
  function carregar() { setErro(null); return agenteLaboratorio(empresa).then(setD).catch(setErro) }
  useEffect(() => { carregar() }, [empresa])            // eslint-disable-line react-hooks/exhaustive-deps
  async function agir(fn, chave) {
    setOcupado(chave); setErro(null)
    try { await fn(); await carregar() } catch (err) { setErro(err) } finally { setOcupado('') }
  }
  const [atual, ...antigas] = d?.recomendacoes || []
  const c = atual?.resultados?.comparacao
  const cabecalho = (
    <CabecalhoPagina rotulo="Resultados" icone={FlaskConical} titulo="Laboratório"
      subtitulo="Compara quem o agente procurou com um grupo que não foi procurado, para saber se a cobrança fez diferença.">
      {isAdmin && (
        <button type="button" onClick={() => agir(() => agenteAnalisar(empresa), 'analisar')} disabled={!!ocupado || !d} className="btn-primary">
          {ocupado === 'analisar' ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />} Gerar análise
        </button>
      )}
    </CabecalhoPagina>
  )
  if (erro && !d) return <>{cabecalho}<ErroCarga erro={erro} onTentar={carregar} /></>
  if (!d) return <>{cabecalho}<div className="flex items-center gap-2 p-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div></>
  return (
    <section className="space-y-4">
      {cabecalho}
      <p className="rounded-[14px] border border-[color-mix(in_srgb,var(--warning)_40%,transparent)] bg-[var(--warning-soft)] px-4 py-3 text-sm text-ink">
        Modo demonstração: carteira e pagamentos são fictícios. Os números mostram o método, não um resultado.
      </p>
      {d.erro && <p role="alert" className="rounded-[14px] border border-line bg-surface px-4 py-3 text-sm text-[var(--danger)]">{d.erro}</p>}
      <ErroCarga erro={erro} compacto />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]">
          <p className="section-label">Como funciona</p>
          <ol className="mt-3 flex list-decimal flex-col gap-2.5 pl-5 text-sm leading-relaxed text-ink-2">
            <li><b className="font-semibold text-ink">Separamos um grupo</b> de devedores parecidos que o agente não procura.</li>
            <li><b className="font-semibold text-ink">Comparamos</b> quanto pagou cada grupo. A conta é feita em código, não pela IA.</li>
            <li><b className="font-semibold text-ink">O Cientista sugere</b> o que mudar. Nada muda na política sem a sua aprovação.</li>
          </ol>
        </section>

        <section className="flex flex-col rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="lab-prop">
          <p className="section-label">Proposta do Cientista</p>
          {atual ? (
            <>
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-3">
                <b className="text-ink">Versão {atual.versao}</b> <SeloEvidencia s={atual.selo} /> · {STATUS_REC[atual.status] || atual.status} · {atual.origem === 'ia' ? 'texto da IA' : 'texto em código (sem IA)'}
              </p>
              <h3 id="lab-prop" className="mt-2 text-[17px] font-semibold leading-snug text-ink">{atual.texto}</h3>
              {atual.relatorio?.resumo && <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{atual.relatorio.resumo}</p>}
              {isAdmin && atual.status === 'proposta' && (
                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  <button type="button" onClick={() => agir(() => agenteDecidirRecomendacao(atual.id, 'aprovada', empresa), 'aprovar')} disabled={!!ocupado} className="btn-primary">
                    {ocupado === 'aprovar' ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Aprovar
                  </button>
                  <button type="button" onClick={() => agir(() => agenteDecidirRecomendacao(atual.id, 'recusada', empresa), 'recusar')} disabled={!!ocupado} className="btn-secondary">
                    {ocupado === 'recusar' ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Recusar
                  </button>
                </div>
              )}
            </>
          ) : (
            <>
              <h3 id="lab-prop" className="mt-1.5 text-[17px] font-semibold text-ink">Nenhuma proposta ainda</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
                O Cientista propõe uma mudança quando há resultados registrados suficientes (pelo menos {MIN_RESULTADOS_PROPOSTA}).
                {isAdmin ? ' Clique em Gerar análise para ver o que os dados de hoje já dizem.' : ''}
              </p>
            </>
          )}
        </section>
      </div>

      {(c || d.funil_negociacao) && (
        <div className={`grid gap-4 ${c && d.funil_negociacao ? 'lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]' : ''}`}>
          {c && <FezDiferenca c={c} hipoteses={atual.relatorio?.hipoteses} />}
          {d.funil_negociacao && <Funil f={d.funil_negociacao} />}
        </div>
      )}

      {!!antigas.length && (
        <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]">
          <p className="section-label">Versões anteriores</p>
          <ul className="mt-2 divide-y divide-line">
            {antigas.map(r => (
              <li key={r.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2.5 text-[13px] text-ink-2">
                <b className="text-ink">v{r.versao}</b> <SeloEvidencia s={r.selo} /> <span className="text-ink-3">{STATUS_REC[r.status] || r.status}</span>
                <span className="w-full text-ink-2 sm:w-auto sm:flex-1">{r.texto}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(isAdmin || isComando) && (
        <details className="group rounded-[22px] border border-line bg-surface px-6 py-[18px]">
          <summary className="cursor-pointer list-none text-sm font-semibold text-ink">
            Mais ações: retreino do modelo e experimento do bandit
            <span className="ml-2 text-xs font-normal text-ink-3 group-open:hidden">abrir</span>
          </summary>
          <div className="mt-4"><AprendizadoCientista empresa={empresa} /></div>
        </details>
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
  // Ao vivo: o agente marcou, remarcou ou desmarcou. Troca a lista só se mudou.
  useAoMudarNoServidor('agenda', useCallback(() => {
    agenteAgenda(empresa).then(r => setD(atual => (JSON.stringify(atual) === JSON.stringify(r) ? atual : r))).catch(() => {})
  }, [empresa]))

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
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><CalendarClock className="h-4 w-4 text-accent-text" /> Agenda dos agentes</h2>
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
                <li key={i.id} className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
                 <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="w-12 tabular-nums text-ink-2">{i.hora || '—'}</span>
                  <span className="font-medium text-ink">{i.nome || 'Devedor'}</span>
                  <span className="rounded border border-line px-1.5 py-px text-[11px] text-ink-2">{TIPO_AGENDA[i.tipo] || i.tipo}</span>
                  <SeloPrioridade passagem={i.passagem} />
                  {i.passagem ? <span className="flex-1" />
                    : <span className="min-w-0 flex-1 truncate text-xs text-ink-2" title={i.observacao}>{i.observacao}</span>}
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
                 </div>
                 {i.passagem && <FichaPassagem passagem={i.passagem} predicaoId={i.predicao_id} empresaId={empresa} />}
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

// Quantos casos estão com a equipe esperando resposta. Atualiza sozinho, como a fila da aba Conversas.
function useEsperando(empresa) {
  const [n, setN] = useState(null)
  useEffect(() => {
    let vivo = true
    const ler = () => { if (!document.hidden) agenteAtendimentos(empresa).then(d => vivo && setN((d.itens || []).filter(i => i.esperando).length)).catch(() => {}) }
    ler()
    const t = setInterval(ler, 15000)
    return () => { vivo = false; clearInterval(t) }
  }, [empresa])
  return n
}

// Um número do topo (prancha "Agentes · Ao vivo"): rótulo, valor e uma linha que diz o que ele significa.
function Placar({ rotulo, valor, detalhe, tom, children }) {
  const estilo = {
    royal: 'border-transparent bg-[var(--royal)] text-[var(--on-brand)]',
    aviso: 'border-[color-mix(in_srgb,var(--warning)_45%,transparent)] bg-[var(--warning-soft)] text-ink',
  }[tom] || 'border-line bg-surface text-ink'
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 rounded-[18px] border px-4 py-4 sm:rounded-[22px] sm:px-5 sm:py-[18px] ${estilo}`}>
      <span className={`text-[11px] font-bold uppercase tracking-[.14em] ${tom === 'royal' ? 'opacity-80' : tom === 'aviso' ? 'text-[var(--warning)]' : 'text-ink-3'}`}>{rotulo}</span>
      <span className="text-[28px] font-bold leading-none tabular-nums sm:text-[34px]">{valor}</span>
      {detalhe && <span className={`text-[13px] ${tom === 'royal' ? 'opacity-85' : 'text-ink-2'}`}>{detalhe}</span>}
      {children}
    </div>
  )
}

function AoVivo({ empresa, onFila }) {
  const navigate = useNavigate()
  const { empresaConfig, isComando } = useAuth()
  const dados = useEscritorio(empresa)
  const esperando = useEsperando(empresa)
  const n = dados.numeros
  const usd = v => `US$ ${Number(v || 0).toFixed(2).replace('.', ',')}`
  const abrir = nome => navigate(`/agente/${encodeURIComponent(nome)}`)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <Placar tom="royal" rotulo="Conversas · 24 h" valor={n ? n.conversas : '—'}
          detalhe={n ? (n.respostas ? `${n.respostas} ${n.respostas === 1 ? 'resposta' : 'respostas'} dos clientes` : 'nenhuma resposta ainda') : null} />
        <Placar rotulo="Acordos · 24 h" valor={n ? n.acordos : '—'} detalhe="fechados pelos agentes" />
        <Placar rotulo="Bloqueios · 24 h" valor={n ? n.bloqueios : '—'} detalhe="mensagens barradas pelo Auditor" />
        <Placar tom={esperando ? 'aviso' : undefined} rotulo="Esperando você" valor={esperando ?? '—'}>
          <button type="button" onClick={onFila} className={`self-start text-[13px] font-semibold hover:underline ${esperando ? 'text-[var(--warning)]' : 'text-accent-text'}`}>
            {esperando ? 'abrir a fila ↗' : 'ninguém na fila agora · ver conversas ↗'}
          </button>
        </Placar>
      </div>
      {isComando && n && (
        <p className="text-[13px] text-ink-2">
          Gasto de IA hoje: <b className="tabular-nums text-ink">{usd(n.custo_hoje_usd)}</b>{n.teto_dia_usd ? <> de {usd(n.teto_dia_usd)} do teto do dia</> : null}
        </p>
      )}
      <EscritorioAgentes key={empresa || 'atual'} dados={dados} nomeEmpresa={empresaConfig?.nome_exibicao} logoUrl={empresaConfig?.foto_url} onPerfil={abrir} mostrarCusto={isComando} />
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
        <CabecalhoPagina rotulo="Agentes" icone={Bot} titulo="Equipe de agentes" className="!mb-0"
          subtitulo="O que os agentes fizeram nas últimas 24 horas e quem está esperando por você.">
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </CabecalhoPagina>
        <div className="flex flex-wrap gap-1 border-b border-line" role="tablist">
          {[['aovivo', 'Ao vivo'], ['conversas', 'Conversas'], ['agenda', 'Agenda'], ['regras', 'Regras']].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}
              className={`-mb-px border-b-2 px-3 py-2.5 text-sm ${aba === k ? 'border-[var(--royal)] font-semibold text-ink' : 'border-transparent font-medium text-ink-2 hover:text-ink'}`}>
              {l}
            </button>
          ))}
        </div>
        {isComando && !alvo ? (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa.</div>
        ) : aba === 'conversas' ? <Conversa empresa={empresa} />
          : aba === 'agenda' ? <Agenda empresa={empresa} />
          : aba === 'regras' ? <Regras empresa={empresa} />
          : <AoVivo empresa={empresa} onFila={() => setAba('conversas')} />}
      </div>
    </AppShell>
  )
}
