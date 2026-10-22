import { useEffect, useMemo, useState } from 'react'
import { agenteEstacao, agenteAgentes } from '../../api'
import { AGENTES, tarefa } from './config'

// Uma consulta compartilhada por sala, lista, detalhe, casos e atividade.
// Respostas de empresas anteriores e requisições sobrepostas são descartadas.
export default function useEscritorio(empresa) {
  const [dados, setDados] = useState({})
  useEffect(() => {
    let vivo = true, ocupado = false, resumoEm = 0
    setDados({ empresa })
    const carregar = async () => {
      if (ocupado || document.hidden) return
      ocupado = true
      const resumo = Date.now() - resumoEm >= 15000
      const r = await Promise.allSettled([agenteEstacao(empresa), ...(resumo ? [agenteAgentes(empresa)] : [])])
      if (vivo) setDados(d => ({ ...d, empresa,
        ...(r[0].status === 'fulfilled' ? { estacao: r[0].value, atualizado: Date.now(), erro: false } : { erro: true }),
        ...(resumo && r[1].status === 'fulfilled' ? { resumo: r[1].value, erroResumo: false } : resumo ? { erroResumo: true } : {}),
      }))
      if (resumo && r[1].status === 'fulfilled') resumoEm = Date.now()
      ocupado = false
    }
    carregar()
    const t = setInterval(carregar, 5000)
    document.addEventListener('visibilitychange', carregar)
    return () => { vivo = false; clearInterval(t); document.removeEventListener('visibilitychange', carregar) }
  }, [empresa])
  return useMemo(() => {
    const atuais = dados.empresa === empresa ? dados : {}
    const e = atuais.estacao, resumos = atuais.resumo?.agentes || []
    const agentes = AGENTES.map(a => {
      const ativos = (e?.executando || []).filter(x => x.quem === a.nome)
      const atual = ativos[0]
      const desconhecido = atuais.erro || !e || !Array.isArray(e.executando) || (!atual && (e.execucoes_sem_sinal > 0 || a.nome === 'Cientista'))
      return { ...a, status: desconhecido ? 'desconhecido' : atual?.estado || 'aguardando',
        atual, ativos, tarefa: atual ? tarefa(atual.no) : 'Sem tarefa informada',
        metricas: resumos.find(x => x.nome === a.nome),
        ultimas: (e?.passos || []).filter(p => p.quem === a.nome).slice(-20).reverse(),
      }
    })
    return { ...atuais, agentes, sinais: e?.sinais || [], casos: e?.casos || [], numeros: atuais.resumo?.numeros, amostra: atuais.resumo?.amostra_limitada }
  }, [dados, empresa])
}
