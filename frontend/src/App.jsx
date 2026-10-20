import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState, Component, lazy, Suspense } from 'react'
import { Loader2 } from 'lucide-react'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import PageTransition from './components/PageTransition'
import { ShellLayout } from './components/AppShell'
import { AVISO_CONECTANDO } from './api'

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(e) { return { error: e } }
  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info?.componentStack)
  }
  render() {
    if (!this.state.error) return this.props.children
    const detalhe = this.state.error?.message || String(this.state.error)
    return (
      <div role="alert" className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center">
        <p className="text-ink text-lg font-semibold">Algo deu errado nesta página.</p>
        <p className="text-ink-2 text-sm max-w-md">Recarregue a página. Se continuar, avise o suporte.</p>
        <button type="button" onClick={() => window.location.reload()} className="btn-primary mt-2">
          Recarregar página
        </button>
        <details className="text-ink-3 text-xs max-w-lg">
          <summary className="cursor-pointer">Detalhe técnico</summary>
          <p className="mt-2 tabular-nums bg-raise-3 border border-line px-4 py-2 rounded-xl break-all">{detalhe}</p>
        </details>
      </div>
    )
  }
}

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

// Pergunta ao /health com prazo. Sem AbortSignal.timeout (não existe em
// navegadores antigos) e sem erro solto: falha de rede só encerra o aviso.
function pingarServidor(prazoMs) {
  const ctrl = typeof AbortController === 'function' ? new AbortController() : null
  const t = ctrl ? setTimeout(() => ctrl.abort(), prazoMs) : null
  return fetch(`${BASE}/health`, ctrl ? { signal: ctrl.signal } : undefined)
    .catch(() => {})
    .finally(() => { if (t) clearTimeout(t) })
}

function ServerWarmupBanner() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => { if (!cancelled) setShow(true) }, 4000)
    pingarServidor(90000).finally(() => { clearTimeout(timer); if (!cancelled) setShow(false) })
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  // Pinga /health a cada 8 min enquanto a aba está visível, para o Render
  // (plano grátis) não hibernar durante o uso.
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) pingarServidor(30000) }, 8 * 60 * 1000)
    return () => clearInterval(id)
  }, [])

  if (!show) return null
  return (
    <div role="status" className="fixed top-0 inset-x-0 z-50 px-4 py-2.5 flex items-center justify-center gap-3 text-sm"
      style={{ color: 'var(--ink)', background: 'rgb(var(--c-warning) / 0.10)', borderBottom: '1px solid rgb(var(--c-warning) / 0.20)', backdropFilter: 'blur(8px)' }}>
      <Loader2 className="h-4 w-4 animate-spin shrink-0" style={{ color: 'var(--warning)' }} aria-hidden="true" />
      <span>{AVISO_CONECTANDO}</span>
    </div>
  )
}

// Cada página vira um chunk próprio: o navegador baixa só a tela que o
// usuário abriu, em vez de todo o sistema no primeiro acesso. Recharts,
// xlsx e jspdf saem do caminho crítico junto com as telas que os usam.
const Home = lazy(() => import('./pages/Home'))
const Inicio = lazy(() => import('./pages/Inicio'))
const PastasDevedores = lazy(() => import('./pages/PastasDevedores'))
const DebtorDetail = lazy(() => import('./pages/DebtorDetail'))
const Feedback = lazy(() => import('./pages/Feedback'))
const BanditDashboard = lazy(() => import('./pages/BanditDashboard'))
const AprendizadoDashboard = lazy(() => import('./pages/AprendizadoDashboard'))
const ComandoDashboard = lazy(() => import('./pages/ComandoDashboard'))
const AdminUsuarios = lazy(() => import('./pages/AdminUsuarios'))
const Auditoria = lazy(() => import('./pages/Auditoria'))
const AlterarSenha = lazy(() => import('./pages/AlterarSenha'))
const EsqueciSenha = lazy(() => import('./pages/EsqueciSenha'))
const RedefinirSenha = lazy(() => import('./pages/RedefinirSenha'))
const Login = lazy(() => import('./pages/Login'))
const Privacidade = lazy(() => import('./pages/Privacidade'))
const Backtest = lazy(() => import('./pages/Backtest'))
const PerformanceIA = lazy(() => import('./pages/PerformanceIA'))
const Agenda = lazy(() => import('./pages/Agenda'))
const PainelOperador = lazy(() => import('./pages/PainelOperador'))
const Resultados = lazy(() => import('./pages/Resultados'))
const Acordos = lazy(() => import('./pages/Acordos'))
const Ofertas = lazy(() => import('./pages/Ofertas'))
const Retencao = lazy(() => import('./pages/Retencao'))
const TreinoModelo = lazy(() => import('./pages/TreinoModelo'))
const ChavesApi = lazy(() => import('./pages/ChavesApi'))
const Ajuda = lazy(() => import('./pages/Ajuda'))
const Premissas = lazy(() => import('./pages/Premissas'))
const DuvidasComando = lazy(() => import('./pages/DuvidasComando'))
const Agente = lazy(() => import('./pages/Agente'))
const AgentePerfil = lazy(() => import('./pages/AgentePerfil'))
const LaboratorioPagina = lazy(() => import('./pages/LaboratorioPagina'))

