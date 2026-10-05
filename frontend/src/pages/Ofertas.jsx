// O1 — Ofertas: o catálogo da empresa, editável, e a alçada do operador.
import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Tags, Plus, Copy, Trash2, Save, Loader2, RotateCcw, ShieldAlert, Check } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import ErroCarga from '../components/ErroCarga'
import ConfirmarModal from '../components/ConfirmarModal'
import { useProtegerSaida } from '../components/protecaoSaida'
import { useAuth } from '../context/AuthContext'
import { buscarOfertas, salvarOfertas, listarEmpresas } from '../api'
import { calcularOferta, familia, NOME_FAMILIA, resumoOferta, brl } from '../utils/ofertas'

const NOVA = () => ({ id: '', nome: 'Nova oferta', descricao: '', desconto_pct: 0, entrada_pct: 0, n_parcelas: 6, juros_mensal_pct: 0, ativa: true })

function Campo({ rotulo, sufixo, value, onChange, min, max, step = 'any', inteiro = false, nota, disabled }) {
  return (
    <label className="block text-xs font-semibold text-ink-2">
      {rotulo}
      <div className="mt-1 flex items-center gap-2">
        <input type="number" inputMode={inteiro ? 'numeric' : 'decimal'} min={min} max={max} step={inteiro ? 1 : step}
          value={value} disabled={disabled} onChange={e => onChange(e.target.value)}
          className="h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-right text-sm font-normal tabular-nums text-ink disabled:opacity-50" />
        {sufixo && <span className="w-12 shrink-0 whitespace-nowrap text-xs font-normal text-ink-2">{sufixo}</span>}
      </div>
      {nota && <span className="mt-1 block text-xs font-normal text-ink-2">{nota}</span>}
    </label>
  )
}

