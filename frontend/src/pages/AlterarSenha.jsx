import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { KeyRound, Eye, EyeOff, Trash2, CheckCircle2, ShieldCheck, UserRound } from 'lucide-react'
import { alterarSenha, deletarConta } from '../api'
import CabecalhoPagina from '../components/CabecalhoPagina'

const VAZIO = { senha_atual: '', nova_senha: '', confirmar: '' }

// Fora do componente da página: definido lá dentro, o React recriava o
// <input> a cada letra e o cursor saía do campo.
function CampoSenha({ id, label, valor, aoMudar, autoComplete }) {
  const [mostrar, setMostrar] = useState(false)
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-semibold text-ink-2">{label}</label>
      <div className="relative">
        <input
          id={id}
          type={mostrar ? 'text' : 'password'}
          required
          autoComplete={autoComplete}
          value={valor}
          onChange={e => aoMudar(e.target.value)}
          className="input-base h-[46px] rounded-[12px] pl-3.5 pr-11 text-[15px]"
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
    <div role="alert" className="rounded-[14px] px-4 py-3 text-sm"
      style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
      {children}
    </div>
  )
}

export default function AlterarSenha() {
  const { logout, isComando, trocarToken, usuario } = useAuth()
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

  const papel = { comando: 'Comando', admin: 'Administrador', operador: 'Operador' }[usuario?.role] || usuario?.role
  const iniciais = String(usuario?.nome || usuario?.email || '').trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase()

  return (
    <AppShell titulo="Minha conta">
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <CabecalhoPagina rotulo="Conta" icone={UserRound} titulo="Minha conta" ajuda="senha-e-sessao" className="!mb-2"
          subtitulo="Seus dados de acesso e segurança." />

        <section className="flex flex-wrap items-center gap-4 rounded-[22px] border border-line bg-surface px-6 py-5">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[var(--royal-soft)] text-lg font-bold text-accent-text" aria-hidden="true">{iniciais || '·'}</span>
          <div className="min-w-0">
            <p className="truncate text-[19px] font-semibold text-ink">{usuario?.nome || 'Sem nome'}</p>
            <p className="truncate text-sm text-ink-2">{[usuario?.email, papel, usuario?.empresa_id].filter(Boolean).join(' · ')}</p>
          </div>
        </section>

        <div className="grid items-start gap-4 lg:grid-cols-2">
          <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="conta-senha">
            <h2 id="conta-senha" className="flex items-center gap-2 text-[17px] font-semibold text-ink"><KeyRound className="h-4 w-4 text-ink-3" aria-hidden="true" /> Senha</h2>
            <p className="mt-0.5 text-[13px] text-ink-2">Mínimo de 8 caracteres, com letras e números.</p>
            {sucesso ? (
              <div className="mt-5 flex flex-col items-start gap-3 rounded-[14px] border border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)] px-4 py-4" role="status">
                <p className="flex items-center gap-2 font-semibold text-ink"><CheckCircle2 className="h-5 w-5 text-[var(--success)]" aria-hidden="true" /> Senha alterada</p>
                <p className="text-sm text-ink-2">As outras sessões abertas com a senha antiga foram encerradas.</p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => navigate(homePath)} className="btn-primary">Voltar ao início</button>
                  <button type="button" onClick={() => setSucesso(false)} className="btn-secondary">Trocar de novo</button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="mt-5 space-y-4">
                <CampoSenha id="senha-atual" label="Senha atual" autoComplete="current-password"
                  valor={form.senha_atual} aoMudar={mudar('senha_atual')} />
                <CampoSenha id="senha-nova" label="Nova senha" autoComplete="new-password"
                  valor={form.nova_senha} aoMudar={mudar('nova_senha')} />
                <CampoSenha id="senha-confirmar" label="Confirmar nova senha" autoComplete="new-password"
                  valor={form.confirmar} aoMudar={mudar('confirmar')} />
                <Erro>{erro}</Erro>
                <button type="submit" disabled={carregando} className="btn-primary w-full disabled:opacity-50">
                  {carregando ? 'Salvando…' : 'Salvar nova senha'}
                </button>
              </form>
            )}
          </section>

          <div className="space-y-4">
            <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="conta-2fa">
              <h2 id="conta-2fa" className="flex items-center gap-2 text-[17px] font-semibold text-ink"><ShieldCheck className="h-4 w-4 text-ink-3" aria-hidden="true" /> Verificação em duas etapas</h2>
              <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">Além da senha, um código do aplicativo autenticador no celular. Protege a conta se a senha vazar.</p>
              <button type="button" onClick={() => navigate('/seguranca')} className="btn-secondary mt-4">Abrir verificação em duas etapas</button>
            </section>

            <ExcluirConta onExcluida={() => { logout(); navigate('/login') }} empresa={usuario?.empresa_id} />
          </div>
        </div>
      </div>
    </AppShell>
  )
}

