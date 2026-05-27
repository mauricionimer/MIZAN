import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  listarUsuarios, registrarUsuario, toggleUsuarioAtivo, alterarRoleUsuario,
  listarConexoes, listarPermissoesConexao, concederPermissaoConexao, revogarPermissaoConexao,
  listarEmpresas, adicionarUsuarioEmpresa, removerUsuarioEmpresa, deletarEmpresa,
  buscarAuditoria, putEmpresaConfig, uploadEmpresaFoto,
} from '../api'
import {
  Users, UserPlus, LogOut, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight,
  ArrowLeft, Database, Lock, Unlock, ChevronDown, ChevronUp,
  Building2, Plus, X, UserMinus, Mail, Trash2, Clock, Camera, Pencil, Check,
} from 'lucide-react'

const ACAO_LABEL = {
  carteira_criada:      'Carteira criada',
  carteira_sincronizada:'Carteira atualizada',
  banco_sincronizado:   'Banco sincronizado',
  feedback_importado:   'Feedbacks importados',
  usuario_criado:       'Usuário criado',
  usuario_ativado:      'Usuário ativado',
  usuario_desativado:   'Usuário desativado',
  role_alterado:        'Permissão alterada',
  senha_alterada:       'Senha alterada',
  conexao_criada:       'Conexão criada',
}

const ACAO_COR = {
  carteira_criada:      'bg-blue-400',
  carteira_sincronizada:'bg-blue-400',
  banco_sincronizado:   'bg-emerald-400',
  feedback_importado:   'bg-violet-400',
  usuario_criado:       'bg-indigo-400',
  usuario_ativado:      'bg-emerald-400',
  usuario_desativado:   'bg-red-400',
  role_alterado:        'bg-amber-400',
  senha_alterada:       'bg-slate-400',
}

function fmtAuditDate(iso) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

const ROLE_BADGE = {
  comando:  'bg-rose-50 text-rose-700 ring-1 ring-rose-200/60',
  admin:    'bg-violet-50 text-violet-700 ring-1 ring-violet-200/60',
  operador: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200/60',
}

function BadgeRole({ role }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[role] ?? 'bg-slate-100 text-slate-500'}`}>
      {role === 'admin' && <ShieldCheck className="w-3 h-3" />}
      {role}
    </span>
  )
}

// ── Painel de permissões de uma conexão ──────────────────────────────────────
function PainelPermissoes({ conexao, operadores, token }) {
  const [aberto, setAberto] = useState(false)
  const [permitidos, setPermitidos] = useState([])
  const [carregando, setCarregando] = useState(false)

  async function carregar() {
    setCarregando(true)
    try {
      const data = await listarPermissoesConexao(token, conexao.id)
      setPermitidos(data.map(o => o.id))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => { if (aberto) carregar() }, [aberto])

  async function toggle(operadorId, temPermissao) {
    if (temPermissao) {
      await revogarPermissaoConexao(token, conexao.id, operadorId)
    } else {
      await concederPermissaoConexao(token, conexao.id, operadorId)
    }
    carregar()
  }

  const somenteOperadores = operadores.filter(o => o.role === 'operador' && o.ativo)

  return (
    <div className="border border-slate-100 rounded-xl overflow-hidden">
      <button
        onClick={() => setAberto(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-sm"
      >
        <div className="flex items-center gap-2 font-medium text-slate-700">
          <Database className="w-4 h-4 text-slate-400" />
          {conexao.nome}
          <span className="text-xs text-slate-400 font-normal">({conexao.tipo})</span>
        </div>
        {aberto ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {aberto && (
        <div className="px-4 py-3 space-y-2">
          {carregando ? (
            <p className="text-xs text-slate-400">Carregando...</p>
          ) : somenteOperadores.length === 0 ? (
            <p className="text-xs text-slate-400">Nenhum operador ativo nesta empresa.</p>
          ) : (
            somenteOperadores.map(op => {
              const tem = permitidos.includes(op.id)
              return (
                <div key={op.id} className="flex items-center justify-between py-1">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{op.nome}</p>
                    <p className="text-xs text-slate-400">{op.email}</p>
                  </div>
                  <button
                    onClick={() => toggle(op.id, tem)}
                    title={tem ? 'Revogar acesso' : 'Conceder acesso'}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      tem
                        ? 'bg-emerald-50 text-emerald-700 hover:bg-red-50 hover:text-red-700'
                        : 'bg-slate-100 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700'
                    }`}
                  >
                    {tem ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
                    {tem ? 'Com acesso' : 'Sem acesso'}
                  </button>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}

