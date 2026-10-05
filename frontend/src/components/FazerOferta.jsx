// O2 — "Fazer oferta": o operador monta a oferta e o sistema diz se é boa para
// quem paga e para o banco (backend/model/oferta.py: analisar). O3 confirma.
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Calculator, CheckCircle2, AlertTriangle, XCircle, Loader2, User, Landmark, ShieldAlert, Info, Send, X, ThumbsUp, Clock, ThumbsDown, History } from 'lucide-react'
import DicaAjuda from './DicaAjuda'
import ErroCarga from './ErroCarga'
import { buscarOfertas, simularOferta, registrarOferta, listarOfertasFeitas } from '../api'
import { hojeISO, somarDias, avisarAgendaMudou } from '../utils/agenda'
import { resumoOferta, NOME_FAMILIA } from '../utils/ofertas'

const brl = (v) => v == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
const pct = (v) => v == null ? '—' : `${Math.round(v * 100)}%`

const VEREDITO = {
  boa:     { label: 'Boa',     icone: CheckCircle2,  cor: 'var(--success)', fundo: 'rgb(var(--c-success) / 0.10)', borda: 'rgb(var(--c-success) / 0.25)' },
  atencao: { label: 'Atenção', icone: AlertTriangle, cor: 'var(--warning)', fundo: 'rgb(var(--c-warning) / 0.10)', borda: 'rgb(var(--c-warning) / 0.25)' },
  ruim:    { label: 'Ruim',    icone: XCircle,       cor: 'var(--danger)',  fundo: 'rgb(var(--c-danger) / 0.10)',  borda: 'rgb(var(--c-danger) / 0.25)' },
}

function Selo({ v, grande = false }) {
  const c = VEREDITO[v] ?? VEREDITO.atencao; const I = c.icone
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${grande ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'}`}
      style={{ background: c.fundo, color: c.cor, border: `1px solid ${c.borda}` }}>
      <I className={grande ? 'h-4 w-4' : 'h-3.5 w-3.5'} /> {c.label}
    </span>
  )
}

function Campo({ rotulo, sufixo, value, onChange, min, max, step = 'any', inteiro, disabled }) {
  return (
    <label className="block text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
      {rotulo}
      <div className="mt-1 flex items-center gap-1.5">
        <input type="number" inputMode={inteiro ? 'numeric' : 'decimal'} min={min} max={max} step={inteiro ? 1 : step}
          value={value} disabled={disabled} onChange={e => onChange(e.target.value)}
          className="h-9 w-full rounded-lg px-2.5 text-right text-sm font-normal tabular-nums disabled:opacity-50"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }} />
        {sufixo && <span className="w-9 shrink-0 whitespace-nowrap text-[11px] font-normal" style={{ color: 'var(--ink-3)' }}>{sufixo}</span>}
      </div>
    </label>
  )
}

function Linha({ k, v, forte }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span style={{ color: 'var(--ink-2)' }}>{k}</span>
      <span className={`tabular-nums ${forte ? 'font-semibold' : ''}`} style={{ color: 'var(--ink)' }}>{v}</span>
    </div>
  )
}

const RESPOSTAS = [
  { k: 'aceitou',    label: 'Aceitou',    icone: ThumbsUp,   cor: 'var(--success)', nota: 'Vira promessa na Agenda' },
  { k: 'vai_pensar', label: 'Vai pensar', icone: Clock,      cor: 'var(--warning)', nota: 'Vira retorno na Agenda' },
  { k: 'recusou',    label: 'Recusou',    icone: ThumbsDown, cor: 'var(--danger)',  nota: 'Fica no histórico' },
]
const NOME_CANAL = { whatsapp: 'WhatsApp', telefone: 'Ligação', carta: 'Carta / e-mail' }
const NOME_RESPOSTA = { aceitou: 'Aceitou', vai_pensar: 'Vai pensar', recusou: 'Recusou' }

function resumoConta(c, n, desconto) {
  const base = n > 1 ? `${c.entrada > 0 ? `${brl(c.entrada)} + ` : ''}${n}x de ${brl(c.parcela)}` : `À vista ${brl(c.total_pago)}`
  return Number(desconto) > 0 ? `${base} · ${Number(desconto)}% de desconto` : base
}

