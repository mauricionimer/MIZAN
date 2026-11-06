import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  consultarMudancas, listarNotificacoes, marcarNotificacaoLida, marcarNotificacoesLidas,
  salvarPreferenciasNotificacoes,
} from '../api'
import { linkInterno, novasQueTocam, tituloDaAba, urgenteParaAvisar } from '../lib/notificacoes'

/**
 * Estado do sino de notificações, um só para a casca inteira (sino, painel e aviso
 * de urgente). Busca a lista quando o servidor avisa que mudou (`mizan:notificacoes`,
 * via useMudancasDoServidor), a cada minuto como reserva e, com a aba escondida,
 * pergunta a cada 20 s à rota leve /mudancas para o aviso do navegador chegar.
 *
 * O que chama a atenção vem marcado pelo servidor (`toca`): urgente sempre; alta
 * fora do horário silencioso. Cada aviso toca uma vez por aba.
 */
const Ctx = createContext(null)
const VISTAS = 'mizan_notificacoes_vistas'          // apagada no logout (limparSessaoLocal)
const FUNDO_MS = 20_000
const RESERVA_MS = 60_000
const VAZIO = { ativo: false, itens: [], naoLidas: 0, urgentes: 0, por_categoria: {}, mais: false, preferencias: null, mensagem: null }

function lerVistas() {
  try { return new Set(JSON.parse(sessionStorage.getItem(VISTAS) || '[]')) } catch { return new Set() }
}
function gravarVistas(s) {
  try { sessionStorage.setItem(VISTAS, JSON.stringify([...s].slice(-300))) } catch { /* sem armazenamento */ }
}
const temNotificacaoDoNavegador = () => typeof window !== 'undefined' && 'Notification' in window

// A página de notificações escuta este evento para refletir na hora o que o sino marcou como lido.
export const EVENTO_LIDAS = 'mizan:notificacoes-lidas'
function avisarLidas(detalhe) {
  try { window.dispatchEvent(new CustomEvent(EVENTO_LIDAS, { detail: detalhe })) } catch { /* sem janela */ }
}

