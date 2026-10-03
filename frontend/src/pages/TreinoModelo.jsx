import ThemeToggle from '../components/ThemeToggle'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Loader2, LogOut, Brain, AlertTriangle, CheckCircle2, ShieldCheck,
  UploadCloud, Undo2, Play, XCircle,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LogoMark } from '../components/Logo'
import {
  treinarModeloEmpresa, estadoTreino, listarModelosEmpresa,
  ativarModeloEmpresa, desativarModeloEmpresa,
} from '../api'
import DicaAjuda from '../components/DicaAjuda'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
const fmtData = iso => iso
  ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  : '—'
const num = (v, casas = 1) => (v == null ? '—' : Number(v).toFixed(casas))

function Cartao({ children, className = '' }) {
  return <section className={`rounded-xl border border-line bg-surface p-6 ${className}`}>{children}</section>
}

function Aviso({ tom = 'warning', children }) {
  const cor = tom === 'erro' ? 'danger' : tom === 'ok' ? 'success' : 'warning'
  return (
    <div className="flex items-start gap-2.5 rounded-xl p-3"
      style={{ background: `rgb(var(--c-${cor}) / 0.08)`, border: `1px solid rgb(var(--c-${cor}) / 0.18)` }}>
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: `var(--${cor})` }} />
      <p className="text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>{children}</p>
    </div>
  )
}

function Metricas({ m }) {
  if (!m) return null
  const linhas = [
    ['KS', 'ks', 1], ['Gini', 'gini', 1], ['AUC', 'auc', 3], ['Brier (menor é melhor)', 'brier', 3],
  ]
  const atual = m.atual || {}
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-ink-3">
            <th className="py-1.5 pr-4 font-medium">Medida (período de teste)</th>
            <th className="py-1.5 pr-4 font-medium">Modelo novo</th>
            <th className="py-1.5 font-medium">
              Modelo atual {atual.origem ? `(${atual.origem === 'proprio' ? 'próprio' : 'geral'})` : ''}
            </th>
          </tr>
        </thead>
        <tbody>
          {linhas.map(([rot, k, c]) => (
            <tr key={k} className="border-t border-line">
              <td className="py-1.5 pr-4 text-ink-2">{rot}</td>
              <td className="py-1.5 pr-4 font-semibold text-ink">{num(m.novo?.[k], c)}</td>
              <td className="py-1.5 text-ink-2">{atual.indisponivel ? '—' : num(atual[k], c)}</td>
            </tr>
          ))}
          <tr className="border-t border-line">
            <td className="py-1.5 pr-4 text-ink-2">Devedores no teste</td>
            <td className="py-1.5 pr-4 text-ink">{m.novo?.n_teste ?? '—'}</td>
            <td className="py-1.5 text-ink-2">{atual.n_teste ?? '—'}</td>
          </tr>
        </tbody>
      </table>
      {atual.indisponivel && (
        <p className="text-xs text-ink-3 mt-2">Não foi possível medir o modelo atual nesta base ({atual.indisponivel}).</p>
      )}
    </div>
  )
}

