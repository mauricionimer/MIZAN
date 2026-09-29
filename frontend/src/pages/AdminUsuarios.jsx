import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  listarUsuarios, registrarUsuario, toggleUsuarioAtivo, alterarRoleUsuario,
  listarConexoes, listarPermissoesConexao, concederPermissaoConexao, revogarPermissaoConexao,
  listarEmpresas, adicionarUsuarioEmpresa, removerUsuarioEmpresa, deletarEmpresa,
  buscarAuditoria, putEmpresaConfig, uploadEmpresaFoto, getEmpresaConfigPublica,
} from '../api'
import {
  Users, UserPlus, LogOut, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight,
  ArrowLeft, Database, Lock, Unlock, ChevronDown, ChevronUp,
  Building2, Plus, X, UserMinus, Mail, Trash2, Clock, Camera, Pencil, Check,
} from 'lucide-react'
import { LogoMark } from '../components/Logo'

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
  return <LogoMark className="h-5 w-5 shrink-0" />
}

const ROLE_BADGE = {
  comando:  'bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/20',
  admin:    'bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20',
  operador: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
}

function BadgeRole({ role }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[role] ?? 'bg-slate-500/10 text-ink-2 ring-1 ring-slate-500/20'}`}>
      {role === 'admin' && <ShieldCheck className="w-3 h-3" />}
      {role}
    </span>
  )
}

// ── Card de permissões de uma conexão ────────────────────────────────────────
const TIPO_COR = {
  postgres:   'bg-sky-500/10 text-sky-400 ring-sky-500/20',
  postgresql: 'bg-sky-500/10 text-sky-400 ring-sky-500/20',
  mysql:      'bg-orange-500/10 text-orange-400 ring-orange-500/20',
  mariadb:    'bg-orange-500/10 text-orange-400 ring-orange-500/20',
  sqlserver:  'bg-blue-500/10 text-blue-400 ring-blue-500/20',
  oracle:     'bg-red-500/10 text-red-400 ring-red-500/20',
  sqlite:     'bg-raise-2 text-ink-2 ring-line',
  sheets:     'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
}

function CardPermissoes({ conexao, operadores, token }) {
  const [permitidos, setPermitidos] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(null) // id do op em salvamento

  async function carregar() {
    try {
      const data = await listarPermissoesConexao(token, conexao.id)
      setPermitidos(data.map(o => o.id))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => { carregar() }, [])

  async function conceder(op) {
    setSalvando(op.id)
    try {
      await concederPermissaoConexao(token, conexao.id, op.id)
      setPermitidos(p => [...p, op.id])
    } finally { setSalvando(null) }
  }

  async function revogar(op) {
    setSalvando(op.id)
    try {
      await revogarPermissaoConexao(token, conexao.id, op.id)
      setPermitidos(p => p.filter(id => id !== op.id))
    } finally { setSalvando(null) }
  }

  const somenteOperadores = operadores.filter(o => (o.role === 'operador' || o.role === 'admin') && o.ativo)
  const comAcesso    = somenteOperadores.filter(o => permitidos.includes(o.id))
  const semAcesso    = somenteOperadores.filter(o => !permitidos.includes(o.id))
  const tipoCor      = TIPO_COR[conexao.tipo] ?? 'bg-slate-500/10 text-ink-2 ring-1 ring-slate-500/20'

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
      <div className="flex items-center gap-3 px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'var(--raise-3)' }}>
          <Database className="w-4 h-4" style={{ color: 'var(--ink-2)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-bold text-ink text-sm">{conexao.nome}</p>
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ring-1 ${tipoCor}`}>{conexao.tipo}</span>
          </div>
          {conexao.host && <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ink-3)' }}>{conexao.host}{conexao.porta ? `:${conexao.porta}` : ''}{conexao.banco ? ` · ${conexao.banco}` : ''}</p>}
        </div>
        <span className="text-xs shrink-0" style={{ color: 'var(--ink-3)' }}>{comAcesso.length}/{somenteOperadores.length} com acesso</span>
      </div>
      {carregando ? (
        <div className="px-5 py-6 text-xs" style={{ color: 'var(--ink-3)' }}>Carregando...</div>
      ) : somenteOperadores.length === 0 ? (
        <div className="px-5 py-6 text-xs" style={{ color: 'var(--ink-3)' }}>Nenhum operador ou admin ativo nesta empresa.</div>
      ) : (
        <div>
          {comAcesso.length > 0 && (
            <div className="px-5 py-3">
              <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                <Unlock className="w-3 h-3" /> Com acesso ({comAcesso.length})
              </p>
              <div className="space-y-1.5">
                {comAcesso.map(op => (
                  <div key={op.id} className="flex items-center justify-between py-1 px-3 rounded-xl" style={{ background: 'rgb(var(--c-success) / 0.06)' }}>
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-emerald-400 shrink-0" style={{ background: 'rgb(var(--c-success) / 0.15)' }}>
                        {(op.nome || op.email)[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink truncate">{op.nome}</p>
                        <p className="text-xs truncate" style={{ color: 'var(--ink-3)' }}>{op.email}</p>
                      </div>
                    </div>
                    <button onClick={() => revogar(op)} disabled={salvando === op.id} title="Revogar acesso"
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 shrink-0 ml-2"
                      style={{ color: 'var(--ink-3)' }}
                      onMouseOver={e => { e.currentTarget.style.background = 'rgb(var(--c-danger) / 0.08)'; e.currentTarget.style.color = 'var(--danger)' }}
                      onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-3)' }}>
                      <X className="w-3.5 h-3.5" />{salvando === op.id ? '...' : 'Remover'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
          {semAcesso.length > 0 && (
            <div className="px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide mb-2 flex items-center gap-1" style={{ color: 'var(--ink-3)' }}>
                <Lock className="w-3 h-3" /> Sem acesso ({semAcesso.length})
              </p>
              <div className="space-y-1.5">
                {semAcesso.map(op => (
                  <div key={op.id} className="flex items-center justify-between py-1 px-3 rounded-xl transition-colors"
                    onMouseOver={e => e.currentTarget.style.background = 'var(--raise-1)'}
                    onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0" style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>
                        {(op.nome || op.email)[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--ink-2)' }}>{op.nome}</p>
                        <p className="text-xs truncate" style={{ color: 'var(--ink-3)' }}>{op.email}</p>
                      </div>
                    </div>
                    <button onClick={() => conceder(op)} disabled={salvando === op.id} title="Conceder acesso"
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-blue-400 transition-colors disabled:opacity-40 shrink-0 ml-2"
                      onMouseOver={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.10)'}
                      onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                      <Plus className="w-3.5 h-3.5" />{salvando === op.id ? '...' : 'Adicionar'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
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
  const usuariosKey = empresa.usuarios.map(u => u.id).sort().join(',')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setMembros(empresa.usuarios) }, [usuariosKey])
  const [adicionando, setAdicionando] = useState(false)
  const [showInput, setShowInput] = useState(false)
  const [erro, setErro] = useState('')

  // Branding
  const [cfg, setCfg]           = useState(null)
  const [editNome, setEditNome] = useState(false)
  const [nomeEdit, setNomeEdit] = useState('')
  const [corEdit, setCorEdit]   = useState('#5966d9')
  const [salvandoNome, setSalvandoNome] = useState(false)
  const [salvandoFoto, setSalvandoFoto] = useState(false)
  const [msgBrand, setMsgBrand] = useState('')
  const fotoRef = useRef(null)

  useEffect(() => {
    getEmpresaConfigPublica(null, empresa.empresa_id).then(c => { if (c) setCfg(c) }).catch(() => {})
  }, [empresa.empresa_id])

  function flashBrand(t) { setMsgBrand(t); setTimeout(() => setMsgBrand(''), 3500) }

  async function handleSalvarNome() {
    setSalvandoNome(true)
    try {
      const r = await putEmpresaConfig(token, { nome_exibicao: nomeEdit, cor_primaria: corEdit }, empresa.empresa_id)
      setCfg(r); setEditNome(false); flashBrand('Perfil atualizado.')
    } catch (e) { flashBrand(e.message) } finally { setSalvandoNome(false) }
  }

  async function handleFoto(e) {
    const file = e.target.files?.[0]; if (!file) return
    setSalvandoFoto(true)
    try {
      await uploadEmpresaFoto(token, file, empresa.empresa_id)
      const r = await getEmpresaConfigPublica(null, empresa.empresa_id)
      if (r) setCfg(r); flashBrand('Foto atualizada.')
    } catch (e) { flashBrand(e.message) } finally { setSalvandoFoto(false) }
  }

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

  const nomeExibicao = cfg?.nome_exibicao || empresa.empresa_id

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
      <div className="px-5 py-4 border-b flex items-center justify-between gap-3" style={{ borderColor: 'var(--line)' }}>
        <div className="relative shrink-0">
          <div className="w-10 h-10 rounded-xl overflow-hidden flex items-center justify-center" style={{ background: 'rgb(var(--c-royal) / 0.12)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
            {cfg?.foto_url
              ? <img src={cfg.foto_url} alt={nomeExibicao} className="w-full h-full object-cover" />
              : <Building2 className="w-4 h-4 text-indigo-400" />}
          </div>
          <label
            className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center cursor-pointer transition-colors shadow"
            style={{ background: 'var(--raised)' }}
            title="Trocar foto"
            onMouseOver={e => e.currentTarget.style.background = 'var(--accent-text)'}
            onMouseOut={e => e.currentTarget.style.background = 'var(--raised)'}>
            {salvandoFoto
              ? <span className="text-ink text-[8px]">...</span>
              : <Camera className="w-2.5 h-2.5 text-ink" />}
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" ref={fotoRef} onChange={handleFoto} />
          </label>
        </div>

        <div className="flex-1 min-w-0">
          {editNome ? (
            <div className="flex gap-1.5 items-center">
              <input autoFocus type="text" value={nomeEdit} onChange={e => setNomeEdit(e.target.value)}
                className="flex-1 text-sm rounded-lg px-2.5 py-1 focus:outline-none"
                style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.30)', color: 'var(--ink)' }}
                placeholder="Nome de exibição" />
              <input type="color" value={corEdit} onChange={e => setCorEdit(e.target.value)}
                title="Cor de destaque" className="w-7 h-7 rounded-md cursor-pointer shrink-0 bg-transparent"
                style={{ border: '1px solid var(--line)' }} />
              <button onClick={handleSalvarNome} disabled={salvandoNome}
                className="px-2.5 py-1 bg-indigo-600 text-brand-ink text-xs rounded-lg hover:bg-indigo-700 disabled:opacity-50">
                <Check className="w-3.5 h-3.5" />
              </button>
              <button onClick={() => setEditNome(false)} className="px-2 py-1 transition-colors" style={{ color: 'var(--ink-3)' }}>
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <div>
                <p className="font-bold text-ink text-sm flex items-center gap-1.5">
                  {nomeExibicao}
                  <span className="inline-block w-2 h-2 rounded-full border border-line-2 shrink-0" style={{ background: cfg?.cor_primaria || '#5966d9' }} />
                </p>
                {cfg?.nome_exibicao && <p className="text-xs" style={{ color: 'var(--ink-3)' }}>ID: {empresa.empresa_id}</p>}
                <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{membros.length} membro{membros.length !== 1 ? 's' : ''}</p>
              </div>
              <button onClick={() => { setNomeEdit(nomeExibicao); setCorEdit(cfg?.cor_primaria || '#5966d9'); setEditNome(true) }}
                className="p-1 rounded transition-colors" title="Editar nome e cor" style={{ color: 'var(--ink-4)' }}
                onMouseOver={e => e.currentTarget.style.color = 'var(--accent-text)'}
                onMouseOut={e => e.currentTarget.style.color = 'var(--ink-4)'}>
                <Pencil className="w-3 h-3" />
              </button>
            </div>
          )}
          {msgBrand && <p className="text-xs text-emerald-400 mt-0.5">{msgBrand}</p>}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => { setShowInput(s => !s); setErro('') }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-indigo-400 transition-colors"
            style={{ background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}
            onMouseOver={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.18)'}
            onMouseOut={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.10)'}>
            <Plus className="w-3.5 h-3.5" /> Adicionar usuário
          </button>
          <button onClick={handleDeletar} title="Excluir empresa"
            className="p-1.5 rounded-lg transition-colors" style={{ color: 'var(--ink-4)' }}
            onMouseOver={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgb(var(--c-danger) / 0.08)' }}
            onMouseOut={e => { e.currentTarget.style.color = 'var(--ink-4)'; e.currentTarget.style.background = 'transparent' }}>
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {showInput && (
        <form onSubmit={handleAdicionar} className="px-5 py-3 border-b flex gap-2 items-center" style={{ borderColor: 'var(--line)', background: 'var(--raise-1)' }}>
          <Mail className="w-4 h-4 shrink-0" style={{ color: 'var(--ink-3)' }} />
          <input type="email" required value={emailInput} onChange={e => { setEmailInput(e.target.value); setErro('') }}
            placeholder="email@dominio.com (já cadastrado no sistema)"
            className="flex-1 text-sm rounded-xl px-3 py-2 focus:outline-none"
            style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.25)', color: 'var(--ink)' }} />
          <button type="submit" disabled={adicionando} className="px-3 py-2 bg-indigo-600 text-brand-ink text-xs font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors whitespace-nowrap">
            {adicionando ? 'Adicionando...' : 'Confirmar'}
          </button>
          <button type="button" onClick={() => { setShowInput(false); setErro('') }} className="p-2 transition-colors" style={{ color: 'var(--ink-3)' }}>
            <X className="w-4 h-4" />
          </button>
        </form>
      )}

      {erro && <p className="px-5 py-2 text-xs text-red-400 border-b" style={{ background: 'rgb(var(--c-danger) / 0.08)', borderColor: 'rgb(var(--c-danger) / 0.15)' }}>{erro}</p>}

      <div>
        {membros.length === 0 ? (
          <p className="px-5 py-4 text-sm text-center" style={{ color: 'var(--ink-3)' }}>Nenhum usuário nesta empresa ainda.</p>
        ) : (
          membros.map(u => (
            <div key={u.id} className={`flex items-center justify-between px-5 py-3 border-b ${!u.ativo ? 'opacity-50' : ''}`} style={{ borderColor: 'var(--line)' }}>
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>
                  {(u.nome || u.email)[0].toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-medium text-ink">{u.nome}</p>
                  <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[u.role] ?? 'bg-raise-2 text-ink-2'}`}>{u.role}</span>
                <button onClick={() => handleRemover(u.id)} title="Remover da empresa"
                  className="p-1.5 rounded-lg transition-colors" style={{ color: 'var(--ink-4)' }}
                  onMouseOver={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgb(var(--c-danger) / 0.08)' }}
                  onMouseOut={e => { e.currentTarget.style.color = 'var(--ink-4)'; e.currentTarget.style.background = 'transparent' }}>
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
// Um degrau por papel: o botão da linha desce quem está acima e sobe quem
// está abaixo. Promover ALGUÉM a comando é decisão de outra ordem e fica no
// formulário de criação, não num botão de linha.
const ROTULO_ROLE = {
  comando:  { destino: 'admin',    acao: 'Rebaixar', desce: true,  titulo: 'Rebaixar para administrador' },
  admin:    { destino: 'operador', acao: 'Rebaixar', desce: true,  titulo: 'Rebaixar para operador' },
  operador: { destino: 'admin',    acao: 'Promover', desce: false, titulo: 'Promover a administrador' },
}

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
  const [corEmpresaEdit, setCorEmpresaEdit] = useState('#5966d9')
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
    setCorEmpresaEdit(empresaConfig?.cor_primaria || '#5966d9')
    setEditandoBrand(true)
  }

  async function handleSalvarNome() {
    setSalvandoBrand(true)
    try {
      await putEmpresaConfig(token, { nome_exibicao: nomeEmpresaEdit, cor_primaria: corEmpresaEdit })
      refreshEmpresaConfig()
      setEditandoBrand(false)
      flashBrand('Perfil da empresa atualizado.')
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
    const novo = ROTULO_ROLE[u.role]?.destino || 'admin'
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
          <button onClick={() => navigate(isComando ? '/comando' : '/')} className="p-1 rounded-lg transition-colors hover:bg-raise-2" style={{ color: 'var(--ink-3)' }}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Logo />
          <span className="font-bold text-ink text-sm">Mizan</span>
          <span className="text-ink-4 text-sm">/</span>
          <span className="text-sm" style={{ color: 'var(--ink-2)' }}>Usuários</span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button onClick={() => navigate('/auditoria')} className="nav-link"><ShieldCheck className="w-4 h-4" /> Auditoria</button>
          <span className="text-sm hidden sm:block" style={{ color: 'var(--ink-3)' }}>{usuario?.nome}</span>
          <button onClick={logout} className="nav-link-danger"><LogOut className="w-4 h-4" /> Sair</button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* Abas */}
        {(isAdmin || isComando) && (
          <div className="flex gap-1 mb-8 p-1 rounded-xl w-fit" style={{ background: 'var(--raise-2)' }}>
            {[
              ['usuarios', <Users className="w-4 h-4" />, 'Usuários'],
              ...(isComando ? [['empresas', <Building2 className="w-4 h-4" />, 'Empresas']] : []),
              ['permissoes', <Database className="w-4 h-4" />, 'Permissões de Banco'],
            ].map(([id, icon, label]) => (
              <button key={id} onClick={() => setAba(id)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                style={aba === id ? { background: 'var(--surface)', color: 'var(--ink)', boxShadow: '0 1px 4px rgba(0,0,0,0.30)' } : { color: 'var(--ink-3)' }}>
                {icon}{label}
              </button>
            ))}
          </div>
        )}

        {msg && <div className="mb-5 text-emerald-400 rounded-xl px-4 py-3 text-sm" style={{ background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>{msg}</div>}
        {erro && <div className="mb-5 text-red-400 rounded-xl px-4 py-3 text-sm" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>{erro}</div>}

        {/* ── ABA USUÁRIOS ── */}
        {aba === 'usuarios' && (
          <>
            {/* Perfil da empresa (admin/comando) */}
            {(isAdmin || isComando) && usuario?.empresa_id && (
              <div className="mb-8 rounded-2xl p-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs font-semibold uppercase tracking-wide flex items-center gap-1.5" style={{ color: 'var(--ink-3)' }}>
                    <Building2 className="h-3.5 w-3.5" /> Perfil da empresa
                  </p>
                  {!editandoBrand ? (
                    <button onClick={abrirEdicaoBrand} className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors font-semibold">
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                  ) : (
                    <button onClick={() => setEditandoBrand(false)} className="text-xs transition-colors" style={{ color: 'var(--ink-3)' }}>Cancelar</button>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  <div className="relative shrink-0">
                    <div className="w-16 h-16 rounded-2xl overflow-hidden flex items-center justify-center" style={{ background: 'var(--raise-3)', border: '1px solid var(--line)' }}>
                      {empresaConfig?.foto_url
                        ? <img src={empresaConfig.foto_url} alt="Logo" className="w-full h-full object-cover" />
                        : <Building2 className="w-6 h-6" style={{ color: 'var(--ink-3)' }} />}
                    </div>
                    {editandoBrand && (
                      <label className="absolute -bottom-1.5 -right-1.5 w-7 h-7 bg-blue-600 hover:bg-blue-700 rounded-full flex items-center justify-center cursor-pointer transition-colors shadow-md" title="Trocar foto">
                        <Camera className="w-3.5 h-3.5 text-brand-ink" />
                        <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" ref={fotoInputRef} onChange={handleFotoChange} />
                      </label>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    {editandoBrand ? (
                      <div className="flex gap-2 items-center">
                        <input type="text" value={nomeEmpresaEdit} onChange={e => setNomeEmpresaEdit(e.target.value)} placeholder="Nome de exibição"
                          className="flex-1 text-sm rounded-xl px-3 py-2 focus:outline-none"
                          style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.30)', color: 'var(--ink)' }}
                        />
                        <input type="color" value={corEmpresaEdit} onChange={e => setCorEmpresaEdit(e.target.value)}
                          title="Cor de destaque da empresa"
                          className="w-10 h-9 rounded-lg cursor-pointer shrink-0 bg-transparent"
                          style={{ border: '1px solid var(--line)' }}
                        />
                        <button onClick={handleSalvarNome} disabled={salvandoBrand}
                          className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-brand-ink text-xs font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors shrink-0">
                          <Check className="w-3.5 h-3.5" />{salvandoBrand ? 'Salvando...' : 'Salvar'}
                        </button>
                      </div>
                    ) : (
                      <>
                        <p className="font-bold text-ink text-base truncate">{empresaConfig?.nome_exibicao || usuario?.empresa_id}</p>
                        <p className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: 'var(--ink-3)' }}>
                          ID: {usuario?.empresa_id}
                          <span className="inline-block w-2.5 h-2.5 rounded-full border border-line-2" style={{ background: empresaConfig?.cor_primaria || '#5966d9' }} />
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {msgBrand && (
                  <p className="mt-3 text-xs text-emerald-400 rounded-lg px-3 py-2" style={{ background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.15)' }}>
                    {msgBrand}
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-ink tracking-tight">Usuários do sistema</h1>
                <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>
                  {isComando ? 'Gerencie todos os usuários e empresas.' : 'Gerencie os operadores da sua empresa.'}
                </p>
              </div>
              {isComando && (
                <button onClick={() => { setShowForm(!showForm); setFormErro('') }} className="btn-primary">
                  <UserPlus className="w-4 h-4" /> Novo usuário
                </button>
              )}
            </div>

            {isComando && showForm && (
              <div className="mb-6 rounded-2xl p-6" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                <h2 className="text-sm font-bold text-ink mb-5">Criar novo usuário</h2>
                <form onSubmit={handleRegistrar} className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Nome completo</label>
                    <input type="text" required value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} className="input-base" placeholder="João Silva" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>E-mail</label>
                    <input type="email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="input-base" placeholder="joao@empresa.com" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Senha inicial</label>
                    <input type="password" required minLength={6} value={form.senha} onChange={e => setForm(f => ({ ...f, senha: e.target.value }))} className="input-base" placeholder="mínimo 6 caracteres" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Permissão</label>
                    <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} className="input-base">
                      <option value="operador">Operador</option>
                      <option value="admin">Administrador</option>
                      <option value="comando">Comando (plataforma)</option>
                    </select>
                    {form.role === 'comando' && (
                      <p className="text-xs mt-1.5" style={{ color: 'var(--warning)' }}>
                        Acesso total à plataforma: todas as empresas, todos os dados,
                        gestão de modelo. Não pertence a nenhuma empresa cliente.
                      </p>
                    )}
                  </div>
                  <div className={`col-span-2 ${form.role === 'comando' ? 'hidden' : ''}`}>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Empresa</label>
                    <select required={form.role !== 'comando'} value={form.empresa_id} onChange={e => setForm(f => ({ ...f, empresa_id: e.target.value }))} className="input-base">
                      <option value="">— selecione uma empresa —</option>
                      {(empresas.empresas || []).map(emp => (
                        <option key={emp.empresa_id} value={emp.empresa_id}>{emp.empresa_id} ({emp.usuarios?.length ?? 0} membros)</option>
                      ))}
                      <option value="__nova__">+ Nova empresa...</option>
                    </select>
                    {form.empresa_id === '__nova__' && (
                      <input type="text" required autoFocus className="input-base mt-2" placeholder="ID da nova empresa (ex: bradesco)"
                        onChange={e => setForm(f => ({ ...f, empresa_id: e.target.value.trim().toLowerCase() }))} />
                    )}
                    <p className="text-xs mt-1" style={{ color: 'var(--ink-3)' }}>Usuários da mesma empresa compartilham dados entre si.</p>
                  </div>
                  {formErro && <p className="col-span-2 text-sm text-red-400 rounded-xl px-4 py-2" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>{formErro}</p>}
                  <div className="col-span-2 flex gap-3 justify-end pt-1">
                    <button type="button" onClick={() => setShowForm(false)}
                      className="px-4 py-2 text-sm rounded-xl transition-colors" style={{ color: 'var(--ink-2)' }}
                      onMouseOver={e => e.currentTarget.style.background = 'var(--raise-2)'}
                      onMouseOut={e => e.currentTarget.style.background = 'transparent'}>Cancelar</button>
                    <button type="submit" disabled={salvando} className="btn-primary disabled:opacity-50">{salvando ? 'Criando...' : 'Criar usuário'}</button>
                  </div>
                </form>
              </div>
            )}

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando...</div>
            ) : (
              <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b" style={{ background: 'var(--raised)', borderColor: 'var(--line)' }}>
                      <th className="text-left px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Nome</th>
                      <th className="text-left px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>E-mail</th>
                      {isComando && <th className="text-left px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Empresa</th>}
                      <th className="text-center px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Permissão</th>
                      <th className="text-center px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Status</th>
                      <th className="text-center px-5 py-3.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuariosExibidos.map(u => (
                      <tr key={u.id} className={`border-b transition-colors ${!u.ativo ? 'opacity-50' : ''}`}
                        style={{ borderColor: 'var(--line)' }}
                        onMouseOver={e => e.currentTarget.style.background = 'var(--raise-1)'}
                        onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                        <td className="px-5 py-4 font-medium text-ink">{u.nome}</td>
                        <td className="px-5 py-4" style={{ color: 'var(--ink-2)' }}>{u.email}</td>
                        {isComando && <td className="px-5 py-4 text-xs" style={{ color: 'var(--ink-3)' }}>{u.empresa_id || '—'}</td>}
                        <td className="px-5 py-4 text-center"><BadgeRole role={u.role} /></td>
                        <td className="px-5 py-4 text-center">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${u.ativo ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20' : 'bg-raise-2 text-ink-3 ring-1 ring-line'}`}>
                            {u.ativo ? 'Ativo' : 'Inativo'}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center justify-center gap-1.5">
                            {u.email === usuario?.email ? (
                              <span className="text-xs italic px-2" style={{ color: 'var(--ink-4)' }}>você</span>
                            ) : (
                              <>
                                <button onClick={() => handleToggleAtivo(u)} title={u.ativo ? 'Desativar usuário' : 'Ativar usuário'}
                                  className="flex items-center gap-1 px-2 py-1 rounded-lg transition-colors text-xs font-medium whitespace-nowrap" style={{ color: 'var(--ink-3)' }}
                                  onMouseOver={e => { e.currentTarget.style.background = 'var(--raise-3)'; e.currentTarget.style.color = 'white' }}
                                  onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-3)' }}>
                                  {u.ativo ? <ToggleRight className="w-4 h-4 text-emerald-400 shrink-0" /> : <ToggleLeft className="w-4 h-4 shrink-0" />}
                                  {u.ativo ? 'Desativar' : 'Ativar'}
                                </button>
                                {isComando && (
                                  <button onClick={() => handleToggleRole(u)} title={ROTULO_ROLE[u.role]?.titulo || 'Promover a admin'}
                                    className="flex items-center gap-1 px-2 py-1 rounded-lg transition-colors text-xs font-medium whitespace-nowrap" style={{ color: 'var(--ink-3)' }}
                                    onMouseOver={e => { e.currentTarget.style.background = 'var(--raise-3)'; e.currentTarget.style.color = 'white' }}
                                    onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-3)' }}>
                                    {ROTULO_ROLE[u.role]?.desce
                                      ? <ShieldOff className="w-4 h-4 text-violet-400 shrink-0" />
                                      : <ShieldCheck className="w-4 h-4 shrink-0" />}
                                    {ROTULO_ROLE[u.role]?.acao || 'Promover'}
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {usuariosExibidos.length === 0 && (
                  <div className="text-center py-12 text-sm" style={{ color: 'var(--ink-3)' }}>Nenhum usuário encontrado.</div>
                )}
              </div>
            )}
            <p className="mt-4 text-xs" style={{ color: 'var(--ink-3)' }}>
              Total: {usuariosExibidos.length} usuário{usuariosExibidos.length !== 1 ? 's' : ''} · Ativos: {usuariosExibidos.filter(u => u.ativo).length}
            </p>

            {auditoria.length > 0 && (
              <div className="mt-10">
                <p className="text-xs font-semibold uppercase tracking-wide mb-3 flex items-center gap-1.5" style={{ color: 'var(--ink-3)' }}>
                  <Clock className="h-3 w-3" /> Atividade Recente
                </p>
                <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                  {auditoria.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3.5 border-b" style={{ borderColor: 'var(--line)' }}>
                      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${ACAO_COR[a.acao] ?? 'bg-slate-500'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-ink font-medium leading-snug">
                          {ACAO_LABEL[a.acao] || a.acao}
                          {a.detalhes?.email_novo && <span className="font-normal" style={{ color: 'var(--ink-2)' }}> — {a.detalhes.email_novo}</span>}
                          {a.detalhes?.email_alvo && <span className="font-normal" style={{ color: 'var(--ink-2)' }}> — {a.detalhes.email_alvo}</span>}
                          {a.detalhes?.nome_arquivo && <span className="font-normal" style={{ color: 'var(--ink-2)' }}> — {a.detalhes.nome_arquivo}</span>}
                          {a.detalhes?.n_devedores != null && <span className="font-normal" style={{ color: 'var(--ink-2)' }}> · {a.detalhes.n_devedores} devedores</span>}
                          {a.detalhes?.importados != null && <span className="font-normal" style={{ color: 'var(--ink-2)' }}> · {a.detalhes.importados} importados</span>}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>
                          por <span className="font-medium">{a.usuario_email || '—'}</span>
                          {a.empresa_id && <span style={{ color: 'var(--ink-4)' }}> · {a.empresa_id}</span>}
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
                <h1 className="text-xl font-bold text-ink tracking-tight">Empresas parceiras</h1>
                <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>Agrupe usuários por empresa. Adicione pelo e-mail de contas já cadastradas.</p>
              </div>
            </div>

            <form onSubmit={handleCriarEmpresa} className="mb-6 flex gap-3 items-center">
              <Building2 className="w-4 h-4 shrink-0" style={{ color: 'var(--ink-3)' }} />
              <input type="text" value={novaEmpresa} onChange={e => setNovaEmpresa(e.target.value)}
                placeholder="Nome/ID da nova empresa (ex: sicoob, bradesco)"
                className="flex-1 text-sm rounded-xl px-4 py-2.5 focus:outline-none"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }} />
              <button type="submit" disabled={criandoEmpresa || !novaEmpresa.trim()}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 text-brand-ink text-sm font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-40 transition-colors whitespace-nowrap">
                <Plus className="w-4 h-4" />{criandoEmpresa ? 'Criando...' : 'Nova empresa'}
              </button>
            </form>

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando...</div>
            ) : (
              <div className="space-y-5">
                {empresas.empresas.length === 0 && (
                  <div className="text-center py-12 text-sm" style={{ color: 'var(--ink-3)' }}>Nenhuma empresa cadastrada ainda. Crie uma acima.</div>
                )}
                {empresas.empresas.map(emp => (
                  <CardEmpresa key={emp.empresa_id} empresa={emp} token={token} onAtualizar={carregarEmpresas} />
                ))}
                {empresas.sem_empresa?.length > 0 && (
                  <div className="mt-8">
                    <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ink-3)' }}>Sem empresa atribuída ({empresas.sem_empresa.length})</p>
                    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                      {empresas.sem_empresa.map(u => (
                        <div key={u.id} className="flex items-center gap-3 px-5 py-3 border-b" style={{ borderColor: 'var(--line)' }}>
                          <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0" style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>
                            {(u.nome || u.email)[0].toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-ink truncate">{u.nome}</p>
                            <p className="text-xs truncate" style={{ color: 'var(--ink-3)' }}>{u.email}</p>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${ROLE_BADGE[u.role] ?? 'bg-raise-2 text-ink-2'}`}>{u.role}</span>
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
              <h1 className="text-xl font-bold text-ink tracking-tight">Permissões de banco de dados</h1>
              <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>Controle quais operadores podem sincronizar cada conexão cadastrada.</p>
            </div>

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando...</div>
            ) : conexoes.length === 0 ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Nenhuma conexão cadastrada ainda.</div>
            ) : (
              <div className="space-y-3">
                {conexoes.map(c => (
                  <CardPermissoes key={c.id} conexao={c} operadores={usuarios} token={token} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
