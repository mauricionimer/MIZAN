import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useLocation } from 'react-router-dom'
import { Search, Loader2, HelpCircle, ChevronDown, AlertTriangle, Info, BookOpen, Send, MessageCircleQuestion, CheckCircle2 } from 'lucide-react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import DicaAjuda from '../components/DicaAjuda'
import { atualizarAvisosDeDuvida } from '../components/useAvisosDeDuvida'
import {
  buscarAjuda, indiceDaAjuda, entradaDaAjuda, estadoDoModelo,
  enviarDuvida, minhasDuvidas, marcarDuvidasVistas, duvidasDaEquipe,
} from '../api'

function Aviso({ tom = 'warning', icone: Icone = AlertTriangle, children }) {
  const cor = tom === 'info' ? 'royal' : 'warning'
  return (
    <div className="flex items-start gap-2.5 rounded-xl p-3"
      style={{ background: `rgb(var(--c-${cor}) / 0.08)`, border: `1px solid rgb(var(--c-${cor}) / 0.18)` }}>
      <Icone className="mt-0.5 h-4 w-4 shrink-0" style={{ color: tom === 'info' ? 'var(--ink-2)' : 'var(--warning)' }} />
      <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>{children}</p>
    </div>
  )
}

function Bloco({ titulo, children }) {
  if (!children) return null
  return (
    <div>
      <p className="section-label mb-1">{titulo}</p>
      <p className="whitespace-pre-line text-sm leading-relaxed text-ink-2">{children}</p>
    </div>
  )
}

