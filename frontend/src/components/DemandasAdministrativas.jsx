import { useCallback, useEffect, useRef, useState } from 'react'
import { Plus, Check, RotateCcw, Loader2 } from 'lucide-react'
import { criarTarefaAdministrativa, listarTarefasAdministrativas, mudarTarefaAdministrativa } from '../api'
import ErroCarga from './ErroCarga'
import { hojeISO, quando, avisarAgendaMudou } from '../utils/agenda'

export default function DemandasAdministrativas({ empresaId, soLeitura, onTotal }) {
  const [itens, setItens] = useState([])
  const [total, setTotal] = useState(0)
  const [situacao, setSituacao] = useState('pendente')
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [ocupado, setOcupado] = useState('')
  const [aberto, setAberto] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [descricao, setDescricao] = useState('')
  const [data, setData] = useState(hojeISO())
  const pedido = useRef(0)
  const carregar = useCallback(async (offset = 0) => {
    const atual = ++pedido.current
    setErro(null); setCarregando(true)
    try {
      const r = await listarTarefasAdministrativas({ empresa_id: empresaId, situacao, offset })
      if (atual !== pedido.current) return
      setItens(atual => offset ? [...atual, ...r.itens] : r.itens); setTotal(r.total)
      if (situacao === 'pendente') onTotal(r.total)
      else {
        const pendentes = await listarTarefasAdministrativas({ empresa_id: empresaId, limite: 1 })
        if (atual === pedido.current) onTotal(pendentes.total)
      }
    } catch (e) { if (atual === pedido.current) setErro(e) } finally { if (atual === pedido.current) setCarregando(false) }
  }, [empresaId, situacao, onTotal])
  useEffect(() => { setItens([]); carregar(); return () => { pedido.current++ } }, [carregar])

  async function criar(e) {
    e.preventDefault(); setOcupado('nova'); setErro(null)
    try {
      await criarTarefaAdministrativa({ titulo: titulo.trim(), descricao, data })
      setTitulo(''); setDescricao(''); setData(hojeISO()); setAberto(false)
      if (situacao !== 'pendente') setSituacao('pendente')
      else await carregar()
      avisarAgendaMudou()
    } catch (err) { setErro(err) } finally { setOcupado('') }
  }
  async function mudar(item) {
    setOcupado(item.id); setErro(null)
    try { await mudarTarefaAdministrativa(item.id, situacao === 'pendente'); await carregar(); avisarAgendaMudou() }
    catch (e) { setErro(e) } finally { setOcupado('') }
  }
  return <section className="space-y-4 rounded-[22px] border border-line bg-surface p-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-base font-semibold text-ink">Demandas administrativas</h2><p className="mt-1 text-xs text-ink-2">Tarefas internas compartilhadas entre os administradores da empresa.</p></div>
      {!soLeitura && <button type="button" className="btn-secondary btn-sm" onClick={() => setAberto(v => !v)} aria-expanded={aberto}><Plus className="h-4 w-4" /> Nova demanda</button>}
    </div>
    {aberto && !soLeitura && <form onSubmit={criar} className="space-y-3 rounded-xl border border-line bg-surface-2 p-4">
      <label className="block text-sm text-ink">Título<input className="input-base mt-1" value={titulo} onChange={e => setTitulo(e.target.value)} required minLength={3} maxLength={120} /></label>
      <label className="block text-sm text-ink">Descrição<textarea className="input-base mt-1" value={descricao} onChange={e => setDescricao(e.target.value)} rows={3} maxLength={2000} /></label>
      <label className="block text-sm text-ink">Prazo<input type="date" className="input-base mt-1" value={data} min={hojeISO()} onChange={e => setData(e.target.value)} required /></label>
      <div className="flex gap-2"><button type="submit" disabled={!!ocupado || titulo.trim().length < 3} className="btn-primary btn-sm">{ocupado === 'nova' ? 'Salvando…' : 'Criar demanda'}</button><button type="button" className="btn-ghost btn-sm" onClick={() => setAberto(false)}>Cancelar</button></div>
    </form>}
    <div className="flex gap-2" role="group" aria-label="Situação das demandas administrativas">
      {[['pendente', 'Pendentes'], ['cumprida', 'Concluídas']].map(([s, label]) => <button key={s} type="button" aria-pressed={situacao === s} disabled={!!ocupado} onClick={() => setSituacao(s)} className={situacao === s ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}>{label}</button>)}
    </div>
    <ErroCarga erro={erro} onTentar={() => carregar()} />
    {carregando && <p role="status" className="flex items-center gap-2 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando demandas…</p>}
    {!carregando && !erro && !itens.length && <p className="py-4 text-sm text-ink-2">{situacao === 'pendente' ? 'Nenhuma demanda administrativa pendente.' : 'Nenhuma demanda administrativa concluída.'}</p>}
    <ul className="space-y-2">{itens.map(item => <li key={item.id} className="flex flex-wrap items-start gap-3 rounded-xl border border-line p-4">
      <div className="min-w-0 flex-1 basis-48"><p className="break-words text-sm font-semibold text-ink">{item.nome}</p><p className="mt-1 text-xs text-ink-2">Prazo: {quando(item.data)}</p>{item.observacao && <p className="mt-2 whitespace-pre-wrap break-words text-sm text-ink-2">{item.observacao}</p>}</div>
      {!soLeitura && <button type="button" disabled={!!ocupado} onClick={() => mudar(item)} className="btn-secondary btn-sm">{situacao === 'pendente' ? <><Check className="h-4 w-4" /> Concluir</> : <><RotateCcw className="h-4 w-4" /> Reabrir</>}</button>}
    </li>)}</ul>
    {!carregando && itens.length < total && <button type="button" className="btn-secondary btn-sm" onClick={() => carregar(itens.length)}>Carregar mais ({total - itens.length})</button>}
  </section>
}
