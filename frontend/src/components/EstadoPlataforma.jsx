import { useEffect, useState } from 'react'
import { estadoDaPlataforma } from '../api'
import { Medidor } from './graficos'

/**
 * Estado da plataforma (Ajuda). Cada linha vem de uma medição real do servidor
 * (backend/plataforma.py). Sem dado, a linha diz "sem medição" em cinza: a tela
 * nunca pinta de verde o que não mediu.
 */
const COR = { ok: 'var(--success)', atencao: 'var(--warning)', problema: 'var(--danger)', sem_medicao: 'var(--text-muted)' }
const ROTULO = { ok: 'Funcionando', atencao: 'Atenção', problema: 'Com problema', sem_medicao: 'Sem medição' }

function hora(iso) {
  try { return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

export default function EstadoPlataforma({ empresaId }) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(false)

  useEffect(() => {
    let vivo = true
    const ler = () => estadoDaPlataforma(empresaId)
      .then(d => { if (vivo) { setDados(d); setErro(false) } })
      .catch(() => { if (vivo) setErro(true) })
    ler()
    const t = setInterval(ler, 60_000)
    return () => { vivo = false; clearInterval(t) }
  }, [empresaId])

  if (erro && !dados) {
    return (
      <section className="rounded-xl border border-line bg-surface p-5" aria-live="polite">
        <p className="section-label">Estado da plataforma</p>
        <p className="mt-1 text-sm text-ink">Não consegui falar com o servidor agora.</p>
        <p className="text-xs text-ink-2">Se isso continuar, a plataforma pode estar fora do ar. Tento de novo a cada minuto.</p>
      </section>
    )
  }
  if (!dados) return <div className="h-40 animate-pulse rounded-xl border border-line bg-surface" aria-label="Medindo a plataforma" />

  return (
    <section className="rounded-xl border border-line bg-surface p-5" aria-labelledby="estado-plat">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="section-label">Estado da plataforma</p>
          <h2 id="estado-plat" className="mt-0.5 text-[15px] font-semibold text-ink">{dados.frase}</h2>
        </div>
        <span className="text-[11px] text-ink-3">medido às {hora(dados.medido_em)}</span>
      </div>
      <ul className="space-y-4">
        {dados.servicos.map((s, i) => (
          <li key={s.id} className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[170px_minmax(0,1fr)_110px] sm:items-center">
            <span className="text-sm font-medium text-ink">{s.nome}</span>
            <div className="min-w-0">
              {s.estado === 'sem_medicao'
                ? <div className="flex h-5 items-center rounded-[3px] border border-dashed border-line px-2 text-[11px] text-ink-3">sem dado nesta janela</div>
                : <Medidor nivel={s.nivel} cor={COR[s.estado]} atraso={i * 0.15} rotulo={`${s.nome}: ${ROTULO[s.estado]}, ${s.nivel}%`} />}
              <p className="mt-1 text-xs text-ink-2">{s.frase}</p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold sm:justify-end" style={{ color: COR[s.estado] }}>
              <span className="h-2 w-2 rounded-full" style={{ background: COR[s.estado] }} aria-hidden="true" />
              {ROTULO[s.estado]}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[11px] text-ink-3">
        Agentes e e-mail: últimas 24 h. Pagamentos: últimos 30 dias, do dia do pagamento ao registro na MIZAN.
      </p>
    </section>
  )
}
