import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import DicaAjuda from './DicaAjuda'
import { useAbasDaArea } from './AppShell'

/**
 * O cabeçalho padrão de toda tela (guia: design/GUIA_DE_DESIGN.md, seção 4).
 *
 *   ← Voltar            (sempre: a pessoa nunca fica sem saída)
 *   RÓTULO DA ÁREA      (eyebrow, caixa alta pequena)
 *   [ícone] Título [?]  (o "?" só aparece se houver ajuda para o perfil)
 *   Uma frase dizendo para que serve a tela.            [ações à direita]
 *
 * Uma tela tem um título só: este. Nada de <h1> próprio nas páginas.
 */
export default function CabecalhoPagina({
  voltar = { to: '/inicio', rotulo: 'Início' }, rotulo, icone: Icone, titulo, selo, ajuda, subtitulo, children, className = '',
}) {
  const abas = useAbasDaArea()
  return (
    <>
    <header className={`mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 ${className}`}>
      <div className="flex min-w-0 flex-col gap-2">
        {voltar && (
          <Link to={voltar.to} className="inline-flex h-8 w-fit items-center gap-1.5 rounded-full border border-line px-3 text-[13px] text-ink-2 transition-colors hover:border-[var(--border-strong)] hover:text-ink">
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />{voltar.rotulo}
          </Link>
        )}
        {rotulo && <span className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-accent-text">{rotulo}</span>}
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          {Icone && <Icone className="h-[22px] w-[22px] shrink-0 text-accent-text" strokeWidth={1.8} aria-hidden="true" />}
          <h1 className="min-w-0 break-words font-display text-[28px] font-bold leading-tight tracking-tight text-ink">{titulo}</h1>
          {selo}
          {ajuda && <DicaAjuda id={ajuda} />}
        </div>
        {subtitulo && <p className="max-w-3xl text-sm text-ink-2">{subtitulo}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2.5">{children}</div>}
    </header>
    {abas}
    </>
  )
}
