import { useEffect, useState } from 'react'
import { Brain, Loader2, Target, BarChart3, Activity, MessageSquare } from 'lucide-react'
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

function Numero({ rotulo, valor, nota }) {
  return (
    <div>
      <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{rotulo}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-ink">{valor}</p>
      {nota && <p className="mt-0.5 text-xs" style={{ color: 'var(--ink-3)' }}>{nota}</p>}
    </div>
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
            <Cartao icone={Brain} titulo="Modelo em uso">
              {m?.usando === 'proprio' && ativa ? (
                <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
                  <Numero rotulo="Modelo" valor="Próprio" nota={`treinado em ${fmtData(ativa.criado_em)}`} />
                  <Numero rotulo="KS no teste do treino" valor={metr.ks ?? '—'} nota={leituraKS(metr.ks)} />
                  <Numero rotulo="AUC no teste do treino" valor={metr.auc != null ? metr.auc.toFixed(2) : '—'} />
                  <Numero rotulo="Devedores no treino" valor={ativa.n_amostras?.toLocaleString('pt-BR') ?? '—'} />
                </div>
              ) : (
                <Vazio>A empresa ainda usa o modelo geral do Mizan. Com o histórico de pagamentos da empresa, o modelo é treinado com os dados dela.</Vazio>
              )}
            </Cartao>

            <Cartao icone={Target} titulo="Acerto nos pagamentos registrados">
              {q?.ok ? (
                <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
                  <Numero rotulo="KS" valor={q.ks ?? '—'} nota={q.ks_leitura || leituraKS(q.ks)} />
                  <Numero rotulo="AUC" valor={q.auc_roc != null ? Number(q.auc_roc).toFixed(2) : '—'} />
                  <Numero rotulo="Devedores medidos" valor={q.n_amostras?.toLocaleString('pt-BR') ?? '—'} />
                  <Numero rotulo="Pagaram" valor={q.n_pagou?.toLocaleString('pt-BR') ?? '—'}
                    nota={q.n_amostras ? `${((q.n_pagou / q.n_amostras) * 100).toFixed(0)}% dos medidos` : null} />
                </div>
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
