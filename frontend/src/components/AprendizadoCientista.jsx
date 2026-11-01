import { useCallback, useEffect, useState } from 'react'
import { cientistaAprendizado, cientistaAcao, cientistaHistorico, cientistaBase } from '../api'

const nomes = { coleta_dados: 'Coleta de dados', retreino_score: 'Retreino do score', experimento_bandit: 'Experimento do bandit' }
const estados = { proposta: 'Aguardando decisão', aprovada: 'Aprovada', recusada: 'Recusada', executando: 'Em execução', concluida: 'Concluída', em_observacao: 'Em observação', encerrada: 'Encerrada', erro: 'Falhou: pode tentar novamente', expirada: 'Expirada: gere nova avaliação' }
const btn = 'rounded-md border border-line px-3 py-1.5 text-xs text-ink disabled:opacity-40'

export default function AprendizadoCientista({ empresa }) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [historico, setHistorico] = useState({})
  const [aviso, setAviso] = useState('')
  const carregar = useCallback(async () => {
    try { setDados(await cientistaAprendizado(empresa)) } catch (e) { setErro(e.message || 'Não foi possível carregar o aprendizado.') }
  }, [empresa])
  useEffect(() => { setDados(null); setHistorico({}); setErro(''); carregar() }, [carregar])
  const emCurso = dados?.acoes.some(r => r.status === 'executando') || !!aviso
  useEffect(() => {
    if (!emCurso) return
    const t = setInterval(carregar, 5000)
    return () => clearInterval(t)
  }, [emCurso, carregar])
  async function agir(acao, id, decisao) {
    setOcupado(true); setErro(''); setAviso('')
    try {
      const r = await cientistaAcao(acao, empresa, id, decisao)
      if (r.aceito) setAviso(r.mensagem)
      await carregar()
      setHistorico({})
    } catch (e) { setErro(e.message || 'A operação falhou.') } finally { setOcupado(false) }
  }
  async function exportarBase(id) {
    try {
      const base = await cientistaBase(id, empresa)
      const url = URL.createObjectURL(new Blob([JSON.stringify(base, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `base-cientista-${id}.json`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setErro(e.message) }
  }
  async function verHistorico(id) {
    try { setHistorico(h => ({ ...h, [id]: null })); const eventos = await cientistaHistorico(id, empresa); setHistorico(h => ({ ...h, [id]: eventos })) }
    catch (e) { setErro(e.message) }
  }
  return <section className="space-y-3 rounded-xl border border-line bg-surface p-4">
    <h2 className="font-semibold text-ink">Aprendizado supervisionado pelo Cientista</h2>
    <p className="text-xs text-ink-2">Dados reais → proposta → aprovação → execução → acompanhamento. O score novo permanece inativo até o COMANDO decidir. Modelo ativo: {dados?.versao_ativa || 'global'}.</p>
    <div className="flex flex-wrap gap-2">
      <button className={btn} disabled={ocupado} onClick={() => agir('avaliar')}>Avaliar dados para retreino</button>
      <button className={btn} disabled={ocupado} onClick={() => agir('experimento')}>Propor experimento do bandit</button>
      <button className={btn} disabled={ocupado} onClick={() => agir('monitorar')}>Atualizar acompanhamento</button>
      <button className={btn} onClick={() => { setAviso(''); carregar() }}>Atualizar lista</button>
    </div>
    {erro && <p role="alert" className="text-sm text-red-300">{erro}</p>}
    {aviso && <p role="status" className="text-xs text-ink-2">{aviso} <button className="underline" onClick={() => setAviso('')}>Fechar aviso</button></p>}
    {dados?.acoes.length === 0 && <p className="text-sm text-ink-2">Nenhuma proposta registrada. Avalie os dados para conhecer o que falta.</p>}
    {dados?.acoes.map(r => {
      const d = r.dados, c = d.coorte
      return <article key={r.id} className="space-y-2 rounded-lg border border-line p-3">
        <h3 className="text-sm font-semibold text-ink">{nomes[r.tipo]} · {estados[r.status] || r.status}</h3>
        <p className="text-xs text-ink-3">{new Date(r.criado_em).toLocaleString('pt-BR')} · {r.id}</p>
        <p className="text-sm text-ink"><strong>O que mudou:</strong> {d.o_que_mudou}</p>
        <p className="text-sm text-ink"><strong>Ação:</strong> {d.relatorio_execucao || d.o_que_fazer}</p>
        <p className="text-sm text-ink-2"><strong>Por quê:</strong> {d.por_que}</p>
        {c && <div className="text-xs text-ink-2">
          <p>{c.elegiveis}/{c.minimos.total} pessoas · {c.pagaram} pagamentos · {c.nao_pagaram} não pagamentos · {c.novos}/{c.minimos.novos} novos · maturidade mínima: {c.minimos.maturidade_dias} dias</p>
          {c.faltas.map(f => <p key={f}>{f}</p>)}
          <p>Exclusões: {Object.entries(c.excluidos).map(([k,v]) => `${k}: ${v}`).join('; ') || 'nenhuma'}</p>
          <p className="break-all">Base SHA-256: {c.sha256}</p>
        </div>}
        {d.decidido_por && <p className="text-xs text-ink-3">Decidido por {d.decidido_por}</p>}
        {d.erro && <p className="text-xs text-red-300">Erro: {d.erro}</p>}
        {d.resultado && <><p className="text-sm text-ink">Modelo {d.versao_modelo}: {d.resultado.recomendacao}</p>
          <p className="text-xs text-ink-2">{d.resultado.motivos.join(' ')}</p>
          <p className="text-xs text-ink-2">AUC candidato: {d.resultado.metricas.novo.auc} · Brier: {d.resultado.metricas.novo.brier} · AUC ativo: {d.resultado.metricas.atual.auc ?? 'comparação indisponível'}</p></>}
        {d.monitoramento && <p className="text-sm text-ink-2">{d.monitoramento.conclusao}. Controle: {d.monitoramento.controle.n}; tratamento: {d.monitoramento.tratamento.n}; pendentes: {d.monitoramento.pendentes}.</p>}
        {d.monitoramento_modelo && <p className="text-sm text-ink-2">Após ativação: {d.monitoramento_modelo.acao} · {d.monitoramento_modelo.n} resultados.</p>}
        <div className="flex flex-wrap gap-2">
          {r.status === 'proposta' && <>
            {r.tipo !== 'coleta_dados' && <button className={btn} disabled={ocupado} onClick={() => agir('decidir', r.id, 'aprovada')}>Aprovar proposta</button>}
            <button className={btn} disabled={ocupado} onClick={() => agir('decidir', r.id, 'recusada')}>Recusar</button>
          </>}
          {['aprovada', 'erro', 'executando'].includes(r.status) && <button className={btn} disabled={ocupado} onClick={() => agir('executar', r.id)}>{r.status === 'executando' ? 'Verificar execução interrompida' : 'Executar ação aprovada'}</button>}
          {r.status === 'em_observacao' && <button className={btn} disabled={ocupado} onClick={() => agir('encerrar', r.id)}>Encerrar e voltar ao bandit original</button>}
          <button className={btn} onClick={() => verHistorico(r.id)}>Ver auditoria</button>
          {c && <button className={btn} onClick={() => exportarBase(r.id)}>Exportar base auditável</button>}
        </div>
        <details className="text-xs text-ink-2"><summary>Relatório completo e critérios</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(d, null, 2)}</pre></details>
        {historico[r.id] && <ol className="space-y-2 text-xs text-ink-2">{historico[r.id].map(e => <li key={e.id}>
          <strong>{e.evento}</strong> · {e.ator} · {new Date(e.criado_em).toLocaleString('pt-BR')}<p>{e.motivo}</p>
          <details><summary>Registro desta etapa</summary><pre className="max-h-64 overflow-auto whitespace-pre-wrap">{JSON.stringify(e.dados, null, 2)}</pre></details>
        </li>)}</ol>}
      </article>
    })}
  </section>
}
