import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2 } from 'lucide-react'
import AppShell from '../components/AppShell'
import GlassFolder from '../components/ui/glass-folder-cards'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { agentePastas, listarCarteiras, listarEmpresas } from '../api'

/**
 * Pastas de devedores. Uma pasta por devedor da carteira, com a cor que os
 * agentes deram a ele (semáforo):
 *   branca   — sem pendência (ainda não foi acionado, ou está tranquilo)
 *   amarela  — em andamento
 *   vermelha — precisa de atenção agora
 * A cor vem do servidor (agente/semaforo.py): regras em código a partir do caso
 * mais a leitura da Triagem. Dentro da pasta ficam os papéis que os agentes
 * juntaram; clicar num deles abre o caso na tela de conversa dos agentes.
 */
// A mesma linguagem das artes do componente de pasta: tinta se dobrando na água
// escura (vermelho = a "ember" do próprio componente), em tom âmbar para o
// amarelo, e mármore branco com veios cinza para o branco.
const ARTE = {
  branco: { style: 'marble', colors: ['#f6f7f9', '#dfe3e8', '#b4bcc7', '#eef0f3', '#cdd3db', '#ffffff', '#99a3b1'],
            scale: 0.62, warp: 3.0, angle: -0.5, gloss: 0.5, veins: 0.55 },
  amarelo: { style: 'marble', colors: ['#080908', '#1b2420', '#4d5a4c', '#17130c', '#b8760c', '#f2a81d', '#ffd98a'],
             scale: 0.62, warp: 3.2, angle: -0.5, gloss: 0.55, veins: 0.6 },
  vermelho: 'ember',
}
const PONTO = { branco: '#cfd5e6', amarelo: '#e8b23c', vermelho: '#d92d20' }
const FILTROS = [
  { id: '', rotulo: 'Todos', chave: 'total' },
  { id: 'vermelho', rotulo: 'Urgentes', chave: 'vermelho' },
  { id: 'amarelo', rotulo: 'Em andamento', chave: 'amarelo' },
  { id: 'branco', rotulo: 'Sem pendência', chave: 'branco' },
]
const POR_PAGINA = 24

function dataCurta(iso) {
  try { return new Date(iso).toLocaleDateString('pt-BR') } catch { return '' }
}