export default function Ofertas() {
  const { token, isComando } = useAuth()
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  const [dados, setDados] = useState(null)
  const [catalogo, setCatalogo] = useState([])
  const [alcada, setAlcada] = useState({})
  const [sel, setSel] = useState(0)
  const [sujo, setSujo] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState(null)
  const [exemplo, setExemplo] = useState(5000)

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  function aplicar(d) {
    setDados(d); setCatalogo(d.catalogo.map(o => ({ ...o }))); setSel(0); setSujo(false)
    setAlcada(Object.fromEntries(Object.keys(d.campos_alcada).map(k => [k, d.alcada[k] ?? ''])))
  }

  const [erroCarga, setErroCarga] = useState(null)
  function carregar() {
    if (isComando && !alvo) { setDados(null); return }
    setErroCarga(null)
    return buscarOfertas(isComando ? alvo : undefined).then(aplicar).catch(e => setErroCarga(e))
  }
  useEffect(() => { carregar() }, [isComando, alvo])     // eslint-disable-line react-hooks/exhaustive-deps

  // Sair pelo menu, fechar ou recarregar a aba com alterações não salvas pede confirmação.
  useProtegerSaida(sujo, 'Você tem alterações não salvas nas ofertas. Deseja sair?')
  const [trocaEmpresa, setTrocaEmpresa] = useState(null)

  const atual = catalogo[sel]
  const efetiva = (o) => {
    const m = o._modo ?? (Number(o.n_parcelas) > 1 ? 'parcelado' : 'avista')
    const { _modo, ...resto } = o
    return { ...resto, n_parcelas: m === 'avista' ? 1 : Math.max(2, parseInt(o.n_parcelas, 10) || 2) }
  }
  const conta = useMemo(() => atual ? calcularOferta(exemplo, efetiva(atual)) : null, [atual, exemplo])

  function mudar(campo, valor) {
    setCatalogo(c => c.map((o, i) => i === sel ? { ...o, [campo]: valor } : o)); setSujo(true); setMsg(null)
  }
  function nova() {
    if (catalogo.length >= (dados?.max_ofertas ?? 20)) return
    setCatalogo(c => [...c, NOVA()]); setSel(catalogo.length); setSujo(true)
  }
  function duplicar() {
    if (!atual || catalogo.length >= (dados?.max_ofertas ?? 20)) return
    setCatalogo(c => [...c, { ...atual, id: '', nome: `${atual.nome} (cópia)`.slice(0, 60) }]); setSel(catalogo.length); setSujo(true)
  }
  function excluir() {
    if (catalogo.length <= 1) return
    setCatalogo(c => c.filter((_, i) => i !== sel)); setSel(0); setSujo(true)
  }

  async function salvar(extra = {}) {
    setSalvando(true); setMsg(null)
    try {
      const d = await salvarOfertas({ catalogo: catalogo.map(efetiva), alcada, ...extra }, isComando ? alvo : undefined)
      aplicar(d)
      setMsg({ tipo: 'ok', texto: extra.restaurar_padrao ? 'Voltou às ofertas padrão.' : 'Ofertas salvas. As propostas da ficha já usam este catálogo.' })
    } catch (e) { setMsg({ tipo: 'erro', erro: e }) } finally { setSalvando(false) }
  }

  // A forma fica separada do número digitado (apagar o campo de parcelas não
  // pode virar "à vista" e sumir com o campo).
  const modo = atual ? (atual._modo ?? (Number(atual.n_parcelas) > 1 ? 'parcelado' : 'avista')) : 'avista'
  const n = modo === 'avista' ? 1 : Math.max(2, parseInt(atual?.n_parcelas, 10) || 2)
  const fam = atual ? familia(n, atual.desconto_pct) : null

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
              <Tags className="h-5 w-5 text-blue-400" /> Ofertas<DicaAjuda id="catalogo-de-ofertas" />
            </h1>
            <p className="mt-1 text-sm text-ink-2">As ofertas que a equipe pode fazer e os limites do operador no simulador.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isComando && (
              <select value={alvo} onChange={e => { const v = e.target.value; if (sujo) setTrocaEmpresa(v); else setAlvo(v) }} aria-label="Empresa"
                className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            {dados && (
              <button onClick={() => salvar()} disabled={!sujo || salvando}
                className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-40">
                {salvando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} {sujo ? 'Salvar alterações' : 'Salvo'}
              </button>
            )}
          </div>
        </div>

        {isComando && !alvo && <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para editar as ofertas dela.</div>}
        <ErroCarga erro={erroCarga} onTentar={carregar} />
        <ErroCarga erro={msg?.tipo === 'erro' ? msg.erro : null} compacto />
        <AnimatePresence>
          {msg?.tipo === 'ok' && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--success)' }}>
              <Check className="h-4 w-4" /> {msg.texto}
            </motion.p>
          )}
        </AnimatePresence>
        {dados?.padrao && !sujo && (
          <p className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
            A empresa usa as 4 ofertas padrão do Mizan. Edite à vontade: ao salvar, este passa a ser o catálogo da empresa.
          </p>
        )}

        {dados && (
          <>
            <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
              <aside className="space-y-2 rounded-xl border border-line bg-surface p-3">
                <ul className="space-y-1.5">
                  {catalogo.map((o, i) => (
                    <li key={i}>
                      <button onClick={() => setSel(i)}
                        className={`w-full rounded-lg border px-3 py-2.5 text-left transition-colors ${sel === i ? 'border-blue-500/40 bg-blue-500/10' : 'border-transparent hover:bg-raise-1'} ${o.ativa ? '' : 'opacity-55'}`}>
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium text-ink">{o.nome || 'Sem nome'}</p>
                          {!o.ativa && <span className="shrink-0 rounded bg-raise-2 px-1.5 py-px text-[11px] text-ink-2">inativa</span>}
                        </div>
                        <p className="truncate text-xs text-ink-2">{resumoOferta(efetiva(o))}</p>
                      </button>
                    </li>
                  ))}
                </ul>
                <button onClick={nova} disabled={catalogo.length >= dados.max_ofertas}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-blue-500/40 px-3 py-2 text-sm font-medium text-blue-400 hover:bg-blue-500/10 disabled:opacity-40">
                  <Plus className="h-4 w-4" /> Nova oferta
                </button>
                <p className="px-1 text-[11px] text-ink-2">{catalogo.length} de {dados.max_ofertas} ofertas</p>
              </aside>

              {atual && (
                <section className="space-y-5 rounded-xl border border-line bg-surface p-5">
                  <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                    <label className="text-xs font-semibold text-ink-2">Nome
                      <input value={atual.nome} maxLength={60} onChange={e => mudar('nome', e.target.value)}
                        className="mt-1 h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm font-normal text-ink" />
                    </label>
                    <label className="flex cursor-pointer items-center gap-2 self-end rounded-lg border border-line px-3 py-2.5 text-sm text-ink">
                      <input type="checkbox" checked={atual.ativa} onChange={e => mudar('ativa', e.target.checked)} className="h-4 w-4 accent-blue-500" /> Ativa
                    </label>
                  </div>
                  <label className="block text-xs font-semibold text-ink-2">Descrição (opcional)
                    <input value={atual.descricao || ''} maxLength={160} onChange={e => mudar('descricao', e.target.value)}
                      placeholder="Ex.: campanha de fim de ano"
                      className="mt-1 h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm font-normal text-ink" />
                  </label>

                  <div className="flex gap-1.5 rounded-lg border border-line bg-surface-2 p-1" role="tablist" aria-label="Forma">
                    {[[1, 'À vista'], [6, 'Parcelado']].map(([v, l]) => {
                      const on = v === 1 ? modo === 'avista' : modo === 'parcelado'
                      return (
                        <button key={l} role="tab" aria-selected={on}
                          onClick={() => { mudar('_modo', v === 1 ? 'avista' : 'parcelado'); if (v !== 1 && (parseInt(atual.n_parcelas, 10) || 1) < 2) mudar('n_parcelas', 6) }}
                          className={`flex-1 rounded-md py-1.5 text-sm font-medium ${on ? 'bg-surface text-ink shadow-sm' : 'text-ink-2 hover:text-ink'}`}>{l}</button>
                      )
                    })}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <Campo rotulo="Desconto" sufixo="%" min={0} max={95} value={atual.desconto_pct} onChange={v => mudar('desconto_pct', v)} />
                    {modo === 'parcelado' && <Campo rotulo="Parcelas" sufixo="x" inteiro min={2} max={120} value={atual.n_parcelas} onChange={v => mudar('n_parcelas', v)} />}
                    {modo === 'parcelado' && <Campo rotulo="Entrada" sufixo="%" min={0} max={90} value={atual.entrada_pct} onChange={v => mudar('entrada_pct', v)} nota="do valor já com desconto; 0 = sem entrada" />}
                    {modo === 'parcelado' && <Campo rotulo="Juros ao mês" sufixo="% a.m." min={0} max={20} step="0.01" value={atual.juros_mensal_pct} onChange={v => mudar('juros_mensal_pct', v)} nota="tabela Price; 0 = sem juros" />}
                  </div>

                  <div className="rounded-xl border border-line bg-surface-2 p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">Prévia numa dívida de</p>
                      <div className="flex items-center gap-1.5 text-sm text-ink-2">R$
                        <input type="number" min={0} value={exemplo} onChange={e => setExemplo(e.target.value)} aria-label="Dívida de exemplo"
                          className="h-8 w-28 rounded-md border border-line bg-surface px-2 text-right text-sm tabular-nums text-ink" />
                      </div>
                    </div>
                    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {[['Valor negociado', brl(conta.valor_negociado)],
                        ...(n > 1 ? [['Entrada', brl(conta.entrada)], [`${n} parcelas de`, brl(conta.parcela)]] : [['Pagamento único', brl(conta.parcela)]]),
                        ['Total pago', brl(conta.total_pago)]].map(([k, v]) => (
                        <div key={k}><dt className="text-xs text-ink-2">{k}</dt><dd className="text-base font-semibold tabular-nums text-ink">{v}</dd></div>
                      ))}
                    </dl>
                    <p className="mt-3 text-xs text-ink-2">
                      Aprende junto com as ofertas de <strong className="font-semibold text-ink">{NOME_FAMILIA[fam]}</strong>: a chance de pagar começa pelo histórico delas.
                      {conta.juros_total > 0 && ` Juros somam ${brl(conta.juros_total)} e não contam como recuperação.`}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2 border-t border-line pt-4">
                    <button onClick={duplicar} disabled={catalogo.length >= dados.max_ofertas}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:bg-raise-2 hover:text-ink disabled:opacity-40">
                      <Copy className="h-4 w-4" /> Duplicar
                    </button>
                    <button onClick={excluir} disabled={catalogo.length <= 1}
                      className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-40">
                      <Trash2 className="h-4 w-4" /> Excluir
                    </button>
                    {!dados.padrao && (
                      <button onClick={() => window.confirm('Voltar às 4 ofertas padrão do Mizan? O catálogo atual será descartado.') && salvar({ restaurar_padrao: true, catalogo: undefined })}
                        className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-ink-2 hover:text-ink">
                        <RotateCcw className="h-4 w-4" /> Restaurar padrão
                      </button>
                    )}
                  </div>
                </section>
              )}
            </div>

            <section className="rounded-xl border border-line bg-surface p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
                <ShieldAlert className="h-4 w-4 text-amber-400" /> Alçada do operador<DicaAjuda id="alcada-do-operador" />
              </h2>
              <p className="mt-1 text-xs text-ink-2">Até onde o operador pode ir no simulador “Fazer oferta”. Fora disso, ele não consegue confirmar a oferta. Vazio = sem limite.</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[['desconto_max_pct', '%', false], ['parcelas_max', 'x', true], ['parcela_min', 'R$', false], ['juros_min_pct', '% a.m.', false]].map(([k, suf, inteiro]) => (
                  <Campo key={k} rotulo={dados.campos_alcada[k]} sufixo={suf} inteiro={inteiro} min={0} value={alcada[k] ?? ''}
                    onChange={v => { setAlcada(a => ({ ...a, [k]: v })); setSujo(true); setMsg(null) }} />
                ))}
              </div>
            </section>
          </>
        )}
      </div>
      <ConfirmarModal aberto={trocaEmpresa !== null} titulo="Trocar de empresa sem salvar?"
        texto="As alterações nas ofertas desta empresa ainda não foram salvas."
        cancelar="Continuar editando" confirmar="Trocar sem salvar" perigo
        onCancelar={() => setTrocaEmpresa(null)}
        onConfirmar={() => { setSujo(false); setAlvo(trocaEmpresa); setTrocaEmpresa(null) }} />
    </AppShell>
  )
}