// ── Card de empresa ──────────────────────────────────────────────────────────
function CardEmpresa({ empresa, token, onAtualizar }) {
  const [membros, setMembros] = useState(empresa.usuarios)
  const [emailInput, setEmailInput] = useState('')

  // Sincroniza quando o servidor atualiza a lista (ex: após adicionar usuário).
  // Usa join de IDs como chave estável para não disparar em re-renders do pai.
  const usuariosKey = empresa.usuarios.map(u => u.id).sort().join(',')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setMembros(empresa.usuarios) }, [usuariosKey])
  const [adicionando, setAdicionando] = useState(false)
  const [showInput, setShowInput] = useState(false)
  const [erro, setErro] = useState('')

  async function handleAdicionar(e) {
    e.preventDefault()
    if (!emailInput.trim()) return
    setAdicionando(true); setErro('')
    try {
      await adicionarUsuarioEmpresa(token, empresa.empresa_id, emailInput.trim())
      setEmailInput(''); setShowInput(false)
      onAtualizar()
    } catch (err) { setErro(err.message) } finally { setAdicionando(false) }
  }

  async function handleRemover(usuarioId) {
    try {
      await removerUsuarioEmpresa(token, empresa.empresa_id, usuarioId)
      // Atualiza só o estado local — mantém o card visível mesmo com 0 membros
      setMembros(prev => prev.filter(u => u.id !== usuarioId))
    } catch (err) { setErro(err.message) }
  }

  async function handleDeletar() {
    if (!confirm(`Excluir empresa "${empresa.empresa_id}"? Todos os ${membros.length} usuário(s) ficarão sem empresa.`)) return
    try {
      await deletarEmpresa(token, empresa.empresa_id)
      onAtualizar()
    } catch (err) { setErro(err.message) }
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0">
            <Building2 className="w-4 h-4 text-indigo-500" />
          </div>
          <div>
            <p className="font-bold text-slate-800 text-sm">{empresa.empresa_id}</p>
            <p className="text-xs text-slate-400">{membros.length} membro{membros.length !== 1 ? 's' : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowInput(s => !s); setErro('') }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Adicionar usuário
          </button>
          <button
            onClick={handleDeletar}
            title="Excluir empresa"
            className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {showInput && (
        <form onSubmit={handleAdicionar} className="px-5 py-3 border-b border-slate-50 flex gap-2 items-center bg-slate-50/50">
          <Mail className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            type="email" required
            value={emailInput}
            onChange={e => { setEmailInput(e.target.value); setErro('') }}
            placeholder="email@dominio.com (já cadastrado no sistema)"
            className="flex-1 text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-400 bg-white"
          />
          <button type="submit" disabled={adicionando} className="px-3 py-2 bg-indigo-600 text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors whitespace-nowrap">
            {adicionando ? 'Adicionando...' : 'Confirmar'}
          </button>
          <button type="button" onClick={() => { setShowInput(false); setErro('') }} className="p-2 text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </form>
      )}

      {erro && <p className="px-5 py-2 text-xs text-red-600 bg-red-50 border-b border-red-100">{erro}</p>}

      <div className="divide-y divide-slate-50">
        {membros.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-400 text-center">Nenhum usuário nesta empresa ainda.</p>
        ) : (
          membros.map(u => (
            <div key={u.id} className={`flex items-center justify-between px-5 py-3 ${!u.ativo ? 'opacity-50' : ''}`}>
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500">
                  {(u.nome || u.email)[0].toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-800">{u.nome}</p>
                  <p className="text-xs text-slate-400">{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[u.role] ?? 'bg-slate-100 text-slate-500'}`}>{u.role}</span>
                <button
                  onClick={() => handleRemover(u.id)}
                  title="Remover da empresa"
                  className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                >
                  <UserMinus className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────
export default function AdminUsuarios() {
  const { token, usuario, logout, isAdmin, isComando, empresaConfig, refreshEmpresaConfig } = useAuth()
  const navigate = useNavigate()

  const [usuarios, setUsuarios] = useState([])
  const [conexoes, setConexoes] = useState([])
  const [empresas, setEmpresas] = useState({ empresas: [], sem_empresa: [] })
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [msg, setMsg] = useState('')
  const [aba, setAba] = useState('usuarios') // 'usuarios' | 'empresas' | 'permissoes'
  const [novaEmpresa, setNovaEmpresa] = useState('')
  const [criandoEmpresa, setCriandoEmpresa] = useState(false)

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', nome: '', senha: '', role: 'operador', empresa_id: '' })
  const [auditoria, setAuditoria] = useState([])
  const [formErro, setFormErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  // Branding da empresa
  const [editandoBrand, setEditandoBrand] = useState(false)
  const [nomeEmpresaEdit, setNomeEmpresaEdit] = useState('')
  const [salvandoBrand, setSalvandoBrand] = useState(false)
  const [msgBrand, setMsgBrand] = useState('')
  const fotoInputRef = useRef(null)

  useEffect(() => {
    if (!isAdmin && !isComando) { navigate('/'); return }
    carregar()
  }, [])

  async function carregar() {
    setCarregando(true); setErro('')
    try {
      const [lista, conxs, emps, audit] = await Promise.all([
        listarUsuarios(token),
        isAdmin || isComando ? listarConexoes() : Promise.resolve([]),
        isComando ? listarEmpresas(token) : Promise.resolve({ empresas: [], sem_empresa: [] }),
        buscarAuditoria({ limit: 10 }),
      ])
      setUsuarios(lista)
      setConexoes(conxs)
      setEmpresas(emps)
      setAuditoria(audit)
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  async function carregarEmpresas() {
    try {
      const emps = await listarEmpresas(token)
      setEmpresas(emps)
    } catch (e) { setErro(e.message) }
  }

  async function handleCriarEmpresa(e) {
    e.preventDefault()
    const id = novaEmpresa.trim().toLowerCase().replace(/\s+/g, '_')
    if (!id) return
    setCriandoEmpresa(true)
    try {
      // Empresa é criada implicitamente ao adicionar o primeiro usuário.
      // Aqui apenas abrimos a empresa vazia na lista local.
      setEmpresas(prev => ({
        ...prev,
        empresas: [...prev.empresas, { empresa_id: id, usuarios: [] }],
      }))
      setNovaEmpresa('')
      flash(`Empresa "${id}" criada. Adicione usuários a ela.`)
    } finally { setCriandoEmpresa(false) }
  }

  function flash(texto) { setMsg(texto); setTimeout(() => setMsg(''), 3500) }
  function flashBrand(texto) { setMsgBrand(texto); setTimeout(() => setMsgBrand(''), 4000) }

  function abrirEdicaoBrand() {
    setNomeEmpresaEdit(empresaConfig?.nome_exibicao || usuario?.empresa_id || '')
    setEditandoBrand(true)
  }

  async function handleSalvarNome() {
    setSalvandoBrand(true)
    try {
      await putEmpresaConfig(token, { nome_exibicao: nomeEmpresaEdit })
      refreshEmpresaConfig()
      setEditandoBrand(false)
      flashBrand('Nome atualizado.')
    } catch (e) { flashBrand(e.message) } finally { setSalvandoBrand(false) }
  }

  async function handleFotoChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setSalvandoBrand(true)
    try {
      await uploadEmpresaFoto(token, file)
      refreshEmpresaConfig()
      flashBrand('Foto atualizada.')
    } catch (e) { flashBrand(e.message) } finally { setSalvandoBrand(false) }
  }

  async function handleToggleAtivo(u) {
    try {
      await toggleUsuarioAtivo(token, u.id, !u.ativo)
      flash(`${u.nome} ${!u.ativo ? 'ativado' : 'desativado'}.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, ativo: !u.ativo } : x))
    } catch (e) { setErro(e.message) }
  }

  async function handleToggleRole(u) {
    const novo = u.role === 'admin' ? 'operador' : 'admin'
    if (!confirm(`Alterar ${u.nome} para ${novo}?`)) return
    try {
      await alterarRoleUsuario(token, u.id, novo)
      flash(`Permissão de ${u.nome} alterada para ${novo}.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, role: novo } : x))
    } catch (e) { setErro(e.message) }
  }

  async function handleRegistrar(e) {
    e.preventDefault(); setFormErro(''); setSalvando(true)
    try {
      await registrarUsuario(token, form)
      flash(`Usuário ${form.email} criado.`)
      setForm({ email: '', nome: '', senha: '', role: 'operador', empresa_id: '' })
      setShowForm(false)
      carregar()
    } catch (e) { setFormErro(e.message) } finally { setSalvando(false) }
  }

  const usuariosExibidos = isAdmin
    ? usuarios.filter(u => u.role !== 'comando')
    : usuarios

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(isComando ? '/comando' : '/admin')} className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-lg hover:bg-slate-100">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Logo />
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          <span className="text-slate-200 text-sm">/</span>
          <span className="text-slate-500 text-sm">Usuários</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400 hidden sm:block">{usuario?.nome}</span>
          <button onClick={logout} className="nav-link-danger"><LogOut className="w-4 h-4" /> Sair</button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* Abas */}
        {(isAdmin || isComando) && (
          <div className="flex gap-1 mb-8 bg-slate-100 p-1 rounded-xl w-fit">
            {[
              ['usuarios', <Users className="w-4 h-4" />, 'Usuários'],
              ...(isComando ? [['empresas', <Building2 className="w-4 h-4" />, 'Empresas']] : []),
              ['permissoes', <Database className="w-4 h-4" />, 'Permissões de Banco'],
            ].map(([id, icon, label]) => (
              <button
                key={id}
                onClick={() => setAba(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${aba === id ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              >
                {icon}{label}
              </button>
            ))}
          </div>
        )}

        {msg && <div className="mb-5 bg-emerald-50 border border-emerald-100 text-emerald-700 rounded-xl px-4 py-3 text-sm">{msg}</div>}
        {erro && <div className="mb-5 bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3 text-sm">{erro}</div>}

        {/* ── ABA USUÁRIOS ── */}
        {aba === 'usuarios' && (
          <>
            {/* Perfil da empresa (admin/comando) */}
            {(isAdmin || isComando) && usuario?.empresa_id && (
              <div className="mb-8 bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] p-5">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5" /> Perfil da empresa
                  </p>
                  {!editandoBrand ? (
                    <button onClick={abrirEdicaoBrand} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors font-semibold">
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                  ) : (
                    <button onClick={() => setEditandoBrand(false)} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
                      Cancelar
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  {/* Foto */}
                  <div className="relative shrink-0">
                    <div className="w-16 h-16 rounded-2xl overflow-hidden bg-slate-100 border border-slate-200 flex items-center justify-center">
                      {empresaConfig?.foto_url
                        ? <img src={empresaConfig.foto_url} alt="Logo" className="w-full h-full object-cover" />
                        : <Building2 className="w-6 h-6 text-slate-400" />}
                    </div>
                    {editandoBrand && (
                      <label
                        className="absolute -bottom-1.5 -right-1.5 w-7 h-7 bg-blue-600 hover:bg-blue-700 rounded-full flex items-center justify-center cursor-pointer transition-colors shadow-md"
                        title="Trocar foto"
                      >
                        <Camera className="w-3.5 h-3.5 text-white" />
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          className="hidden"
                          ref={fotoInputRef}
                          onChange={handleFotoChange}
                        />
                      </label>
                    )}
                  </div>

                  {/* Nome */}
                  <div className="flex-1 min-w-0">
                    {editandoBrand ? (
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={nomeEmpresaEdit}
                          onChange={e => setNomeEmpresaEdit(e.target.value)}
                          placeholder="Nome de exibição"
                          className="flex-1 text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-400"
                        />
                        <button
                          onClick={handleSalvarNome}
                          disabled={salvandoBrand}
                          className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white text-xs font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
                        >
                          <Check className="w-3.5 h-3.5" />
                          {salvandoBrand ? 'Salvando...' : 'Salvar nome'}
                        </button>
                      </div>
                    ) : (
                      <>
                        <p className="font-bold text-slate-900 text-base truncate">
                          {empresaConfig?.nome_exibicao || usuario?.empresa_id}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">ID: {usuario?.empresa_id}</p>
                      </>
                    )}
                  </div>
                </div>

                {msgBrand && (
                  <p className="mt-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                    {msgBrand}
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">Usuários do sistema</h1>
                <p className="text-sm text-slate-500 mt-1">
                  {isComando ? 'Gerencie todos os usuários e empresas.' : 'Gerencie os operadores da sua empresa.'}
                </p>
              </div>
              {isComando && (
                <button onClick={() => { setShowForm(!showForm); setFormErro('') }} className="btn-primary">
                  <UserPlus className="w-4 h-4" /> Novo usuário
                </button>
              )}
            </div>

            {/* Formulário de criação — apenas COMANDO */}
            {isComando && showForm && (
              <div className="mb-6 bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] p-6">
                <h2 className="text-sm font-bold text-slate-800 mb-5">Criar novo usuário</h2>
                <form onSubmit={handleRegistrar} className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Nome completo</label>
                    <input type="text" required value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} className="input-base" placeholder="João Silva" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">E-mail</label>
                    <input type="email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="input-base" placeholder="joao@empresa.com" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Senha inicial</label>
                    <input type="password" required minLength={6} value={form.senha} onChange={e => setForm(f => ({ ...f, senha: e.target.value }))} className="input-base" placeholder="mínimo 6 caracteres" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Permissão</label>
                    <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} className="input-base">
                      <option value="operador">Operador</option>
                      <option value="admin">Administrador</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Empresa</label>
                    <select
                      required
                      value={form.empresa_id}
                      onChange={e => setForm(f => ({ ...f, empresa_id: e.target.value }))}
                      className="input-base"
                    >
                      <option value="">— selecione uma empresa —</option>
                      {(empresas.empresas || []).map(emp => (
                        <option key={emp.empresa_id} value={emp.empresa_id}>
                          {emp.empresa_id} ({emp.usuarios?.length ?? 0} membros)
                        </option>
                      ))}
                      <option value="__nova__">+ Nova empresa...</option>
                    </select>
                    {form.empresa_id === '__nova__' && (
                      <input
                        type="text"
                        required
                        autoFocus
                        className="input-base mt-2"
                        placeholder="ID da nova empresa (ex: bradesco)"
                        onChange={e => setForm(f => ({ ...f, empresa_id: e.target.value.trim().toLowerCase() }))}
                      />
                    )}
                    <p className="text-xs text-slate-400 mt-1">Usuários da mesma empresa compartilham dados entre si.</p>
                  </div>

                  {formErro && <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-2">{formErro}</p>}

                  <div className="col-span-2 flex gap-3 justify-end pt-1">
                    <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors">Cancelar</button>
                    <button type="submit" disabled={salvando} className="btn-primary disabled:opacity-50">{salvando ? 'Criando...' : 'Criar usuário'}</button>
                  </div>
                </form>
              </div>
            )}

            {/* Tabela de usuários */}
            {carregando ? (
              <div className="text-center py-16 text-slate-400 text-sm">Carregando...</div>
            ) : (
              <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100">
                      <th className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Nome</th>
                      <th className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">E-mail</th>
                      {isComando && <th className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Empresa</th>}
                      <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Permissão</th>
                      <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                      <th className="text-center px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuariosExibidos.map(u => (
                      <tr key={u.id} className={`border-b border-slate-50 last:border-0 hover:bg-slate-50/50 transition-colors ${!u.ativo ? 'opacity-50' : ''}`}>
                        <td className="px-5 py-4 font-medium text-slate-900">{u.nome}</td>
                        <td className="px-5 py-4 text-slate-500">{u.email}</td>
                        {isComando && <td className="px-5 py-4 text-slate-400 text-xs">{u.empresa_id || '—'}</td>}
                        <td className="px-5 py-4 text-center"><BadgeRole role={u.role} /></td>
                        <td className="px-5 py-4 text-center">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${u.ativo ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/60' : 'bg-slate-100 text-slate-400 ring-1 ring-slate-200/60'}`}>
                            {u.ativo ? 'Ativo' : 'Inativo'}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center justify-center gap-1">
                            {u.email !== usuario?.email && u.role !== 'comando' ? (
                              <>
                                <button onClick={() => handleToggleAtivo(u)} title={u.ativo ? 'Desativar' : 'Ativar'} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
                                  {u.ativo ? <ToggleRight className="w-5 h-5 text-emerald-500" /> : <ToggleLeft className="w-5 h-5" />}
                                </button>
                                {isComando && (
                                  <button onClick={() => handleToggleRole(u)} title={u.role === 'admin' ? 'Rebaixar para operador' : 'Promover a admin'} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
                                    {u.role === 'admin' ? <ShieldOff className="w-4 h-4 text-violet-500" /> : <ShieldCheck className="w-4 h-4" />}
                                  </button>
                                )}
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
                {usuariosExibidos.length === 0 && (
                  <div className="text-center py-12 text-slate-400 text-sm">Nenhum usuário encontrado.</div>
                )}
              </div>
            )}
            <p className="mt-4 text-xs text-slate-400">
              Total: {usuariosExibidos.length} usuário{usuariosExibidos.length !== 1 ? 's' : ''} · Ativos: {usuariosExibidos.filter(u => u.ativo).length}
            </p>

            {/* ── Atividade Recente ── */}
            {auditoria.length > 0 && (
              <div className="mt-10">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <Clock className="h-3 w-3" /> Atividade Recente
                </p>
                <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] divide-y divide-slate-50 overflow-hidden">
                  {auditoria.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${ACAO_COR[a.acao] ?? 'bg-slate-300'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-slate-800 font-medium leading-snug">
                          {ACAO_LABEL[a.acao] || a.acao}
                          {a.detalhes?.email_novo && (
                            <span className="font-normal text-slate-500"> — {a.detalhes.email_novo}</span>
                          )}
                          {a.detalhes?.email_alvo && (
                            <span className="font-normal text-slate-500"> — {a.detalhes.email_alvo}</span>
                          )}
                          {a.detalhes?.nome_arquivo && (
                            <span className="font-normal text-slate-500"> — {a.detalhes.nome_arquivo}</span>
                          )}
                          {a.detalhes?.n_devedores != null && (
                            <span className="font-normal text-slate-500"> · {a.detalhes.n_devedores} devedores</span>
                          )}
                          {a.detalhes?.importados != null && (
                            <span className="font-normal text-slate-500"> · {a.detalhes.importados} importados</span>
                          )}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          por <span className="font-medium">{a.usuario_email || '—'}</span>
                          {a.empresa_id && <span className="text-slate-300"> · {a.empresa_id}</span>}
                          <span className="ml-1">· {fmtAuditDate(a.created_at)}</span>
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ── ABA EMPRESAS (apenas comando) ── */}
        {aba === 'empresas' && isComando && (
          <>
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">Empresas parceiras</h1>
                <p className="text-sm text-slate-500 mt-1">Agrupe usuários por empresa. Adicione pelo e-mail de contas já cadastradas.</p>
              </div>
            </div>

            {/* Formulário nova empresa */}
            <form onSubmit={handleCriarEmpresa} className="mb-6 flex gap-3 items-center">
              <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
              <input
                type="text"
                value={novaEmpresa}
                onChange={e => setNovaEmpresa(e.target.value)}
                placeholder="Nome/ID da nova empresa (ex: sicoob, bradesco)"
                className="flex-1 text-sm border border-slate-200 rounded-xl px-4 py-2.5 focus:outline-none focus:border-indigo-400 bg-white shadow-sm"
              />
              <button
                type="submit"
                disabled={criandoEmpresa || !novaEmpresa.trim()}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-40 transition-colors whitespace-nowrap"
              >
                <Plus className="w-4 h-4" />
                {criandoEmpresa ? 'Criando...' : 'Nova empresa'}
              </button>
            </form>

            {carregando ? (
              <div className="text-center py-16 text-slate-400 text-sm">Carregando...</div>
            ) : (
              <div className="space-y-5">
                {empresas.empresas.length === 0 && (
                  <div className="text-center py-12 text-slate-400 text-sm">Nenhuma empresa cadastrada ainda. Crie uma acima.</div>
                )}
                {empresas.empresas.map(emp => (
                  <CardEmpresa key={emp.empresa_id} empresa={emp} token={token} onAtualizar={carregarEmpresas} />
                ))}
                {empresas.sem_empresa?.length > 0 && (
                  <div className="mt-8">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Sem empresa atribuída ({empresas.sem_empresa.length})</p>
                    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.06)] divide-y divide-slate-50 overflow-hidden">
                      {empresas.sem_empresa.map(u => (
                        <div key={u.id} className="flex items-center gap-3 px-5 py-3">
                          <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500 shrink-0">
                            {(u.nome || u.email)[0].toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-800 truncate">{u.nome}</p>
                            <p className="text-xs text-slate-400 truncate">{u.email}</p>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${ROLE_BADGE[u.role] ?? 'bg-slate-100 text-slate-500'}`}>{u.role}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ── ABA PERMISSÕES DE BANCO ── */}
        {aba === 'permissoes' && (isAdmin || isComando) && (
          <>
            <div className="mb-8">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Permissões de banco de dados</h1>
              <p className="text-sm text-slate-500 mt-1">Controle quais operadores podem sincronizar cada conexão cadastrada.</p>
            </div>

            {carregando ? (
              <div className="text-center py-16 text-slate-400 text-sm">Carregando...</div>
            ) : conexoes.length === 0 ? (
              <div className="text-center py-16 text-slate-400 text-sm">Nenhuma conexão cadastrada ainda.</div>
            ) : (
              <div className="space-y-3">
                {conexoes.map(c => (
                  <PainelPermissoes key={c.id} conexao={c} operadores={usuarios} token={token} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
