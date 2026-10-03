import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Loader2, HelpCircle, ChevronDown, AlertTriangle, Info, BookOpen } from 'lucide-react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { buscarAjuda, indiceDaAjuda, entradaDaAjuda, estadoDoModelo } from '../api'

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

export default function Ajuda() {
  const { token } = useAuth()
  const { result, setVista } = useAnalysis()

  const [pergunta, setPergunta]   = useState('')
  const [busca, setBusca]         = useState(null)     // { certeza, resultados, pergunta }
  const [buscando, setBuscando]   = useState(false)
  const [erro, setErro]           = useState('')
  const [indice, setIndice]       = useState([])
  const [modelo, setModelo]       = useState(null)
  const [abertas, setAbertas]     = useState({})
  const [navegada, setNavegada]   = useState(null)     // entrada aberta pelo índice
  const ultima = useRef(0)
  const [params] = useSearchParams()

  useEffect(() => {
    indiceDaAjuda(token).then(setIndice).catch(() => {})
    estadoDoModelo(token).then(setModelo).catch(() => {})
    // Link de outra tela ("O que é isto?") abre a resposta direto.
    const direto = params.get('id')
    if (direto) {
      entradaDaAjuda(token, direto).then(e => { setNavegada(e); setAbertas({ [e.id]: true }) }).catch(() => {})
    }
  }, [token])

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
            A busca é feita aqui, no servidor do Mizan, e a sua pergunta não é guardada.
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
