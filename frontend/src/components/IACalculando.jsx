import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

// As etapas que o servidor percorre de fato, na ordem. Elas giram com o tempo
// para mostrar o que está acontecendo — não são uma barra de progresso: o
// servidor não informa em que ponto está, então não há porcentagem inventada.
export const ETAPAS_ANALISE = [
  'Lendo o arquivo e reconhecendo as colunas',
  'Conferindo os dados de cada devedor',
  'Calculando a chance de pagamento com a IA',
  'Estimando quanto cada dívida deve devolver',
  'Montando a fila pelo valor esperado',
  'Gravando a análise',
]

export const ETAPAS_BACKTEST = [
  'Lendo a carteira histórica',
  'Pontuando cada devedor como se fosse antes da cobrança',
  'Montando a fila do Mizan e as de comparação',
  'Comparando com quem pagou de verdade',
  'Medindo o acerto da IA (KS, decis)',
]

/** Painel de "IA calculando" para esperas longas. */
export default function IACalculando({ etapas = ETAPAS_ANALISE, titulo = 'A IA está analisando a carteira', compacto = false }) {
  const reduzir = useReducedMotion()
  const [i, setI] = useState(0)
  const [seg, setSeg] = useState(0)

  useEffect(() => {
    const troca = setInterval(() => setI(n => Math.min(n + 1, etapas.length - 1)), 2600)
    const relogio = setInterval(() => setSeg(s => s + 1), 1000)
    return () => { clearInterval(troca); clearInterval(relogio) }
  }, [etapas.length])

  return (
    <div role="status" aria-live="polite"
      className={`flex flex-col items-center text-center ${compacto ? 'gap-3 py-6' : 'gap-4 py-10'}`}>
      {/* Núcleo pulsando com pontos orbitando: "pensando". */}
      <div className="relative h-16 w-16">
        <motion.div className="absolute inset-0 rounded-full"
          style={{ background: 'rgb(var(--c-royal) / 0.18)' }}
          animate={reduzir ? {} : { scale: [1, 1.35, 1], opacity: [0.7, 0.15, 0.7] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }} />
        <div className="absolute inset-3 flex items-center justify-center rounded-full"
          style={{ background: 'var(--royal)' }}>
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        {!reduzir && [0, 1, 2].map(k => (
          <motion.span key={k} className="absolute left-1/2 top-1/2 h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--accent-text)', marginLeft: -3, marginTop: -3 }}
            animate={{ rotate: 360 }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'linear', delay: k * 0.8 }}>
            <span className="absolute h-1.5 w-1.5 rounded-full" style={{ background: 'var(--accent-text)', transform: 'translateX(30px)' }} />
          </motion.span>
        ))}
      </div>

      <div>
        <p className="text-sm font-semibold text-ink">{titulo}</p>
        <div className="mt-1 h-5 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.p key={i} className="text-xs" style={{ color: 'var(--ink-2)' }}
              initial={reduzir ? { opacity: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduzir ? { opacity: 0 } : { opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}>
              {etapas[i]}…
            </motion.p>
          </AnimatePresence>
        </div>
      </div>

      {/* Uma marca por etapa: as já mostradas acendem. */}
      <div className="flex gap-1.5" aria-hidden="true">
        {etapas.map((_, k) => (
          <span key={k} className="h-1 w-6 rounded-full transition-colors duration-500"
            style={{ background: k <= i ? 'var(--royal)' : 'var(--raise-3)' }} />
        ))}
      </div>
      <p className="text-[11px] tabular-nums" style={{ color: 'var(--ink-4)' }}>
        {seg}s · carteiras grandes levam mais tempo
      </p>
    </div>
  )
}
