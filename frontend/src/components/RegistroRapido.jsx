// P4 — "Não atendeu" em um toque: registra o contato como sem resposta, no canal
// já marcado, e agenda o retorno para amanhã. Só pergunta quando o devedor já
// tem um compromisso pendente na Agenda (para não duplicar).
import { useEffect, useRef, useState } from 'react'
import { PhoneMissed, Loader2, CheckCircle2 } from 'lucide-react'
import ErroCarga from './ErroCarga'
import TituloRecolhivel from './TituloRecolhivel'
import { listarAgenda, registrarContato } from '../api'
import { TIPO_LABEL, quando, hojeISO, somarDias, avisarAgendaMudou } from '../utils/agenda'

const CANAIS = { telefone: 'Ligação', whatsapp: 'WhatsApp', carta: 'Carta / e-mail' }

export default function RegistroRapido({ cpf, canalPadrao, onRegistrado }) {
  const [canal, setCanal] = useState(canalPadrao in CANAIS ? canalPadrao : 'telefone')
  const mexeu = useRef(false)          // o operador escolheu: a recomendação não troca
  useEffect(() => { if (!mexeu.current && canalPadrao in CANAIS) setCanal(canalPadrao) }, [canalPadrao])
  const [fase, setFase] = useState('livre')           // livre | enviando | conflito
  const [aberto, setAberto] = useState(false)
  const [pendentes, setPendentes] = useState([])
  const [erro, setErro] = useState(null)
  const [aviso, setAviso] = useState('')
  const ultima = useRef(true)                          // última escolha, para o "Tentar novamente"

  async function enviar(comRetorno) {
    ultima.current = comRetorno
    setFase('enviando'); setErro(null); setAviso('')
    try {
      const payload = { cpf, canal, resultado: 'sem_resposta', data_contato: hojeISO() }
      if (comRetorno) payload.agenda = { tipo: 'retorno', data: somarDias(hojeISO(), 1) }
      const r = await registrarContato(payload)
      const partes = [`Não atendeu (${CANAIS[canal].toLowerCase()}) registrado.`]
      if (r.agenda) { partes.push(`Retorno ${quando(r.agenda.data, r.agenda.hora).toLowerCase()} na Agenda.`); avisarAgendaMudou() }
      else if (r.agenda_erro) partes.push(`O retorno não entrou na Agenda: ${r.agenda_erro}`)
      setAviso(partes.join(' '))
      setFase('livre')
      onRegistrado?.()
    } catch (e) { setErro(e); setFase('livre') }
  }

  async function iniciar() {
    if (fase !== 'livre') return
    setFase('enviando'); setErro(null); setAviso('')
    let lista = []
    // Sem a Agenda ativa (ou sem conseguir consultar) não há o que duplicar: o
    // próprio registro avisa se algo falhar.
    try {
      const r = await listarAgenda({ cpf, escopo: 'equipe', situacao: 'pendente' })
      lista = r?.ativo ? (r.itens ?? []) : []
    } catch { lista = [] }
    if (lista.length) { setPendentes(lista); setFase('conflito'); return }
    await enviar(true)
  }

  const ocupado = fase === 'enviando'
  const sel = { background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }
  return (
    <div className="rounded-2xl px-4 py-3.5 sm:px-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
      <TituloRecolhivel aberto={aberto} onAlternar={() => setAberto(a => !a)}>
        <PhoneMissed className="h-4 w-4 shrink-0" style={{ color: 'var(--ink-3)' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>Não conseguiu falar com o devedor?</span>
      </TituloRecolhivel>
      {aberto && <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
        <p className="min-w-0 flex-1 basis-56 text-xs" style={{ color: 'var(--ink-2)' }}>Escolha o canal que você tentou: o contato fica registrado como “sem resposta” e o retorno vai para a Agenda amanhã.</p>
        <label className="sr-only" htmlFor="canal-rapido">Canal usado</label>
        <select id="canal-rapido" value={canal} disabled={ocupado || fase === 'conflito'}
          onChange={e => { mexeu.current = true; setCanal(e.target.value) }}
          className="h-11 rounded-lg px-3 text-sm md:h-10" style={sel}>
          {Object.entries(CANAIS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button type="button" onClick={iniciar} disabled={ocupado || fase === 'conflito'} className="btn-secondary min-h-[44px] md:min-h-[40px]">
          {ocupado ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneMissed className="h-4 w-4" />} Não atendeu
        </button>
      </div>}

      {fase === 'conflito' && (
        <div role="alert" className="mt-3 rounded-xl p-3" style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.25)' }}>
          <p className="text-sm" style={{ color: 'var(--ink)' }}>
            Este devedor já tem na Agenda: {pendentes.map(i => `${TIPO_LABEL[i.tipo]} ${quando(i.data, i.hora).toLowerCase()}`).join(' e ')}.
            Agendar outro retorno para amanhã?
          </p>
          <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => enviar(true)} className="btn-primary min-h-[44px]">Registrar e agendar amanhã</button>
            <button type="button" onClick={() => enviar(false)} className="btn-secondary min-h-[44px]">Só registrar o contato</button>
            <button type="button" onClick={() => setFase('livre')} className="btn-ghost min-h-[44px]">Cancelar</button>
          </div>
        </div>
      )}

      {aviso && !erro && (
        <p className="mt-3 flex items-start gap-1.5 text-sm" style={{ color: aviso.includes('não entrou') ? 'var(--warning)' : 'var(--success)' }}>
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {aviso}
        </p>
      )}
      <ErroCarga erro={erro} onTentar={() => enviar(ultima.current)} compacto className="mt-3" />
    </div>
  )
}
