import { useEffect, useState } from 'react'
import { estadoDaPlataforma } from '../api'
import { Medidor } from './graficos'

/**
 * Estado da plataforma (Ajuda). Cada linha vem de uma medição real do servidor
 * (backend/plataforma.py). Sem dado, a linha diz "sem medição" em cinza: a tela
 * nunca pinta de verde o que não mediu.
 *
 * Desenho do canvas: um anel com quantos serviços medidos estão normais, a frase
 * do estado e uma linha por serviço; tocar na linha abre a explicação.
 */
const COR = { ok: 'var(--success)', atencao: 'var(--warning)', problema: 'var(--danger)', sem_medicao: 'var(--text-muted)' }
const ROTULO = { ok: 'Funcionando', atencao: 'Atenção', problema: 'Com problema', sem_medicao: 'Sem medição' }

function hora(iso) {
  try { return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

function Anel({ ok, atencao, total }) {
  const r = 26, c = 2 * Math.PI * r
  const parte = (n) => (total ? (n / total) * c : 0)
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label={`${ok} de ${total} serviços medidos funcionando`} className="shrink-0">
      <circle cx="32" cy="32" r={r} fill="none" stroke="var(--raised)" strokeWidth="7" />
      {ok > 0 && <circle cx="32" cy="32" r={r} fill="none" stroke="var(--success)" strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${Math.max(0, parte(ok) - 4)} ${c}`} transform="rotate(-90 32 32)" />}
      {atencao > 0 && <circle cx="32" cy="32" r={r} fill="none" stroke="var(--warning)" strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${Math.max(0, parte(atencao) - 4)} ${c}`} strokeDashoffset={-parte(ok)} transform="rotate(-90 32 32)" />}
      <text x="32" y="37" textAnchor="middle" fill="var(--text)" fontSize="15" fontWeight="700">{ok}/{total}</text>
    </svg>
  )
}

export default function EstadoPlataforma({ empresaId, className = '' }) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(false)
  const [aberto, setAberto] = useState(null)

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
      <section className={`rounded-2xl border border-line bg-surface px-6 py-[22px] ${className}`} aria-live="polite">
        <p className="section-label">Estado da plataforma</p>
        <p className="mt-1 text-sm text-ink">Não consegui falar com o servidor agora.</p>
        <p className="text-xs text-ink-2">Se isso continuar, a plataforma pode estar fora do ar. Tento de novo a cada minuto.</p>
      </section>
    )
  }
  if (!dados) return <div className={`h-64 animate-pulse rounded-2xl border border-line bg-surface ${className}`} aria-label="Medindo a plataforma" />

  const medidos = dados.servicos.filter(s => s.estado !== 'sem_medicao')
  const ok = medidos.filter(s => s.estado === 'ok').length
  const atencao = medidos.filter(s => s.estado === 'atencao').length

  return (
    <section className={`flex flex-col gap-4 rounded-2xl border border-line bg-surface px-6 py-[22px] ${className}`} aria-labelledby="estado-plat">
      <div className="flex items-center gap-4">
        <Anel ok={ok} atencao={atencao} total={medidos.length} />
        <div className="flex min-w-0 flex-col gap-1">
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="section-label">Estado da plataforma</span>
            <span className="text-xs font-semibold" style={{ color: COR[dados.estado] || COR.ok }}>● {ROTULO[dados.estado] || 'Funcionando'}</span>
          </span>
          <b id="estado-plat" className="text-[17px] leading-snug text-ink">{dados.frase}</b>
          <span className="text-xs text-ink-3">medido às {hora(dados.medido_em)}{dados.sem_medicao ? ` · ${dados.sem_medicao} sem medição na janela` : ''}</span>
        </div>
      </div>
      <ul className="flex flex-col gap-0.5">
        {dados.servicos.map((s, i) => (
          <li key={s.id}>
            <button type="button" onClick={() => setAberto(aberto === s.id ? null : s.id)} aria-expanded={aberto === s.id}
              className={`grid w-full items-center gap-x-3.5 gap-y-1.5 rounded-[14px] px-3 py-[11px] text-left sm:grid-cols-[190px_minmax(0,1fr)_auto] ${aberto === s.id ? 'bg-[var(--raised)]' : 'hover:bg-raise-1'}`}>
              <span className="flex items-center gap-2 text-sm font-medium text-ink">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COR[s.estado] }} aria-hidden="true" />{s.nome}
              </span>
              {s.estado === 'sem_medicao'
                ? <span className="flex h-5 items-center rounded-[6px] border border-dashed border-line px-2 text-[11px] text-ink-3">sem dado nesta janela</span>
                : <Medidor nivel={s.nivel} cor={COR[s.estado]} atraso={i * 0.15} rotulo={`${s.nome}: ${ROTULO[s.estado]}, ${s.nivel}%`} />}
              <span className="whitespace-nowrap text-[13px] font-semibold sm:justify-self-end" style={{ color: COR[s.estado] }}>
                {ROTULO[s.estado]}{s.nivel != null ? ` · ${Math.round(s.nivel)}%` : ''}
              </span>
            </button>
            {aberto === s.id && <p className="px-3 pb-2 pt-1 text-[13px] leading-relaxed text-ink-2">{s.frase} <span className="text-ink-3">Janela: {s.janela}.</span></p>}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-ink-3">
        Agentes e e-mail: últimas 24 h. Pagamentos: últimos 30 dias, do dia do pagamento ao registro na MIZAN. Toque num serviço para ver o que foi medido.
      </p>
    </section>
  )
}
