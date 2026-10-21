import React from 'react'
import { ArrowUpRight, CalendarClock } from 'lucide-react'
import './agenda-equipe-bento.css'

export interface AgendaEquipe {
  id: string
  nome: string
  total: number
  alto: number
  medio: number
  safe: number
}

export interface StatsBentoProps {
  operadores: AgendaEquipe[]
  onSelecionar: (operador: AgendaEquipe) => void
}

const numero = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const contagem = (n: number, singular: string, plural: string) => `${numero(n)} ${n === 1 ? singular : plural}`

// Indicadores e navegação exclusivos de Agenda → Equipe.
export default function StatsBento({ operadores, onSelecionar }: StatsBentoProps) {
  const resumo = operadores.reduce((s, o) => ({
    total: s.total + o.total,
    alto: s.alto + o.alto,
    medio: s.medio + o.medio,
    safe: s.safe + o.safe,
  }), { total: 0, alto: 0, medio: 0, safe: 0 })

  return (
    <section className="agenda-equipe-bento" aria-label="Resumo e agendas da equipe">
      <div className="agenda-equipe-bento__resumo">
        <div className="agenda-equipe-bento__trama" aria-hidden="true" />
        <div className="agenda-equipe-bento__conteudo">
          <span className="agenda-equipe-bento__etiqueta"><CalendarClock size={14} aria-hidden="true" /> Agenda da equipe</span>
          <p className="agenda-equipe-bento__total">{numero(resumo.total)}</p>
          <h2>Compromissos pendentes</h2>
        </div>
        <div className="agenda-equipe-bento__conteudo">
          <p className="agenda-equipe-bento__nota">{contagem(resumo.alto, 'vencido', 'vencidos')} · {numero(resumo.medio)} para hoje ou amanhã · {numero(resumo.safe)} depois</p>
          <span className="agenda-equipe-bento__rodape">{contagem(operadores.length, 'agenda disponível', 'agendas disponíveis')}</span>
        </div>
      </div>

      {operadores.map((o, i) => {
        const iniciais = (o.nome || '?').split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase()
        const proporcao = o.alto + o.medio + o.safe
        return (
          <button key={o.id} type="button" onClick={() => onSelecionar(o)}
            className={`agenda-equipe-bento__agenda ${i === 0 || operadores.length < 3 ? 'agenda-equipe-bento__agenda--larga' : i === 1 ? 'agenda-equipe-bento__agenda--compacta' : 'agenda-equipe-bento__agenda--regular'}`}
            aria-label={`Abrir agenda de ${o.nome}: ${contagem(o.total, 'pendência', 'pendências')}, ${contagem(o.alto, 'vencida', 'vencidas')}`}>
            <span className="agenda-equipe-bento__cabecalho">
              <span className="agenda-equipe-bento__avatar" aria-hidden="true">{iniciais}</span>
              <ArrowUpRight size={18} className="agenda-equipe-bento__seta" aria-hidden="true" />
            </span>
            <span className="agenda-equipe-bento__nome">{o.nome}</span>
            <span className="agenda-equipe-bento__numero">{numero(o.total)} <span>{o.total === 1 ? 'pendência' : 'pendências'}</span></span>
            <span className="agenda-equipe-bento__prazos">
              <span className={o.alto > 0 ? 'agenda-equipe-bento__vencido' : ''}>{contagem(o.alto, 'vencido', 'vencidos')}</span>
              <span>{numero(o.medio)} para hoje/amanhã</span>
              <span>{numero(o.safe)} depois</span>
            </span>
            {proporcao > 0 && <span className="agenda-equipe-bento__barra" aria-hidden="true">
              <span style={{ width: `${o.alto / proporcao * 100}%`, background: 'var(--danger)' }} />
              <span style={{ width: `${o.medio / proporcao * 100}%`, background: 'var(--warning)' }} />
              <span style={{ width: `${o.safe / proporcao * 100}%`, background: 'var(--royal)' }} />
            </span>}
            {o.total === 0 && <span className="agenda-equipe-bento__sem-pendencia">Nada pendente</span>}
          </button>
        )
      })}
    </section>
  )
}
