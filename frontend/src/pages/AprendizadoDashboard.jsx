import StatCard from '../components/StatCard'
import { KpiBento } from '../components/ui/stats-bento'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw, Loader2, GitBranch, AlertTriangle, CheckCircle2, Zap, Sliders, Database, Clock, PlayCircle, ShieldCheck, BarChart3, Award, Microscope, Target,
} from 'lucide-react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import DicaAjuda from '../components/DicaAjuda'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
const MUTED = 'var(--ink-3)'
const MUTED_LIGHT = 'var(--ink-2)'
const LABEL = 'var(--ink-2)'

const fmtPct  = (v, casas = 1) => v != null ? `${(v * 100).toFixed(casas)}%` : '—'
const fmtData = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  : '—'

function Secao({ icon: Icon, titulo, sub, children, right, ajuda }) {
  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
      <div className="px-6 py-4 border-b flex items-center justify-between flex-wrap gap-3" style={{ borderColor: 'var(--line)' }}>
        <div className="flex items-center gap-3">
          <div className="rounded-xl p-2 shrink-0" style={{ background: 'rgb(var(--c-royal) / 0.15)', color: 'rgb(var(--c-royal))' }}>
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-bold text-ink">{titulo}{ajuda && <DicaAjuda id={ajuda} />}</p>
            {sub && <p className="text-xs mt-0.5" style={{ color: MUTED }}>{sub}</p>}
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
    primario:   'text-on-brand hover:brightness-110',
    secundario: 'bg-raise-2 hover:bg-raise-3 text-ink-2',
    perigo:     'bg-red-500/10 hover:bg-red-500/20 text-red-300',
  }[variante]
  const style = variante === 'primario' ? { background: 'var(--royal)' } : undefined
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={style}
      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${cls}`}
      {...props}
    >
      {children}
    </button>
  )
}

function Barra({ pct, cor = 'rgb(var(--c-royal))' }) {
  return (
    <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--raise-3)' }}>
      <div className="h-full rounded-full" style={{ width: `${Math.min(Math.max(pct, 0), 100)}%`, background: cor }} />
    </div>
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

  const [qualidade, setQualidade] = useState(null)
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

  const [alphaInput, setAlphaInput]     = useState(1.0)
  const [empresaZerar, setEmpresaZerar] = useState('')
  const [empresaSel, setEmpresaSel]     = useState('')
  const [empresas, setEmpresas]         = useState([])

  const carregar = useCallback(async () => {
    setLoading(true)
    setErro('')
    try {
      const [q, m, fi, d, pm, cv, sc, dc, ds] = await Promise.all([
        _get('/admin/modelo/qualidade', token).catch(() => null),
        _get('/admin/modelos', token).catch(() => null),
        _get('/admin/feature-importance', token).catch(() => null),
        _get('/admin/drift', token).catch(() => null),
        _get('/admin/price-model', token).catch(() => null),
        _get('/admin/bandit/convergencia', token).catch(() => null),
        _get('/admin/scheduler/status', token).catch(() => null),
        _get('/admin/db-sync/config', token).catch(() => null),
        _get('/admin/db-sync/status', token).catch(() => null),
      ])
      setQualidade(q)
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

  async function executar(nome, fn, recarregar = true) {
    setAcao(nome); setMsg(''); setErro('')
    try {
      const r = await fn()
      setMsg(typeof r === 'string' ? r : (r?.mensagem || r?.motivo || 'Concluído.'))
      if (recarregar) await carregar()
    } catch (e) {
      setErro(e.message)
    } finally {
      setAcao('')
    }
  }

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

  const verEmpresa = () => executar('empresa', async () => {
    const emp = encodeURIComponent(empresaSel.trim().toLowerCase())
    const [q, pm, d, fi] = await Promise.all([
      _get(`/admin/modelo/qualidade?empresa_id=${emp}`, token),
      _get(`/admin/price-model?empresa_id=${emp}`, token),
      _get(`/admin/drift?empresa_id=${emp}`, token).catch(() => null),
      _get(`/admin/feature-importance?empresa_id=${emp}`, token).catch(e => ({ ok: false, mensagem: e.message })),
    ])
    setQualidade(q); setPriceModel(pm); setDrift(d); setImportancia(fi)
    return { mensagem: `Modelo em uso por ${empresaSel.trim().toLowerCase()} medido.` }
  }, false)

  useEffect(() => {
    _get('/comando/visao-geral', token)
      .then(d => setEmpresas((d?.empresas || []).map(e => e.empresa_id).filter(Boolean)))
      .catch(() => {})
  }, [token])

  const zerarBandit = () => {
    const emp = empresaZerar.trim()
    const conf = window.prompt(`Isto apaga, sem volta, o aprendizado das ofertas da empresa "${emp}". Digite ZERAR para confirmar.`)
    if ((conf || '').trim().toUpperCase() !== 'ZERAR') return
    executar('zerar', async () => {
      const d = await _post('/admin/bandit/zerar', token, { empresa_id: emp, confirmacao: conf })
      setEmpresaZerar('')
      return { mensagem: `Aprendizado de ${d.empresa_id} zerado (${d.interacoes_descartadas} interações descartadas).` }
    })
  }

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
    <AppShell titulo="Aprendizado" acoes={<button onClick={carregar} disabled={loading} className="nav-link disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> <span className="hidden sm:inline">Atualizar</span></button>}>

      <div className="w-full max-w-6xl mx-auto space-y-6">
        {loading && !modelos && (
          <div className="flex flex-col items-center justify-center py-28 gap-3" style={{ color: MUTED }}>
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">Carregando painel de aprendizado...</p>
          </div>
        )}

        {erro && (
          <div className="rounded-2xl px-5 py-4 text-sm text-red-300" style={{ background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.25)' }}>{erro}</div>
        )}
        {msg && (
          <div className="flex items-center gap-2 rounded-2xl px-5 py-3.5 text-sm text-emerald-300" style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.25)' }}>
            <CheckCircle2 className="h-4 w-4 shrink-0" /> {msg}
          </div>
        )}

        {!loading && (
          <>
            <div>
              <h1 className="text-xl font-bold text-ink tracking-tight">Gestão do Aprendizado</h1>
              <p className="text-sm mt-1" style={{ color: MUTED_LIGHT }}>Acesso restrito ao COMANDO — versões do modelo, variáveis, drift e ciclo de retreino</p>
            </div>

            {/* Procedência do modelo ativo — em que dado o score se apoia.
                Fica antes de qualquer métrica de propósito: número de modelo
                treinado em dado insuficiente não deve ser lido sem a ressalva. */}
            {qualidade?.procedencia && qualidade.procedencia.nivel !== 'ok' && (
              <div className="flex items-start gap-3 rounded-2xl px-5 py-4 text-sm"
                style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.25)', color: 'var(--ink)' }}>
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-400" />
                <div>
                  <p className="font-semibold">
                    {qualidade.procedencia.nivel === 'sintetico'
                      ? 'Modelo em calibração inicial'
                      : 'Modelo com base real insuficiente'}
                  </p>
                  <p className="mt-0.5" style={{ color: 'var(--ink-2)' }}>{qualidade.procedencia.aviso}</p>
                  <p className="mt-1.5 text-xs tnum" style={{ color: 'var(--ink-2)' }}>
                    Versão ativa: {qualidade.procedencia.versao_ativa}
                    {qualidade.procedencia.n_feedbacks_reais != null && (
                      <> · {qualidade.procedencia.n_feedbacks_reais} de {qualidade.procedencia.minimo_recomendado} resultados reais</>
                    )}
                  </p>
                </div>
              </div>
            )}

            {/* Deriva: PSI da população recente da empresa escolhida (D4) */}
            {drift?.psi?.ok && (
              drift.drift_detectado ? (
                <div className="flex items-start gap-3 rounded-2xl px-5 py-4 text-sm text-amber-300" style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.25)' }}>
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-semibold">A população de {drift.empresa_id} mudou em relação ao treino do modelo<DicaAjuda id="deriva-do-score" /></p>
                    <p className="opacity-90 mt-0.5">{drift.mensagem}</p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-2xl px-5 py-3.5 text-sm text-emerald-300" style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.25)' }}>
                  <CheckCircle2 className="h-4 w-4 shrink-0" /> {drift.mensagem}<DicaAjuda id="deriva-do-score" />
                </div>
              )
            )}

            {/* Qualidade do modelo EM USO por uma empresa (D6): mede o modelo que
                pontua a empresa nos pagamentos reais dela, não um modelo retreinado. */}
            <Secao
              icon={Microscope}
              titulo="Qualidade do modelo em uso" ajuda="overfitting"
              sub="O modelo que pontua esta empresa separa quem paga de quem não paga?"
              right={
                <div className="flex items-center gap-2">
                  <input list="aprendizado-empresas" value={empresaSel} onChange={e => setEmpresaSel(e.target.value)}
                    placeholder="empresa_id" aria-label="Empresa" className="input-base w-40 text-xs py-1.5 px-2" />
                  <datalist id="aprendizado-empresas">{empresas.map(e => <option key={e} value={e} />)}</datalist>
                  <Botao variante="secundario" onClick={verEmpresa} disabled={!empresaSel.trim() || acao === 'empresa'}>
                    {acao === 'empresa' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Medir'}
                  </Botao>
                </div>
              }
            >
              {!qualidade?.ok ? (
                <p className="text-sm" style={{ color: MUTED }}>{qualidade?.motivo || 'Diagnóstico indisponível.'}</p>
              ) : (
                <div className="space-y-6">
                  <div className="rounded-2xl border px-4 py-3.5 text-sm" style={{ background: 'var(--raise-2)', borderColor: 'var(--line)', color: 'var(--ink-2)' }}>
                    <p>
                      Modelo medido: <b className="text-ink">{qualidade.modelo.origem === 'proprio' ? 'próprio da empresa' : 'geral'}</b>
                      {' '}({qualidade.modelo.versao}{qualidade.modelo.tipo_alvo === 'real' ? ', treinado com resultado real' : ', treinado com dados simulados'}),
                      {' '}em <b className="text-ink">{qualidade.n_amostras}</b> devedores de {qualidade.empresa_id} com pagamento registrado
                      {qualidade.base === 'depois_do_treino' ? ' depois do treino dele (os que ele já viu ficam de fora)' : ''}.
                      {' '}Pagaram {fmtPct(qualidade.medicao.taxa_pagamento)}.
                    </p>
                    {qualidade.comparacao_com_o_treino && (
                      <p className="mt-1.5">
                        AUC no teste feito no treino: <b className="text-ink">{qualidade.comparacao_com_o_treino.auc_no_treino}</b> ·
                        {' '}agora: <b className="text-ink">{qualidade.comparacao_com_o_treino.auc_agora}</b>.
                        {' '}Uma queda grande indica que o modelo decorou o treino ou que a carteira mudou.
                      </p>
                    )}
                  </div>

                  {/* KS e Gini — o vocabulário que uma mesa de crédito usa.
                      Vêm antes da acurácia porque é o que se pergunta primeiro. */}
                  {qualidade.separacao && (
                    <div>
                      <p className="section-label mb-3">Separação — o modelo afasta quem paga de quem não paga?</p>
                      {qualidade.separacao.ok ? (
                        <div className="grid grid-cols-2 gap-4">
                          {[
                            { sigla: 'KS', valor: qualidade.separacao.ks, leitura: qualidade.separacao.ks_leitura,
                              regua: '< 20 fraco · 30–40 bom · > 50 suspeito' },
                            { sigla: 'Gini', valor: qualidade.separacao.gini, leitura: qualidade.separacao.gini_leitura,
                              regua: '< 20 fraco · 40–60 bom · > 60 forte' },
                          ].map(m => {
                            const cor = m.leitura === 'suspeito' ? 'var(--warning)'
                              : m.leitura === 'fraco' ? 'var(--danger)'
                              : m.leitura === 'regular' ? 'var(--ink-2)' : 'var(--success)'
                            return (
                              <div key={m.sigla} className="rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
                                <div className="flex items-baseline justify-between">
                                  <span className="section-label">{m.sigla}<DicaAjuda id={m.sigla === 'KS' ? 'ks' : 'gini'} /></span>
                                  <span className="text-xs font-semibold" style={{ color: cor }}>{m.leitura}</span>
                                </div>
                                <p className="tnum text-2xl font-bold mt-1" style={{ color: cor }}>{m.valor}</p>
                                <p className="text-xs mt-1" style={{ color: MUTED }}>{m.regua}</p>
                              </div>
                            )
                          })}
                        </div>
                      ) : (
                        <p className="text-xs" style={{ color: MUTED }}>{qualidade.separacao.motivo}</p>
                      )}
                      {qualidade.separacao.ok && qualidade.separacao.ks_leitura === 'suspeito' && (
                        <p className="text-xs mt-2" style={{ color: 'var(--warning)' }}>
                          KS acima de 50 costuma indicar vazamento de dados — alguma variável carregando a resposta.
                          Confira as colunas usadas no treino antes de confiar nesse número.
                        </p>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    {/* Matriz de confusão */}
                    <div>
                      <p className="section-label mb-3">Matriz de confusão ({qualidade.medicao.n_amostras} casos, corte em 50%)</p>
                      <div className="grid grid-cols-2 gap-2 text-center text-sm">
                        <div className="rounded-xl p-3" style={{ background: 'rgb(var(--c-success) / 0.10)', border: '1px solid rgb(var(--c-success) / 0.22)' }}>
                          <p className="text-lg font-bold text-emerald-300">{qualidade.medicao.matriz_confusao.verdadeiro_positivo}</p>
                          <p className="text-[11px] text-emerald-300/80 mt-0.5">Previu que pagava — pagou</p>
                        </div>
                        <div className="rounded-xl p-3" style={{ background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.22)' }}>
                          <p className="text-lg font-bold text-red-300">{qualidade.medicao.matriz_confusao.falso_positivo}</p>
                          <p className="text-[11px] text-red-300/80 mt-0.5">Previu que pagava — não pagou</p>
                        </div>
                        <div className="rounded-xl p-3" style={{ background: 'rgb(var(--c-warning) / 0.10)', border: '1px solid rgb(var(--c-warning) / 0.22)' }}>
                          <p className="text-lg font-bold text-amber-300">{qualidade.medicao.matriz_confusao.falso_negativo}</p>
                          <p className="text-[11px] text-amber-300/80 mt-0.5">Previu que não pagava — pagou</p>
                        </div>
                        <div className="rounded-xl p-3" style={{ background: 'var(--raise-2)', border: '1px solid var(--line)' }}>
                          <p className="text-lg font-bold text-ink">{qualidade.medicao.matriz_confusao.verdadeiro_negativo}</p>
                          <p className="text-[11px] mt-0.5" style={{ color: MUTED }}>Previu que não pagava — não pagou</p>
                        </div>
                      </div>
                      <KpiBento className="mt-3">
                        <StatCard label={<>Acurácia</>} value={<span>{fmtPct(qualidade.medicao.acuracia)}</span>} />
                        <StatCard label={<>Precisão</>} value={<span>{fmtPct(qualidade.medicao.precisao)}</span>} />
                        <StatCard label={<>Revocação</>} value={<span>{fmtPct(qualidade.medicao.revocacao)}</span>} />
                        <StatCard label={<>F1</>} value={<span>{fmtPct(qualidade.medicao.f1)}</span>} />
                      </KpiBento>
                      <p className="text-[11px] mt-2 leading-relaxed" style={{ color: MUTED }}>
                        "Positivo" aqui = o modelo previu que o devedor paga (score 50 ou mais). Precisão: das vezes que previu
                        pagamento, quantas acertou. Revocação: dos que realmente pagaram, quantos o modelo identificou.
                      </p>
                    </div>

                    {/* Calibração */}
                    <div>
                      <p className="section-label mb-3">
                        Calibração — a probabilidade é confiável?<DicaAjuda id="calibracao" /> <span className="tabular-nums" style={{ color: MUTED }}>(Brier: {qualidade.medicao.brier_score} · AUC: {qualidade.medicao.auc_roc})</span>
                      </p>
                      <div className="space-y-1.5">
                        {qualidade.calibracao_por_faixa.map((f, i) => {
                          const diff = Math.abs(f.prob_media_prevista - f.taxa_real_observada)
                          return (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span className="w-16 shrink-0" style={{ color: MUTED }}>Faixa {i + 1}</span>
                              <span className="w-20 shrink-0" style={{ color: MUTED_LIGHT }}>prev. {fmtPct(f.prob_media_prevista)}</span>
                              <div className="flex-1">
                                <Barra pct={f.prob_media_prevista * 100} />
                              </div>
                              <span className={`w-24 text-right font-semibold shrink-0 ${diff > 0.2 ? 'text-amber-300' : ''}`} style={diff > 0.2 ? undefined : { color: MUTED_LIGHT }}>
                                real {fmtPct(f.taxa_real_observada)}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                      <p className="text-xs mt-3" style={{ color: MUTED }}>
                        Compara, em cada faixa de probabilidade prevista, a taxa real de pagamento observada.
                        Quanto mais próximas, mais confiável é o score — não só pra ranquear, mas como probabilidade de verdade.
                      </p>
                    </div>
                  </div>

                  {/* Volume do treino do modelo em uso vs número de variáveis */}
                  {qualidade.dados_do_treino?.amostras_por_variavel != null && (
                    <div className="flex items-start gap-3 rounded-xl border px-4 py-3 text-xs"
                      style={qualidade.dados_do_treino.adequado
                        ? { background: 'var(--raise-2)', borderColor: 'var(--line)', color: MUTED_LIGHT }
                        : { background: 'rgb(var(--c-warning) / 0.10)', borderColor: 'rgb(var(--c-warning) / 0.25)', color: 'rgb(var(--c-warning))' }}>
                      <Target className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      <span>
                        <DicaAjuda id="dados-suficientes" />O modelo em uso foi treinado com {qualidade.dados_do_treino.n_treino} devedores
                        para {qualidade.dados_do_treino.n_variaveis} variáveis ({qualidade.dados_do_treino.amostras_por_variavel} por variável).
                        {qualidade.dados_do_treino.adequado
                          ? ' Volume adequado para a complexidade do modelo.'
                          : ' Abaixo do recomendado (≥ 20 por variável): desconfie das métricas do treino.'}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </Secao>

            {/* Versões do modelo */}
            <Secao
              icon={GitBranch}
              titulo="Versões do modelo de crédito" ajuda="versoes-e-promocao"
              sub={modelos ? `Ativa: ${modelos.versao_ativa} · ${modelos.total_versoes} versão(ões)` : ''}
              right={
                <Botao variante="secundario" onClick={() => navigate('/comando/treino')}>
                  <PlayCircle className="h-3.5 w-3.5" /> Treinar por empresa
                </Botao>
              }
            >
              <p className="mb-3 text-xs" style={{ color: MUTED }}>
                Este é o modelo geral, usado pelas empresas sem modelo próprio. Ele não é mais retreinado com os
                pagamentos dos clientes: misturaria o que cada empresa ensina. O treino com pagamentos reais é feito
                por empresa, e a versão só passa a valer quando o COMANDO ativa.
              </p>
              {!modelos?.versoes?.length ? (
                <p className="text-sm" style={{ color: MUTED }}>Nenhuma versão de modelo registrada ainda.</p>
              ) : (
                <div className="overflow-x-auto -mx-2">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs font-semibold uppercase tracking-wide" style={{ color: LABEL }}>
                        <th className="px-2 py-2">Versão</th>
                        <th className="px-2 py-2">Origem</th>
                        <th className="px-2 py-2">Criada em</th>
                        <th className="px-2 py-2 text-right">Amostras</th>
                        <th className="px-2 py-2 text-right">AUC-ROC (CV)<DicaAjuda id="auc-e-brier" /></th>
                        <th className="px-2 py-2 text-right">Acurácia real</th>
                        <th className="px-2 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                      {modelos.versoes.map(v => (
                        <tr key={v.versao} style={v.ativa ? { background: 'rgba(37,99,235,0.08)' } : undefined}>
                          <td className="px-2 py-3 tabular-nums text-xs" style={{ color: MUTED_LIGHT }}>{v.versao}</td>
                          <td className="px-2 py-3">
                            <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                              style={v.tipo_alvo === 'real'
                                ? { background: 'rgb(var(--c-success) / 0.12)', color: 'rgb(var(--c-success))' }
                                : { background: 'var(--raise-3)', color: MUTED }}>
                              {v.tipo_alvo === 'real' ? 'Dados reais' : 'Sintético'}
                            </span>
                          </td>
                          <td className="px-2 py-3 text-xs" style={{ color: MUTED }}>{fmtData(v.criado_em)}</td>
                          <td className="px-2 py-3 text-right text-xs" style={{ color: MUTED }}>{v.n_amostras_treino ?? '—'}</td>
                          <td className="px-2 py-3 text-right text-xs" style={{ color: MUTED }}>{fmtPct(v.metricas_treino?.cv_auc_media)}</td>
                          <td className="px-2 py-3 text-right text-xs font-semibold text-ink">{fmtPct(v.acuracia_real)}</td>
                          <td className="px-2 py-3 text-right">
                            {v.ativa ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--accent-text)' }}>
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

            {/* Peso das variáveis no modelo que pontua a empresa escolhida */}
            <Secao
              icon={BarChart3}
              titulo="O que mais pesa no score" ajuda="peso-das-variaveis"
              sub={importancia?.ok
                ? `${importancia.empresa_id} · modelo ${importancia.modelo?.origem === 'proprio' ? 'próprio' : 'geral'} · ${importancia.n_devedores} devedores da análise mais recente`
                : 'Escolha a empresa em "Qualidade do modelo em uso" e clique em Medir'}
            >
              {!importancia?.ok ? (
                <p className="text-sm" style={{ color: MUTED }}>{importancia?.mensagem || 'Indisponível.'}</p>
              ) : (
                <div className="space-y-2.5">
                  {importancia.features.map(f => (
                    <div key={f.variavel} className="flex items-center gap-3">
                      <span className="text-xs w-40 truncate shrink-0" style={{ color: MUTED }}>{f.nome}</span>
                      <div className="flex-1"><Barra pct={f.percentual} /></div>
                      <span className="text-xs font-semibold w-24 text-right shrink-0 tabular-nums" style={{ color: MUTED_LIGHT }}>
                        {f.impacto_medio_pontos.toFixed(1)} pts · {f.percentual}%
                      </span>
                    </div>
                  ))}
                  <p className="text-xs pt-2" style={{ color: MUTED }}>
                    Quanto o score de um devedor muda, em média, quando só aquela informação é trocada pelo valor típico do treino.
                    {importancia.nao_medidas?.length > 0 && ` Não medidas (não ficam gravadas na análise): ${importancia.nao_medidas.join(', ')}.`}
                  </p>
                </div>
              )}
            </Secao>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Price model */}
              <Secao icon={Award} ajuda="taxa-de-recuperacao" titulo="Modelo de precificação" sub="Estima quanto da dívida deve voltar, já contando quem não paga. É por empresa.">
                <p className="mb-3 text-xs" style={{ color: MUTED }}>
                  Empresa: {priceModel?.empresa_id || 'escolha em "Qualidade do modelo em uso" e clique em Medir'}
                </p>
                {!priceModel?.disponivel ? (
                  <p className="text-sm" style={{ color: MUTED }}>{priceModel?.mensagem || 'Indisponível.'}</p>
                ) : (
                  <KpiBento>
                    <StatCard label={<>Amostras / pagamentos</>} value={<span>{priceModel.n_amostras} / {priceModel.n_pagamentos}</span>} />
                    <StatCard label={<>R² médio (CV)</>} value={<span>{priceModel.r2_medio}</span>} />
                    <StatCard label={<>MAE médio</>} value={<span>{priceModel.mae_medio}</span>} />
                  </KpiBento>
                )}
              </Secao>

              {/* Bandit: convergência + alpha */}
              <Secao
                icon={Zap}
                titulo="Bandit de abordagem (LinUCB)" ajuda="estatisticas-do-bandit"
                sub={convergencia ? `${convergencia.acoes_convergidas}/${convergencia.acoes_total} ações convergidas` : ''}
                right={<Botao variante="secundario" onClick={() => navigate('/bandit')}>Ver detalhes</Botao>}
              >
                <div className="flex items-center gap-3">
                  <Sliders className="h-4 w-4 shrink-0" style={{ color: MUTED }} />
                  <label className="text-xs shrink-0" style={{ color: MUTED }}>Exploração (alpha)</label>
                  <input
                    type="range" min={0.1} max={5} step={0.1}
                    value={alphaInput} onChange={e => setAlphaInput(Number(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-xs tabular-nums w-10 text-right" style={{ color: MUTED_LIGHT }}>{alphaInput.toFixed(1)}</span>
                  <Botao onClick={ajustarAlpha} disabled={acao === 'alpha'}>
                    {acao === 'alpha' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Aplicar'}
                  </Botao>
                </div>
                <p className="text-xs mt-3" style={{ color: MUTED }}>
                  Valor alto = mais exploração de novas abordagens; valor baixo = prioriza o que já sabe que funciona.
                </p>
                <div className="mt-4 border-t pt-3 text-xs" style={{ borderColor: 'var(--line)', color: MUTED }}>
                  <p className="mb-2">
                    Até out/2026, pagamentos sem recomendação prévia ensinavam ao bandit uma ação que não foi feita.
                    Isso parou; o histórico de antes ainda carrega essas contagens. Para recomeçar uma empresa do zero:
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <input value={empresaZerar} onChange={e => setEmpresaZerar(e.target.value)} placeholder="empresa_id"
                      aria-label="Empresa para zerar o aprendizado" className="input-base w-40 text-xs py-1.5 px-2" />
                    <Botao variante="perigo" onClick={zerarBandit} disabled={!empresaZerar.trim() || acao === 'zerar'}>
                      {acao === 'zerar' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Zerar aprendizado das ofertas'}
                    </Botao>
                  </div>
                </div>
              </Secao>
            </div>

            {/* Retreinamento automático */}
            <Secao
              icon={Clock}
              titulo="Treino automático por empresa" ajuda="como-o-sistema-aprende"
              sub={scheduler ? `Última verificação: ${fmtData(scheduler.ultima_verificacao)}` : ''}
              right={
                <Botao variante="secundario" onClick={verificarSchedulerAgora} disabled={acao === 'scheduler'}>
                  {acao === 'scheduler' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Verificar agora
                </Botao>
              }
            >
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm">
                <StatCard label={<>Próxima verificação</>} value={<span>{fmtData(scheduler?.proxima_verificacao)}</span>} />
                <StatCard label={<>Versões treinadas (inativas)</>} value={<span>{scheduler?.n_retreinamentos ?? 0}</span>} />
                <div>
                  <p className="text-xs" style={{ color: MUTED }}>Último resultado</p>
                  <p className="font-semibold text-ink">
                    {scheduler?.ultimo_resultado
                      ? (scheduler.ultimo_resultado.mensagem || scheduler.ultimo_resultado.motivo || scheduler.ultimo_resultado.erro || '—')
                      : '—'}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-xs" style={{ color: MUTED }}>
                A cada verificação, cada empresa com pagamentos novos suficientes ganha uma versão nova do próprio modelo,
                treinada só com os pagamentos dela. Nada é ativado sozinho: confira e ative em Treinar por empresa.
              </p>
              {scheduler?.ultimo_resultado?.empresas && (
                <ul className="mt-3 space-y-1 text-xs" style={{ color: MUTED_LIGHT }}>
                  {Object.entries(scheduler.ultimo_resultado.empresas).map(([emp, r]) => (
                    <li key={emp}><span>{emp}</span>: {r.mensagem} ({r.novos} novos)</li>
                  ))}
                </ul>
              )}
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
                <p className="text-sm" style={{ color: MUTED }}>Configuração indisponível.</p>
              ) : (
                <KpiBento>
                  <StatCard label={<>Status</>} value={<span className="font-semibold" style={{ color: dbSyncCfg.ativo ? 'var(--success)' : MUTED_LIGHT }}>{dbSyncCfg.ativo ? 'Ativo' : 'Inativo'}</span>} />
                  <StatCard label={<>Tipo</>} value={<span className="font-semibold text-ink uppercase">{dbSyncCfg.tipo}</span>} />
                  <StatCard label={<>Última sincronização</>} value={<span>{fmtData(dbSyncStatus?.ultimo_sync)}</span>} />
                  <StatCard label={<>Total de sincronizações</>} value={<span>{dbSyncStatus?.n_sincronizacoes ?? 0}</span>} />
                </KpiBento>
              )}
              <p className="text-xs mt-4" style={{ color: MUTED }}>
                Configuração de host/credenciais é feita via API (<code className="tabular-nums">POST /admin/db-sync/config</code>).
                Para importar carteiras de um banco externo, use a tela de Conexões.
              </p>
            </Secao>
          </>
        )}
      </div>
    </AppShell>
  )
}
