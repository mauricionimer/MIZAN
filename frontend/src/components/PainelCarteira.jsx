import { useEffect, useMemo, useState } from 'react'
import { curvaDaFila, buscarAlcance } from '../api'
import DicaAjuda from './DicaAjuda'
import { BarraH, Contador, LinhaDesenhada, Ponto, Aparece } from './graficos'

/**
 * Gráficos do Painel da carteira. Cada um responde uma pergunta, e o título é
 * a resposta (guia: design/GUIA_DE_DESIGN.md, seção 7). As contas ficam nas
 * funções puras abaixo, para a frase, a forma e o número nunca discordarem.
 */

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)
const fmtPct = (v) => `${Math.round(v || 0)}%`

function Secao({ rotulo, titulo, ajuda, subtitulo, children, className = '', direita }) {
  return (
    <Aparece as="section" className={`rounded-xl border border-line bg-surface p-6 ${className}`}>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="section-label">{rotulo}</p>
          <h3 className="mt-0.5 text-[15px] font-semibold text-ink">{titulo}{ajuda && <DicaAjuda id={ajuda} />}</h3>
          {subtitulo && <p className="mt-1 text-xs text-ink-2">{subtitulo}</p>}
        </div>
        {direita}
      </div>
      {children}
    </Aparece>
  )
}

/* ─────────────── contas puras ─────────────── */

const ATE_90 = ['0-30 dias', '31-60 dias', '61-90 dias']

/** Quanto do valor esperado está nos primeiros 90 dias (null sem o campo). */
export function parteAte90(aging) {
  if (!aging?.length || aging.some(a => a.valor_esperado == null)) return null
  const total = aging.reduce((s, a) => s + (a.valor_esperado || 0), 0)
  if (total <= 0) return null
  const cedo = aging.filter(a => ATE_90.includes(a.aging)).reduce((s, a) => s + (a.valor_esperado || 0), 0)
  return (cedo / total) * 100
}

/** Parte do valor esperado que está em fase que paga comissão. */
export function parteComComissao(ciclo) {
  const total = (ciclo || []).reduce((s, f) => s + (f.valor_esperado_liquido || 0), 0)
  if (total <= 0) return null
  const com = ciclo.filter(f => f.tem_comissao).reduce((s, f) => s + (f.valor_esperado_liquido || 0), 0)
  return (com / total) * 100
}

/** O ponto da curva mais perto de um corte (em % da fila). */
export function pontoNoCorte(curva, pctFila) {
  if (!curva?.pontos?.length) return null
  const alvo = Math.max(1, Math.round((curva.total_devedores * pctFila) / 100))
  return curva.pontos.reduce((m, p) => (Math.abs(p.n - alvo) < Math.abs(m.n - alvo) ? p : m), curva.pontos[0])
}

/** Frase do "quem pagou": a faixa com mais resultados acima de 60. */
export function fraseQuemPagou(faixas) {
  const comDado = (faixas || []).filter(f => f.total_feedbacks > 0)
  if (!comDado.length) return null
  const melhor = [...comDado].sort((a, b) => (b.taxa_pagamento ?? 0) - (a.taxa_pagamento ?? 0))[0]
  const pagaram = melhor.pagaram ?? 0
  const de = melhor.total_feedbacks
  return `${fmtNum(pagaram)} de ${fmtNum(de)} com score ${melhor.faixa} pagaram`
}

/* ─────────────── Precificação: a cascata ─────────────── */

