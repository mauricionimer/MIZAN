import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import useModal from './useModal'
import FluxoDevedor from './FluxoDevedor'

export default function FluxoDevedorModal({ devedor, onFechar, onVerCaso }) {
  const caixa = useModal(!!devedor, onFechar)
  if (!devedor) return null
  return createPortal(<div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-3 sm:p-6" onClick={onFechar}>
    <div ref={caixa} role="dialog" aria-modal="true" aria-labelledby="fluxo-devedor-titulo" className="my-auto w-full max-w-5xl rounded-2xl border border-line bg-canvas p-3 shadow-2xl sm:p-5" onClick={e => e.stopPropagation()}>
      <header className="mb-4 flex items-start justify-between gap-3">
        <div><h2 id="fluxo-devedor-titulo" className="text-lg font-semibold text-ink">{devedor.nome || 'Devedor'}</h2><p className="mt-1 text-xs text-ink-2">Fluxo de acompanhamento</p></div>
        <button type="button" onClick={onFechar} aria-label="Fechar fluxo do devedor" className="btn-ghost min-h-[40px] min-w-[40px]"><X size={18} /></button>
      </header>
      <FluxoDevedor predicaoId={devedor.id} />
      <footer className="mt-4 flex flex-wrap justify-end gap-2"><button type="button" className="btn-secondary btn-sm" onClick={() => onVerCaso(devedor)}>Ver conversa dos agentes</button><button type="button" className="btn-primary btn-sm" onClick={onFechar}>Fechar</button></footer>
    </div>
  </div>, document.body)
}
