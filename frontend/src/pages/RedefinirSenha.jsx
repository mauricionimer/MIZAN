import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound, Eye, EyeOff, Loader2 } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function RedefinirSenha() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') || ''

  const [nova, setNova]             = useState('')
  const [confirmar, setConfirmar]   = useState('')
  const [showNova, setShowNova]     = useState(false)
  const [showConf, setShowConf]     = useState(false)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState('')
  const [sucesso, setSucesso]       = useState(false)

  useEffect(() => {
    if (!token) navigate('/login')
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    if (nova.length < 6) { setErro('A senha deve ter pelo menos 6 caracteres.'); return }
    if (nova !== confirmar) { setErro('As senhas não coincidem.'); return }

    setCarregando(true)
    try {
      const res = await fetch(`${BASE}/auth/redefinir-senha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, nova_senha: nova }),
      })
      if (!res.ok) {
        const { detail } = await res.json().catch(() => ({ detail: 'Erro desconhecido.' }))
        throw new Error(detail)
      }
      setSucesso(true)
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <div className="mb-8 text-center">
        <div className="inline-flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white text-lg font-bold">⚖</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Mizan</h1>
        </div>
      </div>

      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        {sucesso ? (
          <div className="text-center py-4">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <KeyRound className="w-6 h-6 text-green-600" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Senha redefinida!</h2>
            <p className="text-sm text-slate-500 mb-6">Sua senha foi atualizada. Faça login com a nova senha.</p>
            <button
              onClick={() => navigate('/login')}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl text-sm font-medium"
            >
              Ir para o login
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-base font-semibold text-slate-800 mb-1">Nova senha</h2>
            <p className="text-sm text-slate-500 mb-6">Escolha uma nova senha com pelo menos 6 caracteres.</p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">Nova senha</label>
                <div className="relative">
                  <input
                    type={showNova ? 'text' : 'password'}
                    required value={nova}
                    onChange={e => setNova(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button type="button" onClick={() => setShowNova(s => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                    {showNova ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">Confirmar nova senha</label>
                <div className="relative">
                  <input
                    type={showConf ? 'text' : 'password'}
                    required value={confirmar}
                    onChange={e => setConfirmar(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button type="button" onClick={() => setShowConf(s => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                    {showConf ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {erro && <p className="text-sm text-red-600">{erro}</p>}
              <button
                type="submit" disabled={carregando}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 flex items-center justify-center gap-2"
              >
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando...</> : 'Salvar nova senha'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
