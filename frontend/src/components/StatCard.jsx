// Adaptador dos indicadores existentes para o sistema bento compartilhado.
// O contexto da grade define a hierarquia; fora dela, usa um cartão compacto.
import { BentoStat, useVarianteKpi } from './ui/stats-bento'

const ACCENT = {
  default: 'var(--text-muted)',
  blue:    'var(--royal)',
  emerald: 'var(--success)',
  amber:   'var(--warning)',
  violet:  'var(--accent-text)',
}

export default function StatCard({
  label, value, icon: Icon, accent = 'default',
  cor, corClasse,       // cor: valor CSS direto (ex. 'var(--success)'); corClasse: classe tailwind (ex. 'text-blue-400'). Têm prioridade sobre `accent`.
  valueColor,
  nota,                 // texto pequeno embaixo do número (opcional)
  barra,                // 0..1: barra de progresso fina embaixo (opcional)
  link,                 // { to, label }: atalho no rodapé do card (opcional)
}) {
  const variante = useVarianteKpi()
  const corFinal = cor ?? (ACCENT[accent] ?? ACCENT.default)
  return <BentoStat variante={variante ?? 'pequeno'} label={label} value={value} icon={Icon} cor={corFinal} valueColor={valueColor} corClasse={corClasse} nota={nota} barra={barra} link={link} />
}
