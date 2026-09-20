import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState, Component } from 'react'
import { Loader2 } from 'lucide-react'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { AnimatePresence } from 'framer-motion'
import PageTransition from './components/PageTransition'

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center">
        <p className="text-ink text-lg font-semibold">Algo deu errado nesta página.</p>
        <p className="text-ink-2 text-sm tabular-nums bg-raise-3 border border-line px-4 py-2 rounded-xl max-w-lg break-all">
          {this.state.error?.message || String(this.state.error)}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="btn-primary mt-2"
        >
          Recarregar página
        </button>
      </div>
    )
  }
}

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function ServerWarmupBanner() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => { if (!cancelled) setShow(true) }, 4000)
    fetch(`${BASE}/health`, { signal: AbortSignal.timeout(90000) })
      .finally(() => { clearTimeout(timer); if (!cancelled) setShow(false) })
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  // Keepalive: pinga /health a cada 8 min enquanto a aba está visível
  // Impede que o Render (free tier) hiberne durante uso ativo da plataforma
  useEffect(() => {
    const INTERVALO = 8 * 60 * 1000
    let id = null
    function ping() {
      if (!document.hidden) fetch(`${BASE}/health`).catch(() => {})
    }
    id = setInterval(ping, INTERVALO)
    return () => clearInterval(id)
  }, [])

  if (!show) return null
  return (
    <div className="fixed top-0 inset-x-0 z-50 px-4 py-2.5 flex items-center justify-center gap-3 text-sm text-amber-400"
      style={{ background: 'rgb(var(--c-warning) / 0.10)', borderBottom: '1px solid rgb(var(--c-warning) / 0.20)', backdropFilter: 'blur(8px)' }}>
      <Loader2 className="h-4 w-4 animate-spin text-amber-400 shrink-0" />
      <span>O servidor está acordando — a primeira requisição pode levar até 30s (plano gratuito).</span>
    </div>
  )
}

import Upload from './pages/Upload'
import Dashboard from './pages/Dashboard'
import DebtorDetail from './pages/DebtorDetail'
import Feedback from './pages/Feedback'
import BanditDashboard from './pages/BanditDashboard'
import AprendizadoDashboard from './pages/AprendizadoDashboard'
import ComandoDashboard from './pages/ComandoDashboard'
import AdminHome from './pages/AdminHome'
import OperadorHome from './pages/OperadorHome'
import AdminUsuarios from './pages/AdminUsuarios'
import Auditoria from './pages/Auditoria'
import AlterarSenha from './pages/AlterarSenha'
import EsqueciSenha from './pages/EsqueciSenha'
import RedefinirSenha from './pages/RedefinirSenha'
import Login from './pages/Login'
import Privacidade from './pages/Privacidade'

function RotaProtegida({ children, roles }) {
  const { autenticado, usuario } = useAuth()
  const location = useLocation()
  if (!autenticado) return <Navigate to="/login" state={{ from: location }} replace />
  if (roles && !roles.includes(usuario?.role)) return <Navigate to="/" replace />
  return children
}

function RotasAnimadas() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait" initial={false}>
          <Routes location={location} key={location.pathname}>
            <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
            <Route path="/esqueci-senha" element={<PageTransition><EsqueciSenha /></PageTransition>} />
            <Route path="/redefinir-senha" element={<PageTransition><RedefinirSenha /></PageTransition>} />
            <Route path="/" element={<PageTransition><RotaProtegida><Upload /></RotaProtegida></PageTransition>} />
            <Route path="/dashboard" element={<PageTransition><RotaProtegida><Dashboard /></RotaProtegida></PageTransition>} />
            <Route path="/devedor/:rank" element={<PageTransition><RotaProtegida><DebtorDetail /></RotaProtegida></PageTransition>} />
            <Route path="/feedback" element={<PageTransition><RotaProtegida><Feedback /></RotaProtegida></PageTransition>} />
            <Route path="/bandit" element={<PageTransition><RotaProtegida roles={['comando']}><BanditDashboard /></RotaProtegida></PageTransition>} />
            <Route path="/aprendizado" element={<PageTransition><RotaProtegida roles={['comando']}><AprendizadoDashboard /></RotaProtegida></PageTransition>} />
            <Route path="/comando" element={<PageTransition><RotaProtegida roles={['comando']}><ComandoDashboard /></RotaProtegida></PageTransition>} />
            <Route path="/admin" element={<PageTransition><RotaProtegida roles={['admin', 'comando']}><AdminHome /></RotaProtegida></PageTransition>} />
            <Route path="/operador" element={<PageTransition><RotaProtegida roles={['operador']}><OperadorHome /></RotaProtegida></PageTransition>} />
            <Route path="/admin/usuarios" element={<PageTransition><RotaProtegida roles={['admin', 'comando']}><AdminUsuarios /></RotaProtegida></PageTransition>} />
            <Route path="/auditoria" element={<PageTransition><RotaProtegida roles={['admin', 'comando']}><Auditoria /></RotaProtegida></PageTransition>} />
            <Route path="/alterar-senha" element={<PageTransition><RotaProtegida><AlterarSenha /></RotaProtegida></PageTransition>} />
            <Route path="/privacidade" element={<PageTransition><Privacidade /></PageTransition>} />
            <Route path="*" element={<Navigate to="/" replace />} /> />
          </Routes>
    </AnimatePresence>
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
