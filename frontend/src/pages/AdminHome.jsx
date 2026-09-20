import ThemeToggle from '../components/ThemeToggle'
import { motion } from 'framer-motion'
import { lista, item } from '../lib/motion'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listarConexoes, listarUsuarios } from '../api'
import {
  Upload, Users, BarChart2, KeyRound, LogOut, Database,
  Shield, ChevronRight,
} from 'lucide-react'
import { LogoMark } from '../components/Logo'

function Logo() {
  return <LogoMark className="h-5 w-5 shrink-0" />
}

function ActionCard({ icon: Icon, label, onClick, accent = 'blue', full = false }) {
  const cfg = {
    blue:    { iconBg: 'rgb(var(--c-royal) / 0.12)',  iconTx: 'text-blue-400'    },
    violet:  { iconBg: 'rgb(var(--c-royal) / 0.12)',  iconTx: 'text-violet-400'  },
    emerald: { iconBg: 'rgb(var(--c-success) / 0.12)',  iconTx: 'text-emerald-400' },
    slate:   { iconBg: 'var(--raise-3)', iconTx: 'text-ink-2'   },
  }[accent]

  return (
    <button
      onClick={onClick}
      className={`group flex items-center gap-4 text-left p-5 rounded-2xl transition-all ${full ? 'col-span-2' : ''}`}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.30)',
      }}
      onMouseOver={e => { e.currentTarget.style.borderColor = 'rgb(var(--c-royal) / 0.30)'; e.currentTarget.style.boxShadow = '0 4px 24px rgba(0,0,0,0.40)' }}
      onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.30)' }}
    >
      <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: cfg.iconBg }}>
        <Icon className={`w-5 h-5 ${cfg.iconTx}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-ink text-sm">{label}</p>
      </div>
      <ChevronRight className="w-4 h-4 shrink-0 transition-colors" style={{ color: 'var(--ink-4)' }} />
    </button>
  )
}

export default function AdminHome() {
  const { token, usuario, logout, empresaConfig } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState({ operadores: 0, conexoes: 0 })

  useEffect(() => {
    Promise.all([listarUsuarios(token), listarConexoes()])
      .then(([users, conxs]) => setStats({
        operadores: users.filter(u => u.role === 'operador' && u.ativo).length,
        conexoes: conxs.length,
      }))
      .catch(() => {})
  }, [])

  const empresa = empresaConfig?.nome_exibicao || usuario?.empresa_id || 'Minha empresa'
  const fotoEmpresa = empresaConfig?.foto_url
  const primeiroNome = usuario?.nome?.split(' ')[0] ?? usuario?.nome ?? ''

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {fotoEmpresa
            ? <img src={fotoEmpresa} alt={empresa} className="w-7 h-7 rounded-lg object-cover border border-line" />
            : <Logo />}
          <span className="font-bold text-ink text-sm">{empresa}</span>
          <span className="text-ink-4 text-sm">·</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1 shrink-0"
            style={{ background: 'rgb(var(--c-royal) / 0.12)', color: 'rgb(var(--c-royal))', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
            <Shield className="w-3 h-3" /> Admin
          </span>
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
            Painel administrativo
          </p>
          <h1 className="text-3xl font-extrabold text-ink tracking-tight">
            Olá, {primeiroNome}
          </h1>
          <p className="mt-2 text-sm flex flex-wrap gap-x-4 gap-y-1" style={{ color: 'var(--ink-2)' }}>
            <span className="font-medium text-ink">{empresa}</span>
            <span>{stats.operadores} operador{stats.operadores !== 1 ? 'es' : ''} ativo{stats.operadores !== 1 ? 's' : ''}</span>
            {stats.conexoes > 0 && (
              <span>{stats.conexoes} banco{stats.conexoes !== 1 ? 's' : ''} cadastrado{stats.conexoes !== 1 ? 's' : ''}</span>
            )}
          </p>
        </div>

        <motion.div variants={lista} initial="inicial" animate="entra"
          className="grid grid-cols-2 gap-4">
          <motion.div variants={item}><ActionCard icon={Upload}   label="Analisar carteira" onClick={() => navigate('/')}               accent="blue"    /></motion.div>
          <motion.div variants={item}><ActionCard icon={Users}    label="Gerenciar equipe"      onClick={() => navigate('/admin/usuarios')} accent="violet"  /></motion.div>
          <motion.div variants={item}><ActionCard icon={Database} label="Bancos de dados"      onClick={() => navigate('/')}               accent="emerald" /></motion.div>
          <motion.div variants={item}><ActionCard icon={KeyRound} label="Alterar senha"                 onClick={() => navigate('/alterar-senha')}  accent="slate"   /></motion.div>
        </motion.div>

        <div className="mt-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full flex items-center justify-between px-5 py-4 rounded-2xl transition-colors text-sm"
            style={{ border: '1px dashed var(--line)', color: 'var(--ink-3)' }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'rgb(var(--c-royal) / 0.30)'; e.currentTarget.style.color = 'var(--ink-2)' }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.color = 'var(--ink-3)' }}
          >
            <span className="flex items-center gap-2">
              <BarChart2 className="w-4 h-4" />
              Ver última análise (se disponível)
            </span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </main>
    </div>
  )
}
