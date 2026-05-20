import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, FileText, AlertCircle, Loader2, History, FolderOpen, Database, RefreshCw, CheckCircle2, XCircle, ChevronRight, Plug } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import { analisarCarteira, analisarDB, testarDB, listarCarteiras, carregarCarteira, getDBSyncConfig, saveDBSyncConfig, executarDBSync } from '../api'

const API_TOKEN = import.meta.env.VITE_API_TOKEN ?? ''

const fmtBRL = (v) => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
  : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtDate = (iso) => {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

const SYNC_TIPOS = [
  { value: 'postgres',  label: 'PostgreSQL', portaPadrao: 5432 },
  { value: 'mysql',     label: 'MySQL',      portaPadrao: 3306 },
  { value: 'mariadb',   label: 'MariaDB',    portaPadrao: 3306 },
  { value: 'sqlserver', label: 'SQL Server', portaPadrao: 1433 },
  { value: 'oracle',    label: 'Oracle',     portaPadrao: 1521 },
  { value: 'sqlite',    label: 'SQLite',     portaPadrao: null },
]

function PainelSyncAuto() {
  const [cfg, setCfg]         = useState(null)
  const [salvando, setSalvando] = useState(false)
  const [sincronizando, setSincronizando] = useState(false)
  const [msg, setMsg]         = useState(null) // {tipo:'ok'|'erro', texto}
  const [aberto, setAberto]   = useState(false)

  useEffect(() => {
    if (!API_TOKEN || !aberto) return
    getDBSyncConfig(API_TOKEN).then(setCfg).catch(() => {})
  }, [aberto])

  const set = (k, v) => setCfg(c => ({ ...c, [k]: v }))
  const isSQLite = cfg?.tipo === 'sqlite'

  const salvar = async () => {
    setSalvando(true); setMsg(null)
    try {
      await saveDBSyncConfig(API_TOKEN, cfg)
      setMsg({ tipo: 'ok', texto: 'Configuração salva.' })
    } catch (e) {
      setMsg({ tipo: 'erro', texto: e.message })
    } finally { setSalvando(false) }
  }

  const sincronizar = async () => {
    setSincronizando(true); setMsg(null)
    try {
      const r = await executarDBSync(API_TOKEN)
      const txt = r.acao === 'sincronizou'
        ? `${r.n_registros} pagamentos sincronizados.`
        : r.acao === 'sem_novos' ? 'Nenhum registro novo.' : r.erro ?? r.acao
      setMsg({ tipo: r.sincronizou || r.acao === 'sem_novos' ? 'ok' : 'erro', texto: txt })
      getDBSyncConfig(API_TOKEN).then(setCfg).catch(() => {})
    } catch (e) {
      setMsg({ tipo: 'erro', texto: e.message })
    } finally { setSincronizando(false) }
  }

  if (!API_TOKEN) return null

  return (
    <div className="w-full max-w-lg mt-4">
      <button
        onClick={() => setAberto(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white rounded-xl border border-slate-200 shadow-sm hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <RefreshCw className="h-4 w-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-700">Sincronização Automática de Pagamentos</span>
          {cfg?.ativo && <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">Ativo</span>}
        </div>
        <span className="text-slate-400 text-xs">{aberto ? '▲' : '▼'}</span>
      </button>

      {aberto && cfg && (
        <div className="bg-white border border-slate-200 border-t-0 rounded-b-xl px-6 py-5 space-y-4 shadow-sm">
          <p className="text-xs text-slate-500">
            Conecte ao seu banco de dados de cobrança. O sistema vai buscar automaticamente quem pagou a cada 24h e registrar os feedbacks.
          </p>

          {/* Toggle ativo */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => set('ativo', !cfg.ativo)}
              className={`w-10 h-5 rounded-full transition-colors relative ${cfg.ativo ? 'bg-emerald-500' : 'bg-slate-200'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${cfg.ativo ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-sm font-medium text-slate-700">{cfg.ativo ? 'Sincronização ativada' : 'Sincronização desativada'}</span>
          </label>

          {/* Tipo */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tipo de banco</label>
            <select value={cfg.tipo} onChange={e => set('tipo', e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300">
              {SYNC_TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {!isSQLite && (
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-500 mb-1">Host</label>
                <input value={cfg.host ?? ''} onChange={e => set('host', e.target.value)} placeholder="localhost"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Porta</label>
                <input value={cfg.porta ?? ''} onChange={e => set('porta', e.target.value ? Number(e.target.value) : null)} type="number"
                  placeholder={String(SYNC_TIPOS.find(t => t.value === cfg.tipo)?.portaPadrao ?? '')}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              {isSQLite ? 'Caminho do arquivo' : 'Nome do banco'}
            </label>
            <input value={cfg.banco ?? ''} onChange={e => set('banco', e.target.value)}
              placeholder={isSQLite ? '/caminho/banco.db' : 'nome_do_banco'}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
          </div>

          {!isSQLite && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Usuário</label>
                <input value={cfg.usuario ?? ''} onChange={e => set('usuario', e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Senha</label>
                <input type="password" value={cfg.senha === '***' ? '' : (cfg.senha ?? '')} onChange={e => set('senha', e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Query SQL</label>
            <textarea value={cfg.query ?? ''} onChange={e => set('query', e.target.value)} rows={3}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none" />
            <p className="text-xs text-slate-400 mt-1">Use <code className="bg-slate-100 px-1 rounded">:ultimo_sync</code> para filtrar apenas registros novos.</p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[['coluna_cpf','Coluna CPF'],['coluna_pagou','Coluna Pagou'],['coluna_valor','Coluna Valor']].map(([k,l]) => (
              <div key={k}>
                <label className="block text-xs font-medium text-slate-500 mb-1">{l}</label>
                <input value={cfg[k] ?? ''} onChange={e => set(k, e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
            ))}
          </div>

          {msg && (
            <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${msg.tipo === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
              {msg.tipo === 'ok' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
              {msg.texto}
            </div>
          )}

          {cfg.ultimo_sync && (
            <p className="text-xs text-slate-400">
              Última sync: {new Intl.DateTimeFormat('pt-BR', {dateStyle:'short',timeStyle:'short'}).format(new Date(cfg.ultimo_sync))}
              {' · '}{cfg.n_sincronizacoes} sincronizações realizadas
            </p>
          )}

          <div className="flex gap-3">
            <button onClick={salvar} disabled={salvando}
              className="flex-1 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {salvando ? 'Salvando...' : 'Salvar configuração'}
            </button>
            <button onClick={sincronizar} disabled={sincronizando}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors">
              <RefreshCw className={`h-3.5 w-3.5 ${sincronizando ? 'animate-spin' : ''}`} />
              {sincronizando ? 'Sincronizando...' : 'Testar agora'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

const DB_TIPOS = [
  { value: 'postgres',  label: 'PostgreSQL',            portaPadrao: 5432 },
  { value: 'mysql',     label: 'MySQL',                  portaPadrao: 3306 },
  { value: 'mariadb',   label: 'MariaDB',                portaPadrao: 3306 },
  { value: 'sqlserver', label: 'SQL Server',             portaPadrao: 1433 },
  { value: 'oracle',    label: 'Oracle',                 portaPadrao: 1521 },
  { value: 'sqlite',    label: 'SQLite (arquivo local)', portaPadrao: null  },
  { value: 'sheets',    label: 'Google Sheets',          portaPadrao: null  },
]

const CAMPOS_MIZAN = [
  { key: 'cpf',            label: 'CPF / Documento',    obrigatorio: true,  hint: 'Identificador único do devedor' },
  { key: 'valor_divida',   label: 'Valor da Dívida',    obrigatorio: true,  hint: 'Saldo devedor em R$' },
  { key: 'dias_em_atraso', label: 'Dias em Atraso',     obrigatorio: true,  hint: 'Dias desde o vencimento' },
  { key: 'nome',           label: 'Nome / Razão Social', obrigatorio: false, hint: 'Padrão: "Desconhecido"' },
  { key: 'produto',        label: 'Produto / Tipo',     obrigatorio: false, hint: 'Padrão: "pessoal"' },
  { key: 'status',         label: 'Status / Situação',  obrigatorio: false, hint: 'Padrão: "inadimplente"' },
  { key: 'uf',             label: 'UF / Estado',        obrigatorio: false, hint: 'Padrão: "SP"' },
  { key: 'renda_estimada', label: 'Renda Estimada',     obrigatorio: false, hint: 'Padrão: 0' },
]

function inp(cls = '') {
  return `w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 ${cls}`
}

function FormDB({ onResult }) {
  const [etapa, setEtapa]       = useState('conexao')   // 'conexao' | 'mapeamento' | 'analisando'
  const [form, setForm]         = useState({
    tipo: 'postgres', host: '', porta: '', banco: '',
    usuario: '', senha: '', query: 'SELECT * FROM devedores', nome_fonte: '',
  })
  const [teste, setTeste]       = useState(null)        // resultado de /testar-db
  const [mapa, setMapa]         = useState({})          // {campo_mizan: coluna_banco}
  const [loadingTeste, setLoadingTeste] = useState(false)
  const [loadingAnalise, setLoadingAnalise] = useState(false)
  const [erro, setErro]         = useState(null)

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setErro(null) }
  const isSQLite  = form.tipo === 'sqlite'
  const isSheets  = form.tipo === 'sheets'
  const isSQLServer = form.tipo === 'sqlserver'
  const isOracle  = form.tipo === 'oracle'
  const tipoInfo  = DB_TIPOS.find(t => t.value === form.tipo)

  function paramsConexao() {
    if (isSheets) {
      let creds = null
      try { creds = form.sheets_credenciais ? JSON.parse(form.sheets_credenciais) : null } catch {}
      return {
        tipo: 'sheets',
        sheets_id: form.sheets_id || null,
        sheets_aba: form.sheets_aba || null,
        sheets_credenciais: creds,
        nome_fonte: form.nome_fonte || 'google_sheets',
        query: null,
      }
    }
    return {
      tipo:          form.tipo,
      host:          isSQLite ? null : (form.host || null),
      porta:         isSQLite ? null : (form.porta ? Number(form.porta) : tipoInfo?.portaPadrao),
      banco:         form.banco || null,
      usuario:       isSQLite ? null : (form.usuario || null),
      senha:         isSQLite ? null : (form.senha || null),
      instance_name: isSQLServer ? (form.instance_name || null) : null,
      service_name:  isOracle ? (form.service_name || null) : null,
      query:         form.query,
      nome_fonte:    form.nome_fonte || `db_${form.tipo}`,
    }
  }

  async function testar() {
    if (!isSheets && !form.query.trim()) { setErro('Informe uma consulta SQL.'); return }
    if (isSheets && !form.sheets_id) { setErro('Informe o ID da planilha.'); return }
    setLoadingTeste(true); setErro(null)
    try {
      const res = await testarDB(paramsConexao())
      setTeste(res)
      setMapa(res.mapeamento_sugerido)
      setEtapa('mapeamento')
    } catch (e) {
      setErro(e.message)
    } finally {
      setLoadingTeste(false)
    }
  }

  async function analisar() {
    const faltando = CAMPOS_MIZAN.filter(c => c.obrigatorio && !mapa[c.key])
    if (faltando.length) {
      setErro(`Mapeie os campos obrigatórios: ${faltando.map(c => c.label).join(', ')}`)
      return
    }
    setLoadingAnalise(true); setEtapa('analisando'); setErro(null)
    try {
      const data = await analisarDB({ ...paramsConexao(), mapeamento: mapa })
      onResult(data)
    } catch (e) {
      setErro(e.message)
      setEtapa('mapeamento')
    } finally {
      setLoadingAnalise(false)
    }
  }

  // ── Etapa 1: conexão ──────────────────────────────────────
  if (etapa === 'conexao') return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Tipo de banco</label>
        <select value={form.tipo} onChange={e => set('tipo', e.target.value)} className={inp()}>
          {DB_TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      {/* Google Sheets */}
      {isSheets && (
        <>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">ID da planilha</label>
            <input value={form.sheets_id || ''} onChange={e => set('sheets_id', e.target.value)}
              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms" className={inp()} />
            <p className="text-xs text-slate-400 mt-1">Encontre o ID na URL da planilha: docs.google.com/spreadsheets/d/<strong>ID</strong>/edit</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Nome da aba (opcional)</label>
            <input value={form.sheets_aba || ''} onChange={e => set('sheets_aba', e.target.value)}
              placeholder="Planilha1" className={inp()} />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Credenciais da Service Account (JSON)</label>
            <textarea value={form.sheets_credenciais || ''} onChange={e => set('sheets_credenciais', e.target.value)}
              rows={4} placeholder='{"type":"service_account","project_id":"..."}' className={inp('font-mono text-xs resize-none')} />
            <p className="text-xs text-slate-400 mt-1">Cole o JSON da Service Account do Google Cloud com acesso à planilha.</p>
          </div>
        </>
      )}

      {/* SQL comum */}
      {!isSQLite && !isSheets && (
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-500 mb-1">Host</label>
            <input value={form.host} onChange={e => set('host', e.target.value)}
              placeholder="localhost" className={inp()} />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Porta</label>
            <input value={form.porta} onChange={e => set('porta', e.target.value)}
              placeholder={String(tipoInfo?.portaPadrao ?? '')} type="number" className={inp()} />
          </div>
        </div>
      )}

      {isSQLServer && (
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Instance Name (opcional)</label>
          <input value={form.instance_name || ''} onChange={e => set('instance_name', e.target.value)}
            placeholder="SQLEXPRESS" className={inp()} />
        </div>
      )}

      {!isSheets && (
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">
            {isSQLite ? 'Caminho do arquivo (.db)' : isOracle ? 'Service Name / SID' : 'Nome do banco'}
          </label>
          <input value={form.banco} onChange={e => set('banco', e.target.value)}
            placeholder={isSQLite ? '/caminho/banco.db' : isOracle ? 'ORCL' : 'nome_do_banco'} className={inp()} />
        </div>
      )}

      {!isSQLite && !isSheets && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Usuário</label>
            <input value={form.usuario} onChange={e => set('usuario', e.target.value)} className={inp()} />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Senha</label>
            <input type="password" value={form.senha} onChange={e => set('senha', e.target.value)} className={inp()} />
          </div>
        </div>
      )}

      {!isSheets && (
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Consulta SQL</label>
          <textarea value={form.query} onChange={e => set('query', e.target.value)} rows={3}
            className={inp('font-mono resize-none')} />
          <p className="text-xs text-slate-400 mt-1">Apenas SELECT. O sistema detecta as colunas automaticamente.</p>
        </div>
      )}

      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Nome da fonte (opcional)</label>
        <input value={form.nome_fonte} onChange={e => set('nome_fonte', e.target.value)}
          placeholder={`consulta_${form.tipo}`} className={inp()} />
      </div>

      {erro && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}

      <button onClick={testar} disabled={loadingTeste}
        className={`w-full py-3 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition-all
          ${loadingTeste ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-sm active:scale-[0.98]'}`}
      >
        {loadingTeste
          ? <><Loader2 className="h-4 w-4 animate-spin" /> Testando conexão...</>
          : <><Plug className="h-4 w-4" /> Testar conexão e detectar colunas</>}
      </button>
    </div>
  )

  // ── Etapa 2: mapeamento de colunas ────────────────────────
  if (etapa === 'mapeamento') return (
    <div className="space-y-4">
      {/* Status da conexão */}
      <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
        <div className="text-sm">
          <span className="font-medium text-emerald-800">Conectado com sucesso.</span>
          <span className="text-emerald-600 ml-1">{teste.total_colunas} colunas encontradas.</span>
        </div>
        <button onClick={() => { setEtapa('conexao'); setTeste(null) }}
          className="ml-auto text-xs text-slate-400 hover:text-slate-600 underline">
          Voltar
        </button>
      </div>

      {/* Mapeamento de campos */}
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Mapeamento de colunas
        </p>
        <div className="space-y-2">
          {CAMPOS_MIZAN.map(campo => {
            const mapeado = !!mapa[campo.key]
            return (
              <div key={campo.key} className="grid grid-cols-2 gap-2 items-center">
                <div className="flex items-center gap-1.5">
                  {mapeado
                    ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    : campo.obrigatorio
                      ? <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                      : <div className="h-3.5 w-3.5 rounded-full border-2 border-slate-200 shrink-0" />}
                  <span className={`text-xs font-medium ${mapeado ? 'text-slate-700' : campo.obrigatorio ? 'text-red-600' : 'text-slate-400'}`}>
                    {campo.label}
                    {campo.obrigatorio && <span className="text-red-400 ml-0.5">*</span>}
                  </span>
                </div>
                <select
                  value={mapa[campo.key] || ''}
                  onChange={e => setMapa(m => ({ ...m, [campo.key]: e.target.value || undefined }))}
                  className={`text-xs border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300 ${
                    mapeado ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : campo.obrigatorio ? 'border-red-200 bg-red-50'
                    : 'border-slate-200'
                  }`}
                >
                  <option value="">{campo.obrigatorio ? '— selecionar —' : `— padrão: ${campo.hint} —`}</option>
                  {teste.colunas.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-slate-400 mt-2">* Obrigatório. Campos sem mapeamento usam valores padrão.</p>
      </div>

      {/* Preview das primeiras linhas */}
      {teste.preview?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
            Preview (primeiras {teste.preview.length} linhas)
          </p>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="text-xs w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {teste.colunas.map(col => (
                    <th key={col} className="px-3 py-2 text-left font-medium text-slate-500 whitespace-nowrap">
                      {col}
                      {Object.entries(mapa).find(([, v]) => v === col) && (
                        <span className="ml-1 text-emerald-500">→ {Object.entries(mapa).find(([, v]) => v === col)[0]}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {teste.preview.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    {teste.colunas.map(col => (
                      <td key={col} className="px-3 py-1.5 text-slate-600 whitespace-nowrap max-w-[120px] truncate">
                        {row[col] ?? '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {erro && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}

      <button onClick={analisar} disabled={loadingAnalise}
        className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-blue-600 hover:bg-blue-700 flex items-center justify-center gap-2 transition-all shadow-sm active:scale-[0.98]"
      >
        <ChevronRight className="h-4 w-4" /> Analisar carteira
      </button>
    </div>
  )

  // ── Etapa 3: analisando ───────────────────────────────────
  return (
    <div className="flex flex-col items-center justify-center py-10 gap-3 text-slate-500">
      <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      <p className="text-sm font-medium">Carregando e analisando dados...</p>
      <p className="text-xs text-slate-400">Isso pode levar alguns segundos dependendo do volume.</p>
    </div>
  )
}

export default function Upload() {
  const [aba, setAba]           = useState('arquivo') // 'arquivo' | 'db'
  const [file, setFile]         = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [historico, setHistorico] = useState([])
  const [histLoading, setHistLoading] = useState(true)
  const [abrindo, setAbrindo]   = useState(null)
  const inputRef = useRef()
  const navigate = useNavigate()
  const { setResult } = useAnalysis()

  useEffect(() => {
    listarCarteiras()
      .then(setHistorico)
      .catch(() => {})
      .finally(() => setHistLoading(false))
  }, [])

  const abrirCarteira = async (id) => {
    if (abrindo) return
    setAbrindo(id)
    try {
      const data = await carregarCarteira(id)
      setResult(data)
      navigate('/dashboard')
    } catch (e) {
      setError(`Erro ao abrir carteira: ${e.message}`)
    } finally {
      setAbrindo(null)
    }
  }

  const handleFile = (f) => {
    if (!f) return
    const nome = f.name.toLowerCase()
    if (!nome.endsWith('.csv') && !nome.endsWith('.xlsx') && !nome.endsWith('.xls')) {
      setError('Apenas arquivos .csv ou .xlsx são aceitos.'); return
    }
    setError(null)
    setFile(f)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [])

  const onDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const onDragLeave = (e) => { e.preventDefault(); setIsDragging(false) }

  const analisar = async () => {
    if (!file || loading) return
    setLoading(true)
    setError(null)
    try {
      const data = await analisarCarteira(file)
      setResult(data)
      navigate('/dashboard')
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  const handleDBResult = (data) => {
    setResult(data)
    navigate('/dashboard')
  }

  const fmtSize = (bytes) => bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      {/* Logo */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white text-lg font-bold">⚖</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Mizan</h1>
        </div>
        <p className="text-slate-500 text-sm">Plataforma de análise de carteira de crédito com IA</p>
      </div>

      {/* Card */}
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <h2 className="text-base font-semibold text-slate-800 mb-1">Carregar carteira</h2>
        <p className="text-sm text-slate-500 mb-5">
          Importe os dados dos devedores via arquivo ou conexão direta com banco de dados.
        </p>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-slate-100 rounded-xl mb-6">
          <button
            onClick={() => { setAba('arquivo'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${aba === 'arquivo' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          >
            <UploadCloud className="h-4 w-4" /> Arquivo
          </button>
          <button
            onClick={() => { setAba('db'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${aba === 'db' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          >
            <Database className="h-4 w-4" /> Banco de Dados
          </button>
        </div>

        {aba === 'arquivo' && (
          <>
            {/* Drop zone */}
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current.click()}
              onKeyDown={(e) => e.key === 'Enter' && inputRef.current.click()}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              className={`
                border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
                transition-all duration-200 select-none
                ${isDragging
                  ? 'border-blue-400 bg-blue-50 scale-[1.01]'
                  : file
                    ? 'border-emerald-300 bg-emerald-50'
                    : 'border-slate-300 hover:border-blue-300 hover:bg-slate-50'}
              `}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => handleFile(e.target.files[0])}
              />

              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <FileText className="h-10 w-10 text-emerald-500" />
                  <p className="font-semibold text-slate-800">{file.name}</p>
                  <p className="text-sm text-slate-400">{fmtSize(file.size)}</p>
                  <p className="text-xs text-blue-500 mt-1">Clique para trocar o arquivo</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <UploadCloud className={`h-10 w-10 transition-colors ${isDragging ? 'text-blue-400' : 'text-slate-300'}`} />
                  <div>
                    <p className="font-medium text-slate-600">Arraste o arquivo aqui</p>
                    <p className="text-sm text-slate-400 mt-0.5">ou clique para selecionar</p>
                  </div>
                  <p className="text-xs text-slate-300 mt-1">CSV ou Excel (.xlsx)</p>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              onClick={analisar}
              disabled={!file || loading}
              className={`
                mt-5 w-full py-3 rounded-xl font-semibold text-sm text-white
                flex items-center justify-center gap-2 transition-all duration-200
                ${!file || loading
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 shadow-sm active:scale-[0.98]'}
              `}
            >
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Analisando carteira...</>
                : 'Analisar carteira'}
            </button>

            <p className="mt-4 text-center text-xs text-slate-400">
              Colunas esperadas: cpf, nome, produto, status, uf, valor_divida, renda_estimada, dias_em_atraso
            </p>
          </>
        )}

        {aba === 'db' && <FormDB onResult={handleDBResult} />}
      </div>

      {/* Sincronização automática de pagamentos */}
      <PainelSyncAuto />

      {/* Histórico de análises */}
      <div className="w-full max-w-lg mt-6">
        <div className="flex items-center gap-2 mb-3">
          <History className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-600">Análises anteriores</h3>
        </div>

        {histLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-300" />
          </div>
        )}

        {!histLoading && historico.length === 0 && (
          <div className="text-center py-8 text-sm text-slate-400 bg-white rounded-xl border border-slate-200">
            Nenhuma análise salva ainda.
          </div>
        )}

        {!histLoading && historico.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100 overflow-hidden">
            {historico.map((c) => (
              <div key={c.id} className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors">
                <FileText className="h-4 w-4 text-slate-300 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{c.nome_arquivo}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {fmtDate(c.created_at)} · {fmtNum(c.total_devedores)} devedores · score médio {c.score_medio?.toFixed(1)}
                  </p>
                </div>
                <div className="text-right shrink-0 hidden sm:block">
                  <p className="text-xs font-semibold text-emerald-600">{fmtBRL(c.valor_esperado)}</p>
                  <p className="text-xs text-slate-400">esperado</p>
                </div>
                <button
                  onClick={() => abrirCarteira(c.id)}
                  disabled={!!abrindo}
                  className="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                >
                  {abrindo === c.id
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <FolderOpen className="h-3.5 w-3.5" />}
                  Abrir
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
