import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { buscarAuditoria } from '../api'
import {
  Download, Loader2, Filter, RefreshCw, ChevronDown,
} from 'lucide-react'
import DicaAjuda from '../components/DicaAjuda'

const ACAO_LABEL = {
  carteira_criada:        'Carteira criada',
  carteira_sincronizada:  'Carteira atualizada',
  banco_sincronizado:     'Banco sincronizado',
  feedback_importado:     'Feedbacks importados',
  usuario_criado:         'Usuário criado',
  usuario_ativado:        'Usuário ativado',
  usuario_desativado:     'Usuário desativado',
  role_alterado:          'Permissão alterada',
  senha_alterada:         'Senha alterada',
  conexao_criada:         'Conexão criada',
  pagamento_confirmado:   'Pagamento confirmado',
  config_empresa_atualizada: 'Configuração da empresa alterada',
}

const ACAO_COR = {
  carteira_criada:       'bg-blue-500/10 text-blue-300 ring-blue-500/20',
  carteira_sincronizada: 'bg-blue-500/10 text-blue-300 ring-blue-500/20',
  banco_sincronizado:    'bg-emerald-500/10 text-emerald-300 ring-emerald-500/20',
  feedback_importado:    'bg-violet-500/10 text-violet-300 ring-violet-500/20',
  usuario_criado:        'bg-indigo-500/10 text-indigo-300 ring-indigo-500/20',
  usuario_ativado:       'bg-emerald-500/10 text-emerald-300 ring-emerald-500/20',
  usuario_desativado:    'bg-red-500/10 text-red-300 ring-red-500/20',
  role_alterado:         'bg-amber-500/10 text-amber-300 ring-amber-500/20',
  senha_alterada:        'bg-slate-500/10 text-ink-2 ring-slate-500/20',
  pagamento_confirmado:  'bg-emerald-500/10 text-emerald-300 ring-emerald-500/20',
}

function fmtData(iso) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(new Date(iso))
}

