// Título de um bloco que começa fechado: o clique abre e fecha o conteúdo.
import { ChevronDown } from 'lucide-react'

export default function TituloRecolhivel({ aberto, onAlternar, children, resumo, className = '' }) {
  return (
    <button type="button" onClick={onAlternar} aria-expanded={aberto}
      className={`flex min-h-[40px] min-w-0 flex-1 items-center gap-2 text-left ${className}`}>
      {children}
      {!aberto && resumo && <span className="truncate text-xs font-normal normal-case tracking-normal" style={{ color: 'var(--ink-3)' }}>{resumo}</span>}
      <ChevronDown className={`ml-auto h-4 w-4 shrink-0 transition-transform ${aberto ? 'rotate-180' : ''}`}
        style={{ color: 'var(--ink-3)' }} aria-hidden="true" />
    </button>
  )
}
