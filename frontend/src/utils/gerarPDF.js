import jsPDF from 'jspdf'
// Mesma regra da tela: a prioridade é a posição na fila, que é ordenada
// por valor esperado. Sem acento porque a fonte do PDF não os cobre.
import { prioridadePorRankAscii } from './prioridade'

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v)
const fmtPct = (v) => `${v.toFixed(1)}%`

const C = {
  blue:      [37,  99,  235],
  blue2:     [29,  78,  216],
  blueLight: [147, 197, 253],
  bluePale:  [219, 234, 254],
  dark:      [15,  23,  42],
  mid:       [71,  85,  105],
  light:     [148, 163, 184],
  bg:        [248, 250, 252],
  border:    [226, 232, 240],
  white:     [255, 255, 255],
  emerald:   [5,   150, 105],
  amber:     [217, 119, 6],
  red:       [220, 38,  38],
  violet:    [139, 92,  246],
  indigo:    [99,  102, 241],
  teal:      [20,  184, 166],
}

const AGING_ORDER  = ['0-29 dias', '30-59 dias', '60-89 dias', '90-179 dias', '180+ dias']
const AGING_COLORS = [C.emerald, C.blue, C.amber, [249,115,22], C.red]
const CLUSTER_COLORS = [C.blue, C.violet, C.emerald, C.amber, C.red, C.indigo, C.teal]

