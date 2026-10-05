import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle2, XCircle, Loader2, ClipboardList, Plus, Trash2, UploadCloud, FileText, Download, Search, X,
} from 'lucide-react'
import { feedbackLote, buscarDevedores, listarEmpresas } from '../api'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { LogoMark } from '../components/Logo'
import DicaAjuda from '../components/DicaAjuda'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const EMPTY = {
  cpf: '', pagou: 'sim', valor_recuperado: '', data_pagamento: '',
  canal_cobranca: '', forma_pagamento: '', modalidade: 'a_vista', parcelas: '2', com_juros: false, taxa_juros_mensal: '', desconto_pct: '',
}

const FORMAS = [
  ['pix', 'Pix'], ['boleto', 'Boleto'], ['cartao_credito', 'Cartão de crédito'], ['cartao_debito', 'Cartão de débito'],
  ['transferencia', 'Transferência'], ['debito_automatico', 'Débito automático'], ['dinheiro', 'Dinheiro'], ['outro', 'Outro'],
]
const NOME_FORMA = Object.fromEntries(FORMAS)

// Por onde a cobrança chegou ao devedor (vale para pagou e para não pagou).
const CANAIS = [
  ['whatsapp', 'WhatsApp'], ['telefone', 'Ligação'], ['sms', 'SMS'], ['email', 'E-mail'], ['carta', 'Carta'],
  ['presencial', 'Presencial (agência)'], ['escritorio', 'Escritório de cobrança'], ['portal', 'App / site do banco'],
  ['espontaneo', 'Devedor procurou sozinho'], ['outro', 'Outro'],
]
const NOME_CANAL = Object.fromEntries(CANAIS)

const fmtCPF = (c) => {
  const d = String(c || '').replace(/\D/g, '')
  return d.length === 11 ? d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4') : c
}
const fmtData = (iso) => { try { return new Date(iso).toLocaleDateString('pt-BR') } catch { return '' } }

/**
 * Busca o devedor por nome ou CPF nas carteiras da empresa e devolve o escolhido
 * (com a carteira). Assim o pagamento fica ligado à carteira certa, e não só ao CPF.
 */
