import { Component, createContext, useContext, useEffect, useState, Suspense } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useLocation, useOutlet } from 'react-router-dom'
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from 'framer-motion'
import {
  LayoutDashboard, UploadCloud, ClipboardList, Users, KeyRound, LogOut, Loader2, Menu, X,
  ShieldCheck, Zap, Brain, Command, FlaskConical, Lock, HelpCircle, SlidersHorizontal,
  MessageCircleQuestion, GraduationCap, KeySquare,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import useAvisosDeDuvida from './useAvisosDeDuvida'
import { LogoMark } from './Logo'
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
 * Cada tela continua escrevendo `<AppShell titulo acoes>…</AppShell>`. Dentro
 * do layout, isso só põe o título e os botões no cabeçalho (por portal) e
 * devolve o conteúdo.
 */

const ShellCtx = createContext(null)

export default function AppShell({ titulo, acoes, children }) {
  const shell = useContext(ShellCtx)
  if (!shell) return children                        // fora do layout (não deveria acontecer)
  return (
    <>
      {titulo && shell.slotTitulo && createPortal(titulo, shell.slotTitulo)}
      {acoes && shell.slotAcoes && createPortal(acoes, shell.slotAcoes)}
      {children}
    </>
  )
}

function useItens() {
  const { isAdmin, isComando } = useAuth()
  const { result } = useAnalysis()
  const avisos = useAvisosDeDuvida()
  const grupos = [
    {
      nome: 'Trabalho',
      itens: [
        ...(result ? [{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, vista: 'dashboard' }] : []),
        { id: 'analise', label: 'Análise de carteira', icon: UploadCloud, vista: 'analise' },
        { id: 'pagamentos', label: 'Pagamentos', icon: ClipboardList, rota: '/feedback' },
      ],
    },
    ...((isAdmin || isComando) ? [{
      nome: 'Gestão',
      itens: [
        { id: 'premissas', label: 'Premissas', icon: SlidersHorizontal, rota: '/premissas' },
        { id: 'backtest',  label: 'Backtest',  icon: FlaskConical,      rota: '/backtest' },
        { id: 'usuarios',  label: 'Usuários',  icon: Users,             rota: '/admin/usuarios' },
        { id: 'auditoria', label: 'Auditoria', icon: ShieldCheck,       rota: '/auditoria' },
        { id: 'retencao',  label: 'Retenção',  icon: Lock,              rota: '/retencao' },
      ],
    }] : []),
    ...(isComando ? [{
      nome: 'Plataforma',
      itens: [
        { id: 'comando',     label: 'Comando',          icon: Command,        rota: '/comando' },
        { id: 'aprendizado', label: 'Aprendizado',      icon: Brain,          rota: '/aprendizado' },
        { id: 'treino',      label: 'Treinar modelo',   icon: GraduationCap,  rota: '/comando/treino' },
        { id: 'bandit',      label: 'Performance IA',   icon: Zap,            rota: '/bandit' },
        { id: 'chaves',      label: 'Chaves de API',    icon: KeySquare,      rota: '/comando/chaves' },
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
  return grupos
}

function Navegacao({ grupos, ativo, acionar, sair, idDestaque }) {
  return (
    <LayoutGroup id={idDestaque}>
      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Navegação principal">
        {grupos.map(g => (
          <div key={g.nome}>
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-3">{g.nome}</p>
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
                      <span className="relative ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-blue-600 px-1.5 text-[11px] font-semibold leading-5 text-white"
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
  const [slotTitulo, setSlotTitulo] = useState(null)
  const [slotAcoes, setSlotAcoes] = useState(null)

  const nomeEmpresa = empresaConfig?.nome_exibicao || 'Mizan'
  const nomeUser = usuario?.nome || 'Operador'
  const iniciais = nomeUser.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  // Na tela inicial, a vista (análise ou dashboard) é o que está na tela.
  const vistaAtual = (vista === 'dashboard' && !result) ? 'analise' : (vista ?? (result ? 'dashboard' : 'analise'))
  const ativo = it => it.vista ? (pathname === '/' && vistaAtual === it.vista) : pathname === it.rota

  function acionar(it) {
    setGaveta(false)
    if (it.vista) {
      // Antes, fora da tela inicial, isto só trocava a vista e nada acontecia na tela.
      setVista(it.vista)
      if (pathname !== '/') navigate('/')
    } else navigate(it.rota)
  }
  function sair() { setGaveta(false); logout(); navigate('/login') }

  // Fecha a gaveta com Esc e ao trocar de tela.
  useEffect(() => { setGaveta(false) }, [pathname])
  useEffect(() => {
    if (!gaveta) return
    const fechar = e => { if (e.key === 'Escape') setGaveta(false) }
    window.addEventListener('keydown', fechar)
    return () => window.removeEventListener('keydown', fechar)
  }, [gaveta])

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
    <ShellCtx.Provider value={{ slotTitulo, slotAcoes }}>
      <div className="flex min-h-screen bg-surface-2 font-sans text-ink">

        {/* ───── Menu fixo (telas médias para cima) ───── */}
        <aside className="panel-surface fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r md:flex">
          {cabecaDoMenu}
          <Navegacao grupos={grupos} ativo={ativo} acionar={acionar} sair={sair} idDestaque="lateral" />
        </aside>

        {/* ───── Gaveta (celular) ───── */}
        <AnimatePresence>
          {gaveta && (
            <>
              <motion.div key="fundo" className="fixed inset-0 z-40 bg-black/50 md:hidden"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
                onClick={() => setGaveta(false)} aria-hidden="true" />
              <motion.aside key="gaveta" role="dialog" aria-modal="true" aria-label="Menu"
                className="panel-surface fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r md:hidden"
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
        <div className="flex min-w-0 flex-1 flex-col md:pl-60">
          <header className="navbar-glass sticky top-0 z-20 flex h-16 items-center justify-between gap-3 px-4 md:px-8">
            <div className="flex min-w-0 items-center gap-2 text-sm">
              <button onClick={() => setGaveta(true)} aria-label="Abrir menu" aria-expanded={gaveta}
                className="-ml-1 rounded-lg p-2 text-ink-2 hover:bg-raise-2 md:hidden"><Menu className="h-5 w-5" /></button>
              <span className="hidden truncate font-semibold text-ink sm:inline md:inline">{nomeEmpresa}</span>
              <span className="hidden text-ink-4 sm:inline">/</span>
              <span ref={setSlotTitulo} className="min-w-0 truncate font-medium text-ink-2" />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span ref={setSlotAcoes} className="flex items-center gap-2" />
              <ThemeToggle />
              <div className="ml-1 flex items-center gap-2.5 border-l border-line pl-3">
                <div className="hidden text-right lg:block">
                  <p className="text-sm font-medium leading-tight text-ink">{nomeUser}</p>
                  <p className="text-xs font-light text-ink-2">{usuario?.email || ''}</p>
                </div>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-brand-ink" aria-hidden="true">
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
                <ErroNaTela key={chave}><Suspense fallback={<Carregando />}>{outlet}</Suspense></ErroNaTela>
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
    </ShellCtx.Provider>
  )
}
