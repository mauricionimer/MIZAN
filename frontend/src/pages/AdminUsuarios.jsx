import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useConfirmar } from '../components/ConfirmarModal'
import { useAuth } from '../context/AuthContext'
import {
  listarUsuarios, registrarUsuario, toggleUsuarioAtivo, alterarRoleUsuario,
  listarConexoes, listarPermissoesConexao, concederPermissaoConexao, revogarPermissaoConexao,
  listarEmpresas, adicionarUsuarioEmpresa, removerUsuarioEmpresa, deletarEmpresa,
  putEmpresaConfig, uploadEmpresaFoto, getEmpresaConfigPublica,
  verDominios, gravarDominios,
} from '../api'
import {
  Users, UserPlus, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight, Database, Lock, Unlock, Building2, Plus, X, UserMinus, Mail, Trash2, Camera, Pencil, Check, AtSign,
} from 'lucide-react'
import DicaAjuda from '../components/DicaAjuda'

// Nome do papel para a tela (o valor gravado continua 'admin', 'comando'...).
const NOME_PAPEL = { comando: 'Comando', admin: 'Administrador', operador: 'Operador' }
const nomePapel = role => NOME_PAPEL[role] ?? role

// Erro em vermelho, anunciado ao leitor de tela.
function MsgErro({ children, className = '' }) {
  if (!children) return null
  return (
    <p role="alert" className={`rounded-xl px-4 py-2 text-sm ${className}`}
      style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>{children}</p>
  )
}

const ROLE_BADGE = {
  comando:  'bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/20',
  admin:    'bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20',
  operador: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
}

