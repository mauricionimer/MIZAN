// F2 — Agenda: retornos e promessas, separados em Alto · Médio · Safe.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { CalendarClock, Check, X, CalendarDays, ExternalLink, Loader2, Banknote, PhoneCall, RotateCcw } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import ErroCarga from '../components/ErroCarga'
import AvisoDesfazer from '../components/AvisoDesfazer'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { listarAgenda, mudarAgenda, buscarPaginaRanking, listarEmpresas, carregarCarteira } from '../api'
import { NIVEIS, NIVEL_CFG, TIPO_LABEL, quando, hojeISO, somarDias, avisarAgendaMudou } from '../utils/agenda'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)

function Remarcar({ item, onSalvar, onCancelar }) {
  const [data, setData] = useState(somarDias(hojeISO(), 1))
  const [hora, setHora] = useState(item.hora || '')
  return (
    <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-line bg-surface-2 p-2.5">
      <label className="text-xs text-ink-2">Nova data
        <input type="date" value={data} min={hojeISO()} onChange={e => setData(e.target.value)}
          className="mt-1 block rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink [color-scheme:dark]" />
      </label>
      <label className="text-xs text-ink-2">Hora
        <input type="time" value={hora} onChange={e => setHora(e.target.value)}
          className="mt-1 block rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink [color-scheme:dark]" />
      </label>
      <button onClick={() => onSalvar(data, hora || null)} disabled={!data} className="btn-primary btn-sm">Salvar</button>
      <button onClick={onCancelar} className="btn-ghost btn-sm">Cancelar</button>
    </div>
  )
}

