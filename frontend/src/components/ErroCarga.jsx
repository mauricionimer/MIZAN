import { useState } from 'react'
import { AlertTriangle, WifiOff, RotateCcw, Loader2, Lock } from 'lucide-react'
import { classificarErro } from '../api'

/**
 * Bloco de erro único das telas: diz o que aconteceu em português e, quando
 * faz sentido repetir (rede, servidor acordando, erro do servidor), oferece
 * "Tentar novamente" — que não dispara duas vezes enquanto está tentando.
 *
 * `erro` pode ser o Error da chamada ou um texto. `onTentar` pode devolver uma
 * promessa; o botão fica ocupado até ela terminar.
 */
export default function ErroCarga({ erro, onTentar, ocupado = false, compacto = false, className = '' }) {
  const [tentandoAqui, setTentando] = useState(false)
  const tentando = tentandoAqui || ocupado
  if (!erro) return null
  const c = classificarErro(erro)
  const Icone = c.tipo === 'rede' || c.tipo === 'acordando' ? WifiOff : c.tipo === 'autorizacao' ? Lock : AlertTriangle
  const cor = c.tipo === 'validacao' || c.tipo === 'negocio' ? 'var(--warning)' : 'var(--danger)'
  async function tentar() {
    if (tentando) return
    setTentando(true)
    // Segura o botão por um instante mesmo quando a tela recarrega por efeito
    // (sem promessa para esperar): cliques seguidos não viram vários pedidos.
    try { await Promise.all([onTentar(), new Promise(r => setTimeout(r, 700))]) } finally { setTentando(false) }
  }
  return (
    <div role="alert" className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl ${compacto ? 'px-3 py-2' : 'px-4 py-3'} ${className}`}
      style={{ background: 'var(--surface-2)', border: `1px solid ${cor}`, borderLeftWidth: 3 }}>
      <Icone className="h-4 w-4 shrink-0" style={{ color: cor }} aria-hidden="true" />
      <p className="min-w-0 flex-1 text-sm" style={{ color: 'var(--ink)' }}>{c.mensagem}</p>
      {onTentar && c.podeTentar && (
        <button type="button" onClick={tentar} disabled={tentando}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 text-sm font-semibold disabled:opacity-60"
          style={{ border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}>
          {tentando ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
          {tentando ? 'Tentando…' : 'Tentar novamente'}
        </button>
      )}
    </div>
  )
}
