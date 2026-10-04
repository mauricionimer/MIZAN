// F4 — roteiros: variáveis, canais e o preenchimento com os dados do devedor.
// A lista de variáveis espelha backend/roteiros.py (o servidor recusa as outras).

export const VARIAVEIS = [
  ['primeiro_nome', 'Primeiro nome'],
  ['nome', 'Nome completo'],
  ['valor_divida', 'Valor da dívida'],
  ['dias_atraso', 'Dias em atraso'],
  ['valor_proposta', 'Valor à vista'],
  ['parcelas', 'Nº de parcelas'],
  ['valor_parcela', 'Valor da parcela'],
  ['desconto', 'Desconto'],
  ['empresa', 'Empresa'],
  ['operador', 'Seu nome'],
]
const CONHECIDAS = new Set(VARIAVEIS.map(([k]) => k))

export const CANAIS = [
  { k: 'whatsapp', label: 'WhatsApp' },
  { k: 'sms', label: 'SMS' },
  { k: 'email', label: 'E-mail' },
  { k: 'telefone', label: 'Ligação' },
]

export const OFERTAS = [
  ['avista_10pct', '10% de desconto à vista'],
  ['parcelado_4x', 'Parcelado em 4x sem juros'],
  ['desconto_30pct', '30% de desconto à vista'],
  ['parcelado_12x', 'Parcelado em 12x'],
]
export const OFERTA_LABEL = Object.fromEntries(OFERTAS)

// Canal da recomendação (bandit) → canal do roteiro. "Carta" do bandit é carta/e-mail.
export const CANAL_DA_RECOMENDACAO = { whatsapp: 'whatsapp', telefone: 'telefone', carta: 'email' }

const brl = (v) => v == null ? null
  : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

export function variaveisDoTexto(texto) {
  return [...String(texto || '').matchAll(/\{([^{}]*)\}/g)].map(m => m[1].trim())
}

export function desconhecidas(texto) {
  return [...new Set(variaveisDoTexto(texto).filter(v => !CONHECIDAS.has(v)))]
}

// Valores das variáveis a partir do devedor e de UMA proposta (a do roteiro).
export function dadosParaRoteiro({ devedor, proposta, empresa, operador }) {
  const nome = (devedor?.nome || '').trim()
  return {
    primeiro_nome: nome ? nome.split(/\s+/)[0] : null,
    nome: nome || null,
    valor_divida: brl(devedor?.valor_divida),
    dias_atraso: devedor?.dias_em_atraso != null ? String(devedor.dias_em_atraso) : null,
    valor_proposta: brl(proposta?.valor_cobrado),
    parcelas: proposta?.n_parcelas != null ? String(proposta.n_parcelas) : null,
    valor_parcela: brl(proposta?.parcela),
    desconto: proposta?.desconto_pct != null ? `${Math.round(proposta.desconto_pct)}%` : null,
    empresa: empresa || null,
    operador: operador ? operador.trim().split(/\s+/)[0] : null,
  }
}

// Troca as variáveis pelos valores. O que não tem valor fica marcado como
// [falta: ...] — o operador vê na hora em vez de mandar "{valor_parcela}".
export function preencher(texto, dados) {
  const faltando = []
  const saida = String(texto || '').replace(/\{([^{}]*)\}/g, (m, chave) => {
    const k = chave.trim()
    if (!CONHECIDAS.has(k)) return m
    const v = dados?.[k]
    if (v == null || v === '') { faltando.push(k); return `[falta: ${VARIAVEIS.find(([x]) => x === k)[1].toLowerCase()}]` }
    return v
  })
  return { texto: saida, faltando: [...new Set(faltando)] }
}

// Devedor de exemplo para a prévia do editor (aparece rotulado como exemplo).
export const EXEMPLO = {
  devedor: { nome: 'Maria Aparecida Souza', valor_divida: 2450, dias_em_atraso: 120 },
  propostas: {
    avista_10pct:   { valor_cobrado: 2205, n_parcelas: 1, parcela: 2205, desconto_pct: 10 },
    desconto_30pct: { valor_cobrado: 1715, n_parcelas: 1, parcela: 1715, desconto_pct: 30 },
    parcelado_4x:   { valor_cobrado: 2450, n_parcelas: 4, parcela: 612.5, desconto_pct: 0 },
    parcelado_12x:  { valor_cobrado: 2450, n_parcelas: 12, parcela: 204.17, desconto_pct: 0 },
  },
}

export function linkWhatsApp(texto) {
  return `https://wa.me/?text=${encodeURIComponent(texto)}`
}
