import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  consultarMudancas, excluirNotificacoes, listarNotificacoes, marcarNotificacaoLida, marcarNotificacoesLidas,
  salvarPreferenciasNotificacoes,
} from '../api'
import AvisoDesfazer from './AvisoDesfazer'
import { descontar, linkInterno, naFaixa, novasQueTocam, tituloDaAba, urgenteParaAvisar } from '../lib/notificacoes'

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

// A página de notificações escuta estes eventos para refletir na hora o que o sino marcou como
// lido e o que o servidor já apagou.
export const EVENTO_LIDAS = 'mizan:notificacoes-lidas'
export const EVENTO_EXCLUIDAS = 'mizan:notificacoes-excluidas'
function avisar_(evento, detalhe) {
  try { window.dispatchEvent(new CustomEvent(evento, { detail: detalhe })) } catch { /* sem janela */ }
}
const avisarLidas = (detalhe) => avisar_(EVENTO_LIDAS, detalhe)
const SEM_OCULTAS = { itens: [], lidas: [] }      // itens: excluídas uma a uma; lidas: filtros de "Excluir as lidas"
const MAX_JUNTAS = 100                             // exclusões seguidas num pedido só (o servidor aceita até 200)

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
  // Lixeira: a notificação some na hora e só é apagada no servidor quando o "Desfazer" acaba (8 s), como no resto
  // do Mizan. Exclusões seguidas se juntam num "Desfazer" só (um toque duplo não apaga a vizinha sem volta).
  // Fechar o aviso, "Excluir as lidas", sair da conta ou fechar a aba confirmam antes.
  const [ocultas, setOcultas] = useState(SEM_OCULTAS)
  const [avisoExclusao, setAvisoExclusao] = useState(null)
  const pendente = useRef(null)          // { ids, itens } ou { lidas: filtro }, com o aviso e o token de quem excluiu
  const confirmarRef = useRef(() => Promise.resolve())
  const tokenRef = useRef(token)
  tokenRef.current = token
  const vistas = useRef(lerVistas())
  const filtroRef = useRef(filtro)
  const irParaRef = useRef(irPara)
  irParaRef.current = irPara
  const base = useRef(typeof document !== 'undefined' ? tituloDaAba(document.title, 0) : 'Mizan')

  // Com "Excluir as lidas" esperando o "Desfazer", marcar outra como lida confirma a exclusão antes e espera por
  // ela: senão a que acabou de ser lida iria junto. Sem nada esperando, devolve null e quem chama segue sem
  // `await`: assim o sino e a página mudam no mesmo instante do clique.
  const antesDeLer = useCallback(() => (pendente.current?.lidas ? confirmarRef.current() : null), [])

  const abrir = useCallback((item) => {
    setAberto(false)
    setUrgente(u => (u && u.id === item.id ? null : u))
    if (!item.lida) {
      const antes = antesDeLer()
      setEstado(s => ({
        ...s,
        itens: s.itens.map(i => (i.id === item.id ? { ...i, lida: true } : i))
          .filter(i => filtroRef.current === 'todas' || i.id !== item.id),
        naoLidas: Math.max(0, s.naoLidas - 1),
        urgentes: Math.max(0, s.urgentes - (item.prioridade === 'urgente' ? 1 : 0)),
      }))
      Promise.resolve(antes).then(() => marcarNotificacaoLida(item.id)).catch(() => {})
      avisarLidas({ ids: [item.id] })
    }
    ;(irParaRef.current || ((rota) => { window.location.assign(rota) }))(linkInterno(item.link))
  }, [antesDeLer])

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
    const espera = antesDeLer()
    if (espera) await espera
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
  }, [antesDeLer, carregar])

  const marcarTodas = useCallback(async () => {
    const espera = antesDeLer()
    if (espera) await espera
    setEstado(s => ({ ...s, naoLidas: 0, urgentes: 0,
      por_categoria: Object.fromEntries(Object.keys(s.por_categoria || {}).map(c => [c, 0])),
      itens: filtroRef.current === 'todas' ? s.itens.map(i => ({ ...i, lida: true })) : [] }))
    setOcultas(o => ({ ...o, itens: o.itens.map(i => ({ ...i, lida: true })) }))   // as escondidas também foram lidas
    setUrgente(null)
    avisarLidas({ todas: true })
    try { await marcarNotificacoesLidas() } catch (e) { setErro(e) } finally { carregar() }
  }, [antesDeLer, carregar])

  // Manda ao servidor a exclusão que esperava o "Desfazer". Ela só sai da lista quando o servidor confirma; se ele
  // recusar, volta a aparecer e o aviso diz isso. `saindo`: a aba está fechando ou a conta mudou.
  const confirmarExclusao = useCallback(async (saindo = false) => {
    const p = pendente.current
    pendente.current = null
    if (!p) return
    setAvisoExclusao(a => (a && a.id === p.aviso ? null : a))
    const tirar = () => setOcultas(o => (p.lidas ? { ...o, lidas: o.lidas.filter(f => f !== p.lidas) }
      : { ...o, itens: o.itens.filter(i => !p.ids.includes(i.id)) }))
    try {
      await excluirNotificacoes(p.lidas ? { lidas: true, ...p.lidas } : { ids: p.ids }, { saindo, token: p.token })
    } catch {
      tirar()
      // Se outra exclusão já espera o "Desfazer", o aviso dela fica; a que falhou só volta à lista.
      const falhou = { id: `falhou-${Date.now()}`, erro: true, texto: p.lidas
        ? 'Não deu para excluir as notificações lidas. Elas voltaram à lista; tente de novo.'
        : p.ids.length > 1 ? 'Não deu para excluir as notificações. Elas voltaram à lista; tente de novo.'
          : 'Não deu para excluir a notificação. Ela voltou à lista; tente de novo.' }
      if (!saindo) setAvisoExclusao(a => (a && pendente.current && a.id === pendente.current.aviso ? a : falhou))
      return
    }
    // Apagou: sai da lista e das contagens de uma vez, e a página faz o mesmo com a dela.
    const sai = p.lidas ? (i => naFaixa(i, p.lidas)) : (i => p.ids.includes(i.id))
    setEstado(s => {
      const atual = new Map(s.itens.map(i => [i.id, i]))
      return { ...s, ...descontar(s, p.lidas ? [] : p.itens.map(i => atual.get(i.id) || i)), itens: s.itens.filter(i => !sai(i)) }
    })
    tirar()
    avisar_(EVENTO_EXCLUIDAS, p.lidas ? { lidas: p.lidas } : { ids: p.ids })
    if (!saindo) carregar()
  }, [carregar])
  confirmarRef.current = confirmarExclusao

  // "Desfazer": nada foi ao servidor ainda; ela só volta a aparecer.
  const desfazerExclusao = useCallback((aviso) => {
    const p = pendente.current
    if (!p || p.aviso !== aviso) throw new Error('Essa exclusão já foi feita.')
    pendente.current = null
    setOcultas(o => (p.lidas ? { ...o, lidas: o.lidas.filter(f => f !== p.lidas) }
      : { ...o, itens: o.itens.filter(i => !p.ids.includes(i.id)) }))
  }, [])

  const excluir = useCallback((item) => {
    if (!item?.id) return
    const antes = pendente.current
    const junta = !!antes && !antes.lidas && antes.ids.length < MAX_JUNTAS
    if (!junta) confirmarRef.current()                            // "Excluir as lidas" esperando vale agora
    const outras = junta ? antes.itens.filter(i => i.id !== item.id) : []
    const itens = [...outras, item]
    const aviso = `excluir-${item.id}-${Date.now()}`
    pendente.current = { ids: itens.map(i => i.id), itens, aviso, token: tokenRef.current }
    setOcultas(o => ({ ...o, itens: [...o.itens.filter(i => i.id !== item.id), item] }))
    setUrgente(u => (u && u.id === item.id ? null : u))
    const varias = itens.length > 1
    setAvisoExclusao({ id: aviso, texto: varias ? `${itens.length} notificações excluídas.` : 'Notificação excluída.',
      desfeito: varias ? 'As notificações voltaram.' : 'A notificação voltou.', desfazer: async () => desfazerExclusao(aviso) })
  }, [desfazerExclusao])

  // "Excluir as lidas": todas as já lidas da pessoa, ou só as do assunto e da prioridade que a página filtra.
  const excluirLidas = useCallback(({ categoria, prioridade } = {}) => {
    confirmarRef.current()
    const aviso = `excluir-lidas-${Date.now()}`
    const filtroDaTela = { ...(categoria ? { categoria } : {}), ...(prioridade ? { prioridade } : {}) }
    pendente.current = { lidas: filtroDaTela, aviso, token: tokenRef.current }
    setOcultas(o => ({ ...o, lidas: [...o.lidas, filtroDaTela] }))
    setAvisoExclusao({ id: aviso, texto: 'Notificações lidas excluídas.', desfeito: 'As notificações voltaram.',
      desfazer: async () => desfazerExclusao(aviso) })
  }, [desfazerExclusao])

  // Fechando a aba, saindo da conta ou trocando de pessoa com uma exclusão esperando: ela vale.
  useEffect(() => {
    const sair = () => confirmarRef.current(true)
    window.addEventListener('pagehide', sair)
    return () => { window.removeEventListener('pagehide', sair); sair() }
  }, [token])

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
    if (!ligado) { setEstado(VAZIO); setUrgente(null); setCarregou(false); setOcultas(SEM_OCULTAS); setAvisoExclusao(null); return }
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

  // O que a lixeira escondeu não aparece em lista nenhuma (a página usa o mesmo filtro), nem conta como não lida.
  // O que já se resolveu também não: o servidor não manda mais, e isto cobre uma resposta antiga.
  const visivel = useCallback(i => !i.resolvida && !ocultas.itens.some(o => o.id === i.id)
    && !ocultas.lidas.some(f => naFaixa(i, f)), [ocultas])
  const visto = useMemo(() => {
    const atual = new Map(estado.itens.map(i => [i.id, i]))
    return { itens: estado.itens.filter(visivel), ...descontar(estado, ocultas.itens.map(i => atual.get(i.id) || i)) }
  }, [estado, ocultas, visivel])

  // "(3) Mizan" na aba do navegador (sem as que a lixeira acabou de esconder).
  useEffect(() => {
    if (typeof document === 'undefined') return
    document.title = tituloDaAba(base.current, ligado && estado.ativo ? visto.naoLidas : 0)
  }, [ligado, estado.ativo, visto.naoLidas])
  useEffect(() => () => { if (typeof document !== 'undefined') document.title = base.current }, [])

  const valor = useMemo(() => ({
    ligado, ...estado, ...visto, visivel, excluir, excluirLidas,
    carregando, carregou, erro, filtro, setFiltro, aberto, urgente, vistaInicial,
    // Só 'preferencias' muda a vista: chamado direto pelo onClick, o argumento é o evento do clique.
    abrirPainel: (vista) => { setVistaInicial(vista === 'preferencias' ? 'preferencias' : 'lista'); setAberto(true); carregar() },
    fecharPainel: () => setAberto(false),
    fecharUrgente: () => setUrgente(null), abrir, irPara: irParaRota, marcarLida, marcarTodas, carregarMais, salvarPreferencias,
    pedirPermissao, recarregar: () => carregar(),
  }), [ligado, estado, visto, visivel, excluir, excluirLidas, carregando, carregou, erro, filtro, setFiltro, aberto,
    urgente, vistaInicial, carregar, abrir, irParaRota, marcarLida, marcarTodas, carregarMais, salvarPreferencias,
    pedirPermissao])

  return (
    <Ctx.Provider value={valor}>
      {children}
      <AvisoDesfazer aviso={avisoExclusao} onFechar={() => { setAvisoExclusao(null); confirmarRef.current() }} />
    </Ctx.Provider>
  )
}

export default function useNotificacoes() {
  return useContext(Ctx)
}
