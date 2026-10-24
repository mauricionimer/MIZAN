import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Undo2, Loader2, Check, X } from 'lucide-react'
import { classificarErro } from '../api'

const DURACAO_MS = 8000

/**
 * Aviso fixo no rodapé da tela depois de uma ação que pode ser desfeita
 * ("Promessa marcada como não paga · Desfazer"). Fica visível mesmo com a
 * página rolada e no celular. Some sozinho em 8 s; "Desfazer" chama
 * `aviso.desfazer()` (que deve reverter no servidor) e não dispara duas vezes.
 *
 * `aviso`: { id, texto, desfeito?, desfazer?: async () => void, acao?: { rotulo, onClick } } | null
 * Sem `desfazer`, é só a confirmação do que foi feito. `acao` é o próximo passo
 * natural ("Registrar pagamento") e fecha o aviso ao ser usada.
 */
export default function AvisoDesfazer({ aviso, onFechar }) {
  const [estado, setEstado] = useState('aberto')    // aberto | desfazendo | desfeito | erro
  const [erro, setErro] = useState('')
  const timer = useRef(null)

  useEffect(() => {
    if (!aviso) return
    setEstado('aberto'); setErro('')
    clearTimeout(timer.current)
    timer.current = setTimeout(onFechar, DURACAO_MS)
    return () => clearTimeout(timer.current)
  }, [aviso?.id])        // eslint-disable-line react-hooks/exhaustive-deps

  async function desfazer() {
    if (estado !== 'aberto') return
    clearTimeout(timer.current)
    setEstado('desfazendo')
    try {
      await aviso.desfazer()
      setEstado('desfeito')
      timer.current = setTimeout(onFechar, 2500)
    } catch (e) {
      setEstado('erro'); setErro(classificarErro(e).mensagem)
      timer.current = setTimeout(onFechar, 7000)
    }
  }

  return createPortal(
    <AnimatePresence>
      {aviso && (
        <motion.div key={aviso.id} role="status" aria-live="polite"
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 24 }}
          className={`fixed inset-x-3 bottom-4 z-[60] mx-auto ${aviso.acao ? 'max-w-xl' : 'max-w-lg'} overflow-hidden rounded-xl shadow-2xl`}
          style={{ background: 'var(--ink)', color: 'var(--surface)' }}>
          <div className="flex items-center gap-3 px-4 py-3">
            {estado === 'desfeito' || !aviso.desfazer ? <Check className="h-4 w-4 shrink-0" /> : null}
            <p className="min-w-0 flex-1 text-sm">
              {estado === 'desfeito' ? (aviso.desfeito || 'Desfeito.') : estado === 'erro' ? erro : aviso.texto}
            </p>
            {aviso.acao && estado === 'aberto' && (
              <button type="button" onClick={() => { aviso.acao.onClick(); onFechar() }}
                className="inline-flex min-h-[40px] shrink-0 items-center rounded-lg px-3 text-sm font-bold"
                style={{ background: 'rgb(255 255 255 / 0.14)' }}>
                {aviso.acao.rotulo}
              </button>
            )}
            {aviso.desfazer && (estado === 'aberto' || estado === 'desfazendo') && (
              <button type="button" onClick={desfazer} disabled={estado === 'desfazendo'}
                className="inline-flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-lg px-3 text-sm font-bold disabled:opacity-60"
                style={{ background: 'rgb(255 255 255 / 0.14)' }}>
                {estado === 'desfazendo' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Undo2 className="h-4 w-4" />}
                Desfazer
              </button>
            )}
            <button type="button" onClick={onFechar} aria-label="Fechar aviso" className="shrink-0 rounded p-1.5 opacity-70 hover:opacity-100">
              <X className="h-4 w-4" />
            </button>
          </div>
          {estado === 'aberto' && (
            <motion.div initial={{ width: '100%' }} animate={{ width: '0%' }} transition={{ duration: DURACAO_MS / 1000, ease: 'linear' }}
              className="h-0.5" style={{ background: 'rgb(255 255 255 / 0.5)' }} />
          )}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body)
}
