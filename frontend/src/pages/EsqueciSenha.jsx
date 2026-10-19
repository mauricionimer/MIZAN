import ThemeToggle from '../components/ThemeToggle'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, CheckCircle2 } from 'lucide-react'
import { LogoMark } from '../components/Logo'

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
      else setErro('Não foi possível falar com o servidor. Tente novamente.')
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <ThemeToggle className="fixed top-4 right-4 z-50" />
      <div className="flex items-center gap-2.5 mb-10">
        <LogoMark className="h-6 w-6 shrink-0" />
        <span className="text-ink text-xl font-bold tracking-tight">Mizan</span>
      </div>

      <div className="w-full max-w-sm rounded-2xl p-8"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          boxShadow: '0 16px 48px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.30)',
        }}>
        <button type="button" onClick={() => navigate('/login')}
          className="flex items-center gap-1.5 text-sm mb-7 transition-colors font-medium"
          style={{ color: 'var(--ink-2)' }}
          onMouseOver={e => e.currentTarget.style.color = 'var(--ink)'}
          onMouseOut={e => e.currentTarget.style.color = 'var(--ink-2)'}>
          <ArrowLeft className="w-4 h-4" aria-hidden="true" /> Voltar ao login
        </button>

        {enviado ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-2 tracking-tight">Pedido enviado</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              Se o e-mail estiver cadastrado, o link chega em instantes. Confira também o spam.
            </p>
            <button onClick={() => navigate('/login')} className="btn-primary mt-6 w-full py-2.5">
              Voltar ao login
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-lg font-bold text-ink mb-1 tracking-tight">Esqueceu a senha?</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              Digite seu e-mail e enviaremos um link para redefinir a senha.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="esqueci-email" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>E-mail</label>
                <input
                  id="esqueci-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  className="input-base"
                />
              </div>
              {erro && (
                <div role="alert" className="text-sm rounded-xl px-4 py-3"
                  style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
                  {erro}
                </div>
              )}
              <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Enviando…</>
                  : 'Enviar link de redefinição'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
