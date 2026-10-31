import { useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { consultarMudancas } from '../api'

/**
 * Telas ao vivo. A cada 2 s (só com a aba visível), pergunta ao servidor a versão de
 * cada assunto — uma consulta levíssima, sem banco. Quando uma muda (o agente remarcou
 * uma reunião, outra pessoa resolveu um compromisso…), avisa as telas abertas pelos
 * mesmos eventos que elas já escutam (`mizan:agenda`, `mizan:casos`), com
 * `detail.origem = 'servidor'`. Cada tela recarrega só o que é dela, sem piscar.
 */
const EVENTOS = { agenda: 'mizan:agenda', casos: 'mizan:casos' }
const INTERVALO_MS = 2000

export default function useMudancasDoServidor() {
  const { token } = useAuth()
  useEffect(() => {
    if (!token) return
    let vivo = true, ultimo = null, ocupado = false
    const checar = async () => {
      if (ocupado || document.hidden) return
      ocupado = true
      try {
        const v = await consultarMudancas()
        if (!vivo || !v) return
        if (ultimo) {
          for (const [topico, evento] of Object.entries(EVENTOS)) {
            if (v[topico] && v[topico] !== ultimo[topico]) {
              window.dispatchEvent(new CustomEvent(evento, { detail: { origem: 'servidor' } }))
            }
          }
        }
        ultimo = v
      } catch { /* a próxima volta tenta de novo */ } finally { ocupado = false }
    }
    checar()
    const t = setInterval(checar, INTERVALO_MS)
    const voltou = () => { if (!document.hidden) checar() }
    document.addEventListener('visibilitychange', voltou)
    window.addEventListener('focus', voltou)
    return () => {
      vivo = false
      clearInterval(t)
      document.removeEventListener('visibilitychange', voltou)
      window.removeEventListener('focus', voltou)
    }
  }, [token])
}

/** Chama `recarregar` quando o servidor avisa que `topico` mudou. */
export function useAoMudarNoServidor(topico, recarregar) {
  useEffect(() => {
    const ouvir = (e) => { if (e?.detail?.origem === 'servidor') recarregar() }
    window.addEventListener(EVENTOS[topico], ouvir)
    return () => window.removeEventListener(EVENTOS[topico], ouvir)
  }, [topico, recarregar])
}
