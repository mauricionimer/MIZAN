import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import { useAuth } from '../context/AuthContext'
import { buscarAuditoria, listarEmpresas } from '../api'
import {
  Download, Loader2, ChevronDown, ScrollText } from 'lucide-react'

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

const PERIODOS = [['0', 'Hoje'], ['7', '7 dias'], ['30', '30 dias'], ['tudo', 'Tudo'], ['escolher', 'Escolher…']]
// Data local (aaaa-mm-dd) de N dias atrás; 0 = hoje.
function diaMenos(n) {
  const d = new Date(); d.setDate(d.getDate() - n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function Auditoria() {
  const navigate = useNavigate()
  const { token, usuario, logout, isComando } = useAuth()

  const [linhas, setLinhas]   = useState([])
  const [loading, setLoading] = useState(true)
  const [temMais, setTemMais] = useState(false)
  const [erro, setErro]       = useState('')
  const [expandido, setExpandido] = useState(null)

  const [filtros, setFiltros] = useState({ acao: '', usuario_email: '', data_inicio: diaMenos(30), data_fim: '', empresa_id: '' })
  const [periodo, setPeriodo] = useState('30')
  const escolherPeriodo = (k) => {
    setPeriodo(k)
    if (k === 'escolher') return
    setFiltros(f => ({ ...f, data_inicio: k === 'tudo' ? '' : diaMenos(Number(k)), data_fim: '' }))
  }

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
        <CabecalhoPagina rotulo="Configurações" icone={ScrollText} titulo="Auditoria" ajuda="auditoria-de-acoes"
          subtitulo="Tudo o que foi feito na conta, por quem e quando.">
          <button type="button" onClick={() => exportarCSV(linhas)} disabled={linhas.length === 0} className="btn-secondary">
            <Download className="h-4 w-4" aria-hidden="true" /> Exportar CSV ({linhas.length})
          </button>
        </CabecalhoPagina>

        {/* Filtros: ação e período em pílulas (canvas). Mudar um filtro já recarrega. */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <select value={filtros.acao} onChange={e => setFiltros(f => ({ ...f, acao: e.target.value }))} aria-label="Ação"
            className="input-base h-11 w-full rounded-[12px] px-3.5 sm:w-60">
            <option value="">Todas as ações</option>
            {Object.entries(ACAO_LABEL).sort((a, b) => a[1].localeCompare(b[1], 'pt-BR')).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {isComando && (
            <select value={filtros.empresa_id} onChange={e => setFiltros(f => ({ ...f, empresa_id: e.target.value }))} aria-label="Empresa"
              className="input-base h-11 w-full rounded-[12px] px-3.5 sm:w-56">
              <option value="">Todas as empresas</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{nomeEmpresa(e.empresa_id)}</option>)}
              <option value="_plataforma">Plataforma (sem empresa)</option>
            </select>
          )}
          {isComando && (
            <input type="email" value={filtros.usuario_email} onChange={e => setFiltros(f => ({ ...f, usuario_email: e.target.value }))}
              placeholder="E-mail de quem fez" aria-label="E-mail do usuário" className="input-base h-11 w-full rounded-[12px] px-3.5 sm:w-56" />
          )}
          <div className="flex max-w-full gap-1 overflow-x-auto rounded-[14px] border border-line bg-surface p-1" role="tablist" aria-label="Período">
            {PERIODOS.map(([k, l]) => (
              <button key={k} type="button" role="tab" aria-selected={periodo === k} onClick={() => escolherPeriodo(k)}
                className={`h-9 whitespace-nowrap rounded-[10px] px-3.5 text-sm transition-colors ${periodo === k ? 'bg-[var(--raised)] font-semibold text-ink' : 'text-ink-2 hover:text-ink'}`}>
                {l}
              </button>
            ))}
          </div>
          {periodo === 'escolher' && (
            <div className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
              <label className="flex items-center gap-2">De
                <input type="date" value={filtros.data_inicio} onChange={e => setFiltros(f => ({ ...f, data_inicio: e.target.value }))}
                  className="input-base h-11 w-auto rounded-[12px] px-3" /></label>
              <label className="flex items-center gap-2">até
                <input type="date" value={filtros.data_fim} onChange={e => setFiltros(f => ({ ...f, data_fim: e.target.value }))}
                  className="input-base h-11 w-auto rounded-[12px] px-3" /></label>
            </div>
          )}
          {loading && linhas.length > 0 && <Loader2 className="h-4 w-4 animate-spin text-ink-3" aria-label="Atualizando" />}
        </div>

        {erro && (
          <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[14px] border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-ink">
            {erro}
            <button type="button" onClick={() => carregar(0, false)} className="btn-secondary btn-sm">Tentar de novo</button>
          </div>
        )}

        <div className="overflow-hidden rounded-[22px] border border-line bg-surface">
          {loading && linhas.length === 0 ? (
            <div className="flex items-center justify-center gap-2 py-16 text-ink-3">
              <Loader2 className="h-5 w-5 animate-spin" /> Carregando…
            </div>
          ) : linhas.length === 0 ? (
            <div className="py-16 text-center text-sm text-ink-3">Nenhum registro de auditoria encontrado para esses filtros.</div>
          ) : (
            <ul className="divide-y divide-line">
              {linhas.map(l => {
                const aberto = expandido === l.id
                const perigo = (ACAO_COR[l.acao] || '').includes('red')
                return (
                  <li key={l.id}>
                    <button type="button" onClick={() => setExpandido(prev => prev === l.id ? null : l.id)} aria-expanded={aberto}
                      className={`grid w-full items-center gap-x-4 gap-y-1 px-6 py-3.5 text-left transition-colors hover:bg-raise-1 sm:grid-cols-[230px_minmax(0,1fr)_auto_16px] ${aberto ? 'bg-raise-1' : ''}`}>
                      <span className={`flex min-w-0 items-center gap-2 text-sm font-semibold ${perigo ? 'text-[var(--danger)]' : 'text-ink'}`}>
                        <span className="truncate">{nomeDaAcao(l.acao)}</span>
                        {isComando && (
                          <span className="shrink-0 rounded-full bg-raise-2 px-2 py-0.5 text-[11px] font-medium text-ink-2">
                            {l.empresa_id ? nomeEmpresa(l.empresa_id) : 'Plataforma'}
                          </span>
                        )}
                      </span>
                      <span className="min-w-0 truncate text-sm text-ink-2">
                        {l.usuario_email || 'sistema'}{l.entidade && <span className="text-ink-3"> · {l.entidade}</span>}
                      </span>
                      <span className="whitespace-nowrap text-xs tabular-nums text-ink-3">{fmtData(l.created_at)}</span>
                      <ChevronDown className={`hidden h-4 w-4 text-ink-3 transition-transform sm:block ${aberto ? 'rotate-180' : ''}`} aria-hidden="true" />
                    </button>
                    {aberto && (
                      <dl className="mx-6 mb-4 grid grid-cols-[minmax(0,140px)_minmax(0,1fr)] gap-x-4 gap-y-1.5 rounded-[14px] border border-line bg-[var(--sunken)] px-4 py-3 text-[13px]">
                        {l.detalhes && Object.entries(l.detalhes).map(([k, v]) => (
                          <div key={k} className="contents">
                            <dt className="text-ink-3">{rotuloDetalhe(k)}</dt>
                            <dd className="min-w-0 break-words text-ink">{textoDetalhe(v)}</dd>
                          </div>
                        ))}
                        <dt className="text-ink-3">E-mail</dt><dd className="min-w-0 break-words text-ink">{l.usuario_email || 'sistema'}</dd>
                        {l.entidade_id && <><dt className="text-ink-3">Identificador</dt><dd className="min-w-0 break-all font-mono text-xs text-ink-2">{l.entidade_id}</dd></>}
                      </dl>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {temMais && (
          <div className="flex justify-center mt-5">
            <button onClick={() => carregar(linhas.length, true)} disabled={loading}
              className="btn-secondary">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Carregar mais
            </button>
          </div>
        )}
      </div>
    </AppShell>
  )
}
