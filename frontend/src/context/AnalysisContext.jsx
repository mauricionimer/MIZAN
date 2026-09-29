import { createContext, useContext, useState, useEffect, useRef } from 'react'
import { carregarCarteira } from '../api'

const Ctx = createContext(null)
const CHAVE_ANALISE = 'mizan_analysis'
const CHAVE_ID      = 'mizan_analysis_id'

/**
 * A análise aberta, e como ela sobrevive a um F5.
 *
 * Antes a análise inteira ia para o sessionStorage, dentro de um try/catch
 * vazio. O sessionStorage tem cota de ~5 MB por origem e uma linha do ranking
 * ocupa 581 bytes em JSON, então a gravação começava a falhar em 8.906
 * devedores — medido no navegador, não estimado. Acima disso o catch engolia o
 * erro, tudo parecia funcionar, e a análise sumia no primeiro recarregamento.
 * Carteira de banco passa desse número em dez vezes.
 *
 * Agora o que persiste é o identificador da carteira, que ocupa dezenas de
 * bytes e não tem teto. No recarregamento a análise volta do servidor. A
 * cópia inteira continua sendo gravada quando cabe, porque aí a volta é
 * instantânea e não custa uma requisição — mas ela virou otimização, não o
 * mecanismo: se não couber, o identificador sozinho dá conta.
 */
export function AnalysisProvider({ children }) {
  const [result, setResultState] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(CHAVE_ANALISE)) } catch { return null }
  })

  // Sem isto, o recarregamento de uma carteira grande piscaria a tela de
  // "carregar carteira" antes de o servidor responder — como se a análise
  // tivesse se perdido, que é justamente o que deixou de acontecer.
  const [restaurando, setRestaurando] = useState(() => {
    try {
      return !sessionStorage.getItem(CHAVE_ANALISE) && !!sessionStorage.getItem(CHAVE_ID)
    } catch { return false }
  })

  // Qual vista da tela única está aberta ("analise" ou "dashboard"). Fica
  // aqui, e não na página, para sobreviver a uma ida às telas que ainda têm
  // rota própria — o usuário volta onde estava.
  const [vista, setVista] = useState(null)

  // A restauração em curso, por carteira. Em desenvolvimento o StrictMode monta,
  // desmonta e remonta: guardar a promessa (em vez de um "já rodou") faz a
  // segunda passada aproveitar a mesma requisição em vez de disparar outra —
  // e, principalmente, faz o resultado chegar a quem ainda está montado.
  const restauracao = useRef({ id: null, promessa: null })

  function setResult(val) {
    setResultState(val)
    if (!val) {
      try {
        sessionStorage.removeItem(CHAVE_ANALISE)
        sessionStorage.removeItem(CHAVE_ID)
      } catch { /* sem armazenamento, o estado em memória basta */ }
      return
    }
    const id = val?.resumo?.carteira_id ?? val?.carteira_id ?? null
    try {
      if (id) sessionStorage.setItem(CHAVE_ID, String(id))
      sessionStorage.setItem(CHAVE_ANALISE, JSON.stringify(val))
    } catch {
      // Não coube: o identificador sozinho é o que garante a volta. Limpa a
      // cópia antiga para não restaurar a carteira errada no próximo F5.
      try { sessionStorage.removeItem(CHAVE_ANALISE) } catch { /* idem */ }
    }
  }

  // Recarregou com carteira grande: a cópia não cabia, mas o identificador
  // está lá. Busca de volta em vez de mandar o usuário analisar tudo de novo.
  useEffect(() => {
    if (result) { setRestaurando(false); return }
    let id = null
    try { id = sessionStorage.getItem(CHAVE_ID) } catch { /* sem armazenamento */ }
    if (!id) { setRestaurando(false); return }

    let vivo = true
    setRestaurando(true)
    if (restauracao.current.id !== id) {
      restauracao.current = { id, promessa: carregarCarteira(id) }
    }
    restauracao.current.promessa
      .then(dados => { if (vivo && dados) setResultState(dados) })
      .catch(() => {
        // Carteira apagada, sessão expirada, servidor fora: cai na tela de
        // análise, que é o destino certo quando não há o que restaurar.
        restauracao.current = { id: null, promessa: null }
        try { sessionStorage.removeItem(CHAVE_ID) } catch { /* idem */ }
      })
      .finally(() => { if (vivo) setRestaurando(false) })
    return () => { vivo = false }
  }, [result])

  useEffect(() => {
    const clear = () => {
      setResultState(null)
      setVista(null)
      setRestaurando(false)
      try {
        sessionStorage.removeItem(CHAVE_ANALISE)
        sessionStorage.removeItem(CHAVE_ID)
      } catch { /* sem armazenamento */ }
    }
    window.addEventListener('mizan:logout', clear)
    return () => window.removeEventListener('mizan:logout', clear)
  }, [])

  return (
    <Ctx.Provider value={{ result, setResult, vista, setVista, restaurando }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAnalysis = () => useContext(Ctx)
