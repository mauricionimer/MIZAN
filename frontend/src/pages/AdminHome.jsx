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
  return <LogoMark className="h-4 w-4" />
}

function ActionCard({ icon: Icon, label, desc, onClick, accent = 'blue', full = false }) {
  const cfg = {
    blue:    { iconBg: 'var(--info-soft)',  iconTx: 'text-[var(--info)]'    },
    violet:  { iconBg: 'rgba(139,92,246,0.12)',  iconTx: 'text-[#6D28D9]'  },
    emerald: { iconBg: 'var(--ok-soft)',  iconTx: 'text-[var(--ok)]' },
    slate:   { iconBg: 'rgba(22,32,60,0.06)', iconTx: 'text-[var(--text-3)]'   },
  }[accent]

  return (
    <button
      onClick={onClick}
      className={`group flex items-center gap-4 text-left p-5 rounded-lg transition-all ${full ? 'col-span-2' : ''}`}
      style={{
        background: 'var(--surface)',
        border: '1px solid rgba(22,32,60,0.10)',
      }}
      onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--info-border)' }}
      onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(22,32,60,0.10)' }}
    >
      <div className="w-11 h-11 rounded-md flex items-center justify-center shrink-0"
        style={{ background: cfg.iconBg }}>
        <Icon className={`w-5 h-5 ${cfg.iconTx}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-[var(--text-1)] text-sm">{label}</p>
        <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-3)' }}>{desc}</p>
      </div>
      <ChevronRight className="w-4 h-4 shrink-0 transition-colors" style={{ color: 'var(--text-muted)' }} />
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
            ? <img src={fotoEmpresa} alt={empresa} className="w-7 h-7 rounded-lg object-cover border border-[var(--border-hi)]" />
            : <Logo />}
          <span className="font-bold text-[var(--text-1)] text-sm">{empresa}</span>
          <span className="text-[var(--border-hi)] text-sm">·</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1 shrink-0"
            style={{ background: 'rgba(139,92,246,0.12)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.20)' }}>
            <Shield className="w-3 h-3" /> Admin
          </span>
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
            Painel administrativo
          </p>
          <h1 className="text-3xl font-extrabold text-[var(--text-1)] tracking-tight">
            Olá, {primeiroNome}
          </h1>
          <p className="mt-2 text-sm flex flex-wrap gap-x-4 gap-y-1" style={{ color: 'var(--text-2)' }}>
            <span className="font-medium text-[var(--text-1)]">{empresa}</span>
            <span>{stats.operadores} operador{stats.operadores !== 1 ? 'es' : ''} ativo{stats.operadores !== 1 ? 's' : ''}</span>
            {stats.conexoes > 0 && (
              <span>{stats.conexoes} banco{stats.conexoes !== 1 ? 's' : ''} cadastrado{stats.conexoes !== 1 ? 's' : ''}</span>
            )}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ActionCard icon={Upload}   label="Analisar carteira"  desc="Enviar CSV/Excel ou conectar banco de dados para análise com IA" onClick={() => navigate('/')}               accent="blue"    />
          <ActionCard icon={Users}    label="Gerenciar equipe"   desc="Operadores, permissões de banco e configurações da empresa"      onClick={() => navigate('/admin/usuarios')} accent="violet"  />
          <ActionCard icon={Database} label="Bancos de dados"    desc="Cadastrar conexões e configurar sincronizações automáticas"      onClick={() => navigate('/')}               accent="emerald" />
          <ActionCard icon={KeyRound} label="Alterar senha"      desc="Atualizar suas credenciais de acesso ao sistema"                 onClick={() => navigate('/alterar-senha')}  accent="slate"   />
        </div>

        <div className="mt-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full flex items-center justify-between px-5 py-4 rounded-lg transition-colors text-sm"
            style={{ border: '1px dashed rgba(22,32,60,0.12)', color: 'var(--text-3)' }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--info-border)'; e.currentTarget.style.color = 'var(--text-2)' }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(22,32,60,0.12)'; e.currentTarget.style.color = 'var(--text-3)' }}
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
