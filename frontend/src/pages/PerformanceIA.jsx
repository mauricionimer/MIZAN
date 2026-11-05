import { useEffect, useState } from 'react'
import { Loader2, Activity, CheckCircle2, AlertTriangle, Info } from 'lucide-react'
import { motion } from 'framer-motion'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import { useAuth } from '../context/AuthContext'
import { listarEmpresas, listarModelosEmpresa } from '../api'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

async function _get(caminho, token) {
  const res = await fetch(`${API_URL}${caminho}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}

const fmtData = (iso) => { try { return new Date(iso).toLocaleDateString('pt-BR') } catch { return '—' } }
const pct = (v) => v == null ? '—' : `${(v * 100).toFixed(0)}%`
const diasDesde = (iso) => { try { return Math.max(0, Math.round((Date.now() - new Date(iso)) / 86400000)) } catch { return null } }

// KS em palavras: a régua do mercado de crédito.
const leituraKS = (ks) => ks == null ? null : ks >= 40 ? 'muito bom' : ks >= 30 ? 'bom' : ks >= 20 ? 'regular' : 'fraco'

// O diagnóstico (backend/model/diagnostico.py) devolve a separação em
// `separacao` e as métricas em `medicao`. A tela lia `q.ks`, `q.auc_roc` e
// `q.n_pagou` no topo, que não existem: com medição real, tudo saía "—".
export function lerQualidade(q) {
  if (!q?.ok) return null
  const sep = q.separacao?.ok === false ? {} : (q.separacao || {})
  const med = q.medicao || {}
  return {
    ks: sep.ks ?? q.ks ?? null,
    ksLeitura: sep.ks_leitura ?? q.ks_leitura ?? null,
    auc: med.auc_roc ?? q.auc_roc ?? null,
    precisao: med.precisao ?? null,
    nAmostras: q.n_amostras ?? med.n_amostras ?? null,
    nPagou: sep.n_pagou ?? q.n_pagou ?? null,
    calibracao: q.calibracao_por_faixa || [],
    treino: q.dados_do_treino || null,
    modelo: q.modelo || null,
  }
}

function Cartao({ rotulo, titulo, sub, children, className = '' }) {
  return (
    <section className={`flex flex-col rounded-[22px] border border-line bg-surface px-6 py-[22px] ${className}`}>
      {rotulo && <p className="section-label">{rotulo}</p>}
      {titulo && <h2 className="mt-1.5 text-[19px] font-semibold leading-snug text-ink">{titulo}</h2>}
      {sub && <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{sub}</p>}
      <div className="mt-4 flex-1">{children}</div>
    </section>
  )
}

function Numero({ rotulo, valor, nota, cor }) {
  return (
    <div className="rounded-[22px] border border-line bg-surface px-5 py-[18px]">
      <p className="section-label">{rotulo}</p>
      <p className="mt-2 text-[28px] font-bold leading-none tracking-tight tabular-nums" style={{ color: cor || 'var(--text)' }}>{valor}</p>
      {nota && <p className="mt-2 text-xs text-ink-2">{nota}</p>}
    </div>
  )
}

// Barra fina com o número ao lado; `marca` desenha o previsto como um traço.
function Linha({ rotulo, valor, marca, forte, i = 0, larguraRotulo = 'sm:grid-cols-[150px_minmax(0,1fr)_52px]' }) {
  return (
    <li className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 ${larguraRotulo}`}>
      <span className={`truncate text-sm ${forte ? 'font-semibold text-ink' : 'text-ink-2'}`}>{rotulo}</span>
      <span className="relative order-last col-span-2 h-2.5 rounded-full bg-[var(--raised)] sm:order-none sm:col-span-1" aria-hidden="true">
        <motion.span className="absolute inset-y-0 left-0 rounded-full" initial={{ width: 0 }} animate={{ width: `${Math.max(1.5, Math.min(100, valor * 100))}%` }}
          transition={{ duration: 0.6, delay: i * 0.05 }} style={{ background: forte ? 'var(--chart-1)' : 'var(--border-strong)' }} />
        {marca != null && <span className="absolute -inset-y-1 w-0.5 rounded bg-[var(--text)]" style={{ left: `${Math.min(100, marca * 100)}%` }} />}
      </span>
      <b className="text-right text-sm tabular-nums text-ink">{pct(valor)}</b>
    </li>
  )
}

