// Contas puras do sino de notificações (docs/NOTIFICACOES.md). Testadas em
// frontend/tests/notificacoes.test.mjs; a tela só desenha o que sai daqui.

export const CATEGORIAS = [
  { id: 'conversas', rotulo: 'Conversas', dica: 'Mensagens novas, casos passados para a equipe e risco grave' },
  { id: 'reunioes', rotulo: 'Reuniões', dica: 'Pedidos, aprovações, horários e lembretes' },
  { id: 'retornos', rotulo: 'Retornos e pagamentos', dica: 'Agenda do dia, promessas, pagamentos e acordos' },
  { id: 'pedidos', rotulo: 'Pedidos e LGPD', dica: 'Contestação, pedido para parar e dados pessoais' },
  { id: 'equipe', rotulo: 'Equipe', dica: 'Devedores recebidos, tarefas e dúvidas respondidas' },
  { id: 'sistema', rotulo: 'Sistema', dica: 'Agente parado, conexões, Cientista e segurança', soAdmin: true },
]

const MIN = 60_000
const fuso = { timeZone: 'America/Sao_Paulo' }

function diaLocal(d) {
  return new Intl.DateTimeFormat('pt-BR', { ...fuso, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d)
}

function horaLocal(d) {
  return new Intl.DateTimeFormat('pt-BR', { ...fuso, hour: '2-digit', minute: '2-digit' }).format(d)
}

function quandoDe(item) {
  const d = new Date(item?.atualizado_em || item?.criado_em || 0)
  return Number.isNaN(d.getTime()) ? new Date(0) : d
}

/** "agora", "há 5 min", "há 2 h", "ontem às 14:30" ou "03/11 às 9:05" (horário de Brasília). */
export function tempoRelativo(iso, agora = new Date()) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = agora.getTime() - d.getTime()
  if (diff < MIN) return 'agora'
  if (diff < 60 * MIN) return `há ${Math.floor(diff / MIN)} min`
  if (diaLocal(d) === diaLocal(agora)) return `há ${Math.floor(diff / (60 * MIN))} h`
  const ontem = new Date(agora.getTime() - 24 * 60 * MIN)
  if (diaLocal(d) === diaLocal(ontem)) return `ontem às ${horaLocal(d)}`
  return `${diaLocal(d).slice(0, 5)} às ${horaLocal(d)}`
}

/** Seções do painel: "Agora" (última hora), "Hoje" e "Antes". Seções vazias não aparecem. */
export function secoes(itens, agora = new Date()) {
  const grupos = { agora: [], hoje: [], antes: [] }
  const ordenados = [...(itens || [])].sort((a, b) => quandoDe(b) - quandoDe(a))
  for (const it of ordenados) {
    const d = quandoDe(it)
    if (agora.getTime() - d.getTime() < 60 * MIN) grupos.agora.push(it)
    else if (diaLocal(d) === diaLocal(agora)) grupos.hoje.push(it)
    else grupos.antes.push(it)
  }
  return [
    { id: 'agora', titulo: 'Agora', itens: grupos.agora },
    { id: 'hoje', titulo: 'Hoje', itens: grupos.hoje },
    { id: 'antes', titulo: 'Antes', itens: grupos.antes },
  ].filter(s => s.itens.length)
}

const DIAS = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado']