function Resposta({ e, aberta, onAlternar, destaque = false }) {
  return (
    <article className={`rounded-xl border bg-surface p-5 ${destaque ? 'border-blue-500/40' : 'border-line'}`}>
      <button onClick={onAlternar} className="flex w-full items-start justify-between gap-3 text-left" aria-expanded={aberta}>
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{e.assunto}</p>
          <h3 className="mt-0.5 text-base font-semibold text-ink">{e.titulo}</h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-2">{e.curta}</p>
        </div>
        <ChevronDown className={`mt-1 h-4 w-4 shrink-0 text-ink-3 transition-transform ${aberta ? 'rotate-180' : ''}`} />
      </button>
      {aberta && (
        <div className="mt-4 space-y-4 border-t border-line pt-4">
          <Bloco titulo="Como é calculado">{e.calculo}</Bloco>
          <Bloco titulo="O que fazer com isso">{e.fazer}</Bloco>
          <Bloco titulo="Quando não confiar">{e.cuidado}</Bloco>
          {e.em_revisao && (
            <Aviso tom="info" icone={Info}>
              Esta resposta descreve o que o sistema faz hoje, mas há uma decisão pendente sobre ele. Ela pode mudar.
            </Aviso>
          )}
          {e.fontes && (
            <div>
              <p className="section-label mb-1">Fontes no código (COMANDO)</p>
              <ul className="space-y-0.5 font-mono text-[11px] text-ink-3">
                {e.fontes.map(f => <li key={f}>{f}</li>)}
              </ul>
              {e.revisar && <p className="mt-2 text-xs text-ink-3">Revisar: {e.revisar}</p>}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

const fmtData = (iso) => (iso ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso)) : '')

function PedirAoComando({ token, inicial, tela, buscou, aberto, onAbrir, onEnviada }) {
  const [texto, setTexto]       = useState(inicial)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro]         = useState('')
  const [feito, setFeito]       = useState(null)
  useEffect(() => { setTexto(inicial); setFeito(null) }, [inicial])

  async function enviar(e) {
    e.preventDefault()
    setEnviando(true); setErro('')
    try {
      const r = await enviarDuvida(token, { pergunta: texto.trim(), tela, buscou })
      setFeito(r); onEnviada?.()
    } catch (e2) { setErro(e2.message) } finally { setEnviando(false) }
  }

  if (feito) {
    return (
      <div className="flex items-start gap-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-xs text-emerald-300" role="status">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Dúvida enviada ao COMANDO. A resposta aparece aqui, em "Minhas dúvidas", e o menu avisa quando chegar.
          {feito.mascarado && ' Retiramos da sua pergunta o que parecia dado pessoal (CPF, telefone, e-mail).'}
        </span>
      </div>
    )
  }
  if (!aberto) {
    return (
      <button onClick={onAbrir} className="inline-flex items-center gap-2 text-sm font-medium text-blue-400 hover:text-blue-300">
        <MessageCircleQuestion className="h-4 w-4" /> Não era isto? Pergunte ao COMANDO
      </button>
    )
  }
  return (
    <form onSubmit={enviar} className="space-y-3 rounded-xl border border-line bg-surface p-5">
      <p className="text-sm font-semibold text-ink">Pergunte ao COMANDO<DicaAjuda id="enviar-duvida" /></p>
      <label htmlFor="duvida-texto" className="sr-only">Sua dúvida</label>
      <textarea id="duvida-texto" value={texto} onChange={e => setTexto(e.target.value)} rows={4} maxLength={2000}
        placeholder="Explique o que você não entendeu, e em que tela estava."
        className="w-full rounded-lg border border-line bg-page p-3 text-sm text-ink placeholder-ink-4 focus:border-blue-500/50 focus:outline-none" />
      <p className="text-xs leading-relaxed text-ink-3">
        Não escreva CPF, nome, telefone ou e-mail de devedores. O sistema retira CPF, CNPJ, telefone e e-mail do
        que você enviar, mas não consegue reconhecer nomes.
      </p>
      {erro && <p className="text-xs text-red-400" role="alert">{erro}</p>}
      <button type="submit" disabled={enviando || texto.trim().length < 3}
        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50">
        {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Enviar
      </button>
    </form>
  )
}

function CartaoDuvida({ d, mostrarAutor = false, destaque = false }) {
  return (
    <li className={`rounded-xl border p-4 ${destaque ? 'border-blue-500/50 bg-blue-500/5' : 'border-line bg-surface'}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-3">
        <span>{mostrarAutor ? `${d.autor_nome || d.autor_email} · ` : ''}{fmtData(d.created_at)}</span>
        <span className={`rounded-full px-2 py-0.5 font-medium ${d.estado === 'respondida' ? 'bg-emerald-500/15 text-emerald-500' : 'bg-raise-2 text-ink-3'}`}>
          {d.estado === 'respondida' ? 'Respondida' : 'Aguardando resposta'}
        </span>
      </div>
      <p className="mt-2 text-sm text-ink">{d.pergunta}</p>
      {d.resposta && (
        <div className="mt-3 rounded-lg bg-raise-1 p-3">
          <p className="section-label mb-1">Resposta do COMANDO</p>
          <p className="whitespace-pre-line text-sm leading-relaxed text-ink-2">{d.resposta}</p>
        </div>
      )}
    </li>
  )
}

export default function Ajuda() {
  const { token, isAdmin } = useAuth()
  const { result, setVista } = useAnalysis()
  const location = useLocation()

  const [pergunta, setPergunta]   = useState('')
  const [busca, setBusca]         = useState(null)     // { certeza, resultados, pergunta }
  const [buscando, setBuscando]   = useState(false)
  const [erro, setErro]           = useState('')
  const [indice, setIndice]       = useState([])
  const [modelo, setModelo]       = useState(null)
  const [abertas, setAbertas]     = useState({})
  const [navegada, setNavegada]   = useState(null)     // entrada aberta pelo índice
  const ultima = useRef(0)
  const [minhas, setMinhas]       = useState([])
  const [novas, setNovas]         = useState(new Set())
  const [equipe, setEquipe]       = useState([])
  const [pedindo, setPedindo]     = useState(false)
  const [params] = useSearchParams()

  useEffect(() => {
    indiceDaAjuda(token).then(setIndice).catch(() => {})
    estadoDoModelo(token).then(setModelo).catch(() => {})
    carregarDuvidas()
    // Link de outra tela ("O que é isto?") abre a resposta direto.
    const direto = params.get('id')
    if (direto) {
      entradaDaAjuda(token, direto).then(e => { setNavegada(e); setAbertas({ [e.id]: true }) }).catch(() => {})
    }
  }, [token])

  async function carregarDuvidas() {
    try {
      const lista = await minhasDuvidas(token)
      setMinhas(lista)
      const naoVistas = lista.filter(d => d.estado === 'respondida' && !d.visto_em).map(d => d.id)
      if (naoVistas.length) {
        setNovas(new Set(naoVistas))                 // destaque só nesta visita
        await marcarDuvidasVistas(token)
        atualizarAvisosDeDuvida()
      }
    } catch { /* sem a lista, a página segue funcionando */ }
    if (isAdmin) duvidasDaEquipe(token).then(setEquipe).catch(() => {})
  }

  async function perguntar(e) {
    e?.preventDefault()
    const q = pergunta.trim()
    if (q.length < 2) return
    setErro(''); setNavegada(null); setBuscando(true)
    const minha = ++ultima.current
    try {
      const r = await buscarAjuda(token, q)
      if (minha !== ultima.current) return
      setBusca({ ...r, pergunta: q })
      setAbertas(r.certeza && r.resultados[0] ? { [r.resultados[0].id]: true } : {})
    } catch (e2) {
      if (minha === ultima.current) setErro(e2.message)
    } finally {
      if (minha === ultima.current) setBuscando(false)
    }
  }

  async function abrirDoIndice(id) {
    setErro(''); setBusca(null)
    try {
      const e = await entradaDaAjuda(token, id)
      setNavegada(e); setAbertas({ [e.id]: true })
    } catch (e2) { setErro(e2.message) }
  }

  const alternar = (id) => setAbertas(a => ({ ...a, [id]: !a[id] }))
  const resultados = busca?.resultados || []

  return (
    <AppShell secao="ajuda" onIrPara={setVista} temResultado={!!result} titulo="Ajuda">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div>
          <p className="section-label">Central de ajuda</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Como posso ajudar?</h1>
          <p className="mt-1 text-sm text-ink-2">
            Pergunte como falaria com um colega: "por que esse devedor está no topo?", "o que é prioridade alta?".
            A busca é feita aqui, no servidor do Mizan, e o que você digita nela não é guardado (só a dúvida que você decidir enviar).
          </p>
        </div>

        {modelo && modelo.nivel !== 'ok' && <Aviso>{modelo.aviso}</Aviso>}

        <form onSubmit={perguntar} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input value={pergunta} onChange={e => setPergunta(e.target.value)} maxLength={300}
              placeholder="Escreva a sua dúvida…" aria-label="Sua dúvida"
              className="h-11 w-full rounded-xl border border-line bg-surface pl-10 pr-3 text-sm text-ink placeholder-ink-4 focus:border-blue-500/50 focus:outline-none" />
          </div>
          <button type="submit" disabled={buscando || pergunta.trim().length < 2}
            className="flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50">
            {buscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <HelpCircle className="h-4 w-4" />}
            Buscar
          </button>
        </form>

        {erro && <Aviso>{erro}</Aviso>}

        {busca && (
          <section className="space-y-3" aria-live="polite">
            {busca.certeza ? (
              <p className="text-xs font-medium text-ink-3">Encontrei isto para "{busca.pergunta}":</p>
            ) : resultados.length > 0 ? (
              <Aviso tom="info" icone={Info}>
                Não tenho certeza de ter entendido a sua pergunta. Estas são as respostas mais próximas;
                se nenhuma servir, escreva de outro jeito ou procure no índice abaixo.
              </Aviso>
            ) : (
              <Aviso tom="info" icone={Info}>
                Não encontrei nada sobre isso na ajuda. Tente outras palavras ou procure no índice abaixo.
              </Aviso>
            )}
            {resultados.map((e, i) => (
              <Resposta key={e.id} e={e} destaque={busca.certeza && i === 0}
                aberta={!!abertas[e.id]} onAlternar={() => alternar(e.id)} />
            ))}
          </section>
        )}

        {navegada && <Resposta e={navegada} aberta={!!abertas[navegada.id]} onAlternar={() => alternar(navegada.id)} />}

        <PedirAoComando token={token} inicial={busca?.pergunta || pergunta} tela={location.state?.de} buscou={busca?.pergunta}
          aberto={pedindo || (!!busca && !busca.certeza)} onAbrir={() => setPedindo(true)} onEnviada={carregarDuvidas} />


        {minhas.length > 0 && (
          <section aria-label="Minhas dúvidas">
            <h2 className="mb-3 text-sm font-semibold text-ink">Minhas dúvidas</h2>
            <ul className="space-y-3">{minhas.map(d => <CartaoDuvida key={d.id} d={d} destaque={novas.has(d.id)} />)}</ul>
          </section>
        )}

        {isAdmin && equipe.length > 0 && (
          <section aria-label="Dúvidas da equipe">
            <h2 className="mb-1 text-sm font-semibold text-ink">Dúvidas da sua equipe</h2>
            <p className="mb-3 text-xs text-ink-3">O que as pessoas da sua empresa perguntaram ao COMANDO. Só leitura.</p>
            <ul className="space-y-3">{equipe.map(d => <CartaoDuvida key={d.id} d={d} mostrarAutor />)}</ul>
          </section>
        )}

        <section>
          <div className="mb-3 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-ink-3" />
            <h2 className="text-sm font-semibold text-ink">Índice</h2>
          </div>
          <div className="space-y-4">
            {indice.map(g => (
              <div key={g.assunto}>
                <p className="section-label mb-1.5">{g.assunto}</p>
                <div className="flex flex-wrap gap-2">
                  {g.entradas.map(en => (
                    <button key={en.id} onClick={() => abrirDoIndice(en.id)}
                      className="rounded-lg border border-line bg-surface px-3 py-1.5 text-left text-xs text-ink-2 transition-colors hover:bg-raise-1 hover:text-ink">
                      {en.titulo}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  )
}
