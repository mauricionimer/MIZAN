import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import {
  Bell, BellRing, CalendarClock, CheckCheck, ChevronLeft, Loader2, MessageSquare, Settings2, ShieldAlert,
  Trash2, TriangleAlert, Users, Wallet, Wrench, X,
} from 'lucide-react'
import useModal from './useModal'
import useNotificacoes from './useNotificacoes'
import ErroCarga from './ErroCarga'
import { useAuth } from '../context/AuthContext'
import { categoriasDoPapel, HORAS, rotuloDoSino, secoes, tempoRelativo } from '../lib/notificacoes'

/**
 * Sino de notificações (docs/NOTIFICACOES.md): o botão do cabeçalho, o painel com a
 * lista e as preferências, e o aviso de urgente no topo da tela. O estado vem de
 * useNotificacoes (um só para a casca inteira).
 */
const ICONE = { conversas: MessageSquare, reunioes: CalendarClock, retornos: Wallet, pedidos: ShieldAlert,
  equipe: Users, sistema: Wrench }

export function SinoNotificacoes() {
  const n = useNotificacoes()
  if (!n?.ligado || !n.ativo) return null
  const Icone = n.urgentes ? BellRing : Bell
  return (
    <button type="button" onClick={() => n.abrirPainel()} aria-label={rotuloDoSino(n.naoLidas, n.urgentes)}
      aria-haspopup="dialog" aria-expanded={n.aberto} title="Notificações"
      className="relative inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-2 hover:bg-raise-2 hover:text-ink">
      <Icone className="h-5 w-5" aria-hidden="true" />
      {n.naoLidas > 0 && (
        <span aria-hidden="true"
          className={`absolute -right-0.5 -top-0.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-full px-1 text-[11px] font-semibold leading-5 tabular-nums ${
            n.urgentes ? 'bg-red-600 text-white' : 'bg-[var(--royal)] text-[var(--on-brand)]'}`}>
          {n.naoLidas > 99 ? '99+' : n.naoLidas}
        </span>
      )}
    </button>
  )
}

export function EsqueletoNotificacoes() {
  return (
    <ul className="space-y-2" aria-hidden="true">
      {[0, 1, 2].map(i => (
        <li key={i} className="flex gap-3 rounded-xl border border-line px-3 py-3">
          <span className="h-8 w-8 shrink-0 rounded-lg bg-raise-2 motion-safe:animate-pulse" />
          <span className="flex-1 space-y-2">
            <span className="block h-3.5 w-3/4 rounded bg-raise-2 motion-safe:animate-pulse" />
            <span className="block h-3 w-1/2 rounded bg-raise-2 motion-safe:animate-pulse" />
          </span>
        </li>
      ))}
    </ul>
  )
}

// Depois da lixeira, o foco vai para a lixeira vizinha (a próxima ou a anterior), para quem usa o teclado.
function focarVizinha(botao) {
  const todas = [...(botao.closest('[data-lista-notificacoes]')?.querySelectorAll('[data-lixeira]') || [])]
  const i = todas.indexOf(botao)
  const alvo = todas[i + 1] || todas[i - 1]
  if (alvo) setTimeout(() => alvo.focus(), 0)
}

