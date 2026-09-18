/**
 * Marca do Mizan.
 *
 * Um ponto e as ondas que ele propaga: cada contato registrado reverbera no
 * modelo e volta como recomendação. O eixo simétrico remete a "mizan" (ميزان),
 * balança/equilíbrio em árabe — a origem do nome.
 *
 * Usa currentColor, então herda a cor do contexto.
 */
export function LogoMark({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="3.3" fill="currentColor" />
      <circle cx="12" cy="12" r="7.3" stroke="currentColor" strokeWidth="1.9"
        strokeDasharray="34 12" strokeLinecap="round" transform="rotate(-120 12 12)" />
      <circle cx="12" cy="12" r="11" stroke="currentColor" strokeWidth="1.9" opacity="0.3"
        strokeDasharray="50 19" strokeLinecap="round" transform="rotate(-120 12 12)" />
    </svg>
  )
}

export default function Logo({ wordmark = true, className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`} style={{ color: 'var(--brand)' }}>
      <LogoMark className="h-5 w-5 shrink-0" />
      {wordmark && (
        <span className="font-semibold text-[15px] tracking-tight" style={{ color: 'var(--text-1)' }}>
          Mizan
        </span>
      )}
    </div>
  )
}

/**
 * Textura de ondas concêntricas para as telas de entrada.
 * Puramente decorativa — opacidade baixa, sem interferir na leitura.
 */
export function RippleBackdrop({ className = '' }) {
  const aneis = Array.from({ length: 11 }, (_, i) => 60 + i * 78)
  return (
    <svg
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      viewBox="0 0 1200 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true"
    >
      <g fill="none" stroke="var(--brand)" strokeWidth="1">
        {aneis.map((r, i) => (
          <ellipse key={r} cx="300" cy="760" rx={r} ry={r * 0.42}
            opacity={0.16 - i * 0.012} />
        ))}
      </g>
    </svg>
  )
}
