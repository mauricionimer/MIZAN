import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound, Eye, EyeOff, Loader2, CheckCircle2 } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function Logo() {
  return (
    <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-sm">⚖</span>
    </div>
  )
}

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
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden"
      style={{ background: 'linear-gradient(180deg, rgba(239,246,255,0.8) 0%, #f8fafc 200px), #f8fafc' }}>
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full opacity-10 -translate-y-1/2 blur-3xl"
        style={{ background: 'radial-gradient(circle, #3b82f6, #1d4ed8)' }} />
      <div className="flex items-center gap-2.5 mb-10 relative">
        <Logo />
        <span className="text-slate-800 text-xl font-bold tracking-tight">Mizan</span>
      </div>

      <div className="w-full max-w-sm bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(15,23,42,0.08)] p-8">
        {sucesso ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 bg-emerald-50 border border-emerald-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-7 h-7 text-emerald-600" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-2 tracking-tight">Senha redefinida!</h2>
            <p className="text-sm text-slate-500 mb-7 leading-relaxed">Sua senha foi atualizada. Faça login com a nova senha.</p>
            <button onClick={() => navigate('/login')} className="btn-primary w-full py-2.5">
              Ir para o login
            </button>
          </div>
        ) : (
          <>
            <div className="w-12 h-12 bg-blue-50 border border-blue-100 rounded-xl flex items-center justify-center mb-5">
              <KeyRound className="w-6 h-6 text-blue-600" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-1 tracking-tight">Nova senha</h2>
            <p className="text-sm text-slate-500 mb-7">Escolha uma nova senha com pelo menos 6 caracteres.</p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Nova senha</label>
                <div className="relative">
                  <input
                    type={showNova ? 'text' : 'password'}
                    required value={nova}
                    onChange={e => setNova(e.target.value)}
                    className="input-base pr-11"
                    placeholder="mínimo 6 caracteres"
                  />
                  <button type="button" onClick={() => setShowNova(s => !s)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">
                    {showNova ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Confirmar nova senha</label>
                <div className="relative">
                  <input
                    type={showConf ? 'text' : 'password'}
                    required value={confirmar}
                    onChange={e => setConfirmar(e.target.value)}
                    className="input-base pr-11"
                    placeholder="repita a nova senha"
                  />
                  <button type="button" onClick={() => setShowConf(s => !s)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">
                    {showConf ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {erro && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  {erro}
                </div>
              )}
              <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando...</> : 'Salvar nova senha'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
