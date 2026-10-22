import { useCallback, useEffect, useRef, useState } from 'react'
import { CircleDot, Loader2, RotateCcw, AlertTriangle, CheckCircle2, Pencil, UserRound } from 'lucide-react'
import { agenteFluxoDevedor, buscarPaginaRanking, definirFaseDevedor } from '../api'
import { useAuth } from '../context/AuthContext'
import BuildPipeline from './ui/build-pipeline'
import ErroCarga from './ErroCarga'

export default function FluxoDevedor({ predicaoId, carteiraId, rank, cpf, versao = 0 }) {
  const [resposta, setResposta] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [faseEscolhida, setFaseEscolhida] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroFase, setErroFase] = useState(null)
  const gravando = useRef(false)
  const { isComando } = useAuth()
  const pedido = useRef(0)
  const resolvido = useRef(null)
  const chave = `${predicaoId || ''}:${carteiraId || ''}:${rank || ''}:${cpf || ''}`
  const temDevedor = !!predicaoId || !!(carteiraId && rank && cpf)
  const carregar = useCallback(async () => {
    if (!temDevedor || gravando.current) return
    const atual = ++pedido.current
    setCarregando(true); setErro(null)
    try {
      let id = predicaoId || (resolvido.current?.chave === chave ? resolvido.current.id : null)
      if (!id) {
        // A análise recém-criada pode manter o ranking em memória sem o id do banco.
        const pagina = await buscarPaginaRanking(carteiraId, { offset: Number(rank) - 1, limit: 1 })
        const linha = pagina.itens?.[0]
        const numeros = v => String(v ?? '').replace(/\D/g, '')
        if (!linha?.id || Number(linha.rank) !== Number(rank) || numeros(linha.cpf) !== numeros(cpf)) throw new Error('Não foi possível identificar este devedor na carteira. Reabra o painel e tente novamente.')
        id = linha.id
        if (atual === pedido.current) resolvido.current = { chave, id }
      }
      if (atual !== pedido.current) return
      const dados = await agenteFluxoDevedor(id)
      if (atual === pedido.current) setResposta({ chave, dados })
    } catch (e) { if (atual === pedido.current) setErro(e) }
    finally { if (atual === pedido.current) setCarregando(false) }
  }, [predicaoId, carteiraId, rank, cpf, chave, temDevedor])
  useEffect(() => { setEditando(false); setErroFase(null) }, [chave])
  useEffect(() => {
    let vivo = true, timer
    const consultar = async () => {
      if (document.visibilityState !== 'hidden') await carregar()
      if (vivo) timer = setTimeout(consultar, 30000)
    }
    consultar()
    const mudou = () => { if (document.visibilityState !== 'hidden') carregar() }
    window.addEventListener('focus', mudou)
    window.addEventListener('mizan:agenda', mudou)
    return () => {
      vivo = false; clearTimeout(timer); pedido.current++
      window.removeEventListener('focus', mudou); window.removeEventListener('mizan:agenda', mudou)
    }
  }, [carregar, versao])
  const dados = resposta?.chave === chave ? resposta.dados : null
  async function salvarFase(e) {
    e.preventDefault()
    const id = predicaoId || (resolvido.current?.chave === chave ? resolvido.current.id : null)
    if (!id || gravando.current) return
    gravando.current = true
    const atual = ++pedido.current
    setSalvando(true); setErroFase(null); setCarregando(false)
    try {
      const dados = await definirFaseDevedor(id, faseEscolhida || null)
      if (atual === pedido.current) { setResposta({ chave, dados }); setEditando(false) }
    } catch (e) { if (atual === pedido.current) setErroFase(e) }
    finally { gravando.current = false; setSalvando(false) }
  }
  return <section className="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-6" aria-label="Fluxo do devedor" aria-busy={carregando}>
    <header className="mb-2 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-ink"><CircleDot size={18} className="text-blue-400" aria-hidden="true" />Situação do devedor</h2>
        <p className="mt-1 text-xs text-ink-2">Atualizado pelos registros dos agentes e pelo Acompanhamento.</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {dados && !isComando && <button type="button" disabled={salvando} onClick={() => { setEditando(v => !v); setFaseEscolhida(dados.manual?.fase ?? dados.fase_atual ?? '') }} className="btn-secondary btn-sm"><Pencil size={14} aria-hidden="true" />Definir fase</button>}
        <button type="button" onClick={carregar} disabled={carregando || salvando || !temDevedor} className="btn-ghost btn-sm" aria-label="Atualizar situação do devedor">
          <RotateCcw size={15} className={carregando ? 'animate-spin' : ''} aria-hidden="true" />Atualizar
        </button>
      </div>
    </header>
    <ErroCarga erro={erro} onTentar={carregar} compacto />
    {!temDevedor && <p className="py-5 text-sm text-ink-2">Este devedor ainda não tem identificação na carteira salva.</p>}
    {carregando && !dados && <p className="flex items-center gap-2 py-6 text-sm text-ink-2" role="status"><Loader2 size={16} className="animate-spin" />Consultando a situação…</p>}
    {dados && <>
      <div className="mt-3 flex flex-wrap gap-2">{(dados.avisos ?? (dados.aviso ? [dados.aviso] : [])).map(aviso => {
        const Icon = aviso.tipo === 'sucesso' ? CheckCircle2 : AlertTriangle
        const cor = aviso.tipo === 'sucesso' ? 'var(--success)' : aviso.tipo === 'atencao' ? 'var(--warning)' : 'var(--accent-text)'
        return <p key={aviso.texto} className="inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-semibold" style={{ color: cor, background: `color-mix(in srgb, ${cor} 10%, transparent)` }} role="status"><Icon size={14} className="shrink-0" aria-hidden="true" />{aviso.texto}</p>
      })}</div>
      {dados.manual && <p className="mt-3 flex items-center gap-2 text-xs text-ink-2"><UserRound size={14} className="shrink-0" aria-hidden="true" />Decisão de {dados.manual.nome}. O acompanhamento automático não substitui esta escolha.</p>}
      {dados.conflito && <p className="mt-2 text-xs text-ink-2">Agentes: {dados.fases.find(f => f.id === dados.fontes?.agentes)?.nome ?? 'Sem fase identificada'} · Operação: {dados.fases.find(f => f.id === dados.fontes?.operacao)?.nome ?? 'Sem fase identificada'}</p>}
      {editando && <form onSubmit={salvarFase} className="mt-4 rounded-xl border border-line bg-surface-2 p-4">
        <label className="block text-sm font-medium text-ink" htmlFor={`fase-${predicaoId || rank}`}>Fase atual do devedor</label>
        <div className="mt-2 flex flex-wrap gap-2">
          <select id={`fase-${predicaoId || rank}`} value={faseEscolhida} disabled={salvando} onChange={e => setFaseEscolhida(e.target.value)} className="min-h-[44px] min-w-0 max-w-full flex-1 rounded-lg border border-line bg-surface px-3 text-sm text-ink">
            <option value="">Automático — acompanhar os registros</option>
            {dados.fases.map(f => <option key={f.id} value={f.id} disabled={f.id === 'pagamento' && !dados.pode_marcar_pagamento}>{f.nome}</option>)}
          </select>
          <button type="submit" disabled={salvando} className="btn-primary btn-sm">{salvando ? 'Salvando…' : 'Aplicar decisão'}</button>
          <button type="button" disabled={salvando} className="btn-ghost btn-sm" onClick={() => setEditando(false)}>Cancelar</button>
        </div>
        {!dados.pode_marcar_pagamento && <p className="mt-2 text-xs text-ink-2">“Pagamento em andamento” será liberado após o primeiro pagamento confirmado.</p>}
        <ErroCarga erro={erroFase} compacto className="mt-3" />
      </form>}
      <BuildPipeline key={chave} stages={dados.fases} currentStageId={dados.fase_atual} description={dados.descricao} />
      {dados.atualizado_em && <p className="mt-3 text-xs text-ink-3">Último registro: {new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo' }).format(new Date(dados.atualizado_em))}</p>}
      {erro && <p className="mt-2 text-xs text-ink-2">Exibindo a última consulta. Não foi possível atualizar agora.</p>}
    </>}
  </section>
}