// O servidor pede a senha de novo para excluir: só o token aberto no
// navegador não basta.
function ExcluirConta({ onExcluida, empresa }) {
  const [confirmando, setConfirmando] = useState(false)
  const [senha, setSenha]             = useState('')
  const [excluindo, setExcluindo]     = useState(false)
  const [erro, setErro]               = useState('')
  // Duas travas antes de apagar: marcar que entendeu e confirmar com um
  // segundo clique (que expira em 5 s). O botão seguro é o principal.
  const [entendo, setEntendo]         = useState(false)
  const [armado, setArmado]           = useState(false)
  useEffect(() => {
    if (!armado) return
    const t = setTimeout(() => setArmado(false), 5000)
    return () => clearTimeout(t)
  }, [armado])

  async function confirmar(e) {
    e.preventDefault()
    if (!senha) { setErro('Digite sua senha para confirmar.'); return }
    if (!entendo) { setErro('Marque que entendeu que não dá para desfazer.'); return }
    if (!armado) { setArmado(true); setErro(''); return }
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
    setConfirmando(false); setSenha(''); setErro(''); setEntendo(false); setArmado(false)
  }

  return (
    <section className="rounded-[22px] border border-[color-mix(in_srgb,var(--danger)_40%,transparent)] bg-surface px-6 py-[22px]" aria-labelledby="conta-excluir">
      <h2 id="conta-excluir" className="flex items-center gap-2 text-[17px] font-semibold text-[var(--danger)]"><Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir conta</h2>
      <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">Direito previsto na LGPD. Os registros de auditoria da empresa continuam, sem o seu nome. Não dá para desfazer.</p>
      {!confirmando ? (
        <button type="button" onClick={() => setConfirmando(true)} className="btn-ghost-danger mt-4">
          <Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir minha conta
        </button>
      ) : (
        <form onSubmit={confirmar} className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[14px] border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-[13px] leading-relaxed text-ink">
              <b className="block">Apaga</b>Seu nome, e-mail, senha e acesso. Você sai da MIZAN na hora.
            </div>
            <div className="rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-3 text-[13px] leading-relaxed text-ink">
              <b className="block">Continua</b>Carteiras, pagamentos, contatos e auditoria{empresa ? ` da empresa ${empresa}` : ' da empresa'}, sem o seu nome.
            </div>
          </div>
          <CampoSenha id="excluir-senha" label="Sua senha" autoComplete="current-password"
            valor={senha} aoMudar={v => { setSenha(v); setArmado(false) }} />
          <label className="flex items-start gap-2.5 rounded-[14px] border border-line px-4 py-3 text-sm text-ink">
            <input type="checkbox" checked={entendo} onChange={e => { setEntendo(e.target.checked); setArmado(false) }}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--danger)]" />
            Entendo que a exclusão é definitiva e não dá para desfazer.
          </label>
          <Erro>{erro}</Erro>
          {armado && (
            <p role="alert" className="text-sm font-semibold" style={{ color: 'var(--danger)' }}>
              Clique de novo em “Excluir definitivamente” para confirmar.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button type="button" onClick={cancelar} className="btn-primary">
              Manter minha conta
            </button>
            <button type="submit" disabled={excluindo || !entendo || !senha} className="btn-danger ml-auto">
              {excluindo ? 'Excluindo…' : armado ? 'Excluir definitivamente' : 'Excluir conta'}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
