import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listarConexoes, listarUsuarios } from '../api'
import {
  Upload, Users, BarChart2, KeyRound, LogOut, Database,
  Shield, ChevronRight,
} from 'lucide-react'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

function ActionCard({ icon: Icon, label, desc, onClick, accent = 'blue', full = false }) {
  const cfg = {
    blue:    { icon: 'bg-blue-50 text-blue-600',    ring: 'hover:border-blue-200'   },
    violet:  { icon: 'bg-violet-50 text-violet-600', ring: 'hover:border-violet-200' },
    emerald: { icon: 'bg-emerald-50 text-emerald-600', ring: 'hover:border-emerald-200' },
    slate:   { icon: 'bg-slate-100 text-slate-600',  ring: 'hover:border-slate-300'  },
  }[accent]

  return (
    <button
      onClick={onClick}
      className={`group flex items-center gap-4 text-left p-5 rounded-2xl border border-slate-100 bg-white hover:shadow-[0_4px_20px_rgba(15,23,42,0.10)] ${cfg.ring} transition-all shadow-[0_2px_12px_rgba(15,23,42,0.06)] ${full ? 'col-span-2' : ''}`}
    >
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${cfg.icon}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-slate-800 text-sm">{label}</p>
        <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{desc}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />
    </button>
  )
}

export default function AdminHome() {
  const { token, usuario, logout, isAdmin, isComando } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState({ operadores: 0, conexoes: 0 })

  useEffect(() => {
    if (!isAdmin && !isComando) { navigate('/'); return }
    Promise.all([listarUsuarios(token), listarConexoes()])
      .then(([users, conxs]) => setStats({
        operadores: users.filter(u => u.role === 'operador' && u.ativo).length,
        conexoes: conxs.length,
      }))
      .catch(() => {})
  }, [])

  const empresa = usuario?.empresa_id || 'Minha empresa'
  const primeiroNome = usuario?.nome?.split(' ')[0] ?? usuario?.nome ?? ''

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          <span className="text-slate-200 text-sm">/</span>
          <span className="text-slate-500 text-sm truncate max-w-[160px]">{empresa}</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700 ring-1 ring-violet-200/60 flex items-center gap-1 shrink-0">
            <Shield className="w-3 h-3" /> Admin
          </span>
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
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Painel administrativo</p>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Olá, {primeiroNome}
          </h1>
          <p className="text-slate-500 mt-2 text-sm flex flex-wrap gap-x-4 gap-y-1">
            <span className="font-medium text-slate-700">{empresa}</span>
            <span>{stats.operadores} operador{stats.operadores !== 1 ? 'es' : ''} ativo{stats.operadores !== 1 ? 's' : ''}</span>
            {stats.conexoes > 0 && (
              <span>{stats.conexoes} banco{stats.conexoes !== 1 ? 's' : ''} cadastrado{stats.conexoes !== 1 ? 's' : ''}</span>
            )}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ActionCard
            icon={Upload}
            label="Analisar carteira"
            desc="Enviar CSV/Excel ou conectar banco de dados para análise com IA"
            onClick={() => navigate('/')}
            accent="blue"
          />
          <ActionCard
            icon={Users}
            label="Gerenciar equipe"
            desc="Operadores, permissões de banco e configurações da empresa"
            onClick={() => navigate('/admin/usuarios')}
            accent="violet"
          />
          <ActionCard
            icon={Database}
            label="Bancos de dados"
            desc="Cadastrar conexões e configurar sincronizações automáticas"
            onClick={() => navigate('/')}
            accent="emerald"
          />
          <ActionCard
            icon={KeyRound}
            label="Alterar senha"
            desc="Atualizar suas credenciais de acesso ao sistema"
            onClick={() => navigate('/alterar-senha')}
            accent="slate"
          />
        </div>

        <div className="mt-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full flex items-center justify-between px-5 py-4 rounded-2xl border border-dashed border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-600 transition-colors text-sm"
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
