import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight, type LucideIcon } from 'lucide-react'
import './agenda-bento-card.css'

export interface AgendaBentoCardProps {
  nome: string
  total: number
  descricao?: string
  legenda?: string
  acao?: string
  icone?: LucideIcon
  onAbrir: () => void
}

const numero = (n: number) => new Intl.NumberFormat('pt-BR').format(n)

// Adaptação do BentoCard enviado: área visual e conteúdo sobreposto.
// Todos os cartões mantêm as mesmas dimensões, sem colunas em destaque.
export function AgendaBentoCard({ nome, total, descricao, legenda = 'compromissos pendentes', acao = 'Ver agenda', icone: Icone, onAbrir }: AgendaBentoCardProps) {
  const reduzir = useReducedMotion()
  const iniciais = (nome || '?').split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase()
  return <motion.button type="button" onClick={onAbrir} className="agenda-bento-card"
    whileHover={reduzir ? undefined : { y: -3 }} transition={{ duration: .18 }}
    aria-label={`Abrir ${nome}, ${numero(total)} ${legenda}`}>
    <span className="agenda-bento-card__graphic" aria-hidden="true">
      <span className="agenda-bento-card__folhas"><span /><span /><span /></span>
      <span className="agenda-bento-card__topo">
        <span className="agenda-bento-card__avatar">{Icone ? <Icone size={22} /> : iniciais}</span>
        <ArrowUpRight size={20} />
      </span>
      <span className="agenda-bento-card__total">{numero(total)}</span>
      <span className="agenda-bento-card__unidade">{legenda}</span>
    </span>
    <span className="agenda-bento-card__content">
      <span className="agenda-bento-card__title">{nome}</span>
      {descricao && <span className="agenda-bento-card__description">{descricao}</span>}
      <span className="agenda-bento-card__action">{acao} <ArrowUpRight size={14} aria-hidden="true" /></span>
    </span>
  </motion.button>
}