function BadgeRole({ role }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[role] ?? 'bg-slate-500/10 text-ink-2 ring-1 ring-slate-500/20'}`}>
      {role === 'admin' && <ShieldCheck className="w-3 h-3" aria-hidden="true" />}
      {nomePapel(role)}
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
  const { pedir, modal } = useConfirmar()
  const [permitidos, setPermitidos] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(null) // id do op em salvamento
  const [erro, setErro] = useState('')

  useEffect(() => {
    let vivo = true
    listarPermissoesConexao(token, conexao.id)
      .then(data => { if (vivo) setPermitidos(data.map(o => o.id)) })
      .catch(e => { if (vivo) setErro(e.message) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [token, conexao.id])

  async function conceder(op) {
    setSalvando(op.id); setErro('')
    try {
      await concederPermissaoConexao(token, conexao.id, op.id)
      setPermitidos(p => [...p, op.id])
    } catch (e) { setErro(e.message) } finally { setSalvando(null) }
  }

  async function revogar(op) {
    const ok = await pedir({ titulo: `Tirar o acesso de ${op.nome || op.email}?`,
      texto: `Deixa de usar a conexão “${conexao.nome}”. Dá para dar o acesso de novo depois.`,
      confirmar: 'Tirar acesso', perigo: true })
    if (!ok) return
    setSalvando(op.id); setErro('')
    try {
      await revogarPermissaoConexao(token, conexao.id, op.id)
      setPermitidos(p => p.filter(id => id !== op.id))
    } catch (e) { setErro(e.message) } finally { setSalvando(null) }
  }

  const somenteOperadores = operadores.filter(o => (o.role === 'operador' || o.role === 'admin') && o.ativo)
  const comAcesso    = somenteOperadores.filter(o => permitidos.includes(o.id))
  const semAcesso    = somenteOperadores.filter(o => !permitidos.includes(o.id))
  const tipoCor      = TIPO_COR[conexao.tipo] ?? 'bg-slate-500/10 text-ink-2 ring-1 ring-slate-500/20'

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
      {modal}
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
      {erro && <MsgErro className="mx-5 mt-3 text-xs">{erro}</MsgErro>}
      {carregando ? (
        <div className="px-5 py-6 text-xs" style={{ color: 'var(--ink-3)' }}>Carregando…</div>
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
                    <button type="button" onClick={() => revogar(op)} disabled={salvando === op.id} title="Tirar acesso" aria-label={`Tirar o acesso de ${op.nome || op.email}`}
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
                    <button type="button" onClick={() => conceder(op)} disabled={salvando === op.id} title="Dar acesso" aria-label={`Dar acesso a ${op.nome || op.email}`}
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
// Domínios de e-mail da empresa: quem digita um e-mail desses no login vê
// "Mizan & <empresa>" com o logo dela. Só o COMANDO grava (ver backend/marca.py).
function DominiosEmpresa({ empresaId, token }) {
  const [dominios, setDominios] = useState([])
  const [texto, setTexto]       = useState('')
  const [editando, setEditando] = useState(false)
  const [erro, setErro]         = useState('')
  const [ocupado, setOcupado]   = useState(false)
  useEffect(() => { verDominios(token, empresaId).then(r => setDominios(r.dominios || [])).catch(() => {}) }, [token, empresaId])

  async function salvar() {
    setOcupado(true); setErro('')
    try {
      const lista = texto.split(/[\s,;]+/).map(d => d.trim()).filter(Boolean)
      const r = await gravarDominios(token, empresaId, lista)
      setDominios(r.dominios); setEditando(false)
    } catch (e) { setErro(e.message) } finally { setOcupado(false) }
  }

  return (
    <div className="px-5 py-3 border-b text-xs" style={{ borderColor: 'var(--line)', color: 'var(--ink-2)' }}>
      <div className="flex flex-wrap items-center gap-2">
        <AtSign className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--ink-3)' }} />
        <span className="font-medium">Marca no login<DicaAjuda id="marca-no-login" />:</span>
        {!editando && (dominios.length
          ? dominios.map(d => <span key={d} className="rounded-md bg-raise-2 px-2 py-0.5 text-ink">@{d}</span>)
          : <span style={{ color: 'var(--ink-3)' }}>nenhum domínio</span>)}
        {!editando && (
          <button type="button" onClick={() => { setTexto(dominios.join(', ')); setEditando(true); setErro('') }}
            aria-label="Editar domínios da marca no login"
            className="ml-auto font-medium" style={{ color: 'var(--accent-text)' }}>Editar</button>
        )}
      </div>
      {editando && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input autoFocus value={texto} onChange={e => setTexto(e.target.value)} aria-label="Domínios de e-mail"
            placeholder="goiasbank.com.br, goias.com.br"
            className="min-w-0 flex-1 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none"
            style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.30)', color: 'var(--ink)' }} />
          <button type="button" onClick={salvar} disabled={ocupado} className="btn-primary btn-sm">Salvar</button>
          <button type="button" onClick={() => setEditando(false)} className="px-2 py-1.5" style={{ color: 'var(--ink-3)' }}>Cancelar</button>
        </div>
      )}
      {erro && <p className="mt-1.5" role="alert" style={{ color: 'var(--danger)' }}>{erro}</p>}
    </div>
  )
}

function CardEmpresa({ empresa, token, onAtualizar }) {
  const { pedir, modal } = useConfirmar()
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
      setCfg(r); setEditNome(false); setErro(''); flashBrand('Perfil atualizado.')
    } catch (e) { setErro(e.message) } finally { setSalvandoNome(false) }
  }

  async function handleFoto(e) {
    const file = e.target.files?.[0]; if (!file) return
    setSalvandoFoto(true)
    try {
      await uploadEmpresaFoto(token, file, empresa.empresa_id)
      const r = await getEmpresaConfigPublica(null, empresa.empresa_id)
      if (r) setCfg(r)
      setErro(''); flashBrand('Foto atualizada.')
    } catch (e) { setErro(e.message) } finally { setSalvandoFoto(false); if (fotoRef.current) fotoRef.current.value = '' }
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

  async function handleRemover(u) {
    const ok = await pedir({ titulo: `Tirar ${u.nome || u.email} da empresa?`,
      texto: 'A conta continua existindo, mas sem empresa: a pessoa deixa de ver os dados daqui.',
      confirmar: 'Tirar da empresa', perigo: true })
    if (!ok) return
    const usuarioId = u.id
    setErro('')
    try {
      await removerUsuarioEmpresa(token, empresa.empresa_id, usuarioId)
      setMembros(prev => prev.filter(u => u.id !== usuarioId))
    } catch (err) { setErro(err.message) }
  }

  async function handleDeletar() {
    const ok = await pedir({ titulo: `Excluir a empresa “${empresa.empresa_id}”?`,
      texto: `Os ${membros.length} usuário(s) dela ficam sem empresa. Não dá para desfazer.`, confirmar: 'Excluir empresa', perigo: true })
    if (!ok) return
    try {
      await deletarEmpresa(token, empresa.empresa_id)
      onAtualizar()
    } catch (err) { setErro(err.message) }
  }

  const nomeExibicao = cfg?.nome_exibicao || empresa.empresa_id

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
      {modal}
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
            title="Trocar foto">
            {salvandoFoto
              ? <span className="text-ink text-[8px]">…</span>
              : <Camera className="w-2.5 h-2.5 text-ink" aria-hidden="true" />}
            <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" ref={fotoRef} onChange={handleFoto}
              aria-label={`Trocar a foto de ${nomeExibicao}`} />
          </label>
        </div>

        <div className="flex-1 min-w-0">
          {editNome ? (
            <div className="flex gap-1.5 items-center">
              <input autoFocus type="text" value={nomeEdit} onChange={e => setNomeEdit(e.target.value)}
                aria-label="Nome de exibição da empresa"
                className="flex-1 text-sm rounded-lg px-2.5 py-1 focus:outline-none"
                style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.30)', color: 'var(--ink)' }}
                placeholder="Nome de exibição" />
              <input type="color" value={corEdit} onChange={e => setCorEdit(e.target.value)}
                title="Cor de destaque" aria-label="Cor de destaque da empresa" className="w-7 h-7 rounded-md cursor-pointer shrink-0 bg-transparent"
                style={{ border: '1px solid var(--line)' }} />
              <button type="button" onClick={handleSalvarNome} disabled={salvandoNome} aria-label="Salvar nome e cor"
                className="btn-primary btn-sm">
                <Check className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => setEditNome(false)} aria-label="Cancelar edição" className="px-2 py-1 transition-colors" style={{ color: 'var(--ink-3)' }}>
                <X className="w-3.5 h-3.5" aria-hidden="true" />
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
                className="p-1 rounded transition-colors" title="Editar nome e cor" aria-label={`Editar nome e cor de ${nomeExibicao}`} style={{ color: 'var(--ink-4)' }}
                onMouseOver={e => e.currentTarget.style.color = 'var(--accent-text)'}
                onMouseOut={e => e.currentTarget.style.color = 'var(--ink-4)'}>
                <Pencil className="w-3 h-3" />
              </button>
            </div>
          )}
          {msgBrand && <p role="status" className="text-xs mt-0.5" style={{ color: 'var(--success)' }}>{msgBrand}</p>}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button type="button" onClick={() => { setShowInput(s => !s); setErro('') }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors"
            style={{ color: 'var(--accent-text)', background: 'rgb(var(--c-royal) / 0.10)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}
            onMouseOver={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.18)'}
            onMouseOut={e => e.currentTarget.style.background = 'rgb(var(--c-royal) / 0.10)'}>
            <Plus className="w-3.5 h-3.5" /> Adicionar usuário
          </button>
          <button type="button" onClick={handleDeletar} title="Excluir empresa" aria-label={`Excluir a empresa ${nomeExibicao}`}
            className="p-1.5 rounded-lg transition-colors" style={{ color: 'var(--ink-4)' }}
            onMouseOver={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgb(var(--c-danger) / 0.08)' }}
            onMouseOut={e => { e.currentTarget.style.color = 'var(--ink-4)'; e.currentTarget.style.background = 'transparent' }}>
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <DominiosEmpresa empresaId={empresa.empresa_id} token={token} />

      {showInput && (
        <form onSubmit={handleAdicionar} className="px-5 py-3 border-b flex gap-2 items-center" style={{ borderColor: 'var(--line)', background: 'var(--raise-1)' }}>
          <Mail className="w-4 h-4 shrink-0" style={{ color: 'var(--ink-3)' }} />
          <input type="email" required value={emailInput} onChange={e => { setEmailInput(e.target.value); setErro('') }}
            aria-label="E-mail de um usuário já cadastrado"
            placeholder="email@dominio.com (já cadastrado no sistema)"
            className="flex-1 text-sm rounded-xl px-3 py-2 focus:outline-none"
            style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.25)', color: 'var(--ink)' }} />
          <button type="submit" disabled={adicionando} className="btn-primary btn-sm whitespace-nowrap">
            {adicionando ? 'Adicionando…' : 'Adicionar'}
          </button>
          <button type="button" onClick={() => { setShowInput(false); setErro('') }} aria-label="Cancelar" className="p-2 transition-colors" style={{ color: 'var(--ink-3)' }}>
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </form>
      )}

      {erro && <p role="alert" className="px-5 py-2 text-xs border-b" style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.08)', borderColor: 'rgb(var(--c-danger) / 0.15)' }}>{erro}</p>}

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
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${ROLE_BADGE[u.role] ?? 'bg-raise-2 text-ink-2'}`}>{nomePapel(u.role)}</span>
                <button type="button" onClick={() => handleRemover(u)} title="Tirar da empresa" aria-label={`Tirar ${u.nome || u.email} da empresa`}
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
  const { pedir: pedirConfirmacao, modal: modalConfirmar } = useConfirmar()
  const { token, usuario, isAdmin, isComando, empresaConfig, refreshEmpresaConfig } = useAuth()
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
  // "+ Nova empresa" fica num estado próprio: antes o texto digitado ia para
  // form.empresa_id, o select perdia a opção e o campo sumia na primeira letra.
  const [empresaNova, setEmpresaNova] = useState('')
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
      const [lista, conxs, emps] = await Promise.all([
        listarUsuarios(token),
        isAdmin || isComando ? listarConexoes() : Promise.resolve([]),
        isComando ? listarEmpresas(token) : Promise.resolve({ empresas: [], sem_empresa: [] }),
      ])
      setUsuarios(lista)
      setConexoes(conxs)
      setEmpresas(emps)
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
      flash(`Empresa pronta: só fica salva quando você adicionar o primeiro usuário.`)
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
      setErro(''); flashBrand('Perfil da empresa atualizado.')
    } catch (e) { setErro(e.message) } finally { setSalvandoBrand(false) }
  }

  async function handleFotoChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setSalvandoBrand(true)
    try {
      await uploadEmpresaFoto(token, file)
      refreshEmpresaConfig()
      setErro(''); flashBrand('Foto atualizada.')
    } catch (e) { setErro(e.message) } finally { setSalvandoBrand(false); if (fotoInputRef.current) fotoInputRef.current.value = '' }
  }

  async function handleToggleAtivo(u) {
    if (u.ativo) {
      const ok = await pedirConfirmacao({ titulo: `Desativar ${u.nome}?`,
        texto: 'A pessoa não consegue mais entrar. Dá para ativar de novo depois.',
        confirmar: 'Desativar', perigo: true })
      if (!ok) return
    }
    setErro('')
    try {
      await toggleUsuarioAtivo(token, u.id, !u.ativo)
      flash(`${u.nome} ${!u.ativo ? 'ativado' : 'desativado'}.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, ativo: !u.ativo } : x))
    } catch (e) { setErro(e.message) }
  }

  async function handleToggleRole(u) {
    const novo = ROTULO_ROLE[u.role]?.destino || 'admin'
    const ok = await pedirConfirmacao({ titulo: `Mudar ${u.nome} para ${nomePapel(novo)}?`,
      texto: novo === 'admin' ? 'Ele passa a ver e gerenciar os usuários, as premissas e as ofertas da empresa.' : 'Ele perde o acesso à gestão da empresa.',
      confirmar: 'Alterar permissão' })
    if (!ok) return
    try {
      await alterarRoleUsuario(token, u.id, novo)
      flash(`${u.nome} agora é ${nomePapel(novo)}.`)
      setUsuarios(prev => prev.map(x => x.id === u.id ? { ...x, role: novo } : x))
    } catch (e) { setErro(e.message) }
  }

  async function handleRegistrar(e) {
    e.preventDefault(); setFormErro('')
    const empresa = form.role === 'comando' ? ''
      : form.empresa_id === '__nova__' ? empresaNova.trim().toLowerCase().replace(/\s+/g, '_')
      : form.empresa_id
    if (form.role !== 'comando' && !empresa) { setFormErro('Escolha a empresa ou digite o nome da nova.'); return }
    setSalvando(true)
    try {
      await registrarUsuario(token, { ...form, empresa_id: empresa })
      flash(`Usuário ${form.email} criado.`)
      setForm({ email: '', nome: '', senha: '', role: 'operador', empresa_id: '' })
      setEmpresaNova('')
      setShowForm(false)
      carregar()
    } catch (e) { setFormErro(e.message) } finally { setSalvando(false) }
  }

  const usuariosExibidos = isAdmin
    ? usuarios.filter(u => u.role !== 'comando')
    : usuarios

  return (
    <AppShell titulo="Usuários">
      {modalConfirmar}

      <div className="w-full max-w-5xl mx-auto">

        {/* Abas */}
        {(isAdmin || isComando) && (
          <div className="flex gap-1 mb-8 p-1 rounded-xl w-fit max-w-full overflow-x-auto" style={{ background: 'var(--raise-2)' }}>
            {[
              ['usuarios', <Users key="i" className="w-4 h-4" aria-hidden="true" />, 'Usuários'],
              ...(isComando ? [['empresas', <Building2 key="i" className="w-4 h-4" aria-hidden="true" />, 'Empresas']] : []),
              ['permissoes', <Database key="i" className="w-4 h-4" aria-hidden="true" />, 'Permissões de banco'],
            ].map(([id, icon, label]) => (
              <button key={id} type="button" onClick={() => setAba(id)} aria-pressed={aba === id}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                style={aba === id ? { background: 'var(--surface)', color: 'var(--ink)', boxShadow: '0 1px 4px rgba(0,0,0,0.30)' } : { color: 'var(--ink-3)' }}>
                {icon}{label}
              </button>
            ))}
          </div>
        )}

        {msg && <div role="status" className="mb-5 rounded-xl px-4 py-3 text-sm" style={{ color: 'var(--success)', background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>{msg}</div>}
        {erro && <MsgErro className="mb-5 py-3">{erro}</MsgErro>}

        {/* ── ABA USUÁRIOS ── */}
        {aba === 'usuarios' && (
          <>
            {/* Perfil da empresa (admin/comando) */}
            {(isAdmin || isComando) && usuario?.empresa_id && (
              <div className="mb-8 rounded-2xl p-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs font-semibold uppercase tracking-wide flex items-center gap-1.5" style={{ color: 'var(--ink-3)' }}>
                    <Building2 className="h-3.5 w-3.5" /> Perfil da empresa<DicaAjuda id="perfil-da-empresa" />
                  </p>
                  {!editandoBrand ? (
                    <button type="button" onClick={abrirEdicaoBrand} className="flex items-center gap-1 text-xs transition-colors font-semibold" style={{ color: 'var(--accent-text)' }}>
                      <Pencil className="w-3 h-3" aria-hidden="true" /> Editar
                    </button>
                  ) : (
                    <button type="button" onClick={() => setEditandoBrand(false)} className="text-xs transition-colors" style={{ color: 'var(--ink-3)' }}>Cancelar</button>
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
                      <label className="absolute -bottom-1.5 -right-1.5 w-7 h-7 rounded-full flex items-center justify-center cursor-pointer transition-colors shadow-md" title="Trocar foto"
                        style={{ background: 'var(--royal)' }}>
                        <Camera className="w-3.5 h-3.5" style={{ color: 'var(--on-brand)' }} aria-hidden="true" />
                        <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" ref={fotoInputRef} onChange={handleFotoChange}
                          aria-label="Trocar a foto da empresa" />
                      </label>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    {editandoBrand ? (
                      <div className="flex gap-2 items-center">
                        <input type="text" value={nomeEmpresaEdit} onChange={e => setNomeEmpresaEdit(e.target.value)} placeholder="Nome de exibição"
                          aria-label="Nome de exibição da empresa"
                          className="flex-1 text-sm rounded-xl px-3 py-2 focus:outline-none"
                          style={{ background: 'var(--surface-2)', border: '1px solid rgb(var(--c-royal) / 0.30)', color: 'var(--ink)' }}
                        />
                        <input type="color" value={corEmpresaEdit} onChange={e => setCorEmpresaEdit(e.target.value)}
                          title="Cor de destaque da empresa" aria-label="Cor de destaque da empresa"
                          className="w-10 h-9 rounded-lg cursor-pointer shrink-0 bg-transparent"
                          style={{ border: '1px solid var(--line)' }}
                        />
                        <button type="button" onClick={handleSalvarNome} disabled={salvandoBrand}
                          className="btn-primary btn-sm shrink-0">
                          <Check className="w-3.5 h-3.5" aria-hidden="true" />{salvandoBrand ? 'Salvando…' : 'Salvar'}
                        </button>
                      </div>
                    ) : (
                      <>
                        <p className="font-bold text-ink text-base truncate">{empresaConfig?.nome_exibicao || usuario?.empresa_id}</p>
                        <p className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: 'var(--ink-3)' }}>
                          <span className="inline-block w-2.5 h-2.5 rounded-full border border-line-2" style={{ background: empresaConfig?.cor_primaria || '#5966d9' }} />
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {msgBrand && (
                  <p role="status" className="mt-3 text-xs rounded-lg px-3 py-2" style={{ color: 'var(--success)', background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.15)' }}>
                    {msgBrand}
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-ink tracking-tight">Usuários do sistema<DicaAjuda id="usuarios-e-papeis" /></h1>
                <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>
                  {isComando ? 'Gerencie todos os usuários e empresas.' : 'Gerencie os operadores da sua empresa.'}
                </p>
              </div>
              {isComando && (
                <button type="button" onClick={() => { setShowForm(!showForm); setFormErro('') }} className="btn-primary">
                  <UserPlus className="w-4 h-4" aria-hidden="true" /> Novo usuário
                </button>
              )}
            </div>

            {isComando && showForm && (
              <div className="mb-6 rounded-2xl p-6" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
                <h2 className="text-sm font-bold text-ink mb-5">Criar novo usuário</h2>
                <form onSubmit={handleRegistrar} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="nu-nome" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Nome completo</label>
                    <input id="nu-nome" type="text" required value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} className="input-base" placeholder="João Silva" />
                  </div>
                  <div>
                    <label htmlFor="nu-email" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>E-mail</label>
                    <input id="nu-email" type="email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="input-base" placeholder="joao@empresa.com" />
                  </div>
                  <div>
                    <label htmlFor="nu-senha" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Senha inicial</label>
                    <input id="nu-senha" type="password" required minLength={8} value={form.senha} onChange={e => setForm(f => ({ ...f, senha: e.target.value }))} className="input-base" placeholder="mínimo 8 caracteres, letras e números" autoComplete="new-password" />
                  </div>
                  <div>
                    <label htmlFor="nu-papel" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Permissão</label>
                    <select id="nu-papel" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} className="input-base">
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
                    <label htmlFor="nu-empresa" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Empresa</label>
                    <select id="nu-empresa" required={form.role !== 'comando'} value={form.empresa_id} onChange={e => setForm(f => ({ ...f, empresa_id: e.target.value }))} className="input-base">
                      <option value="">— selecione uma empresa —</option>
                      {(empresas.empresas || []).map(emp => (
                        <option key={emp.empresa_id} value={emp.empresa_id}>{emp.empresa_id} ({emp.usuarios?.length ?? 0} membros)</option>
                      ))}
                      <option value="__nova__">+ Nova empresa…</option>
                    </select>
                    {form.empresa_id === '__nova__' && (
                      <>
                        <label htmlFor="nu-empresa-nova" className="sr-only">Nome da nova empresa</label>
                        <input id="nu-empresa-nova" type="text" required autoFocus className="input-base mt-2" placeholder="Nome da nova empresa (ex.: bradesco)"
                          value={empresaNova} onChange={e => setEmpresaNova(e.target.value)} />
                      </>
                    )}
                    <p className="text-xs mt-1" style={{ color: 'var(--ink-3)' }}>Usuários da mesma empresa compartilham dados entre si.</p>
                  </div>
                  {formErro && <MsgErro className="col-span-2">{formErro}</MsgErro>}
                  <div className="col-span-2 flex gap-3 justify-end pt-1">
                    <button type="button" onClick={() => setShowForm(false)}
                      className="px-4 py-2 text-sm rounded-xl transition-colors" style={{ color: 'var(--ink-2)' }}
                      onMouseOver={e => e.currentTarget.style.background = 'var(--raise-2)'}
                      onMouseOut={e => e.currentTarget.style.background = 'transparent'}>Cancelar</button>
                    <button type="submit" disabled={salvando} className="btn-primary disabled:opacity-50">{salvando ? 'Criando…' : 'Criar usuário'}</button>
                  </div>
                </form>
              </div>
            )}

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando…</div>
            ) : (
              <div className="rounded-2xl overflow-x-auto" style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 2px 12px rgba(0,0,0,0.40)' }}>
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
                                <button type="button" onClick={() => handleToggleAtivo(u)} title={u.ativo ? 'Desativar usuário' : 'Ativar usuário'}
                                  className="flex items-center gap-1 px-2 py-1 rounded-lg transition-colors text-xs font-medium whitespace-nowrap" style={{ color: 'var(--ink-3)' }}
                                  onMouseOver={e => { e.currentTarget.style.background = 'var(--raise-3)'; e.currentTarget.style.color = 'var(--ink)' }}
                                  onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-3)' }}>
                                  {u.ativo ? <ToggleRight className="w-4 h-4 text-emerald-400 shrink-0" /> : <ToggleLeft className="w-4 h-4 shrink-0" />}
                                  {u.ativo ? 'Desativar' : 'Ativar'}
                                </button>
                                {isComando && (
                                  <button type="button" onClick={() => handleToggleRole(u)} title={ROTULO_ROLE[u.role]?.titulo || 'Promover a administrador'}
                                    className="flex items-center gap-1 px-2 py-1 rounded-lg transition-colors text-xs font-medium whitespace-nowrap" style={{ color: 'var(--ink-3)' }}
                                    onMouseOver={e => { e.currentTarget.style.background = 'var(--raise-3)'; e.currentTarget.style.color = 'var(--ink)' }}
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
                aria-label="Nome da nova empresa"
                placeholder="Nome da nova empresa (ex.: sicoob, bradesco)"
                className="flex-1 text-sm rounded-xl px-4 py-2.5 focus:outline-none"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }} />
              <button type="submit" disabled={criandoEmpresa || !novaEmpresa.trim()}
                className="btn-primary whitespace-nowrap">
                <Plus className="w-4 h-4" aria-hidden="true" />{criandoEmpresa ? 'Criando…' : 'Nova empresa'}
              </button>
            </form>

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando…</div>
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
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${ROLE_BADGE[u.role] ?? 'bg-raise-2 text-ink-2'}`}>{nomePapel(u.role)}</span>
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
              <h1 className="text-xl font-bold text-ink tracking-tight">Permissões de banco de dados<DicaAjuda id="conexao-com-banco" /></h1>
            </div>

            {carregando ? (
              <div className="text-center py-16 text-sm" style={{ color: 'var(--ink-3)' }}>Carregando…</div>
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
    </AppShell>
  )
}
