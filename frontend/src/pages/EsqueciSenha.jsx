import ThemeToggle from '../components/ThemeToggle'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, CheckCircle2, ShieldCheck, Eye, EyeOff } from 'lucide-react'
import { LogoCompleto } from '../components/Logo'
import { textoDoDetalhe } from '../api'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

// Trocar a senha com o código do aplicativo autenticador (sem e-mail). O link por e-mail
// fica só como reserva para conta que ainda não configurou o aplicativo.
export default function EsqueciSenha() {
  const navigate = useNavigate()
  const [modo, setModo]             = useState('app')          // app | email
  const [email, setEmail]           = useState('')
  const [codigo, setCodigo]         = useState('')
  const [recuperacao, setRecuperacao] = useState(false)
  const [nova, setNova]             = useState('')
  const [confirmar, setConfirmar]   = useState('')
  const [verNova, setVerNova]       = useState(false)
  const [verConf, setVerConf]       = useState(false)
  const [pronto, setPronto]         = useState(null)           // 'app' | 'email'
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState('')

  async function enviar(caminho, corpo) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 20000)
    try {
      const res = await fetch(`${BASE}${caminho}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo),
        signal: controller.signal,
      })
      if (!res.ok) {
        const dados = await res.json().catch(() => null)
        throw new Error(textoDoDetalhe(dados?.detail, res.status))
      }
    } finally {
      clearTimeout(timer)
    }
  }

  function falhou(e) {
    if (e.name === 'AbortError') setErro('O servidor demorou muito. Tente novamente em instantes.')
    else if (e.name === 'TypeError') setErro('Não foi possível falar com o servidor. Tente novamente.')
    else setErro(e.message)
  }

  async function trocarComApp(e) {
    e.preventDefault()
    setErro('')
    if (nova.length < 8 || /^\d+$/.test(nova) || /^[a-zA-Z]+$/.test(nova)) {
      setErro('A senha precisa ter no mínimo 8 caracteres, com letras e números.'); return
    }
    if (nova !== confirmar) { setErro('As duas senhas não são iguais.'); return }
    setCarregando(true)
    try {
      await enviar('/auth/esqueci-senha/2fa', { email, codigo, nova_senha: nova })
      setPronto('app')
    } catch (err) {
      falhou(err)
    } finally {
      setCarregando(false)
    }
  }

  async function pedirLink(e) {
    e.preventDefault()
    setErro('')
    setCarregando(true)
    try {
      await enviar('/auth/esqueci-senha', { email })
      setPronto('email')
    } catch (err) {
      falhou(err)
    } finally {
      setCarregando(false)
    }
  }

  function trocarModo(novo) {
    setModo(novo); setErro(''); setCodigo(''); setNova(''); setConfirmar('')
  }

  const rotulo = { color: 'var(--ink-2)' }
  const campoSenha = (id, rot, valor, aoMudar, ver, aoVer, placeholder) => (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold mb-1.5" style={rotulo}>{rot}</label>
      <div className="relative">
        <input id={id} autoComplete="new-password" type={ver ? 'text' : 'password'} required value={valor}
          onChange={e => aoMudar(e.target.value)} className="input-base pr-11" placeholder={placeholder} />
        <button type="button" onClick={aoVer} aria-label={ver ? `Ocultar ${rot.toLowerCase()}` : `Mostrar ${rot.toLowerCase()}`}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors" style={{ color: 'var(--ink-3)' }}>
          {ver ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
  const caixaErro = erro && (
    <div role="alert" className="text-sm rounded-xl px-4 py-3"
      style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
      {erro}
    </div>
  )

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <ThemeToggle className="fixed top-4 right-4 z-50" />
      <LogoCompleto className="mb-10 h-8 w-auto text-ink" />

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

        {pronto ? (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-2 tracking-tight">
              {pronto === 'app' ? 'Senha redefinida' : 'Pedido enviado'}
            </h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              {pronto === 'app'
                ? 'Entre com a nova senha. As sessões abertas nos outros aparelhos foram encerradas.'
                : 'Se o e-mail estiver cadastrado e a conta ainda não usar o aplicativo autenticador, o link chega em instantes. Confira também o spam.'}
            </p>
            <button onClick={() => navigate('/login')} className="btn-primary mt-6 w-full py-2.5">
              Ir para o login
            </button>
          </div>
        ) : modo === 'app' ? (
          <>
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
              style={{ background: 'rgb(var(--c-royal) / 0.12)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
              <ShieldCheck className="w-6 h-6" style={{ color: 'var(--accent-text)' }} aria-hidden="true" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-1 tracking-tight">Esqueceu a senha?</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              Digite seu e-mail e o código do aplicativo autenticador para criar uma nova senha. Não enviamos nada por e-mail.
            </p>
            <form onSubmit={trocarComApp} className="space-y-4">
              <div>
                <label htmlFor="esqueci-email" className="block text-xs font-semibold mb-1.5" style={rotulo}>E-mail</label>
                <input id="esqueci-email" type="email" autoComplete="email" required value={email}
                  onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" className="input-base" />
              </div>
              <div>
                <label htmlFor="esqueci-codigo" className="block text-xs font-semibold mb-1.5" style={rotulo}>
                  {recuperacao ? 'Código de recuperação' : 'Código de 6 dígitos do aplicativo'}
                </label>
                <input id="esqueci-codigo" className="input-base tracking-widest text-center text-lg" required
                  autoComplete="one-time-code" inputMode={recuperacao ? 'text' : 'numeric'}
                  placeholder={recuperacao ? 'xxxxx-xxxxx' : '000000'} value={codigo}
                  onChange={e => setCodigo(recuperacao ? e.target.value.slice(0, 11) : e.target.value.replace(/\D/g, '').slice(0, 6))} />
                <button type="button" className="login-link mt-2 text-xs"
                  onClick={() => { setRecuperacao(r => !r); setCodigo(''); setErro('') }}>
                  {recuperacao ? 'Usar o código do aplicativo' : 'Perdi o celular: usar código de recuperação'}
                </button>
              </div>
              {campoSenha('esqueci-nova', 'Nova senha', nova, setNova, verNova, () => setVerNova(v => !v), 'mínimo 8 caracteres, letras e números')}
              {campoSenha('esqueci-confirmar', 'Confirmar nova senha', confirmar, setConfirmar, verConf, () => setVerConf(v => !v), 'repita a nova senha')}
              {caixaErro}
              <button type="submit" disabled={carregando || (!recuperacao && codigo.length !== 6)}
                className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando…</> : 'Salvar nova senha'}
              </button>
            </form>
            <p className="text-xs mt-6 leading-relaxed text-center" style={{ color: 'var(--ink-3)' }}>
              Ainda não configurou o aplicativo?{' '}
              <button type="button" className="login-link text-xs" onClick={() => trocarModo('email')}>
                Receber um link por e-mail
              </button>
            </p>
          </>
        ) : (
          <>
            <h2 className="text-lg font-bold text-ink mb-1 tracking-tight">Receber link por e-mail</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              Só para quem ainda não configurou o aplicativo autenticador. Quem já configurou usa o código do aplicativo.
            </p>
            <form onSubmit={pedirLink} className="space-y-4">
              <div>
                <label htmlFor="esqueci-email-link" className="block text-xs font-semibold mb-1.5" style={rotulo}>E-mail</label>
                <input id="esqueci-email-link" type="email" autoComplete="email" required value={email}
                  onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" className="input-base" />
              </div>
              {caixaErro}
              <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                {carregando ? <><Loader2 className="h-4 w-4 animate-spin" /> Enviando…</> : 'Enviar link de redefinição'}
              </button>
            </form>
            <p className="text-xs mt-6 text-center">
              <button type="button" className="login-link text-xs" onClick={() => trocarModo('app')}>
                Usar o código do aplicativo
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
