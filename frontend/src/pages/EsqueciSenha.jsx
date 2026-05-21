import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Mail, Loader2 } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

function Logo() {
  return (
    <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-500/20"
      style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
      <span className="text-white font-bold text-sm">⚖</span>
    </div>
  )
}

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
        <Logo />
        <span className="text-white text-xl font-bold tracking-tight">Mizan</span>
      </div>

      <div className="w-full max-w-sm bg-white rounded-2xl border border-white/10 shadow-[0_16px_48px_rgba(2,11,31,0.45),0_4px_12px_rgba(2,11,31,0.25)] p-8">
        <button onClick={() => navigate('/login')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-700 mb-7 transition-colors font-medium">
          <ArrowLeft className="w-4 h-4" /> Voltar ao login
        </button>

        {enviado ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 bg-emerald-50 border border-emerald-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Mail className="w-7 h-7 text-emerald-600" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-2 tracking-tight">E-mail enviado!</h2>
            <p className="text-sm text-slate-500 leading-relaxed">
              Se o e-mail estiver cadastrado, você receberá as instruções em breve. Verifique também a caixa de spam.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="btn-primary mt-6 w-full py-2.5"
            >
              Voltar ao login
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-lg font-bold text-slate-900 mb-1 tracking-tight">Esqueceu a senha?</h2>
            <p className="text-sm text-slate-500 mb-7 leading-relaxed">
              Digite seu e-mail e enviaremos um link para redefinir a senha.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">E-mail</label>
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
                <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  {erro}
                </div>
              )}
              <button
                type="submit"
                disabled={carregando}
                className="btn-primary w-full py-2.5 disabled:opacity-50"
              >
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
