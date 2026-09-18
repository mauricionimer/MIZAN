import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { Upload, ClipboardList, BarChart2, KeyRound, LogOut, ChevronRight } from 'lucide-react'
import { LogoMark } from '../components/Logo'

function Logo() {
  return <LogoMark className="h-4 w-4" />
}

function ActionCard({ icon: Icon, label, desc, onClick, accent = 'blue', disabled = false }) {
  const cfg = {
    blue:    { iconBg: 'var(--info-soft)',  iconTx: 'text-[var(--info)]'    },
    emerald: { iconBg: 'var(--ok-soft)',  iconTx: 'text-[var(--ok)]' },
    amber:   { iconBg: 'var(--warn-soft)',  iconTx: 'text-[var(--warn)]'   },
    slate:   { iconBg: 'rgba(22,32,60,0.06)', iconTx: 'text-[var(--text-3)]'   },
  }[accent]

  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`group flex items-center gap-4 text-left p-5 rounded-lg transition-all ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
      style={{
        background: 'var(--surface)',
        border: '1px solid rgba(22,32,60,0.10)',
      }}
      onMouseOver={e => { if (!disabled) { e.currentTarget.style.borderColor = 'var(--info-border)' } }}
      onMouseOut={e => { if (!disabled) { e.currentTarget.style.borderColor = 'rgba(22,32,60,0.10)' } }}
    >
      <div className="w-11 h-11 rounded-md flex items-center justify-center shrink-0"
        style={{ background: cfg.iconBg }}>
        <Icon className={`w-5 h-5 ${cfg.iconTx}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-[var(--text-1)] text-sm">{label}</p>
        <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-3)' }}>{desc}</p>
      </div>
      {!disabled && <ChevronRight className="w-4 h-4 shrink-0" style={{ color: 'var(--text-muted)' }} />}
    </button>
  )
}

export default function OperadorHome() {
  const { usuario, logout, isOperador } = useAuth()
  const { result } = useAnalysis()
  const navigate = useNavigate()

  const primeiroNome = usuario?.nome?.split(' ')[0] ?? usuario?.nome ?? ''
  const empresa = usuario?.empresa_id || ''

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="font-bold text-[var(--text-1)] text-sm">Mizan</span>
          {empresa && (
            <>
              <span className="text-[var(--border-hi)] text-sm">/</span>
              <span className="text-sm truncate max-w-[160px]" style={{ color: 'var(--text-2)' }}>{empresa}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: 'var(--text-3)' }}>{usuario?.nome}</span>
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-14">
        <div className="mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: 'var(--text-3)' }}>
            Área do cobrador
          </p>
          <h1 className="text-3xl font-extrabold text-[var(--text-1)] tracking-tight">
            Olá, {primeiroNome}
          </h1>
          {empresa && (
            <p className="mt-2 text-sm" style={{ color: 'var(--text-2)' }}>
              Empresa: <span className="font-medium text-[var(--text-1)]">{empresa}</span>
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ActionCard icon={Upload}      label="Analisar carteira"       desc="Enviar CSV/Excel ou sincronizar banco de dados autorizado"            onClick={() => navigate('/')}          accent="blue"    />
          <ActionCard icon={BarChart2}   label="Ver ranking"             desc={result ? 'Ver devedores priorizados e recomendações da IA' : 'Faça uma análise primeiro para ver o ranking'} onClick={() => navigate('/dashboard')} accent="emerald" disabled={!result} />
          <ActionCard icon={ClipboardList} label="Histórico de pagamentos" desc="Ver pagamentos registrados e status dos devedores da carteira"         onClick={() => navigate('/feedback')}  accent="amber"   />
          <ActionCard icon={KeyRound}    label="Alterar senha"           desc="Atualizar suas credenciais de acesso ao sistema"                       onClick={() => navigate('/alterar-senha')} accent="slate" />
        </div>
      </main>
    </div>
  )
}
