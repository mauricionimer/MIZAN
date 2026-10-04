import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { resumoAgenda } from '../api'

/**
 * F2 — o número do item Agenda no menu: compromissos em nível alto + médio.
 * Atualiza a cada abertura de página (no máximo uma consulta por minuto) e na
 * hora em que a agenda muda nesta aba (evento `mizan:agenda`).
 */
const cache = { chave: null, em: 0, valor: { alto: 0, medio: 0 } }

export default function useAvisoAgenda() {
  const { token, isAdmin, isComando } = useAuth()
  const chave = token && !isComando ? `${token}:${isAdmin ? 'equipe' : 'minha'}` : null
  const [valor, setValor] = useState(cache.chave === chave ? cache.valor : { alto: 0, medio: 0 })

  useEffect(() => {
    if (!chave) return
    let vivo = true
    const buscar = (forcar) => {
      if (!forcar && cache.chave === chave && Date.now() - cache.em < 60_000) { setValor(cache.valor); return }
      resumoAgenda({ escopo: isAdmin ? 'equipe' : 'minha' })
        .then(r => {
          cache.chave = chave; cache.em = Date.now(); cache.valor = { alto: r.alto || 0, medio: r.medio || 0 }
          if (vivo) setValor(cache.valor)
        })
        .catch(() => {})
    }
    buscar(false)
    const mudou = () => buscar(true)
    window.addEventListener('mizan:agenda', mudou)
    return () => { vivo = false; window.removeEventListener('mizan:agenda', mudou) }
  }, [chave, isAdmin])

  return valor
}
