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
  { value: 0.25, label: 'A cada 15 min' },
  { value: 1,    label: 'A cada 1h'     },
  { value: 4,    label: 'A cada 4h'     },
  { value: 24,   label: 'A cada 24h'    },
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

const INP_DARK = {
  background: '#0a1220',
  border: '1px solid rgba(255,255,255,0.10)',
  color: 'white',
}

function inp(cls = '') {
  return `w-full rounded-xl px-3.5 py-2.5 text-sm focus:outline-none transition-all ${cls}`
}

function FormDB({ onResult, isOperador = false, empresaAlvo = '' }) {
  const [etapa, setEtapa]       = useState('conexao')
  const [form, setForm]         = useState({
    tipo: 'postgres', host: '', porta: '', banco: '',
    usuario: '', senha: '', query: 'SELECT * FROM devedores', nome_fonte: '',
    intervalo_sync_horas: 1, coluna_writeback: '', valor_pago: 'pago', valor_nao_pago: '',
  })
  const [teste, setTeste]       = useState(null)
  const [mapa, setMapa]         = useState({})
  const [tabelas, setTabelas]   = useState([])
  const [loadingConexao, setLoadingConexao] = useState(false)
  const [loadingTeste, setLoadingTeste]     = useState(false)
  const [loadingAnalise, setLoadingAnalise] = useState(false)
  const [erro, setErro]         = useState(null)

  const [conexoes,        setConexoes]        = useState([])
  const [nomeParaSalvar,  setNomeParaSalvar]  = useState('')
  const [salvandoConexao, setSalvandoConexao] = useState(false)
  const [conexaoSalvaId,  setConexaoSalvaId]  = useState(null)
  const [sincronizandoId, setSincronizandoId] = useState(null)
  const [syncMsg,         setSyncMsg]         = useState(null)
  const [modo,            setModo]            = useState('lista')
  const [carregandoConexoes, setCarregandoConexoes] = useState(true)

  useEffect(() => {
    setCarregandoConexoes(true)
    listarConexoes()
      .then(data => { setConexoes(data); setModo(data.length === 0 ? 'nova' : 'lista') })
      .catch(() => { setModo('nova') })
      .finally(() => setCarregandoConexoes(false))
  }, [])

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setErro(null) }
  const isSQLite    = form.tipo === 'sqlite'
  const isSheets    = form.tipo === 'sheets'
  const isSQLServer = form.tipo === 'sqlserver'
  const isOracle    = form.tipo === 'oracle'
  const tipoInfo    = DB_TIPOS.find(t => t.value === form.tipo)

  function paramsConexao() {
    if (isSheets) {
      let creds = null
      try { creds = form.sheets_credenciais ? JSON.parse(form.sheets_credenciais) : null } catch {}
      return { tipo: 'sheets', sheets_id: form.sheets_id || null, sheets_aba: form.sheets_aba || null, sheets_credenciais: creds, nome_fonte: form.nome_fonte || 'google_sheets', query: null, conexao_id: conexaoSalvaId || null }
    }
    return {
      tipo: form.tipo, host: isSQLite ? null : (form.host || null),
      porta: isSQLite ? null : (form.porta ? Number(form.porta) : tipoInfo?.portaPadrao),
      banco: form.banco || null, usuario: isSQLite ? null : (form.usuario || null),
      senha: isSQLite ? null : (form.senha || null),
      instance_name: isSQLServer ? (form.instance_name || null) : null,
      service_name: isOracle ? (form.service_name || null) : null,
      query: form.query, nome_fonte: form.nome_fonte || `db_${form.tipo}`, conexao_id: conexaoSalvaId || null,
    }
  }

  function carregarConexaoSalva(c) {
    setForm({ tipo: c.tipo, host: c.host || '', porta: c.porta || '', banco: c.banco || '', usuario: c.usuario || '', senha: c.senha || '', query: c.query || 'SELECT * FROM devedores', nome_fonte: c.nome || '', instance_name: c.instance_name || '', service_name: c.service_name || '', sheets_id: c.sheets_id || '', sheets_aba: c.sheets_aba || '', sheets_credenciais: '', intervalo_sync_horas: c.intervalo_sync_horas ?? 1, coluna_writeback: c.coluna_writeback || '', valor_pago: c.valor_pago || 'pago', valor_nao_pago: c.valor_nao_pago || '' })
    setConexaoSalvaId(c.id); setNomeParaSalvar(''); setEtapa('conexao'); setModo('nova'); setErro(null)
  }

  async function salvarConexaoAtual() {
    const nome = (nomeParaSalvar || form.nome_fonte || '').trim()
    if (!nome) return
    setSalvandoConexao(true)
    try {
      const dados = { nome, tipo: form.tipo, host: form.host || null, porta: form.porta ? Number(form.porta) : null, banco: form.banco || null, usuario: form.usuario || null, senha: form.senha || null, instance_name: form.instance_name || null, service_name: form.service_name || null, sheets_id: form.sheets_id || null, sheets_aba: form.sheets_aba || null, query: isSheets ? null : (form.query || null), mapeamento: Object.keys(mapa).length > 0 ? mapa : undefined, empresa_id: empresaAlvo || undefined, intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1, coluna_writeback: form.coluna_writeback || null, valor_pago: form.valor_pago || 'pago', valor_nao_pago: form.valor_nao_pago || null }
      const res = await salvarConexao(dados)
      setConexoes(prev => [res.conexao, ...prev]); setConexaoSalvaId(res.conexao.id); setNomeParaSalvar('')
    } catch (e) { setErro(`Erro ao salvar conexão: ${e.message}`) } finally { setSalvandoConexao(false) }
  }

  async function removerConexaoSalva(id, e) {
    e.stopPropagation()
    try { await deletarConexao(id); setConexoes(prev => prev.filter(c => c.id !== id)); if (conexaoSalvaId === id) setConexaoSalvaId(null) } catch {}
  }

  async function sincronizarConexaoSalva(id, e) {
    e.stopPropagation(); setSincronizandoId(id); setSyncMsg(null)
    try {
      const r = await sincronizarConexao(id)
      setSyncMsg({ tipo: 'ok', texto: `Sincronizado: ${r.n_devedores} devedores importados.` })
      setConexoes(prev => prev.map(c => c.id === id ? { ...c, ultimo_sync: new Date().toISOString() } : c))
      onResult(r.carteira)
    } catch (err) { setSyncMsg({ tipo: 'erro', texto: err.message }) } finally { setSincronizandoId(null) }
  }

  async function conectar() {
    setLoadingConexao(true); setErro(null)
    if (isSheets) {
      if (!form.sheets_id) { setErro('Informe o ID da planilha.'); setLoadingConexao(false); return }
      try { const res = await testarDB(paramsConexao()); setTeste(res); setMapa(res.mapeamento_sugerido); setEtapa('mapeamento') }
      catch (e) { setErro(e.message) } finally { setLoadingConexao(false) }; return
    }
    try {
      const res = await listarTabelas({ tipo: form.tipo, host: form.host || null, porta: form.porta ? Number(form.porta) : null, banco: form.banco || null, usuario: form.usuario || null, senha: form.senha || null, instance_name: isSQLServer ? (form.instance_name || null) : null, service_name: isOracle ? (form.service_name || null) : null, query: 'SELECT 1', conexao_id: conexaoSalvaId || null })
      setTabelas(res.tabelas); setEtapa('tabelas')
    } catch (e) { setErro(e.message) } finally { setLoadingConexao(false) }
  }

  async function selecionarTabela(tabela) {
    const query = `SELECT * FROM ${tabela}`
    setForm(f => ({ ...f, query })); setLoadingTeste(true); setErro(null)
    try { const res = await testarDB({ ...paramsConexao(), query }); setTeste(res); setMapa(res.mapeamento_sugerido); setEtapa('mapeamento') }
    catch (e) { setErro(e.message); setEtapa('tabelas') } finally { setLoadingTeste(false) }
  }

  async function testar() {
    if (!isSheets && !form.query.trim()) { setErro('Informe uma consulta SQL.'); return }
    if (isSheets && !form.sheets_id) { setErro('Informe o ID da planilha.'); return }
    setLoadingTeste(true); setErro(null)
    try { const res = await testarDB(paramsConexao()); setTeste(res); setMapa(res.mapeamento_sugerido); setEtapa('mapeamento') }
    catch (e) { setErro(e.message) } finally { setLoadingTeste(false) }
  }

  async function analisar() {
    const faltando = CAMPOS_MIZAN.filter(c => c.obrigatorio && !mapa[c.key])
    if (faltando.length) { setErro(`Mapeie os campos obrigatórios: ${faltando.map(c => c.label).join(', ')}`); return }
    setLoadingAnalise(true); setEtapa('analisando'); setErro(null)
    let savedId = conexaoSalvaId
    if (!savedId) {
      const autoNome = `${form.tipo.toUpperCase()} · ${(form.host || '').split('.')[0] || form.banco || 'banco'}`
      const nomeEfetivo = form.nome_fonte.trim() || nomeParaSalvar.trim() || autoNome
      try {
        const res = await salvarConexao({ nome: nomeEfetivo, tipo: form.tipo, host: form.host || null, porta: form.porta ? Number(form.porta) : null, banco: form.banco || null, usuario: form.usuario || null, senha: form.senha || null, instance_name: form.instance_name || null, service_name: form.service_name || null, sheets_id: form.sheets_id || null, sheets_aba: form.sheets_aba || null, query: isSheets ? null : (form.query || null), mapeamento: mapa, intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1, coluna_writeback: form.coluna_writeback || null, valor_pago: form.valor_pago || 'pago', valor_nao_pago: form.valor_nao_pago || null })
        savedId = res.conexao.id; setConexoes(prev => [res.conexao, ...prev]); setConexaoSalvaId(savedId); setModo('lista')
      } catch (saveErr) { setErro(`Erro ao salvar conexão: ${saveErr.message}`); setEtapa('mapeamento'); setLoadingAnalise(false); return }
    }
    try {
      const data = await analisarDB({ ...paramsConexao(), mapeamento: mapa, conexao_id: savedId, empresa_id_alvo: empresaAlvo || undefined })
      if (savedId) { atualizarConexao(savedId, { mapeamento: mapa, query: form.query, carteira_id: data.resumo?.carteira_id || undefined, intervalo_sync_horas: Number(form.intervalo_sync_horas) || 1, coluna_writeback: form.coluna_writeback || null, valor_pago: form.valor_pago || 'pago', valor_nao_pago: form.valor_nao_pago || null }).catch(() => {}) }
      onResult(data)
    } catch (e) { setErro(e.message); setEtapa('mapeamento') } finally { setLoadingAnalise(false) }
  }

  const cardStyle = { background: '#0d1628', border: '1px solid rgba(255,255,255,0.07)', boxShadow: '0 8px 32px rgba(0,0,0,0.40)' }

  // ── Lista de conexões salvas ──
  if (etapa === 'conexao' && modo === 'lista') return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#5a7499' }}>Bancos de dados conectados</p>
      {carregandoConexoes && (
        <div className="flex items-center gap-2 text-sm py-4 justify-center" style={{ color: '#5a7499' }}>
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando conexões...
        </div>
      )}
      {conexoes.map(c => (
        <div key={c.id} className="rounded-2xl overflow-hidden" style={cardStyle}>
          <div className="flex items-start gap-3 px-4 pt-4 pb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'rgba(29,106,255,0.12)' }}>
              <Database className="h-4 w-4 text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-white text-sm leading-tight">{c.nome}</p>
              <p className="text-xs mt-0.5" style={{ color: '#5a7499' }}>{c.tipo?.toUpperCase()}{c.host ? ` · ${c.host}` : ''}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {c.ultimo_sync
                  ? <span className="text-xs text-emerald-400 font-medium">Sync {fmtRelativo(c.ultimo_sync)}</span>
                  : <span className="text-xs" style={{ color: '#3d5270' }}>Nunca sincronizado</span>}
                {c.intervalo_sync_horas && (
                  <span className="text-xs text-blue-400 px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(29,106,255,0.10)' }}>
                    {INTERVALOS_SYNC.find(o => o.value === Number(c.intervalo_sync_horas))?.label ?? `${c.intervalo_sync_horas}h`}
                  </span>
                )}
              </div>
            </div>
            {!isOperador && (
              <button onClick={(e) => removerConexaoSalva(c.id, e)} className="transition-colors shrink-0" style={{ color: '#3d5270' }}
                onMouseOver={e => e.currentTarget.style.color = '#f87171'}
                onMouseOut={e => e.currentTarget.style.color = '#3d5270'}>
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="px-4 pb-4 flex gap-2">
            <button onClick={(e) => sincronizarConexaoSalva(c.id, e)} disabled={sincronizandoId !== null}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-colors ${sincronizandoId === c.id ? 'opacity-60 cursor-not-allowed' : ''}`}
              style={{ background: sincronizandoId === c.id ? 'rgba(29,106,255,0.10)' : 'rgba(29,106,255,0.20)', color: '#60a5fa', border: '1px solid rgba(29,106,255,0.25)' }}>
              <RefreshCw className={`h-4 w-4 ${sincronizandoId === c.id ? 'animate-spin' : ''}`} />
              {sincronizandoId === c.id ? 'Sincronizando...' : 'Sincronizar com o banco de dados'}
            </button>
            {!isOperador && (
              <button onClick={() => carregarConexaoSalva(c)}
                className="px-3 py-2.5 rounded-lg text-xs transition-colors whitespace-nowrap"
                style={{ color: '#8fa3c8', border: '1px solid rgba(255,255,255,0.08)' }}
                onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                Editar
              </button>
            )}
          </div>
        </div>
      ))}
      {syncMsg && (
        <div className={`flex items-center gap-2 p-3 rounded-2xl text-sm ${syncMsg.tipo === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}
          style={{ background: syncMsg.tipo === 'ok' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)', border: `1px solid ${syncMsg.tipo === 'ok' ? 'rgba(16,185,129,0.20)' : 'rgba(239,68,68,0.18)'}` }}>
          {syncMsg.tipo === 'ok' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {syncMsg.texto}
        </div>
      )}
      {!isOperador && (
        <button onClick={() => { setModo('nova'); setConexaoSalvaId(null); setForm({ tipo: 'postgres', host: '', porta: '', banco: '', usuario: '', senha: '', query: 'SELECT * FROM devedores', nome_fonte: '', intervalo_sync_horas: 1, coluna_writeback: '', valor_pago: 'pago', valor_nao_pago: '' }); setErro(null) }}
          className="w-full py-3 rounded-2xl border-2 border-dashed text-sm flex items-center justify-center gap-2 transition-colors"
          style={{ borderColor: 'rgba(255,255,255,0.10)', color: '#5a7499' }}
          onMouseOver={e => { e.currentTarget.style.borderColor = 'rgba(29,106,255,0.40)'; e.currentTarget.style.color = '#60a5fa' }}
          onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.10)'; e.currentTarget.style.color = '#5a7499' }}>
          <Plug className="h-4 w-4" /> Conectar um novo banco de dados
        </button>
      )}
      {isOperador && conexoes.length === 0 && !carregandoConexoes && (
        <p className="text-sm text-center py-4" style={{ color: '#5a7499' }}>Nenhuma conexão disponível para você ainda. Solicite acesso ao administrador.</p>
      )}
    </div>
  )

  // ── Operador sem conexões ──
  if (etapa === 'conexao' && isOperador) return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#5a7499' }}>Bancos de dados conectados</p>
      {carregandoConexoes && <div className="flex items-center gap-2 text-sm py-4 justify-center" style={{ color: '#5a7499' }}><Loader2 className="h-4 w-4 animate-spin" /> Carregando...</div>}
      {!carregandoConexoes && conexoes.length === 0 && <p className="text-sm text-center py-4" style={{ color: '#5a7499' }}>Nenhuma conexão disponível. Solicite acesso ao administrador.</p>}
    </div>
  )

  // ── Formulário de nova conexão ──
  if (etapa === 'conexao') return (
    <div className="space-y-4">
      {conexoes.length > 0 && (
        <button onClick={() => { setModo('lista'); setConexaoSalvaId(null); setErro(null) }}
          className="flex items-center gap-1.5 text-sm transition-colors" style={{ color: '#5a7499' }}
          onMouseOver={e => e.currentTarget.style.color = '#8fa3c8'} onMouseOut={e => e.currentTarget.style.color = '#5a7499'}>
          ← Bancos salvos
        </button>
      )}
      <div className="rounded-xl p-4" style={{ background: 'rgba(29,106,255,0.08)', border: '1px solid rgba(29,106,255,0.20)' }}>
        {conexaoSalvaId ? (
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-blue-400 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-blue-400">Editando conexão</p>
              <p className="text-sm font-semibold text-white mt-0.5">{form.nome_fonte}</p>
            </div>
          </div>
        ) : (
          <>
            <label className="block text-xs font-semibold text-blue-400 mb-1">Nome da conexão *</label>
            <input value={form.nome_fonte} onChange={e => set('nome_fonte', e.target.value)} placeholder="ex: banco_principal, clientes_producao..." autoComplete="off"
              className={inp()} style={{ ...INP_DARK, borderColor: 'rgba(29,106,255,0.30)' }} />
            <p className="text-xs text-blue-400/60 mt-1.5">Identifica esta conexão. Depois de salva, basta clicar em <strong>Sincronizar</strong> para atualizar os dados sem preencher nada novamente.</p>
          </>
        )}
      </div>
      <div>
        <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Tipo de banco</label>
        <select value={form.tipo} onChange={e => set('tipo', e.target.value)} className={inp()} style={INP_DARK}>
          {DB_TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      {isSheets && (<>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>ID da planilha</label>
          <input value={form.sheets_id || ''} onChange={e => set('sheets_id', e.target.value)} placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms" className={inp()} style={INP_DARK} />
          <p className="text-xs mt-1" style={{ color: '#5a7499' }}>Encontre o ID na URL da planilha: docs.google.com/spreadsheets/d/<strong>ID</strong>/edit</p>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Nome da aba (opcional)</label>
          <input value={form.sheets_aba || ''} onChange={e => set('sheets_aba', e.target.value)} placeholder="Planilha1" className={inp()} style={INP_DARK} />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Credenciais da Service Account (JSON)</label>
          <textarea value={form.sheets_credenciais || ''} onChange={e => set('sheets_credenciais', e.target.value)} rows={4} placeholder='{"type":"service_account","project_id":"..."}' className={`${inp()} font-mono text-xs resize-none`} style={INP_DARK} />
        </div>
      </>)}
      {!isSQLite && !isSheets && (
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Host</label>
            <input value={form.host} onChange={e => set('host', e.target.value)} placeholder="localhost" className={inp()} style={INP_DARK} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Porta</label>
            <input value={form.porta} onChange={e => set('porta', e.target.value)} placeholder={String(tipoInfo?.portaPadrao ?? '')} type="number" className={inp()} style={INP_DARK} />
          </div>
        </div>
      )}
      {isSQLServer && (
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Instance Name (opcional)</label>
          <input value={form.instance_name || ''} onChange={e => set('instance_name', e.target.value)} placeholder="SQLEXPRESS" className={inp()} style={INP_DARK} />
        </div>
      )}
      {!isSheets && (
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>{isSQLite ? 'Caminho do arquivo (.db)' : isOracle ? 'Service Name / SID' : 'Nome do banco'}</label>
          <input value={form.banco} onChange={e => set('banco', e.target.value)} placeholder={isSQLite ? '/caminho/banco.db' : isOracle ? 'ORCL' : 'nome_do_banco'} className={inp()} style={INP_DARK} />
        </div>
      )}
      {!isSQLite && !isSheets && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Usuário</label>
            <input value={form.usuario} onChange={e => set('usuario', e.target.value)} className={inp()} style={INP_DARK} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Senha</label>
            <input type="password" value={form.senha} onChange={e => set('senha', e.target.value)} className={inp()} style={INP_DARK} />
          </div>
        </div>
      )}
      {!isSheets && (
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Consulta SQL</label>
          <textarea value={form.query} onChange={e => set('query', e.target.value)} rows={3} className={`${inp()} font-mono resize-none`} style={INP_DARK} />
          <p className="text-xs mt-1" style={{ color: '#5a7499' }}>Apenas SELECT. O sistema detecta as colunas automaticamente.</p>
        </div>
      )}
      <div>
        <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Atualização automática</label>
        <select value={form.intervalo_sync_horas} onChange={e => set('intervalo_sync_horas', Number(e.target.value))} className={inp()} style={INP_DARK}>
          {INTERVALOS_SYNC.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <p className="text-xs mt-1" style={{ color: '#5a7499' }}>O sistema relê seu banco automaticamente neste intervalo — qualquer pagamento ou alteração reflete sem intervenção manual.</p>
      </div>
      <div className="rounded-xl p-4 space-y-3" style={{ border: '1px dashed rgba(255,255,255,0.10)' }}>
        <p className="text-xs font-semibold text-white">Gravar pagamentos de volta no banco (opcional)</p>
        <p className="text-xs leading-relaxed" style={{ color: '#5a7499' }}>Quando alguém registrar um pagamento manualmente no Mizan, o sistema atualiza automaticamente a coluna correspondente no seu banco externo.</p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Coluna de status</label>
            <input value={form.coluna_writeback || ''} onChange={e => set('coluna_writeback', e.target.value)} placeholder="ex: status, situacao, pagou" className={inp()} style={INP_DARK} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Valor quando pago</label>
            <input value={form.valor_pago || ''} onChange={e => set('valor_pago', e.target.value)} placeholder="ex: pago, sim, 1" className={inp()} style={INP_DARK} />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: '#8fa3c8' }}>Valor quando não pago <span style={{ color: '#3d5270' }}>(opcional — deixe vazio para não alterar)</span></label>
          <input value={form.valor_nao_pago || ''} onChange={e => set('valor_nao_pago', e.target.value)} placeholder="ex: inadimplente, nao, 0" className={inp()} style={INP_DARK} />
        </div>
      </div>
      {erro && (
        <div className="flex items-start gap-2 p-3 rounded-xl text-red-400 text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)' }}>
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span>
        </div>
      )}
      <button onClick={conectar} disabled={loadingConexao}
        className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all active:scale-[0.97] text-white disabled:opacity-50"
        style={{ background: loadingConexao ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: loadingConexao ? 'none' : '0 4px 16px rgba(29,106,255,0.25)' }}>
        {loadingConexao ? <><Loader2 className="h-4 w-4 animate-spin" /> Conectando...</> : <><Plug className="h-4 w-4" /> Conectar</>}
      </button>
    </div>
  )

  // ── Seleção de tabela ──
  if (etapa === 'tabelas') return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 rounded-xl text-emerald-400" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.20)' }}>
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        <span className="text-sm font-medium">Conectado! {tabelas.length} tabelas encontradas.</span>
        <button onClick={() => setEtapa('conexao')} className="ml-auto text-xs underline" style={{ color: '#5a7499' }}>Voltar</button>
      </div>
      {conexaoSalvaId ? (
        <div className="flex items-center gap-1.5 text-xs text-emerald-400 px-3 py-2 rounded-lg" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)' }}>
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> Conexão salva — será atualizada após a análise.
        </div>
      ) : form.nome_fonte.trim() ? (
        <div className="flex items-center gap-1.5 text-xs text-blue-400 px-3 py-2 rounded-lg" style={{ background: 'rgba(29,106,255,0.08)', border: '1px solid rgba(29,106,255,0.15)' }}>
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Conexão será salva como <strong className="ml-1">"{form.nome_fonte}"</strong> automaticamente após a análise.
        </div>
      ) : null}
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#5a7499' }}>Selecione a tabela com os devedores</p>
      {loadingTeste && <div className="flex items-center gap-2 text-sm py-2" style={{ color: '#8fa3c8' }}><Loader2 className="h-4 w-4 animate-spin" /> Carregando colunas...</div>}
      <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
        {tabelas.map(t => (
          <button key={t} onClick={() => selecionarTabela(t)} disabled={loadingTeste}
            className="text-left px-3 py-2.5 rounded-xl text-sm font-mono truncate transition-colors disabled:opacity-50"
            style={{ border: '1px solid rgba(255,255,255,0.08)', color: '#8fa3c8' }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'rgba(29,106,255,0.40)'; e.currentTarget.style.background = 'rgba(29,106,255,0.08)'; e.currentTarget.style.color = 'white' }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#8fa3c8' }}>
            {t}
          </button>
        ))}
      </div>
      {erro && <div className="flex items-start gap-2 p-3 rounded-xl text-red-400 text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)' }}><AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span></div>}
    </div>
  )

  // ── Mapeamento de colunas ──
  if (etapa === 'mapeamento') return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 rounded-xl text-emerald-400" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.20)' }}>
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        <div className="text-sm"><span className="font-medium">Conectado com sucesso.</span> <span style={{ color: '#8fa3c8' }}>{teste.total_colunas} colunas encontradas.</span></div>
        <button onClick={() => { setEtapa('conexao'); setTeste(null) }} className="ml-auto text-xs underline" style={{ color: '#5a7499' }}>Voltar</button>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: '#5a7499' }}>Mapeamento de colunas</p>
        <div className="space-y-2">
          {CAMPOS_MIZAN.map(campo => {
            const mapeado = !!mapa[campo.key]
            return (
              <div key={campo.key} className="grid grid-cols-2 gap-2 items-center">
                <div className="flex items-center gap-1.5">
                  {mapeado ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    : campo.obrigatorio ? <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                    : <div className="h-3.5 w-3.5 rounded-full border-2 shrink-0" style={{ borderColor: 'rgba(255,255,255,0.15)' }} />}
                  <span className={`text-xs font-medium ${mapeado ? 'text-white' : campo.obrigatorio ? 'text-red-400' : ''}`} style={!mapeado && !campo.obrigatorio ? { color: '#5a7499' } : {}}>
                    {campo.label}{campo.obrigatorio && <span className="text-red-400 ml-0.5">*</span>}
                  </span>
                </div>
                <select value={mapa[campo.key] || ''} onChange={e => setMapa(m => ({ ...m, [campo.key]: e.target.value || undefined }))}
                  className="text-xs rounded-lg px-2 py-1.5 focus:outline-none"
                  style={mapeado ? { background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.20)', color: '#34d399' }
                    : campo.obrigatorio ? { background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.20)', color: '#f87171' }
                    : { ...INP_DARK }}>
                  <option value="">{campo.obrigatorio ? '— selecionar —' : `— padrão: ${campo.hint} —`}</option>
                  {teste.colunas.map(col => <option key={col} value={col}>{col}</option>)}
                </select>
              </div>
            )
          })}
        </div>
        <p className="text-xs mt-2" style={{ color: '#3d5270' }}>* Obrigatório. Campos sem mapeamento usam valores padrão.</p>
      </div>
      {teste.preview?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: '#5a7499' }}>Preview (primeiras {teste.preview.length} linhas)</p>
          <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
            <table className="text-xs w-full">
              <thead className="border-b" style={{ background: '#111d34', borderColor: 'rgba(255,255,255,0.08)' }}>
                <tr>
                  {teste.colunas.map(col => (
                    <th key={col} className="px-3 py-2 text-left font-medium whitespace-nowrap" style={{ color: '#5a7499' }}>
                      {col}
                      {Object.entries(mapa).find(([, v]) => v === col) && <span className="ml-1 text-emerald-400">→ {Object.entries(mapa).find(([, v]) => v === col)[0]}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {teste.preview.map((row, i) => (
                  <tr key={i} className="border-b" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                    {teste.colunas.map(col => <td key={col} className="px-3 py-1.5 whitespace-nowrap max-w-[120px] truncate" style={{ color: '#8fa3c8' }}>{row[col] ?? '—'}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {!conexaoSalvaId && (
        (form.nome_fonte.trim() || nomeParaSalvar.trim()) ? (
          <div className="flex items-center gap-2 p-3 rounded-xl text-xs text-blue-400" style={{ background: 'rgba(29,106,255,0.08)', border: '1px solid rgba(29,106,255,0.15)' }}>
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            Conexão será salva como <strong className="ml-1">"{form.nome_fonte.trim() || nomeParaSalvar.trim()}"</strong> automaticamente ao analisar.
          </div>
        ) : (
          <div className="p-3 rounded-xl space-y-2" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.20)' }}>
            <p className="text-xs font-semibold text-amber-400">Quer salvar esta conexão para reutilizar depois?</p>
            <input value={nomeParaSalvar} onChange={e => setNomeParaSalvar(e.target.value)} placeholder="Nome da conexão (ex: banco_principal)..."
              className="w-full rounded-lg px-3 py-1.5 text-xs focus:outline-none" style={{ background: '#0a1220', border: '1px solid rgba(245,158,11,0.25)', color: 'white' }} />
            <p className="text-xs text-amber-500/60">Preenchendo aqui, a conexão é salva automaticamente ao clicar em Analisar carteira.</p>
          </div>
        )
      )}
      {erro && <div className="flex items-start gap-2 p-3 rounded-xl text-red-400 text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)' }}><AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{erro}</span></div>}
      <button onClick={analisar} disabled={loadingAnalise} className="btn-primary w-full py-3 disabled:opacity-50">
        <ChevronRight className="h-4 w-4" /> Analisar carteira
      </button>
    </div>
  )

  // ── Analisando ──
  return (
    <div className="flex flex-col items-center justify-center py-10 gap-3" style={{ color: '#8fa3c8' }}>
      <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
      <p className="text-sm font-medium text-white">Carregando e analisando dados...</p>
      <p className="text-xs" style={{ color: '#5a7499' }}>Isso pode levar alguns segundos dependendo do volume.</p>
      {!conexaoSalvaId && form.nome_fonte.trim() && <p className="text-xs text-blue-400">Salvando conexão "{form.nome_fonte}" automaticamente...</p>}
    </div>
  )
}

export default function Upload() {
  const [aba, setAba]           = useState('arquivo')
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
    listarCarteiras().then(setHistorico).catch(() => {}).finally(() => setHistLoading(false))
  }, [])

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setListaEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  const abrirCarteira = async (id) => {
    if (abrindo) return
    setAbrindo(id)
    try { const data = await carregarCarteira(id); setResult(data); navigate('/dashboard') }
    catch (e) { setError(`Erro ao abrir carteira: ${e.message}`) } finally { setAbrindo(null) }
  }

  const handleFile = (f) => {
    if (!f) return
    const nome = f.name.toLowerCase()
    if (!nome.endsWith('.csv') && !nome.endsWith('.xlsx') && !nome.endsWith('.xls')) { setError('Apenas arquivos .csv ou .xlsx são aceitos.'); return }
    setError(null); setFile(f)
  }

  const onDrop = useCallback((e) => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files[0]) }, [])
  const onDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const onDragLeave = (e) => { e.preventDefault(); setIsDragging(false) }

  const analisar = async () => {
    if (!file || loading) return
    if (isComando && !empresaAlvo) { setError('Selecione a empresa cliente antes de analisar.'); return }
    setLoading(true); setError(null)
    try { const data = await analisarCarteira(file, isComando ? empresaAlvo : null); setResult(data); navigate('/dashboard') }
    catch (e) { setError(e.message); setLoading(false) }
  }

  const handleDBResult = (data) => { setResult(data); navigate('/dashboard') }
  const fmtSize = (bytes) => bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  const CARD_STYLE = { background: '#0d1628', border: '1px solid rgba(255,255,255,0.07)', boxShadow: '0 16px 48px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.30)' }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {(isAdmin || isComando || isOperador) && (
        <button onClick={() => navigate(isComando ? '/comando' : isAdmin ? '/admin' : '/operador')}
          className="absolute top-5 left-5 z-20 flex items-center gap-1.5 text-sm font-medium transition-colors text-blue-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> Início
        </button>
      )}

      {/* Hero */}
      <div className="mb-12 text-center relative z-10">
        <div className="relative inline-block mb-5">
          <div className="absolute inset-0 rounded-full blur-3xl scale-[2] opacity-20"
            style={{ background: 'radial-gradient(circle, #1d6aff, #1557f0)' }} />
          <div className="relative w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 8px 32px rgba(29,106,255,0.40), 0 2px 8px rgba(29,106,255,0.30)' }}>
            <span className="text-white text-2xl font-bold">⚖</span>
          </div>
        </div>
        <h1 className="text-4xl font-extrabold text-white tracking-tight mb-2">Mizan</h1>
        <p className="text-base max-w-xs mx-auto leading-relaxed" style={{ color: '#8fa3c8' }}>
          Análise de carteira de crédito com inteligência artificial
        </p>
      </div>

      {/* Card principal */}
      <div className="w-full max-w-lg rounded-2xl p-8 relative z-10" style={CARD_STYLE}>
        <h2 className="text-base font-semibold text-white mb-1">Carregar carteira</h2>
        <p className="text-sm mb-5" style={{ color: '#8fa3c8' }}>
          Importe os dados dos devedores via arquivo ou conexão direta com banco de dados.
        </p>

        {/* Seletor empresa COMANDO */}
        {isComando && (
          <div className="mb-5">
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#8fa3c8' }}>
              Empresa cliente <span className="text-red-400">*</span>
            </label>
            <select value={empresaAlvo} onChange={e => setEmpresaAlvo(e.target.value)}
              className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none"
              style={{ background: '#0a1220', border: '1px solid rgba(255,255,255,0.10)', color: empresaAlvo ? 'white' : '#4a6080' }}>
              <option value="">Selecione a empresa cliente...</option>
              {listaEmpresas.map(e => (
                <option key={e.empresa_id} value={e.empresa_id}>
                  {e.nome_exibicao && e.nome_exibicao !== e.empresa_id ? `${e.nome_exibicao} (${e.empresa_id})` : e.empresa_id}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 p-1 rounded-xl mb-6" style={{ background: 'rgba(255,255,255,0.05)' }}>
          <button onClick={() => { setAba('arquivo'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${aba === 'arquivo' ? 'text-white' : ''}`}
            style={aba === 'arquivo' ? { background: '#0d1628', color: 'white', boxShadow: '0 1px 4px rgba(0,0,0,0.30)' } : { color: '#5a7499' }}>
            <UploadCloud className="h-4 w-4" /> Arquivo
          </button>
          <button onClick={() => { setAba('db'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all`}
            style={aba === 'db' ? { background: '#0d1628', color: 'white', boxShadow: '0 1px 4px rgba(0,0,0,0.30)' } : { color: '#5a7499' }}>
            <Database className="h-4 w-4" /> Banco de Dados
          </button>
        </div>

        {aba === 'arquivo' && (
          <>
            <div role="button" tabIndex={0}
              onClick={() => inputRef.current.click()}
              onKeyDown={(e) => e.key === 'Enter' && inputRef.current.click()}
              onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
              className="border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 select-none"
              style={isDragging
                ? { borderColor: '#1d6aff', background: 'rgba(29,106,255,0.08)' }
                : file
                  ? { borderColor: 'rgba(16,185,129,0.40)', background: 'rgba(16,185,129,0.05)' }
                  : { borderColor: 'rgba(255,255,255,0.10)' }}
              onMouseOver={e => { if (!isDragging && !file) e.currentTarget.style.borderColor = 'rgba(29,106,255,0.40)' }}
              onMouseOut={e => { if (!isDragging && !file) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.10)' }}>
              <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(e) => handleFile(e.target.files[0])} />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <FileText className="h-10 w-10 text-emerald-400" />
                  <p className="font-semibold text-white">{file.name}</p>
                  <p className="text-sm" style={{ color: '#8fa3c8' }}>{fmtSize(file.size)}</p>
                  <p className="text-xs text-blue-400 mt-1">Clique para trocar o arquivo</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <UploadCloud className={`h-10 w-10 transition-colors ${isDragging ? 'text-blue-400' : ''}`} style={{ color: isDragging ? '#60a5fa' : '#3d5270' }} />
                  <div>
                    <p className="font-medium" style={{ color: '#8fa3c8' }}>Arraste o arquivo aqui</p>
                    <p className="text-sm mt-0.5" style={{ color: '#5a7499' }}>ou clique para selecionar</p>
                  </div>
                  <p className="text-xs mt-1" style={{ color: '#3d5270' }}>CSV ou Excel (.xlsx)</p>
                </div>
              )}
            </div>
            {error && (
              <div className="mt-4 flex items-start gap-2 p-3 rounded-2xl text-red-400 text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)' }}>
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{error}</span>
              </div>
            )}
            <button onClick={analisar} disabled={!file || loading}
              className="mt-5 w-full py-3 rounded-2xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50"
              style={(!file || loading) ? { background: 'rgba(255,255,255,0.06)' } : { background: 'linear-gradient(135deg,#1d6aff,#1557f0)', boxShadow: '0 4px 16px rgba(29,106,255,0.25)' }}>
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Analisando carteira...</> : 'Analisar carteira'}
            </button>
            <p className="mt-4 text-center text-xs" style={{ color: '#3d5270' }}>
              Colunas esperadas: cpf, nome, produto, status, uf, valor_divida, renda_estimada, dias_em_atraso
            </p>
          </>
        )}

        {aba === 'db' && <FormDB onResult={handleDBResult} isOperador={isOperador} empresaAlvo={isComando ? empresaAlvo : ''} />}
      </div>

      {/* Histórico */}
      <div className="w-full max-w-lg mt-6">
        <div className="flex items-center gap-2 mb-3">
          <History className="h-4 w-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">Análises anteriores</h3>
        </div>

        {histLoading && <div className="flex items-center justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" style={{ color: '#3d5270' }} /></div>}

        {!histLoading && historico.length === 0 && (
          <div className="rounded-2xl p-8" style={{ background: '#0d1628', border: '1px solid rgba(255,255,255,0.07)', boxShadow: '0 8px 32px rgba(0,0,0,0.40)' }}>
            <div className="text-center mb-8">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'rgba(29,106,255,0.12)' }}>
                <span className="text-2xl">⚖</span>
              </div>
              <h3 className="text-base font-semibold text-white mb-1">Bem-vindo ao Mizan</h3>
              <p className="text-sm" style={{ color: '#8fa3c8' }}>Siga os passos abaixo para começar a recuperar valor da sua carteira</p>
            </div>
            <div className="grid grid-cols-4 gap-4">
              {[
                { num: '1', cor: 'blue',    titulo: 'Importe sua carteira',   desc: 'Faça upload de um CSV/Excel ou conecte diretamente ao seu banco de dados.', icon: '📂' },
                { num: '2', cor: 'indigo',  titulo: 'IA analisa e ranqueia',  desc: 'O modelo de ML classifica cada devedor por probabilidade de pagamento.',    icon: '🤖' },
                { num: '3', cor: 'emerald', titulo: 'Defina sua estratégia',  desc: 'Simule preços de compra de carteira e veja o retorno esperado da operação.', icon: '📊' },
                { num: '4', cor: 'amber',   titulo: 'Registre os resultados', desc: 'A cada contato registrado, a IA aprende e melhora as recomendações.',        icon: '🎯' },
              ].map(({ num, cor, titulo, desc, icon }) => {
                const colors = { blue: 'rgba(29,106,255,0.15)', indigo: 'rgba(99,102,241,0.15)', emerald: 'rgba(16,185,129,0.12)', amber: 'rgba(245,158,11,0.12)' }
                const borders = { blue: 'rgba(29,106,255,0.25)', indigo: 'rgba(99,102,241,0.25)', emerald: 'rgba(16,185,129,0.20)', amber: 'rgba(245,158,11,0.20)' }
                const badges  = { blue: '#1d6aff', indigo: '#6366f1', emerald: '#10b981', amber: '#f59e0b' }
                return (
                  <div key={num} className="rounded-xl p-4" style={{ background: colors[cor], border: `1px solid ${borders[cor]}` }}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="w-5 h-5 rounded-full text-white text-xs font-bold flex items-center justify-center shrink-0" style={{ background: badges[cor] }}>{num}</span>
                      <span className="text-lg">{icon}</span>
                    </div>
                    <p className="text-xs font-semibold text-white mb-1">{titulo}</p>
                    <p className="text-xs leading-relaxed" style={{ color: '#8fa3c8' }}>{desc}</p>
                  </div>
                )
              })}
            </div>
            <p className="text-center text-xs mt-6" style={{ color: '#3d5270' }}>
              Comece carregando um arquivo acima — CSV ou Excel com CPF, valor da dívida e dias em atraso são suficientes.
            </p>
          </div>
        )}

        {!histLoading && historico.length > 0 && (
          <div className="rounded-2xl overflow-hidden" style={{ background: '#0d1628', border: '1px solid rgba(255,255,255,0.07)', boxShadow: '0 8px 32px rgba(0,0,0,0.40)' }}>
            {historico.slice(0, histLimit).map((c) => (
              <div key={c.id} className="flex items-center gap-4 px-4 py-3 border-b transition-colors"
                style={{ borderColor: 'rgba(255,255,255,0.05)' }}
                onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                <FileText className="h-4 w-4 shrink-0" style={{ color: '#3d5270' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{c.nome_arquivo}</p>
                  <p className="text-xs mt-0.5" style={{ color: '#5a7499' }}>
                    {c.updated_at ? <>Atualizado {fmtDate(c.updated_at)}</> : fmtDate(c.created_at)}
                    {' '} · {fmtNum(c.total_devedores)} devedores · score médio {c.score_medio?.toFixed(1)}
                  </p>
                </div>
                <div className="text-right shrink-0 hidden sm:block">
                  <p className="text-xs font-semibold text-emerald-400">{fmtBRL(c.valor_esperado)}</p>
                  <p className="text-xs" style={{ color: '#5a7499' }}>esperado</p>
                </div>
                <button onClick={() => abrirCarteira(c.id)} disabled={!!abrindo}
                  className="flex items-center gap-1.5 text-xs font-medium text-blue-400 hover:text-blue-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                  style={{ background: 'rgba(29,106,255,0.10)', border: '1px solid rgba(29,106,255,0.20)' }}
                  onMouseOver={e => e.currentTarget.style.background = 'rgba(29,106,255,0.18)'}
                  onMouseOut={e => e.currentTarget.style.background = 'rgba(29,106,255,0.10)'}>
                  {abrindo === c.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderOpen className="h-3.5 w-3.5" />}
                  Abrir
                </button>
              </div>
            ))}
            {historico.length > histLimit && (
              <button onClick={() => setHistLimit(l => l + 10)}
                className="w-full py-3 text-xs transition-colors"
                style={{ color: '#5a7499' }}
                onMouseOver={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.color = '#8fa3c8' }}
                onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#5a7499' }}>
                Ver mais ({historico.length - histLimit} restantes)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
