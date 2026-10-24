import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { buscarAuditoria, listarEmpresas } from '../api'
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
  pagamento_confirmado:   'Pagamento confirmado (registro antigo)',
  config_empresa_atualizada: 'Configuração da empresa alterada',
  // Demais ações que o servidor registra (backend/main.py, _registrar_auditoria).
  confirmar_pagamento:    'Pagamento confirmado',
  parcela_paga:           'Parcela paga',
  oferta_desfeita:        'Oferta desfeita',
  ofertas_atualizadas:    'Ofertas alteradas',
  premissas_atualizadas:  'Política de cobrança alterada',
  politica_agente_alterada: 'Regras dos agentes alteradas',
  fila_distribuida:       'Fila distribuída',
  responsavel_alterado:   'Responsável alterado',
  agenda_atribuida:       'Atendimento atribuído',
  agenda_reaberta:        'Compromisso reaberto',
  fluxo_fase_definida:    'Fase do devedor definida',
  passagem_retorno:       'Resumo do Supervisor avaliado',
  recomendacao_gerada:    'Recomendação gerada',
  tarefa_administrativa_criada:   'Demanda administrativa criada',
  tarefa_administrativa_concluida: 'Demanda administrativa concluída',
  disponibilidade_criada:   'Disponibilidade criada',
  disponibilidade_editada:  'Disponibilidade alterada',
  disponibilidade_removida: 'Disponibilidade removida',
  usuario_movido_para_empresa: 'Usuário movido de empresa',
  usuario_removido_da_empresa: 'Usuário removido da empresa',
  conta_excluida:         'Conta excluída',
  dominios_atualizados:   'Domínios atualizados',
  foto_empresa_atualizada: 'Logo da empresa alterado',
  empresa_esvaziada:      'Empresa excluída',
  chave_api_criada:       'Chave de API criada',
  chave_api_revogada:     'Chave de API revogada',
  duvida_respondida:      'Dúvida respondida',
  duvida_publicada_faq:   'Dúvida publicada na Ajuda',
  duvida_sugerida_para_ajuda: 'Dúvida sugerida para a Ajuda',
  lacuna_tratada:         'Lacuna da Ajuda tratada',
  lacunas_limpas:         'Lacunas da Ajuda limpas',
  modelo_treinado:        'Modelo treinado',
  modelo_promovido:       'Modelo promovido',
  modelo_ativado:         'Modelo ativado',
  modelo_desativado:      'Modelo desativado',
  bandit_zerado:          'Aprendizado das ofertas reiniciado',
  retencao_executada:     'Limpeza por retenção executada',
  titular_eliminado:      'Dados do titular eliminados (LGPD)',
}
// Código novo, ainda sem nome aqui: vira frase ("lacuna_reaberta" → "Lacuna reaberta"), nunca o código cru.
const nomeDaAcao = (acao) => ACAO_LABEL[acao] || (acao ? (acao.charAt(0).toUpperCase() + acao.slice(1)).replace(/_/g, ' ') : '—')

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

// Detalhe da auditoria em texto, não em código: "n_devedores" vira "Devedores".
const ROTULOS_DETALHE = {
  n_devedores: 'Devedores', cpf_final: 'CPF (final)', valor_recuperado: 'Valor recuperado', email_alvo: 'Usuário',
  role: 'Papel', nova_role: 'Novo papel', email_novo: 'E-mail', rotulo: 'Rótulo', dias: 'Prazo (dias)',
  anonimizadas: 'Registros anonimizados', forcado: 'Forçado', versao: 'Versão', antes: 'Antes', depois: 'Depois',
}
const rotuloDetalhe = k => ROTULOS_DETALHE[k] || (k.charAt(0).toUpperCase() + k.slice(1)).replace(/_/g, ' ')
function textoDetalhe(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'Sim' : 'Não'
  if (Array.isArray(v)) return v.length ? v.map(textoDetalhe).join(', ') : '—'
  if (typeof v === 'object') return Object.entries(v).map(([k, x]) => `${rotuloDetalhe(k)}: ${textoDetalhe(x)}`).join(' · ')
  return String(v)
}

