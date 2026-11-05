import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom'
import { Search, Loader2, HelpCircle, ChevronDown, AlertTriangle, Info, BookOpen, Send, MessageCircleQuestion, CheckCircle2, Compass, LayoutDashboard, FolderOpen, SlidersHorizontal, Wallet, LineChart, Bot } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import EstadoPlataforma from '../components/EstadoPlataforma'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import DicaAjuda from '../components/DicaAjuda'
import { atualizarAvisosDeDuvida } from '../components/useAvisosDeDuvida'
import {
  buscarAjuda, naoResolveu, indiceDaAjuda, entradaDaAjuda,
  enviarDuvida, minhasDuvidas, marcarDuvidasVistas, duvidasDaEquipe, buscarFaq,
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
    <article className={`rounded-2xl border bg-surface px-6 py-5 ${destaque ? 'border-blue-500/40' : 'border-line'}`}>
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
      <button type="button" onClick={onAbrir} className="btn-primary w-full rounded-[14px]">
        <MessageCircleQuestion className="h-4 w-4" aria-hidden="true" /> Perguntar ao COMANDO
      </button>
    )
  }
  return (
    <form onSubmit={enviar} className="space-y-3">
      <p className="text-sm font-semibold text-ink">Pergunte ao COMANDO<DicaAjuda id="enviar-duvida" /></p>
      <label htmlFor="duvida-texto" className="sr-only">Sua dúvida</label>
      <textarea id="duvida-texto" value={texto} onChange={e => setTexto(e.target.value)} rows={4} maxLength={2000}
        placeholder="Explique o que você não entendeu, e em que tela estava."
        className="w-full rounded-[14px] border border-[var(--border)] bg-canvas p-3 text-sm text-ink placeholder:text-ink-3 focus:border-[var(--focus)] focus:outline-none" />
      <p className="text-xs leading-relaxed text-ink-3">
        Não escreva CPF, nome, telefone ou e-mail de devedores. O sistema retira CPF, CNPJ, telefone e e-mail do
        que você enviar, mas não consegue reconhecer nomes.
      </p>
      {erro && <p className="text-xs text-red-400" role="alert">{erro}</p>}
      <button type="submit" disabled={enviando || texto.trim().length < 3}
        className="btn-primary">
        {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Enviar
      </button>
    </form>
  )
}

