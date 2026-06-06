import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { KeyRound, ArrowLeft, Eye, EyeOff, LogOut, Trash2, CheckCircle2 } from 'lucide-react'
import { deletarConta } from '../api'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function Logo() {
  return (
    <div className="w-7 h-7 rounded-lg flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 2px 8px rgba(29,106,255,0.30)' }}>
      <span className="text-white font-bold text-xs">⚖</span>
    </div>
  )
}

export default function AlterarSenha() {
  const { token, usuario, logout, isComando, isAdmin } = useAuth()
  const navigate = useNavigate()
  const homePath = isComando ? '/comando' : isAdmin ? '/admin' : '/operador'

  const [form, setForm] = useState({ senha_atual: '', nova_senha: '', confirmar: '' })
  const [showAtual, setShowAtual]         = useState(false)
  const [showNova, setShowNova]           = useState(false)
  const [showConfirmar, setShowConfirmar] = useState(false)
  const [carregando, setCarregando]       = useState(false)
  const [erro, setErro]                   = useState('')
  const [sucesso, setSucesso]             = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    if (form.nova_senha.length < 6) { setErro('A nova senha deve ter pelo menos 6 caracteres.'); return }
    if (form.nova_senha !== form.confirmar) { setErro('A nova senha e a confirmação não coincidem.'); return }
    if (form.nova_senha === form.senha_atual) { setErro('A nova senha deve ser diferente da senha atual.'); return }
    setCarregando(true)
    try {
      const res = await fetch(`${BASE}/auth/alterar-senha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ senha_atual: form.senha_atual, nova_senha: form.nova_senha }),
      })
      if (!res.ok) {
        const { detail } = await res.json().catch(() => ({ detail: `Erro ${res.status}` }))
        throw new Error(detail)
      }
      setSucesso(true)
      setForm({ senha_atual: '', nova_senha: '', confirmar: '' })
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  function Campo({ label, campo, show, setShow }) {
    return (
      <div>
        <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>{label}</label>
        <div className="relative">
          <input
            type={show ? 'text' : 'password'}
            required
            value={form[campo]}
            onChange={e => setForm(f => ({ ...f, [campo]: e.target.value }))}
            className="input-base pr-11"
          />
          <button type="button" onClick={() => setShow(s => !s)}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
            style={{ color: '#5a7499' }}>
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(homePath)}
            className="transition-colors p-1 rounded-lg hover:bg-white/5"
            style={{ color: '#5a7499' }}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Logo />
          <span className="font-bold text-white text-sm">Mizan</span>
          <span className="text-white/20 text-sm">/</span>
          <span className="text-sm" style={{ color: '#8fa3c8' }}>Alterar senha</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: '#5a7499' }}>{usuario?.nome}</span>
          <button onClick={logout} className="nav-link-danger">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </header>

      <div className="max-w-md mx-auto px-6 py-12">
        <div className="rounded-2xl p-8"
          style={{
            background: '#0d1628',
            border: '1px solid rgba(255,255,255,0.07)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.30)',
          }}>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(29,106,255,0.12)', border: '1px solid rgba(29,106,255,0.20)' }}>
              <KeyRound className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">Alterar senha</h1>
              <p className="text-xs" style={{ color: '#5a7499' }}>Mínimo 6 caracteres</p>
            </div>
          </div>

          <div className="border-t my-5" style={{ borderColor: 'rgba(255,255,255,0.07)' }} />

          {sucesso ? (
            <div className="text-center py-6">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.20)' }}>
                <CheckCircle2 className="w-7 h-7 text-emerald-400" />
              </div>
              <h2 className="text-base font-bold text-white mb-1 tracking-tight">Senha alterada!</h2>
              <p className="text-sm mb-6" style={{ color: '#8fa3c8' }}>Sua senha foi atualizada com sucesso.</p>
              <button onClick={() => navigate(homePath)} className="btn-primary px-6 py-2.5">
                Voltar
              </button>
            </div>
          ) : (
            <>
              <form onSubmit={handleSubmit} className="space-y-4">
                <Campo label="Senha atual" campo="senha_atual" show={showAtual} setShow={setShowAtual} />
                <Campo label="Nova senha" campo="nova_senha" show={showNova} setShow={setShowNova} />
                <Campo label="Confirmar nova senha" campo="confirmar" show={showConfirmar} setShow={setShowConfirmar} />
                {erro && (
                  <div className="text-red-400 rounded-xl px-4 py-3 text-sm"
                    style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
                    {erro}
                  </div>
                )}
                <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                  {carregando ? 'Salvando...' : 'Salvar nova senha'}
                </button>
              </form>
              <DeletarConta onDeleted={() => { logout(); navigate('/login') }} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function DeletarConta({ onDeleted }) {
  const [confirmando, setConfirmando] = useState(false)
  const [deletando, setDeletando]     = useState(false)
  const [erro, setErro]               = useState('')

  async function confirmarDelecao() {
    setDeletando(true); setErro('')
    try {
      await deletarConta()
      onDeleted()
    } catch (e) {
      setErro(e.message)
      setDeletando(false)
    }
  }

  return (
    <div className="mt-8 border-t pt-6" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
      <p className="text-[11px] font-semibold text-red-400/70 uppercase tracking-widest mb-3">Zona de perigo</p>
      {!confirmando ? (
        <button onClick={() => setConfirmando(true)}
          className="flex items-center gap-2 text-sm text-red-400/60 hover:text-red-400 px-3 py-2 rounded-xl transition-colors font-medium hover:bg-red-500/8">
          <Trash2 className="h-4 w-4" /> Deletar minha conta (LGPD)
        </button>
      ) : (
        <div className="space-y-3">
          <div className="text-sm text-red-400 rounded-xl px-4 py-3 leading-relaxed"
            style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
            Isso removerá permanentemente sua conta, conexões salvas e histórico de contatos.{' '}
            <strong>Essa ação não pode ser desfeita.</strong>
          </div>
          {erro && <p className="text-xs text-red-400">{erro}</p>}
          <div className="flex gap-2">
            <button onClick={confirmarDelecao} disabled={deletando}
              className="px-4 py-2 rounded-xl text-sm font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors">
              {deletando ? 'Deletando...' : 'Confirmar exclusão'}
            </button>
            <button onClick={() => setConfirmando(false)}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-colors"
              style={{ color: '#8fa3c8' }}
              onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
