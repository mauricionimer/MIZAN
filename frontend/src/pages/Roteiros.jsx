// F4 — Roteiros: mensagens padrão por canal, com variáveis e prévia ao vivo.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquareText, Plus, Copy, Trash2, Save, Loader2, Building2, User, Sparkles, Check, AlertTriangle } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import ErroCarga from '../components/ErroCarga'
import ConfirmarModal, { useConfirmar } from '../components/ConfirmarModal'
import { useProtegerSaida } from '../components/protecaoSaida'
import { useAuth } from '../context/AuthContext'
import { listarRoteiros, salvarRoteiro, apagarRoteiro, listarEmpresas } from '../api'
import { VARIAVEIS, CANAIS, OFERTAS, OFERTA_LABEL, EXEMPLO, dadosParaRoteiro, preencher, desconhecidas } from '../utils/roteiros'

const NOVO = (canal) => ({ id: null, titulo: '', canal, oferta: '', texto: '', escopo: 'pessoal' })
// O que conta como "mexeu no roteiro": comparar com o que foi carregado.
const chave = (f) => JSON.stringify([f.titulo, f.oferta || '', f.texto, f.escopo])

function Grupo({ titulo, icone: Icone, itens, ativo, onEscolher, vazio }) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 px-1 text-[11px] font-semibold uppercase tracking-wider text-ink-2">
        <Icone className="h-3 w-3" /> {titulo}
      </p>
      {itens.length === 0 ? <p className="px-1 pb-2 text-xs text-ink-2 opacity-70">{vazio}</p> : (
        <ul className="space-y-1">
          {itens.map(r => (
            <li key={r.id}>
              <button onClick={() => onEscolher(r)}
                className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${ativo === r.id ? 'border-blue-500/40 bg-blue-500/10' : 'border-transparent hover:bg-raise-1'}`}>
                <p className="truncate text-sm font-medium text-ink">{r.titulo}</p>
                <p className="truncate text-xs text-ink-2">{r.oferta ? OFERTA_LABEL[r.oferta] : 'Qualquer oferta'}</p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Previa({ canal, texto, oferta, empresa, operador }) {
  const prop = EXEMPLO.propostas[oferta] ?? EXEMPLO.propostas.avista_10pct
  const { texto: pronto, faltando } = preencher(texto, dadosParaRoteiro({ devedor: EXEMPLO.devedor, proposta: prop, empresa, operador }))
  const balao = canal === 'whatsapp'
    ? 'ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-emerald-600 px-3.5 py-2.5 text-white'
    : canal === 'sms' ? 'ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-blue-600 px-3.5 py-2.5 text-white'
    : 'rounded-xl border border-line bg-surface px-4 py-3 text-ink'
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-4">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-2">
        Prévia · {canal === 'telefone' ? 'roteiro de fala' : 'como chega'} · devedor de exemplo
      </p>
      {texto.trim() ? (
        <div className={`${balao} whitespace-pre-wrap text-sm leading-relaxed`}>{pronto}</div>
      ) : <p className="text-xs text-ink-2">Escreva o texto para ver a prévia.</p>}
      {faltando.length > 0 && (
        <p className="mt-2 text-xs text-ink-2">Sem valor no exemplo: {faltando.join(', ')}.</p>
      )}
    </div>
  )
}

export default function Roteiros() {
  const { token, usuario, isAdmin, isComando, empresaConfig } = useAuth()
  const [canal, setCanal] = useState('whatsapp')
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [form, setForm] = useState(NOVO('whatsapp'))
  const [base, setBase] = useState(chave(NOVO('whatsapp')))
  const [pendente, setPendente] = useState(null)     // ação à espera de "Descartar o rascunho?"
  const { pedir: pedirConfirmacao, modal: modalConfirmar } = useConfirmar()
  function carregarForm(f) { setForm(f); setBase(chave(f)) }
  const [somenteLeitura, setSomenteLeitura] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState(null)        // {tipo: 'ok', texto} | {tipo: 'erro', erro}
  const [erroCarga, setErroCarga] = useState(null)
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  const area = useRef(null)
  const cursor = useRef(null)          // onde o cursor fica depois de inserir uma variável
  const empresaNome = empresaConfig?.nome_exibicao || 'sua empresa'

  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])

  function carregar(manterId) {
    if (isComando && !alvo) { setDados(null); setCarregando(false); return }
    setCarregando(true); setErroCarga(null)
    return listarRoteiros({ canal, empresa_id: isComando ? alvo : undefined })
      .then(d => {
        setDados(d)
        if (manterId) {
          const r = d.roteiros.find(x => x.id === manterId)
          if (r) escolher(r, false)
        }
      })
      .catch(e => setErroCarga(e))
      .finally(() => setCarregando(false))
  }
  useEffect(() => { carregarForm(NOVO(canal)); setSomenteLeitura(isComando); setMsg(null); carregar() }, [canal, alvo])   // eslint-disable-line react-hooks/exhaustive-deps

  const daEmpresa = (dados?.roteiros ?? []).filter(r => !r.dono_id)
  const meus = (dados?.roteiros ?? []).filter(r => r.dono_id)
  const padroes = dados?.padroes ?? []

  function escolher(r, limparAviso = true) {
    if (limparAviso) setMsg(null)
    const podeEditar = !isComando && !r.padrao && (r.dono_id ? true : isAdmin)
    setSomenteLeitura(!podeEditar)
    carregarForm({ id: r.padrao ? null : r.id, titulo: r.titulo, canal: r.canal, oferta: r.oferta || '', texto: r.texto,
              escopo: r.dono_id ? 'pessoal' : 'empresa', padrao: !!r.padrao, origem: r.id })
  }

  // Sem rascunho, a ação acontece direto; com rascunho, pergunta antes.
  const sujo = !somenteLeitura && chave(form) !== base
  useProtegerSaida(sujo, 'Você tem um roteiro não salvo. Deseja sair?')
  function pedir(acao) { if (sujo) setPendente(() => acao); else acao() }

  function duplicar() {
    setMsg({ tipo: 'ok', texto: 'Cópia criada: ajuste e salve.' })
    setSomenteLeitura(false)
    setForm(f => ({ ...f, id: null, padrao: false, origem: null, escopo: 'pessoal',
                    titulo: f.titulo.length > 72 ? f.titulo.slice(0, 72) : `${f.titulo} (cópia)` }))
  }

  function inserir(chave) {
    const el = area.current
    const tag = `{${chave}}`
    if (!el) { setForm(f => ({ ...f, texto: f.texto + tag })); return }
    const ini = el.selectionStart ?? form.texto.length, fim = el.selectionEnd ?? ini
    const novo = form.texto.slice(0, ini) + tag + form.texto.slice(fim)
    cursor.current = ini + tag.length
    setForm(f => ({ ...f, texto: novo }))
  }
  // Na mesma renderização em que o texto muda, antes da próxima tecla: o
  // cursor vai para logo depois da variável (o botão não tira o foco).
  useLayoutEffect(() => {
    if (cursor.current == null || !area.current) return
    area.current.focus()
    area.current.setSelectionRange(cursor.current, cursor.current)
    cursor.current = null
  }, [form.texto])

  const erradas = useMemo(() => desconhecidas(form.texto), [form.texto])
  const podeSalvar = !somenteLeitura && form.titulo.trim().length >= 2 && form.texto.trim().length >= 5 && !erradas.length && dados?.ativo

  async function salvar() {
    setSalvando(true); setMsg(null)
    try {
      const r = await salvarRoteiro({ titulo: form.titulo, canal, oferta: form.oferta || null, texto: form.texto, escopo: form.escopo }, form.id)
      setMsg({ tipo: 'ok', texto: form.id ? 'Roteiro atualizado.' : 'Roteiro salvo.' })
      // Salvo é salvo: não depende da lista recarregada trazer o roteiro de volta.
      carregarForm({ ...form, id: r.roteiro.id, origem: r.roteiro.id, padrao: false })
      carregar(r.roteiro.id)
    } catch (e) { setMsg({ tipo: 'erro', erro: e }) } finally { setSalvando(false) }
  }

  async function excluir() {
    if (!form.id) return
    const ok = await pedirConfirmacao({ titulo: `Excluir o roteiro “${form.titulo}”?`,
      texto: 'Ele deixa de aparecer para quem o usa. Não dá para desfazer.', confirmar: 'Excluir', perigo: true })
    if (!ok) return
    try {
      await apagarRoteiro(form.id)
      carregarForm(NOVO(canal)); setMsg({ tipo: 'ok', texto: 'Roteiro excluído.' }); carregar()
    } catch (e) { setMsg({ tipo: 'erro', erro: e }) }
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
              <MessageSquareText className="h-5 w-5 text-blue-400" /> Roteiros<DicaAjuda id="roteiros-de-abordagem" />
            </h1>
            <p className="mt-1 text-sm text-ink-2">Mensagens prontas por canal. Na ficha do devedor elas saem preenchidas com o nome, a dívida e a proposta.</p>
          </div>
          {isComando && (
            <select value={alvo} onChange={e => { const v = e.target.value; pedir(() => setAlvo(v)) }} aria-label="Empresa"
              className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
              <option value="">Escolha a empresa…</option>
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
            </select>
          )}
        </div>

        <div className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface-2 p-1" role="tablist" aria-label="Canal">
          {CANAIS.map(c => (
            <button key={c.k} role="tab" aria-selected={canal === c.k} onClick={() => { if (c.k !== canal) pedir(() => setCanal(c.k)) }}
              className={`relative flex-1 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${canal === c.k ? 'text-ink' : 'text-ink-2 hover:text-ink'}`}>
              {canal === c.k && <motion.span layoutId="aba-canal" className="absolute inset-0 rounded-lg bg-surface shadow-sm" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
              <span className="relative">{c.label}</span>
            </button>
          ))}
        </div>

        {isComando && !alvo && <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver os roteiros dela.</div>}
        <ErroCarga erro={erroCarga} ocupado={carregando} onTentar={() => carregar()} />
        {dados && dados.ativo === false && (
          <p className="flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {dados.mensagem} Enquanto isso, valem os modelos do Mizan.
          </p>
        )}

        {dados && (
          <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
            <aside className="space-y-4 rounded-xl border border-line bg-surface p-3 lg:max-h-[640px] lg:overflow-y-auto">
              {!isComando && (
                <button onClick={() => pedir(() => { carregarForm({ ...NOVO(canal), escopo: isAdmin ? 'empresa' : 'pessoal' }); setSomenteLeitura(false); setMsg(null) })}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-blue-500/40 px-3 py-2 text-sm font-medium text-blue-400 hover:bg-blue-500/10">
                  <Plus className="h-4 w-4" /> Novo roteiro
                </button>
              )}
              <Grupo titulo="Da empresa" icone={Building2} itens={daEmpresa} ativo={form.origem} onEscolher={r => pedir(() => escolher(r))}
                vazio={isAdmin ? 'Crie os roteiros que toda a equipe usa.' : 'O administrador ainda não criou.'} />
              {!isComando && <Grupo titulo="Meus" icone={User} itens={meus} ativo={form.origem} onEscolher={r => pedir(() => escolher(r))} vazio="Só você vê os seus." />}
              <Grupo titulo="Modelos do Mizan" icone={Sparkles} itens={padroes} ativo={form.origem} onEscolher={r => pedir(() => escolher(r))} vazio="" />
            </aside>

            <section className="space-y-4 rounded-xl border border-line bg-surface p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="section-label">
                  {form.padrao ? 'Modelo do Mizan' : form.id ? 'Editar roteiro' : 'Novo roteiro'}
                  {somenteLeitura && <span className="ml-2 rounded-full bg-raise-2 px-2 py-0.5 text-xs font-medium text-ink-2">só leitura</span>}
                </p>
                {carregando && <Loader2 className="h-4 w-4 animate-spin text-ink-2" />}
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-ink-2">Título
                  <input value={form.titulo} disabled={somenteLeitura} maxLength={80} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}
                    placeholder="Ex.: Primeiro contato, à vista"
                    className="mt-1 h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm font-normal text-ink disabled:opacity-70" />
                </label>
                <label className="text-xs font-semibold text-ink-2">Oferta
                  <select value={form.oferta} disabled={somenteLeitura} onChange={e => setForm(f => ({ ...f, oferta: e.target.value }))}
                    className="mt-1 h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm font-normal text-ink disabled:opacity-70 [color-scheme:dark]">
                    <option value="">Qualquer oferta</option>
                    {OFERTAS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </label>
              </div>

              {isAdmin && !somenteLeitura && !form.id && (
                <div className="flex gap-2 text-xs">
                  {[['empresa', 'Da empresa (toda a equipe usa)'], ['pessoal', 'Só meu']].map(([k, l]) => (
                    <label key={k} className={`flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 ${form.escopo === k ? 'border-blue-500/40 bg-blue-500/10 text-ink' : 'border-line text-ink-2'}`}>
                      <input type="radio" name="escopo" className="sr-only" checked={form.escopo === k} onChange={() => setForm(f => ({ ...f, escopo: k }))} /> {l}
                    </label>
                  ))}
                </div>
              )}

              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <span className="text-xs font-semibold text-ink-2">Texto</span>
                  <span className={`text-xs tabular-nums ${form.texto.length > 2000 ? 'text-red-400' : 'text-ink-2'}`}>{form.texto.length}/2000</span>
                </div>
                {!somenteLeitura && (
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {VARIAVEIS.map(([k, l]) => (
                      <button key={k} type="button" onMouseDown={e => e.preventDefault()} onClick={() => inserir(k)} title={`Insere {${k}}`}
                        className="rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-300 hover:bg-blue-500/20">
                        + {l}
                      </button>
                    ))}
                  </div>
                )}
                <textarea ref={area} value={form.texto} disabled={somenteLeitura} rows={7} maxLength={2000}
                  onChange={e => setForm(f => ({ ...f, texto: e.target.value }))}
                  placeholder="Olá, {primeiro_nome}! Aqui é {operador}, da {empresa}…"
                  className="w-full resize-y rounded-lg border border-line bg-surface-2 px-3 py-2.5 font-mono text-[13px] leading-relaxed text-ink disabled:opacity-70" />
                {erradas.length > 0 && (
                  <p className="mt-1 text-xs text-red-400">Variável desconhecida: {erradas.map(v => `{${v}}`).join(', ')}. Use os botões acima.</p>
                )}
              </div>

              <Previa canal={canal} texto={form.texto} oferta={form.oferta} empresa={empresaNome} operador={usuario?.nome} />

              <ErroCarga erro={msg?.tipo === 'erro' ? msg.erro : null} compacto />
              <AnimatePresence>
                {msg?.tipo === 'ok' && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--success)' }}>
                    <Check className="h-4 w-4" /> {msg.texto}
                  </motion.p>
                )}
              </AnimatePresence>

              {!isComando && (
                <div className="flex flex-wrap gap-2 border-t border-line pt-4">
                  {!somenteLeitura && (
                    <button onClick={salvar} disabled={!podeSalvar || salvando} className="btn-primary">
                      {salvando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Salvar
                    </button>
                  )}
                  {(form.id || form.padrao || somenteLeitura) && form.texto && (
                    <button onClick={duplicar} className="btn-secondary">
                      <Copy className="h-4 w-4" /> {form.padrao || somenteLeitura ? 'Usar como base' : 'Duplicar'}
                    </button>
                  )}
                  {form.id && !somenteLeitura && (
                    <button onClick={excluir} className="btn-ghost-danger ml-auto">
                      <Trash2 className="h-4 w-4" /> Excluir
                    </button>
                  )}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
      <ConfirmarModal aberto={!!pendente} titulo="Descartar o rascunho?"
        texto="O texto deste roteiro ainda não foi salvo e será perdido."
        cancelar="Continuar editando" confirmar="Descartar" perigo
        onCancelar={() => setPendente(null)}
        onConfirmar={() => { const a = pendente; setBase(chave(form)); setPendente(null); a() }} />
      {modalConfirmar}
    </AppShell>
  )
}
