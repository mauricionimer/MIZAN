import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Mail, Loader2 } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export default function EsqueciSenha() {
  const navigate = useNavigate()
  const [email, setEmail]         = useState('')
  const [enviado, setEnviado]     = useState(false)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]           = useState('')

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
        <button onClick={() => navigate('/login')} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-700 mb-6">
          <ArrowLeft className="w-4 h-4" /> Voltar ao login
        </button>

        {enviado ? (
          <div className="text-center py-4">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <Mail className="w-6 h-6 text-green-600" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">E-mail enviado!</h2>
            <p className="text-sm text-slate-500">
              Se o e-mail estiver cadastrado, você receberá as instruções em breve. Verifique também a caixa de spam.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="mt-6 w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl text-sm font-medium"
            >
              Voltar ao login
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-base font-semibold text-slate-800 mb-1">Esqueceu a senha?</h2>
            <p className="text-sm text-slate-500 mb-6">
              Digite seu e-mail e enviaremos um link para redefinir a senha.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">E-mail</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {erro && <p className="text-sm text-red-600">{erro}</p>}
              <button
                type="submit"
                disabled={carregando}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 flex items-center justify-center gap-2"
              >
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Enviando...</> : 'Enviar link de redefinição'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