// "O score acerta?": em cada faixa de nota, quantos pagaram (barra) contra o
// que o modelo previu (traço). Faixas da mais alta para a mais baixa.
function Calibracao({ faixas }) {
  const f = [...faixas].reverse()
  const alta = f[0], baixa = f[f.length - 1]
  const maior = f.reduce((m, x) => Math.max(m, Math.abs(x.taxa_real_observada - x.prob_media_prevista)), 0)
  const frase = alta && baixa && alta.taxa_real_observada > baixa.taxa_real_observada
    ? `Sim: ${pct(alta.taxa_real_observada)} dos que tiraram as notas mais altas pagaram, contra ${pct(baixa.taxa_real_observada)} nas mais baixas.`
    : 'Ainda não: as notas altas não pagam mais que as baixas.'
  return (
    <Cartao rotulo="O score acerta?" titulo={frase}
      sub="Barra = quem pagou de verdade · traço = o que o modelo previu. Quanto mais perto, mais dá para confiar na fila.">
      <ul className="flex flex-col gap-3">
        {f.map((x, i) => (
          <Linha key={i} i={i} forte={i < 2} valor={x.taxa_real_observada} marca={x.prob_media_prevista}
            rotulo={i === 0 ? 'Notas mais altas' : i === f.length - 1 ? 'Notas mais baixas' : `${i + 1}ª faixa`} larguraRotulo="sm:grid-cols-[140px_minmax(0,1fr)_52px]" />
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[11px] text-ink-3">
        <span className="flex gap-4">
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-full bg-[var(--chart-1)]" />pagaram</span>
          <span className="flex items-center gap-1.5"><span className="h-3 w-0.5 rounded bg-[var(--text)]" />previsto</span>
        </span>
        <span>Maior diferença: {Math.round(maior * 100)} pontos · {f.reduce((s, x) => s + x.n, 0).toLocaleString('pt-BR')} devedores medidos</span>
      </div>
    </Cartao>
  )
}

// "Por que confiar nesta fila", em linguagem de gerente. Só frases que os
// números recebidos sustentam; o que não tem dado não aparece.
function Confianca({ m, ativa, metr, ql, pesos, deriva }) {
  const itens = []
  const ksReal = ql?.ks != null ? Number(ql.ks) : null
  const ks = ksReal ?? (metr?.ks != null ? Number(metr.ks) : null)
  if (ks != null) {
    const leitura = leituraKS(ks)
    const fonte = ksReal != null
      ? `medido em ${ql.nAmostras?.toLocaleString('pt-BR')} devedores com resultado registrado pela equipe`
      : 'medido no teste do treino'
    itens.push({ tipo: ks >= 30 ? 'ok' : 'atencao',
      texto: ks >= 30 ? `Separa bem quem paga de quem não paga: KS ${ks} (${leitura}), ${fonte}.`
        : `Separação ainda ${leitura === 'fraco' ? 'fraca' : 'regular'}: KS ${ks}, ${fonte}. A fila ajuda, mas com folga menor.` })
  } else {
    itens.push({ tipo: 'info', texto: 'Ainda não há medida de acerto com os dados da empresa: registre pagamentos (pagou e não pagou) para medir.' })
  }
  if (m?.usando === 'proprio' && ativa) {
    itens.push({ tipo: 'ok', texto: `Treinado com ${ativa.n_amostras?.toLocaleString('pt-BR') ?? '—'} devedores da própria empresa, em ${fmtData(ativa.criado_em)}.` })
  } else if (m) {
    itens.push({ tipo: 'info', texto: 'Usa o modelo geral do Mizan; ainda não foi treinado com o histórico desta empresa.' })
  }
  if (deriva?.mensagem) {
    itens.push(deriva.drift_detectado
      ? { tipo: 'atencao', texto: 'A carteira atual está diferente da usada no treino: vale treinar de novo.' }
      : { tipo: 'ok', texto: 'A carteira atual se parece com a do treino: o modelo segue valendo.' })
  }
  const ICONE = { ok: CheckCircle2, atencao: AlertTriangle, info: Info }
  const COR = { ok: 'var(--success)', atencao: 'var(--warning)', info: 'var(--text-muted)' }
  const algumAlerta = itens.some(i => i.tipo === 'atencao')
  return (
    <Cartao rotulo="Por que confiar nesta fila" titulo={ks == null ? 'Ainda sem medida com os dados da empresa.' : algumAlerta ? 'Dá para usar, com um ponto de atenção.' : 'Dá para confiar na ordem da fila.'}>
      <ul className="flex flex-col gap-3">
        {itens.map((it, i) => {
          const I = ICONE[it.tipo]
          return (
            <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink">
              <I className="mt-0.5 h-4 w-4 shrink-0" style={{ color: COR[it.tipo] }} aria-label={it.tipo === 'ok' ? 'ok' : it.tipo === 'atencao' ? 'atenção' : 'informação'} />
              <span>{it.texto}</span>
            </li>
          )
        })}
      </ul>
      {deriva?.drift_detectado && deriva.mensagem && <p className="mt-4 rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-3 text-[13px]" style={{ color: deriva.drift_detectado ? 'var(--warning)' : 'var(--ink-2)' }}>{deriva.mensagem}</p>}
      <p className="mt-4 text-[11px] text-ink-3">KS mede o quanto o score separa quem paga de quem não paga (régua do crédito: 20 regular, 30 bom, 40 muito bom).</p>
    </Cartao>
  )
}

const juntar = (xs) => xs.length > 1 ? `${xs.slice(0, -1).join(', ')} e ${xs.at(-1)}` : xs[0]

export default function PerformanceIA() {
  const { token, isComando } = useAuth()
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(false)

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  useEffect(() => {
    if (isComando && !alvo) { setDados(null); return }
    let vivo = true
    const q = isComando ? `?empresa_id=${encodeURIComponent(alvo)}` : ''
    setCarregando(true)
    Promise.all([
      listarModelosEmpresa(token, isComando ? alvo : '').catch(() => null),
      _get(`/admin/modelo/qualidade${q}`, token).catch(() => null),
      _get(`/admin/feature-importance${q}`, token).catch(() => null),
      _get(`/admin/drift${q}`, token).catch(() => null),
      _get(`/admin/bandit/stats${q}`, token).catch(() => null),
    ]).then(([modelos, qualidade, pesos, deriva, bandit]) => {
      if (vivo) setDados({ modelos, qualidade, pesos, deriva, bandit })
    }).finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [token, isComando, alvo])

  const m = dados?.modelos
  const ativa = m?.versoes?.find(v => v.versao === m?.versao_ativa)
  const metr = ativa?.metricas?.novo || {}
  const ql = lerQualidade(dados?.qualidade)
  const feats = dados?.pesos?.ok ? (dados.pesos.features || []).slice(0, 8) : []
  const acoes = (dados?.bandit?.acoes || []).filter(a => a.n_tentativas > 0)
    .sort((a, b) => (b.taxa_pagamento ?? 0) - (a.taxa_pagamento ?? 0))
  const proprio = m?.usando === 'proprio' && ativa
  const nTreino = proprio ? ativa.n_amostras : ql?.modelo?.n_treino
  const poucos = ql?.treino?.adequado === false
  const dias = proprio ? diasDesde(ativa.criado_em) : null
  const top2 = feats.slice(0, 2)

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <CabecalhoPagina rotulo="Resultados" icone={Activity} titulo="Performance da IA" ajuda="performance-da-ia" className="!mb-0"
          subtitulo="O quanto o modelo acerta quem vai pagar, e o que mais pesa nessa conta.">
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} aria-label="Empresa" className="input-base h-11 w-56 rounded-[12px] px-3">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </CabecalhoPagina>

        {carregando && <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
        {isComando && !alvo && <p className="rounded-[22px] border border-line bg-surface p-6 text-sm text-ink-2">Escolha uma empresa para ver a IA dela.</p>}

        {dados && !carregando && (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Numero rotulo="Acerto do modelo" valor={ql?.precisao != null ? pct(ql.precisao) : '—'}
                nota={ql?.precisao != null ? 'dos que ele disse que pagariam, pagaram' : 'registre pagamentos para medir'} />
              <Numero rotulo="Treinado com" valor={nTreino != null ? `${nTreino.toLocaleString('pt-BR')} devedores` : '—'}
                cor={poucos ? 'var(--warning)' : undefined}
                nota={poucos ? 'poucos para o número de variáveis: o score ainda oscila' : proprio ? 'da própria empresa' : 'modelo geral do Mizan'} />
              <Numero rotulo="Último treino" valor={proprio ? fmtData(ativa.criado_em).slice(0, 5) : 'Geral'}
                nota={proprio ? (dias === 0 ? 'hoje' : `há ${dias} ${dias === 1 ? 'dia' : 'dias'}`) : 'ainda sem treino com o histórico da empresa'} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {ql?.calibracao?.length >= 2
                ? <Calibracao faixas={ql.calibracao} />
                : <Cartao rotulo="O score acerta?" titulo="Ainda não dá para medir."
                    sub={dados.qualidade?.motivo || 'Precisa de pagamentos registrados (pagou e não pagou) para comparar o previsto com o que aconteceu.'} />}
              <Confianca m={m} ativa={ativa} metr={metr} ql={ql} pesos={dados.pesos} deriva={dados.deriva} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Cartao rotulo="O que mais pesa no score"
                titulo={top2.length ? `${juntar(top2.map(f => f.nome.toLowerCase())).replace(/^./, c => c.toUpperCase())} ${top2.length > 1 ? 'explicam' : 'explica'} ${Math.round(top2.reduce((s, f) => s + Number(f.percentual), 0))}% do score.` : 'Disponível depois da primeira análise.'}
                sub={feats.length ? `Quanto cada informação da planilha pesa na chance de pagar. Medido em ${dados.pesos.n_devedores?.toLocaleString('pt-BR')} devedores da análise mais recente.` : (dados.pesos?.mensagem || 'Aparece depois da primeira análise de carteira.')}>
                {!!feats.length && (
                  <ul className="flex flex-col gap-3">
                    {feats.map((f, i) => <Linha key={f.variavel} i={i} forte={i < 2} rotulo={f.nome} valor={Number(f.percentual) / 100} larguraRotulo="sm:grid-cols-[180px_minmax(0,1fr)_52px]" />)}
                  </ul>
                )}
                {!!dados.pesos?.nao_medidas?.length && <p className="mt-3 text-[11px] text-ink-3">Sem dado na planilha: {dados.pesos.nao_medidas.join(', ')}. Preencher deixa o score mais certeiro.</p>}
              </Cartao>

              <Cartao rotulo="Abordagens que mais funcionam"
                titulo={acoes.length ? `${acoes[0].label}: ${pct(acoes[0].taxa_pagamento)} pagam.` : 'Ainda sem contatos registrados.'}
                sub={acoes.length ? `Taxa de pagamento de cada abordagem, em ${dados.bandit.total_interacoes} contatos. Com poucas tentativas, a taxa ainda varia muito.` : 'Aparece quando os operadores registrarem contatos com a abordagem usada.'}>
                {!!acoes.length && (
                  <ul className="flex flex-col gap-3">
                    {acoes.map((a, i) => (
                      <li key={a.id}>
                        <ul><Linha i={i} forte={i === 0} rotulo={a.label} valor={a.taxa_pagamento ?? 0} larguraRotulo="sm:grid-cols-[230px_minmax(0,1fr)_52px]" /></ul>
                        <p className="mt-0.5 text-[11px] text-ink-3">{a.n_pagamentos} de {a.n_tentativas} tentativas{a.n_tentativas < 10 ? ' · amostra pequena' : ''}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Cartao>
            </div>

            <details className="rounded-[22px] border border-line bg-surface px-6 py-[18px]">
              <summary className="cursor-pointer text-sm font-semibold text-ink">Números técnicos do modelo</summary>
              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                {[['Modelo', proprio ? `Próprio (${ativa.versao})` : 'Geral do Mizan'],
                  ['KS medido', ql?.ks != null ? `${ql.ks} (${ql.ksLeitura || leituraKS(ql.ks)})` : '—'],
                  ['AUC medido', ql?.auc != null ? Number(ql.auc).toFixed(2) : '—'],
                  ['Devedores medidos', ql?.nAmostras?.toLocaleString('pt-BR') ?? '—'],
                  ['Pagaram', ql?.nPagou != null ? `${ql.nPagou.toLocaleString('pt-BR')}${ql.nAmostras ? ` (${Math.round((ql.nPagou / ql.nAmostras) * 100)}%)` : ''}` : '—'],
                  ['KS no teste do treino', metr.ks ?? '—'],
                  ['AUC no teste do treino', metr.auc != null ? metr.auc.toFixed(2) : '—'],
                  ['Devedores no treino', nTreino?.toLocaleString('pt-BR') ?? '—']].map(([k, v]) => (
                  <div key={k}><dt className="text-xs text-ink-3">{k}</dt><dd className="mt-0.5 text-sm font-semibold tabular-nums text-ink">{v}</dd></div>
                ))}
              </dl>
            </details>
          </>
        )}
      </div>
    </AppShell>
  )
}
