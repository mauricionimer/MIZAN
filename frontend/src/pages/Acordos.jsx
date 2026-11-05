// A4 — Acordos em andamento: parcelas a vencer e acordos quebrados
// ("pagou a 1ª e parou"). Regras em backend/acordos.py.
import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Handshake, Loader2, ChevronDown, CalendarClock, AlertTriangle, XOctagon, Wallet, Check, Undo2, Info } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'

// Dentro de Pagamentos (aba) não repete o menu e o cabeçalho da página.
const Casca = ({ embutido, children }) => embutido ? <>{children}</> : <AppShell>{children}</AppShell>
import ErroCarga from '../components/ErroCarga'
import AvisoDesfazer from '../components/AvisoDesfazer'
import { useAuth } from '../context/AuthContext'
import { listarAcordos, mudarParcela, listarEmpresas } from '../api'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)
const fmtBRL2 = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)
const plural = (n, um, varios) => `${fmtNum(n)} ${n === 1 ? um : varios}`
const fmtData = (iso) => iso ? new Intl.DateTimeFormat('pt-BR').format(new Date(String(iso).slice(0, 10) + 'T12:00:00')) : '—'

const SIT = {
  quebrado: { label: 'Quebrado', icone: XOctagon,      cor: 'var(--danger)',  fundo: 'rgb(var(--c-danger) / 0.10)',  borda: 'rgb(var(--c-danger) / 0.25)' },
  atrasado: { label: 'Atrasado', icone: AlertTriangle, cor: 'var(--warning)', fundo: 'rgb(var(--c-warning) / 0.10)', borda: 'rgb(var(--c-warning) / 0.25)' },
  em_dia:   { label: 'Em dia',   icone: CalendarClock, cor: 'var(--success)', fundo: 'rgb(var(--c-success) / 0.10)', borda: 'rgb(var(--c-success) / 0.25)' },
  quitado:  { label: 'Quitado',  icone: Check,         cor: 'var(--ink-2)',   fundo: 'var(--raise-2)',                borda: 'var(--line)' },
}
const FILTROS = [['', 'Todos'], ['quebrado', 'Quebrados'], ['atrasado', 'Atrasados'], ['em_dia', 'Em dia'], ['quitado', 'Quitados']]

function Selo({ s }) {
  const c = SIT[s]; const I = c.icone
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{ background: c.fundo, color: c.cor, border: `1px solid ${c.borda}` }}>
      <I className="h-3 w-3" /> {c.label}
    </span>
  )
}