export default function Auditoria() {
  const navigate = useNavigate()
  const { token, usuario, logout, isComando } = useAuth()

  const [linhas, setLinhas]   = useState([])
  const [loading, setLoading] = useState(true)
  const [temMais, setTemMais] = useState(false)
  const [erro, setErro]       = useState('')
  const [expandido, setExpandido] = useState(null)

  const [filtros, setFiltros] = useState({ acao: '', usuario_email: '', data_inicio: '', data_fim: '', empresa_id: '' })

  // COMANDO vê a auditoria de todas as empresas: o seletor separa por empresa.
  // Admin não precisa: o servidor já filtra pela empresa dele.
  const [empresas, setEmpresas] = useState([])
  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])
  const nomeEmpresa = (id) => {
    const e = empresas.find(x => x.empresa_id === id)
    return e?.nome_exibicao || e?.nome || id
  }

  const carregar = useCallback(async (offset = 0, acumular = false) => {
    setLoading(true); setErro('')
    try {
      const params = {
        limit: PAGE_SIZE, offset,
        acao: filtros.acao || undefined,
        usuario_email: filtros.usuario_email || undefined,
        empresa_id: isComando ? (filtros.empresa_id || undefined) : undefined,
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
  }, [filtros, isComando])

  useEffect(() => { carregar(0, false) }, [carregar])

  return (
    <AppShell titulo="Auditoria">

      <div className="w-full max-w-6xl mx-auto">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-ink tracking-tight">Trilha de auditoria<DicaAjuda id="auditoria-de-acoes" /></h1>
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
              {Object.entries(ACAO_LABEL).sort((a, b) => a[1].localeCompare(b[1], 'pt-BR')).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {isComando && (
            <div>
              <label className="block text-[11px] mb-1" style={{ color: 'var(--ink-3)' }}>Empresa</label>
              <select value={filtros.empresa_id} onChange={e => setFiltros(f => ({ ...f, empresa_id: e.target.value }))}
                className="input-base text-xs py-1.5 w-48">
                <option value="">Todas as empresas</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{nomeEmpresa(e.empresa_id)}</option>)}
                <option value="_plataforma">Plataforma (sem empresa)</option>
              </select>
            </div>
          )}
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
                      {nomeDaAcao(l.acao)}
                    </span>
                    {isComando && (
                      <span className="text-[11px] px-2 py-0.5 rounded-full shrink-0"
                        style={{ background: 'var(--raise-2)', color: 'var(--ink-2)' }}>
                        {l.empresa_id ? nomeEmpresa(l.empresa_id) : 'Plataforma'}
                      </span>
                    )}
                    <span className="text-sm text-ink truncate flex-1 min-w-0">
                      {l.usuario_email || 'sistema'}
                      {l.entidade && <span style={{ color: 'var(--ink-3)' }}> · {l.entidade}{l.entidade_id ? ` (${l.entidade_id.slice(0, 12)})` : ''}</span>}
                    </span>
                    <span className="text-xs tabular-nums shrink-0" style={{ color: 'var(--ink-3)' }}>{fmtData(l.created_at)}</span>
                    {l.detalhes && <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${expandido === l.id ? 'rotate-180' : ''}`} style={{ color: 'var(--ink-4)' }} />}
                  </div>
                  {expandido === l.id && l.detalhes && (
                    <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-lg p-3 text-xs" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }}>
                      {Object.entries(l.detalhes).map(([k, v]) => (
                        <div key={k} className="contents">
                          <dt style={{ color: 'var(--ink-3)' }}>{rotuloDetalhe(k)}</dt>
                          <dd className="min-w-0 break-words text-ink-2">{textoDetalhe(v)}</dd>
                        </div>
                      ))}
                    </dl>
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
