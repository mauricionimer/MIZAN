import React, { createContext, useContext } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"

// Variante exclusiva da Agenda da equipe; os KPIs das demais telas não mudam.
export { default as StatsBento } from './agenda-equipe-bento'
export { default } from './agenda-equipe-bento'

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
  variante: Exclude<VarianteKpi, null>
  label: React.ReactNode
  value: React.ReactNode
  icon?: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  cor?: string
  corClasse?: string
  nota?: React.ReactNode
  barra?: number | null
  link?: { to: string; label: string } | null
}

// Classes escritas por extenso: o Tailwind só mantém o que enxerga como texto.
const CLASSE_VARIANTE = { destaque: "bento-kpi--destaque", largo: "bento-kpi--largo", pequeno: "bento-kpi--pequeno" } as const

export function BentoStat({ variante, label, value, icon: Icon, cor, corClasse, nota, barra, link }: BentoStatProps) {
  const destaque = variante === "destaque"
  const rotulo = "text-[10px] font-semibold uppercase tracking-[0.14em]"
  return (
    <div className={`bento-kpi ${CLASSE_VARIANTE[variante]} relative flex h-full flex-col overflow-hidden ${destaque ? "justify-between" : "justify-center"}`}>
      {destaque && <div className="bento-kpi-trama pointer-events-none absolute inset-0" aria-hidden="true" />}
      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <p className={rotulo} style={{ color: destaque ? "rgba(255,255,255,.72)" : "var(--text-muted)" }}>{label}</p>
          {Icon && (
            <span className={destaque ? "bento-kpi-icone" : ""} aria-hidden="true">
              <Icon className={`h-3.5 w-3.5 ${destaque ? "" : corClasse ?? ""}`} style={destaque ? { color: "#fff" } : !corClasse ? { color: cor ?? "var(--text-muted)" } : undefined} />
            </span>
          )}
        </div>
        <p className={`tnum mt-3 font-semibold leading-none tracking-tighter ${destaque ? "text-5xl md:text-6xl" : variante === "largo" ? "text-3xl" : "text-2xl"}`}
          style={{ color: destaque ? "#fff" : "var(--text)" }}>
          {value}
        </p>
        {barra != null && (
          <div className="mt-4 h-1.5 overflow-hidden rounded-full" style={{ background: destaque ? "rgba(255,255,255,.22)" : "var(--raised)" }}>
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, barra * 100)}%`, background: destaque ? "#fff" : "var(--royal)" }} />
          </div>
        )}
      </div>
      {(nota || link) && (
        <div className="relative mt-4 space-y-2">
          {nota && <p className="max-w-xs text-xs" style={{ color: destaque ? "rgba(255,255,255,.72)" : "var(--text-muted)" }}>{nota}</p>}
          {link && (
            <Link to={link.to} className="inline-flex items-center gap-1 text-xs font-medium" style={{ color: destaque ? "#fff" : "var(--royal)" }}>
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
export function KpiBento({ children }: { children: React.ReactNode }) {
  const itens = React.Children.toArray(children).filter(React.isValidElement)
  if (itens.length <= 2) {
    return <div className="grid grid-cols-2 gap-3 sm:gap-4">{itens}</div>
  }
  const [primeiro, segundo, ...resto] = itens
  const cols = resto.length >= 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"
  return (
    <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
      <VarianteKpiContext.Provider value="destaque"><div className="min-h-[11rem]">{primeiro}</div></VarianteKpiContext.Provider>
      <div className="grid gap-3 sm:gap-4">
        <VarianteKpiContext.Provider value="largo"><div>{segundo}</div></VarianteKpiContext.Provider>
        {resto.length > 0 && (
          <div className={`grid grid-cols-2 gap-3 sm:gap-4 ${cols}`}>
            {resto.map((c, i) => (
              <VarianteKpiContext.Provider key={i} value="pequeno"><div>{c}</div></VarianteKpiContext.Provider>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export const useVarianteKpi = () => useContext(VarianteKpiContext)
