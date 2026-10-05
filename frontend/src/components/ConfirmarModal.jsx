import { useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import useModal from './useModal'

/**
 * Confirmação própria do Mizan (no lugar do confirm() do navegador).
 * - Esc ou clique fora = cancelar (a opção segura, que recebe o foco primeiro).
 * - Ação destrutiva (`perigo`): botão de confirmar em vermelho sólido.
 */
export default function ConfirmarModal({ aberto, titulo, texto, confirmar = 'Confirmar', cancelar = 'Cancelar',
                                         perigo = false, onConfirmar, onCancelar }) {
  const caixa = useModal(aberto, onCancelar, { focoInicial: '[data-seguro]' })
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
              <button type="button" data-seguro onClick={onCancelar} className="btn-secondary min-h-[44px]">{cancelar}</button>
              <button type="button" onClick={onConfirmar} className={`${perigo ? 'btn-danger' : 'btn-primary'} min-h-[44px]`}>{confirmar}</button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body)
}

/**
 * Confirmação por promessa, para trocar `window.confirm` sem reescrever o fluxo:
 *
 *   const { pedir, modal } = useConfirmar()
 *   if (!(await pedir({ titulo, texto, confirmar: 'Excluir', perigo: true }))) return
 *   …  // e, no JSX: {modal}
 */
export function useConfirmar() {
  const [aberto, setAberto] = useState(false)
  const [cfg, setCfg] = useState({})          // fica guardada: o texto não some durante a animação de saída
  const resolver = useRef(null)
  const pedir = useCallback((opcoes) => new Promise(res => { resolver.current = res; setCfg(opcoes); setAberto(true) }), [])
  const fechar = (ok) => { const r = resolver.current; resolver.current = null; setAberto(false); r?.(ok) }
  const modal = (
    <ConfirmarModal aberto={aberto} titulo={cfg.titulo} texto={cfg.texto} confirmar={cfg.confirmar}
      cancelar={cfg.cancelar} perigo={cfg.perigo} onConfirmar={() => fechar(true)} onCancelar={() => fechar(false)} />
  )
  return { pedir, modal }
}
