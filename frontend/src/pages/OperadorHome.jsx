import ThemeToggle from '../components/ThemeToggle'
import { motion } from 'framer-motion'
import { lista, item } from '../lib/motion'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { Upload, ClipboardList, BarChart2, KeyRound, LogOut, ChevronRight } from 'lucide-react'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 2px 8px rgba(29,106,255,0.30)' }}>
      <span className="text-brand-ink font-bold text-xs">⚖</span>
    </div>
  )
}

function ActionCard({ icon: Icon, label, desc, onClick, accent = 'blue', disabled = false }) {
  const cfg = {
    blue:    { iconBg: 'rgba(29,106,255,0.12)',  iconTx: 'text-blue-400'    },
    emerald: { iconBg: 'rgba(16,185,129,0.12)',  iconTx: 'text-emerald-400' },
    amber:   { iconBg: 'rgba(245,158,11,0.12)',  iconTx: 'text-amber-400'   },
    slate:   { iconBg: 'var(--raise-3)', iconTx: 'text-ink-2'   },
  }[accent]

  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`group flex items-center gap-4 text-left p-5 rounded-2xl transition-all ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.30)',
      }}
      onMouseOver={e => { if (!disabled) { e.currentTarget.style.borderColor = 'rgba(29,106,255,0.30)'; e.currentTarget.style.boxShadow = '0 4px 24px rgba(0,0,0,0.40)' } }}
      onMouseOut={e => { if (!disabled) { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.30)' } }}
    >
      <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: cfg.iconBg }}>
        <Icon className={`w-5 h-5 ${cfg.iconTx}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-ink text-sm">{label}</p>
        <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--ink-3)' }}>{desc}</p>
      </div>
      {!disabled && <ChevronRight className="w-4 h-4 shrink-0" style={{ color: 'var(--ink-4)' }} />}
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
          <span className="font-bold text-ink text-sm">Mizan</span>
          {empresa && (
            <>
              <span className="text-ink-4 text-sm">/</span>
              <span className="text-sm truncate max-w-[160px]" style={{ color: 'var(--ink-2)' }}>{empresa}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: 'var(--ink-3)' }}>{usuario?.nome}</span>
          <ThemeToggle />
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-14">
        <div className="mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: 'var(--ink-3)' }}>
            Área do cobrador
          </p>
          <h1 className="text-3xl font-extrabold text-ink tracking-tight">
            Olá, {primeiroNome}
          </h1>
          {empresa && (
            <p className="mt-2 text-sm" style={{ color: 'var(--ink-2)' }}>
              Empresa: <span className="font-medium text-ink">{empresa}</span>
            </p>
          )}
        </div>

        <motion.div variants={lista} initial="inicial" animate="entra"
          className="grid grid-cols-2 gap-4">
          <motion.div variants={item}><ActionCard icon={Upload}      label="Analisar carteira"       desc="Enviar CSV/Excel ou sincronizar banco de dados autorizado"            onClick={() => navigate('/')}          accent="blue"    /></motion.div>
          <motion.div variants={item}><ActionCard icon={BarChart2}   label="Ver ranking"             desc={result ? 'Ver devedores priorizados e recomendações da IA' : 'Faça uma análise primeiro para ver o ranking'} onClick={() => navigate('/dashboard')} accent="emerald" disabled={!result} /></motion.div>
          <motion.div variants={item}><ActionCard icon={ClipboardList} label="Histórico de pagamentos" desc="Ver pagamentos registrados e status dos devedores da carteira"         onClick={() => navigate('/feedback')}  accent="amber"   /></motion.div>
          <motion.div variants={item}><ActionCard icon={KeyRound}    label="Alterar senha"           desc="Atualizar suas credenciais de acesso ao sistema"                       onClick={() => navigate('/alterar-senha')} accent="slate" /></motion.div>
        </motion.div>
      </main>
    </div>
  )
}
