import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { KeyRound, Eye, EyeOff, Trash2, CheckCircle2 } from 'lucide-react'
import { alterarSenha, deletarConta } from '../api'
import DicaAjuda from '../components/DicaAjuda'

const VAZIO = { senha_atual: '', nova_senha: '', confirmar: '' }

// Fora do componente da página: definido lá dentro, o React recriava o
// <input> a cada letra e o cursor saía do campo.
function CampoSenha({ id, label, valor, aoMudar, autoComplete }) {
  const [mostrar, setMostrar] = useState(false)
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>{label}</label>
      <div className="relative">
        <input
          id={id}
          type={mostrar ? 'text' : 'password'}
          required
          autoComplete={autoComplete}
          value={valor}
          onChange={e => aoMudar(e.target.value)}
          className="input-base pr-11"
        />
        <button type="button" onClick={() => setMostrar(s => !s)}
          aria-label={mostrar ? `Ocultar ${label.toLowerCase()}` : `Mostrar ${label.toLowerCase()}`}
          aria-pressed={mostrar}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
          style={{ color: 'var(--ink-3)' }}>
          {mostrar ? <EyeOff className="w-4 h-4" aria-hidden="true" /> : <Eye className="w-4 h-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
  )
}

function Erro({ children }) {
  if (!children) return null
  return (
    <div role="alert" className="rounded-xl px-4 py-3 text-sm"
      style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
      {children}
    </div>
  )
}

export default function AlterarSenha() {
  const { logout, isComando, trocarToken } = useAuth()
  const navigate = useNavigate()
  const homePath = isComando ? '/comando' : '/'

  const [form, setForm]             = useState(VAZIO)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState('')
  const [sucesso, setSucesso]       = useState(false)
  const mudar = campo => valor => setForm(f => ({ ...f, [campo]: valor }))

  async function handleSubmit(e) {
    e.preventDefault()
    setErro('')
    if (form.nova_senha.length < 8 || /^\d+$/.test(form.nova_senha) || /^[a-zA-Z]+$/.test(form.nova_senha)) {
      setErro('A nova senha precisa ter no mínimo 8 caracteres, com letras e números.'); return
    }
    if (form.nova_senha !== form.confirmar) { setErro('A nova senha e a confirmação não são iguais.'); return }
    if (form.nova_senha === form.senha_atual) { setErro('A nova senha precisa ser diferente da atual.'); return }
    setCarregando(true)
    try {
      const dados = await alterarSenha(form.senha_atual, form.nova_senha)
      trocarToken(dados?.token)          // as outras sessões abertas caem; esta continua
      setSucesso(true)
      setForm(VAZIO)
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <AppShell titulo="Alterar senha">

      <div className="w-full max-w-md mx-auto">
        <div className="rounded-2xl p-8"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.30)',
          }}>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgb(var(--c-royal) / 0.12)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
              <KeyRound className="w-5 h-5" style={{ color: 'var(--accent-text)' }} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-ink tracking-tight">Alterar senha<DicaAjuda id="senha-e-sessao" /></h1>
              <p className="text-xs" style={{ color: 'var(--ink-3)' }}>Mínimo de 8 caracteres, com letras e números</p>
            </div>
          </div>

          <div className="border-t my-5" style={{ borderColor: 'var(--line)' }} />

          {sucesso ? (
            <div className="text-center py-6" role="status">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
                <CheckCircle2 className="w-7 h-7" style={{ color: 'var(--success)' }} aria-hidden="true" />
              </div>
              <h2 className="text-base font-bold text-ink mb-1 tracking-tight">Senha alterada</h2>
              <p className="text-sm mb-6" style={{ color: 'var(--ink-2)' }}>As outras sessões abertas com a senha antiga foram encerradas.</p>
              <button type="button" onClick={() => navigate(homePath)} className="btn-primary px-6 py-2.5">
                Voltar
              </button>
            </div>
          ) : (
            <>
              <form onSubmit={handleSubmit} className="space-y-4">
                <CampoSenha id="senha-atual" label="Senha atual" autoComplete="current-password"
                  valor={form.senha_atual} aoMudar={mudar('senha_atual')} />
                <CampoSenha id="senha-nova" label="Nova senha" autoComplete="new-password"
                  valor={form.nova_senha} aoMudar={mudar('nova_senha')} />
                <CampoSenha id="senha-confirmar" label="Confirmar nova senha" autoComplete="new-password"
                  valor={form.confirmar} aoMudar={mudar('confirmar')} />
                <Erro>{erro}</Erro>
                <button type="submit" disabled={carregando} className="btn-primary w-full py-2.5 disabled:opacity-50">
                  {carregando ? 'Salvando…' : 'Salvar nova senha'}
                </button>
              </form>
              <ExcluirConta onExcluida={() => { logout(); navigate('/login') }} />
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}

// O servidor pede a senha de novo para excluir: só o token aberto no
// navegador não basta.
function ExcluirConta({ onExcluida }) {
  const [confirmando, setConfirmando] = useState(false)
  const [senha, setSenha]             = useState('')
  const [excluindo, setExcluindo]     = useState(false)
  const [erro, setErro]               = useState('')

  async function confirmar(e) {
    e.preventDefault()
    if (!senha) { setErro('Digite sua senha para confirmar.'); return }
    setExcluindo(true); setErro('')
    try {
      await deletarConta(senha)
      onExcluida()
    } catch (err) {
      setErro(err.message)
      setExcluindo(false)
    }
  }

  function cancelar() {
    setConfirmando(false); setSenha(''); setErro('')
  }

  return (
    <div className="mt-8 border-t pt-6" style={{ borderColor: 'var(--line)' }}>
      <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--danger)' }}>Excluir conta</p>
      {!confirmando ? (
        <button type="button" onClick={() => setConfirmando(true)}
          className="flex items-center gap-2 text-sm px-3 py-2 rounded-xl transition-colors font-medium hover:bg-red-500/10"
          style={{ color: 'var(--danger)' }}>
          <Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir minha conta (LGPD)
        </button>
      ) : (
        <form onSubmit={confirmar} className="space-y-3">
          <div className="text-sm rounded-xl px-4 py-3 leading-relaxed"
            style={{ color: 'var(--ink)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
            Sua conta e seu nome saem dos registros. O histórico de contatos e as conexões ficam com a empresa, sem o seu nome.{' '}
            <strong>Não dá para desfazer.</strong>
          </div>
          <CampoSenha id="excluir-senha" label="Sua senha" autoComplete="current-password"
            valor={senha} aoMudar={setSenha} />
          <Erro>{erro}</Erro>
          <div className="flex gap-2">
            <button type="submit" disabled={excluindo} className="btn-danger">
              {excluindo ? 'Excluindo…' : 'Excluir conta'}
            </button>
            <button type="button" onClick={cancelar}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:bg-[var(--raise-2)]"
              style={{ color: 'var(--ink-2)' }}>
              Cancelar
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
