import { GlassFold } from './ui/glass-fold'
import { useTheme } from '../context/ThemeContext'

/**
 * Fundo de ondas das telas de trabalho: o mesmo GlassFold da entrada, só que
 * como pano de fundo. Bem mais lento, desenhado em baixa resolução, com um
 * desfoque grande e pouca opacidade, mantendo as cores da marca. Fica atrás
 * de tudo (z-index negativo dentro do shell) e não recebe cliques.
 */
export default function FundoOndas() {
  const { claro } = useTheme()
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <GlassFold
        className="fundo-ondas"
        light={claro}
        color1={claro ? '#a9b4f5' : '#5966d9'}
        color2={claro ? '#f1eeff' : '#1a0033'}
        color3={claro ? '#ffffff' : '#b8c0ee'}
        speed={0.08}
        noise={0}
        resolution={0.3}
      />
    </div>
  )
}