function Numero({ icone: Icone, rotulo, valor, nota, cor, i, ativo, onClick }) {
  return (
    <motion.button type="button" onClick={onClick} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
      className={`rounded-[22px] border bg-surface px-5 py-[18px] text-left transition-colors ${ativo ? 'border-[color-mix(in_srgb,var(--royal)_55%,transparent)] ring-1 ring-[color-mix(in_srgb,var(--royal)_30%,transparent)]' : 'border-line hover:border-[var(--border-strong)]'}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="section-label">{rotulo}</p>
        <Icone className="h-4 w-4 text-ink-3" aria-hidden="true" />
      </div>
      <p className="mt-2 text-[28px] font-bold leading-none tabular-nums tracking-tight" style={{ color: cor === 'var(--ink-2)' || cor === 'var(--success)' ? 'var(--text)' : cor }}>{valor}</p>
      <p className="mt-2 text-xs text-ink-2">{nota}</p>
    </motion.button>
  )
}

// Régua de parcelas: paga (cheia), vencida (vermelha), futura (vazia), com o
// "3/6" ao lado: o número vale mesmo sem passar o mouse nos quadrados.
function Regua({ parcelas, hoje, pagas, total }) {
  return (
    <div className="flex items-center gap-2.5">
    <div className="flex flex-wrap gap-1" role="img" aria-label={`${pagas} de ${total} parcelas pagas`}>
      {parcelas.map(p => {
        const vencida = p.situacao !== 'paga' && String(p.vencimento).slice(0, 10) < hoje
        const estilo = p.situacao === 'paga' ? { background: 'var(--success)' }
          : vencida ? { background: 'var(--danger)' } : { background: 'transparent', border: '1px solid var(--line-2, var(--line))' }
        return <span key={p.id} title={`${p.numero}ª · ${fmtData(p.vencimento)} · ${p.situacao === 'paga' ? 'paga' : vencida ? 'vencida' : 'a vencer'}`}
          className="h-4 w-5 rounded-sm" style={estilo} />
      })}
    </div>
    <span className="shrink-0 text-sm font-semibold tabular-nums text-ink">{pagas}/{total}<span className="font-normal text-ink-2"> pagas</span></span>
    </div>
  )
}

function Acordo({ a, hoje, podeBaixar, onParcela, destaque }) {
  const [aberto, setAberto] = useState(false)
  const [ocupado, setOcupado] = useState(null)
  async function agir(p, acao) {
    setOcupado(p.id)
    try { await onParcela(a, p, acao) } finally { setOcupado(null) }
  }
  return (
    <li>
      <button onClick={() => setAberto(o => !o)} aria-expanded={aberto}
        className={`grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-6 py-4 text-left transition-colors hover:bg-raise-1 sm:grid-cols-[minmax(0,1.3fr)_auto_minmax(0,1.2fr)_auto_auto] ${aberto ? 'bg-raise-1' : ''}`}>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{a.nome || a.cpf}</p>
          <p className="truncate text-xs text-ink-2">{a.cpf}{a.responsavel_nome ? ` · ${a.responsavel_nome}` : ''}</p>
        </div>
        <Selo s={a.situacao} />
        <div className="col-span-2 space-y-1 sm:col-span-1">
          <Regua parcelas={a.parcelas} hoje={hoje} pagas={a.pagas} total={a.total} />
          <p className="text-xs text-ink-2">
            {fmtBRL2(a.valor_parcela)}/mês
            {a.dias_atraso > 0 && <span style={{ color: SIT[a.situacao].cor }}> · {a.dias_atraso} dias de atraso</span>}
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-sm font-semibold tabular-nums text-ink">{fmtBRL(a.valor_aberto)}</p>
          <p className="text-xs text-ink-2">{a.situacao === 'quitado' ? 'quitado' : `em aberto · próx. ${fmtData(a.proximo_vencimento)}`}</p>
        </div>
        <ChevronDown className={`h-4 w-4 justify-self-end text-ink-2 transition-transform ${aberto ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence initial={false}>
        {aberto && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden">
            <ul className="mx-6 mb-4 divide-y divide-line rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-1">
              {a.parcelas.map(p => {
                const vencida = p.situacao !== 'paga' && String(p.vencimento).slice(0, 10) < hoje
                const cor = p.situacao === 'paga' ? 'var(--success)' : vencida ? 'var(--danger)' : 'var(--ink-2)'
                return (
                  <li key={p.id} className="-mx-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg px-2 py-2.5 transition-colors duration-700"
                    style={destaque === p.id ? { background: 'rgb(var(--c-success) / 0.12)' } : undefined}>
                    <span className="w-8 text-sm font-semibold tabular-nums text-ink">{p.numero}ª</span>
                    <span className="w-24 text-sm tabular-nums text-ink-2">{fmtData(p.vencimento)}</span>
                    <span className="w-24 text-sm tabular-nums text-ink">{fmtBRL2(p.valor)}</span>
                    <span className="text-xs" style={{ color: cor }}>
                      {p.situacao === 'paga'
                        ? (p.pago_em && String(p.pago_em).slice(0, 10) === hoje ? 'Paga hoje' : `Paga${p.pago_em ? ` em ${fmtData(p.pago_em)}` : ''}`)
                        : vencida ? 'Vencida' : 'A vencer'}
                    </span>
                    <span className="ml-auto">
                      {podeBaixar && p.situacao !== 'paga' && (
                        <button disabled={ocupado === p.id} onClick={() => agir(p, 'pagar')}
                          className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1 rounded-[10px] border border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)] px-3 py-1 text-xs font-semibold text-[var(--success)] hover:brightness-110 disabled:opacity-40">
                          {ocupado === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Marcar paga
                        </button>
                      )}
                      {podeBaixar && p.situacao === 'paga' && p.numero > 1 && (
                        <button disabled={ocupado === p.id} onClick={() => agir(p, 'desfazer')}
                          className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1 rounded-[10px] px-2 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-40">
                          <Undo2 className="h-3 w-3" /> Desfazer
                        </button>
                      )}
                    </span>
                  </li>
                )
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}

export default function Acordos({ embutido = false }) {
  const { token, isAdmin, isComando, isOperador } = useAuth()
  const [dados, setDados] = useState(null)
  const [filtro, setFiltro] = useState('')
  const [erro, setErro] = useState(null)
  const [aviso, setAviso] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  function carregar(silencioso = false) {
    if (isComando && !alvo) { setDados(null); setCarregando(false); return }
    if (!silencioso) setCarregando(true)
    setErro(null)
    return listarAcordos(isComando ? alvo : undefined)
      .then(setDados).catch(e => setErro(e)).finally(() => setCarregando(false))
  }
  useEffect(() => { carregar() }, [isComando, alvo])     // eslint-disable-line react-hooks/exhaustive-deps

  const [destaque, setDestaque] = useState(null)       // parcela que acabou de mudar
  const [desfazer, setDesfazer] = useState(null)
  // Atualiza a parcela na própria linha (o aviso no topo ficava fora da vista
  // de quem trabalha num acordo mais abaixo) e refaz o resumo sem piscar a tela.
  function marcar(acordoId, parcelaId, campos) {
    setDados(d => d && ({ ...d, acordos: d.acordos.map(x => x.id !== acordoId ? x : {
      ...x, parcelas: x.parcelas.map(q => q.id === parcelaId ? { ...q, ...campos } : q) }) }))
    setDestaque(parcelaId); setTimeout(() => setDestaque(d => d === parcelaId ? null : d), 2500)
  }
  async function onParcela(a, p, acao) {
    setAviso(''); setErro(null)
    try {
      await mudarParcela(p.id, acao)
      marcar(a.id, p.id, acao === 'pagar' ? { situacao: 'paga', pago_em: new Date().toISOString() } : { situacao: 'pendente', pago_em: null })
      carregar(true)
      if (acao === 'pagar') {
        setDesfazer({
          id: `${p.id}-${Date.now()}`, texto: `${(a.nome || a.cpf).split(' ')[0]}: ${p.numero}ª parcela marcada como paga.`, desfeito: 'Desfeito. A parcela voltou para em aberto.',
          desfazer: async () => {
            await mudarParcela(p.id, 'desfazer')
            marcar(a.id, p.id, { situacao: 'pendente', pago_em: null })
            carregar(true)
          },
        })
      }
    } catch (e) { setErro(e) }
  }

  const lista = useMemo(() => (dados?.acordos ?? []).filter(a => !filtro || a.situacao === filtro), [dados, filtro])
  const r = dados?.resumo

  return (
    <Casca embutido={embutido}>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <CabecalhoPagina rotulo="Resultados" icone={Handshake} titulo="Acordos" ajuda="acordos-em-andamento" className="!mb-0"
          subtitulo={isOperador ? 'Acordos parcelados dos devedores da sua fila: o que vence nos próximos dias e quem parou de pagar. A baixa de parcela é do administrador.'
                : 'Acordos parcelados: o que vence nos próximos dias e quem parou de pagar.'}>
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
              className="h-11 rounded-[12px] border border-line bg-surface px-3 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </CabecalhoPagina>

        {isComando && !alvo && <div className="rounded-[22px] border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver os acordos.</div>}
        {aviso && <p className="flex items-center gap-1.5 text-sm text-emerald-400"><Check className="h-4 w-4" /> {aviso}</p>}
        <ErroCarga erro={erro} ocupado={carregando} onTentar={carregar} />
        {carregando && !dados && <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
        {dados && dados.ativo === false && (
          <p className="flex items-start gap-2 rounded-[14px] border border-line bg-surface px-4 py-3 text-sm text-ink-2"><Info className="mt-0.5 h-4 w-4 shrink-0" /> {dados.mensagem}</p>
        )}

        {dados?.ativo && (
          <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              <Numero i={0} icone={Wallet} cor="var(--ink-2)" rotulo="Em aberto" valor={fmtBRL(r.valor_aberto)}
                nota={plural(r.acordos - r.quitado, 'acordo ativo', 'acordos ativos')} ativo={filtro === ''} onClick={() => setFiltro('')} />
              <Numero i={1} icone={CalendarClock} cor="var(--success)" rotulo="A vencer em 7 dias" valor={fmtBRL(r.a_vencer_7d_valor)}
                nota={plural(r.a_vencer_7d, 'parcela', 'parcelas')} ativo={filtro === 'em_dia'} onClick={() => setFiltro('em_dia')} />
              <Numero i={2} icone={AlertTriangle} cor="var(--warning)" rotulo="Atrasados" valor={fmtBRL(r.atrasado_valor)}
                nota={`${plural(r.atrasado, 'acordo', 'acordos')} · até ${dados.dias_quebra} dias`} ativo={filtro === 'atrasado'} onClick={() => setFiltro('atrasado')} />
              <Numero i={3} icone={XOctagon} cor="var(--danger)" rotulo="Quebrados" valor={fmtBRL(r.quebrado_valor)}
                nota={`${plural(r.quebrado, 'acordo', 'acordos')} · mais de ${dados.dias_quebra} dias`} ativo={filtro === 'quebrado'} onClick={() => setFiltro('quebrado')} />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {FILTROS.map(([k, l]) => {
                const n = k ? r[k] : r.acordos
                return (
                  <button key={k || 'todos'} onClick={() => setFiltro(k)}
                    className={`h-9 rounded-full border px-3.5 text-[13px] transition-colors ${filtro === k ? 'border-[color-mix(in_srgb,var(--royal)_50%,transparent)] bg-[var(--royal-soft)] font-semibold text-ink' : 'border-line text-ink-2 hover:text-ink'}`}>
                    {l} · {fmtNum(n)}
                  </button>
                )
              })}
              <span className="ml-auto flex items-center gap-3 text-xs text-ink-2">
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: 'var(--success)' }} /> paga</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: 'var(--danger)' }} /> vencida</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full border border-[var(--border-strong)]" /> a vencer</span>
              </span>
            </div>

            {r.acordos === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-[22px] border border-line bg-surface px-6 py-12 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-[var(--raised)] text-accent-text"><Handshake className="h-5 w-5" aria-hidden="true" /></span>
                <b className="text-[17px] text-ink">Nenhum acordo parcelado ainda</b>
                <p className="max-w-md text-sm leading-relaxed text-ink-2">{isOperador
                  ? 'Quando um devedor da sua fila fechar um acordo parcelado, ele aparece aqui com todas as parcelas.'
                  : 'Ao registrar em Pagamentos um pagamento “Parcelado”, o acordo aparece aqui com todas as parcelas.'}</p>
              </div>
            ) : lista.length === 0 ? (
              <p className="rounded-[22px] border border-dashed border-line px-4 py-8 text-center text-sm text-ink-2">Nenhum acordo nesta situação.</p>
            ) : (
              <ul className="divide-y divide-line overflow-hidden rounded-[22px] border border-line bg-surface">
                {lista.map(a => <Acordo key={a.id} a={a} hoje={dados.hoje} podeBaixar={isAdmin} onParcela={onParcela} destaque={destaque} />)}
              </ul>
            )}
          </div>
        )}
      </div>
      <AvisoDesfazer aviso={desfazer} onFechar={() => setDesfazer(null)} />
    </Casca>
  )
}
