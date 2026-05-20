import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { KeyRound, ArrowLeft, Eye, EyeOff, LogOut, Trash2 } from 'lucide-react'
import { deletarConta } from '../api'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function AlterarSenha() {
  const { token, usuario, logout } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({ senha_atual: '', nova_senha: '', confirmar: '' })
  const [showAtual, setShowAtual]       = useState(false)
  const [showNova, setShowNova]         = useState(false)
  const [showConfirmar, setShowConfirmar] = useState(false)
  const [carregando, setCarregando]     = useState(false)
  const [erro, setErro]                 = useState('')
  const [sucesso, setSucesso]           = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')

    if (form.nova_senha.length < 6) {
      setErro('A nova senha deve ter pelo menos 6 caracteres.')
      return
    }
    if (form.nova_senha !== form.confirmar) {
      setErro('A nova senha e a confirmação não coincidem.')
      return
    }
    if (form.nova_senha === form.senha_atual) {
      setErro('A nova senha deve ser diferente da senha atual.')
      return
    }

    setCarregando(true)
    try {
      const res = await fetch(`${BASE}/auth/alterar-senha`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          senha_atual: form.senha_atual,
          nova_senha: form.nova_senha,
        }),
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
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
        <div className="relative">
          <input
            type={show ? 'text' : 'password'}
            required
            value={form[campo]}
            onChange={e => setForm(f => ({ ...f, [campo]: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => setShow(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-800">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <KeyRound className="w-5 h-5 text-blue-600" />
          <span className="font-semibold text-gray-800">Alterar senha</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{usuario?.nome}</span>
          <button
            onClick={logout}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition-colors"
          >
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </nav>

      <div className="max-w-md mx-auto px-6 py-12">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h1 className="text-xl font-bold text-gray-900 mb-1">Alterar senha</h1>
          <p className="text-sm text-gray-500 mb-6">
            Digite sua senha atual e escolha uma nova com no mínimo 6 caracteres.
          </p>

          {sucesso ? (
            <div className="text-center py-6">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <KeyRound className="w-6 h-6 text-green-600" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900 mb-1">Senha alterada!</h2>
              <p className="text-sm text-gray-500 mb-5">Sua senha foi atualizada com sucesso.</p>
              <button
                onClick={() => navigate(-1)}
                className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg text-sm font-medium"
              >
                Voltar
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Campo
                label="Senha atual"
                campo="senha_atual"
                show={showAtual}
                setShow={setShowAtual}
              />
              <Campo
                label="Nova senha"
                campo="nova_senha"
                show={showNova}
                setShow={setShowNova}
              />
              <Campo
                label="Confirmar nova senha"
                campo="confirmar"
                show={showConfirmar}
                setShow={setShowConfirmar}
              />

              {erro && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
                  {erro}
                </div>
              )}

              <button
                type="submit"
                disabled={carregando}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
              >
                {carregando ? 'Salvando...' : 'Salvar nova senha'}
              </button>
            </form>

            {/* Zona de perigo — LGPD */}
            <DeletarConta onDeleted={() => { logout(); navigate('/login') }} />
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
    <div className="mt-8 border-t border-red-100 pt-6">
      <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-3">Zona de perigo</p>
      {!confirmando ? (
        <button onClick={() => setConfirmando(true)}
          className="flex items-center gap-2 text-sm text-red-500 hover:text-red-700 hover:bg-red-50 px-3 py-2 rounded-lg transition-colors">
          <Trash2 className="h-4 w-4" /> Deletar minha conta (LGPD)
        </button>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            Isso removerá permanentemente sua conta, conexões salvas e histórico de contatos. <strong>Essa ação não pode ser desfeita.</strong>
          </p>
          {erro && <p className="text-xs text-red-500">{erro}</p>}
          <div className="flex gap-2">
            <button onClick={confirmarDelecao} disabled={deletando}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors">
              {deletando ? 'Deletando...' : 'Confirmar exclusão'}
            </button>
            <button onClick={() => setConfirmando(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100 transition-colors">
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
