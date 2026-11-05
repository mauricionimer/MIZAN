// A1 — Resultados: "o que está funcionando". Cruza os pagamentos registrados
// por canal, fase de atraso, modalidade, desconto e forma (backend/resultados.py).
// Desenho do canvas: três números numa linha, depois cada corte com uma frase que
// já responde ("WhatsApp é o melhor canal…") e barras finas; contatos por canal
// em "1 em N vira promessa".
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { TrendingUp, Loader2, Info } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import ErroCarga from '../components/ErroCarga'
import { useAuth } from '../context/AuthContext'
import { buscarResultados, listarEmpresas } from '../api'

const fmtBRL = (v) => v == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)
const fmtPct = (v) => v == null ? '—' : `${(v * 100).toFixed(v > 0 && v < 0.1 ? 1 : 0).replace('.', ',')}%`

const NOMES = {
  whatsapp: 'WhatsApp', telefone: 'Ligação', sms: 'SMS', email: 'E-mail', carta: 'Carta',
  presencial: 'Presencial (agência)', escritorio: 'Escritório de cobrança', portal: 'App / site do banco',
  espontaneo: 'Devedor procurou sozinho', outro: 'Outro', nao_informado: 'Não informado',
  a_vista: 'À vista', parcelado: 'Parcelado',
  sem_desconto: 'Sem desconto', ate_10: 'Até 10%', '10_20': '10% a 20%', '20_30': '20% a 30%', acima_30: 'Acima de 30%',
  pix: 'Pix', boleto: 'Boleto', cartao_credito: 'Cartão de crédito', cartao_debito: 'Cartão de débito',
  transferencia: 'Transferência', debito_automatico: 'Débito automático', dinheiro: 'Dinheiro',
  '0-30 dias': 'Até 30 dias', '31-60 dias': '31 a 60 dias', '61-90 dias': '61 a 90 dias',
  '91-180 dias': '91 a 180 dias', '181+ dias': 'Mais de 180',
}
const nome = (k) => NOMES[k] || k

const PERIODOS = [['30d', '30 dias', 'nos últimos 30 dias'], ['90d', '90 dias', 'nos últimos 90 dias'],
  ['365d', '12 meses', 'nos últimos 12 meses'], ['tudo', 'Tudo', 'até agora']]

const informados = (gs) => (gs || []).filter(g => g.chave !== 'nao_informado')

// Uma frase por corte, que responde à pergunta antes do gráfico.
// Cortes com taxa: quem pagou ÷ quem foi cobrado. Sem taxa: parte do total de pagamentos.
const CORTES = [
  { k: 'canal', campo: 'por_canal', taxa: true, melhor: 'melhor_canal',
    sub: 'Taxa de pagamento = quem pagou ÷ quem foi cobrado por esse canal.',
    frase: (gs, m) => m ? `${nome(m.chave)} é o melhor canal com volume: ${fmtPct(m.taxa_pagamento)} pagam.`
      : 'Ainda não há volume para dizer qual canal funciona melhor.' },
  { k: 'fase', campo: 'por_fase', taxa: true, melhor: 'melhor_fase',
    sub: 'Em que faixa de atraso o devedor estava quando foi cobrado.',
    frase: (gs) => {
      const v = informados(gs)
      if (v.length < 2) return 'Em que fase de atraso a cobrança funciona.'
      const a = v[0], z = v[v.length - 1]
      return (a.taxa_pagamento ?? 0) >= (z.taxa_pagamento ?? 0)
        ? `Quanto antes, melhor: ${nome(a.chave).toLowerCase()}, ${fmtPct(a.taxa_pagamento)} pagam; ${nome(z.chave).toLowerCase()}, ${fmtPct(z.taxa_pagamento)}.`
        : `Nesta carteira, quem está há mais tempo paga mais: ${nome(z.chave).toLowerCase()}, ${fmtPct(z.taxa_pagamento)}.`
    } },
  { k: 'modalidade', campo: 'por_modalidade', taxa: false,
    sub: 'Como os pagamentos foram fechados (parte do total de pagamentos).',
    frase: (gs) => {
      const tot = gs.reduce((s, g) => s + g.pagos, 0)
      const av = gs.find(g => g.chave === 'a_vista')
      return tot && av ? `${Math.round((av.pagos / tot) * 10)} em cada 10 pagamentos foram à vista.` : 'Como os pagamentos foram fechados.'
    } },
  { k: 'desconto', campo: 'por_desconto', taxa: false,
    sub: 'Quanto de desconto foi dado nos pagamentos (parte do total).',
    frase: (gs) => {
      const tot = gs.reduce((s, g) => s + g.pagos, 0)
      const top = [...informados(gs)].sort((a, b) => b.pagos - a.pagos)[0]
      return tot && top ? `${nome(top.chave)} é a faixa que mais fecha: ${fmtPct(top.pagos / tot)} dos pagamentos.` : 'Quanto de desconto foi dado.'
    } },
  { k: 'forma', campo: 'por_forma', taxa: false,
    sub: 'Por onde o dinheiro entrou (parte do total).',
    frase: (gs) => {
      const tot = gs.reduce((s, g) => s + g.pagos, 0)
      const top = [...informados(gs)].sort((a, b) => b.pagos - a.pagos)[0]
      return tot && top ? `${nome(top.chave)} é ${fmtPct(top.pagos / tot)} dos pagamentos.` : 'Como o dinheiro entrou.'
    } },
]