export default function TreinoModelo() {
  const navigate = useNavigate()
  const { token, usuario, logout } = useAuth()

  const [empresa, setEmpresa]   = useState('')
  const [empresas, setEmpresas] = useState([])
  const [arquivo, setArquivo]   = useState(null)
  const [job, setJob]           = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro]         = useState('')
  const [info, setInfo]         = useState('')
  const [modelos, setModelos]   = useState(null)
  const [agindo, setAgindo]     = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    fetch(`${API_URL}/comando/visao-geral`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => (r.ok ? r.json() : null))
      .then(d => setEmpresas((d?.empresas || []).map(e => e.empresa_id).filter(Boolean)))
      .catch(() => {})
    return () => clearTimeout(timer.current)
  }, [token])

  const carregarModelos = useCallback(async (emp) => {
    if (!emp.trim()) { setModelos(null); return }
    try { setModelos(await listarModelosEmpresa(token, emp.trim())) }
    catch { setModelos(null) }
  }, [token])

  useEffect(() => {
    const t = setTimeout(() => carregarModelos(empresa), 400)
    return () => clearTimeout(t)
  }, [empresa, carregarModelos])

  function acompanhar(id, emp) {
    const passo = async () => {
      try {
        const j = await estadoTreino(token, id)
        setJob(j)
        if (['concluido', 'recusado', 'falhou'].includes(j.estado)) {
          setEnviando(false)
          carregarModelos(emp)
          return
        }
      } catch (e) {
        setErro(e.message); setEnviando(false); return
      }
      timer.current = setTimeout(passo, 2500)
    }
    passo()
  }

  async function treinar(e) {
    e.preventDefault()
    setErro(''); setInfo(''); setJob(null)
    if (!empresa.trim() || !arquivo) { setErro('Informe a empresa e escolha o arquivo.'); return }
    setEnviando(true)
    try {
      const r = await treinarModeloEmpresa(token, empresa.trim(), arquivo)
      setJob({ id: r.id, estado: 'na_fila' })
      acompanhar(r.id, empresa.trim())
    } catch (e2) {
      setErro(e2.message); setEnviando(false)
    }
  }

  async function ativar(versao) {
    setAgindo(true); setErro(''); setInfo('')
    try {
      try {
        await ativarModeloEmpresa(token, empresa.trim(), versao)
      } catch (e) {
        if (e.status === 409 && window.confirm(`${e.message}\n\nAtivar mesmo assim?`)) {
          await ativarModeloEmpresa(token, empresa.trim(), versao, true)
        } else throw e
      }
      setInfo('Modelo ativado. A partir de agora as análises desta empresa usam o modelo próprio.')
      carregarModelos(empresa)
    } catch (e) { setErro(e.message) } finally { setAgindo(false) }
  }

  async function voltarAoGeral() {
    if (!window.confirm('Voltar esta empresa ao modelo geral? As versões treinadas continuam guardadas.')) return
    setAgindo(true); setErro(''); setInfo('')
    try {
      await desativarModeloEmpresa(token, empresa.trim())
      setInfo('A empresa voltou ao modelo geral.')
      carregarModelos(empresa)
    } catch (e) { setErro(e.message) } finally { setAgindo(false) }
  }

  const reg = job?.registro
  const emAndamento = job && !['concluido', 'recusado', 'falhou'].includes(job.estado)

  return (
    <div className="min-h-screen">
      <header className="navbar-glass px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/comando')} className="p-1 rounded-lg transition-colors hover:bg-raise-2" style={{ color: 'var(--ink-3)' }}>
            <ArrowLeft className="h-4 w-4" />
          </button>
          <LogoMark className="h-5 w-5 shrink-0" />
          <span className="font-bold text-ink text-sm">Mizan</span>
          <span className="text-ink-4 text-sm">/</span>
          <span className="text-sm" style={{ color: 'var(--ink-2)' }}>Treinar modelo de uma empresa</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: 'var(--ink-3)' }}>{usuario?.nome}</span>
          <ThemeToggle />
          <button onClick={() => { logout(); navigate('/login') }} className="nav-link-danger">
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10 space-y-6">
        <Cartao>
          <div className="flex items-start gap-3">
            <ShieldCheck className="h-5 w-5 mt-0.5 text-indigo-500 shrink-0" />
            <div className="space-y-2">
              <h1 className="text-lg font-bold text-ink">O que acontece com o arquivo<DicaAjuda id="treino-por-empresa" /></h1>
              <ul className="text-sm text-ink-2 space-y-1 list-disc pl-5">
                <li>O arquivo é lido na memória do servidor, usado para treinar e <b>descartado</b>. Nada dele é gravado em disco, banco ou log.</li>
                <li>CPF, nome e contatos são removidos antes de o treino começar.</li>
                <li>O que fica guardado, sem identificar ninguém: impressão digital do arquivo (SHA-256), contagens, período, métricas e o próprio modelo.</li>
                <li>O modelo vale <b>só para a empresa escolhida</b>. As demais continuam no modelo geral.</li>
                <li>Treinar não ativa nada: você confere as métricas e ativa em seguida.</li>
              </ul>
            </div>
          </div>
        </Cartao>

        <Cartao>
          <form onSubmit={treinar} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1">Empresa</label>
              <input list="empresas-lista" value={empresa} onChange={e => setEmpresa(e.target.value)}
                placeholder="ex.: goias_bank" className="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink" />
              <datalist id="empresas-lista">{empresas.map(e => <option key={e} value={e} />)}</datalist>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1">Carteira histórica (CSV ou Excel, até 25 MB)</label>
              <input type="file" accept=".csv,.xlsx,.xls" onChange={e => setArquivo(e.target.files?.[0] || null)}
                className="block w-full text-sm text-ink-2" />
              <p className="text-xs text-ink-3 mt-1.5 leading-relaxed">
                Precisa de <b>valor_divida</b>, <b>dias_em_atraso</b> e uma coluna com o <b>resultado real</b> (<b>pagou</b>: sim/não ou 1/0).
                Uma coluna de data (<b>data_referencia</b>) permite validar no tempo, que é a medida mais honesta.
                Mínimo de 300 linhas e 30 de cada resultado.
              </p>
            </div>
            <button type="submit" disabled={enviando}
              className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">
              {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              {enviando ? 'Treinando…' : 'Treinar modelo'}
            </button>
          </form>
        </Cartao>

        {erro && <Aviso tom="erro">{erro}</Aviso>}
        {info && <Aviso tom="ok">{info}</Aviso>}

        {emAndamento && (
          <Cartao>
            <div className="flex items-center gap-3 text-sm text-ink-2">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
              Treinando… isso leva de um a alguns minutos. Pode deixar a tela aberta.
            </div>
          </Cartao>
        )}
        {job?.estado === 'recusado' && <Aviso tom="erro">Arquivo recusado: {job.erro}</Aviso>}
        {job?.estado === 'falhou' && <Aviso tom="erro">{job.erro}</Aviso>}

        {reg && (
          <Cartao className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              <h2 className="font-bold text-ink">Modelo treinado — ainda não ativo</h2>
            </div>
            <p className="text-xs text-ink-3">
              {reg.n_amostras} devedores · {Math.round((reg.taxa_pagamento || 0) * 1000) / 10}% pagaram ·
              validação {reg.validacao === 'temporal' ? 'no tempo' : 'aleatória'}
              {reg.periodo ? ` · ${reg.periodo.inicio} a ${reg.periodo.fim}` : ''} · arquivo descartado
            </p>
            <Metricas m={reg.metricas} />
            {(reg.avisos || []).map((a, i) => <Aviso key={i}>{a}</Aviso>)}
          </Cartao>
        )}

        {modelos && (
          <Cartao className="space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-indigo-500" />
                <h2 className="font-bold text-ink">Modelos de {modelos.empresa_id}<DicaAjuda id="modelo-proprio-ou-geral" /></h2>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-raise-2 text-ink-2">
                Usando: {modelos.usando === 'proprio' ? `modelo próprio (${modelos.versao_ativa})` : 'modelo geral'}
              </span>
            </div>
            {modelos.versoes.length === 0 && <p className="text-sm text-ink-3">Nenhum modelo treinado para esta empresa ainda.</p>}
            {modelos.versoes.map(v => {
              const ativa = v.versao === modelos.versao_ativa
              return (
                <div key={v.versao} className="rounded-lg border border-line p-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="text-xs text-ink-2 space-y-0.5">
                    <p className="font-semibold text-ink">{v.versao} {ativa && <span className="text-emerald-500">· ativo</span>}</p>
                    <p>{fmtData(v.criado_em)} · {v.n_amostras} devedores · KS {num(v.metricas?.novo?.ks)} · AUC {num(v.metricas?.novo?.auc, 3)} · por {v.treinado_por || '—'}</p>
                  </div>
                  {!ativa && (
                    <button onClick={() => ativar(v.versao)} disabled={agindo}
                      className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-raise-2 text-ink hover:opacity-80 disabled:opacity-40">
                      <Play className="h-3.5 w-3.5" /> Ativar
                    </button>
                  )}
                </div>
              )
            })}
            {modelos.usando === 'proprio' && (
              <button onClick={voltarAoGeral} disabled={agindo}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg text-red-400 hover:bg-red-950/40 disabled:opacity-40">
                <Undo2 className="h-3.5 w-3.5" /> Voltar ao modelo geral
              </button>
            )}
          </Cartao>
        )}
      </main>
    </div>
  )
}
