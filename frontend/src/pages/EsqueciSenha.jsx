import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Mail, Loader2, CheckCircle2 } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function EsqueciSenha() {
  const navigate = useNavigate()
  const [email, setEmail]           = useState('')
  const [enviado, setEnviado]       = useState(false)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    setCarregando(true)
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 15000)
      await fetch(`${BASE}/auth/esqueci-senha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
        signal: controller.signal,
      })
      clearTimeout(timer)
      setEnviado(true)
    } catch (e) {
      if (e.name === 'AbortError') setErro('O servidor demorou muito. Tente novamente em instantes.')
      else setErro('Erro ao conectar. Tente novamente.')
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
        <button onClick={() => navigate('/login')}
          className="flex items-center gap-1.5 text-sm mb-7 transition-colors font-medium"
          style={{ color: '#8fa3c8' }}
          onMouseOver={e => e.currentTarget.style.color = 'white'}
          onMouseOut={e => e.currentTarget.style.color = '#8fa3c8'}>
          <ArrowLeft className="w-4 h-4" /> Voltar ao login
        </button>

        {enviado ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.20)' }}>
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-lg font-bold text-white mb-2 tracking-tight">E-mail enviado!</h2>
            <p className="text-sm leading-relaxed" style={{ color: '#8fa3c8' }}>
              Se o e-mail estiver cadastrado, você receberá as instruções em breve. Verifique também a caixa de spam.
            </p>
            <button onClick={() => navigate('/login')} className="btn-primary mt-6 w-full py-2.5">
              Voltar ao login
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-lg font-bold text-white mb-1 tracking-tight">Esqueceu a senha?</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: '#8fa3c8' }}>
              Digite seu e-mail e enviaremos um link para redefinir a senha.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>E-mail</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  className="input-base"
                />
              </div>
              {erro && (
                <div className="text-sm text-red-400 rounded-xl px-4 py-3"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)' }}>
                  {erro}
                </div>
              )}
              <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Enviando...</>
                  : 'Enviar link de redefinição'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
