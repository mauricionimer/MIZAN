// Perfil de um agente: o que faz, como é controlado e o que decidiu nas últimas 24 h.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import AppShell from '../components/AppShell'
import ErroCarga from '../components/ErroCarga'
import StatCard from '../components/StatCard'
import { Retrato, MESAS, TIMES } from '../components/EscritorioAgentes'
import { COR_AGENTE } from './Agente'
import { useAuth } from '../context/AuthContext'
import { agentePerfil } from '../api'

const SOBRE = {
  Triagem: ['Lê cada mensagem: intenção, emoção, urgência e ironia.',
    ['Parar, pessoa ou sofrimento: regra em código, antes da IA', 'Ironia bloqueia o aceite (R13)', 'Resposta fora do formato vira o padrão']],
  Negociador: ['Conversa com o devedor e fecha acordos com 16 ferramentas.',
    ['Todo valor sai do simulador', 'Lei só com fonte da base', 'Cada ação passa pelo Auditor']],
  Supervisor: ['Resume o caso para a equipe e revisa o tom em conversas delicadas.',
    ['Não escreve ao devedor', 'Não libera nada', 'No máximo uma reescrita']],
  Estrategista: ['Decide como abordar cada devedor: tom, oferta inicial ou adiar.',
    ['Quem cobrar e o sorteio ficam em código', 'Ficha sem região, renda ou nome', 'Oferta só dentro da política']],
  Cientista: ['Compara agente e grupo sorteado e propõe o próximo passo.',
    ['Contas e selo de evidência em código', 'Número fora das contas é barrado', 'Só vale depois de aprovado']],
  Acompanhamento: ['Cuida das datas: lembra, oferece nova data ou chama uma pessoa.',
    ['Ações de um cardápio fechado', 'Valor igual ao do compromisso', 'Reserva: mensagem pronta']],
  Orquestrador: ['Recebe cada evento e chama o agente certo, um caso por vez.',
    ['Evento nunca roda duas vezes', 'Falhou duas vezes: vai para uma pessoa', 'Estado salvo a cada passo']],
  Auditor: ['Confere cada ação contra a política da empresa. A palavra final é dele.',
    ['Código, de propósito: não pode ser convencido', 'Regras R0 a R13', 'Toda decisão fica registrada']],
}

const hora = s => (s ? new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '')
const COR_RES = { ok: 'text-success', bloqueado: 'text-danger', erro: 'text-danger' }

function Numero({ rotulo, valor }) {
  return <StatCard label={rotulo} value={valor} />
}

const brl = (v) => v == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
const MOTIVO = { pedido_do_devedor: 'pediu uma pessoa', dificuldade_grave: 'dificuldade grave', atendimento_marcado: 'atendimento marcado',
  fora_da_politica: 'fora da política', duvida: 'dúvida', falha: 'falha' }

// Supervisor: o que as passagens para a equipe dizem (30 dias). Tudo contado em código.
function SinaisEquipe({ s }) {
  if (!s.passagens) return (
    <section className="mt-5 rounded-xl border border-line bg-surface p-4 text-sm text-ink-2">
      <h2 className="text-sm font-semibold text-ink">Passagens para a equipe</h2>
      <p className="mt-2">Nenhuma passagem nos últimos {s.dias} dias.</p>
    </section>
  )
  const motivos = Object.entries(s.por_motivo || {})
  return (
    <section className="mt-5 rounded-xl border border-line bg-surface p-4">
      <h2 className="text-sm font-semibold text-ink">Passagens para a equipe · {s.dias} dias</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Numero rotulo="Passagens" valor={s.passagens} />
        <Numero rotulo="Resumo ajudou" valor={s.nota_supervisor != null ? `${Math.round(s.nota_supervisor * 100)}% (${s.retornos})` : '—'} />
        <Numero rotulo="Disse quanto pode" valor={s.com_valor_dito} />
        <Numero rotulo="Nada coube" valor={s.nao_coube} />
      </div>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
        {motivos.map(([m, n]) => <span key={m}>{MOTIVO[m] || m}: <b className="text-ink">{n}</b></span>)}
        {s.valor_pedido_quando_nao_coube != null && (
          <span>Quando nada coube, o valor típico pedido era <b className="text-ink">{brl(s.valor_pedido_quando_nao_coube)}</b>;
            a menor parcela possível era <b className="text-ink">{brl(s.menor_parcela_possivel)}</b></span>
        )}
      </div>
    </section>
  )
}

