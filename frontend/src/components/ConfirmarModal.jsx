import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'

/**
 * Confirmação própria do Mizan (no lugar do confirm() do navegador).
 * - Esc ou clique fora = cancelar (a opção segura).
 * - O foco abre no botão seguro e fica preso no modal; volta ao elemento que
 *   abriu quando fecha.
 */
export default function ConfirmarModal({ aberto, titulo, texto, confirmar = 'Confirmar', cancelar = 'Cancelar',
                                         perigo = false, onConfirmar, onCancelar }) {
  const caixa = useRef(null)
  const seguro = useRef(null)
  const anterior = useRef(null)

  useEffect(() => {
    if (!aberto) return
    anterior.current = document.activeElement
    const t = setTimeout(() => seguro.current?.focus(), 30)
    const tecla = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onCancelar() }
      if (e.key === 'Tab' && caixa.current) {
        const foc = [...caixa.current.querySelectorAll('button')]
        if (!foc.length) return
        const i = foc.indexOf(document.activeElement)
        if (e.shiftKey && i <= 0) { e.preventDefault(); foc[foc.length - 1].focus() }
        else if (!e.shiftKey && i === foc.length - 1) { e.preventDefault(); foc[0].focus() }
      }
    }
    window.addEventListener('keydown', tecla, true)
    return () => {
      clearTimeout(t)
      window.removeEventListener('keydown', tecla, true)
      anterior.current?.focus?.()
    }
  }, [aberto])        // eslint-disable-line react-hooks/exhaustive-deps

  return createPortal(
    <AnimatePresence>
      {aberto && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onCancelar}>
          <motion.div ref={caixa} initial={{ y: 10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 10, opacity: 0 }}
            role="alertdialog" aria-modal="true" aria-labelledby="confirmar-titulo" aria-describedby="confirmar-texto"
            onClick={e => e.stopPropagation()}
            className="w-full max-w-sm rounded-2xl p-5 shadow-2xl" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: perigo ? 'var(--danger)' : 'var(--warning)' }} aria-hidden="true" />
              <div>
                <h2 id="confirmar-titulo" className="text-base font-bold" style={{ color: 'var(--ink)' }}>{titulo}</h2>
                {texto && <p id="confirmar-texto" className="mt-1 text-sm" style={{ color: 'var(--ink-2)' }}>{texto}</p>}
              </div>
            </div>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button ref={seguro} type="button" onClick={onCancelar}
                className="min-h-[44px] rounded-lg px-4 text-sm font-semibold"
                style={{ border: '1px solid var(--line)', color: 'var(--ink)', background: 'var(--surface)' }}>
                {cancelar}
              </button>
              <button type="button" onClick={onConfirmar}
                className={`min-h-[44px] rounded-lg px-4 text-sm font-semibold text-white ${perigo ? 'bg-red-600 hover:bg-red-500' : 'bg-blue-600 hover:bg-blue-500'}`}>
                {confirmar}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body)
}
