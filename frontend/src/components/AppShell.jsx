import { Component, createContext, useContext, useEffect, useState, Suspense } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useLocation, useOutlet } from 'react-router-dom'
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from 'framer-motion'
import {
  UploadCloud, KeyRound, LogOut, Loader2, Menu, X,
  Zap, Brain, Command, Lock, HelpCircle, SlidersHorizontal,
  MessageCircleQuestion, GraduationCap, KeySquare, CalendarClock, Gauge, TrendingUp, Handshake, Bot, LayoutGrid, FolderOpen,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import useAvisosDeDuvida from './useAvisosDeDuvida'
import useAvisoAgenda from './useAvisoAgenda'
import ConfirmarModal from './ConfirmarModal'
import useModal from './useModal'
import { saidaTravada, liberarSaida, confirmarVoltar } from './protecaoSaida'
import { LogoMark } from './Logo'
import FundoOndas from './FundoOndas'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { pagina, SEM_MOVIMENTO, TRANSICAO } from '../lib/motion'

/**
 * A casca da plataforma: navegação fixa à esquerda, cabeçalho em cima, e só o
 * conteúdo troca.
 *
 * `ShellLayout` é a rota-mãe de todas as telas logadas: fica montado enquanto a
 * pessoa navega, então o menu não pisca e o destaque do item ativo desliza de
 * um item para o outro. Antes cada tela montava a própria casca (e 11 delas nem
 * tinham menu: só uma seta de voltar), e a animação de página levava o menu
 * junto a cada clique.
 *
 * Cada tela escreve `<AppShell acoes>…</AppShell>`. Dentro do layout, isso só
 * põe os botões no cabeçalho (por portal) e devolve o conteúdo. O `titulo` é
 * aceito e ignorado: o nome da tela saiu do cabeçalho.
 */

const ShellCtx = createContext(null)

export default function AppShell({ acoes, children }) {
  const shell = useContext(ShellCtx)
  if (!shell) return children                        // fora do layout (não deveria acontecer)
  return (
    <>
      {acoes && shell.slotAcoes && createPortal(acoes, shell.slotAcoes)}
      {children}
    </>
  )
}

// Menu em áreas: poucos itens; cada área tem abas no topo da tela (AbasDaArea).
// As telas são as mesmas de antes; muda só onde ficam e o nome.
function useItens() {
  const { isAdmin, isComando } = useAuth()
  const { result } = useAnalysis()
  const avisos = useAvisosDeDuvida()
  const agenda = useAvisoAgenda()
  const gestor = isAdmin || isComando
  const avisoAgenda = { aviso: isComando ? 0 : agenda.alto + agenda.medio, corAviso: agenda.alto > 0 ? 'bg-red-600 text-white' : 'bg-amber-400 text-black',
    tituloAviso: agenda.alto > 0 ? `compromissos (${agenda.alto} ${agenda.alto === 1 ? 'vencido' : 'vencidos'})` : 'compromissos para hoje ou amanhã' }
  const carteira = { id: 'carteira', label: 'Carteira', icon: UploadCloud, vista: 'analise', abas: [
    ...(result ? [{ id: 'dashboard', label: 'Painel da carteira', vista: 'dashboard' }] : []),
    { id: 'analise', label: 'Análise', vista: 'analise' },
    { id: 'pagamentos', label: 'Pagamentos', rota: '/feedback' },
  ] }
  const inicio = { id: 'inicio', label: 'Início', icon: LayoutGrid, rota: '/inicio' }
  const pastas = { id: 'pastas', label: 'Pastas', icon: FolderOpen, rota: '/pastas' }
  const hoje = { id: 'hoje', label: 'Hoje', icon: CalendarClock, rota: '/agenda', ...avisoAgenda }

  const principais = gestor ? [
    inicio,
    hoje,
    carteira,
    pastas,
    { id: 'agente', label: 'Agentes', icon: Bot, rota: '/agente', prefixo: '/agente' },
    { id: 'resultados', label: 'Resultados', icon: TrendingUp, rota: '/resultados', abas: [
      { id: 'resultados', label: 'Resultados', rota: '/resultados' },
      { id: 'painel', label: 'Equipe', rota: '/painel' },
      { id: 'acordos', label: 'Acordos', rota: '/acordos' },
      ...(!isComando ? [{ id: 'ia', label: 'Performance da IA', rota: '/ia' }] : []),
      { id: 'laboratorio', label: 'Laboratório', rota: '/laboratorio' },
    ] },
    { id: 'config', label: 'Configurações', icon: SlidersHorizontal, rota: '/ofertas', abas: [
      { id: 'ofertas', label: 'Ofertas', rota: '/ofertas' },
      { id: 'premissas', label: 'Política de cobrança', rota: '/premissas' },
      { id: 'usuarios', label: 'Usuários', rota: '/admin/usuarios' },
      { id: 'auditoria', label: 'Auditoria', rota: '/auditoria' },
      { id: 'backtest', label: 'Simulação histórica', rota: '/backtest' },
    ] },
  ] : [
    inicio,
    hoje,
    carteira,
    pastas,
    { id: 'acordos', label: 'Meus acordos', icon: Handshake, rota: '/acordos' },
    { id: 'painel', label: 'Meu painel', icon: Gauge, rota: '/painel' },
    { id: 'ia', label: 'Performance da IA', icon: Brain, rota: '/ia' },
  ]

  return [
    { nome: '', itens: principais },
    ...(isComando ? [{
      nome: 'Plataforma',
      itens: [
        { id: 'comando',     label: 'Comando',          icon: Command,        rota: '/comando' },
        { id: 'aprendizado', label: 'Aprendizado',      icon: Brain,          rota: '/aprendizado' },
        { id: 'treino',      label: 'Treinar modelo',   icon: GraduationCap,  rota: '/comando/treino' },
        { id: 'bandit',      label: 'Performance IA',   icon: Zap,            rota: '/bandit' },
        { id: 'chaves',      label: 'Chaves de API',    icon: KeySquare,      rota: '/comando/chaves' },
        { id: 'retencao',    label: 'Retenção',         icon: Lock,           rota: '/retencao' },
        { id: 'duvidas',     label: 'Dúvidas',          icon: MessageCircleQuestion, rota: '/comando/duvidas',
          aviso: avisos.abertas, tituloAviso: 'dúvidas abertas' },
      ],
    }] : []),
    {
      nome: 'Conta',
      itens: [
        { id: 'ajuda', label: 'Ajuda', icon: HelpCircle, rota: '/ajuda', aviso: avisos.respostas, tituloAviso: 'respostas novas' },
        { id: 'senha', label: 'Alterar senha', icon: KeyRound, rota: '/alterar-senha' },
      ],
    },
  ]
}

// Abas da área no topo da tela (ex.: Resultados · Equipe · Acordos).
function AbasDaArea({ item, ativoExato, acionar }) {
  if (!item?.abas || item.abas.length < 2) return null
  return (
    <div className="mb-6 flex flex-wrap gap-1 border-b border-line" role="tablist" aria-label={item.label}>
      {item.abas.map(aba => {
        const on = ativoExato(aba)
        return (
          <button key={aba.id} role="tab" aria-selected={on} onClick={() => acionar(aba)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              on ? 'border-blue-500 text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>
            {aba.label}
          </button>
        )
      })}
    </div>
  )
}

function Navegacao({ grupos, ativo, acionar, sair, idDestaque }) {
  return (
    <LayoutGroup id={idDestaque}>
      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Navegação principal">
        {grupos.map(g => (
          <div key={g.nome || 'principal'}>
            {g.nome && <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-3">{g.nome}</p>}
            <div className="flex flex-col gap-0.5">
              {g.itens.map(it => {
                const Icon = it.icon
                const on = ativo(it)
                return (
                  <button key={it.id} onClick={() => acionar(it)} aria-current={on ? 'page' : undefined}
                    className={`relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                      on ? 'text-ink' : 'text-ink-2 hover:bg-raise-1 hover:text-ink'}`}>
                    {/* O destaque é um só e desliza até o item ativo. */}
                    {on && (
                      <motion.span layoutId="destaque" className="absolute inset-0 rounded-lg bg-raise-2"
                        transition={{ type: 'spring', stiffness: 520, damping: 40 }}>
                        <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-blue-500" />
                      </motion.span>
                    )}
                    <Icon className={`relative h-[18px] w-[18px] shrink-0 ${on ? 'text-blue-400' : ''}`} />
                    <span className="relative truncate">{it.label}</span>
                    {it.aviso > 0 && (
                      <span className={`relative ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full ${it.corAviso || 'bg-[var(--royal)] text-[var(--on-brand)]'} px-1.5 text-[11px] font-semibold leading-5`}
                        aria-label={`${it.aviso} ${it.tituloAviso}`}>{it.aviso > 99 ? '99+' : it.aviso}</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-line p-3">
        <button onClick={sair}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-ink-2 transition-colors hover:bg-red-500/10 hover:text-red-400">
          <LogOut className="h-[18px] w-[18px]" /> Sair
        </button>
      </div>
    </LayoutGroup>
  )
}

// Erro numa tela fica na tela: o menu continua de pé para a pessoa sair dali.
// (O ErrorBoundary de App.jsx pegava tudo e derrubava o app inteiro.)
class ErroNaTela extends Component {
  state = { erro: null }
  static getDerivedStateFromError(erro) { return { erro } }
  render() {
    if (!this.state.erro) return this.props.children
    return (
      <div className="mx-auto max-w-lg py-16 text-center" role="alert">
        <p className="text-lg font-semibold text-ink">Algo deu errado nesta tela.</p>
        <p className="mt-2 break-all rounded-xl border border-line bg-raise-3 px-4 py-2 text-sm text-ink-2">
          {this.state.erro?.message || String(this.state.erro)}
        </p>
        <p className="mt-3 text-sm text-ink-2">Use o menu para ir a outra tela, ou recarregue a página.</p>
        <button onClick={() => window.location.reload()} className="btn-primary mt-4">Recarregar</button>
      </div>
    )
  }
}

function Carregando() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" role="status" aria-live="polite">
      <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      <span className="sr-only">Carregando…</span>
    </div>
  )
}

export function ShellLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const outlet = useOutlet()
  const reduzir = useReducedMotion()
  const { usuario, logout, empresaConfig } = useAuth()
  const { vista, setVista, result } = useAnalysis()
  const grupos = useItens()
  const [gaveta, setGaveta] = useState(false)
  const [slotAcoes, setSlotAcoes] = useState(null)
  const [saidaPendente, setSaidaPendente] = useState(null)   // ação de navegar à espera da confirmação
  // Botão "voltar" do navegador numa tela com alterações não salvas.
  useEffect(() => {
    const aoBloquear = () => {
      const trava = saidaTravada()
      if (trava) setSaidaPendente({ mensagem: trava.mensagem, voltar: true, ir: confirmarVoltar })
    }
    window.addEventListener('mizan:voltar-bloqueado', aoBloquear)
    return () => window.removeEventListener('mizan:voltar-bloqueado', aoBloquear)
  }, [])

  const nomeEmpresa = empresaConfig?.nome_exibicao || 'Mizan'
  const nomeUser = usuario?.nome || 'Operador'
  const iniciais = nomeUser.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  // Na tela inicial, a vista (análise ou dashboard) é o que está na tela.
  const vistaAtual = (vista === 'dashboard' && !result) ? 'analise' : (vista ?? (result ? 'dashboard' : 'analise'))
  const ativoExato = it => it.vista ? (pathname === '/' && vistaAtual === it.vista) : pathname === it.rota
  // Item do menu fica aceso em qualquer aba da área dele.
  const ativo = it => ativoExato(it) || (it.prefixo && pathname.startsWith(it.prefixo))
    || (it.abas || []).some(ativoExato) || (it.vista && pathname === '/')
  const areaAtual = grupos.flatMap(g => g.itens).find(ativo)

  function acionar(it) {
    setGaveta(false)
    // Tela com alterações não salvas: pergunta antes de sair.
    const trava = saidaTravada()
    if (trava && !ativo(it)) { setSaidaPendente({ mensagem: trava.mensagem, ir: () => irPara(it) }); return }
    irPara(it)
  }
  function irPara(it) {
    if (it.vista) {
      // Antes, fora da tela inicial, isto só trocava a vista e nada acontecia na tela.
      setVista(it.vista)
      if (pathname !== '/') navigate('/')
    } else navigate(it.rota)
  }
  function sair() {
    setGaveta(false)
    const trava = saidaTravada()
    const efetivar = () => { logout(); navigate('/login') }
    if (trava) { setSaidaPendente({ mensagem: trava.mensagem, ir: efetivar }); return }
    efetivar()
  }

  // Fecha a gaveta ao trocar de tela; com ela aberta, Esc fecha e o foco fica preso
  // nela (mesmo comportamento dos demais modais) e volta ao botão do menu.
  useEffect(() => { setGaveta(false) }, [pathname])
  const caixaGaveta = useModal(gaveta, () => setGaveta(false))

  const marca = empresaConfig?.foto_url
    ? <img src={empresaConfig.foto_url} alt={nomeEmpresa} className="h-8 w-8 rounded object-cover" />
    : <LogoMark size={26} />
  const cabecaDoMenu = (
    <div className="flex h-16 shrink-0 items-center gap-2.5 px-5">
      {marca}
      <span className="truncate text-[15px] font-bold tracking-tight text-ink">{nomeEmpresa}</span>
    </div>
  )
  const chave = pathname
  const variantes = reduzir ? SEM_MOVIMENTO : pagina

  return (
    <ShellCtx.Provider value={{ slotAcoes }}>
      <div className="relative isolate flex min-h-screen bg-surface-2 font-sans text-ink">
        <FundoOndas />

        {/* Menu em gaveta em todas as telas: abre pelo botão ☰ e não ocupa espaço. */}

        {/* ───── Gaveta (celular) ───── */}
        <AnimatePresence>
          {gaveta && (
            <>
              <motion.div key="fundo" className="fixed inset-0 z-40 bg-black/50"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
                onClick={() => setGaveta(false)} aria-hidden="true" />
              <motion.aside ref={caixaGaveta} key="gaveta" role="dialog" aria-modal="true" aria-label="Menu"
                className="panel-surface fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r"
                initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
                transition={reduzir ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 42 }}>
                <div className="flex items-center justify-between pr-3">
                  {cabecaDoMenu}
                  <button onClick={() => setGaveta(false)} aria-label="Fechar menu"
                    className="rounded-lg p-2 text-ink-2 hover:bg-raise-2"><X className="h-5 w-5" /></button>
                </div>
                <Navegacao grupos={grupos} ativo={ativo} acionar={acionar} sair={sair} idDestaque="gaveta" />
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        {/* ───── Coluna principal ───── */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="navbar-glass sticky top-0 z-20 flex h-16 items-center justify-between gap-3 px-4 md:px-8">
            <div className="flex min-w-0 items-center gap-2 text-sm">
              <button onClick={() => setGaveta(true)} aria-label="Abrir menu" aria-expanded={gaveta}
                className="-ml-1 rounded-lg p-2 text-ink-2 hover:bg-raise-2"><Menu className="h-5 w-5" /></button>
              {/* Sem o nome da tela aqui: o menu já marca onde a pessoa está, e cada
                  tela tem o próprio título. */}
              <button onClick={() => acionar({ id: 'inicio', rota: '/inicio' })} title="Ir para o início"
                className="truncate rounded-md px-1 font-semibold text-ink hover:text-[var(--royal)]">{nomeEmpresa}</button>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span ref={setSlotAcoes} className="flex items-center gap-2" />
              <ThemeToggle />
              <div className="ml-1 flex items-center gap-2.5 border-l border-line pl-3">
                <div className="hidden text-right lg:block">
                  <p className="text-sm font-medium leading-tight text-ink">{nomeUser}</p>
                  <p className="text-xs font-light text-ink-2">{usuario?.email || ''}</p>
                </div>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--royal)] text-xs font-bold text-brand-ink" aria-hidden="true">
                  {iniciais}
                </div>
              </div>
            </div>
          </header>

          <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
            {/* Só o conteúdo anima: o menu e o cabeçalho ficam parados. */}
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={chave} variants={variantes} initial="inicial" animate="entra" exit="sai"
                transition={TRANSICAO}>
                <AbasDaArea item={areaAtual} ativoExato={ativoExato} acionar={acionar} />
                <ErroNaTela key={chave}><Suspense fallback={<Carregando />}>{outlet}</Suspense></ErroNaTela>
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
      <ConfirmarModal aberto={!!saidaPendente} titulo={saidaPendente?.mensagem}
        texto="O que não foi salvo nesta tela será perdido."
        cancelar="Continuar editando" confirmar="Sair sem salvar" perigo
        onCancelar={() => setSaidaPendente(null)}
        onConfirmar={() => { const ir = saidaPendente.ir; if (!saidaPendente.voltar) liberarSaida(); setSaidaPendente(null); ir() }} />
    </ShellCtx.Provider>
  )
}