export function NotificacoesProvider({ irPara, children }) {
  const { token, isComando } = useAuth()
  const ligado = !!token && !isComando
  const [estado, setEstado] = useState(VAZIO)
  const [carregando, setCarregando] = useState(false)
  const [carregou, setCarregou] = useState(false)
  const [erro, setErro] = useState(null)
  const [filtro, setFiltroEstado] = useState('pendentes')
  const [aberto, setAberto] = useState(false)
  const [vistaInicial, setVistaInicial] = useState('lista')       // o painel abre na lista ou nas preferências
  const [urgente, setUrgente] = useState(null)
  const vistas = useRef(lerVistas())
  const filtroRef = useRef(filtro)
  const irParaRef = useRef(irPara)
  irParaRef.current = irPara
  const base = useRef(typeof document !== 'undefined' ? tituloDaAba(document.title, 0) : 'Mizan')

  const abrir = useCallback((item) => {
    setAberto(false)
    setUrgente(u => (u && u.id === item.id ? null : u))
    if (!item.lida) {
      setEstado(s => ({
        ...s,
        itens: s.itens.map(i => (i.id === item.id ? { ...i, lida: true } : i))
          .filter(i => filtroRef.current === 'todas' || i.id !== item.id),
        naoLidas: Math.max(0, s.naoLidas - 1),
        urgentes: Math.max(0, s.urgentes - (item.prioridade === 'urgente' ? 1 : 0)),
      }))
      marcarNotificacaoLida(item.id).catch(() => {})
      avisarLidas({ ids: [item.id] })
    }
    ;(irParaRef.current || ((rota) => { window.location.assign(rota) }))(linkInterno(item.link))
  }, [])

  const irParaRota = useCallback((rota) => {
    setAberto(false)
    ;(irParaRef.current || ((r) => { window.location.assign(r) }))(linkInterno(rota))
  }, [])

  const avisar = useCallback((r) => {
    const novas = novasQueTocam(r?.itens, vistas.current)
    if (!novas.length) return
    const prefs = r?.preferencias || {}
    if (typeof document !== 'undefined' && document.hidden && prefs.navegador && temNotificacaoDoNavegador()
        && Notification.permission === 'granted') {
      // Fora do Mizan, nunca o nome do devedor: só o tipo do aviso.
      for (const n of novas.slice(0, 3)) {
        try {
          const aviso = new Notification(n.externo || 'Aviso novo no Mizan',
            { body: 'Abra o Mizan para ver.', tag: `mizan-${n.id}`, icon: '/favicon.svg' })
          aviso.onclick = () => { window.focus(); abrir(n); aviso.close() }
        } catch { /* navegador sem suporte ao construtor (ex.: celular) */ }
      }
    }
    const u = urgenteParaAvisar(r?.itens, vistas.current)
    if (u) setUrgente(u)
    novas.forEach(n => vistas.current.add(n.id))
    gravarVistas(vistas.current)
  }, [abrir])

  const carregar = useCallback(async (f) => {
    if (!ligado) return
    const qual = f || filtroRef.current
    setCarregando(true)
    try {
      const r = await listarNotificacoes({ filtro: qual })
      if (qual !== filtroRef.current) return            // a pessoa trocou de aba enquanto carregava
      setEstado({ ativo: !!r?.ativo, itens: r?.itens || [], naoLidas: r?.nao_lidas || 0, urgentes: r?.urgentes || 0,
        por_categoria: r?.por_categoria || {}, mais: !!r?.mais, preferencias: r?.preferencias || null,
        mensagem: r?.mensagem || null })
      setErro(null)
      avisar(r)
    } catch (e) {
      setErro(e)
    } finally {
      setCarregando(false)
      setCarregou(true)
    }
  }, [ligado, avisar])

  const carregarMais = useCallback(async () => {
    const ultimo = estado.itens[estado.itens.length - 1]
    if (!ultimo || !estado.mais) return
    try {
      const r = await listarNotificacoes({ filtro: filtroRef.current, antes: ultimo.atualizado_em })
      setEstado(s => ({ ...s, itens: [...s.itens, ...(r?.itens || []).filter(i => !s.itens.some(x => x.id === i.id))],
        mais: !!r?.mais }))
    } catch (e) { setErro(e) }
  }, [estado.itens, estado.mais])

  const setFiltro = useCallback((f) => {
    filtroRef.current = f
    setFiltroEstado(f)
    carregar(f)
  }, [carregar])

  const marcarLida = useCallback(async (id) => {
    setEstado(s => {
      const alvo = s.itens.find(i => i.id === id)
      if (!alvo || alvo.lida) return s
      return { ...s,
        itens: s.itens.map(i => (i.id === id ? { ...i, lida: true } : i)).filter(i => filtroRef.current === 'todas' || i.id !== id),
        naoLidas: Math.max(0, s.naoLidas - 1),
        urgentes: Math.max(0, s.urgentes - (alvo.prioridade === 'urgente' ? 1 : 0)),
        por_categoria: { ...s.por_categoria,
          [alvo.categoria]: Math.max(0, ((s.por_categoria || {})[alvo.categoria] || 0) - 1) } }
    })
    setUrgente(u => (u && u.id === id ? null : u))
    avisarLidas({ ids: [id] })
    try { await marcarNotificacaoLida(id) } catch (e) { setErro(e); carregar() }
  }, [carregar])

  const marcarTodas = useCallback(async () => {
    setEstado(s => ({ ...s, naoLidas: 0, urgentes: 0,
      por_categoria: Object.fromEntries(Object.keys(s.por_categoria || {}).map(c => [c, 0])),
      itens: filtroRef.current === 'todas' ? s.itens.map(i => ({ ...i, lida: true })) : [] }))
    setUrgente(null)
    avisarLidas({ todas: true })
    try { await marcarNotificacoesLidas() } catch (e) { setErro(e) } finally { carregar() }
  }, [carregar])

  const salvarPreferencias = useCallback(async (p) => {
    const r = await salvarPreferenciasNotificacoes(p)
    setEstado(s => ({ ...s, preferencias: r }))
    return r
  }, [])

  const pedirPermissao = useCallback(async () => {
    if (!temNotificacaoDoNavegador()) return 'indisponivel'
    if (Notification.permission !== 'default') return Notification.permission
    try { return await Notification.requestPermission() } catch { return 'denied' }
  }, [])

  // Primeira carga, troca de pessoa e limpeza no logout.
  useEffect(() => {
    if (!ligado) { setEstado(VAZIO); setUrgente(null); setCarregou(false); return }
    carregar()
  }, [ligado, token])        // eslint-disable-line react-hooks/exhaustive-deps

  // O servidor avisou que mudou (via /mudancas, a cada 2 s com a aba visível).
  useEffect(() => {
    const mudou = () => carregar()
    window.addEventListener('mizan:notificacoes', mudou)
    return () => window.removeEventListener('mizan:notificacoes', mudou)
  }, [carregar])

  // Reserva com a aba visível; com ela escondida, a rota leve, para o aviso do navegador.
  useEffect(() => {
    if (!ligado) return
    let vivo = true, versao = null, ocupado = false
    const reserva = setInterval(() => { if (!document.hidden) carregar() }, RESERVA_MS)
    const fundo = setInterval(async () => {
      if (!document.hidden || ocupado) return
      ocupado = true
      try {
        const v = await consultarMudancas()
        if (!vivo || !v?.notificacoes) return
        if (versao && v.notificacoes !== versao) carregar()
        versao = v.notificacoes
      } catch { /* a próxima volta tenta de novo */ } finally { ocupado = false }
    }, FUNDO_MS)
    return () => { vivo = false; clearInterval(reserva); clearInterval(fundo) }
  }, [ligado, carregar])

  // "(3) Mizan" na aba do navegador.
  useEffect(() => {
    if (typeof document === 'undefined') return
    document.title = tituloDaAba(base.current, ligado && estado.ativo ? estado.naoLidas : 0)
  }, [ligado, estado.ativo, estado.naoLidas])
  useEffect(() => () => { if (typeof document !== 'undefined') document.title = base.current }, [])

  const valor = useMemo(() => ({
    ligado, ...estado, carregando, carregou, erro, filtro, setFiltro, aberto, urgente, vistaInicial,
    // Só 'preferencias' muda a vista: chamado direto pelo onClick, o argumento é o evento do clique.
    abrirPainel: (vista) => { setVistaInicial(vista === 'preferencias' ? 'preferencias' : 'lista'); setAberto(true); carregar() },
    fecharPainel: () => setAberto(false),
    fecharUrgente: () => setUrgente(null), abrir, irPara: irParaRota, marcarLida, marcarTodas, carregarMais, salvarPreferencias,
    pedirPermissao, recarregar: () => carregar(),
  }), [ligado, estado, carregando, carregou, erro, filtro, setFiltro, aberto, urgente, vistaInicial, carregar, abrir,
    irParaRota, marcarLida, marcarTodas, carregarMais, salvarPreferencias, pedirPermissao])

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

export default function useNotificacoes() {
  return useContext(Ctx)
}
