// Ficha da passagem para a equipe (docs/PLANO_PASSAGEM_EQUIPE.md): o que a pessoa
// da equipe precisa ver de relance quando o agente passa o caso.
import { useState } from 'react'
import { ThumbsUp, ThumbsDown, Lightbulb, History, Wallet, Loader2 } from 'lucide-react'
import { agentePassagemRetorno } from '../api'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)

export const NIVEL_PASSAGEM = {
  urgente: { rotulo: 'Urgente', cor: '#f87171', fundo: 'rgba(248,113,113,.12)' },
  alta: { rotulo: 'Alta', cor: '#fbbf24', fundo: 'rgba(251,191,36,.12)' },
  normal: { rotulo: 'Normal', cor: '#94a3b8', fundo: 'rgba(148,163,184,.12)' },
}

const EMOCAO = { calmo: 'calma', ansioso: 'ansiosa', irritado: 'irritada', triste: 'triste', desesperado: 'desesperada' }

export function SeloPrioridade({ passagem }) {
  if (!passagem) return null
  const n = NIVEL_PASSAGEM[passagem.nivel] || NIVEL_PASSAGEM.normal
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{ background: n.fundo, color: n.cor }} title={`Prioridade ${passagem.prioridade} de 100`}>
      {n.rotulo}
      {passagem.emocao && passagem.emocao !== 'calmo' && <span className="font-normal">· {EMOCAO[passagem.emocao]}</span>}
    </span>
  )
}

export default function FichaPassagem({ passagem, predicaoId, empresaId }) {
  const [retorno, setRetorno] = useState(passagem?.retorno || null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  if (!passagem) return null
  const s = passagem.sugestao

  async function avaliar(ajudou) {
    setEnviando(true); setErro('')
    try { setRetorno(await agentePassagemRetorno(predicaoId, ajudou, '', empresaId)) }
    catch { setErro('Não deu para salvar agora.') }
    finally { setEnviando(false) }
  }

  return (
    <div className="mt-2 space-y-1.5 rounded-lg border border-line bg-surface-2 p-2.5 text-xs">
      {passagem.situacao && <p className="text-ink">{passagem.situacao}</p>}
      {passagem.o_que_quer && <p className="text-ink-2"><span className="font-medium text-ink">Quer: </span>{passagem.o_que_quer}</p>}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-ink-2">
        {passagem.valor_dito > 0 && (
          <span className="inline-flex items-center gap-1"><Wallet className="h-3 w-3" /> Consegue <b className="text-ink tabular-nums">{fmtBRL(passagem.valor_dito)}</b>/mês</span>
        )}
        {passagem.tentado?.length > 0 && (
          <span className="inline-flex items-center gap-1"><History className="h-3 w-3" /> Já oferecido: {passagem.tentado.slice(-3).map(t => t.resumo).join(' · ')}</span>
        )}
      </div>
      {s && (
        <p className="flex items-start gap-1.5 rounded-md px-2 py-1.5" style={{ background: 'rgba(59,130,246,.10)' }}>
          <Lightbulb className="mt-px h-3.5 w-3.5 shrink-0 text-blue-400" />
          <span><b className="text-ink">Sugestão: {s.resumo}</b> <span className="text-ink-2">— {s.motivo}</span></span>
        </p>
      )}
      {passagem.proximo_passo && <p className="text-ink-2"><span className="font-medium text-ink">Primeiro passo: </span>{passagem.proximo_passo}</p>}
      {predicaoId && (
        <div className="flex items-center gap-2 pt-0.5 text-ink-2">
          {retorno ? (
            <span>Resumo {retorno.ajudou ? 'ajudou' : 'não ajudou'} · obrigado</span>
          ) : (
            <>
              <span>O resumo ajudou?</span>
              <button disabled={enviando} onClick={() => avaliar(true)} aria-label="Ajudou"
                className="rounded p-1 hover:bg-raise-2 hover:text-emerald-400 disabled:opacity-40"><ThumbsUp className="h-3.5 w-3.5" /></button>
              <button disabled={enviando} onClick={() => avaliar(false)} aria-label="Não ajudou"
                className="rounded p-1 hover:bg-raise-2 hover:text-red-400 disabled:opacity-40"><ThumbsDown className="h-3.5 w-3.5" /></button>
              {enviando && <Loader2 className="h-3 w-3 animate-spin" />}
              {erro && <span style={{ color: 'var(--warning)' }}>{erro}</span>}
            </>
          )}
        </div>
      )}
    </div>
  )
}
