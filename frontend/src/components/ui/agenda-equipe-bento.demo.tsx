import React from 'react'
import StatsBento, { type StatsBentoProps } from './agenda-equipe-bento'

// A prévia recebe os mesmos dados reais e a ação de navegação da Agenda.
export default function StatsBentoDemo(props: StatsBentoProps) {
  return <StatsBento {...props} />
}
