import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, AlertTriangle, HelpCircle, Save } from 'lucide-react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { buscarPremissas, gravarPremissas, listarEmpresas } from '../api'
import DicaAjuda from '../components/DicaAjuda'
import { useProtegerSaida } from '../components/protecaoSaida'

const ROTULO_ESCOLHA = {
  valor_esperado: 'Maior valor esperado (recupera mais)',
  proporcional_por_grupo: 'Proporcional por região (reparte o esforço)',
}

// O que a pessoa digita ↔ o que o servidor guarda. Fração (0–1) aparece em %.
const paraTela = (p, v) => {
  if (v == null) return ''
  if (p.tipo === 'escolha') return v
  return String(Math.round(v * p.escala_ui * 1e6) / 1e6).replace('.', ',')
}
const doServidor = (p, txt) => {
  if (p.tipo === 'escolha') return txt === '' ? null : txt
  const t = String(txt).trim()
  if (t === '') return null
  const n = Number(t.replace(',', '.'))
  return Number.isFinite(n) ? n / p.escala_ui : t        // texto inválido segue; o servidor recusa e diz por quê
}
const mostraPadrao = (p) => (p.padrao == null ? 'não informado' : p.tipo === 'escolha'
  ? ROTULO_ESCOLHA[p.padrao] || p.padrao : `${paraTela(p, p.padrao)}${p.unidade === '%' || !p.unidade ? '%' : ` ${p.unidade}`}`)

