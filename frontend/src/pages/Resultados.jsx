// A1 — Resultados: "o que está funcionando". Cruza os pagamentos registrados
// por canal, fase de atraso, modalidade, desconto e forma (backend/resultados.py).
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Loader2, Info, Trophy, Banknote, ClipboardCheck, Percent, Receipt } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
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
}
const nome = (k) => NOMES[k] || k

const PERIODOS = [['30d', '30 dias'], ['90d', '90 dias'], ['365d', '12 meses'], ['tudo', 'Tudo']]

const CORTES = [
  { k: 'canal', label: 'Canal', campo: 'por_canal', taxa: true, melhor: 'melhor_canal',
    pergunta: 'Por qual canal a cobrança chegou, e quanto disso virou pagamento.' },
  { k: 'fase', label: 'Fase de atraso', campo: 'por_fase', taxa: true, melhor: 'melhor_fase',
    pergunta: 'Em que faixa de atraso o devedor estava quando foi cobrado.' },
  { k: 'modalidade', label: 'À vista × parcelado', campo: 'por_modalidade', taxa: false,
    pergunta: 'Como os pagamentos foram fechados.' },
  { k: 'desconto', label: 'Desconto', campo: 'por_desconto', taxa: false,
    pergunta: 'Quanto de desconto foi dado nos pagamentos.' },
  { k: 'forma', label: 'Forma de pagamento', campo: 'por_forma', taxa: false,
    pergunta: 'Como o dinheiro entrou.' },
]

function Numero({ icone: Icone, rotulo, valor, nota, i }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
      className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">{rotulo}</p>
        <Icone className="h-4 w-4 text-ink-2" />
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums tracking-tight text-ink sm:text-3xl">{valor}</p>
      {nota && <p className="mt-1 text-xs text-ink-2">{nota}</p>}
    </motion.div>
  )
}

