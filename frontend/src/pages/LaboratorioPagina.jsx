// Laboratório (Agente Cientista), na área Resultados.
import AppShell from '../components/AppShell'
import { Laboratorio } from './Agente'

export default function LaboratorioPagina() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl">
        <Laboratorio />
      </div>
    </AppShell>
  )
}
