import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { novidadesDeDuvidas, listarDuvidasComando } from '../api'

/**
 * Os números que acendem o menu: respostas novas esperando por quem perguntou
 * (todos os perfis) e dúvidas abertas esperando o COMANDO.
 *
 * Uma consulta por abertura de página, no máximo uma por minuto: é um aviso,
 * não um canal em tempo real, e não pode pesar no banco a cada clique.
 */
const cache = { token: null, em: 0, valor: { respostas: 0, abertas: 0 } }

export function atualizarAvisosDeDuvida() { cache.em = 0 }

export default function useAvisosDeDuvida() {
  const { token, isComando } = useAuth()
  const [valor, setValor] = useState(cache.token === token ? cache.valor : { respostas: 0, abertas: 0 })

  useEffect(() => {
    if (!token) return
    if (cache.token === token && Date.now() - cache.em < 60_000) { setValor(cache.valor); return }
    let vivo = true
    Promise.all([
      novidadesDeDuvidas(token).then(r => r.respondidas_nao_vistas || 0).catch(() => 0),
      isComando ? listarDuvidasComando(token, { estado: 'aberta', limite: 1 }).then(r => r.abertas || 0).catch(() => 0) : Promise.resolve(0),
    ]).then(([respostas, abertas]) => {
      cache.token = token; cache.em = Date.now(); cache.valor = { respostas, abertas }
      if (vivo) setValor(cache.valor)
    })
    return () => { vivo = false }
  }, [token, isComando])

  return valor
}
