import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider, useAuth } from './context/AuthContext'

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

  if (!show) return null
  return (
    <div className="fixed top-0 inset-x-0 z-50 bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex items-center justify-center gap-3 text-sm text-amber-800 shadow-sm">
      <Loader2 className="h-4 w-4 animate-spin text-amber-500 shrink-0" />
      <span>O servidor está acordando — a primeira requisição pode levar até 30s (plano gratuito).</span>
    </div>
  )
}
import Upload from './pages/Upload'
import Dashboard from './pages/Dashboard'
import DebtorDetail from './pages/DebtorDetail'
import Feedback from './pages/Feedback'
import BanditDashboard from './pages/BanditDashboard'
import AdminUsuarios from './pages/AdminUsuarios'
import AlterarSenha from './pages/AlterarSenha'
import EsqueciSenha from './pages/EsqueciSenha'
import RedefinirSenha from './pages/RedefinirSenha'
import Login from './pages/Login'

function RotaProtegida({ children }) {
  const { autenticado } = useAuth()
  const location = useLocation()
  if (!autenticado) return <Navigate to="/login" state={{ from: location }} replace />
  return children
}

export default function App() {
  return (
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
            <Route path="/bandit" element={<RotaProtegida><BanditDashboard /></RotaProtegida>} />
            <Route path="/admin/usuarios" element={<RotaProtegida><AdminUsuarios /></RotaProtegida>} />
            <Route path="/alterar-senha" element={<RotaProtegida><AlterarSenha /></RotaProtegida>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AnalysisProvider>
    </AuthProvider>
  )
}
