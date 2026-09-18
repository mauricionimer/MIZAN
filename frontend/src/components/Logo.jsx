/**
 * Marca do Mizan: três barras decrescentes — a carteira priorizada, que é o
 * que o produto faz. Usa var(--brand) para acompanhar a cor da empresa no
 * modo white-label.
 */
export function LogoMark({ className = 'h-4 w-4' }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect x="1" y="2.5"  width="14" height="2.6" rx="1.3" fill="var(--brand)" />
      <rect x="1" y="6.7"  width="9.5" height="2.6" rx="1.3" fill="var(--brand)" opacity="0.6" />
      <rect x="1" y="10.9" width="5"  height="2.6" rx="1.3" fill="var(--brand)" opacity="0.3" />
    </svg>
  )
}

export default function Logo({ wordmark = true, className = '' }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <LogoMark className="h-4 w-4 shrink-0" />
      {wordmark && (
        <span className="font-semibold text-white text-sm tracking-tight">Mizan</span>
      )}
    </div>
  )
}
