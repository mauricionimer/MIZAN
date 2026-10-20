import AppShell from '../components/AppShell'
import GlassFolder from '../components/ui/glass-folder-cards'
import { useTheme } from '../context/ThemeContext'

/**
 * Pastas de devedores, primeira versão: só a pasta animada, com dados de
 * exemplo, para validar o componente na plataforma. Na próxima etapa cada pasta
 * passa a ser um devedor real, e os arquivos dentro dela, o que os agentes
 * juntaram sobre ele (perfil, conversas, recomendação, promessas).
 */
const EXEMPLOS = [
  { nome: 'Mariana Alves', meta: 'Rank #1 · 42 dias', arte: 'aurora', semente: 3, arquivos: [
    { name: 'Perfil do devedor', meta: 'Triagem' },
    { name: 'Conversas', meta: '3 mensagens' },
    { name: 'Recomendação', meta: 'WhatsApp · entrada + 10x', art: 'dusk' },
    { name: 'Promessas', meta: '1 em aberto' },
  ] },
  { nome: 'Carlos Menezes', meta: 'Rank #2 · 67 dias', arte: 'ember', semente: 11, arquivos: [
    { name: 'Perfil do devedor', meta: 'Triagem' },
    { name: 'Conversas', meta: '5 mensagens' },
    { name: 'Recomendação', meta: 'Ligação · desconto 8%', art: 'ember' },
  ] },
  { nome: 'Joana Teixeira', meta: 'Rank #3 · 18 dias', arte: 'glacier', semente: 7, arquivos: [
    { name: 'Perfil do devedor', meta: 'Triagem' },
    { name: 'Acordo', meta: 'Quitado', art: 'verdant' },
  ] },
]

export default function PastasDevedores() {
  const { claro } = useTheme()
  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="hub-titulo">Pastas de devedores</h1>
        <p className="hub-sub">Exemplo ilustrativo: passe o mouse para inclinar a pasta e clique para abrir.</p>
        <div className="mt-28 grid grid-cols-1 items-end justify-items-center gap-x-10 gap-y-12 md:grid-cols-2 xl:grid-cols-3">
          {EXEMPLOS.map((d, i) => (
            <GlassFolder key={d.nome} label={d.nome} meta={d.meta} tone={claro ? 'light' : 'dark'}
              art={d.arte} seed={d.semente} files={d.arquivos} action="none" width={320} appearDelay={i * 140} />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
