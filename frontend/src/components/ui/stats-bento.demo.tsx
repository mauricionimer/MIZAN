import StatsBento, { BentoStat } from '@/components/ui/stats-bento'

// Valores recebidos pela aplicação; sem indicadores fictícios na interface.
export default function StatsBentoDemo({ stats }: { stats: { label: string; value: string | number; nota?: string }[] }) {
  return <StatsBento aria-label="Prévia de indicadores">
    {stats.map(stat => <BentoStat key={stat.label} {...stat} />)}
  </StatsBento>
}
