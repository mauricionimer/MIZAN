import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState, Component } from 'react'
import { Loader2 } from 'lucide-react'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider, useAuth } from './context/AuthContext'

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center">
        <p className="text-white text-lg font-semibold">Algo deu errado nesta página.</p>
        <p className="text-blue-200 text-sm font-mono bg-black/30 px-4 py-2 rounded-md max-w-lg break-all">
          {this.state.error?.message || String(this.state.error)}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-5 py-2 bg-white text-blue-900 font-semibold rounded-md hover:bg-blue-50 transition-colors"
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
      style={{ background: 'rgba(245,158,11,0.10)', borderBottom: '1px solid rgba(245,158,11,0.20)', backdropFilter: 'blur(8px)' }}>
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

export default function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <AnalysisProvider>
        <ServerWarmupBanner />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/esqueci-senha" element={<EsqueciSenha />} />
            <Route path="/redefinir-senha" element={<RedefinirSenha />} />
            <Route path="/" element={<RotaProtegida><Upload /></RotaProtegida>} />
            <Route path="/dashboard" element={<RotaProtegida><Dashboard /></RotaProtegida>} />
            <Route path="/devedor/:rank" element={<RotaProtegida><DebtorDetail /></RotaProtegida>} />
            <Route path="/feedback" element={<RotaProtegida><Feedback /></RotaProtegida>} />
            <Route path="/bandit" element={<RotaProtegida roles={['comando']}><BanditDashboard /></RotaProtegida>} />
            <Route path="/aprendizado" element={<RotaProtegida roles={['comando']}><AprendizadoDashboard /></RotaProtegida>} />
            <Route path="/comando" element={<RotaProtegida roles={['comando']}><ComandoDashboard /></RotaProtegida>} />
            <Route path="/admin" element={<RotaProtegida roles={['admin', 'comando']}><AdminHome /></RotaProtegida>} />
            <Route path="/operador" element={<RotaProtegida roles={['operador']}><OperadorHome /></RotaProtegida>} />
            <Route path="/admin/usuarios" element={<RotaProtegida roles={['admin', 'comando']}><AdminUsuarios /></RotaProtegida>} />
            <Route path="/auditoria" element={<RotaProtegida roles={['admin', 'comando']}><Auditoria /></RotaProtegida>} />
            <Route path="/alterar-senha" element={<RotaProtegida><AlterarSenha /></RotaProtegida>} />
            <Route path="/privacidade" element={<Privacidade />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AnalysisProvider>
    </AuthProvider>
    </ErrorBoundary>
  )
}