const listrado = (cor) => `repeating-linear-gradient(45deg, ${cor} 0 3px, transparent 3px 6px)`

// Barra fina por grupo: o destaque vai em royal, o resto em cinza; amostra pequena é listrada.
// O número fica escrito ao lado (nunca só a cor).
function Corte({ c, grupos, melhor }) {
  const tot = grupos.reduce((s, g) => s + g.pagos, 0) || 1
  const valor = (g) => c.taxa ? (g.taxa_pagamento ?? 0) : g.pagos / tot
  const destaque = c.taxa ? melhor?.chave : [...informados(grupos)].sort((a, b) => b.pagos - a.pagos)[0]?.chave
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="text-[17px] font-semibold leading-snug text-ink">{c.frase(grupos, melhor)}</h3>
        <p className="mt-0.5 text-[13px] text-ink-2">{c.sub}</p>
      </div>
      <ul className="flex flex-col gap-2.5">
        {grupos.map((g, i) => {
          const v = valor(g)
          const forte = g.chave === destaque
          const cor = forte ? 'var(--chart-1)' : 'var(--border-strong)'
          const dica = c.taxa
            ? `${nome(g.chave)}: ${fmtPct(g.taxa_pagamento)} pagaram (${fmtNum(g.pagos)} de ${fmtNum(g.registros)})`
            : `${nome(g.chave)}: ${fmtNum(g.pagos)} pagamentos, ${fmtBRL(g.recuperado)}`
          return (
            <li key={g.chave} title={dica} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[200px_minmax(0,1fr)_56px]">
              <span className="min-w-0">
                <span className={`block truncate text-sm ${forte ? 'font-semibold text-ink' : g.chave === 'nao_informado' ? 'italic text-ink-3' : 'text-ink-2'}`}>{nome(g.chave)}</span>
                {c.taxa && <span className="block text-[11px] text-ink-3">{fmtNum(g.registros)}{g.amostra_pequena ? ' · amostra pequena' : ''}</span>}
              </span>
              <span className="order-last col-span-2 h-2 overflow-hidden rounded-full bg-[var(--raised)] sm:order-none sm:col-span-1" aria-hidden="true">
                <motion.span className="block h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${Math.max(1.5, v * 100)}%` }}
                  transition={{ duration: 0.6, delay: i * 0.05, ease: 'easeOut' }}
                  style={{ background: g.amostra_pequena ? listrado(cor) : cor }} />
              </span>
              <span className="text-right text-sm font-semibold tabular-nums text-ink">{fmtPct(v)}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

const umEm = (taxa) => taxa ? Math.max(1, Math.round(1 / taxa)) : null

function Contatos({ grupos, amostraMinima }) {
  const v = (grupos || []).filter(g => g.contatos)
  if (!v.length) return <p className="text-sm text-ink-2">Nenhum contato registrado no período.</p>
  const max = Math.max(...v.map(g => g.contatos)) || 1
  const ord = [...v].filter(g => !g.amostra_pequena && g.taxa_promessa).sort((a, b) => b.taxa_promessa - a.taxa_promessa)
  const bom = ord[0], ruim = ord[ord.length - 1]
  const nomeC = (k) => k === 'carta' ? 'Carta / e-mail' : nome(k)
  const noC = (k) => ({ telefone: 'Na ligação', email: 'No e-mail', carta: 'Na carta' })[k] || `No ${nomeC(k)}`
  return (
    <>
      <h3 className="text-[17px] font-semibold leading-snug text-ink">
        {bom ? `${noC(bom.chave)}, 1 em cada ${umEm(bom.taxa_promessa)} contatos vira promessa.` : 'Quantos contatos viram promessa de pagamento.'}
        {bom && ruim && ruim !== bom ? ` ${noC(ruim.chave)}, 1 em ${umEm(ruim.taxa_promessa)}.` : ''}
      </h3>
      <p className="mt-0.5 text-[13px] text-ink-2">Dos contatos registrados: quantos viraram conversa de verdade e quantos viraram promessa de pagamento.</p>
      <ul className="mt-4 flex flex-col gap-2.5">
        {v.map((g, i) => {
          const w = (g.contatos / max) * 100
          return (
            <li key={g.chave} title={`${nomeC(g.chave)}: ${fmtNum(g.contatos)} contatos, ${fmtPct(g.taxa_efetivo)} viraram conversa, ${fmtPct(g.taxa_promessa)} promessa`}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[110px_minmax(0,1fr)_150px]">
              <span className="truncate text-sm text-ink-2">{nomeC(g.chave)}</span>
              <span className="relative order-last col-span-2 h-2.5 rounded-full bg-[var(--raised)] sm:order-none sm:col-span-1" aria-hidden="true">
                <motion.span className="absolute inset-y-0 left-0 rounded-full" initial={{ width: 0 }} animate={{ width: `${w}%` }}
                  transition={{ duration: 0.6, delay: i * 0.05 }}
                  style={{ background: g.amostra_pequena ? listrado('var(--border-strong)') : 'var(--border-strong)' }} />
                <motion.span className="absolute inset-y-0 left-0 rounded-full bg-[var(--chart-4)] opacity-60" initial={{ width: 0 }}
                  animate={{ width: `${w * (g.taxa_efetivo || 0)}%` }} transition={{ duration: 0.6, delay: 0.1 + i * 0.05 }} />
                <motion.span className="absolute inset-y-0 left-0 rounded-full bg-[var(--chart-1)]" initial={{ width: 0 }}
                  animate={{ width: `${Math.max(g.taxa_promessa ? 1.5 : 0, w * (g.taxa_promessa || 0))}%` }} transition={{ duration: 0.6, delay: 0.2 + i * 0.05 }} />
              </span>
              <span className="whitespace-nowrap text-right text-[13px] text-ink-3">
                {g.taxa_promessa ? <><b className="font-semibold text-ink">1 em {umEm(g.taxa_promessa)}</b> vira promessa</> : 'nenhuma promessa'}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[11px] text-ink-3">
        <span className="flex flex-wrap gap-4">
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-full bg-[var(--border-strong)]" />contatos</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-full bg-[var(--chart-4)] opacity-60" />conversa de verdade</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-full bg-[var(--chart-1)]" />promessa de pagamento</span>
        </span>
        <span>barra listrada = amostra pequena (menos de {amostraMinima})</span>
      </div>
    </>
  )
}

function Numero({ rotulo, valor, nota, cor }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-6 py-5">
      <span className="text-[13px] text-ink-2">{rotulo}</span>
      <b className="text-[28px] font-bold leading-none tracking-tight tabular-nums" style={{ color: cor || 'var(--text)' }}>{valor}</b>
      <span className="text-xs text-ink-2">{nota}</span>
    </div>
  )
}

export default function Resultados() {
  const { token, isComando } = useAuth()
  const navigate = useNavigate()
  const [periodo, setPeriodo] = useState('90d')
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [tentativa, setTentativa] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  useEffect(() => {
    if (isComando && !alvo) { setDados(null); setCarregando(false); return }
    let vivo = true
    setCarregando(true); setErro(null)
    buscarResultados(periodo, isComando ? alvo : undefined)
      .then(d => { if (vivo) setDados(d) })
      .catch(e => { if (vivo) setErro(e) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [periodo, isComando, alvo, tentativa])

  const t = dados?.totais
  const quando = PERIODOS.find(p => p[0] === periodo)?.[2]

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <CabecalhoPagina rotulo="Resultados" icone={TrendingUp} titulo="O que a cobrança recuperou" ajuda="painel-de-resultados" className="!mb-0"
          subtitulo="O que está funcionando, a partir dos pagamentos registrados.">
          <div className="flex flex-wrap items-center gap-2">
            {isComando && (
              <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
                className="h-11 rounded-[12px] border border-line bg-surface px-3 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            <div className="flex gap-1 rounded-[14px] border border-line bg-surface p-1" role="tablist" aria-label="Período">
              {PERIODOS.map(([k, l]) => (
                <button key={k} type="button" role="tab" aria-selected={periodo === k} onClick={() => setPeriodo(k)}
                  className={`h-9 rounded-[10px] px-3.5 text-sm transition-colors ${periodo === k ? 'bg-[var(--raised)] font-semibold text-ink' : 'text-ink-2 hover:text-ink'}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>
        </CabecalhoPagina>

        {isComando && !alvo && <div className="rounded-[22px] border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver os resultados.</div>}
        <ErroCarga erro={erro} ocupado={carregando} onTentar={() => setTentativa(t => t + 1)} />
        {carregando && !dados && <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}

        {dados && (
          <div className={`space-y-4 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
            {!dados.condicoes_ativas && (
              <p className="flex items-start gap-2 rounded-[14px] border border-line bg-surface px-4 py-3 text-xs text-ink-2">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> O banco ainda não guarda canal e condições do pagamento: rode sql/migracao_feedbacks_acordo.sql e sql/migracao_feedbacks_canal.sql.
              </p>
            )}
            {t.registros === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-[22px] border border-line bg-surface px-6 py-12 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-[var(--raised)] text-accent-text"><TrendingUp className="h-5 w-5" aria-hidden="true" /></span>
                <b className="text-[17px] text-ink">Nenhum pagamento registrado {quando}</b>
                <p className="max-w-md text-sm leading-relaxed text-ink-2">Os resultados aparecem quando a equipe registra quem pagou e quem não pagou, com o canal. Leva menos de um minuto por devedor.</p>
                <button type="button" className="btn-primary mt-1" onClick={() => navigate('/feedback')}>Registrar pagamentos</button>
              </div>
            ) : (
              <>
                <section className="grid divide-y divide-line rounded-[22px] border border-line bg-surface sm:grid-cols-3 sm:divide-x sm:divide-y-0" aria-label="Resumo do período">
                  <Numero rotulo="Quanto entrou" valor={fmtBRL(t.recuperado)} cor="var(--success)" nota={`em ${fmtNum(t.pagos)} ${t.pagos === 1 ? 'pagamento' : 'pagamentos'}`} />
                  <Numero rotulo="Quem pagou" valor={fmtPct(t.taxa_pagamento)} nota={`${fmtNum(t.pagos)} de ${fmtNum(t.registros)} cobrados`} />
                  <Numero rotulo="Valor médio pago" valor={fmtBRL(t.ticket_medio)} nota="por pagamento registrado" />
                </section>

                <section className="flex flex-col gap-8 rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="res-func">
                  <p id="res-func" className="section-label">O que está funcionando</p>
                  {CORTES.map(c => {
                    const gs = dados[c.campo] ?? []
                    return gs.length ? <Corte key={c.k} c={c} grupos={gs} melhor={c.melhor ? dados[c.melhor] : null} /> : null
                  })}
                  {CORTES.some(c => (dados[c.campo] ?? []).some(g => g.amostra_pequena)) && (
                    <p className="-mt-3 text-[11px] text-ink-3">Barra listrada = amostra pequena (menos de {dados.amostra_minima} registros ou pagamentos): o número existe, mas não deve guiar decisão sozinho.</p>
                  )}
                </section>

                <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="res-contatos">
                  <p id="res-contatos" className="section-label mb-2">Contatos por canal</p>
                  <Contatos grupos={dados.contatos_por_canal} amostraMinima={dados.amostra_minima} />
                </section>
              </>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
