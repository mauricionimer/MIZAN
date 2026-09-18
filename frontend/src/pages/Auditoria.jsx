import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { buscarAuditoria } from '../api'
import {
  ArrowLeft, LogOut, ShieldCheck, Download, Loader2, Filter, RefreshCw, ChevronDown,
} from 'lucide-react'
import { LogoMark } from '../components/Logo'

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
  carteira_criada:       'bg-[var(--info-soft)] text-[var(--info)] ring-[var(--info-border)]',
  carteira_sincronizada: 'bg-[var(--info-soft)] text-[var(--info)] ring-[var(--info-border)]',
  banco_sincronizado:    'bg-[var(--ok-soft)] text-[var(--ok)] ring-[var(--ok-border)]',
  feedback_importado:    'bg-[#F5F3FF] text-[#6D28D9] ring-[var(--border)]',
  usuario_criado:        'bg-[#EEF2FF] text-[#4338CA] ring-indigo-500/20',
  usuario_ativado:       'bg-[var(--ok-soft)] text-[var(--ok)] ring-[var(--ok-border)]',
  usuario_desativado:    'bg-[var(--danger-soft)] text-[var(--danger)] ring-[var(--danger-border)]',
  role_alterado:         'bg-[var(--warn-soft)] text-[var(--warn)] ring-[var(--warn-border)]',
  senha_alterada:        'bg-[var(--surface-sub)] text-[var(--text-2)] ring-[var(--border)]',
  pagamento_confirmado:  'bg-[var(--ok-soft)] text-[var(--ok)] ring-[var(--ok-border)]',
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
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(isComando ? '/comando' : '/admin')} className="p-1 rounded-lg transition-colors hover:bg-[rgba(22,32,60,0.04)]" style={{ color: 'var(--text-3)' }}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <LogoMark className="h-4 w-4 shrink-0" />
          <span className="font-semibold text-[var(--text-1)] text-sm">Mizan</span>
          <span className="text-[var(--border-hi)] text-sm">/</span>
          <span className="text-sm" style={{ color: 'var(--text-2)' }}>Auditoria</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: 'var(--text-3)' }}>{usuario?.nome}</span>
          <button onClick={logout} className="nav-link-danger"><LogOut className="w-4 h-4" /> Sair</button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-1)] tracking-tight">Trilha de auditoria</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>
              Histórico de ações {isComando ? 'de toda a plataforma' : 'da sua empresa'} — compliance e rastreabilidade
            </p>
          </div>
          <button
            onClick={() => exportarCSV(linhas)}
            disabled={linhas.length === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold text-[var(--text-1)] transition-colors disabled:opacity-40"
            style={{ background: 'var(--brand)' }}
          >
            <Download className="w-3.5 h-3.5" /> Exportar CSV ({linhas.length})
          </button>
        </div>

        {/* Filtros */}
        <div className="rounded-lg p-4 mb-6 flex flex-wrap items-end gap-3" style={{ background: 'var(--surface)', border: '1px solid rgba(22,32,60,0.10)' }}>
          <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--text-2)' }}>
            <Filter className="w-3.5 h-3.5" /> Filtros
          </div>
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--text-3)' }}>Ação</label>
            <select value={filtros.acao} onChange={e => setFiltros(f => ({ ...f, acao: e.target.value }))}
              className="input-base text-xs py-1.5 w-48">
              <option value="">Todas</option>
              {Object.entries(ACAO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {isComando && (
            <div>
              <label className="block text-[11px] mb-1" style={{ color: 'var(--text-3)' }}>E-mail do usuário</label>
              <input type="email" value={filtros.usuario_email} onChange={e => setFiltros(f => ({ ...f, usuario_email: e.target.value }))}
                placeholder="nome@empresa.com" className="input-base text-xs py-1.5 w-52" />
            </div>
          )}
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--text-3)' }}>De</label>
            <input type="date" value={filtros.data_inicio} onChange={e => setFiltros(f => ({ ...f, data_inicio: e.target.value }))}
              className="input-base text-xs py-1.5" />
          </div>
          <div>
            <label className="block text-[11px] mb-1" style={{ color: 'var(--text-3)' }}>Até</label>
            <input type="date" value={filtros.data_fim} onChange={e => setFiltros(f => ({ ...f, data_fim: e.target.value }))}
              className="input-base text-xs py-1.5" />
          </div>
          <button onClick={() => carregar(0, false)} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
            style={{ background: 'rgba(22,32,60,0.06)', color: 'var(--text-2)' }}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Aplicar
          </button>
        </div>

        {erro && <div className="mb-5 text-[var(--danger)] rounded-md px-4 py-3 text-sm" style={{ background: 'var(--danger-soft)', border: '1px solid var(--danger-border)' }}>{erro}</div>}

        {/* Tabela */}
        <div className="rounded-lg overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid rgba(22,32,60,0.10)' }}>
          {loading && linhas.length === 0 ? (
            <div className="flex items-center justify-center py-16 gap-2" style={{ color: 'var(--text-3)' }}>
              <Loader2 className="h-5 w-5 animate-spin" /> Carregando...
            </div>
          ) : linhas.length === 0 ? (
            <div className="py-16 text-center text-sm" style={{ color: 'var(--text-3)' }}>Nenhum registro de auditoria encontrado para esses filtros.</div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'rgba(22,32,60,0.06)' }}>
              {linhas.map(l => (
                <div key={l.id} className="px-5 py-3.5">
                  <div
                    className="flex items-center gap-3 cursor-pointer"
                    onClick={() => setExpandido(prev => prev === l.id ? null : l.id)}
                  >
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ring-1 shrink-0 ${ACAO_COR[l.acao] || 'bg-[var(--surface-sub)] text-[var(--text-2)] ring-[var(--border)]'}`}>
                      {ACAO_LABEL[l.acao] || l.acao}
                    </span>
                    <span className="text-sm text-[var(--text-1)] truncate flex-1 min-w-0">
                      {l.usuario_email || 'sistema'}
                      {l.entidade && <span style={{ color: 'var(--text-3)' }}> · {l.entidade}{l.entidade_id ? ` (${l.entidade_id.slice(0, 12)})` : ''}</span>}
                    </span>
                    <span className="text-xs font-mono shrink-0" style={{ color: 'var(--text-3)' }}>{fmtData(l.created_at)}</span>
                    {l.detalhes && <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${expandido === l.id ? 'rotate-180' : ''}`} style={{ color: 'var(--text-muted)' }} />}
                  </div>
                  {expandido === l.id && l.detalhes && (
                    <pre className="mt-2.5 text-xs rounded-lg p-3 overflow-x-auto" style={{ background: 'var(--surface)', color: 'var(--text-2)', border: '1px solid rgba(22,32,60,0.06)' }}>
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
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold transition-colors disabled:opacity-50"
              style={{ background: 'rgba(22,32,60,0.06)', color: 'var(--text-2)' }}>
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Carregar mais
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
