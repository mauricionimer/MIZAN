import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listarUsuarios, registrarUsuario, toggleUsuarioAtivo, alterarRoleUsuario } from '../api'
import { Users, UserPlus, LogOut, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight, ArrowLeft } from 'lucide-react'

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
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/dashboard')} className="text-gray-500 hover:text-gray-800">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Users className="w-5 h-5 text-blue-600" />
          <span className="font-semibold text-gray-800">Gerenciar Usuários</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600">{usuario?.nome}</span>
          <button
            onClick={logout}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition-colors"
          >
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Usuários do sistema</h1>
            <p className="text-sm text-gray-500 mt-1">
              Gerencie quem tem acesso ao Mizan e suas permissões.
            </p>
          </div>
          <button
            onClick={() => { setShowForm(!showForm); setFormErro('') }}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Novo usuário
          </button>
        </div>

        {/* Mensagem de sucesso */}
        {msg && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-800 rounded-lg px-4 py-3 text-sm">
            {msg}
          </div>
        )}

        {/* Erro geral */}
        {erro && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 text-sm">
            {erro}
          </div>
        )}

        {/* Formulário de novo usuário */}
        {showForm && (
          <div className="mb-6 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Criar novo usuário</h2>
            <form onSubmit={handleRegistrar} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Nome completo</label>
                <input
                  type="text"
                  required
                  value={form.nome}
                  onChange={e => setForm(f => ({ ...f, nome: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="João Silva"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">E-mail</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="joao@empresa.com"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Senha inicial</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={form.senha}
                  onChange={e => setForm(f => ({ ...f, senha: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="mínimo 6 caracteres"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Permissão</label>
                <select
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="operador">Operador</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>

              {formErro && (
                <p className="col-span-2 text-sm text-red-600">{formErro}</p>
              )}

              <div className="col-span-2 flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={salvando}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
                >
                  {salvando ? 'Criando...' : 'Criar usuário'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Tabela de usuários */}
        {carregando ? (
          <div className="text-center py-12 text-gray-500">Carregando...</div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Nome</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">E-mail</th>
                  <th className="text-center px-5 py-3 font-medium text-gray-600">Permissão</th>
                  <th className="text-center px-5 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-center px-5 py-3 font-medium text-gray-600">Ações</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map(u => (
                  <tr key={u.id} className={`border-b border-gray-100 last:border-0 ${!u.ativo ? 'opacity-50' : ''}`}>
                    <td className="px-5 py-3 font-medium text-gray-900">{u.nome}</td>
                    <td className="px-5 py-3 text-gray-600">{u.email}</td>
                    <td className="px-5 py-3 text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-50 text-blue-700'
                      }`}>
                        {u.role === 'admin' ? <ShieldCheck className="w-3 h-3" /> : null}
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.ativo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {u.ativo ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-center gap-2">
                        {/* Não permite alterar o próprio usuário logado */}
                        {u.email !== usuario?.email ? (
                          <>
                            <button
                              onClick={() => handleToggleAtivo(u)}
                              title={u.ativo ? 'Desativar' : 'Ativar'}
                              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
                            >
                              {u.ativo ? <ToggleRight className="w-5 h-5 text-green-600" /> : <ToggleLeft className="w-5 h-5" />}
                            </button>
                            <button
                              onClick={() => handleToggleRole(u)}
                              title={u.role === 'admin' ? 'Rebaixar para operador' : 'Promover a admin'}
                              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
                            >
                              {u.role === 'admin'
                                ? <ShieldOff className="w-4 h-4 text-purple-500" />
                                : <ShieldCheck className="w-4 h-4 text-gray-400" />}
                            </button>
                          </>
                        ) : (
                          <span className="text-xs text-gray-400 italic">você</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {usuarios.length === 0 && (
              <div className="text-center py-10 text-gray-400">Nenhum usuário encontrado.</div>
            )}
          </div>
        )}

        <p className="mt-4 text-xs text-gray-400">
          Total: {usuarios.length} usuário{usuarios.length !== 1 ? 's' : ''} •
          Ativos: {usuarios.filter(u => u.ativo).length}
        </p>
      </div>
    </div>
  )
}