function CartaoDuvida({ d, mostrarAutor = false, destaque = false }) {
  return (
    <li className={`rounded-2xl border p-4 ${destaque ? 'border-[var(--royal)] bg-[var(--royal-soft)]' : 'border-line bg-surface'}`}>
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
  const { token, isAdmin, isComando } = useAuth()
  const { result, setVista } = useAnalysis()
  const location = useLocation()

  const [pergunta, setPergunta]   = useState('')
  const [busca, setBusca]         = useState(null)     // { certeza, resultados, pergunta }
  const [buscando, setBuscando]   = useState(false)
  const [erro, setErro]           = useState('')
  const [indice, setIndice]       = useState([])
  const [abertas, setAbertas]     = useState({})
  const [navegada, setNavegada]   = useState(null)     // entrada aberta pelo índice
  const ultima = useRef(0)
  const [minhas, setMinhas]       = useState([])
  // Perguntas frequentes publicadas pelo COMANDO (sem autor nem empresa).
  const [faq, setFaq]             = useState([])
  useEffect(() => { buscarFaq(token).then(d => setFaq(Array.isArray(d) ? d : [])).catch(() => {}) }, [token])
  const [novas, setNovas]         = useState(new Set())
  const [equipe, setEquipe]       = useState([])
  const [pedindo, setPedindo]     = useState(!!location.state?.pedir)   // vindo de "Pedir ao Comando" de outra tela
  const [registrou, setRegistrou] = useState(false)   // 'isto não resolveu' já enviado para esta busca
  const [params] = useSearchParams()

  useEffect(() => {
    indiceDaAjuda(token).then(setIndice).catch(() => {})
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
    setErro(''); setNavegada(null); setBuscando(true); setRegistrou(false)
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

  async function naoServiu() {
    setRegistrou(true); setPedindo(true)
    try { await naoResolveu(token, { pergunta: busca.pergunta, entrada_id: resultados[0]?.id }) } catch { /* o registro é só um aviso ao COMANDO */ }
  }

  const [tema, setTema] = useState(null)
  const alternar = (id) => setAbertas(a => ({ ...a, [id]: !a[id] }))
  const resultados = busca?.resultados || []

  return (
    <AppShell secao="ajuda" onIrPara={setVista} temResultado={!!result} titulo="Ajuda">
      <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-6">
        <CabecalhoPagina rotulo="Central de ajuda" icone={HelpCircle} titulo="Como posso ajudar?" className="!mb-0"
          subtitulo="Escreva a dúvida com as suas palavras, veja se a plataforma está funcionando ou peça ajuda ao Comando." />

        <form onSubmit={perguntar} className="flex gap-2.5">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-ink-3" />
            <input value={pergunta} onChange={e => setPergunta(e.target.value)} maxLength={300}
              placeholder="Escreva a sua dúvida… ex.: por que a pasta ficou vermelha?" aria-label="Sua dúvida"
              className="h-[52px] w-full rounded-[14px] border border-[var(--border)] bg-surface pl-11 pr-4 text-[15px] text-ink placeholder:text-ink-3 focus:border-[var(--focus)] focus:outline-none" />
          </div>
          <button type="submit" disabled={buscando || pergunta.trim().length < 2} className="btn-primary h-[52px] rounded-[14px] px-6">
            {buscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
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
                se nenhuma servir, escreva de outro jeito ou procure nas perguntas por tema abaixo.
              </Aviso>
            ) : (
              <Aviso tom="info" icone={Info}>
                Não encontrei nada sobre isso na ajuda. Tente outras palavras ou procure nas perguntas por tema abaixo.
              </Aviso>
            )}
            {resultados.map((e, i) => (
              <Resposta key={e.id} e={e} destaque={busca.certeza && i === 0}
                aberta={!!abertas[e.id]} onAlternar={() => alternar(e.id)} />
            ))}
            {busca.certeza && resultados.length > 0 && !registrou && (
              <button onClick={naoServiu} className="text-sm font-medium text-ink-3 hover:text-ink">
                Isto não resolveu a minha dúvida
              </button>
            )}
          </section>
        )}

        {navegada && <Resposta e={navegada} aberta={!!abertas[navegada.id]} onAlternar={() => alternar(navegada.id)} />}

        {(!isComando || isAdmin) && (
          <div className={`grid items-start gap-5 ${isAdmin ? 'lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]' : ''}`}>
            {!isComando && <EstadoPlataforma />}
            {isAdmin && <ComecePorAqui />}
          </div>
        )}

        {indice.length > 0 && (
          <section aria-label="Guias da plataforma" className="flex flex-col gap-3.5">
            <div className="flex items-center justify-between gap-3">
              <span className="section-label">Guias da plataforma</span>
              <span className="text-xs text-ink-3">{indice.reduce((s, g) => s + g.entradas.length, 0)} respostas</span>
            </div>
            <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
              {indice.map((g, k) => (
                <button key={g.assunto} type="button" onClick={() => { setTema(g.assunto); document.getElementById('perguntas-por-tema')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}
                  className={`flex items-center gap-4 overflow-hidden rounded-[18px] border bg-surface p-3 text-left transition-colors ${tema === g.assunto ? 'border-[var(--royal)]' : 'border-line hover:border-[var(--border-strong)]'}`}>
                  <span className="flex h-[72px] w-[84px] shrink-0 flex-col items-center justify-center gap-1 rounded-[14px] bg-[var(--royal-soft)] text-accent-text">
                    {(() => { const I = ICONES_GUIA[k % ICONES_GUIA.length]; return <I className="h-7 w-7" strokeWidth={1.6} aria-hidden="true" /> })()}
                    <span className="text-[11px] font-semibold">{g.entradas.length} {g.entradas.length === 1 ? 'resposta' : 'respostas'}</span>
                  </span>
                  <span className="flex min-w-0 flex-col gap-1">
                    <b className="text-[15px] text-ink">{g.assunto}</b>
                    <span className="line-clamp-2 text-[13px] leading-snug text-ink-2">{g.entradas.slice(0, 2).map(e => e.titulo).join(' · ')}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
          <section id="perguntas-por-tema" aria-label="Perguntas por tema" className="flex scroll-mt-24 flex-col gap-4 rounded-2xl border border-line bg-surface px-6 py-[22px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="section-label">Perguntas por tema</span>
              {tema && <button type="button" onClick={() => setTema(null)} className="text-[13px] text-accent-text hover:underline">Ver todos os temas</button>}
            </div>
            {!indice.length && <p className="text-sm text-ink-3">Carregando o índice…</p>}
            {indice.filter(g => !tema || g.assunto === tema).map(g => (
              <div key={g.assunto} className="flex flex-col gap-1.5">
                <b className="text-sm text-ink">{g.assunto}</b>
                {g.entradas.map(en => (
                  <button key={en.id} type="button" onClick={() => { abrirDoIndice(en.id); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                    className="self-start text-left text-sm text-accent-text hover:underline">{en.titulo}</button>
                ))}
              </div>
            ))}
            {faq.length > 0 && (
              <div className="flex flex-col gap-2 border-t border-line pt-4">
                <b className="text-sm text-ink">Perguntas frequentes</b>
                {faq.map(f => (
                  <details key={f.id} className="group rounded-[14px] border border-line px-4 py-3">
                    <summary className="cursor-pointer list-none text-sm font-medium text-ink marker:hidden">
                      <span className="mr-2 inline-block text-ink-3 transition-transform group-open:rotate-90">›</span>{f.pergunta}
                    </summary>
                    <p className="mt-2 whitespace-pre-line pl-5 text-sm leading-relaxed text-ink-2">{f.resposta}</p>
                  </details>
                ))}
              </div>
            )}
          </section>

          <aside className="flex flex-col gap-3.5">
            <section className="flex flex-col gap-3 rounded-2xl border border-[var(--border-strong)] bg-[var(--royal-soft)] px-6 py-[22px]">
              <b className="text-[17px] text-ink">Falar com uma pessoa</b>
              <span className="text-sm leading-relaxed text-ink-2">O COMANDO responde aqui mesmo, em "Minhas dúvidas", e o menu avisa quando a resposta chegar.</span>
              <PedirAoComando token={token} inicial={busca?.pergunta || pergunta || location.state?.pedir || ''} tela={location.state?.de} buscou={busca?.pergunta}
                aberto={pedindo || (!!busca && !busca.certeza)} onAbrir={() => setPedindo(true)} onEnviada={carregarDuvidas} />
            </section>
            {minhas.length > 0 && (
              <section aria-label="Minhas dúvidas" className="flex flex-col gap-3">
                <span className="section-label">Minhas dúvidas</span>
                <ul className="space-y-3">{minhas.map(d => <CartaoDuvida key={d.id} d={d} destaque={novas.has(d.id)} />)}</ul>
              </section>
            )}
            {isAdmin && equipe.length > 0 && (
              <section aria-label="Dúvidas da equipe" className="flex flex-col gap-2">
                <span className="section-label">Dúvidas da sua equipe</span>
                <p className="text-xs text-ink-3">O que as pessoas da sua empresa perguntaram ao COMANDO. Só leitura.</p>
                <ul className="space-y-3">{equipe.map(d => <CartaoDuvida key={d.id} d={d} mostrarAutor />)}</ul>
              </section>
            )}
          </aside>
        </div>
      </div>
    </AppShell>
  )
}

const ICONES_GUIA = [Compass, LayoutDashboard, FolderOpen, SlidersHorizontal, Wallet, LineChart, Bot, BookOpen]

/* "Comece por aqui": os primeiros passos de quem administra a empresa. Cada passo
   leva à tela certa; a pessoa marca o que já fez (fica guardado neste navegador). */
const PASSOS = [
  { id: 'carteira', titulo: 'Enviar a primeira carteira', det: 'A MIZAN calcula quem cobrar primeiro', tempo: '2 min', rota: '/' },
  { id: 'politica', titulo: 'Revisar a política de cobrança', det: 'Limites de desconto, horário e contatos', tempo: '3 min', rota: '/premissas' },
  { id: 'duas-etapas', titulo: 'Ligar a verificação em duas etapas', det: 'Protege a conta da empresa', tempo: '1 min', rota: '/seguranca' },
  { id: 'equipe', titulo: 'Convidar a equipe', det: 'Quem faz a cobrança precisa de acesso próprio', tempo: '2 min', rota: '/admin/usuarios' },
  { id: 'pagamentos', titulo: 'Registrar os primeiros pagamentos', det: 'É o que ensina o modelo a acertar', tempo: '5 min', rota: '/feedback' },
]
const CHAVE_PASSOS = 'mizan_comece_por_aqui'

function ComecePorAqui() {
  const navigate = useNavigate()
  const [feitos, setFeitos] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CHAVE_PASSOS) || '{}') || {} } catch { return {} }
  })
  const marcar = (id) => setFeitos(f => {
    const n = { ...f }; if (n[id]) delete n[id]; else n[id] = true
    try { localStorage.setItem(CHAVE_PASSOS, JSON.stringify(n)) } catch { /* sem armazenamento: vale só nesta visita */ }
    return n
  })
  const total = PASSOS.length
  const qtd = PASSOS.filter(p => feitos[p.id]).length
  const prox = PASSOS.find(p => !feitos[p.id])
  const r = 22, c = 2 * Math.PI * r
  return (
    <section aria-label="Comece por aqui" className="flex flex-col gap-3.5 rounded-2xl border border-line bg-surface px-6 py-[22px]">
      <div className="flex items-center gap-3.5">
        <svg width="56" height="56" viewBox="0 0 56 56" role="img" aria-label={`${qtd} de ${total} passos feitos`} className="shrink-0">
          <circle cx="28" cy="28" r={r} fill="none" stroke="var(--raised)" strokeWidth="6" />
          {qtd > 0 && <circle cx="28" cy="28" r={r} fill="none" stroke="var(--royal)" strokeWidth="6" strokeLinecap="round"
            strokeDasharray={`${(qtd / total) * c} ${c}`} transform="rotate(-90 28 28)" />}
          <text x="28" y="33" textAnchor="middle" fill="var(--text)" fontSize="14" fontWeight="700">{qtd}/{total}</text>
        </svg>
        <div className="flex min-w-0 flex-col gap-1">
          <span className="section-label">Comece por aqui</span>
          <b className="text-[15px] leading-snug text-ink">{prox ? `Próximo: ${prox.titulo.toLowerCase()}` : 'Tudo pronto. A MIZAN está configurada.'}</b>
        </div>
      </div>
      <ul className="flex flex-col gap-0.5">
        {PASSOS.map((p, k) => {
          const feito = !!feitos[p.id], eProx = p === prox
          return (
            <li key={p.id} className={`flex items-center gap-3 rounded-xl px-2 py-2.5 ${eProx ? 'bg-[var(--raised)]' : ''}`}>
              <button type="button" onClick={() => marcar(p.id)} aria-pressed={feito} aria-label={feito ? `Desmarcar: ${p.titulo}` : `Marcar como feito: ${p.titulo}`}
                className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-xs font-bold ${feito ? 'border border-[color-mix(in_srgb,var(--success)_40%,transparent)] bg-[var(--success-soft)] text-[var(--success)]' : eProx ? 'bg-[var(--action)] text-white' : 'border-[1.5px] border-[var(--border-strong)] text-ink-3'}`}>
                {feito ? '✓' : k + 1}
              </button>
              <button type="button" onClick={() => navigate(p.rota)} className="flex min-w-0 flex-1 flex-col text-left">
                <span className={`text-sm font-semibold ${feito ? 'text-ink-3 line-through' : 'text-ink'}`}>{p.titulo}</span>
                <span className="text-xs text-ink-3">{p.det}</span>
              </button>
              <span className="shrink-0 text-xs text-ink-3">{p.tempo}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
