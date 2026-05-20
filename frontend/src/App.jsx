import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import Upload from './pages/Upload'
import Dashboard from './pages/Dashboard'
import DebtorDetail from './pages/DebtorDetail'
import Feedback from './pages/Feedback'
import BanditDashboard from './pages/BanditDashboard'
import AdminUsuarios from './pages/AdminUsuarios'
import AlterarSenha from './pages/AlterarSenha'
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
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
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