export function Precificacao({ pricing, custo, retorno, onCusto, onRetorno }) {
  if (!pricing) return null
  const { ver, liquido, preco, face, desconto } = pricing
  const custoR = ver - liquido
  const retornoR = liquido - preco
  const max = ver || 1
  // Cada degrau começa onde o anterior parou: o que sai é mostrado como o
  // pedaço que falta, para a conta se ler da esquerda para a direita.
  const degraus = [
    { id: 've', nome: 'Valor esperado de recuperação', valor: ver, de: 0, ate: ver, cor: 'var(--royal)', ajuda: 'valor-esperado' },
    { id: 'cc', nome: `− custo de cobrança (${custo}%)`, valor: -custoR, de: liquido, ate: ver, cor: 'var(--warning)' },
    { id: 'ra', nome: `− retorno que você quer (${retorno}%)`, valor: -retornoR, de: preco, ate: liquido, cor: 'var(--chart-4)' },
    { id: 'pm', nome: 'Preço máximo de compra', valor: preco, de: 0, ate: preco, cor: 'var(--success)', forte: true },
  ]
  return (
    <Secao rotulo="Precificação" ajuda="precificacao-simulador"
      titulo={<>Pagando até <span className="tabular-nums">{fmtBRL(preco)}</span>, a compra rende os {retorno}% que você quer</>}
      subtitulo={face > 0 ? `É ${fmtPct(desconto)} abaixo do valor de face de ${fmtBRL(face)}.` : null}>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
        <ol className="space-y-4" aria-label="Da recuperação esperada ao preço máximo">
          {degraus.map((d, i) => (
            <li key={d.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5">
              <span className={`text-sm ${d.forte ? 'font-semibold text-ink' : 'text-ink-2'}`}>{d.nome}{d.ajuda && <DicaAjuda id={d.ajuda} />}</span>
              <span className={`whitespace-nowrap text-right tabular-nums ${d.forte ? 'text-lg font-bold text-ink' : 'text-sm text-ink'}`}>
                <Contador valor={d.valor} formatar={fmtBRL} />
              </span>
              <div className="relative col-span-2 h-3 rounded-full bg-raise-2">
                <div className="absolute inset-y-0" style={{ left: `${(d.de / max) * 100}%`, width: `${((d.ate - d.de) / max) * 100}%` }}>
                  <BarraH valor={1} max={1} cor={d.cor} altura={12} atraso={i * 0.25} rotulo={`${d.nome}: ${fmtBRL(Math.abs(d.valor))}`} />
                </div>
              </div>
            </li>
          ))}
        </ol>
        <div className="space-y-5 rounded-xl border border-line bg-raise-1 p-4">
          <p className="text-xs font-semibold text-ink-2">Mude as premissas e veja o preço mudar</p>
          <Regulador rotulo="Custo de cobrança" dica="despesas e comissões" valor={custo} min={5} max={50} onChange={onCusto} cor="var(--warning)" />
          <Regulador rotulo="Retorno que você quer" dica="o ganho mínimo da operação" valor={retorno} min={10} max={80} onChange={onRetorno} cor="var(--success)" />
        </div>
      </div>
    </Secao>
  )
}

function Regulador({ rotulo, dica, valor, min, max, onChange, cor }) {
  const pct = ((valor - min) / (max - min)) * 100
  const id = `reg-${rotulo.replace(/\s+/g, '-')}`
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs text-ink-2">{rotulo}</label>
        <span className="text-sm font-bold tabular-nums text-ink">{valor}%</span>
      </div>
      <input id={id} type="range" min={min} max={max} step={1} value={valor} onChange={e => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full"
        style={{ background: `linear-gradient(to right, ${cor} ${pct}%, var(--raised) ${pct}%)` }} />
      <p className="mt-1 text-[11px] text-ink-3">{dica}</p>
    </div>
  )
}

/* ─────────────── Aging: quanto volta, por tempo de atraso ─────────────── */

export function AgingValor({ aging }) {
  const parte = parteAte90(aging)
  const temValor = parte != null
  const maxFace = Math.max(1, ...aging.map(a => a.valor_total || 0))
  const maxDev = Math.max(1, ...aging.map(a => a.total_devedores || 0))
  return (
    <Secao rotulo="Tempo de atraso" ajuda="aging"
      titulo={temValor ? `${fmtPct(parte)} do que dá para recuperar está nos primeiros 90 dias` : 'Quantos devedores há em cada faixa de atraso'}
      subtitulo={temValor ? 'Trilho = valor de face; cheio = valor esperado.' : 'Esta análise é de antes do valor esperado por faixa: reenvie a carteira para ver quanto volta em cada uma.'}>
      <ul className="space-y-4">
        {aging.map((a, i) => (
          <li key={a.aging} className="grid grid-cols-[88px_minmax(0,1fr)] items-center gap-x-4 gap-y-1 sm:grid-cols-[96px_minmax(0,1fr)_200px]">
            <span className="text-sm text-ink-2">{a.aging}</span>
            {temValor ? (
              <div className="relative h-3">
                <div className="absolute inset-y-0 left-0 rounded-full bg-raise-2" style={{ width: `${((a.valor_total || 0) / maxFace) * 100}%` }} />
                <div className="absolute inset-y-0 left-0" style={{ width: `${((a.valor_total || 0) / maxFace) * 100}%` }}>
                  <BarraH valor={a.valor_esperado || 0} max={a.valor_total || 1} altura={12} atraso={i * 0.12} className="!bg-transparent"
                    rotulo={`${a.aging}: ${fmtBRL(a.valor_esperado)} esperados de ${fmtBRL(a.valor_total)} de face`} />
                </div>
              </div>
            ) : (
              <BarraH valor={a.total_devedores} max={maxDev} altura={12} atraso={i * 0.12} rotulo={`${a.aging}: ${fmtNum(a.total_devedores)} devedores`} />
            )}
            <span className="col-start-2 text-xs tabular-nums text-ink-3 sm:col-start-3 sm:text-right">
              {temValor ? <><span className="font-semibold text-ink">{fmtBRL(a.valor_esperado)}</span> de {fmtBRL(a.valor_total)}</> : `${fmtNum(a.total_devedores)} devedores`}
            </span>
          </li>
        ))}
      </ul>
    </Secao>
  )
}

/* ─────────────── Até onde vale cobrar ─────────────── */

const CORTES = [10, 20, 30, 50]

export function AteOndeCobrar({ carteiraId }) {
  const [curva, setCurva] = useState(null)
  const [erro, setErro] = useState(false)
  const [corte, setCorte] = useState(20)
  const [exato, setExato] = useState(null)

  useEffect(() => {
    if (!carteiraId) return
    let vivo = true
    curvaDaFila(carteiraId).then(c => { if (vivo) setCurva(c) }).catch(() => { if (vivo) setErro(true) })
    return () => { vivo = false }
  }, [carteiraId])

  const ponto = useMemo(() => pontoNoCorte(curva, corte), [curva, corte])

  // O número do corte vem somado de verdade pelo /alcance; a curva é o desenho.
  useEffect(() => {
    if (!carteiraId || !ponto) return
    let vivo = true
    setExato(null)
    buscarAlcance(carteiraId, ponto.n).then(a => { if (vivo) setExato(a) }).catch(() => {})
    return () => { vivo = false }
  }, [carteiraId, ponto])

  if (erro || (curva && !curva.pontos?.length)) return null
  if (!curva) {
    return <div className="h-[300px] animate-pulse rounded-xl border border-line bg-surface" aria-label="Carregando a curva da fila" />
  }

  const W = 900, H = 240, P = 8
  const n = curva.total_devedores || 1
  const x = (k) => P + ((W - 2 * P) * k) / n
  const y = (pct) => H - P - ((H - 2 * P) * pct) / 100
  const d = `M ${x(0)} ${y(0)} ` + curva.pontos.map(p => `L ${x(p.n).toFixed(1)} ${y(p.pct).toFixed(1)}`).join(' ')
  const valor = exato?.valor ?? ponto.valor
  const pct = exato?.pct ?? ponto.pct

  return (
    <Secao rotulo="Fila de cobrança" ajuda="fila-ordem"
      titulo={`Cobrar os primeiros ${corte}% traz ${fmtPct(pct)} do que a carteira pode render`}
      subtitulo="A fila já vem do maior valor esperado para o menor: a curva sobe rápido e depois achata."
      direita={(
        <div className="flex gap-1 rounded-full border border-line p-1" role="group" aria-label="Corte da fila">
          {CORTES.map(c => (
            <button key={c} type="button" onClick={() => setCorte(c)} aria-pressed={corte === c}
              className={`h-8 rounded-full px-3 text-xs font-semibold tabular-nums transition-colors ${corte === c ? 'bg-royal text-white' : 'text-ink-2 hover:text-ink'}`}>
              {c}%
            </button>
          ))}
        </div>
      )}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px]">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
          aria-label={`Curva acumulada: os primeiros ${corte}% da fila trazem ${fmtPct(pct)} do valor esperado`}>
          {[25, 50, 75, 100].map(g => (
            <line key={g} x1={P} x2={W - P} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeDasharray="3 4" />
          ))}
          <path d={`${d} L ${x(n)} ${y(0)} Z`} fill="var(--royal)" opacity="0.08" />
          <LinhaDesenhada d={d} />
          <line x1={x(ponto.n)} x2={x(ponto.n)} y1={y(0)} y2={y(ponto.pct)} stroke="var(--text-muted)" strokeDasharray="4 4" />
          <circle cx={x(ponto.n)} cy={y(ponto.pct)} r="6" fill="var(--royal)" stroke="var(--card)" strokeWidth="3" />
        </svg>
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-1">
          <div>
            <dt className="text-xs text-ink-3">Cobrar os primeiros</dt>
            <dd className="mt-0.5 text-xl font-bold tabular-nums text-ink">{fmtNum(ponto.n)}</dd>
            <dd className="text-xs tabular-nums text-ink-2">trazem {fmtBRL(valor)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-3">O próximo da fila vale</dt>
            <dd className="mt-0.5 text-xl font-bold tabular-nums text-ink">{fmtBRL(ponto.proximo)}</dd>
            <dd className="text-xs text-ink-2">compare com o custo de cobrar um caso</dd>
          </div>
        </dl>
      </div>
    </Secao>
  )
}

/* ─────────────── Regime: comissão ou não ─────────────── */

export function RegimeBarras({ ciclo }) {
  const parte = parteComComissao(ciclo)
  if (!ciclo?.length || parte == null) return null
  const totalFace = ciclo.reduce((s, f) => s + (f.valor_face || 0), 0) || 1
  const totalEsp = ciclo.reduce((s, f) => s + (f.valor_esperado_liquido || 0), 0) || 1
  const cor = (i) => `rgb(var(--c-royal) / ${0.35 + (0.6 * i) / Math.max(1, ciclo.length - 1)})`
  const Linha = ({ nome, campo, total }) => (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3">
      <span className="text-xs text-ink-2">{nome}</span>
      <div className="flex h-4 gap-[2px] overflow-hidden rounded-full" role="img"
        aria-label={`${nome}: ${ciclo.map(f => `${f.rotulo} ${fmtPct(((f[campo] || 0) / total) * 100)}`).join(', ')}`}>
        {ciclo.map((f, i) => (
          <div key={f.fase} style={{ width: `${((f[campo] || 0) / total) * 100}%` }}>
            <BarraH valor={1} max={1} altura={16} cor={cor(i)} atraso={i * 0.2} className="!rounded-none" />
          </div>
        ))}
      </div>
    </div>
  )
  return (
    <div className="mb-5 space-y-2.5">
      <p className="text-sm text-ink">
        <span className="font-semibold tabular-nums">{fmtPct(parte)}</span> do que deve voltar já está na fase que paga comissão.
      </p>
      <Linha nome="Valor de face" campo="valor_face" total={totalFace} />
      <Linha nome="Valor esperado" campo="valor_esperado_liquido" total={totalEsp} />
      <div className="flex flex-wrap gap-x-4 gap-y-1 pl-[122px] text-[11px] text-ink-3">
        {ciclo.map((f, i) => (
          <span key={f.fase} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: cor(i) }} />{f.rotulo}</span>
        ))}
      </div>
    </div>
  )
}

