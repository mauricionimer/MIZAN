// Contas de oferta — espelho de backend/model/oferta.py (o servidor refaz e manda).
export function parcelaPrice(saldo, n, jurosPct) {
  const i = Number(jurosPct) / 100
  if (n <= 0) return 0
  if (!(i > 0)) return saldo / n
  return saldo * i / (1 - Math.pow(1 + i, -n))
}

export function calcularOferta(divida, { desconto_pct = 0, entrada_pct = 0, n_parcelas = 1, juros_mensal_pct = 0 }) {
  const d = Math.max(0, Number(divida) || 0)
  const n = Math.max(1, parseInt(n_parcelas, 10) || 1)
  const negociado = d * (1 - (Number(desconto_pct) || 0) / 100)
  if (n === 1) return { valor_negociado: negociado, entrada: 0, parcela: negociado, total_pago: negociado, economia: Math.max(0, d - negociado), juros_total: 0 }
  const entrada = negociado * (Number(entrada_pct) || 0) / 100
  const parcela = parcelaPrice(negociado - entrada, n, juros_mensal_pct)
  const total = entrada + parcela * n
  return { valor_negociado: negociado, entrada, parcela, total_pago: total, economia: Math.max(0, d - total), juros_total: Math.max(0, total - negociado) }
}

export function familia(n, desconto) {
  if ((parseInt(n, 10) || 1) <= 1) return Number(desconto) <= 15 ? 'avista_10pct' : 'desconto_30pct'
  return (parseInt(n, 10) || 1) <= 6 ? 'parcelado_4x' : 'parcelado_12x'
}

export const NOME_FAMILIA = {
  avista_10pct: 'à vista, desconto pequeno',
  desconto_30pct: 'à vista, desconto grande',
  parcelado_4x: 'parcelado curto (até 6x)',
  parcelado_12x: 'parcelado longo (7x ou mais)',
}

const brl = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)
const num = (v) => String(Number(v)).replace('.', ',')

export function resumoOferta(o) {
  const n = parseInt(o.n_parcelas, 10) || 1
  const partes = []
  if (n === 1) partes.push('À vista')
  else partes.push(`${Number(o.entrada_pct) > 0 ? `entrada de ${num(o.entrada_pct)}% + ` : ''}${n}x`)
  if (Number(o.desconto_pct) > 0) partes.push(`${num(o.desconto_pct)}% de desconto`)
  if (n > 1) partes.push(Number(o.juros_mensal_pct) > 0 ? `${num(o.juros_mensal_pct)}% a.m.` : 'sem juros')
  return partes.join(' · ')
}

export { brl }
