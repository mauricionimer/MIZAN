import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Copy, Download, CheckCircle2, Smartphone, KeyRound, LogOut, Loader2 } from 'lucide-react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { situacao2fa, iniciar2fa, confirmar2fa, novosCodigos2fa, desativar2fa, MSG_SENHA_PARA_CONFIGURAR } from '../api'

// Verificação em duas etapas (backend/dois_fatores.py).
// - obrigatorio: tela cheia, no primeiro acesso de administrador (nada mais abre antes);
// - no perfil (/seguranca): ligar, trocar de celular, novos códigos e, se não for
//   obrigatório, desligar.

function Erro({ children }) {
  if (!children) return null
  return (
    <div role="alert" className="rounded-xl px-4 py-3 text-sm"
      style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
      {children}
    </div>
  )
}

function CampoCodigo({ id, valor, aoMudar, rotulo = 'Código de 6 dígitos do app', aceitaRecuperacao = false }) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>{rotulo}</label>
      <input id={id} className="input-base tracking-widest text-center text-lg" required autoComplete="one-time-code"
        inputMode={aceitaRecuperacao ? 'text' : 'numeric'} placeholder={aceitaRecuperacao ? '000000 ou xxxxx-xxxxx' : '000000'}
        value={valor}
        onChange={e => aoMudar(aceitaRecuperacao ? e.target.value.slice(0, 11) : e.target.value.replace(/\D/g, '').slice(0, 6))} />
    </div>
  )
}

function Cartao({ children }) {
  return (
    <div className="w-full max-w-md mx-auto rounded-2xl p-6 sm:p-8"
      style={{ background: 'var(--surface)', border: '1px solid var(--line)', boxShadow: '0 16px 48px rgba(0,0,0,0.30)' }}>
      {children}
    </div>
  )
}

function Cabecalho({ subtitulo }) {
  return (
    <>
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: 'rgb(var(--c-royal) / 0.12)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
          <ShieldCheck className="w-5 h-5" style={{ color: 'var(--accent-text)' }} aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-ink tracking-tight">Verificação em duas etapas</h1>
          <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{subtitulo}</p>
        </div>
      </div>
      <div className="border-t my-5" style={{ borderColor: 'var(--line)' }} />
    </>
  )
}

function CodigosRecuperacao({ codigos, aoConcluir, textoBotao }) {
  const [guardou, setGuardou] = useState(false)
  const [copiado, setCopiado] = useState(false)
  const texto = `Mizan: códigos de recuperação da verificação em duas etapas\n` +
    `Cada código vale uma vez. Guarde em lugar seguro.\n\n${codigos.join('\n')}\n`
  function copiar() {
    navigator.clipboard?.writeText(texto).then(() => setCopiado(true)).catch(() => {})
  }
  function baixar() {
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain' }))
    const a = document.createElement('a')
    a.href = url; a.download = 'mizan-codigos-de-recuperacao.txt'; a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--success)' }}>
        <CheckCircle2 className="w-4 h-4" aria-hidden="true" /> Verificação em duas etapas ligada
      </div>
      <p className="text-sm" style={{ color: 'var(--ink-2)' }}>
        Se perder o celular, entre com um destes códigos. <strong>Cada um vale uma vez</strong> e eles não
        aparecem de novo: guarde agora em lugar seguro.
      </p>
      <ul className="grid grid-cols-2 gap-2 font-mono text-sm rounded-xl p-3"
        style={{ background: 'var(--surface-2, var(--raise-2))', border: '1px solid var(--line)' }}>
        {codigos.map(c => <li key={c} className="text-center text-ink">{c}</li>)}
      </ul>
      <div className="flex gap-2">
        <button type="button" onClick={copiar} className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm">
          <Copy className="w-4 h-4" aria-hidden="true" /> {copiado ? 'Copiados' : 'Copiar'}
        </button>
        <button type="button" onClick={baixar} className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm">
          <Download className="w-4 h-4" aria-hidden="true" /> Baixar
        </button>
      </div>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={guardou} onChange={e => setGuardou(e.target.checked)} />
        Guardei os códigos em lugar seguro
      </label>
      <button type="button" disabled={!guardou} onClick={aoConcluir} className="btn-primary w-full py-2.5 disabled:opacity-50">
        {textoBotao}
      </button>
    </div>
  )
}

