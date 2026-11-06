import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Bell, CheckCheck, Inbox, Loader2, Settings2, TriangleAlert } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import ErroCarga from '../components/ErroCarga'
import useNotificacoes, { EVENTO_LIDAS } from '../components/useNotificacoes'
import { EsqueletoNotificacoes, ItemNotificacao } from '../components/Notificacoes'
import { useAuth } from '../context/AuthContext'
import { listarNotificacoes } from '../api'
import { categoriasDoPapel, porDia } from '../lib/notificacoes'

/**
 * Notificações (docs/PLANO_NOTIFICACOES.md, seção 12): tudo o que o sino avisou para
 * a pessoa, com o histórico dos últimos 90 dias e filtros por assunto. O sino e esta
 * página andam juntos: marcar como lida num muda o outro na hora.
 */
const TITULO = 'Notificações'
const SUBTITULO = 'Tudo o que o Mizan avisou para você: o que falta ver e o histórico dos últimos 90 dias.'
const POR_PAGINA = 50

function Chip({ ativo, onClick, children }) {
  return (
    <button type="button" aria-pressed={ativo} onClick={onClick}
      className={`inline-flex min-h-[40px] items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors ${ativo
        ? 'border-[var(--royal)] bg-[rgb(var(--c-royal)/0.10)] font-semibold text-ink'
        : 'border-line text-ink-2 hover:border-[var(--border-strong)] hover:text-ink'}`}>
      {children}
    </button>
  )
}

