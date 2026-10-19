// KPI conforme o brief (seção 5): card, rótulo em maiúsculas pequeno, número
// grande com tabular-nums e ícone tingido no canto. Sem legenda descritiva
// embaixo do número por padrão — a seção 7 do brief pede a remoção dessas
// frases — mas quem precisava de uma nota pequena (`nota`), barra de
// progresso (`barra`) ou um link de atalho (`link`) ganhou essas props
// opcionais ao ser migrado para este componente único (ver Agente.jsx,
// AgentePerfil.jsx, PainelOperador.jsx, Resultados.jsx).
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { motion } from 'framer-motion'

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
  nota,                 // texto pequeno embaixo do número (opcional)
  barra,                // 0..1: barra de progresso fina embaixo (opcional)
  link,                 // { to, label }: atalho no rodapé do card (opcional)
  i,                    // índice para o efeito cascata de entrada (opcional)
}) {
  const corFinal = cor ?? (ACCENT[accent] ?? ACCENT.default)
  const temAnimacao = i != null
  const Wrapper = temAnimacao ? motion.div : 'div'
  const propsAnimacao = temAnimacao
    ? { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { delay: i * 0.04 } }
    : {}

  return (
    <Wrapper {...propsAnimacao} className="card px-6 py-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-muted)',
        }}>
          {label}
        </p>
        {Icon && (corClasse
          ? <Icon className={`h-3.5 w-3.5 ${corClasse}`} />
          : <Icon className="h-3.5 w-3.5" style={{ color: corFinal }} />)}
      </div>
      <p className="tnum text-[1.75rem] font-semibold tracking-tight leading-none"
        style={{ color: 'var(--text)' }}>
        {value}
      </p>
      {barra != null && (
        <div className="h-1.5 overflow-hidden rounded-full bg-raise-2">
          <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(100, barra * 100)}%` }} />
        </div>
      )}
      {nota && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{nota}</p>}
      {link && (
        <Link to={link.to} className="inline-flex min-h-[36px] items-center gap-1 text-xs font-semibold text-blue-400 hover:text-blue-300">
          {link.label} <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      )}
    </Wrapper>
  )
}