/* ─────────────── Quem pagou, por faixa de score ─────────────── */

const MAX_BOLINHAS = 40

export function QuemPagou({ perf }) {
  const faixas = perf?.metricas_por_faixa || []
  const frase = fraseQuemPagou(faixas)
  if (!frase) return null
  const maiorAmostra = Math.max(...faixas.map(f => f.total_feedbacks || 0))
  // Até 40 resultados por faixa, uma bolinha é um resultado. Acima disso, cada
  // bolinha vale vários, e a legenda diz quantos.
  const porBolinha = Math.max(1, Math.ceil(maiorAmostra / MAX_BOLINHAS))
  return (
    <Secao rotulo="Resultados reais" ajuda="quem-pagou" titulo={frase}
      subtitulo={porBolinha === 1 ? 'Cada bolinha é um resultado registrado.' : `Cada bolinha são ${porBolinha} resultados registrados.`}
      direita={perf.acuracia_geral != null && (
        <span className="rounded-full border border-line px-3 py-1 text-xs text-ink-2">
          O score acertou <span className="font-semibold tabular-nums text-ink">{perf.acuracia_geral}%</span><DicaAjuda id="acuracia-geral" />
        </span>
      )}>
      <ul className="space-y-4">
        {faixas.map((f, fi) => {
          const pag = Math.round((f.pagaram || 0) / porBolinha)
          const nao = Math.round((f.nao_pagaram || 0) / porBolinha)
          return (
            <li key={f.faixa} className="grid grid-cols-[72px_minmax(0,1fr)] items-start gap-x-4 gap-y-1 sm:grid-cols-[80px_minmax(0,1fr)_120px]">
              <span className="pt-0.5 text-sm font-medium text-ink">{f.faixa}</span>
              <div className="flex flex-wrap gap-1" role="img" aria-label={`Score ${f.faixa}: ${f.pagaram} pagaram, ${f.nao_pagaram} não pagaram`}>
                {Array.from({ length: pag }, (_, i) => (
                  <Ponto key={`p${i}`} atraso={fi * 0.1 + i * 0.012} className="h-3 w-3 rounded-full" style={{ background: 'var(--success)' }} />
                ))}
                {Array.from({ length: nao }, (_, i) => (
                  <Ponto key={`n${i}`} atraso={fi * 0.1 + (pag + i) * 0.012} className="h-3 w-3 rounded-full border-2" style={{ borderColor: 'var(--text-muted)' }} />
                ))}
                {!f.total_feedbacks && <span className="text-xs text-ink-3">sem resultado ainda</span>}
              </div>
              <span className="col-start-2 text-xs tabular-nums text-ink-3 sm:col-start-3 sm:text-right">
                {f.total_feedbacks ? <><span className="font-semibold text-ink">{fmtPct(f.taxa_pagamento)}</span> pagaram</> : '—'}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="mt-4 flex gap-4 text-[11px] text-ink-3">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: 'var(--success)' }} />pagou</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2" style={{ borderColor: 'var(--text-muted)' }} />não pagou</span>
      </div>
    </Secao>
  )
}

/* ─────────────── Perfis de devedores ─────────────── */

export function Perfis({ clusters }) {
  if (!clusters?.length) return null
  const ord = [...clusters].sort((a, b) => (b.total_devedores || 0) - (a.total_devedores || 0))
  const total = ord.reduce((s, c) => s + (c.total_devedores || 0), 0) || 1
  const maior = ord[0]
  return (
    <Secao rotulo="Segmentação" ajuda="perfil-cluster"
      titulo={`${fmtPct((maior.total_devedores / total) * 100)} dos devedores são do perfil ${maior.perfil_cluster}`}>
      <ul className="space-y-3.5">
        {ord.map((c, i) => (
          <li key={c.perfil_cluster} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-ink-2">{c.perfil_cluster}</span>
              <span className="shrink-0 tabular-nums text-ink">{fmtNum(c.total_devedores)}</span>
            </div>
            <BarraH valor={c.total_devedores} max={maior.total_devedores || 1} atraso={i * 0.1}
              rotulo={`${c.perfil_cluster}: ${fmtNum(c.total_devedores)} devedores`} />
          </li>
        ))}
      </ul>
    </Secao>
  )
}
