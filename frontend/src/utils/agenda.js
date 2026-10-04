// F2 — apresentação da agenda: níveis de aviso e datas legíveis.
// O nível vem calculado do servidor (agenda.py); aqui só a cor e o texto.

export const NIVEIS = ['alto', 'medio', 'safe']

export const NIVEL_CFG = {
  alto:  { label: 'Alto',  dica: 'Venceu e segue pendente', cor: 'var(--danger)',  fundo: 'rgb(var(--c-danger) / 0.10)',  borda: 'rgb(var(--c-danger) / 0.25)' },
  medio: { label: 'Médio', dica: 'Vence hoje ou amanhã',    cor: 'var(--warning)', fundo: 'rgb(var(--c-warning) / 0.10)', borda: 'rgb(var(--c-warning) / 0.25)' },
  safe:  { label: 'Safe',  dica: 'Daqui a 2 dias ou mais',  cor: 'var(--success)', fundo: 'rgb(var(--c-success) / 0.10)', borda: 'rgb(var(--c-success) / 0.25)' },
}

export const TIPO_LABEL = { promessa: 'Promessa', retorno: 'Retorno' }

const _dia = (iso) => new Date(String(iso).slice(0, 10) + 'T12:00:00')

// "hoje" no formato AAAA-MM-DD, no fuso do navegador (o do operador).
export function hojeISO() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function somarDias(iso, n) {
  const d = _dia(iso); d.setDate(d.getDate() + n)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// "Hoje", "Amanhã", "Ontem", "há 3 dias", "sex., 17/10".
export function quando(dataISO, hora, hoje = hojeISO()) {
  const dias = Math.round((_dia(dataISO) - _dia(hoje)) / 86400000)
  let txt
  if (dias === 0) txt = 'Hoje'
  else if (dias === 1) txt = 'Amanhã'
  else if (dias === -1) txt = 'Ontem'
  else if (dias < 0) txt = `Venceu há ${-dias} dias`
  else txt = new Intl.DateTimeFormat('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' }).format(_dia(dataISO))
  return hora ? `${txt} · ${hora}` : txt
}

// Texto curto do selo na linha da fila.
export function seloFila(ag) {
  if (!ag) return null
  const tipo = ag.tipo === 'promessa' ? 'Promessa' : 'Retorno'
  if (ag.nivel === 'alto') return ag.tipo === 'promessa' ? 'Promessa vencida' : 'Retorno atrasado'
  const q = quando(ag.data, null)
  return `${tipo} ${q.toLowerCase()}`
}

// Avisa as outras partes da tela (menu, fila) que a agenda mudou.
export function avisarAgendaMudou() {
  window.dispatchEvent(new Event('mizan:agenda'))
}
