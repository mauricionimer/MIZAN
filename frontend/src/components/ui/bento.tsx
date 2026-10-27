import React from "react"
import { Link } from "react-router-dom"
import { clsx } from "clsx"
import { motion } from "framer-motion"
import { prepararPagina } from '../../lib/paginas'

export { AgendaBentoCard } from './agenda-bento-card'

// Bloco do hub de entrada. Adaptado do bento do 21st.dev: card com arte em cima,
// texto embaixo e leve elevação ao passar o mouse. Aqui o card é um link (vai
// para a área) e as cores vêm das variáveis do tema, nos modos claro e escuro.

export interface BentoCardProps {
  to: string
  eyebrow: React.ReactNode
  title: React.ReactNode
  description: React.ReactNode
  /** Arte do topo do card. */
  graphic?: React.ReactNode
  /** Pílula opcional no canto (ex.: compromissos vencidos). */
  badge?: React.ReactNode
  className?: string
  /** Chamado ao clicar; chame e.preventDefault() para assumir a navegação. */
  onNavigate?: (e: React.MouseEvent) => void
  /** Mostra um indicador de carregamento no canto. */
  loading?: boolean
}

export function BentoCard({ to, eyebrow, title, description, graphic, badge, className = "", onNavigate, loading }: BentoCardProps) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 380, damping: 30 }}
      className={clsx("hub-card group relative flex flex-col overflow-hidden transform-gpu", className)}
    >
      <Link to={to} onClick={onNavigate} onPointerEnter={() => prepararPagina(to)} onFocus={() => prepararPagina(to)}
        className="flex h-full flex-col focus:outline-none" aria-label={`${eyebrow}: ${title}`}>
        <div className="hub-card-arte relative shrink-0">
          {graphic}
          {loading && <span className="hub-card-badge absolute right-4 top-4 z-10" role="status">Abrindo…</span>}
          {badge && !loading && <span className="hub-card-badge absolute right-4 top-4 z-10">{badge}</span>}
        </div>
        <div className="hub-card-texto relative z-10">
          <p className="hub-card-eyebrow">{eyebrow}</p>
          <p className="hub-card-titulo">{title}</p>
          <p className="hub-card-desc">{description}</p>
        </div>
      </Link>
    </motion.div>
  )
}

export function BentoGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">{children}</div>
}
