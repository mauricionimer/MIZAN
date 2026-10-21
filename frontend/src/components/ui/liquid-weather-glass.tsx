import React, { useId } from 'react'
import { clsx } from 'clsx'
import './liquid-weather-glass.css'

interface LiquidGlassCardProps {
  children: React.ReactNode
  className?: string
  borderRadius?: string
  blurIntensity?: 'sm' | 'md' | 'lg' | 'xl'
  shadowIntensity?: 'none' | 'xs' | 'sm' | 'md'
  glowIntensity?: 'none' | 'sm' | 'md'
}

// Camadas do componente enviado, adaptadas para cartões de navegação estáveis.
// O filtro atua apenas no fundo: os textos e o botão permanecem nítidos.
export function LiquidGlassCard({ children, className, borderRadius = '22px', blurIntensity = 'xl', shadowIntensity = 'xs', glowIntensity = 'none' }: LiquidGlassCardProps) {
  const filterId = `liquid-glass-${useId().replace(/:/g, '')}`
  const blur = { sm: 4, md: 8, lg: 12, xl: 20 }[blurIntensity]
  const edge = { none: 'none', xs: 'inset 1px 1px 1px rgba(255,255,255,.3), inset -1px -1px 1px rgba(255,255,255,.18)', sm: 'inset 2px 2px 2px rgba(255,255,255,.35), inset -2px -2px 2px rgba(255,255,255,.25)', md: 'inset 3px 3px 3px rgba(255,255,255,.45), inset -3px -3px 3px rgba(255,255,255,.35)' }[shadowIntensity]
  const glow = { none: '0 4px 12px rgba(0,0,0,.08)', sm: '0 4px 12px rgba(0,0,0,.12), 0 0 24px rgba(255,255,255,.1)', md: '0 4px 16px rgba(0,0,0,.15), 0 0 32px rgba(255,255,255,.15)' }[glowIntensity]

  return <div className={clsx('mizan-liquid-glass', className)} style={{ borderRadius }}>
    <svg className="mizan-liquid-glass__defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs><filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" baseFrequency="0.003 0.007" numOctaves="1" result="turbulence" />
        <feDisplacementMap in="SourceGraphic" in2="turbulence" scale="28" xChannelSelector="R" yChannelSelector="G" />
      </filter></defs>
    </svg>
    <div className="mizan-liquid-glass__bend" aria-hidden="true" style={{ backdropFilter: `blur(${blur}px)`, WebkitBackdropFilter: `blur(${blur}px)`, filter: `url(#${filterId})` }} />
    <div className="mizan-liquid-glass__face" aria-hidden="true" style={{ boxShadow: glow }} />
    <div className="mizan-liquid-glass__edge" aria-hidden="true" style={{ boxShadow: edge }} />
    <div className="mizan-liquid-glass__content">{children}</div>
  </div>
}
