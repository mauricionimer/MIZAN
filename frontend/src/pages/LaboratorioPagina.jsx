// Laboratório por empresa; COMANDO escolhe o cliente antes de qualquer leitura.
import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import { useAuth } from '../context/AuthContext'
import { listarEmpresas } from '../api'
import { Laboratorio } from './Agente'

export default function LaboratorioPagina() {
  const { isComando } = useAuth()
  const [empresas, setEmpresas] = useState([])
  const [empresa, setEmpresa] = useState('')
  const [erro, setErro] = useState('')
  useEffect(() => {
    if (isComando) listarEmpresas().then(r => setEmpresas(Array.isArray(r) ? r : r.empresas || [])).catch(e => setErro(e.message))
  }, [isComando])
  return <AppShell>
    <div className="mx-auto w-full max-w-7xl space-y-4">
      {isComando && <label className="block text-sm text-ink">Empresa
        <select className="ml-2 rounded border border-line bg-surface p-2" value={empresa} onChange={e => setEmpresa(e.target.value)}>
          <option value="">Selecione uma empresa</option>
          {empresas.map(e => <option key={e.empresa_id || e.id} value={e.empresa_id || e.id}>{e.nome_exibicao || e.nome || e.empresa_nome || e.empresa_id || e.id}</option>)}
        </select>
      </label>}
      {erro && <p role="alert" className="text-red-300">{erro}</p>}
      {(!isComando || empresa) && <Laboratorio key={empresa} empresa={empresa || undefined} />}
    </div>
  </AppShell>
}
