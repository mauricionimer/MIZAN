// F3 — "Meu painel" (operador) e "Painel da equipe" (admin, COMANDO).
// Só contagens do que foi registrado; nada estimado (backend/painel.py).
// Layout da prancha "Equipe": três números numa linha e, por operador, uma frase que
// responde "quem converte melhor?" seguida da tabela com barras finas.
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, Users, Gauge, Loader2, Info, ChevronRight } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import ErroCarga from '../components/ErroCarga'
import { useAuth } from '../context/AuthContext'
import { buscarPainelOperador, buscarPainelEquipe, buscarPainelDeUmOperador, listarEmpresas } from '../api'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)
const fmtPct = (v) => v == null ? '—' : `${Math.round(v * 100)}%`
const PERIODOS = [['hoje', 'Hoje'], ['7d', '7 dias'], ['30d', '30 dias']]
const NO_PERIODO = { hoje: 'hoje', '7d': 'nos últimos 7 dias', '30d': 'nos últimos 30 dias' }
const plural = (n, um, varios) => `${fmtNum(n)} ${n === 1 ? um : varios}`
const iniciais = (nome) => String(nome || '').trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase() || '·'
// "1 a cada N contatos" vira acordo. Sem acordo, não há razão.
const umACada = (contatos, acordos) => acordos > 0 && contatos > 0 ? Math.max(1, Math.round(contatos / acordos)) : null
// Promessas pagas entre as que já venceram (pagas + não pagas); as pendentes ainda não contam.
const taxaPagas = (o) => { const n = (o.promessas_cumpridas || 0) + (o.promessas_quebradas || 0); return n ? o.promessas_cumpridas / n : null }

// Três números numa linha, separados por hairlines (prancha: Contatos, Acordos, Recebido).
function Numeros({ itens }) {
  return (
    <section className="grid grid-cols-1 divide-y divide-line rounded-[22px] border border-line bg-surface sm:grid-cols-3 sm:divide-x sm:divide-y-0">
      {itens.map(({ rotulo, valor, nota, cor }) => (
        <div key={rotulo} className="flex min-w-0 flex-col gap-1 px-6 py-5">
          <span className="text-[13px] text-ink-2">{rotulo}</span>
          <span className={`text-[28px] font-bold leading-none tabular-nums ${cor || 'text-ink'}`}>{valor}</span>
          {nota && <span className="text-xs text-ink-2">{nota}</span>}
        </div>
      ))}
    </section>
  )
}

function BarraMeta({ feitos, meta }) {
  if (!meta) return null
  const pct = Math.min(1, feitos / meta)
  const bateu = feitos >= meta
  return (
    <section className="rounded-[22px] border border-line bg-surface px-6 py-5">
      <p className="section-label">Meta do dia</p>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-ink"><span className="text-[28px] font-bold tabular-nums">{fmtNum(feitos)}</span> de {fmtNum(meta)} contatos hoje</p>
        <span className={`text-sm font-semibold ${bateu ? 'text-[var(--success)]' : 'text-ink-2'}`}>{bateu ? 'Meta batida' : `faltam ${fmtNum(meta - feitos)}`}</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--sunken)]">
        <div className={`h-full rounded-full transition-[width] duration-500 ${bateu ? 'bg-[var(--success)]' : 'bg-[var(--royal)]'}`} style={{ width: `${pct * 100}%` }} />
      </div>
    </section>
  )
}

function Avisos({ d }) {
  const lista = []
  if (d && d.agenda_ativa === false) lista.push('Acordos ainda não aparecem: falta rodar sql/migracao_operador.sql no Supabase.')
  if (d && d.divisao_ativa === false) lista.push('“Recebido” por operador depende da divisão da fila: falta rodar sql/migracao_operador.sql no Supabase.')
  if (!lista.length) return null
  return lista.map(t => (
    <p key={t} className="flex items-start gap-2 rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-3 text-xs text-ink-2">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" /> {t}
    </p>
  ))
}

