import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, KeyRound, Loader2, Copy, Ban } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import { LogoMark } from '../components/Logo'
import DicaAjuda from '../components/DicaAjuda'
import { useAuth } from '../context/AuthContext'
import { listarChavesApi, criarChaveApi, revogarChaveApi } from '../api'

const fmtData = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  : '—'

export default function ChavesApi() {
  const navigate = useNavigate()
  const { token } = useAuth()
  const [chaves, setChaves]   = useState([])
  const [empresa, setEmpresa] = useState('')
  const [rotulo, setRotulo]   = useState('')
  const [nova, setNova]       = useState(null)   // { chave, ... } — mostrada uma vez
  const [erro, setErro]       = useState('')
  const [ocupado, setOcupado] = useState(false)

  const carregar = useCallback(async () => {
    try { setChaves(await listarChavesApi(token)) } catch (e) { setErro(e.message) }
  }, [token])
  useEffect(() => { carregar() }, [carregar])

  async function criar(e) {
    e.preventDefault(); setErro(''); setNova(null); setOcupado(true)
    try {
      setNova(await criarChaveApi(token, empresa.trim().toLowerCase(), rotulo.trim()))
      setRotulo(''); await carregar()
    } catch (e2) { setErro(e2.message) } finally { setOcupado(false) }
  }

  async function revogar(c) {
    if (!window.confirm(`Revogar a chave "${c.rotulo || c.id}" de ${c.empresa_id}? A integração que a usa para de funcionar na hora.`)) return
    setErro('')
    try { await revogarChaveApi(token, c.id); await carregar() } catch (e) { setErro(e.message) }
  }

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/comando')} className="p-1 rounded-lg hover:bg-raise-2" style={{ color: 'var(--ink-3)' }} aria-label="Voltar">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <LogoMark className="h-5 w-5 shrink-0" />
          <span className="font-bold text-ink text-sm">Mizan</span>
          <span className="text-ink-4 text-sm">/</span>
          <span className="text-sm" style={{ color: 'var(--ink-2)' }}>Chaves de API</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-6">
        <section className="rounded-xl border border-line bg-surface p-6 space-y-4">
          <h1 className="text-lg font-bold text-ink flex items-center gap-2"><KeyRound className="h-5 w-5" /> Nova chave<DicaAjuda id="chaves-de-api" /></h1>
          <p className="text-sm text-ink-2">
            A chave permite que o sistema do cliente avise o Mizan dos pagamentos (webhook). Ela vale só para a empresa
            escolhida e é mostrada uma única vez.
          </p>
          <form onSubmit={criar} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <input value={empresa} onChange={e => setEmpresa(e.target.value)} placeholder="empresa_id (ex.: goias_bank)" aria-label="Empresa"
              className="rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink" />
            <input value={rotulo} onChange={e => setRotulo(e.target.value)} placeholder="Rótulo (ex.: webhook produção)" aria-label="Rótulo"
              className="rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink" />
            <button type="submit" disabled={ocupado || !empresa.trim() || rotulo.trim().length < 2}
              className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50">
              {ocupado ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} Criar
            </button>
          </form>
          {nova && (
            <div className="rounded-lg p-3 space-y-2" style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.25)' }}>
              <p className="text-xs font-semibold text-ink">{nova.aviso}</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all rounded bg-page px-2 py-1 text-xs text-ink">{nova.chave}</code>
                <button onClick={() => navigator.clipboard?.writeText(nova.chave)} aria-label="Copiar a chave"
                  className="rounded-lg bg-raise-2 p-2 text-ink hover:opacity-80"><Copy className="h-4 w-4" /></button>
              </div>
            </div>
          )}
          {erro && <p className="text-sm text-red-400" role="alert">{erro}</p>}
        </section>

        <section className="rounded-xl border border-line bg-surface p-6">
          <h2 className="mb-3 font-bold text-ink">Chaves existentes</h2>
          {chaves.length === 0 && <p className="text-sm text-ink-3">Nenhuma chave cadastrada.</p>}
          <ul className="space-y-2">
            {chaves.map(c => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3 text-xs">
                <div className="text-ink-2">
                  <p className="font-semibold text-ink">{c.rotulo || '(sem rótulo)'} · {c.empresa_id}</p>
                  <p>Criada {fmtData(c.created_at)} · último uso {fmtData(c.ultimo_uso)} · {c.ativa ? 'ativa' : 'revogada'}</p>
                </div>
                {c.ativa && (
                  <button onClick={() => revogar(c)} className="flex items-center gap-1 rounded-lg px-3 py-1.5 font-medium text-red-400 hover:bg-red-950/40">
                    <Ban className="h-3.5 w-3.5" /> Revogar
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}