export default function PastasDevedores() {
  const { claro } = useTheme()
  const { token, isComando } = useAuth()
  const { result } = useAnalysis()
  const navigate = useNavigate()

  const [empresas, setEmpresas] = useState([])
  const [empresa, setEmpresa] = useState('')
  const empresaId = isComando ? empresa : undefined
  const [carteiras, setCarteiras] = useState([])
  const [carteiraId, setCarteiraId] = useState('')
  const [carregandoCarteiras, setCarregandoCarteiras] = useState(true)
  const [busca, setBusca] = useState('')
  const [buscaAplicada, setBuscaAplicada] = useState('')
  const [cor, setCor] = useState('')
  const [itens, setItens] = useState([])
  const [contagem, setContagem] = useState({ total: 0, vermelho: 0, amarelo: 0, branco: 0 })
  const [filtrado, setFiltrado] = useState(0)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)
  const pedido = useRef(0)

  useEffect(() => {
    if (isComando) listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  // Carteiras da empresa (pelo nome do arquivo). Começa na que está aberta na
  // análise; senão, na mais recente.
  useEffect(() => {
    if (isComando && !empresa) { setCarteiras([]); setCarteiraId(''); setCarregandoCarteiras(false); return }
    let vivo = true
    setCarregandoCarteiras(true)
    listarCarteiras({ empresaId, limite: 100 })
      .then(lista => {
        if (!vivo) return
        setCarteiras(lista || [])
        const aberta = result?.resumo?.carteira_id ?? result?.carteira_id
        setCarteiraId(atual => (lista || []).some(c => c.id === atual) ? atual
          : (lista || []).some(c => c.id === aberta) ? aberta : (lista?.[0]?.id || ''))
      })
      .catch(setErro)
      .finally(() => vivo && setCarregandoCarteiras(false))
    return () => { vivo = false }
  }, [empresaId]) // eslint-disable-line react-hooks/exhaustive-deps

  // A busca espera a pessoa parar de digitar.
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 350)
    return () => clearTimeout(t)
  }, [busca])

  const buscar = useCallback(async (offset) => {
    if (!carteiraId) return
    const meu = ++pedido.current
    setCarregando(true); setErro(null)
    try {
      const d = await agentePastas({ carteiraId, busca: buscaAplicada, cor, limit: POR_PAGINA, offset, empresaId })
      if (meu !== pedido.current) return            // chegou uma resposta mais nova
      setItens(atual => offset === 0 ? d.itens : [...atual, ...d.itens])
      setContagem(d.contagem); setFiltrado(d.filtrado)
    } catch (e) {
      if (meu === pedido.current) setErro(e)
    } finally {
      if (meu === pedido.current) setCarregando(false)
    }
  }, [carteiraId, buscaAplicada, cor, empresaId])

  useEffect(() => { setItens([]); buscar(0) }, [buscar])

  const tone = claro ? 'light' : 'dark'
  const verCaso = useMemo(() => (d) => navigate(`/agente?aba=conversas&caso=${encodeURIComponent(d.id)}&nome=${encodeURIComponent(d.nome || '')}`), [navigate])

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="hub-titulo">Pastas de devedores</h1>
        <p className="hub-sub">Uma pasta por devedor. A cor é a leitura dos agentes: branca, amarela ou vermelha.</p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {isComando && (
            <select value={empresa} onChange={e => setEmpresa(e.target.value)} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
          <select value={carteiraId} onChange={e => setCarteiraId(e.target.value)} aria-label="Carteira"
            disabled={!carteiras.length}
            className="min-w-[14rem] rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink focus:outline-none [color-scheme:dark]">
            {!carteiras.length && <option value="">{carregandoCarteiras ? 'Carregando carteiras…' : 'Nenhuma carteira'}</option>}
            {carteiras.map(c => (
              <option key={c.id} value={c.id}>{c.nome_arquivo || 'Carteira'}{c.created_at ? ` · ${dataCurta(c.created_at)}` : ''}</option>
            ))}
          </select>
          <label className="relative min-w-[16rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input type="search" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar por nome ou CPF"
              aria-label="Buscar devedor por nome ou CPF"
              className="w-full rounded-lg border border-line bg-surface-2 py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:outline-none" />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filtrar pela cor">
          {FILTROS.map(f => {
            const on = cor === f.id
            return (
              <button key={f.id || 'todos'} type="button" onClick={() => setCor(f.id)} aria-pressed={on}
                className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                  on ? 'border-[var(--royal)] bg-raise-2 text-ink' : 'border-line text-ink-2 hover:text-ink'}`}>
                {f.id && <span className="h-2.5 w-2.5 rounded-full ring-1 ring-black/20" style={{ background: PONTO[f.id] }} aria-hidden="true" />}
                {f.rotulo}
                <span className="tabular-nums text-ink-3">{contagem[f.chave] ?? 0}</span>
              </button>
            )
          })}
        </div>

        {erro && (
          <div role="alert" className="mt-6 rounded-xl border border-line bg-surface p-4 text-sm" style={{ color: 'var(--danger)' }}>
            Não foi possível carregar as pastas. {erro.message || ''}
            <button type="button" onClick={() => buscar(0)} className="ml-3 underline">Tentar de novo</button>
          </div>
        )}

        <div className="mt-16 grid grid-cols-1 items-start justify-items-center gap-x-8 gap-y-14 md:grid-cols-2 xl:grid-cols-3">
          {itens.map((d, i) => (
            <div key={d.id} className="flex flex-col items-center gap-3">
              <GlassFolder
                key={`${d.id}-${d.semaforo.cor}-${d.arquivos.length}`}
                label={d.nome || 'Sem nome'} meta={`#${d.rank ?? '–'}${d.dias_em_atraso != null ? ` · ${d.dias_em_atraso} dias` : ''}`}
                tone={tone} art={ARTE[d.semaforo.cor]} seed={(d.rank || i) % 97}
                files={d.arquivos} action="none" width={300} appearDelay={(i % POR_PAGINA % 6) * 90}
                onFileSelect={() => verCaso(d)}
              />
              <p className="flex max-w-[300px] items-center gap-2 text-sm text-ink-2" title={`Cor decidida por: ${d.semaforo.origem === 'agente' ? 'avaliação do agente' : 'regras do sistema'}`}>
                <span className="h-3 w-3 shrink-0 rounded-full ring-1 ring-black/25" style={{ background: PONTO[d.semaforo.cor] }} aria-hidden="true" />
                <span><strong className="font-semibold text-ink">{d.semaforo.rotulo}</strong> · {d.semaforo.motivo}</span>
              </p>
            </div>
          ))}
        </div>

        {!carregando && !erro && carteiraId && itens.length === 0 && (
          <p className="mt-16 text-center text-ink-2">Nenhum devedor encontrado{buscaAplicada ? ` para “${buscaAplicada}”` : ''}.</p>
        )}
        {!carregando && !carteiraId && !carregandoCarteiras && (
          <p className="mt-16 text-center text-ink-2">{isComando && !empresa ? 'Escolha a empresa.' : 'Ainda não há carteira. Suba uma em Carteira.'}</p>
        )}
        {carregando && <div className="mt-10 flex justify-center" role="status"><Loader2 className="h-5 w-5 animate-spin text-ink-3" /><span className="sr-only">Carregando…</span></div>}
        {!carregando && itens.length > 0 && itens.length < filtrado && (
          <div className="mt-12 flex justify-center">
            <button type="button" onClick={() => buscar(itens.length)} className="btn-secondary px-5 py-2.5">
              Carregar mais ({filtrado - itens.length})
            </button>
          </div>
        )}
      </div>
    </AppShell>
  )
}
