// F3 — "Meu painel" (operador) e "Painel da equipe" (admin, COMANDO).
// Só contagens do que foi registrado; nada estimado (backend/painel.py).
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, Gauge, PhoneOutgoing, Handshake, Banknote, Target, Loader2, Info, ArrowRight } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import ErroCarga from '../components/ErroCarga'
import StatCard from '../components/StatCard'
import { KpiBento } from '../components/ui/stats-bento'
import { useAuth } from '../context/AuthContext'
import { buscarPainelOperador, buscarPainelEquipe, buscarPainelDeUmOperador, listarEmpresas } from '../api'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)
const fmtPct = (v) => v == null ? '—' : `${Math.round(v * 100)}%`
const PERIODOS = [['hoje', 'Hoje'], ['7d', '7 dias'], ['30d', '30 dias']]

function Cartao({ icone: Icone, rotulo, valor, nota, cor = 'text-royal', i = 0, link }) {
  return <StatCard icon={Icone} label={rotulo} value={valor} nota={nota} corClasse={cor} i={i} link={link} />
}

function BarraMeta({ feitos, meta, compacta = false }) {
  if (!meta) return null
  const pct = Math.min(1, feitos / meta)
  const bateu = feitos >= meta
  return (
    <div className={compacta ? 'min-w-[7rem]' : ''}>
      {!compacta && (
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <p className="text-sm text-ink"><span className="text-2xl font-bold tabular-nums">{fmtNum(feitos)}</span> de {fmtNum(meta)} contatos hoje</p>
          <span className={`text-sm font-semibold ${bateu ? 'text-success' : 'text-ink-2'}`}>
            {bateu ? 'Meta batida' : `faltam ${fmtNum(meta - feitos)}`}
          </span>
        </div>
      )}
      <div className={`${compacta ? 'h-1.5' : 'h-2.5'} overflow-hidden rounded-full bg-raise-3`}>
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct * 100}%` }} transition={{ duration: 0.6, ease: 'easeOut' }}
          className={`h-full rounded-full ${bateu ? 'bg-emerald-500' : 'bg-blue-500'}`} />
      </div>
      {compacta && <p className="mt-0.5 text-xs tabular-nums text-ink-2">{fmtNum(feitos)}/{fmtNum(meta)}</p>}
    </div>
  )
}

function Avisos({ d }) {
  const lista = []
  if (d && d.agenda_ativa === false) lista.push('Acordos ainda não aparecem: falta rodar sql/migracao_operador.sql no Supabase.')
  if (d && d.divisao_ativa === false) lista.push('“Recebido” por operador depende da divisão da fila: falta rodar sql/migracao_operador.sql no Supabase.')
  if (!lista.length) return null
  return lista.map(t => (
    <p key={t} className="flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {t}
    </p>
  ))
}

function MeusNumeros({ d }) {
  return (
    <>
      {d.meta_dia ? (
        <div className="rounded-xl border border-line bg-surface p-5">
          <p className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-2">
            <Target className="h-3.5 w-3.5 text-accent-text" /> Meta do dia
          </p>
          <BarraMeta feitos={d.contatos_hoje} meta={d.meta_dia} />
        </div>
      ) : null}
      <KpiBento>
        <Cartao i={0} icone={PhoneOutgoing} rotulo="Contatos feitos" valor={fmtNum(d.contatos)}
          nota={d.contatos ? `${fmtNum(d.contatos_efetivos)} efetivos · ${fmtPct(d.taxa_contato_efetivo)}` : 'Nenhum contato no período'} />
        <Cartao i={1} icone={Handshake} rotulo="Acordos fechados" valor={fmtNum(d.acordos)} cor="text-warning"
          nota={d.acordos ? `${fmtBRL(d.acordos_valor)} prometidos` : 'Promessas de pagamento registradas'} />
        <Cartao i={2} icone={Banknote} rotulo="Recebido" valor={fmtBRL(d.recebido)} cor="text-success"
          nota={`${fmtNum(d.pagamentos)} ${d.pagamentos === 1 ? 'pagamento confirmado' : 'pagamentos confirmados'} da sua fila`} />
        <Cartao i={3} icone={Gauge} rotulo="Promessas" valor={`${fmtNum(d.promessas_cumpridas)} pagas`} cor="text-ink-2"
          nota={`${fmtNum(d.promessas_quebradas)} não pagas · ${fmtNum(d.promessas_pendentes)} pendentes`}
          link={d.promessas_pendentes > 0 ? { to: '/agenda', label: 'Ver na Agenda' } : null} />
      </KpiBento>
    </>
  )
}

function Individual({ id, periodo, empresa, onVoltar }) {
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [tent, setTent] = useState(0)
  useEffect(() => {
    let vivo = true
    setErro(null)
    buscarPainelDeUmOperador(id, periodo, empresa).then(r => { if (vivo) setD(r) }).catch(e => { if (vivo) setErro(e) })
    return () => { vivo = false }
  }, [id, periodo, empresa, tent])
  const o = d?.ofertas, r = d?.retornos
  return (
    <section className="space-y-4">
      <button type="button" onClick={onVoltar} className="btn-ghost btn-sm inline-flex min-h-[40px] items-center gap-1">
        <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Voltar para a equipe
      </button>
      <ErroCarga erro={erro} onTentar={() => setTent(t => t + 1)} />
      {!d && !erro && <div className="flex items-center gap-2 py-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
      {d && (
        <>
          <h2 className="text-base font-semibold text-ink">{d.operador.nome}</h2>
          <KpiBento>
            <Cartao i={0} icone={PhoneOutgoing} rotulo="Contatos" valor={fmtNum(d.contatos)}
              nota={d.contatos ? `${fmtPct(d.taxa_contato_efetivo)} efetivos` : 'Nenhum contato no período'} />
            <Cartao i={1} icone={Target} rotulo="Devedores trabalhados" valor={fmtNum(d.devedores_trabalhados)} cor="text-accent-text" nota="Devedores diferentes contatados" />
            <Cartao i={2} icone={Handshake} rotulo="Promessas" valor={fmtNum(d.acordos)} cor="text-warning"
              nota={d.acordos ? `${fmtBRL(d.acordos_valor)} prometidos` : 'Promessas registradas'} />
            <Cartao i={3} icone={Gauge} rotulo="Promessas pagas" valor={fmtNum(d.promessas_cumpridas)} cor="text-ink-2"
              nota={`${fmtNum(d.promessas_quebradas)} não pagas · ${fmtNum(d.promessas_pendentes)} pendentes`} />
            <Cartao i={4} icone={Banknote} rotulo="Valor recuperado" valor={fmtBRL(d.recebido)} cor="text-success" nota={`${fmtNum(d.pagamentos)} pagamentos confirmados`} />
            <Cartao i={5} icone={Handshake} rotulo="Ofertas feitas" valor={o.ativo ? fmtNum(o.feitas) : '—'} cor="text-accent-text"
              nota={o.ativo ? `${fmtNum(o.aceitas)} aceitas · ${fmtNum(o.vai_pensar)} a pensar · ${fmtNum(o.recusadas)} recusadas` : 'Disponível após ativar o histórico de ofertas'} />
            <Cartao i={6} icone={ArrowRight} rotulo="Retornos marcados" valor={r.ativo ? fmtNum(r.marcados) : '—'} cor="text-warning"
              nota={r.ativo ? `${fmtNum(r.feitos)} feitos · ${fmtNum(r.pendentes)} pendentes` : 'Disponível com a Agenda ativa'} />
          </KpiBento>
        </>
      )}
    </section>
  )
}

function Equipe({ d, comando, onAbrir }) {
  const t = d.total
  return (
    <>
      <KpiBento>
        <Cartao i={0} icone={PhoneOutgoing} rotulo="Contatos da equipe" valor={fmtNum(t.contatos)}
          nota={t.contatos ? `${fmtPct(t.taxa_contato_efetivo)} efetivos` : 'Nenhum contato no período'} />
        <Cartao i={1} icone={Handshake} rotulo="Acordos fechados" valor={fmtNum(t.acordos)} cor="text-warning"
          nota={t.acordos ? `${fmtBRL(t.acordos_valor)} prometidos` : 'Promessas registradas'} />
        <Cartao i={2} icone={Banknote} rotulo="Recebido" valor={fmtBRL(t.recebido)} cor="text-success"
          nota={d.recebido_sem_responsavel > 0 ? `${fmtBRL(d.recebido_sem_responsavel)} de devedores sem responsável` : `${fmtNum(t.pagamentos)} pagamentos confirmados`} />
        <Cartao i={3} icone={Gauge} rotulo="Promessas" valor={`${fmtNum(t.promessas_cumpridas)} pagas`} cor="text-ink-2"
          nota={`${fmtNum(t.promessas_quebradas)} não pagas · ${fmtNum(t.promessas_pendentes)} pendentes`}
          link={t.promessas_pendentes > 0 && !comando ? { to: '/agenda', label: 'Ver na Agenda' } : null} />
      </KpiBento>
      <section className="overflow-hidden rounded-xl border border-line bg-surface">
        <div className="border-b border-line px-5 py-3">
          <h2 className="section-label">Por operador <span className="font-normal normal-case tracking-normal text-ink-2">· clique no nome para ver o desempenho individual</span></h2>
        </div>
        {d.operadores.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-ink-2">Nenhum operador ativo nesta empresa.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-2">
                <tr>
                  {['Operador', 'Contatos', 'Efetivos', 'Acordos', 'Pagas', 'Não pagas', 'Recebido', ...(d.meta_dia ? ['Meta hoje'] : [])].map((h, k) => (
                    <th key={h} className={`whitespace-nowrap px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-ink-2 ${k ? 'text-right' : 'text-left'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.operadores.map(o => (
                  <tr key={o.operador_id} className="border-b border-line last:border-0">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-ink">
                      <button type="button" onClick={() => onAbrir(o.operador_id)} className="min-h-[40px] text-left text-accent-text hover:opacity-80">{o.nome}</button>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{fmtNum(o.contatos)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-2">{fmtPct(o.taxa_contato_efetivo)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{fmtNum(o.acordos)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-success">{fmtNum(o.promessas_cumpridas)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-danger">{fmtNum(o.promessas_quebradas)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-ink">{fmtBRL(o.recebido)}</td>
                    {d.meta_dia ? <td className="px-4 py-3"><div className="ml-auto w-28"><BarraMeta compacta feitos={o.contatos_hoje} meta={d.meta_dia} /></div></td> : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {!d.meta_dia && <p className="text-xs text-ink-2">Para acompanhar a meta diária, informe “Meta de contatos por operador por dia” em Premissas.</p>}
    </>
  )
}

export default function PainelOperador() {
  const { token, isOperador, isComando } = useAuth()
  const equipe = !isOperador
  const [periodo, setPeriodo] = useState('hoje')
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [tentativa, setTentativa] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  const [opSel, setOpSel] = useState(null)

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  useEffect(() => {
    if (isComando && !alvo) { setDados(null); setCarregando(false); return }
    let vivo = true
    setCarregando(true); setErro(null)
    ;(equipe ? buscarPainelEquipe(periodo, isComando ? alvo : undefined) : buscarPainelOperador(periodo))
      .then(d => { if (vivo) setDados(d) })
      .catch(e => { if (vivo) setErro(e) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [periodo, equipe, isComando, alvo, tentativa])

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
              <Gauge className="h-5 w-5 text-accent-text" /> {equipe ? 'Painel da equipe' : 'Meu painel'}<DicaAjuda id="painel-do-operador" />
            </h1>
            <p className="mt-1 text-sm text-ink-2">
              {equipe ? 'Contatos, acordos e quanto entrou, por operador.' : 'Seus contatos, acordos e quanto entrou da sua fila.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isComando && (
              <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
                className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            <div className="flex rounded-lg border border-line bg-surface-2 p-0.5" role="tablist" aria-label="Período">
              {PERIODOS.map(([k, l]) => (
                <button key={k} role="tab" aria-selected={periodo === k} onClick={() => setPeriodo(k)}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${periodo === k ? 'bg-surface text-ink shadow-sm' : 'text-ink-2 hover:text-ink'}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>

        {isComando && !alvo && (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver o painel da equipe.</div>
        )}
        <ErroCarga erro={erro} ocupado={carregando} onTentar={() => setTentativa(t => t + 1)} />
        {carregando && !dados && (
          <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
        )}
        {dados && (
          <div className={`space-y-4 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
            <Avisos d={dados} />
            {equipe ? (opSel
              ? <Individual id={opSel} periodo={periodo} empresa={isComando ? alvo : undefined} onVoltar={() => setOpSel(null)} />
              : <Equipe d={dados} comando={isComando} onAbrir={setOpSel} />) : <MeusNumeros d={dados} />}
          </div>
        )}
      </div>
    </AppShell>
  )
}