export default function DoisFatores({ obrigatorio = false }) {
  const { trocarToken, concluir2fa, logout, usuario } = useAuth()
  const navigate = useNavigate()
  const [sit, setSit] = useState(null)
  const [etapa, setEtapa] = useState('inicio')          // inicio | qr | codigos
  const [qr, setQr] = useState(null)                    // { segredo, uri, qr }
  const [codigo, setCodigo] = useState('')
  const [codigos, setCodigos] = useState([])
  const [acao, setAcao] = useState(null)                // trocar | codigos | desligar (2FA já ligado)
  const [codigoAtual, setCodigoAtual] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [pedirSenha, setPedirSenha] = useState(false)   // sessão antiga: o servidor pede a senha para configurar

  function carregar() { return situacao2fa().then(setSit).catch(e => setErro(e.message)) }
  useEffect(() => { carregar() }, [])                    // eslint-disable-line react-hooks/exhaustive-deps

  async function rodar(fn) {
    setOcupado(true); setErro('')
    try { await fn() } catch (e) { setErro(e.message) } finally { setOcupado(false) }
  }

  const comecar = (atual = '') => rodar(async () => {
    try {
      setQr(await iniciar2fa(atual, pedirSenha ? senha : ''))
    } catch (e) {
      if (e.message === MSG_SENHA_PARA_CONFIGURAR) setPedirSenha(true)
      throw e
    }
    setCodigo(''); setEtapa('qr'); setAcao(null); setCodigoAtual(''); setSenha(''); setPedirSenha(false)
  })

  const confirmar = e => { e.preventDefault(); rodar(async () => {
    const r = await confirmar2fa(codigo)
    trocarToken(r.token)                 // a partir daqui só vale a sessão com o código
    setCodigos(r.codigos_recuperacao || []); setEtapa('codigos')
  }) }

  const gerarCodigos = e => { e.preventDefault(); rodar(async () => {
    const r = await novosCodigos2fa(codigoAtual)
    setCodigos(r.codigos_recuperacao || []); setCodigoAtual(''); setAcao(null); setEtapa('codigos')
  }) }

  const desligar = e => { e.preventDefault(); rodar(async () => {
    const r = await desativar2fa(senha, codigoAtual)
    trocarToken(r.token); setSenha(''); setCodigoAtual(''); setAcao(null); await carregar()
  }) }

  function concluir() {
    concluir2fa()
    if (obrigatorio) navigate('/inicio', { replace: true })
    else { setEtapa('inicio'); carregar() }
  }

  let corpo
  if (!sit && !erro) {
    corpo = <div className="flex items-center gap-2 text-sm text-ink-2"><Loader2 className="w-4 h-4 animate-spin" /> Carregando…</div>
  } else if (sit && !sit.disponivel) {
    corpo = <p className="text-sm" style={{ color: 'var(--ink-2)' }}>A verificação em duas etapas ainda não foi habilitada no servidor.</p>
  } else if (etapa === 'qr' && qr) {
    corpo = (
      <form onSubmit={confirmar} className="space-y-4">
        <ol className="text-sm space-y-1.5 list-decimal pl-5" style={{ color: 'var(--ink-2)' }}>
          <li>Instale um app autenticador no celular: Google Authenticator, Microsoft Authenticator ou Authy.</li>
          <li>No app, toque em <strong>+</strong> e leia o QR code abaixo.</li>
          <li>Digite o código de 6 dígitos que aparece no app.</li>
        </ol>
        {qr.qr && (
          <div className="flex justify-center">
            <img src={qr.qr} alt="QR code para o app autenticador" width={200} height={200}
              className="rounded-xl" style={{ background: '#fff', padding: 8 }} />
          </div>
        )}
        <div className="text-xs space-y-1" style={{ color: 'var(--ink-3)' }}>
          <p>Não consegue ler o QR? Digite esta chave no app:</p>
          <p className="font-mono text-sm text-ink break-all select-all">{qr.segredo.match(/.{1,4}/g).join(' ')}</p>
          <a href={qr.uri} className="inline-flex items-center gap-1 underline" style={{ color: 'var(--accent-text)' }}>
            <Smartphone className="w-3.5 h-3.5" aria-hidden="true" /> Abrir no app deste celular
          </a>
        </div>
        <CampoCodigo id="dois-fatores-codigo" valor={codigo} aoMudar={setCodigo} />
        <Erro>{erro}</Erro>
        <button type="submit" disabled={ocupado || codigo.length !== 6} className="btn-primary w-full py-2.5 disabled:opacity-50">
          {ocupado ? 'Conferindo…' : 'Confirmar e ligar'}
        </button>
      </form>
    )
  } else if (etapa === 'codigos') {
    corpo = <CodigosRecuperacao codigos={codigos} aoConcluir={concluir} textoBotao={obrigatorio ? 'Entrar no Mizan' : 'Concluir'} />
  } else if (sit?.ativo) {
    corpo = (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--success)' }}>
          <CheckCircle2 className="w-4 h-4" aria-hidden="true" /> Ligada
          {sit.ativado_em && <span className="font-normal" style={{ color: 'var(--ink-3)' }}>
            desde {new Date(sit.ativado_em).toLocaleDateString('pt-BR')}</span>}
        </div>
        <p className="text-sm" style={{ color: 'var(--ink-2)' }}>
          Códigos de recuperação restantes: <strong>{sit.codigos_restantes}</strong>
        </p>
        {!acao && (
          <div className="flex flex-col gap-2">
            <button type="button" className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm" onClick={() => setAcao('trocar')}>
              <Smartphone className="w-4 h-4" aria-hidden="true" /> Trocar de celular
            </button>
            <button type="button" className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm" onClick={() => setAcao('codigos')}>
              <KeyRound className="w-4 h-4" aria-hidden="true" /> Gerar novos códigos de recuperação
            </button>
            {!sit.obrigatorio && (
              <button type="button" className="px-3 py-2 text-sm rounded-xl text-left hover:bg-red-500/10" style={{ color: 'var(--danger)' }}
                onClick={() => setAcao('desligar')}>
                Desligar a verificação em duas etapas
              </button>
            )}
          </div>
        )}
        {acao === 'trocar' && (
          <form onSubmit={e => { e.preventDefault(); comecar(codigoAtual) }} className="space-y-3">
            <p className="text-sm" style={{ color: 'var(--ink-2)' }}>Para trocar de celular, digite o código atual (ou um de recuperação).</p>
            <CampoCodigo id="dois-fatores-atual" valor={codigoAtual} aoMudar={setCodigoAtual} rotulo="Código atual" aceitaRecuperacao />
            <Erro>{erro}</Erro>
            <div className="flex gap-2">
              <button type="submit" disabled={ocupado || !codigoAtual} className="btn-primary px-4 py-2 disabled:opacity-50">Continuar</button>
              <button type="button" onClick={() => { setAcao(null); setErro('') }} className="px-4 py-2 text-sm" style={{ color: 'var(--ink-2)' }}>Cancelar</button>
            </div>
          </form>
        )}
        {acao === 'codigos' && (
          <form onSubmit={gerarCodigos} className="space-y-3">
            <p className="text-sm" style={{ color: 'var(--ink-2)' }}>Os códigos antigos deixam de valer.</p>
            <CampoCodigo id="dois-fatores-novos" valor={codigoAtual} aoMudar={setCodigoAtual} rotulo="Código atual" aceitaRecuperacao />
            <Erro>{erro}</Erro>
            <div className="flex gap-2">
              <button type="submit" disabled={ocupado || !codigoAtual} className="btn-primary px-4 py-2 disabled:opacity-50">Gerar</button>
              <button type="button" onClick={() => { setAcao(null); setErro('') }} className="px-4 py-2 text-sm" style={{ color: 'var(--ink-2)' }}>Cancelar</button>
            </div>
          </form>
        )}
        {acao === 'desligar' && (
          <form onSubmit={desligar} className="space-y-3">
            <div>
              <label htmlFor="dois-fatores-senha" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Sua senha</label>
              <input id="dois-fatores-senha" type="password" className="input-base" required autoComplete="current-password"
                value={senha} onChange={e => setSenha(e.target.value)} />
            </div>
            <CampoCodigo id="dois-fatores-desligar" valor={codigoAtual} aoMudar={setCodigoAtual} rotulo="Código atual" aceitaRecuperacao />
            <Erro>{erro}</Erro>
            <div className="flex gap-2">
              <button type="submit" disabled={ocupado} className="btn-danger">Desligar</button>
              <button type="button" onClick={() => { setAcao(null); setErro('') }} className="px-4 py-2 text-sm" style={{ color: 'var(--ink-2)' }}>Cancelar</button>
            </div>
          </form>
        )}
      </div>
    )
  } else {
    corpo = (
      <div className="space-y-4">
        <p className="text-sm" style={{ color: 'var(--ink-2)' }}>
          {obrigatorio
            ? 'Para proteger os dados dos devedores, administradores entram com a senha e com um código do celular. Leva um minuto.'
            : 'Além da senha, peça um código do celular ao entrar. Recomendado.'}
        </p>
        {pedirSenha && (
          <div>
            <label htmlFor="dois-fatores-senha-config" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Sua senha</label>
            <input id="dois-fatores-senha-config" type="password" className="input-base" required autoComplete="current-password"
              value={senha} onChange={e => setSenha(e.target.value)} />
          </div>
        )}
        <Erro>{erro === MSG_SENHA_PARA_CONFIGURAR && senha ? '' : erro}</Erro>
        <button type="button" disabled={ocupado || (pedirSenha && !senha)} onClick={() => comecar()} className="btn-primary w-full py-2.5 disabled:opacity-50">
          {ocupado ? 'Preparando…' : 'Configurar agora'}
        </button>
      </div>
    )
  }

  if (obrigatorio) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 py-10" style={{ background: 'var(--bg)' }}>
        <Cartao>
          <Cabecalho subtitulo={usuario?.email || 'Obrigatória para administradores'} />
          {corpo}
        </Cartao>
        <button type="button" onClick={logout} className="mt-6 flex items-center gap-1.5 text-sm" style={{ color: 'var(--ink-3)' }}>
          <LogOut className="w-4 h-4" aria-hidden="true" /> Sair
        </button>
      </div>
    )
  }
  return (
    <AppShell titulo="Verificação em duas etapas">
      <Cartao>
        <Cabecalho subtitulo="Senha + código do celular ao entrar" />
        {corpo}
      </Cartao>
    </AppShell>
  )
}