export function ItemNotificacao({ item, agora, onAbrir, onLida, onExcluir }) {
  const Icone = ICONE[item.categoria] || Bell
  const urgente = item.prioridade === 'urgente'
  const cor = urgente ? 'var(--danger)' : 'var(--royal)'
  return (
    <li className={`flex gap-3 rounded-xl border px-3 py-3 ${item.lida ? 'border-line/60' : 'border-line bg-raise-1'}`}>
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        style={{ background: urgente ? 'rgb(var(--c-danger) / 0.12)' : 'rgb(var(--c-royal) / 0.10)', color: cor }}>
        <Icone className="h-4 w-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          <p className={`min-w-0 flex-1 break-words text-sm ${item.lida ? 'text-ink-2' : 'font-semibold text-ink'}`}>
            {item.titulo}
          </p>
          {!item.lida && (
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: cor }} aria-hidden="true" />
          )}
        </div>
        {item.texto && <p className="mt-0.5 break-words text-[13px] text-ink-2">{item.texto}</p>}
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-3">
          {urgente && !item.lida && (
            <span className="inline-flex items-center gap-1 font-semibold" style={{ color: 'var(--danger)' }}>
              <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" /> Urgente
            </span>
          )}
          <span className="tabular-nums">{tempoRelativo(item.atualizado_em || item.criado_em, agora)}</span>
          {item.lida && <span>· Lida</span>}
        </p>
        <div className="mt-2 flex items-start gap-2">
          <div className="flex min-w-0 flex-1 flex-wrap gap-2">
            <button type="button" onClick={() => onAbrir(item)} className="btn-secondary btn-sm">{item.acao || 'Abrir'}</button>
            {!item.lida && (
              <button type="button" onClick={() => onLida(item.id)} className="btn-ghost btn-sm">Marcar como lida</button>
            )}
          </div>
          {onExcluir && (
            <button type="button" data-lixeira onClick={(e) => { focarVizinha(e.currentTarget); onExcluir(item) }}
              aria-label={`Excluir a notificação: ${item.titulo}`} title="Excluir"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-[rgb(var(--c-danger)/0.10)] hover:text-[var(--danger)]">
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

function Lista() {
  const n = useNotificacoes()
  const agora = useMemo(() => new Date(), [n.itens])            // eslint-disable-line react-hooks/exhaustive-deps
  const grupos = useMemo(() => secoes(n.itens, agora), [n.itens, agora])
  const [maisCarregando, setMaisCarregando] = useState(false)
  if (!n.carregou && n.carregando) return <EsqueletoNotificacoes />
  if (n.erro && !n.itens.length) return <ErroCarga erro={n.erro} onTentar={n.recarregar} />
  if (!n.itens.length) {
    return (
      <div className="rounded-xl border border-dashed border-line px-4 py-8 text-center">
        <CheckCheck className="mx-auto h-6 w-6 text-ink-3" aria-hidden="true" />
        <p className="mt-2 text-sm font-semibold text-ink">
          {n.filtro === 'pendentes' ? 'Tudo lido por aqui' : 'Ainda não há notificações'}
        </p>
        <p className="mt-1 text-[13px] text-ink-2">
          {n.filtro === 'pendentes'
            ? 'Quando algo precisar de você (uma mensagem, uma reunião, um pagamento para conferir), aparece aqui.'
            : 'O que você já leu fica aqui por 30 dias. O que já passou ou foi resolvido sai sozinho.'}
        </p>
        {n.filtro === 'pendentes' && (
          <button type="button" onClick={() => n.setFiltro('todas')} className="btn-ghost btn-sm mt-3">Ver todas</button>
        )}
      </div>
    )
  }
  return (
    <div className="space-y-5" data-lista-notificacoes>
      {n.erro && <ErroCarga erro={n.erro} onTentar={n.recarregar} compacto />}
      {grupos.map(g => (
        <section key={g.id} aria-labelledby={`notificacoes-${g.id}`}>
          <h3 id={`notificacoes-${g.id}`} className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{g.titulo}</h3>
          <ul className="space-y-2">
            {g.itens.map(i => (
              <ItemNotificacao key={i.id} item={i} agora={agora} onAbrir={n.abrir} onLida={n.marcarLida} onExcluir={n.excluir} />
            ))}
          </ul>
        </section>
      ))}
      {n.mais && (
        <button type="button" disabled={maisCarregando} className="btn-ghost btn-sm w-full"
          onClick={async () => { setMaisCarregando(true); try { await n.carregarMais() } finally { setMaisCarregando(false) } }}>
          {maisCarregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</> : 'Carregar as mais antigas'}
        </button>
      )}
    </div>
  )
}

function Preferencias({ onVoltar }) {
  const n = useNotificacoes()
  const { isAdmin } = useAuth()
  const inicial = n.preferencias || {}
  const [p, setP] = useState({ navegador: false, email_resumo: false, silencio_ligado: true, silencio_inicio: 20,
    silencio_fim: 8, desligadas: [], ...inicial })
  const [salvando, setSalvando] = useState(false)
  const [salvo, setSalvo] = useState(false)
  const [erro, setErro] = useState(null)
  const [aviso, setAviso] = useState('')
  const suporte = typeof window !== 'undefined' && 'Notification' in window
  const muda = (campo, valor) => { setP(x => ({ ...x, [campo]: valor })); setSalvo(false) }

  async function navegador(ligar) {
    setAviso('')
    if (!ligar) { muda('navegador', false); return }
    const r = await n.pedirPermissao()
    if (r === 'granted') muda('navegador', true)
    else if (r === 'indisponivel') setAviso('Este navegador não mostra avisos. No celular, use o sino com o Mizan aberto.')
    else setAviso('O navegador bloqueou os avisos do Mizan. Libere nas configurações do site e tente de novo.')
  }
  async function salvar() {
    if (salvando) return
    setSalvando(true); setErro(null)
    try { setP(await n.salvarPreferencias(p)); setSalvo(true) } catch (e) { setErro(e) } finally { setSalvando(false) }
  }
  const caixa = 'flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-canvas px-3.5 py-3'
  return (
    <div className="space-y-5">
      <button type="button" onClick={onVoltar} className="btn-ghost btn-sm -ml-2">
        <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Voltar aos avisos
      </button>
      <fieldset className="space-y-2">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Onde avisar</legend>
        <label className={caixa}>
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--royal)]" checked={!!p.navegador}
            disabled={!suporte} onChange={e => navegador(e.target.checked)} />
          <span className="text-sm text-ink">
            Aviso do navegador
            <span className="block text-[13px] text-ink-2">Com o Mizan aberto em outra aba, o urgente e o importante aparecem no canto da tela. O texto não leva o nome do cliente.</span>
          </span>
        </label>
        {aviso && <p role="status" className="text-[13px]" style={{ color: 'var(--warning)' }}>{aviso}</p>}
        <label className={caixa}>
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--royal)]" checked={!!p.email_resumo}
            onChange={e => muda('email_resumo', e.target.checked)} />
          <span className="text-sm text-ink">
            Resumo por e-mail às 8h
            <span className="block text-[13px] text-ink-2">Quantos avisos estão abertos, por assunto. Sem nome, CPF ou valor.</span>
          </span>
        </label>
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Horário silencioso</legend>
        <label className={caixa}>
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--royal)]" checked={!!p.silencio_ligado}
            onChange={e => muda('silencio_ligado', e.target.checked)} />
          <span className="text-sm text-ink">
            Só o urgente toca neste horário
            <span className="block text-[13px] text-ink-2">O resto fica no sino, sem chamar a atenção.</span>
          </span>
        </label>
        {p.silencio_ligado && (
          <div className="flex flex-wrap items-center gap-2 pl-1 text-sm text-ink-2">
            <label htmlFor="silencio-inicio">Das</label>
            <select id="silencio-inicio" className="input-base !w-auto" value={p.silencio_inicio}
              onChange={e => muda('silencio_inicio', Number(e.target.value))}>
              {HORAS.map(h => <option key={h.valor} value={h.valor}>{h.rotulo}</option>)}
            </select>
            <label htmlFor="silencio-fim">às</label>
            <select id="silencio-fim" className="input-base !w-auto" value={p.silencio_fim}
              onChange={e => muda('silencio_fim', Number(e.target.value))}>
              {HORAS.map(h => <option key={h.valor} value={h.valor}>{h.rotulo}</option>)}
            </select>
          </div>
        )}
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Assuntos</legend>
        <p className="text-[13px] text-ink-2">O que é urgente sempre chega: risco grave, reunião em 5 minutos, agente parado.</p>
        {categoriasDoPapel(isAdmin).map(c => {
          const ligada = !(p.desligadas || []).includes(c.id)
          return (
            <label key={c.id} className={caixa}>
              <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--royal)]" checked={ligada}
                onChange={e => muda('desligadas', e.target.checked
                  ? (p.desligadas || []).filter(x => x !== c.id) : [...(p.desligadas || []), c.id])} />
              <span className="text-sm text-ink">{c.rotulo}<span className="block text-[13px] text-ink-2">{c.dica}</span></span>
            </label>
          )
        })}
      </fieldset>
      {erro && <ErroCarga erro={erro} />}
      <div className="flex items-center gap-3">
        <button type="button" onClick={salvar} disabled={salvando} className="btn-primary min-h-[44px]">
          {salvando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando…</> : 'Salvar preferências'}
        </button>
        {salvo && <span role="status" className="text-sm" style={{ color: 'var(--success)' }}>Preferências salvas.</span>}
      </div>
    </div>
  )
}

