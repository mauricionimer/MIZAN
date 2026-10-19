import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound, Eye, EyeOff, Loader2, CheckCircle2 } from 'lucide-react'
import { LogoMark } from '../components/Logo'
import { textoDoDetalhe } from '../api'

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

  useEffect(() => { if (!token) navigate('/login') }, [token, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    if (nova.length < 8 || /^\d+$/.test(nova) || /^[a-zA-Z]+$/.test(nova)) {
      setErro('A senha precisa ter no mínimo 8 caracteres, com letras e números.'); return
    }
    if (nova !== confirmar) { setErro('As duas senhas não são iguais.'); return }
    setCarregando(true)
    try {
      const res = await fetch(`${BASE}/auth/redefinir-senha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, nova_senha: nova }),
      })
      if (!res.ok) {
        const dados = await res.json().catch(() => null)
        throw new Error(textoDoDetalhe(dados?.detail, res.status))
      }
      setSucesso(true)
    } catch (e) {
      setErro(e.name === 'TypeError' ? 'Não foi possível falar com o servidor. Tente novamente.' : e.message)
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
        {sucesso ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-2 tracking-tight">Senha redefinida</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              Entre com a nova senha.
            </p>
            <button type="button" onClick={() => navigate('/login')} className="btn-primary w-full py-2.5">
              Ir para o login
            </button>
          </div>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
              style={{ background: 'rgb(var(--c-royal) / 0.12)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
              <KeyRound className="w-6 h-6" style={{ color: 'var(--accent-text)' }} aria-hidden="true" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-1 tracking-tight">Nova senha</h2>
            <p className="text-sm mb-7" style={{ color: 'var(--ink-2)' }}>
              Mínimo de 8 caracteres, com letras e números.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="redef-nova" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Nova senha</label>
                <div className="relative">
                  <input id="redef-nova" autoComplete="new-password" type={showNova ? 'text' : 'password'} required value={nova}
                    onChange={e => setNova(e.target.value)} className="input-base pr-11"
                    placeholder="mínimo 8 caracteres, letras e números" />
                  <button type="button" onClick={() => setShowNova(s => !s)} aria-label={showNova ? 'Ocultar nova senha' : 'Mostrar nova senha'}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: 'var(--ink-3)' }}>
                    {showNova ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label htmlFor="redef-confirmar" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Confirmar nova senha</label>
                <div className="relative">
                  <input id="redef-confirmar" autoComplete="new-password" type={showConf ? 'text' : 'password'} required value={confirmar}
                    onChange={e => setConfirmar(e.target.value)} className="input-base pr-11"
                    placeholder="repita a nova senha" />
                  <button type="button" onClick={() => setShowConf(s => !s)} aria-label={showConf ? 'Ocultar confirmação' : 'Mostrar confirmação'}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: 'var(--ink-3)' }}>
                    {showConf ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {erro && (
                <div role="alert" className="text-sm rounded-xl px-4 py-3"
                  style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
                  {erro}
                </div>
              )}
              <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando…</> : 'Salvar nova senha'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