export function gerarRelatorioPDF(result, pricing, custoCobranca, retornoAlvo) {
  const { resumo, distribuicao_aging, distribuicao_cluster, ranking_completo } = result

  const doc = new jsPDF('p', 'mm', 'a4')
  const PW = 210
  const PH = 297
  const M  = 14
  const CW = PW - 2 * M

  let page = 1
  let y = 0

  // ── Drawing helpers ──────────────────────────────────────────

  function fill(x, ry, w, h, color) {
    doc.setFillColor(...color)
    doc.rect(x, ry, w, h, 'F')
  }

  function stroke(x, ry, w, h, color, lw = 0.25) {
    doc.setDrawColor(...color)
    doc.setLineWidth(lw)
    doc.rect(x, ry, w, h, 'S')
  }

  function hLine(ry, color = C.border, lw = 0.2) {
    doc.setDrawColor(...color)
    doc.setLineWidth(lw)
    doc.line(M, ry, PW - M, ry)
  }

  function t(str, x, ry, { size = 9, color = C.dark, align = 'left', bold = false } = {}) {
    doc.setFontSize(size)
    doc.setTextColor(...color)
    doc.setFont('helvetica', bold ? 'bold' : 'normal')
    doc.text(String(str), x, ry, { align })
  }

  // ── Page header (pages 2+) ────────────────────────────────────

  function pageHeader(subtitle = 'Relatorio de Analise de Carteira') {
    fill(0, 0, PW, 12, C.blue)
    t('MIZAN', M, 8, { size: 8, color: C.white, bold: true })
    t(subtitle, PW / 2, 8, { size: 7.5, color: C.blueLight, align: 'center' })
    t(`Pagina ${page}`, PW - M, 8, { size: 7, color: C.blueLight, align: 'right' })
    y = 18
  }

  function pageFooter() {
    fill(0, PH - 8, PW, 8, C.bg)
    doc.setDrawColor(...C.border)
    doc.setLineWidth(0.2)
    doc.line(0, PH - 8, PW, PH - 8)
    t('Mizan  |  Plataforma de Analise de Carteira de Credito com IA', M, PH - 3, { size: 6, color: C.light })
    t(`Pagina ${page}`, PW - M, PH - 3, { size: 6, color: C.light, align: 'right' })
  }

  function checkBreak(needed) {
    if (y + needed > PH - 14) {
      pageFooter()
      doc.addPage()
      page++
      pageHeader('Ranking de Recuperabilidade (continuacao)')
      tableHeader()
    }
  }

  // ── Section title ────────────────────────────────────────────

  function sectionTitle(title, ry) {
    t(title, M, ry, { size: 7, color: C.light, bold: true })
    hLine(ry + 2, C.border)
    return ry + 7
  }

  // ── KPI card ────────────────────────────────────────────────

  function kpiCard(x, ry, w, h, label, value, sub, accent) {
    fill(x, ry, w, h, C.white)
    stroke(x, ry, w, h, C.border)
    fill(x, ry, 2, h, accent)
    t(label, x + 5, ry + 5.5, { size: 6, color: C.light, bold: true })
    t(value, x + 5, ry + 12, { size: 11, color: C.dark, bold: true })
    if (sub) t(sub, x + 5, ry + 16.5, { size: 5.5, color: C.light })
  }

  // ── Pricing cell ─────────────────────────────────────────────

  function pricingCell(x, ry, w, h, label, value, sub, highlight) {
    fill(x, ry, w, h, highlight ? C.blue : C.bg)
    stroke(x, ry, w, h, highlight ? C.blue : C.border)
    t(label, x + 4, ry + 5.5, { size: 5.5, color: highlight ? C.blueLight : C.light, bold: true })
    t(value, x + 4, ry + 13,  { size: 11,  color: highlight ? C.white : C.dark, bold: true })
    if (sub) t(sub, x + 4, ry + 18, { size: 5.5, color: highlight ? C.blueLight : C.light })
  }

  // ═══════════════════════════════════════════════════════════
  // PAGINA 1  —  Resumo Executivo
  // ═══════════════════════════════════════════════════════════

  // Header cover
  fill(0, 0, PW, 30, C.blue)
  fill(0, 24, PW, 6, C.blue2)

  // Branding
  fill(M, 6, 14, 14, C.blue2)
  t('M', M + 7, 15.5, { size: 13, color: C.white, bold: true, align: 'center' })
  t('MIZAN', M + 18, 11, { size: 14, color: C.white, bold: true })
  t('Relatorio de Analise de Carteira de Credito', M + 18, 17, { size: 8.5, color: C.blueLight })

  // Date + summary
  const hoje = new Date().toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })
  t(hoje, PW - M, 11, { size: 8, color: C.blueLight, align: 'right' })
  t(`${fmtNum(resumo.total_devedores)} devedores analisados`, PW - M, 17, { size: 8, color: C.blueLight, align: 'right' })

  y = 38

  // ── KPIs ──
  y = sectionTitle('INDICADORES PRINCIPAIS', y)

  const kW = (CW - 9) / 4
  const kH = 21
  const prioritarios = ranking_completo.filter(d => (d.score_recuperabilidade ?? 0) >= 70).length

  kpiCard(M,             y, kW, kH, 'TOTAL DE DEVEDORES',    fmtNum(resumo.total_devedores), 'na carteira', C.blue)
  kpiCard(M + kW + 3,   y, kW, kH, 'VALOR DE FACE',          fmtBRL(resumo.total_em_risco),  'valor nominal', C.indigo)
  kpiCard(M + kW*2 + 6, y, kW, kH, 'SCORE MEDIO',            resumo.score_medio.toFixed(1),  'recuperabilidade (0-100)', C.emerald)
  kpiCard(M + kW*3 + 9, y, kW, kH, 'DEVEDORES PRIORITARIOS', fmtNum(prioritarios),            'score >= 70', C.amber)

  y += kH + 9

  // ── Precificação ──
  y = sectionTitle('PRECIFICACAO DA CARTEIRA', y)
  t(`Custo de cobranca: ${custoCobranca}%   Retorno alvo: ${retornoAlvo}%`, M, y - 1, { size: 7, color: C.light })
  y += 1

  const pW = (CW) / 4 - 1
  const pH = 22
  pricingCell(M,            y, pW, pH, 'VALOR ESPERADO DE RECUPERACAO', fmtBRL(pricing.ver),    resumo.taxa_recuperacao_esperada != null ? `${fmtPct(resumo.taxa_recuperacao_esperada)} do face` : '', false)
  pricingCell(M + pW + 2,  y, pW, pH, 'VALOR LIQUIDO (apos custos)',    fmtBRL(pricing.liquido), `custos: ${fmtBRL(pricing.ver - pricing.liquido)}`, false)
  pricingCell(M + pW*2+4,  y, pW, pH, 'PRECO SUGERIDO DE COMPRA',       fmtBRL(pricing.preco),   `${fmtPct(pricing.desconto)} de desconto`, true)
  pricingCell(M + pW*3+6,  y, pW, pH, 'RETORNO ESPERADO DA OPERACAO',   fmtPct(pricing.retorno), `lucro: ${fmtBRL(pricing.liquido - pricing.preco)}`, false)

  y += pH + 9

  // ── Aging ──
  y = sectionTitle('DISTRIBUICAO POR AGING (DIAS EM ATRASO)', y)

  const agingSorted = [...distribuicao_aging].sort(
    (a, b) => AGING_ORDER.indexOf(a.aging) - AGING_ORDER.indexOf(b.aging)
  )
  const totalAging = agingSorted.reduce((s, d) => s + d.total_devedores, 0)
  const maxAging   = Math.max(...agingSorted.map(d => d.total_devedores))
  const agingBarMaxW = CW - 65

  agingSorted.forEach((d, i) => {
    const pct   = totalAging > 0 ? d.total_devedores / totalAging : 0
    const barW  = maxAging  > 0 ? (d.total_devedores / maxAging) * agingBarMaxW : 0
    const rowY  = y + i * 8.5
    const color = AGING_COLORS[i % AGING_COLORS.length]

    // Color dot
    fill(M, rowY + 1.5, 3, 3, color)
    // Label
    t(d.aging, M + 6, rowY + 4, { size: 7, color: C.mid })
    // Track
    fill(M + 44, rowY, agingBarMaxW, 6, C.bg)
    if (barW > 0) fill(M + 44, rowY, barW, 6, color)
    // Pct
    t(`${(pct * 100).toFixed(1)}%`, M + 44 + agingBarMaxW + 3, rowY + 4.5, { size: 7, color: C.mid, bold: true })
    // Count
    t(fmtNum(d.total_devedores), PW - M, rowY + 4.5, { size: 6.5, color: C.light, align: 'right' })
  })

  y += agingSorted.length * 8.5 + 7

  // ── Clusters ──
  y = sectionTitle('PERFIS DE DEVEDORES (CLUSTERS)', y)

  const totalCluster = distribuicao_cluster.reduce((s, d) => s + d.total_devedores, 0)
  const maxCluster   = Math.max(...distribuicao_cluster.map(d => d.total_devedores))
  const clusterBarMaxW = CW - 65

  distribuicao_cluster.forEach((d, i) => {
    const pct   = totalCluster > 0 ? d.total_devedores / totalCluster : 0
    const barW  = maxCluster  > 0 ? (d.total_devedores / maxCluster) * clusterBarMaxW : 0
    const rowY  = y + i * 8.5
    const color = CLUSTER_COLORS[i % CLUSTER_COLORS.length]

    fill(M, rowY + 1.5, 3, 3, color)
    t(d.perfil_cluster, M + 6, rowY + 4, { size: 7, color: C.mid })
    fill(M + 44, rowY, clusterBarMaxW, 6, C.bg)
    if (barW > 0) fill(M + 44, rowY, barW, 6, color)
    t(`${(pct * 100).toFixed(1)}%`, M + 44 + clusterBarMaxW + 3, rowY + 4.5, { size: 7, color: C.mid, bold: true })
    t(fmtNum(d.total_devedores), PW - M, rowY + 4.5, { size: 6.5, color: C.light, align: 'right' })
  })

  y += distribuicao_cluster.length * 8.5 + 4

  pageFooter()

  // ═══════════════════════════════════════════════════════════
  // PAGINA 2+  —  Ranking de Recuperabilidade
  // ═══════════════════════════════════════════════════════════

  doc.addPage()
  page++
  pageHeader('Ranking de Recuperabilidade')

  // Column definitions
  const COLS = [
    { label: '#',           w: 7,   align: 'right'  },
    { label: 'Nome',        w: 52,  align: 'left'   },
    { label: 'CPF',         w: 28,  align: 'left'   },
    { label: 'Produto',     w: 22,  align: 'left'   },
    { label: 'Valor Face',  w: 22,  align: 'right'  },
    { label: 'Vlr Esperado',w: 22,  align: 'right'  },
    { label: 'Score',       w: 11,  align: 'right'  },
    { label: 'Prioridade',  w: 18,  align: 'center' },
  ]
  const totalW = COLS.reduce((s, c) => s + c.w, 0)
  const scale  = CW / totalW

  function tableHeader() {
    fill(M, y, CW, 7.5, C.bg)
    stroke(M, y, CW, 7.5, C.border)
    let cx = M
    COLS.forEach(col => {
      const cw = col.w * scale
      const tx = col.align === 'right'  ? cx + cw - 1.5
               : col.align === 'center' ? cx + cw / 2
               :                          cx + 2
      t(col.label, tx, y + 5, { size: 6, color: C.light, bold: true, align: col.align === 'center' ? 'center' : col.align })
      cx += cw
    })
    y += 7.5
  }

  tableHeader()

  const ROW_H = 6.8
  const MAX_ROWS = 80

  ranking_completo.slice(0, MAX_ROWS).forEach((d, ri) => {
    checkBreak(ROW_H + 2)

    // Alternating stripe
    if (ri % 2 === 0) fill(M, y, CW, ROW_H, [245, 247, 250])

    const score = d.score_recuperabilidade ?? 0
    const prio  = prioridadePorRankAscii(d.rank, ranking_completo.length)
    const scoreColor = score >= 70 ? C.emerald : score >= 40 ? C.amber : C.light
    const prioColor  = prio === 'Alta' ? C.emerald : prio === 'Media' ? C.amber : C.light

    const cells = [
      { val: String(d.rank),                                                                       col: 0 },
      { val: (d.nome    ?? '').slice(0, 30),                                                       col: 1 },
      { val: d.cpf      ?? '',                                                                     col: 2 },
      { val: (d.produto ?? '').slice(0, 13),                                                       col: 3 },
      { val: fmtBRL(d.valor_divida ?? 0),                                                          col: 4 },
      { val: d.valor_esperado_recuperacao != null ? fmtBRL(d.valor_esperado_recuperacao) : '—',   col: 5 },
      { val: String(score),                                                                         col: 6, color: scoreColor, bold: true },
      { val: prio,                                                                                  col: 7, color: prioColor,  bold: true },
    ]

    let cx = M
    cells.forEach(({ val, col, color: cellColor, bold }) => {
      const colDef = COLS[col]
      const cw = colDef.w * scale
      const tx = colDef.align === 'right'  ? cx + cw - 1.5
               : colDef.align === 'center' ? cx + cw / 2
               :                              cx + 2
      t(val, tx, y + 4.6, {
        size: 6.5,
        color: cellColor ?? C.mid,
        align: colDef.align === 'center' ? 'center' : colDef.align,
        bold: bold ?? false,
      })
      cx += cw
    })

    // Bottom divider
    doc.setDrawColor(...C.border)
    doc.setLineWidth(0.15)
    doc.line(M, y + ROW_H, PW - M, y + ROW_H)

    y += ROW_H
  })

  // Note if capped
  if (ranking_completo.length > MAX_ROWS) {
    y += 4
    t(
      `* Exibindo os ${MAX_ROWS} primeiros de ${fmtNum(ranking_completo.length)} devedores, ordenados por score de recuperabilidade.`,
      M, y, { size: 6, color: C.light }
    )
  }

  pageFooter()

  const date = new Date().toISOString().slice(0, 10)
  doc.save(`mizan-relatorio-${date}.pdf`)
}
