import { useState, useEffect, useRef, useId } from 'react'
import { useNavigate } from 'react-router-dom'
import { HelpCircle, Loader2, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { indiceDaAjuda, entradaDaAjuda } from '../api'

/**
 * O "?" ao lado de uma métrica: abre a resposta curta da Central de Ajuda ali
 * mesmo, com o caminho para a explicação completa.
 *
 * Só aparece se o perfil de quem está logado puder ver aquela resposta: o
 * índice da ajuda (uma consulta por sessão) diz quais. Assim o operador não vê
 * um "?" que leva a uma explicação de tela que ele não tem.
 */

// Um cache por sessão. A chave é o token: trocar de usuário descarta tudo.
const cache = { token: null, ids: null, pendente: null, entradas: new Map() }

function indiceVisivel(token) {
  if (cache.token !== token) {
    cache.token = token; cache.ids = null; cache.pendente = null; cache.entradas = new Map()
  }
  if (cache.ids) return Promise.resolve(cache.ids)
  if (!cache.pendente) {
    cache.pendente = indiceDaAjuda(token)
      .then(grupos => { cache.ids = new Set(grupos.flatMap(g => g.entradas.map(e => e.id))); return cache.ids })
      .catch(() => { cache.pendente = null; return new Set() })       // sem índice, nenhum "?"
  }
  return cache.pendente
}

export default function DicaAjuda({ id, className = '' }) {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [visivel, setVisivel] = useState(false)
  const [aberta, setAberta]   = useState(false)
  const [entrada, setEntrada] = useState(null)
  const [erro, setErro]       = useState(false)
  const [alinhaDireita, setAlinhaDireita] = useState(false)
  const raiz = useRef(null)
  const titulo = useId()

  useEffect(() => {
    let vivo = true
    indiceVisivel(token).then(ids => { if (vivo) setVisivel(ids.has(id)) })
    return () => { vivo = false }
  }, [token, id])

  useEffect(() => {
    if (!aberta) return
    const fora = (e) => { if (raiz.current && !raiz.current.contains(e.target)) setAberta(false) }
    const esc  = (e) => { if (e.key === 'Escape') setAberta(false) }
    document.addEventListener('mousedown', fora)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', fora); document.removeEventListener('keydown', esc) }
  }, [aberta])

  if (!visivel) return null

  async function alternar(e) {
    e.stopPropagation()                  // o "?" pode estar dentro de um cabeçalho clicável
    if (aberta) { setAberta(false); return }
    const r = raiz.current?.getBoundingClientRect()
    setAlinhaDireita(!!r && r.left > window.innerWidth / 2)
    setAberta(true); setErro(false)
    if (cache.entradas.has(id)) { setEntrada(cache.entradas.get(id)); return }
    try {
      const d = await entradaDaAjuda(token, id)
      cache.entradas.set(id, d); setEntrada(d)
    } catch { setErro(true) }
  }

  return (
    <span ref={raiz} className={`relative inline-flex align-middle ${className}`}>
      <button type="button" onClick={alternar} aria-expanded={aberta} aria-label="O que é isto?"
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full text-ink-3 transition-colors hover:text-blue-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      {aberta && (
        <span role="dialog" aria-labelledby={titulo}
          // No celular vira uma folha na parte de baixo da tela (um balão ao lado
          // de um "?" no canto sairia da tela); de tablet para cima, balão ancorado.
          className={`fixed inset-x-4 bottom-4 z-50 rounded-xl border border-line bg-surface p-4 text-left normal-case tracking-normal shadow-xl sm:absolute sm:inset-x-auto sm:bottom-auto sm:top-6 sm:w-72 ${alinhaDireita ? 'sm:right-0' : 'sm:left-0'}`}
          onClick={e => e.stopPropagation()}>
          <button type="button" onClick={() => setAberta(false)} aria-label="Fechar"
            className="absolute right-2 top-2 text-ink-3 hover:text-ink"><X className="h-3.5 w-3.5" /></button>
          {!entrada && !erro && <span className="flex items-center gap-2 text-xs text-ink-3"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando…</span>}
          {erro && <span className="text-xs text-ink-2">Não consegui carregar a explicação agora.</span>}
          {entrada && (
            <>
              <span id={titulo} className="block pr-5 text-sm font-semibold text-ink">{entrada.titulo}</span>
              <span className="mt-1.5 block text-xs font-normal leading-relaxed text-ink-2">{entrada.curta}</span>
              {entrada.em_revisao && (
                <span className="mt-2 block text-[11px] font-normal text-ink-3">Esta resposta pode mudar: há uma decisão pendente.</span>
              )}
              <button type="button" onClick={() => navigate(`/ajuda?id=${encodeURIComponent(id)}`)}
                className="mt-3 text-xs font-medium text-blue-400 hover:text-blue-300">
                Ver a explicação completa →
              </button>
            </>
          )}
        </span>
      )}
    </span>
  )
}
