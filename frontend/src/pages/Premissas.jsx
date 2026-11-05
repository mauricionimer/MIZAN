import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, AlertTriangle, HelpCircle, Save, SlidersHorizontal } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { buscarPremissas, gravarPremissas, listarEmpresas } from '../api'
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

// Grupos do canvas: cada cartão responde uma pergunta; premissa nova sem grupo cai em "Outras".
const GRUPOS = [
  { titulo: 'Quanto vale cobrar', sub: 'Entram no valor esperado de cada devedor e na comparação cobrar × vender.',
    chaves: ['recuperacao_se_pagar', 'comissao_especializada_pct', 'cessao_pct'] },
  { titulo: 'Quanto o devedor aguenta pagar', sub: 'Limitam a parcela proposta pela sobra do mês de cada pessoa.',
    chaves: ['buffer_margem_pct', 'comprometimento_max_pct'] },
  { titulo: 'Fila e equipe', sub: 'Como a fila é ordenada e quanto cada operador deve render por dia.',
    chaves: ['criterio_priorizacao', 'meta_contatos_dia'] },
]

function Campo({ p, valor, erro, onChange, onAjuda }) {
  const id = `prem-${p.chave}`
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={id} className="text-[13px] font-semibold text-ink-2">{p.rotulo}</label>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${p.definida ? 'bg-[var(--success-soft)] text-[var(--success)]' : 'bg-raise-2 text-ink-3'}`}>
          {p.definida ? 'Informada' : 'Padrão'}
        </span>
      </div>
      {p.tipo === 'escolha' ? (
        <select id={id} value={valor} onChange={e => onChange(e.target.value)}
          className="input-base h-[46px] rounded-[12px] px-3.5 text-[15px]">
          <option value="">Padrão: {mostraPadrao(p)}</option>
          {p.opcoes.map(o => <option key={o} value={o}>{ROTULO_ESCOLHA[o] || o}</option>)}
        </select>
      ) : (
        <div className="relative">
          <input id={id} inputMode={p.tipo === 'inteiro' ? 'numeric' : 'decimal'} value={valor} onChange={e => onChange(e.target.value)}
            placeholder={p.padrao == null ? 'não informado' : paraTela(p, p.padrao)}
            aria-invalid={!!erro} aria-describedby={erro ? `${id}-erro` : `${id}-desc`}
            className={`input-base h-[46px] rounded-[12px] pl-3.5 pr-24 text-[15px] tabular-nums ${erro ? '!border-[var(--danger)]' : ''}`} />
          <span className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-sm text-ink-3">{p.unidade || '%'}</span>
        </div>
      )}
      {erro && <p id={`${id}-erro`} className="text-xs text-[var(--danger)]">{erro}</p>}
      <p id={`${id}-desc`} className="text-xs leading-relaxed text-ink-3">
        {p.descricao}{' '}
        <button type="button" onClick={() => onAjuda(p.ajuda_id)}
          className="inline-flex items-center gap-1 font-semibold text-accent-text hover:underline">
          <HelpCircle className="h-3 w-3" aria-hidden="true" /> O que é isto?
        </button>
      </p>
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
      <div className="mx-auto w-full max-w-5xl space-y-5">
        <CabecalhoPagina rotulo="Configurações" icone={SlidersHorizontal} titulo="Política de cobrança" ajuda="como-configurar-premissas" className="!mb-0"
          subtitulo="As premissas que o MIZAN usa para calcular valor esperado, preço e fila." />

        {isComando && (
          <div>
            <label htmlFor="empresa-alvo" className="mb-1 block text-xs font-medium text-ink-2">Empresa</label>
            <select id="empresa-alvo" value={alvo} onChange={e => setAlvo(e.target.value)}
              className="input-base h-11 max-w-sm rounded-[12px] px-3.5">
              <option value="">Escolha a empresa…</option>
              {empresas.map(emp => (
                <option key={emp.empresa_id} value={emp.empresa_id}>{emp.nome_exibicao || emp.empresa_id}</option>
              ))}
            </select>
          </div>
        )}

        {erroGeral && (
          <div className="flex items-start gap-2 rounded-[14px] border border-[color-mix(in_srgb,var(--danger)_35%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-ink" role="alert">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {erroGeral}
          </div>
        )}
        {msg && (
          <div className="flex items-start gap-2 rounded-[14px] border border-[color-mix(in_srgb,var(--success)_35%,transparent)] bg-[var(--success-soft)] px-4 py-3 text-sm text-ink" role="status">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {msg}
          </div>
        )}

        {!dados && !erroGeral && !(isComando && !alvo) && (
          <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>
        )}

        {dados && (
          <form onSubmit={salvar} className="space-y-4">
            {[...GRUPOS, { titulo: 'Outras', sub: '', chaves: dados.premissas.map(p => p.chave).filter(k => !GRUPOS.some(g => g.chaves.includes(k))) }]
              .map(g => ({ ...g, itens: g.chaves.map(k => dados.premissas.find(p => p.chave === k)).filter(Boolean) }))
              .filter(g => g.itens.length)
              .map(g => (
                <section key={g.titulo} className="rounded-[22px] border border-line bg-surface px-6 py-[22px]">
                  <h2 className="text-[17px] font-semibold text-ink">{g.titulo}</h2>
                  {g.sub && <p className="mt-0.5 text-[13px] text-ink-2">{g.sub}</p>}
                  <div className="mt-4 grid gap-x-5 gap-y-5 sm:grid-cols-2">
                    {g.itens.map(p => (
                      <Campo key={p.chave} p={p} valor={texto[p.chave] ?? ''} erro={erros[p.chave]}
                        onChange={v => setTexto(t => ({ ...t, [p.chave]: v }))}
                        onAjuda={id => navigate(`/ajuda?id=${encodeURIComponent(id)}`)} />
                    ))}
                  </div>
                </section>
              ))}
            {/* Salvar no fim do conteúdo (canvas), sem cobrir os campos. */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-line bg-surface px-5 py-3.5">
              <span role="status" className={`inline-flex items-center gap-1.5 text-sm ${alteradas.length ? 'font-medium text-amber-400' : msg ? 'text-emerald-400' : 'text-ink-3'}`}>
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
