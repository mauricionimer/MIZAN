import { useState, useEffect } from 'react'

/**
 * Atrasa um valor até ele parar de mudar.
 *
 * A busca da tabela agora vai ao servidor. Sem isto, digitar "Maria" dispararia
 * cinco requisições e a última a chegar poderia não ser a da palavra inteira.
 */
export function useDebounce(valor, ms = 300) {
  const [adiado, setAdiado] = useState(valor)
  useEffect(() => {
    const id = setTimeout(() => setAdiado(valor), ms)
    return () => clearTimeout(id)
  }, [valor, ms])
  return adiado
}