export function PainelNotificacoes() {
  const n = useNotificacoes()
  const reduzir = useReducedMotion()
  const aberto = !!n?.aberto
  const caixa = useModal(aberto, () => n?.fecharPainel())
  const [vista, setVista] = useState('lista')
  useEffect(() => { if (aberto) setVista(n?.vistaInicial || 'lista') }, [aberto])   // eslint-disable-line react-hooks/exhaustive-deps
  if (!n?.ligado) return null
  return createPortal(
    <AnimatePresence>
      {aberto && (
        <>
          <motion.div key="fundo" className="fixed inset-0 z-[55] bg-black/40" aria-hidden="true"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduzir ? 0 : 0.18 }}
            onClick={n.fecharPainel} />
          <motion.aside key="painel" ref={caixa} role="dialog" aria-modal="true" aria-labelledby="notificacoes-titulo"
            className="fixed inset-y-0 right-0 z-[56] flex w-full flex-col border-l border-line bg-surface shadow-2xl sm:w-[420px] sm:max-w-[92vw]"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={reduzir ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 42 }}>
            <div className="flex items-center gap-2 border-b border-line px-4 py-3">
              <h2 id="notificacoes-titulo" className="min-w-0 flex-1 text-base font-bold text-ink">
                {vista === 'preferencias' ? 'Preferências de notificação' : 'Notificações'}
              </h2>
              {vista === 'lista' && (
                <button type="button" onClick={() => setVista('preferencias')} aria-label="Preferências de notificação"
                  title="Preferências" className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-2 hover:bg-raise-2">
                  <Settings2 className="h-5 w-5" aria-hidden="true" />
                </button>
              )}
              <button type="button" onClick={n.fecharPainel} aria-label="Fechar notificações"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-2 hover:bg-raise-2">
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            {vista === 'lista' && (
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2">
                <div role="tablist" aria-label="Quais notificações" className="flex gap-1">
                  {[['pendentes', `Não lidas${n.naoLidas ? ` (${n.naoLidas > 99 ? '99+' : n.naoLidas})` : ''}`], ['todas', 'Todas']].map(([id, rotulo]) => (
                    <button key={id} type="button" role="tab" aria-selected={n.filtro === id} onClick={() => n.setFiltro(id)}
                      className={`-mb-px min-h-[40px] border-b-2 px-3 text-sm ${n.filtro === id
                        ? 'border-[var(--royal)] font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
                      {rotulo}
                    </button>
                  ))}
                </div>
                <div className="ml-auto flex flex-wrap justify-end gap-1">
                  {n.naoLidas > 0 && (
                    <button type="button" onClick={n.marcarTodas} className="btn-ghost btn-sm">
                      <CheckCheck className="h-4 w-4" aria-hidden="true" /> Marcar todas como lidas
                    </button>
                  )}
                  {n.filtro === 'todas' && n.itens.some(i => i.lida) && (
                    <button type="button" onClick={() => n.excluirLidas()} className="btn-ghost-danger btn-sm">
                      <Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir as lidas
                    </button>
                  )}
                </div>
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              {vista === 'preferencias' ? <Preferencias onVoltar={() => setVista('lista')} /> : <Lista />}
            </div>
            {vista === 'lista' && (
              <div className="border-t border-line px-4 py-3">
                <button type="button" onClick={() => n.irPara('/notificacoes')} className="btn-secondary btn-sm w-full">
                  Ver todas as notificações
                </button>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body)
}

/** O urgente aparece no topo da tela, com o botão da ação. Fechar não marca como lido. */
export function AvisoUrgente() {
  const n = useNotificacoes()
  const reduzir = useReducedMotion()
  const u = n?.ligado && !n.aberto ? n.urgente : null
  return createPortal(
    <AnimatePresence>
      {u && (
        <motion.div key={u.id} role="alert" aria-live="assertive"
          initial={reduzir ? false : { opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
          transition={{ duration: reduzir ? 0 : 0.25 }}
          className="fixed inset-x-3 top-[72px] z-[60] mx-auto max-w-lg overflow-hidden rounded-xl border border-line bg-surface shadow-2xl sm:left-auto sm:right-6 sm:mx-0 sm:w-[420px]"
          style={{ borderLeft: '4px solid var(--danger)' }}>
          <div className="flex items-start gap-3 px-4 py-3">
            <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--danger)' }} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--danger)' }}>Urgente</p>
              <p className="break-words text-sm font-semibold text-ink">{u.titulo}</p>
              {u.texto && <p className="mt-0.5 break-words text-[13px] text-ink-2">{u.texto}</p>}
              <div className="mt-2.5 flex flex-wrap gap-2">
                <button type="button" onClick={() => n.abrir(u)} className="btn-primary btn-sm">{u.acao || 'Abrir'}</button>
                <button type="button" onClick={() => n.marcarLida(u.id)} className="btn-ghost btn-sm">Marcar como lida</button>
              </div>
            </div>
            <button type="button" onClick={n.fecharUrgente} aria-label="Fechar aviso urgente"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-2 hover:bg-raise-2">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body)
}