// Barra horizontal: uma série, uma cor. O número fica escrito ao lado (nunca só a cor).
function Barras({ grupos, taxa }) {
  const valor = (g) => taxa ? (g.taxa_pagamento ?? 0) : g.recuperado
  const max = Math.max(...grupos.map(valor), taxa ? 0 : 1) || 1
  return (
    <ul className="space-y-2.5" aria-hidden="true">
      {grupos.map(g => {
        const v = valor(g)
        const pequeno = g.amostra_pequena
        const dica = taxa
          ? `${nome(g.chave)}: ${fmtPct(g.taxa_pagamento)} pagaram (${fmtNum(g.pagos)} de ${fmtNum(g.registros)})`
          : `${nome(g.chave)}: ${fmtBRL(g.recuperado)} em ${fmtNum(g.pagos)} pagamentos`
        return (
          <li key={g.chave} title={dica}
            className="group grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[minmax(7rem,9.5rem)_1fr_auto]">
            <span className={`truncate text-xs ${g.chave === 'nao_informado' ? 'text-ink-2 italic' : 'text-ink'}`}>{nome(g.chave)}</span>
            <div className="relative order-last col-span-2 h-4 rounded-r bg-raise-2/60 sm:order-none sm:col-span-1 sm:h-5">
              <motion.div initial={{ width: 0 }} animate={{ width: `${Math.max(1.5, (v / max) * 100)}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="h-full rounded-r-[4px] transition-opacity group-hover:opacity-80"
                style={pequeno
                  ? { background: 'repeating-linear-gradient(45deg, var(--chart-1) 0 3px, transparent 3px 6px)', border: '1px solid var(--chart-1)' }
                  : { background: 'var(--chart-1)' }} />
            </div>
            <span className="text-right text-xs tabular-nums text-ink sm:w-24">
              {taxa ? fmtPct(g.taxa_pagamento) : fmtBRL(g.recuperado)}
              {pequeno && <span className="block text-[11px] text-ink-2">amostra pequena</span>}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function Tabela({ grupos, taxa }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            {['Grupo', ...(taxa ? ['Registros', 'Pagaram', 'Taxa'] : ['Pagamentos']), 'Recuperado', 'Ticket médio'].map((h, i) => (
              <th key={h} className={`whitespace-nowrap px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-ink-2 ${i ? 'text-right' : 'text-left'}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grupos.map(g => (
            <tr key={g.chave} className="border-b border-line last:border-0">
              <td className="whitespace-nowrap px-3 py-2 text-ink">{nome(g.chave)}{g.amostra_pequena && <span className="ml-1.5 rounded bg-raise-2 px-1 py-px text-[11px] text-ink-2">amostra pequena</span>}</td>
              {taxa && <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtNum(g.registros)}</td>}
              <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtNum(g.pagos)}</td>
              {taxa && <td className="px-3 py-2 text-right font-semibold tabular-nums text-ink">{fmtPct(g.taxa_pagamento)}</td>}
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink">{fmtBRL(g.recuperado)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink-2">{fmtBRL(g.ticket_medio)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Contatos({ grupos }) {
  if (!grupos?.length) return <p className="text-sm text-ink-2">Nenhum contato registrado no período.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            {['Canal', 'Contatos', 'Efetivos', 'Viraram promessa'].map((h, i) => (
              <th key={h} className={`whitespace-nowrap px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-ink-2 ${i ? 'text-right' : 'text-left'}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grupos.map(g => (
            <tr key={g.chave} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink">{g.chave === 'carta' ? 'Carta / e-mail' : nome(g.chave)}{g.amostra_pequena && <span className="ml-1.5 rounded bg-raise-2 px-1 py-px text-[11px] text-ink-2">amostra pequena</span>}</td>
              <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtNum(g.contatos)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-ink">{fmtPct(g.taxa_efetivo)}</td>
              <td className="px-3 py-2 text-right font-semibold tabular-nums text-ink">{fmtPct(g.taxa_promessa)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Resultados() {
  const { token, isComando } = useAuth()
  const [periodo, setPeriodo] = useState('90d')
  const [corte, setCorte] = useState('canal')
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

  const c = CORTES.find(x => x.k === corte)
  const grupos = dados?.[c.campo] ?? []
  const destaque = c.melhor ? dados?.[c.melhor] : null
  const t = dados?.totais

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
              <TrendingUp className="h-5 w-5 text-blue-400" /> Resultados<DicaAjuda id="painel-de-resultados" />
            </h1>
            <p className="mt-1 text-sm text-ink-2">O que está funcionando, a partir dos pagamentos registrados.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isComando && (
              <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa"
                className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            <div className="flex rounded-lg border border-line bg-surface-2 p-0.5" role="tablist" aria-label="Período">
              {PERIODOS.map(([k, l]) => (
                <button key={k} role="tab" aria-selected={periodo === k} onClick={() => setPeriodo(k)}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${periodo === k ? 'bg-surface text-ink shadow-sm' : 'text-ink-2 hover:text-ink'}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>

        {isComando && !alvo && <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver os resultados.</div>}
        <ErroCarga erro={erro} ocupado={carregando} onTentar={() => setTentativa(t => t + 1)} />
        {carregando && !dados && <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}

        {dados && (
          <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
            {!dados.condicoes_ativas && (
              <p className="flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> O banco ainda não guarda canal e condições do pagamento: rode sql/migracao_feedbacks_acordo.sql e sql/migracao_feedbacks_canal.sql.
              </p>
            )}
            {t.registros === 0 ? (
              <div className="rounded-xl border border-line bg-surface px-6 py-12 text-center">
                <TrendingUp className="mx-auto h-8 w-8 text-ink-2 opacity-50" />
                <p className="mt-3 text-sm font-medium text-ink">Nenhum pagamento registrado no período</p>
                <p className="mt-1 text-xs text-ink-2">Os resultados aparecem conforme a equipe registra em Pagamentos quem pagou e quem não pagou, com o canal.</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
                  <Numero i={0} icone={ClipboardCheck} rotulo="Registros" valor={fmtNum(t.registros)} nota="pagou e não pagou" />
                  <Numero i={1} icone={Percent} rotulo="Taxa de pagamento" valor={fmtPct(t.taxa_pagamento)} nota={`${fmtNum(t.pagos)} pagaram`} />
                  <Numero i={2} icone={Banknote} rotulo="Recuperado" valor={fmtBRL(t.recuperado)} />
                  <Numero i={3} icone={Receipt} rotulo="Ticket médio" valor={fmtBRL(t.ticket_medio)} nota="por pagamento" />
                </div>

                <section className="rounded-xl border border-line bg-surface">
                  <div className="flex gap-1 overflow-x-auto border-b border-line p-1.5" role="tablist" aria-label="Corte">
                    {CORTES.map(x => (
                      <button key={x.k} role="tab" aria-selected={corte === x.k} onClick={() => setCorte(x.k)}
                        className={`relative whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${corte === x.k ? 'text-ink' : 'text-ink-2 hover:text-ink'}`}>
                        {corte === x.k && <motion.span layoutId="aba-corte" className="absolute inset-0 rounded-lg bg-raise-2" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
                        <span className="relative">{x.label}</span>
                      </button>
                    ))}
                  </div>
                  <div className="space-y-4 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-ink">{c.pergunta}</p>
                        <p className="mt-0.5 text-xs text-ink-2">
                          {c.taxa ? 'Taxa de pagamento = quem pagou ÷ registros do grupo.' : 'Só pagamentos: essas condições são registradas quando o devedor paga, então não há taxa aqui.'}
                        </p>
                      </div>
                      {destaque && (
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
                          <Trophy className="h-3.5 w-3.5" /> Melhor: {nome(destaque.chave)} · {fmtPct(destaque.taxa_pagamento)}
                        </span>
                      )}
                    </div>
                    {grupos.length === 0 ? <p className="text-sm text-ink-2">Sem dados neste corte.</p> : (
                      <div className="space-y-5">
                        <div className="max-w-3xl"><Barras grupos={grupos} taxa={c.taxa} /></div>
                        <Tabela grupos={grupos} taxa={c.taxa} />
                      </div>
                    )}
                    <p className="text-xs text-ink-2">
                      Barra hachurada = amostra pequena (menos de {dados.amostra_minima} {c.taxa ? 'registros' : 'pagamentos'}): o número existe, mas não deve guiar decisão sozinho.
                    </p>
                  </div>
                </section>

                <section className="rounded-xl border border-line bg-surface p-5">
                  <h2 className="mb-1 text-sm font-semibold text-ink">Contatos por canal</h2>
                  <p className="mb-3 text-xs text-ink-2">Dos contatos registrados na ficha do devedor: quantos foram efetivos (houve conversa) e quantos viraram promessa de pagamento.</p>
                  <Contatos grupos={dados.contatos_por_canal} />
                </section>
              </>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