// O3 — confirmar que a oferta foi feita: canal, resposta do devedor e data.
function Confirmar({ cpf, analise, condicoes, canalPadrao, despesas, onFechar, onFeito }) {
  const [canal, setCanal] = useState(canalPadrao || 'telefone')
  const [resposta, setResposta] = useState('aceitou')
  const [data, setData] = useState(somarDias(hojeISO(), 3))
  const [hora, setHora] = useState('')
  const [obs, setObs] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  const pedeData = resposta !== 'recusou'
  async function enviar() {
    setEnviando(true); setErro('')
    try {
      const r = await registrarOferta({
        cpf, ...condicoes, canal, resposta, observacao: obs || undefined,
        despesas_mensais: despesas === '' || despesas == null ? undefined : Number(despesas),
        ...(pedeData ? { data, hora: hora || undefined } : {}),
      })
      onFeito(r, resposta)
    } catch (e) { setErro(e) } finally { setEnviando(false) }
  }
  const sel = { background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--ink)' }
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onFechar}>
      <motion.div initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} onClick={e => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-labelledby="confirmar-oferta"
        className="flex max-h-[90vh] w-full max-w-md flex-col rounded-2xl shadow-2xl" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
        <div className="flex items-start justify-between border-b px-5 py-4" style={{ borderColor: 'var(--line)' }}>
          <div>
            <h2 id="confirmar-oferta" className="text-base font-bold" style={{ color: 'var(--ink)' }}>Confirmar oferta feita</h2>
            <p className="mt-0.5 text-xs" style={{ color: 'var(--ink-2)' }}>{resumoConta(analise.conta, condicoes.n_parcelas, condicoes.desconto_pct)}</p>
          </div>
          <button onClick={onFechar} aria-label="Fechar" className="rounded-lg p-1" style={{ color: 'var(--ink-2)' }}><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-4 overflow-y-auto px-5 py-4">
          {analise.geral === 'ruim' && (
            <p className="flex items-start gap-2 rounded-lg px-3 py-2 text-xs" style={{ background: 'rgb(var(--c-warning) / 0.10)', color: 'var(--warning)' }}>
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> A análise desta oferta deu “Ruim”. Registre se ela foi feita: o histórico serve justamente para aprender com isso.
            </p>
          )}
          <label className="block text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>Por onde
            <select value={canal} onChange={e => setCanal(e.target.value)} className="mt-1 h-10 w-full rounded-lg px-3 text-sm font-normal" style={sel}>
              {Object.entries(NOME_CANAL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
          <div>
            <p className="mb-1.5 text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>O que o devedor respondeu</p>
            <div className="grid grid-cols-3 gap-2">
              {RESPOSTAS.map(r => {
                const I = r.icone; const on = resposta === r.k
                return (
                  <button key={r.k} type="button" onClick={() => setResposta(r.k)} aria-pressed={on}
                    className="flex flex-col items-center gap-1 rounded-xl px-2 py-3 text-xs font-semibold transition-colors"
                    style={on ? { border: `1.5px solid ${r.cor}`, color: r.cor, background: 'var(--raise-1)' } : { border: '1px solid var(--line)', color: 'var(--ink-2)' }}>
                    <I className="h-5 w-5" /> {r.label}
                    <span className="text-[10px] font-normal" style={{ color: 'var(--ink-3)' }}>{r.nota}</span>
                  </button>
                )
              })}
            </div>
          </div>
          {pedeData && (
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>{resposta === 'aceitou' ? 'Data prometida' : 'Data do retorno'}
                <input type="date" min={hojeISO()} value={data} onChange={e => setData(e.target.value)} className="mt-1 h-10 w-full rounded-lg px-3 text-sm font-normal [color-scheme:dark]" style={sel} />
              </label>
              <label className="text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>Hora (opcional)
                <input type="time" value={hora} onChange={e => setHora(e.target.value)} className="mt-1 h-10 w-full rounded-lg px-3 text-sm font-normal [color-scheme:dark]" style={sel} />
              </label>
            </div>
          )}
          <label className="block text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>Observação (opcional)
            <textarea rows={2} maxLength={300} value={obs} onChange={e => setObs(e.target.value)} placeholder="Ex.: paga no dia do salário"
              className="mt-1 w-full resize-none rounded-lg px-3 py-2 text-sm font-normal" style={sel} />
          </label>
          <ErroCarga erro={erro} compacto />
        </div>
        <div className="flex justify-end gap-2 border-t px-5 py-4" style={{ borderColor: 'var(--line)' }}>
          <button onClick={onFechar} className="rounded-lg px-4 py-2 text-sm" style={{ color: 'var(--ink-2)' }}>Cancelar</button>
          <button onClick={enviar} disabled={enviando || (pedeData && !data)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-40">
            {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Registrar
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function Historico({ cpf, versao }) {
  const [dados, setDados] = useState(null)
  useEffect(() => { listarOfertasFeitas(cpf).then(setDados).catch(() => setDados(null)) }, [cpf, versao])
  if (!dados?.ativo || !dados.itens.length) return null
  const fmt = (iso) => new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  return (
    <div className="border-t pt-4" style={{ borderColor: 'var(--line)' }}>
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>
        <History className="h-3.5 w-3.5" /> Ofertas feitas a este devedor
      </p>
      <ul className="space-y-1.5">
        {dados.itens.slice(0, 8).map(o => {
          const r = RESPOSTAS.find(x => x.k === o.resposta)
          return (
            <li key={o.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded-lg px-3 py-2 text-xs" style={{ background: 'var(--surface-2)' }}>
              <span className="font-semibold" style={{ color: r?.cor }}>{NOME_RESPOSTA[o.resposta]}</span>
              <span style={{ color: 'var(--ink)' }}>{resumoConta(o, o.n_parcelas, o.desconto_pct)}</span>
              <span className="ml-auto" style={{ color: 'var(--ink-3)' }}>{NOME_CANAL[o.canal] || o.canal} · {o.operador_nome} · {fmt(o.created_at)}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function FazerOferta({ cpf, despesas, canalPadrao, confirmavel = true, onRegistrada, sugeridaId, pedido, onSimulado }) {
  const [confirmando, setConfirmando] = useState(null)      // {analise, condicoes}
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0)
  const [catalogo, setCatalogo] = useState([])
  const [base, setBase] = useState('')
  const [f, setF] = useState({ desconto_pct: 0, entrada_pct: 0, n_parcelas: 6, juros_mensal_pct: 0 })
  // A forma fica separada do número digitado: apagar o campo de parcelas para
  // digitar outro não pode virar "à vista" e travar o campo.
  const [modo, setModo] = useState('parcelado')
  const [res, setRes] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const seq = useRef(0)
  const [tentativa, setTentativa] = useState(0)
  const tocado = useRef(false)          // o operador já mexeu: a sugestão não sobrescreve
  const raiz = useRef(null)

  useEffect(() => {
    buscarOfertas().then(d => setCatalogo((d.catalogo || []).filter(o => o.ativa))).catch(() => setCatalogo([]))
  }, [])

  // Começa pela oferta sugerida em Propostas (a melhor que cabe no bolso);
  // sem sugestão, pela primeira do catálogo.
  useEffect(() => {
    if (tocado.current || !catalogo.length) return
    usarBase(catalogo.find(o => o.id === sugeridaId) || catalogo[0])
  }, [catalogo, sugeridaId])        // eslint-disable-line react-hooks/exhaustive-deps

  // "Ajustar e oferecer" numa proposta: carrega aqui e rola até o simulador.
  useEffect(() => {
    if (!pedido) return
    const o = catalogo.find(x => x.id === pedido.id)
    if (!o) return
    tocado.current = true
    usarBase(o)
    raiz.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [pedido])                      // eslint-disable-line react-hooks/exhaustive-deps

  function usarBase(o) {
    setBase(o.id)
    setModo(o.n_parcelas > 1 ? 'parcelado' : 'avista')
    setF({ desconto_pct: o.desconto_pct, entrada_pct: o.entrada_pct, n_parcelas: o.n_parcelas, juros_mensal_pct: o.juros_mensal_pct })
  }
  const mudar = (k, v) => { tocado.current = true; setF(x => ({ ...x, [k]: v })); setBase('') }
  const n = modo === 'avista' ? 1 : Math.max(2, parseInt(f.n_parcelas, 10) || 2)

  // A análise acompanha cada mudança, com uma pequena espera para não chamar
  // o servidor a cada tecla; a resposta antiga que chegar depois é descartada.
  useEffect(() => {
    const id = ++seq.current
    const t = setTimeout(() => {
      setCarregando(true); setErro('')
      simularOferta(cpf, { ...f, n_parcelas: n, despesas_mensais: despesas === '' || despesas == null ? undefined : Number(despesas), base_id: base || undefined })
        .then(r => {
          if (id !== seq.current) return
          // Resposta fora do formato (proxy, versão antiga do servidor): mostra
          // um erro em vez de derrubar a ficha inteira.
          if (!r?.conta || !r?.devedor || !r?.banco) {
            setRes(null); setErro(Object.assign(new Error('Erro HTTP 502'), { status: 502 })); return
          }
          setRes(r); onSimulado?.(r)
        })
        .catch(e => { if (id === seq.current) { setErro(e); setRes(null) } })
        .finally(() => { if (id === seq.current) setCarregando(false) })
    }, 350)
    return () => clearTimeout(t)
  }, [cpf, f.desconto_pct, f.entrada_pct, f.juros_mensal_pct, n, despesas, base, tentativa])    // eslint-disable-line react-hooks/exhaustive-deps

  const c = res?.conta
  const geral = res?.geral

  return (
    <div ref={raiz} className="scroll-mt-20 rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-5 py-4" style={{ borderColor: 'var(--line)' }}>
        <p className="section-label flex items-center gap-1.5"><Calculator className="h-3.5 w-3.5" /> Fazer oferta<DicaAjuda id="simulador-de-oferta" /></p>
        {res && <span className="flex items-center gap-2 text-xs" style={{ color: 'var(--ink-3)' }}>
          {carregando && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Análise geral <Selo v={geral} />
        </span>}
      </div>

      <div className="space-y-4 px-5 py-4">
        {catalogo.length > 0 && (
          <div>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>Começar de uma oferta da empresa</p>
            <div className="flex flex-wrap gap-1.5">
              {catalogo.map(o => (
                <button key={o.id} type="button" onClick={() => { tocado.current = true; usarBase(o) }} title={resumoOferta(o)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${base === o.id ? 'border-blue-500/40 bg-blue-500/15 text-blue-300' : 'hover:text-ink'}`}
                  style={base === o.id ? undefined : { borderColor: 'var(--line)', color: 'var(--ink-2)', background: 'var(--raise-1)' }}>
                  {o.nome}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-1.5 rounded-lg p-1" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }} role="tablist" aria-label="Forma">
          {[[1, 'À vista'], [6, 'Parcelado']].map(([v, l]) => {
            const on = v === 1 ? modo === 'avista' : modo === 'parcelado'
            return (
              <button key={l} type="button" role="tab" aria-selected={on}
                onClick={() => { setModo(v === 1 ? 'avista' : 'parcelado'); setBase(''); if (v !== 1 && (parseInt(f.n_parcelas, 10) || 1) < 2) setF(x => ({ ...x, n_parcelas: 6 })) }}
                className="flex-1 rounded-md py-1.5 text-sm font-medium"
                style={on ? { background: 'var(--surface)', color: 'var(--ink)', boxShadow: '0 1px 2px rgb(0 0 0 / .08)' } : { color: 'var(--ink-2)' }}>{l}</button>
            )
          })}
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Campo rotulo="Desconto" sufixo="%" min={0} max={95} value={f.desconto_pct} onChange={v => mudar('desconto_pct', v)} />
          <Campo rotulo="Parcelas" sufixo="x" inteiro min={2} max={120} value={modo === 'avista' ? 1 : f.n_parcelas} disabled={modo === 'avista'} onChange={v => mudar('n_parcelas', v)} />
          <Campo rotulo="Entrada" sufixo="%" min={0} max={90} value={f.entrada_pct} disabled={modo === 'avista'} onChange={v => mudar('entrada_pct', v)} />
          <Campo rotulo="Juros" sufixo="% a.m." min={0} max={20} step="0.01" value={f.juros_mensal_pct} disabled={modo === 'avista'} onChange={v => mudar('juros_mensal_pct', v)} />
        </div>

        <ErroCarga erro={erro} ocupado={carregando} onTentar={() => setTentativa(t => t + 1)} />

        <AnimatePresence>
          {res?.fora_da_alcada?.length > 0 && (
            <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="flex items-start gap-2 rounded-xl px-3.5 py-2.5 text-sm"
              style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.25)', color: 'var(--danger)' }}>
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span><strong>Fora da sua alçada.</strong> {res.fora_da_alcada.join(' ')} Ajuste a oferta ou fale com o administrador.</span>
            </motion.div>
          )}
        </AnimatePresence>

        {res && c && (
          <div className={`grid gap-4 transition-opacity md:grid-cols-2 ${carregando ? 'opacity-60' : ''}`}>
            <div className="rounded-xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }}>
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: 'var(--ink)' }}><User className="h-4 w-4" /> Para quem paga</p>
                <Selo v={res.devedor.veredito} />
              </div>
              {n > 1 ? (
                <>
                  {c.entrada > 0 && <Linha k="Entrada" v={brl(c.entrada)} />}
                  <Linha k={`${n} parcelas de`} v={brl(c.parcela)} forte />
                  <Linha k="Parcela máxima que cabe" v={res.devedor.parcela_maxima != null ? brl(res.devedor.parcela_maxima) : 'não verificável'} />
                  {res.devedor.comprometimento != null && <Linha k="Da sobra do mês" v={pct(res.devedor.comprometimento)} />}
                </>
              ) : <Linha k="Pagamento único" v={brl(c.total_pago)} forte />}
              <Linha k="Total pago" v={brl(c.total_pago)} />
              {c.economia > 0 && <Linha k="Economia" v={brl(c.economia)} />}
              <ul className="mt-2 space-y-1 border-t pt-2 text-xs" style={{ borderColor: 'var(--line)', color: 'var(--ink-2)' }}>
                {res.devedor.motivos.map((m, i) => <li key={i}>• {m}</li>)}
              </ul>
            </div>

            <div className="rounded-xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }}>
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: 'var(--ink)' }}><Landmark className="h-4 w-4" /> Para o banco</p>
                <Selo v={res.banco.veredito} />
              </div>
              <Linha k="Valor negociado" v={brl(c.valor_negociado)} />
              <Linha k="Chance de pagar" v={pct(res.banco.chance_pagar)} />
              <Linha k="Valor esperado" v={brl(res.banco.valor_esperado)} forte />
              {res.banco.razao_melhor != null && (
                <div className="py-1.5">
                  <div className="flex justify-between text-xs" style={{ color: 'var(--ink-2)' }}>
                    <span>vs. melhor oferta ({res.banco.melhor_oferta})</span><span className="tabular-nums">{pct(res.banco.razao_melhor)}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--raise-3)' }}>
                    <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, res.banco.razao_melhor * 100)}%`, background: VEREDITO[res.banco.veredito].cor }} />
                  </div>
                </div>
              )}
              {res.banco.valor_venda != null && <Linha k="Se vendesse a dívida" v={brl(res.banco.valor_venda)} />}
              <ul className="mt-2 space-y-1 border-t pt-2 text-xs" style={{ borderColor: 'var(--line)', color: 'var(--ink-2)' }}>
                {res.banco.motivos.map((m, i) => <li key={i}>• {m}</li>)}
              </ul>
            </div>
          </div>
        )}

        {res && (
          <p className="flex items-start gap-1.5 text-[11px]" style={{ color: 'var(--ink-3)' }}>
            <Info className="mt-0.5 h-3 w-3 shrink-0" />
            A chance de pagar vem das ofertas de {NOME_FAMILIA[res.familia]}
            {res.banco.origem_chance === 'bandit' ? ` (histórico de ${res.banco.observacoes_chance} ofertas registradas)` : ' (estimativa do modelo, ainda sem histórico)'};
            {' '}o sistema ainda não estima como cada ponto de desconto muda essa chance.
          </p>
        )}

        {aviso && <p className="flex items-center gap-1.5 text-sm" style={{ color: aviso.startsWith('Oferta registrada') ? 'var(--success)' : 'var(--warning)' }}><CheckCircle2 className="h-4 w-4" /> {aviso}</p>}

        {res && (
          <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-4" style={{ borderColor: 'var(--line)' }}>
            {!confirmavel && <span className="text-xs" style={{ color: 'var(--ink-3)' }}>Só quem trabalha a fila da empresa registra ofertas.</span>}
            <button type="button" onClick={() => { setAviso(''); setConfirmando({ analise: res, condicoes: { ...f, n_parcelas: n, base_id: base || undefined } }) }}
              disabled={!res.pode_confirmar || !confirmavel || carregando}
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-40">
              <Send className="h-4 w-4" /> Confirmar que fiz esta oferta
            </button>
          </div>
        )}

        <Historico cpf={cpf} versao={versao} />
      </div>

      <AnimatePresence>
        {confirmando && (
          <Confirmar cpf={cpf} analise={confirmando.analise} condicoes={confirmando.condicoes} canalPadrao={canalPadrao} despesas={despesas}
            onFechar={() => setConfirmando(null)}
            onFeito={(r, resposta) => {
              setConfirmando(null); setVersao(v => v + 1)
              if (r.agenda) avisarAgendaMudou()
              const partes = [`Oferta registrada: ${NOME_RESPOSTA[resposta].toLowerCase()}.`]
              if (r.agenda) partes.push(resposta === 'aceitou' ? 'A promessa está na Agenda.' : 'O retorno está na Agenda.')
              if (r.agenda_erro) partes.push(`Agenda: ${r.agenda_erro}`)
              if (r.oferta_erro) partes.push(r.oferta_erro)
              setAviso(partes.join(' '))
              onRegistrada?.(r)
            }} />
        )}
      </AnimatePresence>
    </div>
  )
}
