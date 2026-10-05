// F1 — painel "Distribuir fila": o admin escolhe os operadores e a fila é
// repartida em serpente pela ordem do valor esperado (docs/PLANO_OPERADOR.md).
import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Users, Loader2, Check, Shuffle } from 'lucide-react'
import { distribuirFila } from '../api'
import DicaAjuda from './DicaAjuda'
import ErroCarga from './ErroCarga'

const fmtBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)
const fmtNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0)

// Mesma conta do servidor (fila_operadores.serpentina), só para a prévia.
function contarSerpentina(n, k) {
  const c = Array(k).fill(0)
  for (let i = 0; i < n; i++) {
    const volta = Math.floor(i / k), pos = i % k
    c[volta % 2 === 0 ? pos : k - 1 - pos]++
  }
  return c
}

export default function DistribuirFila({ carteiraId, resumo, onFechar, onFeito }) {
  const operadores = resumo?.operadores ?? []
  const atuais = Object.fromEntries((resumo?.por_operador ?? []).map(g => [g.operador_id, g.devedores]))
  const temDono = (resumo?.total ?? 0) - (resumo?.sem_responsavel?.devedores ?? 0)
  const [marcados, setMarcados] = useState(() => operadores.map(o => o.id))
  const [somenteSem, setSomenteSem] = useState(temDono > 0)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')

  const base = somenteSem ? (resumo?.sem_responsavel?.devedores ?? 0) : (resumo?.total ?? 0)
  const valorBase = somenteSem
    ? (resumo?.sem_responsavel?.valor_esperado ?? 0)
    : (resumo?.por_operador ?? []).reduce((s, g) => s + g.valor_esperado, 0) + (resumo?.sem_responsavel?.valor_esperado ?? 0)
  const escolhidos = operadores.filter(o => marcados.includes(o.id))
  const partes = useMemo(() => contarSerpentina(base, escolhidos.length || 1), [base, escolhidos.length])

  function alternar(id) {
    setMarcados(m => m.includes(id) ? m.filter(x => x !== id) : [...m, id])
  }

  async function confirmar() {
    setEnviando(true); setErro('')
    try {
      const r = await distribuirFila(carteiraId, escolhidos.map(o => o.id), somenteSem)
      onFeito?.(r)
    } catch (e) {
      setErro(e)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        onClick={onFechar}>
        <motion.div initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 12, opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={e => e.stopPropagation()}
          role="dialog" aria-modal="true" aria-labelledby="distribuir-titulo"
          className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl border border-line bg-surface shadow-2xl">

          <div className="flex items-start justify-between border-b border-line px-6 py-5">
            <div>
              <h2 id="distribuir-titulo" className="flex items-center gap-2 text-base font-bold text-ink">
                <Shuffle className="h-4 w-4 text-blue-400" />
                Distribuir fila<DicaAjuda id="divisao-da-fila" />
              </h2>
              <p className="mt-1 text-xs text-ink-2">
                Cada operador recebe uma fatia com o mesmo perfil de valor: a fila é repartida em rodízio
                (1, 2, 3, 3, 2, 1…) na ordem do valor esperado.
              </p>
            </div>
            <button onClick={onFechar} aria-label="Fechar"
              className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-raise-3 hover:text-ink">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-5 overflow-y-auto px-6 py-5">
            {operadores.length === 0 ? (
              <div className="rounded-xl border border-line bg-surface-2 px-4 py-6 text-center">
                <Users className="mx-auto h-6 w-6 text-ink-2 opacity-60" />
                <p className="mt-2 text-sm font-medium text-ink">Nenhum operador ativo nesta empresa</p>
                <p className="mt-1 text-xs text-ink-2">Crie os operadores em Usuários e volte aqui.</p>
              </div>
            ) : (
              <>
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink-2">Operadores</p>
                    <button onClick={() => setMarcados(marcados.length === operadores.length ? [] : operadores.map(o => o.id))}
                      className="text-xs text-ink-2 underline hover:text-ink">
                      {marcados.length === operadores.length ? 'Desmarcar todos' : 'Marcar todos'}
                    </button>
                  </div>
                  <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
                    {operadores.map(o => {
                      const on = marcados.includes(o.id)
                      const idx = escolhidos.findIndex(e => e.id === o.id)
                      const recebe = on ? partes[idx] : 0
                      const fica = somenteSem ? (atuais[o.id] ?? 0) + recebe : recebe
                      return (
                        <li key={o.id}>
                          <label className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors ${on ? 'bg-blue-500/[0.06]' : 'hover:bg-raise-1'}`}>
                            <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${on ? 'border-blue-400 bg-blue-500 text-white' : 'border-line bg-surface-2'}`}>
                              {on && <Check className="h-3 w-3" />}
                            </span>
                            <input type="checkbox" className="sr-only" checked={on} onChange={() => alternar(o.id)} />
                            <span className="flex-1 truncate text-sm text-ink">{o.nome}</span>
                            <span className="text-right text-xs tabular-nums text-ink-2">
                              {on
                                ? <><span className="font-semibold text-ink">+{fmtNum(recebe)}</span>{somenteSem && <> · fica com {fmtNum(fica)}</>}</>
                                : somenteSem && atuais[o.id] ? <>mantém {fmtNum(atuais[o.id])}</> : '—'}
                            </span>
                          </label>
                        </li>
                      )
                    })}
                  </ul>
                </div>

                <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
                  <input type="checkbox" checked={somenteSem} onChange={e => setSomenteSem(e.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-blue-500" />
                  <span>
                    <span className="block text-sm font-medium text-ink">Só quem está sem responsável</span>
                    <span className="block text-xs text-ink-2">
                      {somenteSem
                        ? `Quem já tem dono continua com ele (${fmtNum(temDono)} devedores).`
                        : 'Refaz a divisão da carteira inteira: quem já tinha dono pode mudar de operador.'}
                    </span>
                  </span>
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-line bg-surface-2 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">Devedores a repartir</p>
                    <p className="mt-1 text-lg font-bold tabular-nums text-ink">{fmtNum(base)}</p>
                  </div>
                  <div className="rounded-xl border border-line bg-surface-2 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">Valor esperado por operador</p>
                    <p className="mt-1 text-lg font-bold tabular-nums text-ink">
                      {escolhidos.length ? <>≈ {fmtBRL(valorBase / escolhidos.length)}</> : '—'}
                    </p>
                  </div>
                </div>
              </>
            )}
            <ErroCarga erro={erro} compacto />
          </div>

          <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
            <button onClick={onFechar}
              className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink-2 transition-colors hover:bg-raise-2 hover:text-ink">
              Cancelar
            </button>
            <button onClick={confirmar} disabled={enviando || !escolhidos.length || !base}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-500 disabled:opacity-40">
              {enviando && <Loader2 className="h-4 w-4 animate-spin" />}
              {base ? `Distribuir ${fmtNum(base)} devedores` : 'Nada a distribuir'}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
