import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2, ClipboardList, ArrowLeft, Plus, Trash2, UploadCloud, FileText, Download, LogOut } from 'lucide-react'
import { feedbackLote } from '../api'
import { useAuth } from '../context/AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const EMPTY = { cpf: '', pagou: 'sim', valor_recuperado: '', data_pagamento: '' }

function StatusBadge({ ok }) {
  return ok
    ? <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-0.5"><CheckCircle2 className="h-3.5 w-3.5" /> Registrado</span>
    : <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-full px-2.5 py-0.5"><XCircle className="h-3.5 w-3.5" /> Erro</span>
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

function ImportacaoLote() {
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
      const res = await feedbackLote(file, API_TOKEN)
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
    <div className="col-span-5 space-y-5">

      {/* Instruções + template */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 flex gap-4 items-start">
        <FileText className="h-5 w-5 text-slate-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-700 mb-1">Formato esperado do arquivo</p>
          <p className="text-xs text-slate-500 mb-2">
            Colunas obrigatórias: <code className="bg-white border border-slate-200 rounded px-1">cpf</code> e <code className="bg-white border border-slate-200 rounded px-1">pagou</code> (sim/não ou 1/0).
            {' '}Opcionais: <code className="bg-white border border-slate-200 rounded px-1">valor_recuperado</code>, <code className="bg-white border border-slate-200 rounded px-1">data_pagamento</code>.
          </p>
          <button onClick={baixarTemplate}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors">
            <Download className="h-3.5 w-3.5" /> Baixar template CSV
          </button>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={e => { e.preventDefault(); setIsDragging(false) }}
        onDrop={e => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files[0]) }}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          isDragging ? 'border-blue-400 bg-blue-50' :
          file       ? 'border-emerald-300 bg-emerald-50' :
                       'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
          onChange={e => handleFile(e.target.files[0])} />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileText className="h-8 w-8 text-emerald-500" />
            <p className="font-medium text-slate-800 text-sm">{file.name}</p>
            <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-400">
            <UploadCloud className="h-8 w-8" />
            <p className="text-sm">Arraste o arquivo ou clique para selecionar</p>
            <p className="text-xs">CSV ou Excel (.xlsx)</p>
          </div>
        )}
      </div>

      {erro && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
          <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
          <p className="text-xs text-red-700">{erro}</p>
        </div>
      )}

      <button onClick={importar} disabled={!file || loading}
        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-200 text-white font-medium text-sm py-2.5 rounded-lg transition-colors">
        {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Importando...</> : <><UploadCloud className="h-4 w-4" /> Importar feedbacks</>}
      </button>

      {/* Resultado */}
      {resultado && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Total',      value: resultado.total,      color: 'slate'   },
              { label: 'Importados', value: resultado.importados, color: 'emerald' },
              { label: 'Erros',      value: resultado.erros,      color: resultado.erros > 0 ? 'red' : 'slate' },
            ].map(({ label, value, color }) => (
              <div key={label} className={`rounded-xl border p-4 text-center ${
                color === 'emerald' ? 'bg-emerald-50 border-emerald-200' :
                color === 'red'     ? 'bg-red-50 border-red-200' :
                                      'bg-slate-50 border-slate-200'
              }`}>
                <p className={`text-2xl font-bold ${
                  color === 'emerald' ? 'text-emerald-700' :
                  color === 'red'     ? 'text-red-600' : 'text-slate-700'
                }`}>{value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>

          {erros.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 bg-red-50">
                <p className="text-xs font-semibold text-red-700">Linhas com erro</p>
              </div>
              <div className="divide-y divide-slate-50 max-h-48 overflow-y-auto">
                {erros.map((e, i) => (
                  <div key={i} className="px-4 py-2.5 flex items-center gap-3">
                    <span className="text-xs text-slate-400 font-mono w-12 shrink-0">Ln {e.linha}</span>
                    <span className="text-xs font-mono text-slate-600">{e.cpf}</span>
                    <span className="text-xs text-red-500 ml-auto">{e.erro}</span>
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
  const { token, usuario, logout } = useAuth()
  const [aba, setAba]           = useState('manual')
  const [form, setForm]         = useState(EMPTY)
  const [loading, setLoading]   = useState(false)
  const [historico, setHistorico] = useState([])
  const [erro, setErro]         = useState('')

  function set(field, value) {
    setForm(prev => ({ ...prev, [field]: value }))
    setErro('')
  }

  function formatarCPF(raw) {
    const nums = raw.replace(/\D/g, '').slice(0, 11)
    return nums
      .replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d{1,2})$/, '$1-$2')
  }

  async function enviar(e) {
    e.preventDefault()
    const cpf = form.cpf.replace(/\D/g, '')
    if (cpf.length !== 11) { setErro('CPF inválido — informe 11 dígitos.'); return }

    setLoading(true)
    setErro('')
    try {
      const body = {
        cpf,
        pagou: form.pagou === 'sim',
        valor_recuperado: form.valor_recuperado ? parseFloat(form.valor_recuperado.replace(',', '.')) : 0,
      }
      if (form.data_pagamento) body.data_pagamento = form.data_pagamento

      const res = await fetch(`${API_URL}/feedback`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body:    JSON.stringify(body),
      })
      const data = await res.json()

      setHistorico(prev => [{
        cpf:              form.cpf,
        pagou:            form.pagou === 'sim',
        valor_recuperado: body.valor_recuperado,
        data_pagamento:   form.data_pagamento,
        ok:               res.ok,
        feedback_id:      data.feedback_id,
        erro_msg:         res.ok ? null : (data.detail || 'Erro desconhecido'),
        ts:               new Date().toLocaleTimeString('pt-BR'),
      }, ...prev])

      if (res.ok) {
        setForm(EMPTY)
      } else {
        setErro(data.detail || 'Erro ao registrar feedback.')
      }
    } catch (err) {
      setErro('Não foi possível conectar ao backend.')
      setHistorico(prev => [{
        cpf: form.cpf, pagou: form.pagou === 'sim',
        valor_recuperado: 0, data_pagamento: form.data_pagamento,
        ok: false, feedback_id: null, erro_msg: err.message,
        ts: new Date().toLocaleTimeString('pt-BR'),
      }, ...prev])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">

      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">⚖</span>
          </div>
          <span className="font-bold text-slate-800">Mizan</span>
          <span className="text-slate-300 mx-1">/</span>
          <span className="text-slate-500 text-sm">Feedback de Pagamentos</span>
        </div>
        <span className="text-xs text-slate-400 hidden sm:block">{usuario?.nome}</span>
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar
        </button>
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-50"
        >
          <LogOut className="h-3.5 w-3.5" /> Sair
        </button>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Cabeçalho */}
        <div>
          <h1 className="text-xl font-bold text-slate-800">Registrar Pagamentos</h1>
          <p className="text-sm text-slate-500 mt-1">
            Informe quem pagou para o modelo aprender e melhorar as próximas recomendações.
          </p>
        </div>

        {/* Abas */}
        <div className="flex gap-1 p-1 bg-slate-100 rounded-xl w-fit">
          {[
            { key: 'manual', label: 'Manual (um por vez)' },
            { key: 'lote',   label: 'Importar em lote'   },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => setAba(key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                aba === key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* Aba lote */}
        {aba === 'lote' && (
          <div className="grid grid-cols-5 gap-6">
            <ImportacaoLote />
          </div>
        )}

        {/* Aba manual */}
        {aba === 'manual' && <div className="grid grid-cols-5 gap-6 items-start">

          {/* Formulário */}
          <form onSubmit={enviar} className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">

            {/* CPF */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                CPF do devedor
              </label>
              <input
                type="text"
                inputMode="numeric"
                placeholder="000.000.000-00"
                value={form.cpf}
                onChange={e => set('cpf', formatarCPF(e.target.value))}
                required
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Pagou? */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                Realizou pagamento?
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { val: 'sim', label: 'Sim, pagou', color: 'emerald' },
                  { val: 'nao', label: 'Não pagou',  color: 'red'     },
                ].map(({ val, label, color }) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => set('pagou', val)}
                    className={`py-2.5 rounded-lg border text-sm font-medium transition-all ${
                      form.pagou === val
                        ? color === 'emerald'
                          ? 'bg-emerald-600 border-emerald-600 text-white shadow-sm'
                          : 'bg-red-500 border-red-500 text-white shadow-sm'
                        : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Valor recuperado — só se pagou */}
            {form.pagou === 'sim' && (
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                  Valor recuperado <span className="font-normal normal-case text-slate-400">(opcional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">R$</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0,00"
                    value={form.valor_recuperado}
                    onChange={e => set('valor_recuperado', e.target.value)}
                    className="w-full border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            {/* Data */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                Data do pagamento <span className="font-normal normal-case text-slate-400">(opcional)</span>
              </label>
              <input
                type="date"
                value={form.data_pagamento}
                max={new Date().toISOString().split('T')[0]}
                onChange={e => set('data_pagamento', e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Erro */}
            {erro && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                <p className="text-xs text-red-700">{erro}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium text-sm py-2.5 rounded-lg transition-colors"
            >
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Registrando...</>
                : <><Plus className="h-4 w-4" /> Registrar feedback</>}
            </button>
          </form>

          {/* Histórico da sessão */}
          <div className="col-span-3 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ClipboardList className="h-4 w-4 text-slate-400" />
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Registros desta sessão
                </h2>
              </div>
              {historico.length > 0 && (
                <button
                  onClick={() => setHistorico([])}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-500 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Limpar
                </button>
              )}
            </div>

            {historico.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-6">
                <ClipboardList className="h-10 w-10 text-slate-200 mb-3" />
                <p className="text-sm text-slate-400">Nenhum feedback registrado ainda.</p>
                <p className="text-xs text-slate-300 mt-1">Os registros aparecem aqui após o envio.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {historico.map((item, i) => (
                  <div key={i} className="px-5 py-3.5 flex items-center gap-4">
                    <StatusBadge ok={item.ok} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-medium text-slate-800">{item.cpf}</span>
                        <span className={`text-xs font-medium ${item.pagou ? 'text-emerald-600' : 'text-red-500'}`}>
                          {item.pagou ? '✓ Pagou' : '✗ Não pagou'}
                        </span>
                        {item.pagou && item.valor_recuperado > 0 && (
                          <span className="text-xs text-slate-500">{fmtBRL(item.valor_recuperado)}</span>
                        )}
                        {item.data_pagamento && (
                          <span className="text-xs text-slate-400">
                            {new Date(item.data_pagamento + 'T00:00:00').toLocaleDateString('pt-BR')}
                          </span>
                        )}
                      </div>
                      {item.erro_msg && (
                        <p className="text-xs text-red-500 mt-0.5">{item.erro_msg}</p>
                      )}
                      {item.ok && item.feedback_id && (
                        <p className="text-xs text-slate-300 mt-0.5 font-mono">id: {item.feedback_id}</p>
                      )}
                    </div>
                    <span className="text-xs text-slate-300 shrink-0">{item.ts}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>}

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-4 flex gap-3">
          <CheckCircle2 className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
          <div className="text-sm text-blue-700 space-y-0.5">
            <p className="font-medium">Como funciona</p>
            <p className="text-blue-600 text-xs leading-relaxed">
              Cada feedback registrado alimenta o modelo de ML e o bandit LinUCB.
              O bandit aprende quais canais e ofertas geraram pagamento e passa a priorizá-los nas próximas recomendações.
              O modelo retreina automaticamente quando acumular 30 feedbacks novos.
            </p>
          </div>
        </div>

      </main>
    </div>
  )
}
