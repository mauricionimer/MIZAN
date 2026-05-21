import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listarUsuarios, registrarUsuario, toggleUsuarioAtivo, alterarRoleUsuario } from '../api'
import { Users, UserPlus, LogOut, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight, ArrowLeft } from 'lucide-react'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

export default function AdminUsuarios() {
  const { token, usuario, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  const [usuarios, setUsuarios] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [msg, setMsg] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', nome: '', senha: '', role: 'operador' })
  const [formErro, setFormErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!isAdmin) { navigate('/'); return }
    carregar()
  }, [])

  async function carregar() {
    setCarregando(true)
    setErro('')
    try {
      const lista = await listarUsuarios(token)
      setUsuarios(lista)
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  async function handleToggleAtivo(u) {
    const novoAtivo = !u.ativo
    try {
      await toggleUsuarioAtivo(token, u.id, novoAtivo)
      setMsg(`Usuário ${u.nome} ${novoAtivo ? 'ativado' : 'desativado'} com sucesso.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, ativo: novoAtivo } : x))
      setTimeout(() => setMsg(''), 3000)
    } catch (e) {
      setErro(e.message)
    }
  }

  async function handleToggleRole(u) {
    const novoRole = u.role === 'admin' ? 'operador' : 'admin'
    if (!confirm(`Alterar ${u.nome} para ${novoRole}?`)) return
    try {
      await alterarRoleUsuario(token, u.id, novoRole)
      setMsg(`Permissão de ${u.nome} alterada para ${novoRole}.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, role: novoRole } : x))
      setTimeout(() => setMsg(''), 3000)
    } catch (e) {
      setErro(e.message)
    }
  }

  async function handleRegistrar(e) {
    e.preventDefault()
    setFormErro('')
    setSalvando(true)
    try {
      await registrarUsuario(token, form)
      setMsg(`Usuário ${form.email} criado com sucesso.`)
      setForm({ email: '', nome: '', senha: '', role: 'operador' })
      setShowForm(false)
      carregar()
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setFormErro(e.message)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/dashboard')} className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-lg hover:bg-slate-100">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Logo />
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          <span className="text-slate-200 text-sm">/</span>
          <span className="text-slate-500 text-sm">Usuários</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400 hidden sm:block">{usuario?.nome}</span>
          <button onClick={logout} className="nav-link-danger">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Usuários do sistema</h1>
            <p className="text-sm text-slate-500 mt-1">Gerencie quem tem acesso ao Mizan e suas permissões.</p>
          </div>
          <button
            onClick={() => { setShowForm(!showForm); setFormErro('') }}
            className="btn-primary"
          >
            <UserPlus className="w-4 h-4" /> Novo usuário
          </button>
        </div>

        {msg && (
          <div className="mb-5 bg-emerald-50 border border-emerald-100 text-emerald-700 rounded-xl px-4 py-3 text-sm">
            {msg}
          </div>
        )}

        {erro && (
          <div className="mb-5 bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3 text-sm">
            {erro}
          </div>
        )}

        {showForm && (
          <div className="mb-6 bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] p-6">
            <h2 className="text-sm font-bold text-slate-800 mb-5">Criar novo usuário</h2>
            <form onSubmit={handleRegistrar} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Nome completo</label>
                <input
                  type="text"
                  required
                  value={form.nome}
                  onChange={e => setForm(f => ({ ...f, nome: e.target.value }))}
                  className="input-base"
                  placeholder="João Silva"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">E-mail</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="input-base"
                  placeholder="joao@empresa.com"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Senha inicial</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={form.senha}
                  onChange={e => setForm(f => ({ ...f, senha: e.target.value }))}
                  className="input-base"
                  placeholder="mínimo 6 caracteres"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Permissão</label>
                <select
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="input-base"
                >
                  <option value="operador">Operador</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>

              {formErro && (
                <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-2">{formErro}</p>
              )}

              <div className="col-span-2 flex gap-3 justify-end pt-1">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={salvando} className="btn-primary disabled:opacity-50">
                  {salvando ? 'Criando...' : 'Criar usuário'}
                </button>
              </div>
            </form>
          </div>
        )}

        {carregando ? (
          <div className="text-center py-16 text-slate-400 text-sm">Carregando...</div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Nome</th>
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">E-mail</th>
                  <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Permissão</th>
                  <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Ações</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map(u => (
                  <tr key={u.id} className={`border-b border-slate-50 last:border-0 hover:bg-slate-50/50 transition-colors ${!u.ativo ? 'opacity-50' : ''}`}>
                    <td className="px-5 py-4 font-medium text-slate-900">{u.nome}</td>
                    <td className="px-5 py-4 text-slate-500">{u.email}</td>
                    <td className="px-5 py-4 text-center">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        u.role === 'admin'
                          ? 'bg-violet-50 text-violet-700 ring-1 ring-violet-200/60'
                          : 'bg-blue-50 text-blue-700 ring-1 ring-blue-200/60'
                      }`}>
                        {u.role === 'admin' && <ShieldCheck className="w-3 h-3" />}
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-center">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        u.ativo
                          ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/60'
                          : 'bg-slate-100 text-slate-400 ring-1 ring-slate-200/60'
                      }`}>
                        {u.ativo ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center justify-center gap-1">
                        {u.email !== usuario?.email ? (
                          <>
                            <button
                              onClick={() => handleToggleAtivo(u)}
                              title={u.ativo ? 'Desativar' : 'Ativar'}
                              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                            >
                              {u.ativo ? <ToggleRight className="w-5 h-5 text-emerald-500" /> : <ToggleLeft className="w-5 h-5" />}
                            </button>
                            <button
                              onClick={() => handleToggleRole(u)}
                              title={u.role === 'admin' ? 'Rebaixar para operador' : 'Promover a admin'}
                              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                            >
                              {u.role === 'admin'
                                ? <ShieldOff className="w-4 h-4 text-violet-500" />
                                : <ShieldCheck className="w-4 h-4" />}
                            </button>
                          </>
                        ) : (
                          <span className="text-xs text-slate-300 italic px-2">você</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {usuarios.length === 0 && (
              <div className="text-center py-12 text-slate-400 text-sm">Nenhum usuário encontrado.</div>
            )}
          </div>
        )}

        <p className="mt-4 text-xs text-slate-400">
          Total: {usuarios.length} usuário{usuarios.length !== 1 ? 's' : ''} · Ativos: {usuarios.filter(u => u.ativo).length}
        </p>
      </div>
    </div>
  )
}
