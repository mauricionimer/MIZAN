/**
 * Marca do Mizan — gráfico ascendente.
 *
 * Três barras inclinadas subindo, em degradê de azul. Especificação em
 * design/MIZAN_REDESIGN.md (seção 4) e design/MizanLogo.tsx — convertido
 * para JSX porque o projeto não usa TypeScript.
 */
export function LogoMark({ className = 'h-5 w-5', size, title = 'Mizan' }) {
  const dim = size ? { width: size, height: size } : undefined
  return (
    <svg
      viewBox="0 0 30 30"
      className={size ? undefined : className}
      style={dim}
      role="img"
      aria-label={title}
    >
      <polygon points="6.5,15 11.5,15 9,27 4,27" fill="#b8c0ee" />
      <polygon points="13.5,9 18.5,9 16,27 11,27" fill="#8f9be9" />
      <polygon points="20.5,3 25.5,3 23,27 18,27" fill="#5966d9" />
    </svg>
  )
}

/** Alias: o símbolo é chamado de MizanMark no material de design. */
export const MizanMark = LogoMark

/** Símbolo + wordmark. O wordmark é só a fonte display, peso 700. */
export default function Logo({ size = 28, gap = 10, wordmark = true, className = '', wordClassName = '' }) {
  return (
    <span className={`inline-flex items-center ${className}`} style={{ gap }}>
      <LogoMark size={size} />
      {wordmark && (
        <span
          className={wordClassName}
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: size * 1.05,
            letterSpacing: '-0.03em',
            lineHeight: 1,
            color: 'currentColor',
          }}
        >
          Mizan
        </span>
      )}
    </span>
  )
}
