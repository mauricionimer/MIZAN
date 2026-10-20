import StatCard from '../components/StatCard'
import { KpiBento } from '../components/ui/stats-bento'
import { useEffect, useState } from 'react'
import { Brain, Loader2, Target, BarChart3, Activity, MessageSquare, ShieldCheck, CheckCircle2, AlertTriangle, Info } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
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

// KS em palavras: a régua do mercado de crédito.
const leituraKS = (ks) => ks == null ? null : ks >= 40 ? 'muito bom' : ks >= 30 ? 'bom' : ks >= 20 ? 'regular' : 'fraco'

function Cartao({ icone: Icone, titulo, children }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-6">
      <div className="mb-4 flex items-center gap-2">
        <Icone className="h-4 w-4 text-ink-3" />
        <h2 className="text-sm font-semibold text-ink">{titulo}</h2>
      </div>
      {children}
    </section>
  )
}

function Numero({ rotulo, valor, nota }) { return <StatCard label={rotulo} value={valor} nota={nota} /> }

// A5 — "por que confiar nesta fila?", em linguagem de gerente. Só frases que
// os números já recebidos sustentam; o que não tem dado não aparece.
function Confianca({ m, ativa, metr, q, pesos, deriva }) {
  const itens = []
  const ksReal = q?.ok && q.ks != null ? Number(q.ks) : null
  const ks = ksReal ?? (metr?.ks != null ? Number(metr.ks) : null)
  if (ks != null) {
    const leitura = leituraKS(ks)
    const fonte = ksReal != null
      ? `medido em ${q.n_amostras?.toLocaleString('pt-BR')} devedores com resultado registrado pela equipe`
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
  const top = pesos?.ok ? (pesos.features || []).slice(0, 3).map(f => f.nome.toLowerCase()) : []
  if (top.length) {
    itens.push({ tipo: 'info', texto: `O que mais decide a posição na fila: ${top.length > 1 ? `${top.slice(0, -1).join(', ')} e ${top.at(-1)}` : top[0]}.` })
  }
  const ICONE = { ok: CheckCircle2, atencao: AlertTriangle, info: Info }
  const COR = { ok: 'var(--success)', atencao: 'var(--warning)', info: 'var(--ink-2)' }
  return (
    <section className="rounded-xl border border-line bg-surface p-6">
      <div className="mb-4 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-blue-400" />
        <h2 className="text-sm font-semibold text-ink">Por que confiar nesta fila</h2>
      </div>
      <ul className="space-y-2.5">
        {itens.map((it, i) => {
          const I = ICONE[it.tipo]
          return (
            <li key={i} className="flex items-start gap-2.5 text-sm text-ink">
              <I className="mt-0.5 h-4 w-4 shrink-0" style={{ color: COR[it.tipo] }} aria-label={it.tipo === 'ok' ? 'ok' : it.tipo === 'atencao' ? 'atenção' : 'informação'} />
              <span>{it.texto}</span>
            </li>
          )
        })}
      </ul>
      <p className="mt-3 text-xs" style={{ color: 'var(--ink-3)' }}>
        KS mede o quanto o score separa quem paga de quem não paga (régua do crédito: 20 regular, 30 bom, 40 muito bom). Detalhes abaixo.
      </p>
    </section>
  )
}

const Vazio = ({ children }) => <p className="text-sm" style={{ color: 'var(--ink-3)' }}>{children}</p>

/**
 * Performance da IA da empresa, para o admin dela (só leitura). O servidor
 * prende o admin à própria empresa; o COMANDO escolhe qual ver.
 */
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
  const q = dados?.qualidade
  const acoes = (dados?.bandit?.acoes || []).filter(a => a.n_tentativas > 0)
    .sort((a, b) => (b.taxa_pagamento ?? 0) - (a.taxa_pagamento ?? 0))

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-xl font-bold tracking-tight text-ink">Performance da IA<DicaAjuda id="performance-da-ia" /></h1>
          {isComando && (
            <select value={alvo} onChange={e => setAlvo(e.target.value)} className="input-base w-56 text-sm">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </div>

        {carregando && <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
        {isComando && !alvo && <Vazio>Escolha uma empresa para ver a IA dela.</Vazio>}

        {dados && !carregando && (
          <>
            <Confianca m={m} ativa={ativa} metr={metr} q={q} pesos={dados.pesos} deriva={dados.deriva} />

            <Cartao icone={Brain} titulo="Modelo em uso">
              {m?.usando === 'proprio' && ativa ? (
                <KpiBento>
                  <Numero rotulo="Modelo" valor="Próprio" nota={`treinado em ${fmtData(ativa.criado_em)}`} />
                  <Numero rotulo="KS no teste do treino" valor={metr.ks ?? '—'} nota={leituraKS(metr.ks)} />
                  <Numero rotulo="AUC no teste do treino" valor={metr.auc != null ? metr.auc.toFixed(2) : '—'} />
                  <Numero rotulo="Devedores no treino" valor={ativa.n_amostras?.toLocaleString('pt-BR') ?? '—'} />
                </KpiBento>
              ) : (
                <Vazio>A empresa ainda usa o modelo geral do Mizan. Com o histórico de pagamentos da empresa, o modelo é treinado com os dados dela.</Vazio>
              )}
            </Cartao>

            <Cartao icone={Target} titulo="Acerto nos pagamentos registrados">
              {q?.ok ? (
                <KpiBento>
                  <Numero rotulo="KS" valor={q.ks ?? '—'} nota={q.ks_leitura || leituraKS(q.ks)} />
                  <Numero rotulo="AUC" valor={q.auc_roc != null ? Number(q.auc_roc).toFixed(2) : '—'} />
                  <Numero rotulo="Devedores medidos" valor={q.n_amostras?.toLocaleString('pt-BR') ?? '—'} />
                  <Numero rotulo="Pagaram" valor={q.n_pagou?.toLocaleString('pt-BR') ?? '—'}
                    nota={q.n_amostras ? `${((q.n_pagou / q.n_amostras) * 100).toFixed(0)}% dos medidos` : null} />
                </KpiBento>
              ) : (
                <Vazio>{q?.motivo || 'Ainda não há pagamentos registrados suficientes para medir o acerto da IA com os dados da empresa.'}</Vazio>
              )}
            </Cartao>

            <Cartao icone={BarChart3} titulo="O que mais pesa no score">
              {dados.pesos?.ok && dados.pesos.features?.length ? (
                <div className="space-y-2.5">
                  {dados.pesos.features.slice(0, 8).map(f => (
                    <div key={f.variavel}>
                      <div className="flex justify-between text-sm">
                        <span className="text-ink">{f.nome}</span>
                        <span className="tabular-nums text-ink-2">{Number(f.percentual).toFixed(0)}%</span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full" style={{ background: 'var(--raise-3)' }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.min(100, f.percentual)}%`, background: 'var(--chart-1)' }} />
                      </div>
                    </div>
                  ))}
                  <p className="pt-1 text-xs" style={{ color: 'var(--ink-3)' }}>
                    Medido nos devedores da análise mais recente ({dados.pesos.n_devedores?.toLocaleString('pt-BR')}).
                  </p>
                </div>
              ) : (
                <Vazio>{dados.pesos?.mensagem || 'Disponível depois da primeira análise de carteira.'}</Vazio>
              )}
            </Cartao>

            <Cartao icone={Activity} titulo="Estabilidade da carteira">
              {dados.deriva?.mensagem ? (
                <p className="text-sm" style={{ color: dados.deriva.drift_detectado ? 'var(--warning)' : 'var(--ink-2)' }}>
                  {dados.deriva.mensagem}
                </p>
              ) : <Vazio>Sem análises recentes para comparar com o treino.</Vazio>}
            </Cartao>

            <Cartao icone={MessageSquare} titulo="Abordagens que mais funcionam">
              {acoes.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: 'var(--ink-3)' }}>
                        <th className="py-1.5 text-left font-medium">Abordagem</th>
                        <th className="text-right font-medium">Tentativas</th>
                        <th className="text-right font-medium">Pagaram</th>
                        <th className="text-right font-medium">Taxa</th>
                      </tr>
                    </thead>
                    <tbody>
                      {acoes.map(a => (
                        <tr key={a.id} style={{ borderTop: '1px solid var(--line)' }}>
                          <td className="py-1.5 text-ink">{a.label}</td>
                          <td className="text-right tabular-nums text-ink-2">{a.n_tentativas}</td>
                          <td className="text-right tabular-nums text-ink-2">{a.n_pagamentos}</td>
                          <td className="text-right font-semibold tabular-nums text-ink">{pct(a.taxa_pagamento)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs" style={{ color: 'var(--ink-3)' }}>
                    {dados.bandit.total_interacoes} contatos registrados. Com poucas tentativas por abordagem, a taxa ainda varia muito.
                  </p>
                </div>
              ) : (
                <Vazio>Aparece quando os operadores registrarem contatos com a abordagem usada.</Vazio>
              )}
            </Cartao>
          </>
        )}
      </div>
    </AppShell>
  )
}
