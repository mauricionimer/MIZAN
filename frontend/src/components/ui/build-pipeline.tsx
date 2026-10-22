import { useId, useLayoutEffect, useRef, useState } from 'react'
import { ArrowRight, CircleDot, Handshake, MessageCircle, Phone, Wallet, Square } from 'lucide-react'
import './build-pipeline.css'

export interface PipelineStage { id: string; nome: string }
export interface BuildPipelineProps {
  stages: PipelineStage[]
  currentStageId: string | null
  description?: string
}

const icons = [Square, Phone, MessageCircle, Handshake, Wallet]
const explanations: Record<string, string> = {
  nao_iniciado: 'Ponto de partida antes do primeiro contato.',
  contactado: 'Contato iniciado com o devedor.',
  negociando: 'Negociação em curso, incluindo promessa ainda sem acordo confirmado.',
  acordo: 'Oferta aceita ou acordo registrado.',
  pagamento: 'Pelo menos um pagamento confirmado. A situação dos pagamentos aparece nos avisos.',
}
const points = (vertices: number[][]) => vertices.map(p => p.join(',')).join(' ')

/** Geometria adaptada do BuildPipeline enviado: blocos isométricos conectados.
 * A seleção só inspeciona as fases. A situação vem do servidor.
 */
export function BuildPipeline({ stages, currentStageId, description }: BuildPipelineProps) {
  const root = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const id = useId()
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const observer = new ResizeObserver(() => setWidth(el.clientWidth))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const columns = Math.max(1, Math.min(stages.length, Math.floor(width / 150)))
  const rows = Math.ceil(stages.length / columns)
  const height = rows * 148 + 12
  const nodes = stages.map((_, i) => {
    const row = Math.floor(i / columns)
    const col = row % 2 ? columns - 1 - i % columns : i % columns
    return { x: (col + .5) * width / columns, y: row * 148 + 60 }
  })
  const chosen = stages.find(s => s.id === selected) ?? stages.find(s => s.id === currentStageId)
  return <div className="devedor-pipeline" ref={root}>
    {width > 0 && <div className="devedor-pipeline__plot" style={{ height }}>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="devedor-pipeline__chart">
        <defs><marker id={`${id}-seta`} markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0 0L5 2.5L0 5Z" fill="var(--ink-3)" /></marker></defs>
        {nodes.slice(0, -1).map((node, i) => {
          const next = nodes[i + 1]
          const direction = next.x > node.x ? 1 : -1
          const edge = node.x > width / 2 ? 1 : -1
          const path = next.y === node.y
            ? `M${node.x + direction * 35} ${node.y - 14}H${next.x - direction * 39}`
            : columns === 1 ? `M${node.x} ${node.y + 79}V${next.y - 48}`
            : `M${node.x + edge * 35} ${node.y - 14}H${node.x + edge * 56}V${next.y - 14}H${next.x + edge * 39}`
          return <path key={i} d={path} fill="none" stroke="var(--border-strong)" strokeWidth="1.4" markerEnd={`url(#${id}-seta)`} />
        })}
        {nodes.map(({ x, y }, i) => {
          const roof = [[x, y - 38], [x + 30, y - 23], [x, y - 8], [x - 30, y - 23]]
          const base = roof.map(([px, py]) => [px, py + 24])
          return <g key={stages[i].id} data-current={stages[i].id === currentStageId} className="devedor-pipeline__block">
            <polygon points={points([[x, y - 4], [x + 35, y + 13], [x, y + 30], [x - 35, y + 13]])} className="devedor-pipeline__ground" />
            <polygon points={points([roof[3], roof[2], base[2], base[3]])} className="devedor-pipeline__left" />
            <polygon points={points([roof[1], roof[2], base[2], base[1]])} className="devedor-pipeline__right" />
            <polygon points={points(roof)} className="devedor-pipeline__roof" />
          </g>
        })}
      </svg>
      <ol className="devedor-pipeline__stages" aria-label="Fases do devedor">
        {nodes.map((node, i) => {
          const stage = stages[i], Icon = icons[i] ?? Square
          const current = stage.id === currentStageId
          return <li key={stage.id} style={{ left: node.x - 68, top: node.y - 43 }}>
            <button type="button" aria-current={current ? 'step' : undefined} aria-pressed={chosen?.id === stage.id}
              aria-label={`${stage.nome}${current ? ', fase atual' : ''}`} onClick={() => setSelected(stage.id)}>
              <span className="devedor-pipeline__icon"><Icon size={18} strokeWidth={1.7} aria-hidden="true" /></span>
              <strong>{stage.nome}</strong>
              <span className="devedor-pipeline__state">{current ? <><CircleDot size={12} aria-hidden="true" />Fase atual</> : <>{String(i + 1).padStart(2, '0')}</>}</span>
            </button>
          </li>
        })}
      </ol>
    </div>}
    <div className="devedor-pipeline__detail" aria-live="polite">
      <ArrowRight size={16} aria-hidden="true" />
      <p><strong>{chosen?.nome ?? 'Fase não identificada'}</strong><span>{!chosen || chosen.id === currentStageId ? description : explanations[chosen.id]}</span></p>
    </div>
  </div>
}

export default BuildPipeline