export default function AgentePerfil() {
  const { nome } = useParams()
  const navigate = useNavigate()
  const { isComando } = useAuth()
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  useEffect(() => { setD(null); agentePerfil(nome).then(setD).catch(setErro) }, [nome])
  const cor = COR_AGENTE[nome] || '#94a3b8'
  const [faz, controles] = SOBRE[nome] || ['', []]
  const time = TIMES[MESAS[nome]?.time]?.nome

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl space-y-5">
        <button onClick={() => navigate('/agente')} className="flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
          <ArrowLeft className="h-4 w-4" /> Agentes</button>

        <div className="flex flex-wrap items-center gap-5 rounded-xl border border-line bg-surface p-5">
          <div className="rounded-xl px-3 pt-2" style={{ background: '#e5e9f1' }}><Retrato nome={nome} cor={cor} tamanho={56} /></div>
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold" style={{ color: cor }}>{nome}</h1>
            <p className="mt-0.5 text-sm text-ink-2">{faz}</p>
            <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
              {time && <span className="rounded bg-raise-2 px-2 py-0.5 text-ink-2">{time}</span>}
              {d && <span className={`rounded px-2 py-0.5 ${d.papel ? (d.ia_ligada ? 'bg-emerald-500/15 text-success' : 'bg-amber-500/15 text-warning') : 'bg-raise-2 text-ink-2'}`}>
                {d.papel ? (d.ia_ligada ? 'IA ligada' : 'IA desligada: em código') : 'Código'}</span>}
              {isComando && d?.modelo && <span className="rounded bg-raise-2 px-2 py-0.5 text-ink-3">{d.modelo}</span>}
              {isComando && d?.versao_prompt && <span className="rounded bg-raise-2 px-2 py-0.5 text-ink-3">{d.versao_prompt}</span>}
            </div>
          </div>
        </div>

        {erro && !d && <ErroCarga erro={erro} />}
        {!d && !erro && <div className="flex items-center gap-2 p-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> carregando…</div>}
        {d && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Numero rotulo="Ações (24 h)" valor={d.acoes} />
              <Numero rotulo="Bloqueios" valor={d.bloqueios} />
              <Numero rotulo={d.papel ? 'Sem IA (reserva)' : 'Erros'} valor={d.papel ? d.sem_ia : d.erros} />
              <Numero rotulo="Tempo médio" valor={d.tempo_medio_ms != null ? `${(d.tempo_medio_ms / 1000).toFixed(1).replace('.', ',')} s` : '—'} />
            </div>

            <div className="grid gap-5 md:grid-cols-[1fr_2fr]">
              <section className="rounded-xl border border-line bg-surface p-4">
                <h2 className="text-sm font-semibold text-ink">Como é controlado</h2>
                <ul className="mt-3 space-y-2">
                  {controles.map(c => <li key={c} className="flex gap-2 text-sm text-ink-2"><span style={{ color: cor }}>■</span>{c}</li>)}
                </ul>
                {isComando && d.papel && <p className="mt-4 text-xs text-ink-3">Custo nas últimas 24 h: US$ {Number(d.custo_usd || 0).toFixed(4).replace('.', ',')}</p>}
              </section>
              <section className="rounded-xl border border-line bg-surface p-4">
                <h2 className="text-sm font-semibold text-ink">Últimas decisões</h2>
                <ol className="mt-3 divide-y divide-line">
                  {(d.ultimas || []).map((p, k) => (
                    <li key={k} className="flex items-baseline justify-between gap-3 py-2 text-sm">
                      <span className="text-ink-2">{p.explicacao}
                        {p.resultado !== 'ok' && <span className={`ml-1 ${COR_RES[p.resultado] || ''}`}>· {p.regra || p.resultado}</span>}</span>
                      <span className="shrink-0 text-xs text-ink-3">{hora(p.criado_em)}</span>
                    </li>
                  ))}
                  {!(d.ultimas || []).length && <li className="py-2 text-sm text-ink-3">Nenhuma decisão nas últimas 24 h.</li>}
                </ol>
              </section>
            </div>
            {d.sinais_equipe && <SinaisEquipe s={d.sinais_equipe} />}
          </>
        )}
      </div>
    </AppShell>
  )
}
