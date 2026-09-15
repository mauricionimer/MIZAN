import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, Loader2, LogOut, Brain, GitBranch, TrendingUp,
  AlertTriangle, CheckCircle2, Zap, Sliders, Database, Clock, PlayCircle,
  ShieldCheck, BarChart3, Award,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const fmtPct  = (v, casas = 1) => v != null ? `${(v * 100).toFixed(casas)}%` : '—'
const fmtData = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  : '—'

function Secao({ icon: Icon, titulo, sub, children, right }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_1px_4px_rgba(15,23,42,0.06)] overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl p-2 bg-blue-50 text-blue-600 shrink-0">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-800">{titulo}</p>
            {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
          </div>
        </div>
        {right}
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}

function Botao({ children, onClick, disabled, variante = 'primario', ...props }) {
  const cls = {
    primario:  'bg-blue-600 hover:bg-blue-700 text-white',
    secundario: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
    perigo:    'bg-red-50 hover:bg-red-100 text-red-600',
  }[variante]
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${cls}`}
      {...props}
    >
      {children}
    </button>
  )
}

async function _get(path, token) {
  const res = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
async function _post(path, token, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

export default function AprendizadoDashboard() {
  const navigate = useNavigate()
  const { token, usuario, logout } = useAuth()

  const [modelos, setModelos]     = useState(null)
  const [importancia, setImportancia] = useState(null)
  const [drift, setDrift]         = useState(null)
  const [priceModel, setPriceModel] = useState(null)
  const [convergencia, setConvergencia] = useState(null)
  const [scheduler, setScheduler] = useState(null)
  const [dbSyncCfg, setDbSyncCfg] = useState(null)
  const [dbSyncStatus, setDbSyncStatus] = useState(null)

  const [loading, setLoading] = useState(true)
  const [erro, setErro]       = useState('')
  const [acao, setAcao]       = useState('')   // ação em andamento (retreinar/promover/sync/etc.)
  const [msg, setMsg]         = useState('')

  const [minFeedbacks, setMinFeedbacks] = useState(30)
  const [autoPromover, setAutoPromover] = useState(false)
  const [alphaInput, setAlphaInput]     = useState(1.0)

  const carregar = useCallback(async () => {
    setLoading(true)
    setErro('')
    try {
      const [m, fi, d, pm, cv, sc, dc, ds] = await Promise.all([
        _get('/admin/modelos', token).catch(() => null),
        _get('/admin/feature-importance', token).catch(() => null),
        _get('/admin/drift', token).catch(() => null),
        _get('/admin/price-model', token).catch(() => null),
        _get('/admin/bandit/convergencia', token).catch(() => null),
        _get('/admin/scheduler/status', token).catch(() => null),
        _get('/admin/db-sync/config', token).catch(() => null),
        _get('/admin/db-sync/status', token).catch(() => null),
      ])
      setModelos(m); setImportancia(fi); setDrift(d); setPriceModel(pm)
      setConvergencia(cv); setScheduler(sc); setDbSyncCfg(dc); setDbSyncStatus(ds)
      if (cv) setAlphaInput(cv.alpha)
    } catch (e) {
      setErro('Erro ao carregar dados de aprendizado: ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { carregar() }, [carregar])

  async function executar(nome, fn) {
    setAcao(nome); setMsg(''); setErro('')
    try {
      const r = await fn()
      setMsg(typeof r === 'string' ? r : (r?.mensagem || r?.motivo || 'Concluído.'))
      await carregar()
    } catch (e) {
      setErro(e.message)
    } finally {
      setAcao('')
    }
  }

  const dispararRetreino = () => executar('retreinar', () =>
    _post(`/admin/retreinar?min_feedbacks=${minFeedbacks}&auto_promover=${autoPromover}`, token))

  const promoverVersao = (versao) => executar(`promover-${versao}`, () =>
    _post('/admin/retreinar/promover', token, { versao }))

  const ajustarAlpha = () => executar('alpha', async () => {
    const res = await fetch(`${API_URL}/admin/bandit/alpha`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ alpha: alphaInput }),
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(d.detail || `HTTP ${res.status}`)
    return { mensagem: `Alpha ajustado para ${d.alpha}.` }
  })

  const verificarSchedulerAgora = () => executar('scheduler', () =>
    _post('/admin/scheduler/verificar', token))

  const executarDbSyncAgora = () => executar('dbsync', () =>
    _post('/admin/db-sync/executar', token))

  const toggleDbSyncAtivo = () => executar('dbsync-toggle', async () => {
    const res = await fetch(`${API_URL}/admin/db-sync/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...dbSyncCfg, ativo: !dbSyncCfg.ativo, senha: dbSyncCfg.senha === '***' ? '***' : dbSyncCfg.senha }),
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(d.detail || `HTTP ${res.status}`)
    return { mensagem: d.ativo ? 'Sincronização automática ativada.' : 'Sincronização automática desativada.' }
  })

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/comando')} className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-lg hover:bg-slate-100">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20"
            style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
            <Brain className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="font-bold text-slate-800 text-sm">Mizan</span>
          <span className="text-slate-200 text-sm">/</span>
          <span className="text-slate-500 text-sm">Gestão do Aprendizado</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={carregar} disabled={loading} className="nav-link disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Atualizar
          </button>
          <span className="text-sm text-slate-400 hidden sm:block">{usuario?.nome}</span>
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-6">
        {loading && !modelos && (
          <div className="flex flex-col items-center justify-center py-28 gap-3 text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">Carregando painel de aprendizado...</p>
          </div>
        )}

        {erro && (
          <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-4 text-sm text-red-700">{erro}</div>
        )}
        {msg && (
          <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 rounded-2xl px-5 py-3.5 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4 shrink-0" /> {msg}
          </div>
        )}

        {!loading && (
          <>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Gestão do Aprendizado</h1>
              <p className="text-sm text-slate-500 mt-1">Acesso restrito ao COMANDO — versões do modelo, variáveis, drift e ciclo de retreino</p>
            </div>

            {/* Drift */}
            {drift && (
              drift.drift_detectado ? (
                <div className="flex items-start gap-3 bg-amber-50 border border-amber-100 rounded-2xl px-5 py-4 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-500" />
                  <div>
                    <p className="font-semibold">Possível drift do modelo detectado</p>
                    <p className="text-amber-700 mt-0.5">{drift.mensagem}</p>
                  </div>
                </div>
              ) : drift.media_recente_30d != null ? (
                <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-100 rounded-2xl px-5 py-3.5 text-sm text-emerald-700">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" /> {drift.mensagem}
                </div>
              ) : null
            )}

            {/* Versões do modelo */}
            <Secao
              icon={GitBranch}
              titulo="Versões do modelo de crédito"
              sub={modelos ? `Ativa: ${modelos.versao_ativa} · ${modelos.total_versoes} versão(ões)` : ''}
              right={
                <div className="flex items-center gap-2">
                  <input
                    type="number" min={1} value={minFeedbacks}
                    onChange={e => setMinFeedbacks(Number(e.target.value))}
                    className="w-20 text-xs border border-slate-200 rounded-lg px-2 py-1.5"
                    title="Mínimo de feedbacks para retreinar"
                  />
                  <label className="flex items-center gap-1.5 text-xs text-slate-500">
                    <input type="checkbox" checked={autoPromover} onChange={e => setAutoPromover(e.target.checked)} />
                    auto-promover
                  </label>
                  <Botao onClick={dispararRetreino} disabled={acao === 'retreinar'}>
                    {acao === 'retreinar' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="h-3.5 w-3.5" />}
                    Retreinar agora
                  </Botao>
                </div>
              }
            >
              {!modelos?.versoes?.length ? (
                <p className="text-sm text-slate-400">Nenhuma versão de modelo registrada ainda.</p>
              ) : (
                <div className="overflow-x-auto -mx-2">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        <th className="px-2 py-2">Versão</th>
                        <th className="px-2 py-2">Origem</th>
                        <th className="px-2 py-2">Criada em</th>
                        <th className="px-2 py-2 text-right">Amostras</th>
                        <th className="px-2 py-2 text-right">AUC-ROC (CV)</th>
                        <th className="px-2 py-2 text-right">Acurácia real</th>
                        <th className="px-2 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {modelos.versoes.map(v => (
                        <tr key={v.versao} className={v.ativa ? 'bg-blue-50/50' : ''}>
                          <td className="px-2 py-3 font-mono text-xs text-slate-600">{v.versao}</td>
                          <td className="px-2 py-3">
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${v.tipo_alvo === 'real' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                              {v.tipo_alvo === 'real' ? 'Dados reais' : 'Sintético'}
                            </span>
                          </td>
                          <td className="px-2 py-3 text-xs text-slate-500">{fmtData(v.criado_em)}</td>
                          <td className="px-2 py-3 text-right text-xs text-slate-500">{v.n_amostras_treino ?? '—'}</td>
                          <td className="px-2 py-3 text-right text-xs text-slate-500">{fmtPct(v.metricas_treino?.cv_auc_media)}</td>
                          <td className="px-2 py-3 text-right text-xs font-semibold text-slate-700">{fmtPct(v.acuracia_real)}</td>
                          <td className="px-2 py-3 text-right">
                            {v.ativa ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600">
                                <ShieldCheck className="h-3.5 w-3.5" /> Ativa
                              </span>
                            ) : (
                              <Botao variante="secundario" onClick={() => promoverVersao(v.versao)} disabled={acao === `promover-${v.versao}`}>
                                {acao === `promover-${v.versao}` ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Promover'}
                              </Botao>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Secao>

            {/* Importância das variáveis */}
            <Secao
              icon={BarChart3}
              titulo="O que mais pesa no score"
              sub={importancia ? `${importancia.total_features} variáveis no modelo ativo` : 'Importância de cada variável no modelo ativo'}
            >
              {!importancia?.features?.length ? (
                <p className="text-sm text-slate-400">Importância indisponível para o modelo atual.</p>
              ) : (
                <div className="space-y-2.5">
                  {importancia.features.slice(0, 12).map(f => (
                    <div key={f.nome} className="flex items-center gap-3">
                      <span className="text-xs font-mono text-slate-500 w-40 truncate shrink-0">{f.nome}</span>
                      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(f.percentual, 100)}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-slate-600 w-12 text-right shrink-0">{f.percentual}%</span>
                    </div>
                  ))}
                </div>
              )}
            </Secao>

            <div className="grid grid-cols-2 gap-6">
              {/* Price model */}
              <Secao icon={Award} titulo="Modelo de precificação" sub="Estima quanto do valor devido é recuperado quando o devedor paga">
                {!priceModel?.disponivel ? (
                  <p className="text-sm text-slate-400">{priceModel?.mensagem || 'Indisponível.'}</p>
                ) : (
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div><p className="text-xs text-slate-400">Amostras / pagamentos</p><p className="font-bold text-slate-700">{priceModel.n_amostras} / {priceModel.n_pagamentos}</p></div>
                    <div><p className="text-xs text-slate-400">R² médio (CV)</p><p className="font-bold text-slate-700">{priceModel.r2_medio}</p></div>
                    <div><p className="text-xs text-slate-400">MAE médio</p><p className="font-bold text-slate-700">{priceModel.mae_medio}</p></div>
                  </div>
                )}
              </Secao>

              {/* Bandit: convergência + alpha */}
              <Secao
                icon={Zap}
                titulo="Bandit de abordagem (LinUCB)"
                sub={convergencia ? `${convergencia.acoes_convergidas}/${convergencia.acoes_total} ações convergidas` : ''}
                right={<Botao variante="secundario" onClick={() => navigate('/bandit')}>Ver detalhes</Botao>}
              >
                <div className="flex items-center gap-3">
                  <Sliders className="h-4 w-4 text-slate-400 shrink-0" />
                  <label className="text-xs text-slate-500 shrink-0">Exploração (alpha)</label>
                  <input
                    type="range" min={0.1} max={5} step={0.1}
                    value={alphaInput} onChange={e => setAlphaInput(Number(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-xs font-mono text-slate-600 w-10 text-right">{alphaInput.toFixed(1)}</span>
                  <Botao onClick={ajustarAlpha} disabled={acao === 'alpha'}>
                    {acao === 'alpha' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Aplicar'}
                  </Botao>
                </div>
                <p className="text-xs text-slate-400 mt-3">
                  Valor alto = mais exploração de novas abordagens; valor baixo = prioriza o que já sabe que funciona.
                </p>
              </Secao>
            </div>

            {/* Retreinamento automático */}
            <Secao
              icon={Clock}
              titulo="Retreinamento automático (scheduler)"
              sub={scheduler ? `Última verificação: ${fmtData(scheduler.ultima_verificacao)}` : ''}
              right={
                <Botao variante="secundario" onClick={verificarSchedulerAgora} disabled={acao === 'scheduler'}>
                  {acao === 'scheduler' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Verificar agora
                </Botao>
              }
            >
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div><p className="text-xs text-slate-400">Próxima verificação</p><p className="font-semibold text-slate-700">{fmtData(scheduler?.proxima_verificacao)}</p></div>
                <div><p className="text-xs text-slate-400">Retreinamentos automáticos</p><p className="font-semibold text-slate-700">{scheduler?.n_retreinamentos ?? 0}</p></div>
                <div>
                  <p className="text-xs text-slate-400">Último resultado</p>
                  <p className="font-semibold text-slate-700">
                    {scheduler?.ultimo_resultado
                      ? (scheduler.ultimo_resultado.motivo || (scheduler.ultimo_resultado.ok ? 'Sucesso' : 'Falha'))
                      : '—'}
                  </p>
                </div>
              </div>
            </Secao>

            {/* Conexão de sincronização de pagamentos */}
            <Secao
              icon={Database}
              titulo="Sincronização com banco de dados do cliente"
              sub="Busca pagamentos confirmados de um banco externo para realimentar o aprendizado (closed-loop)"
              right={
                dbSyncCfg && (
                  <div className="flex items-center gap-2">
                    <Botao variante={dbSyncCfg.ativo ? 'perigo' : 'secundario'} onClick={toggleDbSyncAtivo} disabled={acao === 'dbsync-toggle'}>
                      {acao === 'dbsync-toggle' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : (dbSyncCfg.ativo ? 'Desativar' : 'Ativar')}
                    </Botao>
                    <Botao onClick={executarDbSyncAgora} disabled={acao === 'dbsync' || !dbSyncCfg.ativo}>
                      {acao === 'dbsync' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      Sincronizar agora
                    </Botao>
                  </div>
                )
              }
            >
              {!dbSyncCfg ? (
                <p className="text-sm text-slate-400">Configuração indisponível.</p>
              ) : (
                <div className="grid grid-cols-4 gap-4 text-sm">
                  <div><p className="text-xs text-slate-400">Status</p><p className={`font-semibold ${dbSyncCfg.ativo ? 'text-emerald-600' : 'text-slate-500'}`}>{dbSyncCfg.ativo ? 'Ativo' : 'Inativo'}</p></div>
                  <div><p className="text-xs text-slate-400">Tipo</p><p className="font-semibold text-slate-700 uppercase">{dbSyncCfg.tipo}</p></div>
                  <div><p className="text-xs text-slate-400">Última sincronização</p><p className="font-semibold text-slate-700">{fmtData(dbSyncStatus?.ultimo_sync)}</p></div>
                  <div><p className="text-xs text-slate-400">Total de sincronizações</p><p className="font-semibold text-slate-700">{dbSyncStatus?.n_sincronizacoes ?? 0}</p></div>
                </div>
              )}
              <p className="text-xs text-slate-400 mt-4">
                Configuração de host/credenciais é feita via API (<code className="font-mono">POST /admin/db-sync/config</code>).
                Para importar carteiras de um banco externo, use a tela de Conexões.
              </p>
            </Secao>
          </>
        )}
      </main>
    </div>
  )
}
