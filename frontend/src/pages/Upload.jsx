import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, FileText, AlertCircle, Loader2, History, FolderOpen, Database, RefreshCw, CheckCircle2, XCircle, ChevronRight, Plug, X, ArrowLeft } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import { useAuth } from '../context/AuthContext'
import { analisarCarteira, analisarDB, testarDB, listarTabelas, listarCarteiras, carregarCarteira, listarConexoes, salvarConexao, deletarConexao, sincronizarConexao, atualizarConexao, listarEmpresas } from '../api'

const fmtBRL = (v) => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
  : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
const fmtDate = (iso) => {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}
const fmtRelativo = (iso) => {
  if (!iso) return null
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'agora mesmo'
  if (min < 60) return `há ${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `há ${h}h`
  return `há ${Math.floor(h / 24)}d`
}

const INTERVALOS_SYNC = [
  { value: 0.25,  label: 'A cada 15 min' },
  { value: 1,     label: 'A cada 1h' },
  { value: 4,     label: 'A cada 4h' },
  { value: 24,    label: 'A cada 24h' },
]

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
  return `w-full border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition bg-white ${cls}`
}

function FormDB({ onResult, isOperador = false, empresaAlvo = '' }) {
  const [etapa, setEtapa]       = useState('conexao')   // 'conexao' | 'mapeamento' | 'analisando'
  const [form, setForm]         = useState({
    tipo: 'postgres', host: '', porta: '', banco: '',
    usuario: '', senha: '', query: 'SELECT * FROM devedores', nome_fonte: '',
    intervalo_sync_horas: 1,
  })
  const [teste, setTeste]       = useState(null)
  const [mapa, setMapa]         = useState({})
  const [tabelas, setTabelas]   = useState([])
  const [loadingConexao, setLoadingConexao] = useState(false)
  const [loadingTeste, setLoadingTeste] = useState(false)
  const [loadingAnalise, setLoadingAnalise] = useState(false)
  const [erro, setErro]         = useState(null)

  const [conexoes,        setConexoes]        = useState([])
  const [nomeParaSalvar,  setNomeParaSalvar]  = useState('')
  const [salvandoConexao, setSalvandoConexao] = useState(false)
  const [conexaoSalvaId,  setConexaoSalvaId]  = useState(null)
  const [sincronizandoId, setSincronizandoId] = useState(null)
  const [syncMsg,         setSyncMsg]         = useState(null) // {tipo, texto}
  const [modo,            setModo]            = useState('lista') // 'lista' | 'nova'
  const [carregandoConexoes, setCarregandoConexoes] = useState(true)

  useEffect(() => {
    setCarregandoConexoes(true)
    listarConexoes()
      .then(data => {
        setConexoes(data)
        setModo(data.length === 0 ? 'nova' : 'lista')
      })
      .catch(() => { setModo('nova') })
      .finally(() => setCarregandoConexoes(false))
  }, [])

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
        conexao_id: conexaoSalvaId || null,
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
      conexao_id:    conexaoSalvaId || null,
    }
  }

  function carregarConexaoSalva(c) {
    setForm({
      tipo: c.tipo, host: c.host || '', porta: c.porta || '',
      banco: c.banco || '', usuario: c.usuario || '', senha: c.senha || '',
      query: c.query || 'SELECT * FROM devedores', nome_fonte: c.nome || '',
      instance_name: c.instance_name || '', service_name: c.service_name || '',
      sheets_id: c.sheets_id || '', sheets_aba: c.sheets_aba || '', sheets_credenciais: '',
      intervalo_sync_horas: c.intervalo_sync_horas ?? 1,
    })
    setConexaoSalvaId(c.id)
    setEtapa('conexao')
    setModo('nova')
    setErro(null)
  }

  async function salvarConexaoAtual() {
    const nome = (nomeParaSalvar || form.nome_fonte || '').trim()
    if (!nome) return
    setSalvandoConexao(true)
    try {
      const dados = {
        nome,
        tipo: form.tipo,
        host: form.host || null,
        porta: form.porta ? Number(form.porta) : null,
        banco: form.banco || null,
        usuario: form.usuario || null,
        senha: form.senha || null,
        instance_name: form.instance_name || null,
        service_name: form.service_name || null,
        sheets_id: form.sheets_id || null,
        sheets_aba: form.sheets_aba || null,
        query: isSheets ? null : (form.query || null),
        mapeamento: Object.keys(mapa).length > 0 ? mapa : undefined,
        empresa_id: empresaAlvo || undefined,
        intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1,
      }
      const res = await salvarConexao(dados)
      setConexoes(prev => [res.conexao, ...prev])
      setConexaoSalvaId(res.conexao.id)
      setNomeParaSalvar('')
    } catch (e) {
      setErro(`Erro ao salvar conexão: ${e.message}`)
    } finally {
      setSalvandoConexao(false)
    }
  }

  async function removerConexaoSalva(id, e) {
    e.stopPropagation()
    try {
      await deletarConexao(id)
      setConexoes(prev => prev.filter(c => c.id !== id))
      if (conexaoSalvaId === id) setConexaoSalvaId(null)
    } catch {}
  }

  async function sincronizarConexaoSalva(id, e) {
    e.stopPropagation()
    setSincronizandoId(id); setSyncMsg(null)
    try {
      const r = await sincronizarConexao(id)
      setSyncMsg({ tipo: 'ok', texto: `Sincronizado: ${r.n_devedores} devedores importados.` })
      setConexoes(prev => prev.map(c => c.id === id ? { ...c, ultimo_sync: new Date().toISOString() } : c))
      onResult(r.carteira)
    } catch (err) {
      setSyncMsg({ tipo: 'erro', texto: err.message })
    } finally {
      setSincronizandoId(null)
    }
  }

  async function conectar() {
    setLoadingConexao(true); setErro(null)
    if (isSheets) {
      if (!form.sheets_id) { setErro('Informe o ID da planilha.'); setLoadingConexao(false); return }
      // Sheets: vai direto para testar (não tem tabelas)
      try {
        const res = await testarDB(paramsConexao())
        setTeste(res); setMapa(res.mapeamento_sugerido); setEtapa('mapeamento')
      } catch (e) { setErro(e.message) }
      finally { setLoadingConexao(false) }
      return
    }
    try {
      const res = await listarTabelas({
        tipo: form.tipo, host: form.host || null,
        porta: form.porta ? Number(form.porta) : null,
        banco: form.banco || null,
        usuario: form.usuario || null,
        senha: form.senha || null,
        instance_name: isSQLServer ? (form.instance_name || null) : null,
        service_name: isOracle ? (form.service_name || null) : null,
        query: 'SELECT 1',
        conexao_id: conexaoSalvaId || null,
      })
      setTabelas(res.tabelas)
      setEtapa('tabelas')
    } catch (e) { setErro(e.message) }
    finally { setLoadingConexao(false) }
  }

  async function selecionarTabela(tabela) {
    const query = `SELECT * FROM ${tabela}`
    setForm(f => ({ ...f, query }))
    setLoadingTeste(true); setErro(null)
    try {
      const res = await testarDB({ ...paramsConexao(), query })
      setTeste(res); setMapa(res.mapeamento_sugerido); setEtapa('mapeamento')
    } catch (e) { setErro(e.message); setEtapa('tabelas') }
    finally { setLoadingTeste(false) }
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

    // 1. Salva a conexão PRIMEIRO (antes da análise) para garantir que fica no banco
    let savedId = conexaoSalvaId
    if (!savedId) {
      const autoNome = `${form.tipo.toUpperCase()} · ${(form.host || '').split('.')[0] || form.banco || 'banco'}`
      const nomeEfetivo = form.nome_fonte.trim() || nomeParaSalvar.trim() || autoNome
      try {
        const res = await salvarConexao({
          nome: nomeEfetivo,
          tipo: form.tipo,
          host: form.host || null,
          porta: form.porta ? Number(form.porta) : null,
          banco: form.banco || null,
          usuario: form.usuario || null,
          senha: form.senha || null,
          instance_name: form.instance_name || null,
          service_name: form.service_name || null,
          sheets_id: form.sheets_id || null,
          sheets_aba: form.sheets_aba || null,
          query: isSheets ? null : (form.query || null),
          mapeamento: mapa,
          intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1,
        })
        savedId = res.conexao.id
        setConexoes(prev => [res.conexao, ...prev])
        setConexaoSalvaId(savedId)
        setModo('lista')
      } catch (saveErr) {
        setErro(`Erro ao salvar conexão: ${saveErr.message}`)
        setEtapa('mapeamento')
        setLoadingAnalise(false)
        return
      }
    }

    // 2. Analisa com o banco
    try {
      const data = await analisarDB({ ...paramsConexao(), mapeamento: mapa, conexao_id: savedId, empresa_id_alvo: empresaAlvo || undefined })
      if (savedId) {
        atualizarConexao(savedId, {
          mapeamento: mapa,
          query: form.query,
          carteira_id: data.resumo?.carteira_id || undefined,
          intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1,
        }).catch(() => {})
      }
      onResult(data)
    } catch (e) {
      setErro(e.message)
      setEtapa('mapeamento')
    } finally {
      setLoadingAnalise(false)
    }
  }

  // ── Etapa 1 — lista de conexões salvas ───────────────────────
  if (etapa === 'conexao' && modo === 'lista') return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
        Bancos de dados conectados
      </p>

      {carregandoConexoes && (
        <div className="flex items-center gap-2 text-sm text-slate-400 py-4 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando conexões...
        </div>
      )}

      {conexoes.map(c => (
        <div key={c.id} className="rounded-2xl border border-slate-100 bg-white overflow-hidden shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)]">
          <div className="flex items-start gap-3 px-4 pt-4 pb-3">
            <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
              <Database className="h-4 w-4 text-blue-500" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-slate-800 text-sm leading-tight">{c.nome}</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {c.tipo?.toUpperCase()}{c.host ? ` · ${c.host}` : ''}
              </p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {c.ultimo_sync ? (
                  <span className="text-xs text-emerald-600 font-medium">
                    Sync {fmtRelativo(c.ultimo_sync)}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">Nunca sincronizado</span>
                )}
                {c.intervalo_sync_horas && (
                  <span className="text-xs text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full">
                    {INTERVALOS_SYNC.find(o => o.value === Number(c.intervalo_sync_horas))?.label ?? `${c.intervalo_sync_horas}h`}
                  </span>
                )}
              </div>
            </div>
            {!isOperador && (
              <button onClick={(e) => removerConexaoSalva(c.id, e)} className="text-slate-300 hover:text-red-400 transition-colors shrink-0">
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="px-4 pb-4 flex gap-2">
            <button
              onClick={(e) => sincronizarConexaoSalva(c.id, e)}
              disabled={sincronizandoId !== null}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-colors
                ${sincronizandoId === c.id
                  ? 'bg-blue-100 text-blue-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'}`}
            >
              <RefreshCw className={`h-4 w-4 ${sincronizandoId === c.id ? 'animate-spin' : ''}`} />
              {sincronizandoId === c.id ? 'Sincronizando...' : 'Sincronizar com o banco de dados'}
            </button>
            {!isOperador && (
              <button
                onClick={() => carregarConexaoSalva(c)}
                className="px-3 py-2.5 rounded-lg text-xs text-slate-500 border border-slate-200 hover:bg-slate-50 transition-colors whitespace-nowrap"
              >
                Editar
              </button>
            )}
          </div>
        </div>
      ))}

      {syncMsg && (
        <div className={`flex items-center gap-2 p-3 rounded-2xl text-sm border ${
          syncMsg.tipo === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-red-50 text-red-600 border-red-100'
        }`}>
          {syncMsg.tipo === 'ok' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {syncMsg.texto}
        </div>
      )}

      {!isOperador && (
        <button
          onClick={() => {
            setModo('nova')
            setConexaoSalvaId(null)
            setForm({ tipo: 'postgres', host: '', porta: '', banco: '', usuario: '', senha: '', query: 'SELECT * FROM devedores', nome_fonte: '', intervalo_sync_horas: 1 })
            setErro(null)
          }}
          className="w-full py-3 rounded-2xl border-2 border-dashed border-slate-200 text-sm text-slate-500 hover:border-blue-300 hover:text-blue-600 flex items-center justify-center gap-2 transition-colors"
        >
          <Plug className="h-4 w-4" />
          Conectar um novo banco de dados
        </button>
      )}

      {isOperador && conexoes.length === 0 && !carregandoConexoes && (
        <p className="text-sm text-slate-400 text-center py-4">Nenhuma conexão disponível para você ainda. Solicite acesso ao administrador.</p>
      )}
    </div>
  )

  // ── Etapa 1 — formulário de nova conexão ou edição (apenas admin/comando) ──
  if (etapa === 'conexao' && isOperador) return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Bancos de dados conectados</p>
      {carregandoConexoes && <div className="flex items-center gap-2 text-sm text-slate-400 py-4 justify-center"><Loader2 className="h-4 w-4 animate-spin" /> Carregando...</div>}
      {!carregandoConexoes && conexoes.length === 0 && (
        <p className="text-sm text-slate-400 text-center py-4">Nenhuma conexão disponível. Solicite acesso ao administrador.</p>
      )}
    </div>
  )

  if (etapa === 'conexao') return (
    <div className="space-y-4">
      {conexoes.length > 0 && (
        <button
          onClick={() => { setModo('lista'); setConexaoSalvaId(null); setErro(null) }}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors"
        >
          ← Bancos salvos
        </button>
      )}

      {/* Nome da conexão em destaque — primeiro campo */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        {conexaoSalvaId ? (
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-blue-500 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-blue-700">Editando conexão</p>
              <p className="text-sm font-semibold text-slate-800 mt-0.5">{form.nome_fonte}</p>
            </div>
          </div>
        ) : (
          <>
            <label className="block text-xs font-semibold text-blue-700 mb-1">
              Nome da conexão *
            </label>
            <input
              value={form.nome_fonte}
              onChange={e => set('nome_fonte', e.target.value)}
              placeholder="ex: banco_principal, clientes_producao..."
              autoComplete="off"
              className="w-full border border-blue-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <p className="text-xs text-blue-500 mt-1.5">
              Identifica esta conexão. Depois de salva, basta clicar em <strong>Sincronizar</strong> para atualizar os dados sem preencher nada novamente.
            </p>
          </>
        )}
      </div>

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
        <label className="block text-xs font-medium text-slate-500 mb-1">Atualização automática</label>
        <select
          value={form.intervalo_sync_horas}
          onChange={e => set('intervalo_sync_horas', Number(e.target.value))}
          className={inp()}
        >
          {INTERVALOS_SYNC.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <p className="text-xs text-slate-400 mt-1">
          O sistema relê seu banco automaticamente neste intervalo — qualquer pagamento ou alteração reflete sem intervenção manual.
        </p>
      </div>

      {erro && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}

      <button onClick={conectar} disabled={loadingConexao}
        className={`w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all active:scale-[0.97]
          ${loadingConexao ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'text-white active:scale-[0.97]'}`}
        style={loadingConexao ? {} : { background: 'linear-gradient(135deg,#1d4ed8,#2563eb)', boxShadow: '0 1px 2px rgba(29,78,216,0.2),0 4px 12px rgba(29,78,216,0.15)' }}
      >
        {loadingConexao
          ? <><Loader2 className="h-4 w-4 animate-spin" /> Conectando...</>
          : <><Plug className="h-4 w-4" /> Conectar</>}
      </button>
    </div>
  )

  // ── Etapa 1.5: seleção de tabela ─────────────────────────
  if (etapa === 'tabelas') return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-100 rounded-xl">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
        <span className="text-sm font-medium text-emerald-800">
          Conectado! {tabelas.length} tabelas encontradas.
        </span>
        <button onClick={() => setEtapa('conexao')} className="ml-auto text-xs text-slate-400 hover:text-slate-600 underline">
          Voltar
        </button>
      </div>

      {conexaoSalvaId ? (
        <div className="flex items-center gap-1.5 text-xs text-emerald-600 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-100">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> Conexão salva — será atualizada após a análise.
        </div>
      ) : form.nome_fonte.trim() ? (
        <div className="flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 px-3 py-2 rounded-lg border border-blue-100">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Conexão será salva como <strong className="ml-1">"{form.nome_fonte}"</strong> automaticamente após a análise.
        </div>
      ) : null}

      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
        Selecione a tabela com os devedores
      </p>

      {loadingTeste && (
        <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando colunas...
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
        {tabelas.map(t => (
          <button key={t} onClick={() => selecionarTabela(t)} disabled={loadingTeste}
            className="text-left px-3 py-2.5 rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50 text-sm text-slate-700 transition-colors disabled:opacity-50 font-mono truncate"
          >
            {t}
          </button>
        ))}
      </div>

      {erro && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}
    </div>
  )

  // ── Etapa 2: mapeamento de colunas ────────────────────────
  if (etapa === 'mapeamento') return (
    <div className="space-y-4">
      {/* Status da conexão */}
      <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-100 rounded-xl">
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

      {!conexaoSalvaId && (
        (form.nome_fonte.trim() || nomeParaSalvar.trim()) ? (
          <div className="flex items-center gap-2 p-3 rounded-xl text-xs bg-blue-50 border border-blue-100 text-blue-700">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            Conexão será salva como <strong className="ml-1">"{form.nome_fonte.trim() || nomeParaSalvar.trim()}"</strong> automaticamente ao analisar.
          </div>
        ) : (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-100 space-y-2">
            <p className="text-xs font-semibold text-amber-700">Quer salvar esta conexão para reutilizar depois?</p>
            <input value={nomeParaSalvar} onChange={e => setNomeParaSalvar(e.target.value)}
              placeholder="Nome da conexão (ex: banco_principal)..."
              className="w-full border border-amber-200 rounded-lg px-3 py-1.5 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-amber-300" />
            <p className="text-xs text-amber-600">Preenchendo aqui, a conexão é salva automaticamente ao clicar em Analisar carteira.</p>
          </div>
        )
      )}

      {erro && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}

      <button onClick={analisar} disabled={loadingAnalise}
        className="btn-primary w-full py-3 disabled:opacity-50"
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
      {!conexaoSalvaId && form.nome_fonte.trim() && (
        <p className="text-xs text-blue-500">Salvando conexão "{form.nome_fonte}" automaticamente...</p>
      )}
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
  const [histLimit, setHistLimit] = useState(10)
  const [abrindo, setAbrindo]   = useState(null)
  const [empresaAlvo, setEmpresaAlvo] = useState('')
  const [listaEmpresas, setListaEmpresas] = useState([])
  const inputRef = useRef()
  const navigate = useNavigate()
  const { setResult } = useAnalysis()
  const { token, isOperador, isAdmin, isComando } = useAuth()

  useEffect(() => {
    listarCarteiras()
      .then(setHistorico)
      .catch(() => {})
      .finally(() => setHistLoading(false))
  }, [])

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token)
      .then(d => setListaEmpresas(d.empresas || []))
      .catch(() => {})
  }, [isComando, token])

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
    if (isComando && !empresaAlvo) { setError('Selecione a empresa cliente antes de analisar.'); return }
    setLoading(true)
    setError(null)
    try {
      const data = await analisarCarteira(file, isComando ? empresaAlvo : null)
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
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {(isAdmin || isComando || isOperador) && (
        <button
          onClick={() => navigate(isComando ? '/comando' : isAdmin ? '/admin' : '/operador')}
          className="absolute top-5 left-5 z-20 flex items-center gap-1.5 text-blue-200 hover:text-white transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" /> Início
        </button>
      )}
      {/* Hero */}
      <div className="mb-12 text-center relative z-10">
        <div className="relative inline-block mb-5">
          <div className="absolute inset-0 rounded-full blur-3xl scale-[2] opacity-25"
            style={{ background: 'radial-gradient(circle, #3b82f6, #1d4ed8)' }} />
          <div className="relative w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)', boxShadow: '0 8px 32px rgba(29,78,216,0.4), 0 2px 8px rgba(29,78,216,0.3)' }}>
            <span className="text-white text-2xl font-bold">⚖</span>
          </div>
        </div>
        <h1 className="text-4xl font-extrabold text-white tracking-tight mb-2">Mizan</h1>
        <p className="text-blue-200 text-base max-w-xs mx-auto leading-relaxed">
          Análise de carteira de crédito com inteligência artificial
        </p>
      </div>

      {/* Card */}
      <div className="w-full max-w-lg bg-white rounded-2xl border border-white/10 p-8 relative z-10"
        style={{ boxShadow: '0 16px 48px rgba(2,11,31,0.50), 0 4px 12px rgba(2,11,31,0.30)' }}>
        <h2 className="text-base font-semibold text-slate-800 mb-1">Carregar carteira</h2>
        <p className="text-sm text-slate-500 mb-5">
          Importe os dados dos devedores via arquivo ou conexão direta com banco de dados.
        </p>

        {/* Seletor de empresa (apenas COMANDO) */}
        {isComando && (
          <div className="mb-5">
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">
              Empresa cliente <span className="text-red-500">*</span>
            </label>
            <select
              value={empresaAlvo}
              onChange={e => setEmpresaAlvo(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
              <option value="">Selecione a empresa cliente...</option>
              {listaEmpresas.map(e => (
                <option key={e.empresa_id} value={e.empresa_id}>
                  {e.nome_exibicao && e.nome_exibicao !== e.empresa_id
                    ? `${e.nome_exibicao} (${e.empresa_id})`
                    : e.empresa_id}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-slate-100 rounded-xl mb-6">
          <button
            onClick={() => { setAba('arquivo'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${aba === 'arquivo' ? 'bg-white text-slate-800 shadow-[0_1px_3px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:text-slate-700'}`}
          >
            <UploadCloud className="h-4 w-4" /> Arquivo
          </button>
          <button
            onClick={() => { setAba('db'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${aba === 'db' ? 'bg-white text-slate-800 shadow-[0_1px_3px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:text-slate-700'}`}
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
                border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
                transition-all duration-200 select-none
                ${isDragging
                  ? 'border-blue-400 bg-blue-50 scale-[1.01]'
                  : file
                    ? 'border-emerald-300 bg-emerald-50'
                    : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50/50'}
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
              <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-2xl text-red-600 text-sm">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              onClick={analisar}
              disabled={!file || loading}
              className={`
                mt-5 w-full py-3 rounded-2xl font-semibold text-sm text-white
                flex items-center justify-center gap-2 transition-all duration-200
                ${!file || loading
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'active:scale-[0.98]'}
              `}
              style={(!file || loading) ? {} : { background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}
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

        {aba === 'db' && <FormDB onResult={handleDBResult} isOperador={isOperador} empresaAlvo={isComando ? empresaAlvo : ''} />}
      </div>


      {/* Histórico de análises */}
      <div className="w-full max-w-lg mt-6">
        <div className="flex items-center gap-2 mb-3">
          <History className="h-4 w-4 text-blue-300" />
          <h3 className="text-sm font-semibold text-white">Análises anteriores</h3>
        </div>

        {histLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-300" />
          </div>
        )}

        {!histLoading && historico.length === 0 && (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.35),0_2px_8px_rgba(2,11,31,0.20)] p-8">
            <div className="text-center mb-8">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">⚖</span>
              </div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">Bem-vindo ao Mizan</h3>
              <p className="text-sm text-slate-500">Siga os passos abaixo para começar a recuperar valor da sua carteira</p>
            </div>
            <div className="grid grid-cols-4 gap-4">
              {[
                {
                  num: '1', cor: 'blue', titulo: 'Importe sua carteira',
                  desc: 'Faça upload de um CSV/Excel ou conecte diretamente ao seu banco de dados.',
                  icon: '📂',
                },
                {
                  num: '2', cor: 'indigo', titulo: 'IA analisa e ranqueia',
                  desc: 'O modelo de ML classifica cada devedor por probabilidade de pagamento.',
                  icon: '🤖',
                },
                {
                  num: '3', cor: 'emerald', titulo: 'Defina sua estratégia',
                  desc: 'Simule preços de compra de carteira e veja o retorno esperado da operação.',
                  icon: '📊',
                },
                {
                  num: '4', cor: 'amber', titulo: 'Registre os resultados',
                  desc: 'A cada contato registrado, a IA aprende e melhora as recomendações.',
                  icon: '🎯',
                },
              ].map(({ num, cor, titulo, desc, icon }) => {
                const borda = { blue: 'border-blue-100 bg-blue-50', indigo: 'border-indigo-100 bg-indigo-50', emerald: 'border-emerald-100 bg-emerald-50', amber: 'border-amber-100 bg-amber-50' }[cor]
                const badge = { blue: 'bg-blue-600', indigo: 'bg-indigo-600', emerald: 'bg-emerald-600', amber: 'bg-amber-500' }[cor]
                return (
                  <div key={num} className={`rounded-xl border p-4 ${borda}`}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`w-5 h-5 rounded-full ${badge} text-white text-xs font-bold flex items-center justify-center shrink-0`}>{num}</span>
                      <span className="text-lg">{icon}</span>
                    </div>
                    <p className="text-xs font-semibold text-slate-700 mb-1">{titulo}</p>
                    <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
                  </div>
                )
              })}
            </div>
            <p className="text-center text-xs text-slate-400 mt-6">
              Comece carregando um arquivo acima — CSV ou Excel com CPF, valor da dívida e dias em atraso são suficientes.
            </p>
          </div>
        )}

        {!histLoading && historico.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_32px_rgba(2,11,31,0.30),0_2px_6px_rgba(2,11,31,0.15)] divide-y divide-slate-50 overflow-hidden">
            {historico.slice(0, histLimit).map((c) => (
              <div key={c.id} className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors">
                <FileText className="h-4 w-4 text-slate-300 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{c.nome_arquivo}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {c.updated_at
                      ? <>Atualizado {fmtDate(c.updated_at)}</>
                      : fmtDate(c.created_at)
                    } · {fmtNum(c.total_devedores)} devedores · score médio {c.score_medio?.toFixed(1)}
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
            {historico.length > histLimit && (
              <button
                onClick={() => setHistLimit(l => l + 10)}
                className="w-full py-3 text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Ver mais ({historico.length - histLimit} restantes)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