export default function Notificacoes() {
  const { isComando, isAdmin } = useAuth()
  const sino = useNotificacoes()
  const [filtro, setFiltro] = useState('pendentes')
  const [categoria, setCategoria] = useState('')
  const [soUrgentes, setSoUrgentes] = useState(false)
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(!isComando)
  const [erro, setErro] = useState(null)
  const [maisCarregando, setMaisCarregando] = useState(false)
  const pedido = useRef(0)
  const filtroRef = useRef(filtro)
  filtroRef.current = filtro

  const carregar = useCallback(async () => {
    if (isComando) return
    const meu = ++pedido.current
    setCarregando(true)
    try {
      const r = await listarNotificacoes({ filtro, limite: POR_PAGINA, categoria: categoria || undefined,
        prioridade: soUrgentes ? 'urgente' : undefined })
      if (meu !== pedido.current) return
      setDados(r); setErro(null)
    } catch (e) {
      if (meu === pedido.current) setErro(e)
    } finally {
      if (meu === pedido.current) setCarregando(false)
    }
  }, [isComando, filtro, categoria, soUrgentes])

  useEffect(() => { carregar() }, [carregar])

  // Ao vivo: o servidor avisou que mudou, ou o sino marcou algo como lido nesta aba.
  useEffect(() => {
    const doServidor = () => carregar()
    const lidas = (e) => {
      const { ids, todas } = e.detail || {}
      setDados(d => {
        if (!d) return d
        const itens = d.itens.map(i => (todas || (ids || []).includes(i.id) ? { ...i, lida: true } : i))
          .filter(i => filtroRef.current === 'todas' || !i.lida)
        return { ...d, itens }
      })
    }
    window.addEventListener('mizan:notificacoes', doServidor)
    window.addEventListener(EVENTO_LIDAS, lidas)
    return () => {
      window.removeEventListener('mizan:notificacoes', doServidor)
      window.removeEventListener(EVENTO_LIDAS, lidas)
    }
  }, [carregar])

  async function carregarMais() {
    const ultimo = dados?.itens?.[dados.itens.length - 1]
    if (!ultimo || maisCarregando) return
    setMaisCarregando(true)
    try {
      const r = await listarNotificacoes({ filtro, limite: POR_PAGINA, antes: ultimo.atualizado_em,
        categoria: categoria || undefined, prioridade: soUrgentes ? 'urgente' : undefined })
      setDados(d => ({ ...d, mais: !!r?.mais,
        itens: [...d.itens, ...(r?.itens || []).filter(i => !d.itens.some(x => x.id === i.id))] }))
    } catch (e) {
      setErro(e)
    } finally {
      setMaisCarregando(false)
    }
  }

  // As contagens do sino estão sempre em dia (ele acompanha cada marcação); sem ele, as da página.
  const doSino = sino?.ligado && sino.ativo
  const naoLidas = doSino ? sino.naoLidas : (dados?.nao_lidas || 0)
  const urgentes = doSino ? sino.urgentes : (dados?.urgentes || 0)
  const porCategoria = (doSino && Object.keys(sino.por_categoria || {}).length ? sino.por_categoria : dados?.por_categoria) || {}
  const agora = useMemo(() => new Date(), [dados])          // eslint-disable-line react-hooks/exhaustive-deps
  const grupos = useMemo(() => porDia(dados?.itens || [], agora), [dados, agora])
  const categorias = categoriasDoPapel(isAdmin)
  const rotuloCategoria = categorias.find(c => c.id === categoria)?.rotulo
  const comFiltro = !!categoria || soUrgentes

  if (isComando) {
    return (
      <AppShell titulo={TITULO}>
        <CabecalhoPagina rotulo="Avisos" icone={Bell} titulo={TITULO} ajuda="notificacoes" subtitulo={SUBTITULO} />
        <div role="status" className="rounded-[22px] border border-line bg-surface px-6 py-8 text-center">
          <Bell className="mx-auto h-6 w-6 text-ink-3" aria-hidden="true" />
          <p className="mt-2 font-semibold text-ink">O COMANDO não tem sino</p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-ink-2">
            As notificações são de quem trabalha numa empresa: o administrador e os operadores recebem aqui o que precisa
            deles. O COMANDO acompanha as empresas pelo painel COMANDO e pelas Dúvidas.
          </p>
        </div>
      </AppShell>
    )
  }

  function vazio() {
    if (dados && !dados.ativo) {
      return { titulo: 'As notificações ainda não foram ligadas', texto: 'Quando forem ligadas no banco da empresa, os avisos aparecem aqui e no sino.' }
    }
    if (comFiltro) {
      const assunto = rotuloCategoria ? ` de ${rotuloCategoria}` : ''
      const tipo = soUrgentes ? ' urgente' : ''
      return { titulo: `Nenhuma notificação${tipo}${assunto}${filtro === 'pendentes' ? ' não lida' : ''}`,
        texto: 'Tente outro assunto ou limpe os filtros.', acao: { rotulo: 'Limpar filtros', onClick: () => { setCategoria(''); setSoUrgentes(false) } } }
    }
    if (filtro === 'pendentes') {
      return { titulo: 'Tudo lido por aqui', texto: 'Quando algo precisar de você (uma mensagem, uma reunião, um pagamento para conferir), aparece aqui e no sino.',
        acao: { rotulo: 'Ver todas', onClick: () => setFiltro('todas') } }
    }
    return { titulo: 'Ainda não há notificações', texto: 'Os avisos dos últimos 90 dias ficam guardados aqui.' }
  }

  return (
    <AppShell titulo={TITULO}>
      <CabecalhoPagina rotulo="Avisos" icone={Bell} titulo={TITULO} ajuda="notificacoes" subtitulo={SUBTITULO}>
        {sino?.ligado && (
          <button type="button" onClick={() => sino.abrirPainel('preferencias')} className="btn-secondary btn-sm">
            <Settings2 className="h-4 w-4" aria-hidden="true" /> Preferências
          </button>
        )}
        {naoLidas > 0 && (
          <button type="button" onClick={() => sino?.marcarTodas()} className="btn-primary btn-sm">
            <CheckCheck className="h-4 w-4" aria-hidden="true" /> Marcar todas como lidas
          </button>
        )}
      </CabecalhoPagina>

      <div className="space-y-5">
        <p className="flex flex-wrap items-center gap-x-2 text-sm text-ink-2" aria-live="polite">
          <span className="font-semibold text-ink tabular-nums">
            {naoLidas ? `${naoLidas} ${naoLidas === 1 ? 'não lida' : 'não lidas'}` : 'Tudo lido'}
          </span>
          {urgentes > 0 && (
            <span className="inline-flex items-center gap-1 font-semibold" style={{ color: 'var(--danger)' }}>
              · <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" /> {urgentes} {urgentes === 1 ? 'urgente' : 'urgentes'}
            </span>
          )}
        </p>

        <div className="space-y-3 rounded-[22px] border border-line bg-surface px-4 py-4 sm:px-5">
          <div role="tablist" aria-label="Quais notificações" className="flex gap-1 border-b border-line">
            {[['pendentes', `Não lidas${naoLidas ? ` (${naoLidas > 99 ? '99+' : naoLidas})` : ''}`], ['todas', 'Todas']].map(([id, rotulo]) => (
              <button key={id} type="button" role="tab" aria-selected={filtro === id} onClick={() => setFiltro(id)}
                className={`-mb-px min-h-[40px] border-b-2 px-3 text-sm ${filtro === id
                  ? 'border-[var(--royal)] font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
                {rotulo}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Assunto">
            <Chip ativo={!categoria} onClick={() => setCategoria('')}>Todos os assuntos</Chip>
            {categorias.map(c => (
              <Chip key={c.id} ativo={categoria === c.id} onClick={() => setCategoria(categoria === c.id ? '' : c.id)}>
                {c.rotulo}
                {porCategoria[c.id] > 0 && <span className="tabular-nums text-ink-3">({porCategoria[c.id]})</span>}
              </Chip>
            ))}
          </div>
          <label className="inline-flex min-h-[40px] cursor-pointer items-center gap-2 text-sm text-ink">
            <input type="checkbox" className="h-4 w-4 accent-[var(--royal)]" checked={soUrgentes}
              onChange={e => setSoUrgentes(e.target.checked)} />
            Só urgentes
          </label>
        </div>

        {carregando && !dados ? <EsqueletoNotificacoes />
          : erro && !dados?.itens?.length ? <ErroCarga erro={erro} onTentar={carregar} />
          : !dados?.itens?.length ? (() => {
            const v = vazio()
            return (
              <div className="rounded-[22px] border border-dashed border-line px-6 py-10 text-center">
                <Inbox className="mx-auto h-6 w-6 text-ink-3" aria-hidden="true" />
                <p className="mt-2 font-semibold text-ink">{v.titulo}</p>
                <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">{v.texto}</p>
                {v.acao && <button type="button" onClick={v.acao.onClick} className="btn-ghost btn-sm mt-3">{v.acao.rotulo}</button>}
              </div>
            )
          })() : (
            <div className="space-y-6" aria-busy={carregando}>
              {erro && <ErroCarga erro={erro} onTentar={carregar} compacto />}
              {grupos.map(g => (
                <section key={g.id} aria-labelledby={`dia-${g.id}`}>
                  <h2 id={`dia-${g.id}`} className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{g.titulo}</h2>
                  <ul className="space-y-2">
                    {g.itens.map(i => (
                      <ItemNotificacao key={i.id} item={i} agora={agora} onAbrir={sino?.abrir} onLida={sino?.marcarLida} />
                    ))}
                  </ul>
                </section>
              ))}
              {dados.mais && (
                <button type="button" onClick={carregarMais} disabled={maisCarregando} className="btn-ghost btn-sm w-full">
                  {maisCarregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</> : 'Carregar as mais antigas'}
                </button>
              )}
            </div>
          )}
      </div>
    </AppShell>
  )
}
