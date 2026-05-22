import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import {
  Upload, ClipboardList, BarChart2, KeyRound, LogOut, ChevronRight,
} from 'lucide-react'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

function ActionCard({ icon: Icon, label, desc, onClick, accent = 'blue', disabled = false }) {
  const cfg = {
    blue:    { icon: 'bg-blue-50 text-blue-600',      ring: 'hover:border-blue-200'   },
    emerald: { icon: 'bg-emerald-50 text-emerald-600', ring: 'hover:border-emerald-200' },
    amber:   { icon: 'bg-amber-50 text-amber-600',    ring: 'hover:border-amber-200'  },
    slate:   { icon: 'bg-slate-100 text-slate-500',   ring: 'hover:border-slate-300'  },
  }[accent]

  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`group flex items-center gap-4 text-left p-5 rounded-2xl border border-slate-100 bg-white transition-all shadow-[0_2px_12px_rgba(15,23,42,0.06)] ${
        disabled
          ? 'opacity-40 cursor-not-allowed'
          : `hover:shadow-[0_4px_20px_rgba(15,23,42,0.10)] ${cfg.ring}`
      }`}
    >
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${cfg.icon}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-slate-800 text-sm">{label}</p>
        <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{desc}</p>
      </div>
      {!disabled && <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />}
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
    <div className="min-h-screen bg-slate-50">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          {empresa && (
            <>
              <span className="text-slate-200 text-sm">/</span>
              <span className="text-slate-500 text-sm truncate max-w-[160px]">{empresa}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400 hidden sm:block">{usuario?.nome}</span>
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-14">
        <div className="mb-10">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Área do cobrador</p>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Olá, {primeiroNome}
          </h1>
          {empresa && (
            <p className="text-slate-500 mt-2 text-sm">
              Empresa: <span className="font-medium text-slate-700">{empresa}</span>
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ActionCard
            icon={Upload}
            label="Analisar carteira"
            desc="Enviar CSV/Excel ou sincronizar banco de dados autorizado"
            onClick={() => navigate('/')}
            accent="blue"
          />
          <ActionCard
            icon={BarChart2}
            label="Ver ranking"
            desc={result ? 'Ver devedores priorizados e recomendações da IA' : 'Faça uma análise primeiro para ver o ranking'}
            onClick={() => navigate('/dashboard')}
            accent="emerald"
            disabled={!result}
          />
          <ActionCard
            icon={ClipboardList}
            label="Registrar pagamento"
            desc="Informar resultado de contato ou confirmação de pagamento"
            onClick={() => navigate('/feedback')}
            accent="amber"
          />
          <ActionCard
            icon={KeyRound}
            label="Alterar senha"
            desc="Atualizar suas credenciais de acesso ao sistema"
            onClick={() => navigate('/alterar-senha')}
            accent="slate"
          />
        </div>
      </main>
    </div>
  )
}
