import ThemeToggle from '../components/ThemeToggle'
import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2, ClipboardList, ArrowLeft, Plus, Trash2, UploadCloud, FileText, Download, LogOut } from 'lucide-react'
import { feedbackLote } from '../api'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { LogoMark } from '../components/Logo'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const EMPTY = { cpf: '', pagou: 'sim', valor_recuperado: '', data_pagamento: '' }

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
    <div className="col-span-5 space-y-5">
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
    if (!podeRegistrar) return
    const cpf = form.cpf.replace(/\D/g, '')
    if (cpf.length !== 11) { setErro('CPF inválido — informe 11 dígitos.'); return }

    setLoading(true); setErro('')
    try {
      const body = {
        cpf,
        pagou: form.pagou === 'sim',
        valor_recuperado: form.valor_recuperado ? parseFloat(form.valor_recuperado.replace(',', '.')) : 0,
      }
      if (form.data_pagamento) body.data_pagamento = form.data_pagamento

      const res = await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      const wb = data.writeback ? ` · banco externo atualizado (${data.writeback})` : ''
      setHistorico(prev => [{
        cpf: form.cpf, pagou: form.pagou === 'sim',
        valor_recuperado: body.valor_recuperado,
        data_pagamento: form.data_pagamento,
        ok: res.ok,
        feedback_id: data.feedback_id,
        writeback: data.writeback || null,
        erro_msg: res.ok ? null : (data.detail || 'Erro desconhecido'),
        ts: new Date().toLocaleTimeString('pt-BR'),
      }, ...prev])

      if (res.ok) {
        setForm(EMPTY)
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
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={voltarAoDashboard} className="transition-colors p-1 rounded-lg hover:bg-raise-2" style={{ color: 'var(--ink-3)' }}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Logo />
          <span className="font-bold text-ink text-sm">Mizan</span>
          <span className="text-ink-4 text-sm">/</span>
          <span className="text-sm" style={{ color: 'var(--ink-2)' }}>Pagamentos</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: 'var(--ink-3)' }}>{usuario?.nome}</span>
          <ThemeToggle />
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-ink tracking-tight">Pagamentos</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ink-2)' }}>
            Acompanhe e registre pagamentos da carteira.
          </p>
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
              <div className="grid grid-cols-5 gap-6">
                <ImportacaoLote token={token} />
              </div>
            )}

            {aba === 'manual' && (
              <div className="grid grid-cols-5 gap-6 items-start">
                <form onSubmit={enviar} className="col-span-2 rounded-2xl p-6 space-y-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>CPF do devedor</label>
                    <input type="text" inputMode="numeric" placeholder="000.000.000-00"
                      value={form.cpf} onChange={e => set('cpf', formatarCPF(e.target.value))}
                      required className="input-base tabular-nums" />
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

                  {form.pagou === 'sim' && (
                    <div>
                      <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                        Valor recuperado <span className="font-normal text-ink-4">(opcional)</span>
                      </label>
                      <div className="relative">
                        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-4 text-sm">R$</span>
                        <input type="number" min="0" step="0.01" placeholder="0,00"
                          value={form.valor_recuperado} onChange={e => set('valor_recuperado', e.target.value)}
                          className="input-base pl-9" />
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                      Data do pagamento <span className="font-normal text-ink-4">(opcional)</span>
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

                <div className="col-span-3 rounded-2xl overflow-hidden" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
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
                      <p className="text-xs text-ink-4 mt-1">Os registros aparecem aqui após o envio.</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-line">
                      {historico.map((item, i) => (
                        <div key={i} className="px-5 py-3.5 flex items-center gap-4">
                          <StatusBadge ok={item.ok} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 flex-wrap">
                              <span className="tabular-nums text-sm font-semibold text-ink">{item.cpf}</span>
                              <span className={`text-xs font-semibold ${item.pagou ? 'text-emerald-400' : 'text-red-400'}`}>
                                {item.pagou ? '✓ Pagou' : '✗ Não pagou'}
                              </span>
                              {item.pagou && item.valor_recuperado > 0 && (
                                <span className="text-xs text-ink-2">{fmtBRL(item.valor_recuperado)}</span>
                              )}
                            </div>
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

        <div className="rounded-2xl px-5 py-4 flex gap-3" style={{ background: 'rgb(var(--c-royal) / 0.08)', border: '1px solid rgb(var(--c-royal) / 0.18)' }}>
          <CheckCircle2 className="h-5 w-5 text-blue-300 shrink-0 mt-0.5" />
          <div className="text-sm text-blue-200 space-y-0.5">
            <p className="font-semibold">Como funciona</p>
            <p className="text-blue-300/90 text-xs leading-relaxed">
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
