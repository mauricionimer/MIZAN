import { useEffect, useRef, useState } from 'react'
import { animate, motion, useInView, useReducedMotion } from 'framer-motion'

/**
 * Peças de gráfico com a animação de entrada da MIZAN (guia, seção 6).
 *
 * Regras: o movimento explica (a barra cresce até o valor, a linha se desenha
 * na ordem do tempo, o número conta até o total). Roda uma vez, quando a peça
 * aparece na tela. Com "reduzir movimento" no sistema, tudo já nasce pronto.
 * Cor sempre por token (var(--royal), var(--success)…), nunca hex solto.
 */

const SAIDA = [0.22, 1, 0.36, 1]

function useEntrou(margem = '-40px') {
  const ref = useRef(null)
  const visto = useInView(ref, { once: true, margin: margem })
  return [ref, visto]
}

/** Barra horizontal fina que cresce até o valor. `listrada` = amostra pequena. */
export function BarraH({ valor = 0, max = 100, cor = 'var(--royal)', altura = 8, listrada = false, atraso = 0, rotulo, className = '' }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou()
  const p = max > 0 ? Math.max(0, Math.min(1, valor / max)) : 0
  const fundo = listrada
    ? `repeating-linear-gradient(135deg, ${cor} 0 6px, color-mix(in srgb, ${cor} 45%, transparent) 6px 10px)`
    : cor
  return (
    <div ref={ref} className={`relative w-full overflow-hidden rounded-full bg-raise-2 ${className}`} style={{ height: altura }}
      role="img" aria-label={rotulo || `${Math.round(p * 100)}%`}>
      <motion.div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${p * 100}%`, background: fundo, transformOrigin: 'left' }}
        initial={reduzir ? false : { scaleX: 0 }} animate={visto || reduzir ? { scaleX: 1 } : { scaleX: 0 }}
        transition={{ duration: 0.9, delay: atraso, ease: SAIDA }} />
    </div>
  )
}

/** Número que conta até o valor. `formatar` recebe o número e devolve o texto. */
export function Contador({ valor = 0, formatar = (n) => Math.round(n).toLocaleString('pt-BR'), duracao = 1.1, className = '' }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou()
  const [atual, setAtual] = useState(reduzir ? valor : 0)
  useEffect(() => {
    if (reduzir || !visto) { if (reduzir) setAtual(valor); return }
    const c = animate(0, valor, { duration: duracao, ease: SAIDA, onUpdate: setAtual })
    return () => c.stop()
  }, [valor, visto, reduzir, duracao])
  return <span ref={ref} className={`tabular-nums ${className}`}>{formatar(atual)}</span>
}

/**
 * Régua de um traço (0–100): ○ onde estava antes, ● onde está agora.
 * O ponto de agora desliza do "antes" (ou do início) até o valor.
 */
export function Regua({ esquerda, direita, antes = null, agora, cor = 'var(--royal)', atraso = 0, rotulo }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou()
  const de = antes ?? 0
  return (
    <div ref={ref} className="w-full">
      <div className="relative h-5" role="img" aria-label={rotulo || `${esquerda} ${agora} de 100, ${direita}${antes != null ? `; antes ${antes}` : ''}`}>
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-raise-2" />
        {/* o quanto mudou desde o primeiro contato: faixa entre o antes e o agora */}
        {antes != null && (
          <span className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full" aria-hidden="true"
            style={{ left: `${Math.min(antes, agora)}%`, width: `${Math.abs(agora - antes)}%`, background: 'var(--border-strong)' }} />
        )}
        {antes != null && (
          <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-surface"
            style={{ left: `${antes}%`, borderColor: 'var(--text-muted)' }} aria-hidden="true" />
        )}
        <motion.span className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full shadow-sm"
          style={{ background: cor, boxShadow: '0 0 0 3px var(--card)' }} aria-hidden="true"
          initial={reduzir ? false : { left: `${de}%`, opacity: 0 }}
          animate={visto || reduzir ? { left: `${agora}%`, opacity: 1 } : { left: `${de}%`, opacity: 0 }}
          transition={{ duration: 1, delay: atraso, ease: SAIDA }} />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-ink-3"><span>{esquerda}</span><span>{direita}</span></div>
    </div>
  )
}

/**
 * Medidor em segmentos: acende da esquerda até o nível, na cor do estado.
 * O resto fica num cinza sóbrio. Usado no estado da plataforma (Ajuda).
 */
export function Medidor({ nivel = 0, cor = 'var(--success)', segmentos = 28, atraso = 0, rotulo }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou()
  const acesos = Math.round((Math.max(0, Math.min(100, nivel)) / 100) * segmentos)
  return (
    <div ref={ref} className="flex h-5 w-full items-stretch gap-[3px]" role="img" aria-label={rotulo || `${nivel}%`}>
      {Array.from({ length: segmentos }, (_, i) => {
        const aceso = i < acesos
        return (
          <motion.span key={i} className="flex-1 rounded-[2px]"
            initial={reduzir ? false : { backgroundColor: 'var(--raised)' }}
            animate={{ backgroundColor: aceso && (visto || reduzir) ? cor : 'var(--raised)' }}
            transition={{ duration: 0.18, delay: reduzir ? 0 : atraso + i * 0.025 }} />
        )
      })}
    </div>
  )
}

/** Linha de SVG que se desenha (use dentro de um <svg>). */
export function LinhaDesenhada({ d, cor = 'var(--royal)', espessura = 2.5, tracejada = false, atraso = 0, ...resto }) {
  const reduzir = useReducedMotion()
  const ref = useRef(null)
  const visto = useInView(ref, { once: true, margin: '-40px' })
  return (
    <motion.path ref={ref} d={d} fill="none" stroke={cor} strokeWidth={espessura} strokeLinecap="round" strokeLinejoin="round"
      strokeDasharray={tracejada ? '5 5' : undefined}
      initial={reduzir || tracejada ? false : { pathLength: 0 }} animate={visto || reduzir || tracejada ? { pathLength: 1 } : { pathLength: 0 }}
      transition={{ duration: 1.4, delay: atraso, ease: SAIDA }} {...resto} />
  )
}

/** Um ponto que aparece com um leve "pop" (bolinhas, células de mapa). */
export function Ponto({ atraso = 0, className = '', style, children, ...resto }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou()
  return (
    <motion.span ref={ref} className={className} style={style} {...resto}
      initial={reduzir ? false : { scale: 0, opacity: 0 }} animate={visto || reduzir ? { scale: 1, opacity: 1 } : { scale: 0, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 380, damping: 22, delay: atraso }}>{children}</motion.span>
  )
}

/** Bloco que sobe e aparece quando entra na tela (seções e cartões). */
export function Aparece({ atraso = 0, className = '', style, children, as = 'div' }) {
  const reduzir = useReducedMotion()
  const [ref, visto] = useEntrou('-60px')
  const M = motion[as] || motion.div
  return (
    <M ref={ref} className={className} style={style} initial={reduzir ? false : { opacity: 0, y: 12 }}
      animate={visto || reduzir ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }} transition={{ duration: 0.5, delay: atraso, ease: SAIDA }}>
      {children}
    </M>
  )
}
