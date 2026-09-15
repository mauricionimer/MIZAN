import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound, Eye, EyeOff, Loader2, CheckCircle2 } from 'lucide-react'

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

  useEffect(() => { if (!token) navigate('/login') }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    if (nova.length < 8 || /^\d+$/.test(nova) || /^[a-zA-Z]+$/.test(nova)) {
      setErro('A senha deve ter no mínimo 8 caracteres e combinar letras e números.'); return
    }
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
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="flex items-center gap-2.5 mb-10">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 4px 16px rgba(29,106,255,0.30)' }}>
          <span className="text-white font-bold text-sm">⚖</span>
        </div>
        <span className="text-white text-xl font-bold tracking-tight">Mizan</span>
      </div>

      <div className="w-full max-w-sm rounded-2xl p-8"
        style={{
          background: '#0d1628',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 16px 48px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.30)',
        }}>
        {sucesso ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.20)' }}>
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-lg font-bold text-white mb-2 tracking-tight">Senha redefinida!</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: '#8fa3c8' }}>
              Sua senha foi atualizada. Faça login com a nova senha.
            </p>
            <button onClick={() => navigate('/login')} className="btn-primary w-full py-2.5">
              Ir para o login
            </button>
          </div>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
              style={{ background: 'rgba(29,106,255,0.12)', border: '1px solid rgba(29,106,255,0.20)' }}>
              <KeyRound className="w-6 h-6 text-blue-400" />
            </div>
            <h2 className="text-lg font-bold text-white mb-1 tracking-tight">Nova senha</h2>
            <p className="text-sm mb-7" style={{ color: '#8fa3c8' }}>
              Escolha uma nova senha com no mínimo 8 caracteres, combinando letras e números.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Nova senha</label>
                <div className="relative">
                  <input type={showNova ? 'text' : 'password'} required value={nova}
                    onChange={e => setNova(e.target.value)} className="input-base pr-11"
                    placeholder="mínimo 8 caracteres, letras e números" />
                  <button type="button" onClick={() => setShowNova(s => !s)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: '#7c93bd' }}>
                    {showNova ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>Confirmar nova senha</label>
                <div className="relative">
                  <input type={showConf ? 'text' : 'password'} required value={confirmar}
                    onChange={e => setConfirmar(e.target.value)} className="input-base pr-11"
                    placeholder="repita a nova senha" />
                  <button type="button" onClick={() => setShowConf(s => !s)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: '#7c93bd' }}>
                    {showConf ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {erro && (
                <div className="text-sm text-red-400 rounded-xl px-4 py-3"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
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