function csvEscape(v) {
  const s = v == null ? '' : String(v)
  return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function exportarCSV(linhas) {
  const cabecalho = ['data_hora', 'acao', 'entidade', 'entidade_id', 'usuario_email', 'empresa_id', 'detalhes']
  const corpo = linhas.map(l => [
    l.created_at, l.acao, l.entidade || '', l.entidade_id || '', l.usuario_email || '',
    l.empresa_id || '', l.detalhes ? JSON.stringify(l.detalhes) : '',
  ].map(csvEscape).join(';'))
  const csv = '﻿' + [cabecalho.join(';'), ...corpo].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mizan-auditoria-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const PAGE_SIZE = 100

export default function Auditoria() {
  const navigate = useNavigate()
  const { token, usuario, logout, isComando } = useAuth()

  const [linhas, setLinhas]   = useState([])
  const [loading, setLoading] = useState(true)
  const [temMais, setTemMais] = useState(false)
  const [erro, setErro]       = useState('')
  const [expandido, setExpandido] = useState(null)

  const [filtros, setFiltros] = useState({ acao: '', usuario_email: '', data_inicio: '', data_fim: '' })

  const carregar = useCallback(async (offset = 0, acumular = false) => {
    setLoading(true); setErro('')
    try {
      const params = {
        limit: PAGE_SIZE, offset,
        acao: filtros.acao || undefined,
        usuario_email: filtros.usuario_email || undefined,
        data_inicio: filtros.data_inicio ? `${filtros.data_inicio}T00:00:00` : undefined,
        data_fim: filtros.data_fim ? `${filtros.data_fim}T23:59:59` : undefined,
      }
      const dados = await buscarAuditoria(params)
      setLinhas(prev => acumular ? [...prev, ...dados] : dados)
      setTemMais(dados.length === PAGE_SIZE)
    } catch (e) {
      setErro('Erro ao carregar auditoria: ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [filtros])

  useEffect(() => { carregar(0, false) }, [carregar])

  return (
    <AppShell titulo="Auditoria">

      <div className="w-full max-w-6xl mx-auto">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-ink tracking-tight">Trilha de auditoria<DicaAjuda id="auditoria-de-acoes" /></h1>
            <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>
              Histórico de ações {isComando ? 'de toda a plataforma' : 'da sua empresa'} — compliance e rastreabilidade
            </p>
          </div>
          <button
            onClick={() => exportarCSV(linhas)}
            disabled={linhas.length === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-ink transition-colors disabled:opacity-40"
            style={{ background: 'var(--brand)' }}
          >
            <Download className="w-3.5 h-3.5" /> Exportar CSV ({linhas.length})
          </button>
        </div>

        {/* Filtros */}
        <div className="rounded-2xl p-4 mb-6 flex flex-wrap items-end gap-3" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
          <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
            <Filter className="w-3.5 h-3.5" /> Filtros
          </div>
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--ink-3)' }}>Ação</label>
            <select value={filtros.acao} onChange={e => setFiltros(f => ({ ...f, acao: e.target.value }))}
              className="input-base text-xs py-1.5 w-48">
              <option value="">Todas</option>
              {Object.entries(ACAO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {isComando && (
            <div>
              <label className="block text-[11px] mb-1" style={{ color: 'var(--ink-3)' }}>E-mail do usuário</label>
              <input type="email" value={filtros.usuario_email} onChange={e => setFiltros(f => ({ ...f, usuario_email: e.target.value }))}
                placeholder="nome@empresa.com" className="input-base text-xs py-1.5 w-52" />
            </div>
          )}
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--ink-3)' }}>De</label>
            <input type="date" value={filtros.data_inicio} onChange={e => setFiltros(f => ({ ...f, data_inicio: e.target.value }))}
              className="input-base text-xs py-1.5" />
          </div>
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--ink-3)' }}>Até</label>
            <input type="date" value={filtros.data_fim} onChange={e => setFiltros(f => ({ ...f, data_fim: e.target.value }))}
              className="input-base text-xs py-1.5" />
          </div>
          <button onClick={() => carregar(0, false)} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
            style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Aplicar
          </button>
        </div>

        {erro && <div className="mb-5 text-red-400 rounded-xl px-4 py-3 text-sm" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>{erro}</div>}

        {/* Tabela */}
        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
          {loading && linhas.length === 0 ? (
            <div className="flex items-center justify-center py-16 gap-2" style={{ color: 'var(--ink-3)' }}>
              <Loader2 className="h-5 w-5 animate-spin" /> Carregando...
            </div>
          ) : linhas.length === 0 ? (
            <div className="py-16 text-center text-sm" style={{ color: 'var(--ink-3)' }}>Nenhum registro de auditoria encontrado para esses filtros.</div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--line)' }}>
              {linhas.map(l => (
                <div key={l.id} className="px-5 py-3.5">
                  <div
                    className="flex items-center gap-3 cursor-pointer"
                    onClick={() => setExpandido(prev => prev === l.id ? null : l.id)}
                  >
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ring-1 shrink-0 ${ACAO_COR[l.acao] || 'bg-slate-500/10 text-ink-2 ring-slate-500/20'}`}>
                      {ACAO_LABEL[l.acao] || l.acao}
                    </span>
                    <span className="text-sm text-ink truncate flex-1 min-w-0">
                      {l.usuario_email || 'sistema'}
                      {l.entidade && <span style={{ color: 'var(--ink-3)' }}> · {l.entidade}{l.entidade_id ? ` (${l.entidade_id.slice(0, 12)})` : ''}</span>}
                    </span>
                    <span className="text-xs tabular-nums shrink-0" style={{ color: 'var(--ink-3)' }}>{fmtData(l.created_at)}</span>
                    {l.detalhes && <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${expandido === l.id ? 'rotate-180' : ''}`} style={{ color: 'var(--ink-4)' }} />}
                  </div>
                  {expandido === l.id && l.detalhes && (
                    <pre className="mt-2.5 text-xs rounded-lg p-3 overflow-x-auto" style={{ background: 'var(--surface-2)', color: 'var(--ink-2)', border: '1px solid var(--line)' }}>
                      {JSON.stringify(l.detalhes, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {temMais && (
          <div className="flex justify-center mt-5">
            <button onClick={() => carregar(linhas.length, true)} disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
              style={{ background: 'var(--raise-3)', color: 'var(--ink-2)' }}>
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Carregar mais
            </button>
          </div>
        )}
      </div>
    </AppShell>
  )
}