function Item({ item, mostrarOperador, onAcao, onAbrir, carteiraAberta, soLeitura }) {
  const [abrindo, setAbrindo] = useState(false)
  const outraCarteira = !!item.carteira_id && item.carteira_id !== carteiraAberta
  async function abrir() {
    if (abrindo) return
    setAbrindo(true)
    try { await onAbrir(item) } finally { setAbrindo(false) }
  }
  const [remarcando, setRemarcando] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const cfg = NIVEL_CFG[item.nivel] ?? NIVEL_CFG.safe
  const promessa = item.tipo === 'promessa'

  async function agir(acao, extra) {
    setOcupado(true)
    try { await onAcao(item, acao, extra); setRemarcando(false) } finally { setOcupado(false) }
  }

  return (
    <motion.li layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
      className="rounded-xl border bg-surface p-4" style={{ borderColor: 'var(--line)', borderLeft: `3px solid ${cfg.cor}` }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{item.nome || item.cpf}</p>
          <p className="text-xs tabular-nums text-ink-2">{item.cpf}{mostrarOperador && item.operador_nome ? ` · ${item.operador_nome}` : ''}</p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
          style={{ background: cfg.fundo, color: cfg.cor, border: `1px solid ${cfg.borda}` }}>
          {promessa ? <Banknote className="h-3 w-3" /> : <PhoneCall className="h-3 w-3" />}
          {TIPO_LABEL[item.tipo]}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm font-medium" style={{ color: cfg.cor }}>{quando(item.data, item.hora)}</span>
        {promessa && item.valor > 0 && <span className="text-sm font-semibold tabular-nums text-ink">{fmtBRL(item.valor)}</span>}
      </div>
      {item.observacao && <p className="mt-1.5 text-xs leading-relaxed text-ink-2">{item.observacao}</p>}

      {soLeitura ? null : remarcando
        ? <Remarcar item={item} onCancelar={() => setRemarcando(false)} onSalvar={(data, hora) => agir('remarcar', { data, hora })} />
        : (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button disabled={ocupado} onClick={() => agir('cumprir')} title={promessa ? "Marca a promessa como cumprida. O pagamento só entra nos resultados quando for registrado em Pagamentos." : undefined}
              className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-40">
              <Check className="h-3 w-3" /> {promessa ? 'Cumpriu' : 'Feito'}
            </button>
            {promessa && (
              <button disabled={ocupado} onClick={() => agir('quebrar')}
                className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-400 hover:bg-red-500/20 disabled:opacity-40">
                <X className="h-3 w-3" /> Não pagou
              </button>
            )}
            <button disabled={ocupado} onClick={() => setRemarcando(true)}
              className="min-h-[40px] md:min-h-[32px] inline-flex items-center gap-1 rounded-md border border-line bg-raise-1 px-2.5 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-40">
              <CalendarDays className="h-3 w-3" /> Remarcar
            </button>
            {!promessa && (
              <button disabled={ocupado} onClick={() => agir('cancelar')}
                className="min-h-[40px] md:min-h-[32px] rounded-md px-2 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-40">Cancelar</button>
            )}
            {item.carteira_id ? (
              // De outra carteira: abre a carteira dele e entra na ficha (sem hover para explicar).
              <button onClick={abrir} disabled={abrindo}
                className="min-h-[40px] md:min-h-[32px] ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-blue-400 hover:text-blue-300 disabled:opacity-60">
                {abrindo ? <><Loader2 className="h-3 w-3 animate-spin" /> {outraCarteira ? 'Abrindo carteira…' : 'Abrindo…'}</>
                  : <>Abrir devedor <ExternalLink className="h-3 w-3" /></>}
              </button>
            ) : (
              <span className="ml-auto self-center text-xs text-ink-2">Sem carteira ligada</span>
            )}
          </div>
        )}
    </motion.li>
  )
}

export default function Agenda() {
  const { token, isAdmin, isComando } = useAuth()
  // COMANDO consulta a agenda de uma empresa, sem alterar (quem resolve é a operação).
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])
  const navigate = useNavigate()
  const { result, setResult } = useAnalysis()
  const carteiraAberta = result?.resumo?.carteira_id ?? result?.carteira_id ?? null
  const [escopo, setEscopo] = useState(isAdmin || isComando ? 'equipe' : 'minha')
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)          // falha ao carregar a lista
  const [erroAcao, setErroAcao] = useState(null)  // falha numa ação (resolver, remarcar, abrir)
  const [aviso, setAviso] = useState('')
  const [desfazer, setDesfazer] = useState(null)  // aviso com "Desfazer" no rodapé
  const [aba, setAba] = useState('alto')          // no celular, uma coluna por vez

  const carregar = useCallback(() => {
    if (isComando && !alvo) { setDados(null); setCarregando(false); return }
    setCarregando(true); setErro(null); setErroAcao(null)
    return listarAgenda({ escopo, empresa_id: isComando ? alvo : undefined })
      .then(setDados)
      .catch(e => setErro(e))
      .finally(() => setCarregando(false))
  }, [escopo, isComando, alvo])
  useEffect(() => { carregar() }, [carregar])

  const grupos = useMemo(() => {
    const g = { alto: [], medio: [], safe: [] }
    for (const i of dados?.itens ?? []) (g[i.nivel] ?? g.safe).push(i)
    return g
  }, [dados])

  const ordenar = (lista) => [...lista].sort((a, b) =>
    String(a.data).localeCompare(String(b.data)) || String(a.hora || '99:99').localeCompare(String(b.hora || '99:99')))

  async function acao(item, acao, extra) {
    setAviso(''); setErroAcao(null)
    try {
      const r = await mudarAgenda(item.id, acao, extra)
      setDados(d => ({
        ...d,
        itens: r.item.situacao === 'pendente'
          ? d.itens.map(i => i.id === item.id ? { ...i, ...r.item } : i)
          : d.itens.filter(i => i.id !== item.id),
      }))
      avisarAgendaMudou()
      const nome = (item.nome || 'devedor').split(' ')[0]
      if (acao === 'remarcar') {
        // Remarcar não some da lista e pode ser refeito: basta a confirmação.
        setAviso(`${nome}: remarcado para ${quando(r.item.data, r.item.hora).toLowerCase()}.`)
        return
      }
      const texto = {
        cumprir: item.tipo === 'promessa' ? `${nome}: promessa cumprida. Registre o pagamento em Pagamentos.` : `${nome}: retorno feito.`,
        quebrar: `${nome}: promessa marcada como não paga.`,
        cancelar: `${nome}: retorno cancelado.`,
      }[acao]
      // Desfazer de verdade: reabre no servidor, só se ninguém mexeu depois.
      setDesfazer({
        id: `${item.id}-${Date.now()}`, texto, desfeito: 'Desfeito. O compromisso voltou para a Agenda.',
        desfazer: async () => {
          const v = await mudarAgenda(item.id, 'reabrir', { situacao_esperada: r.item.situacao })
          setDados(d => ({ ...d, itens: ordenar([...d.itens.filter(i => i.id !== item.id), { ...item, ...v.item }]) }))
          avisarAgendaMudou()
        },
      })
    } catch (e) {
      setErroAcao(e)
    }
  }

  async function abrir(item) {
    setErroAcao(null)
    try {
      // Devedor de outra carteira: abre a carteira dele antes (o servidor só
      // entrega carteiras da empresa de quem pede).
      if (item.carteira_id !== carteiraAberta) {
        const carteira = await carregarCarteira(item.carteira_id)
        setResult(carteira)
      }
      const p = await buscarPaginaRanking(item.carteira_id, { busca: item.cpf, limit: 1 })
      const rank = p.itens?.[0]?.rank
      if (rank) navigate(`/devedor/${rank}`)
      else setErroAcao('Este devedor não está mais nessa carteira (ela pode ter sido analisada de novo).')
    } catch (e) { setErroAcao(e) }
  }

  const total = (dados?.itens ?? []).length

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
              <CalendarClock className="h-5 w-5 text-blue-400" /> Agenda<DicaAjuda id="agenda-de-retorno" />
            </h1>
            <p className="mt-1 text-sm text-ink-2">
              Retornos e promessas de pagamento. Quando o pagamento é registrado em Pagamentos, a promessa vira cumprida sozinha.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isComando && (
              <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
                className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            {isAdmin && (
              <div className="flex rounded-lg border border-line bg-surface-2 p-0.5">
                {[['equipe', 'Equipe'], ['minha', 'Minha']].map(([k, l]) => (
                  <button key={k} onClick={() => setEscopo(k)}
                    className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${escopo === k ? 'bg-surface text-ink shadow-sm' : 'text-ink-2 hover:text-ink'}`}>
                    {l}
                  </button>
                ))}
              </div>
            )}
            <button onClick={carregar} aria-label="Atualizar"
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface-2 text-ink-2 hover:text-ink">
              <RotateCcw className={`h-3.5 w-3.5 ${carregando ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {aviso && <p className="flex items-center gap-1.5 text-sm text-emerald-400"><Check className="h-4 w-4" /> {aviso}</p>}
        <ErroCarga erro={erro} onTentar={carregar} />
        <ErroCarga erro={erroAcao} onTentar={carregar} compacto />

        {isComando && !alvo && (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver a agenda da equipe dela.</div>
        )}

        {dados && dados.ativo === false && (
          <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">{dados.mensagem}</div>
        )}

        {carregando && !dados && (
          <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando a agenda…</div>
        )}

        {dados?.ativo && total === 0 && (
          <div className="rounded-xl border border-line bg-surface px-6 py-12 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-ink-2 opacity-50" />
            <p className="mt-3 text-sm font-medium text-ink">Nada pendente</p>
            <p className="mt-1 text-xs text-ink-2">
              Ao registrar um contato na ficha do devedor, marque a data prometida ou o retorno: ele aparece aqui.
            </p>
          </div>
        )}

        {dados?.ativo && total > 0 && (
          <>
            {/* celular: abas; computador: três colunas */}
            <div className="flex gap-1.5 md:hidden">
              {NIVEIS.map(n => (
                <button key={n} onClick={() => setAba(n)}
                  className="min-h-[44px] flex-1 rounded-lg border px-2 py-2 text-xs font-semibold"
                  style={aba === n
                    ? { background: NIVEL_CFG[n].fundo, color: NIVEL_CFG[n].cor, borderColor: NIVEL_CFG[n].borda }
                    : { borderColor: 'var(--line)', color: 'var(--ink-2)' }}>
                  {NIVEL_CFG[n].label} · {grupos[n].length}
                </button>
              ))}
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {NIVEIS.map(n => (
                <section key={n} className={`${aba === n ? '' : 'hidden'} md:block`}>
                  <div className="mb-2 flex items-center justify-between rounded-lg px-3 py-2"
                    style={{ background: NIVEL_CFG[n].fundo, border: `1px solid ${NIVEL_CFG[n].borda}` }}>
                    <span className="text-xs font-bold uppercase tracking-wider" style={{ color: NIVEL_CFG[n].cor }}>
                      {NIVEL_CFG[n].label} · {grupos[n].length}
                    </span>
                    <span className="text-xs text-ink-2">{NIVEL_CFG[n].dica}</span>
                  </div>
                  <ul className="space-y-2.5">
                    <AnimatePresence initial={false}>
                      {grupos[n].map(i => (
                        <Item key={i.id} item={i} mostrarOperador={escopo === 'equipe'}
                          onAcao={acao} onAbrir={abrir} carteiraAberta={carteiraAberta} soLeitura={isComando} />
                      ))}
                    </AnimatePresence>
                    {grupos[n].length === 0 && (
                      <li className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-xs text-ink-2">Nada aqui.</li>
                    )}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
      <AvisoDesfazer aviso={desfazer} onFechar={() => setDesfazer(null)} />
    </AppShell>
  )
}
