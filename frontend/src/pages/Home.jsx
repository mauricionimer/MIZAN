import { lazy, Suspense } from 'react'
import { Loader2 } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import Upload from './Upload'

// O dashboard carrega recharts e o gerador de PDF; deixá-lo em pedaço próprio
// mantém a primeira tela leve para quem ainda não tem carteira aberta.
const Dashboard = lazy(() => import('./Dashboard'))

/**
 * A tela única da plataforma.
 *
 * Não existem mais "página de upload" e "página de dashboard": existe uma
 * página com a navegação à esquerda, e o conteúdo é a análise de carteira ou o
 * dashboard. Sem carteira carregada, só há a análise — clicar nela é onde o
 * usuário sobe um arquivo ou conecta o banco. Carregou, o dashboard aparece no
 * mesmo lugar, e a análise continua ali para trocar de carteira.
 */
export default function Home() {
  const { result, vista, setVista, restaurando } = useAnalysis()

  // Recarregou com carteira grande: a análise está voltando do servidor.
  // Mostrar a tela de carregar carteira agora daria a impressão de que ela se
  // perdeu — que é exatamente o que deixou de acontecer.
  if (restaurando) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2" role="status" aria-live="polite">
        <Loader2 className="h-5 w-5 animate-spin text-ink-3" />
        <span className="text-sm text-ink-2">Recuperando a análise…</span>
      </div>
    )
  }

  // A vista escolhida manda, desde que ainda faça sentido: sem carteira, não
  // há dashboard para mostrar.
  const atual = (vista === 'dashboard' && !result) ? 'analise'
              : (vista ?? (result ? 'dashboard' : 'analise'))

  if (atual === 'dashboard') {
    return (
      <Suspense fallback={
        <div className="flex min-h-screen items-center justify-center" role="status" aria-live="polite">
          <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
          <span className="sr-only">Carregando dashboard…</span>
        </div>
      }>
        <Dashboard onIrPara={setVista} />
      </Suspense>
    )
  }

  return <Upload onIrPara={setVista} temResultado={!!result} />
}