function BuscaDevedor({ escolhido, onEscolher, empresaAlvo, exigeEmpresa }) {
  const [texto, setTexto] = useState('')
  const [itens, setItens] = useState([])
  const [aberto, setAberto] = useState(false)
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState('')
  const caixa = useRef(null)

  useEffect(() => {
    const fechar = (e) => { if (caixa.current && !caixa.current.contains(e.target)) setAberto(false) }
    document.addEventListener('mousedown', fechar)
    return () => document.removeEventListener('mousedown', fechar)
  }, [])

  useEffect(() => {
    const q = texto.trim()
    if (q.length < 2 || (exigeEmpresa && !empresaAlvo)) { setItens([]); setErro(''); return }
    let cancelado = false
    const t = setTimeout(() => {
      setBuscando(true); setErro('')
      buscarDevedores(q, empresaAlvo)
        .then(d => { if (!cancelado) { setItens(d.itens || []); setAberto(true) } })
        .catch(e => { if (!cancelado) { setItens([]); setErro(e.message) } })
        .finally(() => { if (!cancelado) setBuscando(false) })
    }, 300)
    return () => { cancelado = true; clearTimeout(t) }
  }, [texto, empresaAlvo, exigeEmpresa])

  if (escolhido) {
    return (
      <div className="flex items-start justify-between gap-3 rounded-xl px-4 py-3"
        style={{ background: 'rgb(var(--c-royal) / 0.08)', border: '1px solid rgb(var(--c-royal) / 0.25)' }}>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink truncate">{escolhido.nome || 'Sem nome'}</p>
          <p className="text-xs tabular-nums mt-0.5" style={{ color: 'var(--ink-2)' }}>
            {fmtCPF(escolhido.cpf)} · {escolhido.produto || '—'}
            {escolhido.valor_divida != null && <> · {fmtBRL(escolhido.valor_divida)}</>}
          </p>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--ink-3)' }}>
            Carteira: {escolhido.carteira_nome || '—'}{escolhido.carteira_data && <> · {fmtData(escolhido.carteira_data)}</>}
          </p>
        </div>
        <button type="button" onClick={() => onEscolher(null)} aria-label="Trocar devedor"
          className="shrink-0 rounded-md p-1 text-ink-3 hover:bg-raise-2 hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div ref={caixa} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-4" />
        <input type="text" value={texto} onChange={e => setTexto(e.target.value)} onFocus={() => itens.length && setAberto(true)}
          placeholder={exigeEmpresa && !empresaAlvo ? 'Escolha a empresa primeiro' : 'Nome ou CPF do devedor'}
          disabled={exigeEmpresa && !empresaAlvo}
          className="input-base pl-10" autoComplete="off" />
        {buscando && <Loader2 className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ink-4" />}
      </div>
      {erro && <p className="mt-1.5 text-xs text-red-400">{erro}</p>}
      {aberto && texto.trim().length >= 2 && !buscando && (
        <div className="absolute z-30 mt-1.5 w-full max-h-80 overflow-y-auto rounded-xl shadow-xl"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--line-2)' }}>
          {itens.length === 0 ? (
            <p className="px-4 py-3 text-xs" style={{ color: 'var(--ink-3)' }}>
              Nenhum devedor com esse nome ou CPF nas carteiras da empresa.
            </p>
          ) : itens.map(d => (
            <button key={`${d.id}`} type="button"
              onClick={() => { onEscolher(d); setTexto(''); setItens([]); setAberto(false) }}
              className="block w-full px-4 py-2.5 text-left hover:bg-raise-2 border-b border-line last:border-0">
              <p className="text-sm font-medium text-ink truncate">{d.nome || 'Sem nome'}</p>
              <p className="text-xs tabular-nums" style={{ color: 'var(--ink-2)' }}>
                {fmtCPF(d.cpf)} · {d.produto || '—'}{d.valor_divida != null && <> · {fmtBRL(d.valor_divida)}</>}
                {d.dias_em_atraso != null && <> · {d.dias_em_atraso} dias</>}
              </p>
              <p className="text-[11px]" style={{ color: 'var(--ink-3)' }}>
                Carteira: {d.carteira_nome || '—'}{d.carteira_data && <> · {fmtData(d.carteira_data)}</>}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Logo() {
  return <LogoMark className="h-5 w-5 shrink-0" />
}

function StatusBadge({ ok }) {
  return ok
    ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-300 bg-emerald-500/10 ring-1 ring-emerald-500/20 rounded-full px-2.5 py-0.5"><CheckCircle2 className="h-3.5 w-3.5" /> Registrado</span>
    : <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-300 bg-red-500/10 ring-1 ring-red-500/20 rounded-full px-2.5 py-0.5"><XCircle className="h-3.5 w-3.5" /> Erro</span>
}

function baixarTemplate() {
  const csv = 'cpf;pagou;valor_recuperado;data_pagamento\n12345678901;sim;1500.00;2026-05-19\n98765432100;nao;;'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'template_feedbacks.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

function ImportacaoLote({ token }) {
  const inputRef              = useRef()
  const [file, setFile]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [erro, setErro]       = useState('')
  const [isDragging, setIsDragging] = useState(false)

  function handleFile(f) {
    if (!f) return
    const nome = f.name.toLowerCase()
    if (!nome.endsWith('.csv') && !nome.endsWith('.xlsx') && !nome.endsWith('.xls')) {
      setErro('Apenas CSV ou Excel.'); return
    }
    setFile(f); setErro(''); setResultado(null)
  }

  async function importar() {
    if (!file) return
    setLoading(true); setErro(''); setResultado(null)
    try {
      const res = await feedbackLote(file, token)
      setResultado(res)
      setFile(null)
    } catch (e) {
      setErro(e.message)
    } finally {
      setLoading(false)
    }
  }

  const erros = resultado?.detalhes?.filter(d => !d.ok) ?? []

  return (
    <div className="lg:col-span-5 space-y-5">
      <div className="rounded-2xl p-5 flex gap-4 items-start" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
        <FileText className="h-5 w-5 shrink-0 mt-0.5" style={{ color: 'var(--ink-3)' }} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-ink mb-1">Formato esperado do arquivo</p>
          <p className="text-xs mb-3 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
            Colunas obrigatórias: <code className="bg-raise-3 border border-line text-ink rounded px-1 tabular-nums">cpf</code> e{' '}
            <code className="bg-raise-3 border border-line text-ink rounded px-1 tabular-nums">pagou</code> (sim/não ou 1/0).
            {' '}Opcionais: <code className="bg-raise-3 border border-line text-ink rounded px-1 tabular-nums">valor_recuperado</code>,{' '}
            <code className="bg-raise-3 border border-line text-ink rounded px-1 tabular-nums">data_pagamento</code>.
          </p>
          <button onClick={baixarTemplate}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-300 hover:text-blue-200 bg-blue-500/10 hover:bg-blue-500/20 px-3 py-1.5 rounded-lg transition-colors">
            <Download className="h-3.5 w-3.5" /> Baixar template CSV
          </button>
        </div>
      </div>

      <div
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={e => { e.preventDefault(); setIsDragging(false) }}
        onDrop={e => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files[0]) }}
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
          isDragging ? 'border-blue-400/60 bg-blue-500/10' :
          file       ? 'border-emerald-400/50 bg-emerald-500/10' :
                       'border-line hover:border-blue-400/40 hover:bg-raise-1'
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
          onChange={e => handleFile(e.target.files[0])} />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileText className="h-9 w-9 text-emerald-400" />
            <p className="font-semibold text-ink text-sm">{file.name}</p>
            <p className="text-xs" style={{ color: 'var(--ink-3)' }}>{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ink-3)' }}>
            <UploadCloud className="h-9 w-9" />
            <p className="text-sm font-medium">Arraste o arquivo ou clique para selecionar</p>
            <p className="text-xs">CSV ou Excel (.xlsx)</p>
          </div>
        )}
      </div>

      {erro && (
        <div className="flex items-start gap-2 rounded-xl px-4 py-3" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>
          <XCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{erro}</p>
        </div>
      )}

      <button onClick={importar} disabled={!file || loading} className="btn-primary w-full py-2.5 disabled:opacity-50">
        {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Importando...</> : <><UploadCloud className="h-4 w-4" /> Importar feedbacks</>}
      </button>

      {resultado && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Total',      value: resultado.total,      color: 'slate'   },
              { label: 'Importados', value: resultado.importados, color: 'emerald' },
              { label: 'Erros',      value: resultado.erros,      color: resultado.erros > 0 ? 'red' : 'slate' },
            ].map(({ label, value, color }) => (
              <div key={label} className={`rounded-2xl border p-4 text-center ${
                color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/20' :
                color === 'red'     ? 'bg-red-500/10 border-red-500/20' :
                                      'bg-raise-1 border-line'
              }`}>
                <p className={`text-2xl font-bold ${
                  color === 'emerald' ? 'text-emerald-300' :
                  color === 'red'     ? 'text-red-300' : 'text-ink'
                }`}>{value}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ink-2)' }}>{label}</p>
              </div>
            ))}
          </div>

          {erros.length > 0 && (
            <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <div className="px-4 py-3 border-b border-line bg-red-500/10">
                <p className="text-xs font-semibold text-red-300 uppercase tracking-wide">Linhas com erro</p>
              </div>
              <div className="divide-y divide-line max-h-48 overflow-y-auto">
                {erros.map((e, i) => (
                  <div key={i} className="px-4 py-2.5 flex items-center gap-3">
                    <span className="text-xs tabular-nums w-12 shrink-0" style={{ color: 'var(--ink-3)' }}>Ln {e.linha}</span>
                    <span className="text-xs tabular-nums" style={{ color: 'var(--ink-2)' }}>{e.cpf}</span>
                    <span className="text-xs text-red-400 ml-auto">{e.erro}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Feedback() {
  const navigate = useNavigate()
  const { setVista } = useAnalysis()
  const voltarAoDashboard = () => { setVista('dashboard'); navigate('/') }
  const { token, usuario, logout, isComando, isAdmin, isOperador } = useAuth()
  const podeRegistrar = isAdmin || isComando
  const [aba, setAba]             = useState('manual')
  const [form, setForm]           = useState(EMPTY)
  const [loading, setLoading]     = useState(false)
  const [historico, setHistorico] = useState([])
  const [erro, setErro]           = useState('')
  const [sucesso, setSucesso]     = useState('')
  const [devedor, setDevedor]     = useState(null)
  // COMANDO não pertence a uma empresa: escolhe em qual registrar.
  const [empresas, setEmpresas]   = useState([])
  const [empresaAlvo, setEmpresaAlvo] = useState('')
  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  function set(field, value) {
    setForm(prev => ({ ...prev, [field]: value }))
    setErro('')
  }

  async function enviar(e) {
    e.preventDefault()
    if (!podeRegistrar) return
    if (!devedor) { setErro('Escolha o devedor pelo nome ou CPF.'); return }
    const cpf = String(devedor.cpf)
    const parcelado = form.pagou === 'sim' && form.modalidade === 'parcelado'
    const nParcelas = parcelado ? parseInt(form.parcelas, 10) : 1
    if (parcelado && !(nParcelas >= 2 && nParcelas <= 120)) { setErro('Parcelas: de 2 a 120.'); return }

    setLoading(true); setErro('')
    try {
      const body = {
        cpf,
        pagou: form.pagou === 'sim',
        valor_recuperado: form.valor_recuperado ? parseFloat(form.valor_recuperado.replace(',', '.')) : 0,
      }
      if (form.data_pagamento) body.data_pagamento = form.data_pagamento
      body.predicao_id = devedor.id
      if (isComando && empresaAlvo) body.empresa = empresaAlvo
      if (form.canal_cobranca) body.canal_cobranca = form.canal_cobranca
      if (form.pagou === 'sim') {
        if (form.forma_pagamento) body.forma_pagamento = form.forma_pagamento
        body.parcelas = nParcelas
        body.com_juros = parcelado ? !!form.com_juros : false
        if (body.com_juros && form.taxa_juros_mensal !== '') body.taxa_juros_mensal = parseFloat(String(form.taxa_juros_mensal).replace(',', '.'))
        if (form.desconto_pct !== '') body.desconto_pct = parseFloat(String(form.desconto_pct).replace(',', '.'))
      }

      const res = await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      const wb = data.writeback ? ` · banco externo atualizado (${data.writeback})` : ''
      setHistorico(prev => [{
        cpf: fmtCPF(cpf), nome: devedor.nome, pagou: form.pagou === 'sim',
        forma: body.forma_pagamento ? NOME_FORMA[body.forma_pagamento] : null,
        canal: body.canal_cobranca ? NOME_CANAL[body.canal_cobranca] : null,
        parcelas: body.parcelas, com_juros: body.com_juros, desconto: body.desconto_pct,
        valor_recuperado: body.valor_recuperado,
        data_pagamento: form.data_pagamento,
        ok: res.ok,
        feedback_id: data.feedback_id,
        writeback: data.writeback || null,
        erro_msg: res.ok ? null : (data.detail || 'Erro desconhecido'),
        ts: new Date().toLocaleTimeString('pt-BR'),
      }, ...prev])

      if (res.ok) {
        setForm(EMPTY); setDevedor(null)
        setSucesso(`Pagamento registrado com sucesso.${wb}`)
        setTimeout(() => setSucesso(''), 6000)
      } else {
        setErro(data.detail || 'Erro ao registrar.')
      }
    } catch (err) {
      setErro('Não foi possível conectar ao servidor.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell titulo="Pagamentos">

      <div className="w-full max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-ink tracking-tight">Pagamentos<DicaAjuda id="registrar-pagamento" /></h1>
        </div>

        {/* Operador: só visualiza, não registra */}
        {isOperador && (
          <div className="rounded-2xl px-6 py-8 flex flex-col items-center text-center gap-3" style={{ background: 'rgb(var(--c-royal) / 0.08)', border: '1px solid rgb(var(--c-royal) / 0.18)' }}>
            <div className="w-12 h-12 rounded-2xl bg-blue-500/15 flex items-center justify-center">
              <ClipboardList className="h-6 w-6 text-blue-300" />
            </div>
            <div>
              <p className="text-sm font-bold text-ink">Registro de pagamentos é feito pelo administrador</p>
              <p className="text-xs mt-1 max-w-md leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                Os pagamentos são atualizados automaticamente quando o banco de dados da empresa é sincronizado.
                Qualquer alteração de status aparece aqui para toda a equipe em tempo real.
              </p>
            </div>
            <button onClick={voltarAoDashboard}
              className="mt-2 px-4 py-2 text-brand-ink text-sm font-semibold rounded-xl transition-colors" style={{ background: 'var(--brand)' }}>
              Ver dashboard
            </button>
          </div>
        )}

        {/* Admin / Comando: pode registrar manualmente */}
        {podeRegistrar && (
          <>
            <div className="flex gap-1 p-1 rounded-xl w-fit" style={{ background: 'var(--raise-2)', border: '1px solid var(--line)' }}>
              {[
                { key: 'manual', label: 'Manual (um por vez)' },
                { key: 'lote',   label: 'Importar em lote'   },
              ].map(({ key, label }) => (
                <button key={key} onClick={() => setAba(key)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    aba === key ? 'bg-raise-3 text-ink' : 'text-ink-2 hover:text-ink'
                  }`}>
                  {label}
                </button>
              ))}
            </div>

            {aba === 'lote' && (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                <ImportacaoLote token={token} />
              </div>
            )}

            {aba === 'manual' && (
              <div className="grid grid-cols-1 gap-6 items-start lg:grid-cols-5">
                <form onSubmit={enviar} className="lg:col-span-2 rounded-2xl p-6 space-y-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                  {isComando && (
                    <div>
                      <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Empresa</label>
                      <select value={empresaAlvo} onChange={e => { setEmpresaAlvo(e.target.value); setDevedor(null) }} className="input-base">
                        <option value="">Escolha a empresa…</option>
                        {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
                      </select>
                    </div>
                  )}
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Devedor</label>
                    <BuscaDevedor escolhido={devedor} onEscolher={d => { setDevedor(d); setErro('') }}
                      empresaAlvo={isComando ? empresaAlvo : ''} exigeEmpresa={isComando} />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-2" style={{ color: 'var(--ink-2)' }}>Realizou pagamento?</label>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { val: 'sim', label: 'Sim, pagou', active: 'bg-emerald-600 border-emerald-600 text-brand-ink' },
                        { val: 'nao', label: 'Não pagou',  active: 'bg-red-500 border-red-500 text-brand-ink' },
                      ].map(({ val, label, active }) => (
                        <button key={val} type="button" onClick={() => set('pagou', val)}
                          className={`py-2.5 rounded-xl border text-sm font-semibold transition-all ${
                            form.pagou === val ? active : 'bg-raise-2 border-line text-ink-2 hover:border-line-2 hover:bg-raise-3 hover:text-ink'
                          }`}>
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Canal de cobrança</label>
                    <select value={form.canal_cobranca} onChange={e => set('canal_cobranca', e.target.value)} className="input-base">
                      <option value="">Não informado</option>
                      {CANAIS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
                    </select>
                  </div>

                  {form.pagou === 'sim' && (
                    <div>
                      <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                        {form.modalidade === 'parcelado' ? 'Valor recebido agora (1ª parcela)' : 'Valor recuperado'}
                      </label>
                      <div className="relative">
                        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-4 text-sm">R$</span>
                        <input type="number" min="0" step="0.01" placeholder="0,00"
                          value={form.valor_recuperado} onChange={e => set('valor_recuperado', e.target.value)}
                          className="input-base pl-9" />
                      </div>
                    </div>
                  )}

                  {/* Condições do acordo: o que foi negociado. Ficam guardadas por
                      pagamento para medir que condição funciona. */}
                  {form.pagou === 'sim' && (
                    <div className="space-y-4 rounded-xl p-4" style={{ background: 'var(--raise-1)', border: '1px solid var(--line)' }}>
                      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-2)' }}>Condições do acordo</p>
                      <div>
                        <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Forma de pagamento</label>
                        <select value={form.forma_pagamento} onChange={e => set('forma_pagamento', e.target.value)} className="input-base">
                          <option value="">Não informada</option>
                          {FORMAS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Modelo</label>
                        <div className="grid grid-cols-2 gap-2">
                          {[['a_vista', 'À vista'], ['parcelado', 'Parcelado']].map(([v, r]) => (
                            <button key={v} type="button" onClick={() => set('modalidade', v)}
                              className={`py-2 rounded-lg border text-sm font-medium transition-all ${
                                form.modalidade === v ? 'bg-blue-600/15 border-blue-500/60 text-ink font-semibold' : 'bg-raise-2 border-line text-ink-2 hover:text-ink'}`}>
                              {r}
                            </button>
                          ))}
                        </div>
                      </div>
                      {form.modalidade === 'parcelado' && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Parcelas</label>
                            <input type="number" min="2" max="120" value={form.parcelas}
                              onChange={e => set('parcelas', e.target.value)} className="input-base tabular-nums" />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Juros</label>
                            <div className="grid grid-cols-2 gap-1.5">
                              {[[false, 'Sem'], [true, 'Com']].map(([v, r]) => (
                                <button key={r} type="button" onClick={() => set('com_juros', v)}
                                  className={`py-2 rounded-lg border text-sm font-medium transition-all ${
                                    form.com_juros === v ? 'bg-blue-600/15 border-blue-500/60 text-ink font-semibold' : 'bg-raise-2 border-line text-ink-2 hover:text-ink'}`}>
                                  {r}
                                </button>
                              ))}
                            </div>
                          </div>
                          {form.com_juros && (
                            <div className="col-span-2">
                              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Taxa de juros (% ao mês)</label>
                              <input type="number" min="0" max="20" step="0.01" placeholder="ex.: 1,99"
                                value={form.taxa_juros_mensal} onChange={e => set('taxa_juros_mensal', e.target.value)} className="input-base tabular-nums" />
                            </div>
                          )}
                          <p className="col-span-2 text-[11px]" style={{ color: 'var(--ink-3)' }}>
                            Abre um acordo em Acordos: esta é a 1ª parcela (paga) e as outras vencem todo mês, no mesmo dia e valor.
                          </p>
                        </div>
                      )}
                      <div>
                        <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Desconto concedido (%)</label>
                        <input type="number" min="0" max="100" step="0.1" placeholder="0"
                          value={form.desconto_pct} onChange={e => set('desconto_pct', e.target.value)} className="input-base tabular-nums" />
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                      Data do pagamento
                    </label>
                    <input type="date" value={form.data_pagamento}
                      max={new Date().toISOString().split('T')[0]}
                      onChange={e => set('data_pagamento', e.target.value)} className="input-base" />
                  </div>

                  {sucesso && (
                    <div className="flex items-start gap-2 rounded-xl px-4 py-3" style={{ background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                      <p className="text-sm text-emerald-300 font-medium">{sucesso}</p>
                    </div>
                  )}
                  {erro && (
                    <div className="flex items-start gap-2 rounded-xl px-4 py-3" style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>
                      <XCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                      <p className="text-sm text-red-300">{erro}</p>
                    </div>
                  )}

                  <button type="submit" disabled={loading} className="btn-primary w-full py-2.5 disabled:opacity-50">
                    {loading
                      ? <><Loader2 className="h-4 w-4 animate-spin" /> Registrando...</>
                      : <><Plus className="h-4 w-4" /> Registrar pagamento</>}
                  </button>
                </form>

                <div className="lg:col-span-3 rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                  <div className="px-5 py-4 border-b border-line flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ClipboardList className="h-4 w-4 text-ink-3" />
                      <span className="section-label">Registros desta sessão</span>
                    </div>
                    {historico.length > 0 && (
                      <button onClick={() => setHistorico([])}
                        className="flex items-center gap-1 text-xs text-ink-3 hover:text-red-400 transition-colors">
                        <Trash2 className="h-3.5 w-3.5" /> Limpar
                      </button>
                    )}
                  </div>

                  {historico.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center px-6">
                      <ClipboardList className="h-10 w-10 text-line-2 mb-3" />
                      <p className="text-sm text-ink-2">Nenhum pagamento registrado ainda.</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-line">
                      {historico.map((item, i) => (
                        <div key={i} className="px-5 py-3.5 flex items-center gap-4">
                          <StatusBadge ok={item.ok} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 flex-wrap">
                              {item.nome && <span className="text-sm font-semibold text-ink">{item.nome}</span>}
                              <span className="tabular-nums text-xs text-ink-2">{item.cpf}</span>
                              <span className={`text-xs font-semibold ${item.pagou ? 'text-emerald-400' : 'text-red-400'}`}>
                                {item.pagou ? '✓ Pagou' : '✗ Não pagou'}
                              </span>
                              {item.pagou && item.valor_recuperado > 0 && (
                                <span className="text-xs text-ink-2">{fmtBRL(item.valor_recuperado)}</span>
                              )}
                            </div>
                            {item.canal && (
                              <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>via {item.canal}</p>
                            )}
                            {item.pagou && (item.forma || item.parcelas) && (
                              <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>
                                {[item.forma,
                                  item.parcelas > 1 ? `${item.parcelas}x ${item.com_juros ? 'com' : 'sem'} juros` : 'à vista',
                                  item.desconto ? `${item.desconto}% de desconto` : null].filter(Boolean).join(' · ')}
                              </p>
                            )}
                            {item.writeback && (
                              <p className="text-xs text-blue-300 mt-0.5">↳ banco externo atualizado: {item.writeback}</p>
                            )}
                            {item.erro_msg && (
                              <p className="text-xs text-red-400 mt-0.5">{item.erro_msg}</p>
                            )}
                          </div>
                          <span className="text-xs text-ink-4 shrink-0">{item.ts}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

      </div>
    </AppShell>
  )
}