function chaveDoDia(d) {
  // AAAA-MM-DD no horário de Brasília (en-CA já sai nesse formato).
  return new Intl.DateTimeFormat('en-CA', { ...fuso, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d)
}

/**
 * A página de notificações agrupa por dia: "Hoje", "Ontem" e, antes disso,
 * "Terça-feira, 03/11". Os dias vêm do mais novo para o mais antigo.
 */
export function porDia(itens, agora = new Date()) {
  const hoje = chaveDoDia(agora)
  const ontem = chaveDoDia(new Date(agora.getTime() - 24 * 60 * MIN))
  const grupos = new Map()
  for (const it of [...(itens || [])].sort((a, b) => quandoDe(b) - quandoDe(a))) {
    const d = quandoDe(it)
    const chave = chaveDoDia(d)
    if (!grupos.has(chave)) {
      const [a, m, dia] = chave.split('-').map(Number)
      const semana = DIAS[new Date(Date.UTC(a, m - 1, dia, 12)).getUTCDay()]
      const titulo = chave === hoje ? 'Hoje' : chave === ontem ? 'Ontem' : `${semana}, ${String(dia).padStart(2, '0')}/${String(m).padStart(2, '0')}`
      grupos.set(chave, { id: chave, titulo, itens: [] })
    }
    grupos.get(chave).itens.push(it)
  }
  return [...grupos.values()]
}

/** Só telas internas do Mizan: qualquer outra coisa vira o Início. */
export function linkInterno(link) {
  const l = String(link || '')
  return l.startsWith('/') && !l.startsWith('//') && !l.includes('\\') && !/^\/[a-z]+:/i.test(l) ? l : '/inicio'
}

/** "(3) Mizan — …": o número de não lidas na aba do navegador. */
export function tituloDaAba(base, naoLidas) {
  const limpo = String(base || '').replace(/^\(\d+\+?\)\s*/, '')
  if (!naoLidas || naoLidas < 1) return limpo
  return `(${naoLidas > 99 ? '99+' : naoLidas}) ${limpo}`
}

/** Texto para leitor de tela do botão do sino. */
export function rotuloDoSino(naoLidas, urgentes) {
  if (!naoLidas) return 'Notificações: nenhuma nova'
  const n = `${naoLidas} ${naoLidas === 1 ? 'nova' : 'novas'}`
  return urgentes ? `Notificações: ${n}, ${urgentes} ${urgentes === 1 ? 'urgente' : 'urgentes'}` : `Notificações: ${n}`
}

/**
 * O que deve chamar a atenção agora: itens que o servidor marcou como "toca"
 * (urgente sempre; alta fora do horário silencioso), ainda não lidos e que esta
 * aba ainda não mostrou. Os mais novos primeiro.
 */
export function novasQueTocam(itens, jaMostradas) {
  const vistas = jaMostradas instanceof Set ? jaMostradas : new Set(jaMostradas || [])
  return [...(itens || [])]
    .filter(i => i && i.toca && !i.lida && !i.resolvida && !vistas.has(i.id))
    .sort((a, b) => quandoDe(b) - quandoDe(a))
}

/** O aviso na tela (rodapé) é só para o urgente. */
export function urgenteParaAvisar(itens, jaMostradas) {
  return novasQueTocam(itens, jaMostradas).find(i => i.prioridade === 'urgente') || null
}

/** Preferências que a tela mostra: as categorias de cada papel. */
export function categoriasDoPapel(ehAdmin) {
  return CATEGORIAS.filter(c => ehAdmin || !c.soAdmin)
}

/** Lista de horas para o horário silencioso ("20h"). */
// ── Lixeira ──────────────────────────────────────────────────────────────────
/** A notificação entra em "Excluir as lidas" com este filtro ({ categoria, prioridade }; vazio = todas)? */
export function naFaixa(item, faixa) {
  return !!item?.lida && (!faixa?.categoria || item.categoria === faixa.categoria)
    && (!faixa?.prioridade || item.prioridade === faixa.prioridade)
}

/** Tira das contagens do sino as não lidas que saíram da lista (excluídas ou esperando o "Desfazer"). */
export function descontar(estado, saem) {
  const naoLidas = (saem || []).filter(i => i && !i.lida)
  const porCategoria = { ...(estado?.por_categoria || {}) }
  naoLidas.forEach(i => { if (porCategoria[i.categoria] > 0) porCategoria[i.categoria] -= 1 })
  return {
    naoLidas: Math.max(0, (estado?.naoLidas || 0) - naoLidas.length),
    urgentes: Math.max(0, (estado?.urgentes || 0) - naoLidas.filter(i => i.prioridade === 'urgente').length),
    por_categoria: porCategoria,
  }
}

export const HORAS = Array.from({ length: 24 }, (_, h) => ({ valor: h, rotulo: `${h}h` }))