function RotaProtegida({ children, roles }) {
  const { autenticado, usuario } = useAuth()
  const location = useLocation()
  if (!autenticado) return <Navigate to="/login" state={{ from: location }} replace />
  if (roles && !roles.includes(usuario?.role)) return <Navigate to="/inicio" replace />
  return children
}

// Aparece enquanto o chunk da página está sendo baixado. Discreto de
// propósito: em conexão normal isso dura poucas centenas de milissegundos e
// um spinner grande piscando ficaria pior do que o vazio.
function TelaCarregando() {
  return (
    <div className="min-h-screen flex items-center justify-center" role="status" aria-live="polite">
      <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      <span className="sr-only">Carregando página…</span>
    </div>
  )
}

// Atalho para rota com papéis: função comum (não componente).
const P = (roles, el) => <RotaProtegida roles={roles}>{el}</RotaProtegida>

function RotasAnimadas() {
  const location = useLocation()
  return (
    <Suspense fallback={<TelaCarregando />}>
      <Routes location={location}>
        <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
        <Route path="/esqueci-senha" element={<PageTransition><EsqueciSenha /></PageTransition>} />
        <Route path="/redefinir-senha" element={<PageTransition><RedefinirSenha /></PageTransition>} />
        <Route path="/privacidade" element={<PageTransition><Privacidade /></PageTransition>} />
        {/* Todas as telas logadas dentro de um layout só: o menu fica montado e
            só o conteúdo troca (ver components/AppShell.jsx). A análise de
            carteira e o dashboard são vistas de "/", não rotas; "/dashboard"
            ficou de links salvos e cai na regra coringa. */}
        <Route element={<RotaProtegida><ShellLayout /></RotaProtegida>}>
          <Route path="/inicio" element={<Inicio />} />
          <Route path="/pastas" element={P(['operador', 'admin', 'comando'], <PastasDevedores />)} />
          <Route path="/" element={<Home />} />
          <Route path="/devedor/:rank" element={<DebtorDetail />} />
          <Route path="/ajuda" element={<Ajuda />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="/alterar-senha" element={<AlterarSenha />} />
          <Route path="/bandit" element={P(['comando'], <BanditDashboard />)} />
          <Route path="/aprendizado" element={P(['comando'], <AprendizadoDashboard />)} />
          <Route path="/comando/duvidas" element={P(['comando'], <DuvidasComando />)} />
          <Route path="/comando/treino" element={P(['comando'], <TreinoModelo />)} />
          <Route path="/comando/chaves" element={P(['comando'], <ChavesApi />)} />
          <Route path="/comando" element={P(['comando'], <ComandoDashboard />)} />
          <Route path="/admin/usuarios" element={P(['admin', 'comando'], <AdminUsuarios />)} />
          <Route path="/painel" element={P(['operador', 'admin', 'comando'], <PainelOperador />)} />
          <Route path="/ofertas" element={P(['admin', 'comando'], <Ofertas />)} />
          <Route path="/agente" element={P(['admin', 'comando'], <Agente />)} />
          <Route path="/agente/:nome" element={P(['admin', 'comando'], <AgentePerfil />)} />
          <Route path="/laboratorio" element={P(['admin', 'comando'], <LaboratorioPagina />)} />
          <Route path="/acordos" element={P(['operador', 'admin', 'comando'], <Acordos />)} />
          <Route path="/resultados" element={P(['admin', 'comando'], <Resultados />)} />
          <Route path="/roteiros" element={<Navigate to="/feedback?secao=roteiros" replace />} />
          <Route path="/agenda" element={P(['operador', 'admin', 'comando'], <Agenda />)} />
          <Route path="/backtest" element={P(['admin', 'comando'], <Backtest />)} />
          <Route path="/premissas" element={P(['admin', 'comando'], <Premissas />)} />
          <Route path="/retencao" element={P(['comando'], <Retencao />)} />
          <Route path="/auditoria" element={P(['admin', 'comando'], <Auditoria />)} />
          <Route path="/ia" element={P(['operador', 'admin', 'comando'], <PerformanceIA />)} />
        </Route>
        <Route path="*" element={<Navigate to="/inicio" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
    <ThemeProvider>
      <AuthProvider>
      <AnalysisProvider>
        <ServerWarmupBanner />
        <BrowserRouter>
          <RotasAnimadas />
        </BrowserRouter>
      </AnalysisProvider>
      </AuthProvider>
    </ThemeProvider>
    </ErrorBoundary>
  )
}
