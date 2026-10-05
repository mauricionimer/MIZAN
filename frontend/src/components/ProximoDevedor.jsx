// P4 — depois de registrar um atendimento, leva direto ao próximo devedor da
// fila de quem atendeu, sem passar pela lista.
import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, Loader2, X } from 'lucide-react'
import ErroCarga from './ErroCarga'
import { buscarDistribuicao, buscarPaginaRanking } from '../api'

const PAGINA = 10
const MAX_PAGINAS = 5       // até 50 devedores à frente; quem já pagou não é "próximo"

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v || 0)

// O operador com a fila dividida segue a dele; sem divisão (ou administrador),
// a fila da carteira. Falha ao descobrir isso NÃO cai na fila inteira: o
// "próximo" seria de outro operador.
async function acharProximo({ carteiraId, rankAtual, doOperador, pagos }) {
  let escopo
  if (doOperador) {
    const dist = await buscarDistribuicao(carteiraId)
    if (dist.ativo && dist.meus > 0) escopo = 'me'
  }
  let apos = rankAtual
  for (let i = 0; i < MAX_PAGINAS; i++) {
    const p = await buscarPaginaRanking(carteiraId, { apos_rank: apos, limit: PAGINA, responsavel: escopo })
    const itens = p.itens ?? []
    const proximo = itens.find(x => !pagos?.has(String(x.cpf)))
    if (proximo) return { devedor: proximo, escopo }
    if (itens.length < PAGINA) break
    apos = itens[itens.length - 1].rank
  }
  return { devedor: null, escopo }
}

export default function ProximoDevedor({ carteiraId, rankAtual, doOperador, pagos, onIr, onVoltar, onFechar }) {
  const [estado, setEstado] = useState({ carregando: true })

  const procurar = useCallback(async () => {
    setEstado({ carregando: true })
    try {
      setEstado({ ...(await acharProximo({ carteiraId, rankAtual, doOperador, pagos })) })
    } catch (e) { setEstado({ erro: e }) }
  }, [carteiraId, rankAtual, doOperador, pagos])
  useEffect(() => { procurar() }, [procurar])

  const { carregando, erro, devedor, escopo } = estado
  const minha = escopo === 'me'
  return (
    <div className="sticky bottom-3 z-30 mt-5" role="status" aria-live="polite">
      <div className="rounded-2xl p-3.5 shadow-xl sm:p-4" style={{ background: 'var(--surface)', border: '1px solid rgb(var(--c-success) / 0.35)' }}>
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--success)' }} aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>Atendimento registrado.</p>
            {carregando && (
              <p className="mt-0.5 flex items-center gap-1.5 text-xs" style={{ color: 'var(--ink-2)' }}>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Procurando o próximo da {minha ? 'sua ' : ''}fila…
              </p>
            )}
            {!carregando && !erro && devedor && (
              <p className="mt-0.5 text-sm" style={{ color: 'var(--ink-2)' }}>
                Próximo da {minha ? 'sua ' : ''}fila: <strong className="font-semibold" style={{ color: 'var(--ink)' }}>{devedor.nome}</strong>
                <span className="tabular-nums"> · #{devedor.rank} · {fmtBRL(devedor.valor_divida)}</span>
              </p>
            )}
            {!carregando && !erro && !devedor && (
              <p className="mt-0.5 text-sm" style={{ color: 'var(--ink-2)' }}>Não há mais devedores em aberto na {minha ? 'sua ' : ''}fila depois deste.</p>
            )}
          </div>
          <button type="button" onClick={onFechar} aria-label="Dispensar aviso"
            className="-m-1.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg" style={{ color: 'var(--ink-2)' }}>
            <X className="h-4 w-4" />
          </button>
        </div>
        {erro && <ErroCarga erro={erro} onTentar={procurar} compacto className="mt-3" />}
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onVoltar} className="btn-secondary min-h-[44px]">Voltar à fila</button>
          {devedor && (
            <button type="button" onClick={() => onIr(devedor.rank)} className="btn-primary min-h-[44px]">
              Próximo devedor da {minha ? 'minha ' : ''}fila <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
