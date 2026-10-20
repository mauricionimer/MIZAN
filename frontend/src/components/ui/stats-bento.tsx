import React, { createContext, useContext } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"

// Organização dos números (KPIs) em bento, adaptada do stats-bento do 21st.dev.
// O original é uma vitrine de números fixos; aqui ele vira layout: o primeiro
// número da tela é o destaque grande, o segundo é largo, e os demais ficam em
// cartões menores. Os cartões continuam sendo os StatCard de sempre; quem diz
// em que posição cada um está é o contexto abaixo. Cores do tema (claro/escuro)
// vêm das variáveis do projeto, e nenhum número é inventado: o que aparece é o
// que a tela já mostrava.

export type VarianteKpi = "destaque" | "largo" | "pequeno" | null

export const VarianteKpiContext = createContext<VarianteKpi>(null)

export interface BentoStatProps {
  variante?: Exclude<VarianteKpi, null>
  label: React.ReactNode
  value: React.ReactNode
  icon?: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  cor?: string
  valueColor?: string
  corClasse?: string
  nota?: React.ReactNode
  barra?: number | null
  link?: { to: string; label: string } | null
}

// Classes escritas por extenso: o Tailwind só mantém o que enxerga como texto.
const CLASSE_VARIANTE = { destaque: "bento-kpi--destaque", largo: "bento-kpi--largo", pequeno: "bento-kpi--pequeno" } as const

export function BentoStat({ variante: varianteProp, label, value, icon: Icon, cor, valueColor, corClasse, nota, barra, link }: BentoStatProps) {
  const herdada = useContext(VarianteKpiContext)
  const variante = varianteProp ?? herdada ?? 'pequeno'
  const destaque = variante === "destaque"
  const rotulo = "text-[10px] font-semibold uppercase tracking-[0.14em]"
  return (
    <div className={`bento-kpi ${CLASSE_VARIANTE[variante]} relative flex h-full flex-col overflow-hidden ${destaque ? "justify-between" : "justify-center"}`}>
      {destaque && <div className="bento-kpi-trama pointer-events-none absolute inset-0" aria-hidden="true" />}
      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <div className={rotulo} style={{ color: destaque ? "var(--on-brand)" : "var(--text-muted)" }}>{label}</div>
          {Icon && (
            <span className={destaque ? "bento-kpi-icone" : ""} aria-hidden="true">
              <Icon className={`h-3.5 w-3.5 ${destaque ? "" : corClasse ?? ""}`} style={destaque ? { color: "var(--on-brand)" } : !corClasse ? { color: cor ?? "var(--text-muted)" } : undefined} />
            </span>
          )}
        </div>
        <p className={`bento-kpi-value tnum mt-3 font-semibold leading-tight tracking-tight ${destaque ? "text-3xl sm:text-4xl" : variante === "largo" ? "text-3xl" : "text-2xl"}`}
          style={{ color: destaque ? "var(--on-brand)" : valueColor ?? "var(--text)" }}>
          {value}
        </p>
        {barra != null && (
          <div className="mt-4 h-1.5 overflow-hidden rounded-full" role="progressbar" aria-label={typeof label === 'string' ? label : 'Progresso'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number.isFinite(barra) ? Math.max(0, Math.min(100, barra * 100)) : 0} style={{ background: destaque ? "rgba(255,255,255,.22)" : "var(--raised)" }}>
            <div className="h-full rounded-full" style={{ width: `${Number.isFinite(barra) ? Math.max(0, Math.min(100, barra * 100)) : 0}%`, background: destaque ? "var(--on-brand)" : "var(--royal)" }} />
          </div>
        )}
      </div>
      {(nota || link) && (
        <div className="relative mt-4 space-y-2">
          {nota && <p className="text-xs leading-relaxed" style={{ color: destaque ? "var(--on-brand)" : "var(--text-muted)" }}>{nota}</p>}
          {link && (
            <Link to={link.to} className="inline-flex min-h-[40px] items-center gap-1 text-xs font-medium" style={{ color: destaque ? "var(--on-brand)" : "var(--accent-text)" }}>
              {link.label} <ArrowRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Arruma os cartões de números em bento.
 *  1 ou 2 números: grade simples, sem destaque (não há o que destacar).
 *  3 ou mais: o primeiro é o destaque grande à esquerda; à direita, o segundo
 *  largo em cima e os demais em cartões menores embaixo.
 * Em tela estreita tudo empilha em duas colunas.
 */
export function KpiBento({ children, className = '', 'aria-label': ariaLabel = 'Indicadores' }: { children: React.ReactNode; className?: string; 'aria-label'?: string }) {
  const itens = React.Children.toArray(children).filter(React.isValidElement)
  if (itens.length <= 2) {
    return <div role="group" aria-label={ariaLabel} className={`bento-stats grid grid-cols-1 gap-4 ${itens.length === 2 ? 'sm:grid-cols-2' : ''} ${className}`}>{itens}</div>
  }
  const [primeiro, segundo, ...resto] = itens
  const cols = resto.length >= 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"
  return (
    <div role="group" aria-label={ariaLabel} className={`bento-stats grid min-w-0 gap-4 lg:grid-cols-2 ${className}`}>
      <VarianteKpiContext.Provider value="destaque"><div className="min-w-0 min-h-[11rem]">{primeiro}</div></VarianteKpiContext.Provider>
      <div className="grid min-w-0 gap-4">
        <VarianteKpiContext.Provider value="largo"><div className="min-w-0">{segundo}</div></VarianteKpiContext.Provider>
        {resto.length > 0 && (
          <div className={`grid min-w-0 grid-cols-1 gap-4 ${cols}`}>
            {resto.map((c, i) => (
              <VarianteKpiContext.Provider key={i} value="pequeno"><div className="min-w-0">{c}</div></VarianteKpiContext.Provider>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export const useVarianteKpi = () => useContext(VarianteKpiContext)

// Nome público do componente enviado; o alias mantém as integrações existentes.
export const StatsBento = KpiBento
export default StatsBento
