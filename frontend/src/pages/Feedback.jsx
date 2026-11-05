import { useState, useRef, useEffect } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  CheckCircle2, XCircle, Loader2, ClipboardList, UploadCloud, FileText, Download, Search, X, CreditCard, ChevronDown,
} from 'lucide-react'
import { feedbackLote, buscarDevedores, listarEmpresas } from '../api'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'

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
// Na tela, o CPF aparece mascarado (como na prancha); o número inteiro fica na busca.
const mascararCPF = (c) => {
  const d = String(c || '').replace(/\D/g, '')
  return d.length === 11 ? `***.${d.slice(3, 6)}.${d.slice(6, 9)}-**` : c
}
const iniciais = (nome) => String(nome || '').trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase() || '·'
const Rotulo = ({ children, htmlFor }) => <label htmlFor={htmlFor} className="mb-1.5 block text-[13px] font-semibold text-ink-2">{children}</label>
// Opção em pílula (canal, à vista/parcelado, juros): a ativa ganha o royal suave.
function Pilula({ ativo, onClick, children }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={ativo}
      className={`h-9 rounded-full border px-3.5 text-[13px] transition-colors ${ativo
        ? 'border-[color-mix(in_srgb,var(--royal)_55%,transparent)] bg-[var(--royal-soft)] font-semibold text-ink'
        : 'border-line bg-surface text-ink-2 hover:text-ink'}`}>
      {children}
    </button>
  )
}

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
      <div className="flex items-center gap-3 rounded-[12px] border border-line-2 bg-[var(--sunken)] px-3.5 py-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--royal-soft)] text-[11px] font-bold text-accent-text" aria-hidden="true">{iniciais(escolhido.nome)}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold text-ink">{escolhido.nome || 'Sem nome'}</p>
          {escolhido.carteira_nome && (
            <p className="truncate text-xs text-ink-3">Carteira: {escolhido.carteira_nome}{escolhido.carteira_data && <> · {fmtData(escolhido.carteira_data)}</>}</p>
          )}
        </div>
        <span className="hidden shrink-0 text-right text-[13px] tabular-nums text-ink-2 sm:block">
          {mascararCPF(escolhido.cpf)}{escolhido.valor_divida != null && <> · {fmtBRL(escolhido.valor_divida)}</>}
        </span>
        <button type="button" onClick={() => onEscolher(null)} aria-label="Trocar devedor" title="Trocar devedor"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] text-ink-3 hover:bg-[var(--raised)] hover:text-ink">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    )
  }

  return (
    <div ref={caixa} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <input type="text" value={texto} onChange={e => setTexto(e.target.value)} onFocus={() => itens.length && setAberto(true)}
          placeholder={exigeEmpresa && !empresaAlvo ? 'Escolha a empresa primeiro' : 'Nome ou CPF do devedor'}
          disabled={exigeEmpresa && !empresaAlvo}
          className="input-base h-[46px] rounded-[12px] pl-10 text-[15px]" autoComplete="off" aria-label="Devedor: nome ou CPF" />
        {buscando && <Loader2 className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ink-4" />}
      </div>
      {erro && <p className="mt-1.5 text-xs text-[var(--danger)]">{erro}</p>}
      {aberto && texto.trim().length >= 2 && !buscando && (
        <div className="absolute z-30 mt-1.5 max-h-80 w-full overflow-y-auto rounded-[14px] border border-line-2 bg-[var(--raised)] shadow-xl">
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
              <p className="text-xs" style={{ color: 'var(--ink-3)' }}>
                Carteira: {d.carteira_nome || '—'}{d.carteira_data && <> · {fmtData(d.carteira_data)}</>}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
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
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <section className="space-y-4 rounded-[22px] border border-line bg-surface px-6 py-[22px]">
        <h2 className="text-[17px] font-semibold text-ink">Importar uma planilha de pagamentos</h2>
        <button type="button" onClick={() => inputRef.current.click()}
          onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={e => { e.preventDefault(); setIsDragging(false) }}
          onDrop={e => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files[0]) }}
          className={`flex w-full flex-col items-center gap-2 rounded-[18px] border border-dashed px-6 py-9 text-center transition-colors ${
            isDragging ? 'border-[var(--royal)] bg-[var(--royal-soft)]'
              : file ? 'border-[color-mix(in_srgb,var(--success)_50%,transparent)] bg-[var(--success-soft)]'
                : 'border-[color-mix(in_srgb,var(--royal)_45%,transparent)] bg-[color-mix(in_srgb,var(--royal-soft)_45%,transparent)] hover:bg-[var(--royal-soft)]'}`}>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={e => handleFile(e.target.files[0])} />
          <span className="flex h-11 w-11 items-center justify-center rounded-[12px] bg-[var(--raised)] text-accent-text">
            {file ? <FileText className="h-5 w-5" aria-hidden="true" /> : <UploadCloud className="h-5 w-5" aria-hidden="true" />}
          </span>
          {file
            ? <><b className="text-[15px] text-ink">{file.name}</b><span className="text-xs text-ink-3">{(file.size / 1024).toFixed(1)} KB · clique para trocar</span></>
            : <><b className="text-[15px] text-ink">Arraste a planilha ou clique para escolher</b><span className="text-xs text-ink-3">CSV ou Excel (.xlsx)</span></>}
        </button>
        {erro && (
          <p role="alert" className="flex items-start gap-2 rounded-[14px] border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-ink">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" aria-hidden="true" /> {erro}
          </p>
        )}
        <button type="button" onClick={importar} disabled={!file || loading} className="btn-primary h-12 w-full disabled:opacity-50">
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Importando…</> : <><UploadCloud className="h-4 w-4" aria-hidden="true" /> Importar pagamentos</>}
        </button>

        {resultado && (
          <div className="space-y-3">
            <div className="grid grid-cols-3 divide-x divide-line rounded-[18px] border border-line">
              {[['Linhas', resultado.total, 'text-ink'], ['Importadas', resultado.importados, 'text-[var(--success)]'],
                ['Com erro', resultado.erros, resultado.erros > 0 ? 'text-[var(--danger)]' : 'text-ink']].map(([rot, v, cor]) => (
                <div key={rot} className="px-4 py-3">
                  <p className="text-xs text-ink-2">{rot}</p>
                  <p className={`text-[22px] font-bold tabular-nums ${cor}`}>{v}</p>
                </div>
              ))}
            </div>
            {erros.length > 0 && (
              <div className="overflow-hidden rounded-[18px] border border-line">
                <p className="border-b border-line bg-[var(--danger-soft)] px-4 py-2.5 text-xs font-semibold text-ink">Linhas com erro</p>
                <div className="max-h-48 divide-y divide-line overflow-y-auto">
                  {erros.map((e, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                      <span className="w-12 shrink-0 tabular-nums text-ink-3">Linha {e.linha}</span>
                      <span className="tabular-nums text-ink-2">{mascararCPF(e.cpf)}</span>
                      <span className="ml-auto text-[var(--danger)]">{e.erro}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="lote-cols">
        <h2 id="lote-cols" className="text-[15px] font-semibold text-ink">O que a planilha precisa ter</h2>
        {[['Obrigatório', [['cpf', 'CPF', '000.000.000-00'], ['pagou', 'Pagou?', 'sim / não ou 1 / 0']]],
          ['Opcional', [['valor_recuperado', 'Valor recebido', '1500.00'], ['data_pagamento', 'Data do pagamento', '2026-05-19']]]].map(([g, cols]) => (
          <div key={g} className="mt-3">
            <p className="section-label">{g}</p>
            <ul className="mt-1.5 flex flex-col gap-1.5">
              {cols.map(([k, n, ex]) => (
                <li key={k} className="flex items-center gap-2.5 text-[13px]">
                  <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-[var(--border-strong)]" aria-hidden="true" />
                  <span className="text-ink">{n}</span> <code className="text-[11px] text-ink-3">{k}</code>
                  <span className="ml-auto text-ink-3">{ex}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <button type="button" onClick={baixarTemplate} className="btn-secondary btn-sm mt-4">
          <Download className="h-3.5 w-3.5" aria-hidden="true" /> Baixar modelo CSV
        </button>
      </section>
    </div>
  )
}

export default function Feedback() {
  const navigate = useNavigate()
  const { setVista } = useAnalysis()
  const voltarAoDashboard = () => { setVista('dashboard'); navigate('/') }
  const { token, isComando, isAdmin, isOperador } = useAuth()
  const podeRegistrar = isAdmin || isComando
  const [aba, setAba]             = useState('manual')
  // Acordos e Roteiros saíram daqui (prancha): os links antigos (?secao=) levam às telas próprias.
  const [params] = useSearchParams()
  const secaoAntiga = params.get('secao')
  const [condicoes, setCondicoes] = useState(false)
  // Vindo do "Registrar pagamento" da Agenda: devedor e valor prometido já preenchidos.
  const registrar = useLocation().state?.registrar ?? null
  const [form, setForm]           = useState(() => registrar?.valor > 0 ? { ...EMPTY, valor_recuperado: String(registrar.valor) } : EMPTY)
  const [loading, setLoading]     = useState(false)
  const [historico, setHistorico] = useState([])
  const [erro, setErro]           = useState('')
  const [sucesso, setSucesso]     = useState('')
  const [devedor, setDevedor]     = useState(registrar?.devedor ?? null)
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
    // O parcelado abre um acordo com parcelas no valor da 1ª: sem valor, as
    // parcelas nasceriam de R$ 0 em Acordos.
    if (parcelado && !(parseFloat(String(form.valor_recuperado).replace(',', '.')) > 0)) {
      setErro('Informe o valor recebido agora (1ª parcela): é ele que define as próximas parcelas em Acordos.'); return
    }

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

  if (secaoAntiga === 'acordos') return <Navigate to="/acordos" replace />
  if (secaoAntiga === 'roteiros') return <Navigate to="/roteiros" replace />

  const pagos = historico.filter(h => h.ok && h.pagou)
  const somaPaga = pagos.reduce((t, h) => t + (h.valor_recuperado || 0), 0)
  const parcelado = form.modalidade === 'parcelado'

  return (
    <AppShell titulo="Pagamentos">
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <CabecalhoPagina rotulo="Carteira" icone={CreditCard} titulo="Pagamentos" ajuda="registrar-pagamento" className="!mb-2"
          subtitulo="Registre quem pagou. É isso que ensina o modelo a acertar quem cobrar primeiro.">
          {podeRegistrar && (
            <div className="flex rounded-[14px] border border-line bg-surface p-1" role="tablist" aria-label="Como registrar">
              {[['manual', 'Um por vez'], ['lote', 'Importar planilha']].map(([k, l]) => (
                <button key={k} type="button" role="tab" aria-selected={aba === k} onClick={() => setAba(k)}
                  className={`h-9 rounded-[10px] px-3.5 text-sm transition-colors ${aba === k ? 'bg-[var(--raised)] font-semibold text-ink' : 'text-ink-2 hover:text-ink'}`}>
                  {l}
                </button>
              ))}
            </div>
          )}
        </CabecalhoPagina>

        {/* Operador: só visualiza, não registra */}
        {isOperador && (
          <section className="flex flex-col items-center gap-3 rounded-[22px] border border-line bg-surface px-6 py-10 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-[var(--royal-soft)] text-accent-text"><ClipboardList className="h-6 w-6" aria-hidden="true" /></span>
            <p className="text-[15px] font-semibold text-ink">O registro de pagamentos é feito pelo administrador</p>
            <p className="max-w-md text-sm leading-relaxed text-ink-2">
              Os pagamentos se atualizam sozinhos quando o banco de dados da empresa é sincronizado, e aparecem para toda a equipe.
            </p>
            <div className="mt-1 flex flex-wrap justify-center gap-2">
              <button type="button" onClick={voltarAoDashboard} className="btn-primary">Ver o painel da carteira</button>
              <Link to="/acordos" className="btn-secondary">Meus acordos</Link>
              <Link to="/roteiros" className="btn-secondary">Roteiros de mensagem</Link>
            </div>
          </section>
        )}

        {podeRegistrar && aba === 'lote' && <ImportacaoLote token={token} />}

        {podeRegistrar && aba === 'manual' && (
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
            <form onSubmit={enviar} className="space-y-4 rounded-[22px] border border-line bg-surface px-6 py-[22px]">
              <h2 className="text-[17px] font-semibold text-ink">Registrar um resultado</h2>
              {isComando && (
                <div>
                  <Rotulo htmlFor="pg-empresa">Empresa</Rotulo>
                  <select id="pg-empresa" value={empresaAlvo} onChange={e => { setEmpresaAlvo(e.target.value); setDevedor(null) }} className="input-base h-[46px] rounded-[12px]">
                    <option value="">Escolha a empresa…</option>
                    {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
                  </select>
                </div>
              )}
              <div>
                <Rotulo>Devedor</Rotulo>
                <BuscaDevedor escolhido={devedor} onEscolher={d => { setDevedor(d); setErro('') }}
                  empresaAlvo={isComando ? empresaAlvo : ''} exigeEmpresa={isComando} />
              </div>

              <div>
                <Rotulo>Pagou?</Rotulo>
                <div className="grid grid-cols-2 gap-2" role="group" aria-label="Pagou?">
                  {[['sim', 'Sim, pagou', 'border-[color-mix(in_srgb,var(--success)_50%,transparent)] bg-[var(--success-soft)]'],
                    ['nao', 'Não pagou', 'border-[color-mix(in_srgb,var(--danger)_50%,transparent)] bg-[var(--danger-soft)]']].map(([val, label, ativo]) => (
                    <button key={val} type="button" onClick={() => set('pagou', val)} aria-pressed={form.pagou === val}
                      className={`h-11 rounded-[12px] border text-sm font-semibold transition-colors ${form.pagou === val
                        ? `${ativo} text-ink`
                        : 'border-line bg-surface text-ink-2 hover:text-ink'}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className={`grid gap-3 ${form.pagou === 'sim' ? 'sm:grid-cols-2' : ''}`}>
                {form.pagou === 'sim' && (
                  <div>
                    <Rotulo htmlFor="pg-valor">{parcelado ? 'Recebido agora (1ª parcela)' : 'Valor recebido'}</Rotulo>
                    <div className="relative">
                      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-3">R$</span>
                      <input id="pg-valor" type="number" min="0" step="0.01" placeholder="0,00" inputMode="decimal"
                        value={form.valor_recuperado} onChange={e => set('valor_recuperado', e.target.value)}
                        className="input-base h-[46px] rounded-[12px] pl-10 text-[15px] tabular-nums" />
                    </div>
                  </div>
                )}
                <div>
                  <Rotulo htmlFor="pg-data">{form.pagou === 'sim' ? 'Data' : 'Data do contato'}</Rotulo>
                  <input id="pg-data" type="date" value={form.data_pagamento} max={new Date().toISOString().split('T')[0]}
                    onChange={e => set('data_pagamento', e.target.value)} className="input-base h-[46px] rounded-[12px] text-[15px]" />
                </div>
              </div>

              <div>
                <Rotulo>Por onde ele foi cobrado</Rotulo>
                <div className="flex flex-wrap gap-1.5">
                  {CANAIS.map(([v, r]) => (
                    <Pilula key={v} ativo={form.canal_cobranca === v} onClick={() => set('canal_cobranca', form.canal_cobranca === v ? '' : v)}>{r}</Pilula>
                  ))}
                </div>
              </div>

              {/* Condições do acordo: o que foi negociado. Ficam guardadas por pagamento
                  para medir que condição funciona. Opcional, por isso começa fechado. */}
              {form.pagou === 'sim' && (
                <div className="rounded-[14px] border border-line">
                  <button type="button" onClick={() => setCondicoes(c => !c)} aria-expanded={condicoes}
                    className="flex min-h-[44px] w-full items-center justify-between gap-3 px-4 text-left">
                    <span className="text-sm font-semibold text-ink">Condições do acordo
                      <span className="ml-1.5 font-normal text-ink-3">
                        {[form.forma_pagamento && NOME_FORMA[form.forma_pagamento], parcelado ? `${form.parcelas}x` : 'à vista', form.desconto_pct && `${form.desconto_pct}% de desconto`].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                    <ChevronDown className={`h-4 w-4 shrink-0 text-ink-3 transition-transform ${condicoes ? 'rotate-180' : ''}`} aria-hidden="true" />
                  </button>
                  {condicoes && (
                    <div className="space-y-4 border-t border-line px-4 py-4">
                      <div>
                        <Rotulo>Forma de pagamento</Rotulo>
                        <div className="flex flex-wrap gap-1.5">
                          {FORMAS.map(([v, r]) => <Pilula key={v} ativo={form.forma_pagamento === v} onClick={() => set('forma_pagamento', form.forma_pagamento === v ? '' : v)}>{r}</Pilula>)}
                        </div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <Rotulo>Modelo</Rotulo>
                          <div className="flex gap-1.5">
                            <Pilula ativo={!parcelado} onClick={() => set('modalidade', 'a_vista')}>À vista</Pilula>
                            <Pilula ativo={parcelado} onClick={() => set('modalidade', 'parcelado')}>Parcelado</Pilula>
                          </div>
                        </div>
                        <div>
                          <Rotulo htmlFor="pg-desc">Desconto concedido</Rotulo>
                          <div className="relative">
                            <input id="pg-desc" type="number" min="0" max="100" step="0.1" placeholder="0" inputMode="decimal"
                              value={form.desconto_pct} onChange={e => set('desconto_pct', e.target.value)} className="input-base h-[46px] rounded-[12px] pr-9 tabular-nums" />
                            <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-3">%</span>
                          </div>
                        </div>
                      </div>
                      {parcelado && (
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <Rotulo htmlFor="pg-parc">Parcelas</Rotulo>
                            <div className="relative">
                              <input id="pg-parc" type="number" min="2" max="120" value={form.parcelas} inputMode="numeric"
                                onChange={e => set('parcelas', e.target.value)} className="input-base h-[46px] rounded-[12px] pr-14 tabular-nums" />
                              <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-3">vezes</span>
                            </div>
                          </div>
                          <div>
                            <Rotulo>Juros</Rotulo>
                            <div className="flex gap-1.5">
                              <Pilula ativo={!form.com_juros} onClick={() => set('com_juros', false)}>Sem juros</Pilula>
                              <Pilula ativo={form.com_juros} onClick={() => set('com_juros', true)}>Com juros</Pilula>
                            </div>
                          </div>
                          {form.com_juros && (
                            <div className="sm:col-span-2">
                              <Rotulo htmlFor="pg-juros">Taxa de juros</Rotulo>
                              <div className="relative">
                                <input id="pg-juros" type="number" min="0" max="20" step="0.01" placeholder="1,99" inputMode="decimal"
                                  value={form.taxa_juros_mensal} onChange={e => set('taxa_juros_mensal', e.target.value)} className="input-base h-[46px] rounded-[12px] pr-24 tabular-nums" />
                                <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-3">% ao mês</span>
                              </div>
                            </div>
                          )}
                          <p className="text-xs text-ink-3 sm:col-span-2">Abre um acordo em Acordos: esta é a 1ª parcela (paga) e as outras vencem todo mês, no mesmo dia e valor.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {sucesso && (
                <p role="status" className="flex items-start gap-2 rounded-[14px] border border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)] px-4 py-3 text-sm font-medium text-ink">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]" aria-hidden="true" /> {sucesso}
                </p>
              )}
              {erro && (
                <p role="alert" className="flex items-start gap-2 rounded-[14px] border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-ink">
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" aria-hidden="true" /> {erro}
                </p>
              )}

              <button type="submit" disabled={loading} className="btn-primary h-12 w-full disabled:opacity-50">
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Registrando…</> : 'Registrar'}
              </button>
            </form>

            <section className="rounded-[22px] border border-line bg-surface px-6 py-[22px]" aria-labelledby="pg-sessao">
              <div className="flex items-baseline justify-between gap-3">
                <h2 id="pg-sessao" className="text-[15px] font-semibold text-ink">Registrados agora</h2>
                {historico.length > 0 && (
                  <span className="text-[13px] tabular-nums text-ink-2">
                    {historico.length} {historico.length === 1 ? 'registro' : 'registros'}{somaPaga > 0 && <> · <b className="text-[var(--success)]">{fmtBRL(somaPaga)}</b></>}
                  </span>
                )}
              </div>
              {historico.length === 0 ? (
                <div className="py-10 text-center">
                  <p className="text-[15px] font-semibold text-ink">Nada registrado ainda</p>
                  <p className="mt-1 text-sm text-ink-2">Cada resultado que você registra aparece aqui, para conferir.</p>
                </div>
              ) : (
                <ul className="mt-3 space-y-2">
                  {historico.map((item, i) => (
                    <li key={i} className={`flex items-center gap-3 rounded-[14px] border px-4 py-3 ${item.ok ? 'border-line bg-[var(--sunken)]' : 'border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)]'}`}>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink">{item.nome || item.cpf}</p>
                        <p className="truncate text-xs text-ink-3">
                          {[mascararCPF(item.cpf), item.canal && `via ${item.canal}`,
                            item.pagou && item.forma, item.pagou && (item.parcelas > 1 ? `${item.parcelas}x ${item.com_juros ? 'com' : 'sem'} juros` : 'à vista'),
                            item.pagou && item.desconto ? `${item.desconto}% de desconto` : null, item.ts].filter(Boolean).join(' · ')}
                        </p>
                        {item.writeback && <p className="mt-0.5 text-xs text-accent-text">Banco externo atualizado: {item.writeback}</p>}
                        {item.erro_msg && <p className="mt-0.5 text-xs text-[var(--danger)]">Não registrado: {item.erro_msg}</p>}
                      </div>
                      <span className={`shrink-0 text-sm font-semibold tabular-nums ${!item.ok ? 'text-[var(--danger)]' : item.pagou ? 'text-ink' : 'text-ink-3'}`}>
                        {!item.ok ? 'Erro' : item.pagou ? (item.valor_recuperado > 0 ? fmtBRL(item.valor_recuperado) : 'Pagou') : 'Não pagou'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-5 border-t border-line pt-4 text-[13px] leading-relaxed text-ink-3">
                Acordos ficam em <Link to="/acordos" className="font-semibold text-accent-text hover:underline">Resultados › Acordos</Link>.
                {' '}Roteiros de mensagem, em <Link to="/roteiros" className="font-semibold text-accent-text hover:underline">Configurações › Roteiros</Link>.
              </p>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  )
}
