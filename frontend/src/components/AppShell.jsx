import { useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, UploadCloud, ClipboardList, Users, KeyRound, LogOut,
  ShieldCheck, Zap, Brain, Command, FlaskConical,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import { LogoMark } from './Logo'
import { useAuth } from '../context/AuthContext'

/**
 * A casca da plataforma: uma tela só, com os cartões de navegação à esquerda.
 *
 * Antes cada função morava numa página inteira e o usuário pulava de tela em
 * tela — menu do admin, tela de upload, dashboard. Agora a navegação é fixa e
 * só o conteúdo troca: quem entra sem carteira cai em "Análise de carteira" e,
 * assim que a carteira carrega, o dashboard aparece no mesmo lugar.
 *
 * `secao` diz qual item está ativo entre as vistas internas ("dashboard",
 * "analise"). Os itens que ainda levam a rotas próprias marcam sozinhos pelo
 * caminho atual.
 */
export default function AppShell({ secao, onIrPara, titulo, acoes, temResultado = false, children }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { usuario, logout, isAdmin, isComando, empresaConfig } = useAuth()

  const nomeEmpresa = empresaConfig?.nome_exibicao || 'Mizan'
  const nomeUser    = usuario?.nome || 'Operador'
  const iniciais    = nomeUser.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  // Vista interna (troca o conteúdo sem sair da página) ou rota (tela própria
  // que ainda não foi trazida para dentro da casca).
  const itens = [
    ...(temResultado
      ? [{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, vista: 'dashboard' }]
      : []),
    { id: 'analise', label: 'Análise de carteira', icon: UploadCloud, vista: 'analise' },
    { id: 'pagamentos', label: 'Pagamentos', icon: ClipboardList, rota: '/feedback' },
    ...((isAdmin || isComando) ? [
      { id: 'backtest', label: 'Backtest',  icon: FlaskConical, rota: '/backtest' },
      { id: 'usuarios', label: 'Usuários',  icon: Users,        rota: '/admin/usuarios' },
      { id: 'auditoria', label: 'Auditoria', icon: ShieldCheck, rota: '/auditoria' },
    ] : []),
    ...(isComando ? [
      { id: 'comando',     label: 'Comando',       icon: Command, rota: '/comando' },
      { id: 'bandit',      label: 'Performance IA', icon: Zap,    rota: '/bandit' },
      { id: 'aprendizado', label: 'Aprendizado',   icon: Brain,   rota: '/aprendizado' },
    ] : []),
    { id: 'senha', label: 'Alterar senha', icon: KeyRound, rota: '/alterar-senha' },
  ]

  function ativo(it) {
    return it.vista ? secao === it.vista : pathname === it.rota
  }

  function acionar(it) {
    if (it.vista) onIrPara?.(it.vista)
    else navigate(it.rota)
  }

  const marca = empresaConfig?.foto_url
    ? <img src={empresaConfig.foto_url} alt={nomeEmpresa} className="h-8 w-8 rounded object-cover" />
    : <LogoMark size={26} />

  return (
    <div className="flex min-h-screen bg-surface-2 font-sans text-ink">

      {/* ───── Navegação à esquerda (telas médias para cima) ───── */}
      <aside className="panel-surface fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r md:flex">
        <div className="flex h-16 items-center gap-2.5 px-5">
          {marca}
          <span className="truncate text-[15px] font-bold tracking-tight text-ink">{nomeEmpresa}</span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-4">
          {itens.map((it) => {
            const Icon = it.icon
            const on = ativo(it)
            return (
              <button
                key={it.id}
                onClick={() => acionar(it)}
                aria-current={on ? 'page' : undefined}
                className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                  on ? 'bg-raise-2 text-ink' : 'text-ink-2 hover:bg-raise-1 hover:text-ink'
                }`}
              >
                {on && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-blue-500" />}
                <Icon className={`h-[18px] w-[18px] ${on ? 'text-blue-400' : ''}`} />
                {it.label}
              </button>
            )
          })}
        </nav>

        <div className="border-t border-line p-3">
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-2 transition-colors hover:bg-red-500/10 hover:text-red-400"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Sair
          </button>
        </div>
      </aside>

      {/* ───── Coluna principal ───── */}
      <div className="flex min-w-0 flex-1 flex-col md:pl-60">

        <header className="navbar-glass flex h-16 items-center justify-between gap-3 px-4 md:px-8">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="md:hidden">{marca}</span>
            <span className="truncate font-semibold text-ink">{nomeEmpresa}</span>
            {titulo && <>
              <span className="text-ink-4">/</span>
              <span className="hidden truncate font-light text-ink-2 sm:inline">{titulo}</span>
            </>}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {acoes}
            <ThemeToggle />
            <div className="ml-2 flex items-center gap-2.5 border-l border-line pl-4">
              <div className="hidden text-right lg:block">
                <p className="text-sm font-medium leading-tight text-ink">{nomeUser}</p>
                <p className="text-xs font-light text-ink-2">{usuario?.email || ''}</p>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-brand-ink">
                {iniciais}
              </div>
            </div>
          </div>
        </header>

        {/* No celular a mesma navegação vira uma faixa rolável: os itens são os
            mesmos, só deitados, porque uma coluna de 240px não cabe. */}
        <nav className="flex min-w-0 gap-1 overflow-x-auto border-b border-line bg-surface px-3 py-2 md:hidden">
          {itens.map((it) => {
            const Icon = it.icon
            const on = ativo(it)
            return (
              <button
                key={it.id}
                onClick={() => acionar(it)}
                aria-current={on ? 'page' : undefined}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  on ? 'bg-raise-2 text-ink' : 'text-ink-2'
                }`}
              >
                <Icon className={`h-4 w-4 ${on ? 'text-blue-400' : ''}`} />
                {it.label}
              </button>
            )
          })}
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-ink-2"
          >
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </nav>

        <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  )
}