function Promessas({ d, link }) {
  return (
    <p className="text-[13px] text-ink-2">
      Promessas {NO_PERIODO[d.periodo] || 'no período'}: <b className="text-ink">{plural(d.promessas_cumpridas, 'paga', 'pagas')}</b>
      {' · '}{plural(d.promessas_quebradas, 'não paga', 'não pagas')}{' · '}{plural(d.promessas_pendentes, 'pendente', 'pendentes')}
      {link && d.promessas_pendentes > 0 && <> · <Link to="/agenda" className="font-semibold text-accent-text hover:underline">ver na Agenda</Link></>}
    </p>
  )
}

function MeusNumeros({ d, periodo }) {
  return (
    <>
      {d.meta_dia ? <BarraMeta feitos={d.contatos_hoje} meta={d.meta_dia} /> : null}
      <Numeros itens={[
        { rotulo: 'Contatos feitos', valor: fmtNum(d.contatos), nota: d.contatos ? `${fmtNum(d.contatos_efetivos)} efetivos (${fmtPct(d.taxa_contato_efetivo)})` : `nenhum contato ${NO_PERIODO[periodo]}` },
        { rotulo: 'Acordos fechados', valor: fmtNum(d.acordos), nota: d.acordos ? `${fmtBRL(d.acordos_valor)} prometidos` : 'promessas registradas' },
        { rotulo: 'Recebido', valor: fmtBRL(d.recebido), cor: d.recebido ? 'text-[var(--success)]' : undefined, nota: `${plural(d.pagamentos, 'pagamento confirmado', 'pagamentos confirmados')} da sua fila` },
      ]} />
      <Promessas d={{ ...d, periodo }} link />
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
      <button type="button" onClick={onVoltar} className="btn-secondary btn-sm">
        <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Voltar para a equipe
      </button>
      <ErroCarga erro={erro} onTentar={() => setTent(t => t + 1)} />
      {!d && !erro && <div className="flex items-center gap-2 py-6 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Carregando…</div>}
      {d && (
        <>
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[var(--royal-soft)] text-xs font-bold text-accent-text" aria-hidden="true">{iniciais(d.operador.nome)}</span>
            <h2 className="text-[19px] font-semibold text-ink">{d.operador.nome}</h2>
          </div>
          <Numeros itens={[
            { rotulo: 'Contatos', valor: fmtNum(d.contatos), nota: d.contatos ? `${fmtNum(d.devedores_trabalhados)} devedores · ${fmtPct(d.taxa_contato_efetivo)} efetivos` : `nenhum contato ${NO_PERIODO[periodo]}` },
            { rotulo: 'Acordos fechados', valor: fmtNum(d.acordos), nota: umACada(d.contatos, d.acordos) ? `1 a cada ${umACada(d.contatos, d.acordos)} contatos · ${fmtBRL(d.acordos_valor)}` : 'promessas registradas' },
            { rotulo: 'Recebido', valor: fmtBRL(d.recebido), cor: d.recebido ? 'text-[var(--success)]' : undefined, nota: plural(d.pagamentos, 'pagamento confirmado', 'pagamentos confirmados') },
          ]} />
          <Promessas d={{ ...d, periodo }} />
          <div className="grid gap-4 sm:grid-cols-2">
            <section className="rounded-[22px] border border-line bg-surface px-6 py-5">
              <p className="section-label">Ofertas feitas</p>
              {o.ativo ? <>
                <p className="mt-1 text-[28px] font-bold leading-none tabular-nums text-ink">{fmtNum(o.feitas)}</p>
                <p className="mt-1.5 text-xs text-ink-2">{fmtNum(o.aceitas)} aceitas · {fmtNum(o.vai_pensar)} a pensar · {fmtNum(o.recusadas)} recusadas</p>
              </> : <p className="mt-1 text-sm text-ink-2">Aparece depois de ativar o histórico de ofertas.</p>}
            </section>
            <section className="rounded-[22px] border border-line bg-surface px-6 py-5">
              <p className="section-label">Retornos marcados</p>
              {r.ativo ? <>
                <p className="mt-1 text-[28px] font-bold leading-none tabular-nums text-ink">{fmtNum(r.marcados)}</p>
                <p className="mt-1.5 text-xs text-ink-2">{fmtNum(r.feitos)} feitos · {fmtNum(r.pendentes)} pendentes</p>
              </> : <p className="mt-1 text-sm text-ink-2">Aparece com a Agenda ativa.</p>}
            </section>
          </div>
        </>
      )}
    </section>
  )
}

// A frase do topo da tabela: quem converte melhor, a média e quem pede atenção.
export function fraseDaEquipe(operadores, total) {
  const comAcordo = operadores.filter(o => umACada(o.contatos, o.acordos))
  if (!total.contatos) return { titulo: 'Nenhum contato registrado no período.', apoio: 'Os números aparecem aqui assim que a equipe registra os contatos.' }
  if (!comAcordo.length) return { titulo: `${plural(total.contatos, 'contato', 'contatos')} e nenhum acordo ainda.`, apoio: 'O acordo conta quando a promessa é registrada na pasta do devedor ou na Agenda.' }
  const melhor = [...comAcordo].sort((a, b) => umACada(a.contatos, a.acordos) - umACada(b.contatos, b.acordos))[0]
  const nMelhor = umACada(melhor.contatos, melhor.acordos)
  const media = umACada(total.contatos, total.acordos)
  const primeiro = String(melhor.nome || '').split(' ')[0] || 'Quem converte melhor'
  const titulo = operadores.length > 1
    ? `${primeiro} fecha 1 acordo a cada ${nMelhor} contatos. A média da equipe é 1 a cada ${media}.`
    : `${primeiro} fecha 1 acordo a cada ${nMelhor} contatos.`
  // Quem está bem abaixo da média (30% pior) ou contatou bastante sem fechar nada.
  const pior = operadores
    .filter(o => o !== melhor && o.contatos >= 5)
    .map(o => ({ o, n: umACada(o.contatos, o.acordos) }))
    .filter(({ n }) => n == null || n > media * 1.3)
    .sort((a, b) => (b.n ?? Infinity) - (a.n ?? Infinity))[0]
  const nomePior = pior && (String(pior.o.nome || '').split(' ')[0] || 'Um operador')
  const apoio = !pior ? null
    : pior.n == null ? `${nomePior} fez ${plural(pior.o.contatos, 'contato', 'contatos')} sem acordo: vale ouvir as ligações junto com ${primeiro}.`
      : `${nomePior} está em 1 a cada ${pior.n}: vale ouvir as ligações junto com ${primeiro}.`
  return { titulo, apoio }
}

function Equipe({ d, onAbrir, periodo }) {
  const navigate = useNavigate()
  const t = d.total
  const ops = d.operadores
  const maxContatos = Math.max(1, ...ops.map(o => o.contatos || 0))
  const { titulo, apoio } = fraseDaEquipe(ops, t)
  return (
    <>
      <Numeros itens={[
        { rotulo: 'Contatos da equipe', valor: fmtNum(t.contatos), nota: t.contatos ? `${NO_PERIODO[periodo]} · ${fmtPct(t.taxa_contato_efetivo)} efetivos` : `nenhum contato ${NO_PERIODO[periodo]}` },
        { rotulo: 'Acordos fechados', valor: fmtNum(t.acordos), nota: t.acordos ? `${fmtBRL(t.acordos_valor)} prometidos` : 'promessas registradas' },
        { rotulo: 'Recebido', valor: fmtBRL(t.recebido), cor: t.recebido ? 'text-[var(--success)]' : undefined,
          nota: d.recebido_sem_responsavel > 0 ? `${fmtBRL(d.recebido_sem_responsavel)} de devedores sem responsável` : plural(t.pagamentos, 'pagamento confirmado', 'pagamentos confirmados') },
      ]} />
      {d.meta_dia ? null : <p className="text-xs text-ink-3">Para acompanhar a meta diária, informe “Meta de contatos por operador por dia” em Política de cobrança.</p>}

      <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="eq-por-op">
        <p id="eq-por-op" className="section-label">Por operador</p>
        {ops.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <p className="text-[15px] font-semibold text-ink">Nenhum operador nesta empresa ainda</p>
            <p className="text-sm text-ink-2">Convide quem faz a cobrança para ver o trabalho de cada um aqui.</p>
            <button type="button" className="btn-primary mt-2" onClick={() => navigate('/admin/usuarios')}>Convidar operador</button>
          </div>
        ) : (
          <>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug text-ink">{titulo}</h2>
            {apoio && <p className="mt-0.5 text-[13px] text-ink-2">{apoio}</p>}
            {/* Celular: uma linha por operador, sem tabela rolando de lado. */}
            <ul className="mt-3 divide-y divide-line sm:hidden">
              {ops.map(o => {
                const n = umACada(o.contatos, o.acordos)
                const pagas = taxaPagas(o)
                return (
                  <li key={o.operador_id}>
                    <button type="button" onClick={() => onAbrir(o.operador_id)} className="flex w-full items-center gap-3 py-3 text-left">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[var(--royal-soft)] text-[11px] font-bold text-accent-text" aria-hidden="true">{iniciais(o.nome)}</span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline justify-between gap-2">
                          <b className="truncate text-ink">{o.nome}</b>
                          <b className="shrink-0 tabular-nums text-ink">{fmtBRL(o.recebido)}</b>
                        </span>
                        <span className="mt-0.5 block text-xs text-ink-2">
                          {plural(o.contatos, 'contato', 'contatos')} · {plural(o.acordos, 'acordo', 'acordos')}{n ? ` (1 a cada ${n})` : ''} · {pagas == null ? 'nenhuma promessa venceu' : `${fmtPct(pagas)} das promessas pagas`}
                        </span>
                        <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-[var(--sunken)]" aria-hidden="true">
                          <span className="block h-full rounded-full bg-[var(--chart-1)]" style={{ width: `${(o.contatos / maxContatos) * 100}%` }} />
                        </span>
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
                    </button>
                  </li>
                )
              })}
            </ul>
            <div className="mt-4 hidden overflow-x-auto sm:block">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-ink-3">
                    <th className="pb-2.5 font-medium">Operador</th>
                    <th className="pb-2.5 font-medium">Contatos</th>
                    <th className="pb-2.5 font-medium">Acordos</th>
                    <th className="pb-2.5 font-medium">Recebido</th>
                    <th className="pb-2.5 font-medium">Promessas pagas</th>
                    {d.meta_dia ? <th className="pb-2.5 font-medium">Meta hoje</th> : null}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {ops.map(o => {
                    const n = umACada(o.contatos, o.acordos)
                    const pagas = taxaPagas(o)
                    const corPagas = pagas == null ? 'var(--ink-3)' : pagas >= 0.7 ? 'var(--success)' : pagas >= 0.4 ? 'var(--warning)' : 'var(--danger)'
                    return (
                      <tr key={o.operador_id}>
                        <td className="py-3 pr-4">
                          <button type="button" onClick={() => onAbrir(o.operador_id)} className="group flex min-h-[44px] items-center gap-2.5 text-left" title="Ver o desempenho individual">
                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[var(--royal-soft)] text-[11px] font-bold text-accent-text" aria-hidden="true">{iniciais(o.nome)}</span>
                            <span className="font-semibold text-ink group-hover:text-accent-text">{o.nome}</span>
                            <ChevronRight className="h-3.5 w-3.5 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
                          </button>
                        </td>
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-3">
                            <span className="h-1.5 w-32 overflow-hidden rounded-full bg-[var(--sunken)]" aria-hidden="true">
                              <span className="block h-full rounded-full bg-[var(--chart-1)]" style={{ width: `${(o.contatos / maxContatos) * 100}%` }} />
                            </span>
                            <b className="tabular-nums text-ink">{fmtNum(o.contatos)}</b>
                          </div>
                        </td>
                        <td className="whitespace-nowrap py-3 pr-4 tabular-nums">
                          <b className="text-ink">{fmtNum(o.acordos)}</b>
                          {n && <span className="text-xs text-ink-3"> · 1 a cada {n}</span>}
                        </td>
                        <td className="whitespace-nowrap py-3 pr-4 font-semibold tabular-nums text-ink">{fmtBRL(o.recebido)}</td>
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2.5">
                            <span className="h-1.5 w-11 overflow-hidden rounded-full bg-[var(--sunken)]" aria-hidden="true">
                              <span className="block h-full rounded-full" style={{ width: `${(pagas || 0) * 100}%`, background: corPagas }} />
                            </span>
                            <b className="tabular-nums" style={{ color: corPagas }}>{fmtPct(pagas)}</b>
                            {pagas == null && <span className="text-xs text-ink-3">nenhuma venceu</span>}
                          </div>
                        </td>
                        {d.meta_dia ? <td className="whitespace-nowrap py-3 text-xs tabular-nums text-ink-2">{fmtNum(o.contatos_hoje)} de {fmtNum(d.meta_dia)}</td> : null}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-ink-3">Promessas pagas contam só as que já venceram. Toque num nome para ver o desempenho individual.</p>
          </>
        )}
      </section>
    </>
  )
}

export default function PainelOperador() {
  const { token, isOperador, isComando } = useAuth()
  const equipe = !isOperador
  // Período e operador aberto moram na URL: o voltar do navegador sai do
  // individual para a equipe, e o link abre direto no mesmo lugar.
  const [params, setParams] = useSearchParams()
  const periodo = PERIODOS.some(([k]) => k === params.get('periodo')) ? params.get('periodo') : 'hoje'
  const opSel = equipe ? params.get('op') : null
  const irPara = useCallback((mudancas, { substituir = false } = {}) => {
    setParams(atual => {
      const novo = new URLSearchParams(atual)
      for (const [k, v] of Object.entries(mudancas)) v == null ? novo.delete(k) : novo.set(k, v)
      return novo
    }, { replace: substituir })
  }, [setParams])
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [tentativa, setTentativa] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')

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
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <CabecalhoPagina rotulo={equipe ? 'Resultados' : 'Meu trabalho'} icone={equipe ? Users : Gauge}
          titulo={equipe ? 'Painel da equipe' : 'Meu painel'} ajuda="painel-do-operador" className="!mb-2"
          subtitulo={equipe ? 'Contatos, acordos e quanto entrou, por operador.' : 'Seus contatos, acordos e quanto entrou da sua fila.'}>
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
              className="input-base h-[44px] w-auto rounded-[12px] text-sm">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
          <div className="flex rounded-[14px] border border-line bg-surface p-1" role="tablist" aria-label="Período">
            {PERIODOS.map(([k, l]) => (
              <button key={k} type="button" role="tab" aria-selected={periodo === k} onClick={() => irPara({ periodo: k === 'hoje' ? null : k }, { substituir: true })}
                className={`h-9 rounded-[10px] px-3.5 text-sm transition-colors ${periodo === k ? 'bg-[var(--raised)] font-semibold text-ink' : 'text-ink-2 hover:text-ink'}`}>
                {l}
              </button>
            ))}
          </div>
        </CabecalhoPagina>

        {isComando && !alvo && (
          <div className="rounded-[22px] border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver o painel da equipe.</div>
        )}
        <ErroCarga erro={erro} ocupado={carregando} onTentar={() => setTentativa(t => t + 1)} />
        {carregando && !dados && (
          <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Carregando…</div>
        )}
        {dados && (
          <div className={`space-y-4 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
            <Avisos d={dados} />
            {equipe ? (opSel
              ? <Individual id={opSel} periodo={periodo} empresa={isComando ? alvo : undefined} onVoltar={() => irPara({ op: null })} />
              : <Equipe d={dados} periodo={periodo} onAbrir={(id) => irPara({ op: id })} />) : <MeusNumeros d={dados} periodo={periodo} />}
          </div>
        )}
      </div>
    </AppShell>
  )
}
