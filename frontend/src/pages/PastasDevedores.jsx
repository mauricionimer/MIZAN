import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, Loader2, ArrowRight } from 'lucide-react'
import AppShell from '../components/AppShell'
import GlassFolder from '../components/ui/glass-folder-cards'
import FluxoDevedorModal from '../components/FluxoDevedorModal'
import ErroCarga from '../components/ErroCarga'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { agentePastas, listarCarteiras, listarEmpresas } from '../api'
import { useAoMudarNoServidor } from '../components/useMudancasDoServidor'

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
// Apenas o painel de fundo recebe a cor lisa; a frente continua translúcida.
const COR_PASTA = { branco: '#f3f4f6', amarelo: '#c5a51b', vermelho: '#cf6461' }
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

  // Empresa, carteira, busca e filtro moram na URL: ao voltar do caso de um
  // devedor (ou recarregar), a pessoa encontra as pastas como deixou.
  const [params, setParams] = useSearchParams()
  const irPara = useCallback((mudancas) => {
    setParams(atual => {
      const novo = new URLSearchParams(atual)
      for (const [k, v] of Object.entries(mudancas)) v ? novo.set(k, v) : novo.delete(k)
      return novo
    }, { replace: true })
  }, [setParams])
  const empresa = isComando ? (params.get('empresa') || '') : ''
  const empresaId = isComando ? empresa : undefined
  const carteiraId = params.get('carteira') || ''
  const buscaAplicada = params.get('q') || ''
  const cor = FILTROS.some(f => f.id && f.id === params.get('cor')) ? params.get('cor') : ''

  const [empresas, setEmpresas] = useState([])
  const [carteiras, setCarteiras] = useState([])
  const [carregandoCarteiras, setCarregandoCarteiras] = useState(true)
  const [erroCarteiras, setErroCarteiras] = useState(null)
  const [tentCarteiras, setTentCarteiras] = useState(0)
  const [busca, setBusca] = useState(buscaAplicada)
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
    if (isComando && !empresa) { setCarteiras([]); irPara({ carteira: null }); setCarregandoCarteiras(false); return }
    let vivo = true
    setCarregandoCarteiras(true); setErroCarteiras(null)
    listarCarteiras({ empresaId, limite: 100 })
      .then(lista => {
        if (!vivo) return
        setCarteiras(lista || [])
        const aberta = result?.resumo?.carteira_id ?? result?.carteira_id
        const atual = new URLSearchParams(window.location.search).get('carteira')
        irPara({ carteira: (lista || []).some(c => c.id === atual) ? atual
          : (lista || []).some(c => c.id === aberta) ? aberta : (lista?.[0]?.id || null) })
      })
      .catch(e => { if (vivo) setErroCarteiras(e) })
      .finally(() => vivo && setCarregandoCarteiras(false))
    return () => { vivo = false }
  }, [empresaId, tentCarteiras]) // eslint-disable-line react-hooks/exhaustive-deps

  // A busca espera a pessoa parar de digitar.
  useEffect(() => {
    const t = setTimeout(() => { if (busca.trim() !== buscaAplicada) irPara({ q: busca.trim() }) }, 350)
    return () => clearTimeout(t)
  }, [busca]) // eslint-disable-line react-hooks/exhaustive-deps
  // O voltar do navegador troca a busca da URL: o campo acompanha.
  useEffect(() => { setBusca(b => b.trim() === buscaAplicada ? b : buscaAplicada) }, [buscaAplicada])

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

  // Ao vivo: um caso mudou (cor da pasta, situação). Relê as pastas já abertas na
  // tela, em silêncio, sem voltar ao topo; só troca se algo mudou.
  const itensRef = useRef(itens)
  itensRef.current = itens
  const carregandoRef = useRef(false)
  carregandoRef.current = carregando
  const recarregarQuieto = useCallback(async () => {
    if (!carteiraId || carregandoRef.current) return
    const meu = pedido.current
    try {
      const limite = Math.max(POR_PAGINA, itensRef.current.length)
      const d = await agentePastas({ carteiraId, busca: buscaAplicada, cor, limit: limite, offset: 0, empresaId })
      if (meu !== pedido.current) return
      setItens(atual => (JSON.stringify(atual) === JSON.stringify(d.itens) ? atual : d.itens))
      setContagem(c => (JSON.stringify(c) === JSON.stringify(d.contagem) ? c : d.contagem))
      setFiltrado(d.filtrado)
    } catch { /* fica como está; a próxima mudança tenta de novo */ }
  }, [carteiraId, buscaAplicada, cor, empresaId])
  useAoMudarNoServidor('casos', recarregarQuieto)

  const tone = claro ? 'light' : 'dark'
  const [fluxoAberto, setFluxoAberto] = useState(null)
  useEffect(() => { setFluxoAberto(null) }, [carteiraId, empresaId])
  const verCaso = useMemo(() => (d) => navigate(`/agente?aba=conversas&caso=${encodeURIComponent(d.id)}&nome=${encodeURIComponent(d.nome || '')}`), [navigate])

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="hub-titulo">Pastas de devedores</h1>
        <p className="hub-sub">Uma pasta por devedor. A cor é a leitura dos agentes: branca, amarela ou vermelha.</p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {isComando && (
            <select value={empresa} onChange={e => irPara({ empresa: e.target.value, carteira: null })} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
          <select value={carteiraId} onChange={e => irPara({ carteira: e.target.value })} aria-label="Carteira"
            disabled={!carteiras.length}
            className="min-w-[14rem] rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink focus:outline-none [color-scheme:dark]">
            {!carteiras.length && <option value="">{carregandoCarteiras ? 'Carregando carteiras…' : erroCarteiras ? 'Carteiras indisponíveis' : 'Nenhuma carteira'}</option>}
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
              <button key={f.id || 'todos'} type="button" onClick={() => irPara({ cor: f.id })} aria-pressed={on}
                className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                  on ? 'border-[var(--royal)] bg-raise-2 text-ink' : 'border-line text-ink-2 hover:text-ink'}`}>
                {f.id && <span className="h-2.5 w-2.5 rounded-full ring-1 ring-black/20" style={{ background: PONTO[f.id] }} aria-hidden="true" />}
                {f.rotulo}
                <span className="tabular-nums text-ink-3">{contagem[f.chave] ?? 0}</span>
              </button>
            )
          })}
        </div>

        <ErroCarga erro={erroCarteiras} onTentar={() => setTentCarteiras(t => t + 1)} ocupado={carregandoCarteiras} className="mt-6" />
        <ErroCarga erro={erro} onTentar={() => buscar(0)} className="mt-6" />

        <div className="mt-16 grid grid-cols-1 items-start justify-items-center gap-x-8 gap-y-14 md:grid-cols-2 xl:grid-cols-3">
          {itens.map((d, i) => (
            <div key={d.id} className="flex flex-col items-center gap-3">
              <GlassFolder
                key={`${d.id}-${d.semaforo.cor}-${d.arquivos.length}`}
                label={d.nome || 'Sem nome'} meta={`#${d.rank ?? '–'}${d.dias_em_atraso != null ? ` · ${d.dias_em_atraso} dias` : ''}`}
                tone={tone} art="none" solidColor={COR_PASTA[d.semaforo.cor]}
                files={[{ name: 'Fluxo do devedor', meta: 'Fases e situação atual' }, ...d.arquivos]} action="none" width={300} appearDelay={(i % POR_PAGINA % 6) * 90}
                onFileSelect={(_, index) => index === 0 ? setFluxoAberto(d) : verCaso(d)}
              />
              <p className="flex max-w-[300px] items-center gap-2 text-sm text-ink-2" title={`Cor decidida por: ${d.semaforo.origem === 'agente' ? 'avaliação do agente' : 'regras do sistema'}`}>
                <span className="h-3 w-3 shrink-0 rounded-full ring-1 ring-black/25" style={{ background: PONTO[d.semaforo.cor] }} aria-hidden="true" />
                <span><strong className="font-semibold text-ink">{d.semaforo.rotulo}</strong> · {d.semaforo.motivo}</span>
              </p>
              {/* Atalho de um clique: a pasta também abre e mostra os papéis. */}
              <button type="button" onClick={() => setFluxoAberto(d)} aria-label={`Ver fluxo de ${d.nome || 'devedor'}`}
                className="-mt-1 inline-flex min-h-[40px] items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-accent-text transition-colors hover:bg-raise-2">
                Ver fluxo <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>

        {!carregando && !erro && !erroCarteiras && carteiraId && itens.length === 0 && (
          <p className="mt-16 text-center text-ink-2">Nenhum devedor encontrado{buscaAplicada ? ` para “${buscaAplicada}”` : ''}.</p>
        )}
        {!carregando && !carteiraId && !carregandoCarteiras && !erroCarteiras && (
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
      <FluxoDevedorModal devedor={fluxoAberto} onFechar={() => setFluxoAberto(null)} onVerCaso={verCaso} />
    </AppShell>
  )
}