function Campo({ p, valor, erro, onChange, onAjuda }) {
  const id = `prem-${p.chave}`
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <label htmlFor={id} className="text-sm font-semibold text-ink">{p.rotulo}</label>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${p.definida ? 'bg-emerald-500/15 text-emerald-500' : 'bg-raise-2 text-ink-3'}`}>
          {p.definida ? 'Informada' : 'Padrão'}
        </span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-ink-2">{p.descricao}</p>

      <div className="mt-3 flex items-center gap-2">
        {p.tipo === 'escolha' ? (
          <select id={id} value={valor} onChange={e => onChange(e.target.value)}
            className="h-10 w-full max-w-sm rounded-lg border border-line bg-page px-3 text-sm text-ink">
            <option value="">Padrão: {mostraPadrao(p)}</option>
            {p.opcoes.map(o => <option key={o} value={o}>{ROTULO_ESCOLHA[o] || o}</option>)}
          </select>
        ) : (
          <>
            <input id={id} inputMode={p.tipo === 'inteiro' ? 'numeric' : 'decimal'} value={valor} onChange={e => onChange(e.target.value)}
              placeholder={p.padrao == null ? 'não informado' : paraTela(p, p.padrao)}
              aria-invalid={!!erro} aria-describedby={erro ? `${id}-erro` : undefined}
              className={`h-10 w-32 rounded-lg border bg-page px-3 text-right text-sm text-ink ${erro ? 'border-red-500/60' : 'border-line'}`} />
            <span className="text-sm text-ink-2">{p.unidade || '%'}</span>
          </>
        )}
      </div>
      {erro && <p id={`${id}-erro`} className="mt-1.5 text-xs text-red-400">{erro}</p>}

      <div className="mt-3 flex flex-wrap items-center justify-end gap-2 text-[11px] text-ink-3">
        <button type="button" onClick={() => onAjuda(p.ajuda_id)}
          className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300">
          <HelpCircle className="h-3.5 w-3.5" /> O que é isto?
        </button>
      </div>
    </div>
  )
}

export default function Premissas() {
  const { token, isComando } = useAuth()
  const { result, setVista } = useAnalysis()
  const navigate = useNavigate()

  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo]         = useState('')
  const [dados, setDados]       = useState(null)
  const [texto, setTexto]       = useState({})
  const [erros, setErros]       = useState({})
  const [msg, setMsg]           = useState('')
  const [erroGeral, setErroGeral] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(r => setEmpresas(r?.empresas || [])).catch(() => {})
  }, [isComando, token])

  const carregar = useCallback(async (empresa) => {
    if (isComando && !empresa) { setDados(null); return }
    setErroGeral(''); setErros({}); setMsg('')
    try {
      const r = await buscarPremissas(token, isComando ? empresa : undefined)
      setDados(r)
      setTexto(Object.fromEntries(r.premissas.map(p => [p.chave, p.definida ? paraTela(p, p.valor) : ''])))
    } catch (e) { setErroGeral(e.message); setDados(null) }
  }, [isComando, token])

  useEffect(() => { carregar(alvo) }, [alvo, carregar])

  const mudou = (p) => texto[p.chave] !== (p.definida ? paraTela(p, p.valor) : '')
  const alteradas = dados ? dados.premissas.filter(mudou) : []
  // Igual a Ofertas: sair (menu, aba, voltar, fechar a aba) com alteração pendente pergunta antes.
  useProtegerSaida(alteradas.length > 0, 'Você tem alterações não salvas na política de cobrança. Deseja sair?')
  const descartar = () => {
    setErros({}); setErroGeral('')
    setTexto(Object.fromEntries(dados.premissas.map(p => [p.chave, p.definida ? paraTela(p, p.valor) : ''])))
  }

  async function salvar(e) {
    e.preventDefault()
    setSalvando(true); setErros({}); setErroGeral(''); setMsg('')
    try {
      const valores = Object.fromEntries(alteradas.map(p => [p.chave, doServidor(p, texto[p.chave])]))
      const r = await gravarPremissas(token, valores, isComando ? alvo : undefined)
      setDados(r)
      setTexto(Object.fromEntries(r.premissas.map(p => [p.chave, p.definida ? paraTela(p, p.valor) : ''])))
      setMsg('Política de cobrança salva. Vale para as próximas análises; as carteiras já analisadas não mudam.')
    } catch (e2) {
      if (e2.erros) setErros(e2.erros)
      setErroGeral(e2.message)
    } finally { setSalvando(false) }
  }

  return (
    <AppShell secao="premissas" onIrPara={setVista} temResultado={!!result} titulo="Política de cobrança">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div>
          <p className="section-label">Configuração da empresa</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Política de cobrança<DicaAjuda id="como-configurar-premissas" /></h1>
        </div>

        {isComando && (
          <div>
            <label htmlFor="empresa-alvo" className="mb-1 block text-xs font-medium text-ink-2">Empresa</label>
            <select id="empresa-alvo" value={alvo} onChange={e => setAlvo(e.target.value)}
              className="h-10 w-full max-w-sm rounded-lg border border-line bg-surface px-3 text-sm text-ink">
              <option value="">Escolha a empresa…</option>
              {empresas.map(emp => (
                <option key={emp.empresa_id} value={emp.empresa_id}>{emp.nome_exibicao || emp.empresa_id}</option>
              ))}
            </select>
          </div>
        )}

        {erroGeral && (
          <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300" role="alert">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {erroGeral}
          </div>
        )}
        {msg && (
          <div className="flex items-start gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300" role="status">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {msg}
          </div>
        )}

        {!dados && !erroGeral && !(isComando && !alvo) && (
          <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
        )}

        {dados && (
          <form onSubmit={salvar} className="space-y-4">
            {dados.premissas.map(p => (
              <Campo key={p.chave} p={p} valor={texto[p.chave] ?? ''} erro={erros[p.chave]}
                onChange={v => setTexto(t => ({ ...t, [p.chave]: v }))}
                onAjuda={id => navigate(`/ajuda?id=${encodeURIComponent(id)}`)} />
            ))}
            <div className="sticky bottom-4 flex items-center justify-between gap-3 rounded-xl border border-line bg-surface p-3 shadow-lg">
              <span role="status" className={`inline-flex items-center gap-1.5 text-xs ${alteradas.length ? 'font-medium text-amber-400' : msg ? 'text-emerald-400' : 'text-ink-3'}`}>
                {alteradas.length
                  ? <><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> {alteradas.length === 1 ? '1 alteração não salva' : `${alteradas.length} alterações não salvas`}</>
                  : msg ? <><CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Tudo salvo</> : 'Nada alterado'}
              </span>
              <div className="flex items-center gap-2">
                {alteradas.length > 0 && !salvando && (
                  <button type="button" onClick={descartar} className="btn-ghost btn-sm">Descartar</button>
                )}
                <button type="submit" disabled={salvando || !alteradas.length}
                  className="btn-primary">
                  {salvando ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando…</> : <><Save className="h-4 w-4" /> Salvar</>}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </AppShell>
  )
}
