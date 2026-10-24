import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Users, Activity, FolderOpen, Minus, Plus, Scan, Crosshair, ArrowUpRight, Radio, X, Clock3 } from 'lucide-react'
import SalaCanvas from './SalaCanvas'
import Retrato from './Retrato'
import { ESTADOS, TIMES, hora, curto, mensagem } from './config'
import './escritorio.css'

function Estado({ valor }) {
  const e=ESTADOS[valor] || ESTADOS.desconhecido
  return <span className="ao-status" style={{'--ao-state':e.cor}}><i />{e.nome}</span>
}
function Janela({ titulo, children, fechar }) {
  return <section className="ao-window" aria-label={titulo}>
    <div className="ao-window-title"><h3 tabIndex={-1}>{titulo}</h3>{fechar&&<button type="button" onClick={fechar} aria-label={`Fechar ${titulo}`}><X size={13}/></button>}</div>
    <div className="ao-window-body">{children}</div>
  </section>
}
function Lista({ agentes, selecionado, onSelecionar }) {
  return <div className="ao-agent-list">{agentes.map(a=><button type="button" key={a.id} className={`ao-agent-row ${selecionado===a.id?'ao-selected':''}`} onClick={()=>onSelecionar(a.id)} aria-pressed={selecionado===a.id}>
    <span className="ao-portrait-small" style={{background:a.cor+'44'}}><Retrato nome={a.nome} cor={a.cor} tamanho={23}/></span>
    <span className="ao-agent-copy"><strong>{a.nome}</strong><span>{a.papel}</span><span className="ao-row-task" title={a.tarefa}>{a.atual?a.tarefa:a.metricas?.ultimo_em?`Última ação ${hora(a.metricas.ultimo_em)}`:'Sem atividade registrada'}</span></span>
    <i className="ao-agent-dot" style={{background:ESTADOS[a.status]?.cor}} title={ESTADOS[a.status]?.nome}/>
    <span className="sr-only">{ESTADOS[a.status]?.nome}</span>
  </button>)}</div>
}
function Detalhe({ agente:a, seguir, onSeguir, onPerfil, mostrarCusto, resumoAntigo, amostra }) {
  if(!a)return <p className="ao-empty">Selecione um agente na sala ou na lista.</p>
  const m=a.metricas
  return <>
    <div className="ao-detail-top"><div className="ao-portrait" style={{'--ao-agent':a.cor}}><Retrato nome={a.nome} cor={a.cor} tamanho={46}/></div><div><h4>{a.nome}</h4><p>{a.papel}</p><Estado valor={a.status}/><span className="ao-sector">{TIMES[a.time]?.nome} · {a.ia?'Agente':'Código'}</span></div></div>
    <p className="ao-description">{a.desc}</p>
    <div className="ao-section-label">Tarefa atual</div>
    <div className="ao-task"><strong>{a.tarefa}</strong>{a.atual ? <span>Caso #{curto(a.atual.caso_id)} · {a.ativos.length>1?`${a.ativos.length} eventos em execução`:'Execução confirmada'}</span> : <span>{a.status==='desconhecido'?'Aguardando um sinal atualizado.':'Nenhuma execução informada pelo sistema.'}</span>}</div>
    {a.ativos.length>1&&<div className="ao-parallel">{a.ativos.slice(1).map(x=><span key={x.id}>Também: #{curto(x.caso_id)} · {x.no}</span>)}</div>}
    <div className="ao-section-label">Métricas · últimas 24 h{resumoAntigo?' · desatualizadas':''}</div>
    {amostra&&<p className="ao-panel-note">Amostra das últimas 5.000 etapas da empresa nesta janela.</p>}
    <div className="ao-metrics">
      <div><strong>{m?.acoes??'—'}</strong><span>etapas registradas</span></div>
      <div><strong>{m?.tempo_medio_ms!=null?`${m.tempo_medio_ms.toLocaleString('pt-BR')} ms`:'—'}</strong><span>tempo médio</span></div>
      <div><strong>{m?.tokens!=null?m.tokens.toLocaleString('pt-BR'):'—'}</strong><span>tokens</span></div>
      <div><strong>{m?.bloqueios??'—'}</strong><span>bloqueios</span></div>
    </div>
    {mostrarCusto&&m&&<p className="ao-model">Custo: US$ {Number(m.custo_usd||0).toFixed(4)}</p>}
    {m?.modelo&&<p className="ao-model" title={m.modelo}>Modelo: {m.modelo}{m.versao_prompt?` · prompt ${m.versao_prompt}`:''}</p>}
    <div className="ao-detail-buttons"><button type="button" className={seguir?'ao-follow-active':''} onClick={onSeguir} aria-pressed={seguir}><Crosshair size={13}/>{seguir?'Seguindo':'Seguir na sala'}</button><button type="button" onClick={()=>onPerfil(a.nome)} title="Abrir o perfil completo do agente"><ArrowUpRight size={14}/>Perfil</button></div>
    <div className="ao-section-label">Últimas ações · 15 min</div>
    <div className="ao-actions">{a.ultimas.length?a.ultimas.map((p,i)=><div key={`${p.trace_id}-${p.no}-${p.criado_em}-${i}`}><time>{hora(p.criado_em)}</time><i style={{background:p.resultado==='erro'?'#cf453c':p.resultado==='bloqueado'||p.resultado==='aguardando'?'#c98c28':'#47986b'}}/><span>{p.explicacao||p.expli||p.no}<small>{p.duracao_ms??0} ms · {(p.tokens_entrada||0)+(p.tokens_saida||0)} tokens</small></span></div>):<p className="ao-empty">Nenhuma etapa registrada nesta janela.</p>}</div>
  </>
}
function Casos({ casos }) {
  const unicos=useMemo(()=>[...new Map([...casos].reverse().map(c=>[c.caso_id,c])).values()].reverse(),[casos])
  const sit={pendente:'Na fila',processando:'Em execução',falhou:'Falha no evento'}
  return <><p className="ao-panel-note">Casos com eventos na amostra recente. Um evento concluído não significa dívida quitada.</p>{unicos.length?unicos.map(c=><article className="ao-case" key={c.caso_id}><header><strong>Caso #{curto(c.caso_id)}</strong><span>{sit[c.situacao]||c.situacao}</span></header><p>{c.tipo?.replaceAll('_',' ')}</p><div className="ao-case-stages">{c.etapas?.map(n=><span key={n}>✓ {n}</span>)}{c.quem&&<b>● {c.quem}</b>}</div>{c.situacao==='processando'&&!c.quem&&<small>Sem sinal recente da etapa atual.</small>}</article>):<p className="ao-empty">Nenhum evento pendente nesta amostra.</p>}</>
}
function Feed({ sinais }) {
  return sinais.length ? <ol className="ao-feed">{sinais.map(e=><li key={e.id}><time>{hora(e.t)}</time><i style={{background:e.tipo==='erro'?'#c8463b':e.resultado==='bloqueado'?'#c98c28':e.tipo==='fim'?'#47986b':e.tipo==='handoff'?'#7972bc':'#5185b5'}}/><div>{mensagem(e)}<small>{e.tipo==='handoff'?'Passagem registrada':e.tipo==='inicio'?'Início de etapa':e.tipo==='fim'?'Fim de etapa':'Falha registrada'}</small></div></li>)}</ol> : <p className="ao-empty">Os próximos eventos registrados aparecerão aqui.</p>
}
export default function EscritorioAgentes({ dados, nomeEmpresa, logoUrl, onPerfil, mostrarCusto }) {
  const [selecionado,setSelecionado]=useState('Orquestrador'),[painel,setPainel]=useState('detalhes'),[seguir,setSeguir]=useState(false),[controle,setControle]=useState(null)
  const direita=useRef(null), lista=useRef(null), montou=useRef(false)
  useEffect(()=>{
    if(!montou.current){montou.current=true;return}
    if(direita.current?.closest('.ao-office').getBoundingClientRect().width<1240){direita.current?.querySelector('h3')?.focus({preventScroll:true});direita.current?.scrollIntoView({block:'nearest',behavior:'auto'})}
  },[painel,selecionado])
  const selecionar=useCallback(nome=>{setSelecionado(nome);setPainel('detalhes')},[])
  const a=dados.agentes.find(x=>x.nome===selecionado)
  const contagem=dados.agentes.reduce((acc,a)=>({...acc,[a.status]:(acc[a.status]||0)+1}),{})
  const mover=(tipo,delta)=>{setSeguir(false);setControle({tipo,delta,id:Date.now()})}
  return <section className="ao-office" aria-label="Escritório dos agentes">
    <div className="ao-frame">
    <div className="ao-office-top"><div className="ao-office-brand"><span className="ao-brand-icon">M</span><div><h2>Sala dos Agentes</h2><p>{nomeEmpresa||'MIZAN'} · Operação de cobrança</p></div></div><div className="ao-counts">{Object.entries(ESTADOS).filter(([k])=>contagem[k]).map(([k,e])=><span key={k}><i style={{background:e.cor}}/>{contagem[k]} {e.nome.toLowerCase()}</span>)}</div><span className={`ao-connection ${dados.erro?'ao-disconnected':''}`} role="status"><Radio size={12}/>{dados.erro?'Conexão interrompida':!dados.estacao?'Conectando…':`Atualizado ${hora(dados.atualizado)}`}</span></div>
    {(dados.erro||dados.erroResumo)&&<div className="ao-warning" role="status">{dados.estacao?'Mantendo os últimos dados disponíveis. Tentando reconectar…':'Não foi possível carregar a operação. Tentando novamente…'}</div>}
    <div className="ao-layout">
      <div className="ao-room"><SalaCanvas agentes={dados.agentes} sinais={dados.sinais} selecionado={selecionado} onSelecionar={selecionar} controle={controle} seguir={seguir} onManual={()=>setSeguir(false)} nomeEmpresa={nomeEmpresa} logoUrl={logoUrl} obsoleto={dados.erro}/><div className="ao-room-info"><Clock3 size={12}/>{dados.estacao?.ligado===false?'Automação desligada':'Eventos reais do sistema'}</div></div>
      <div className="ao-right" ref={direita}><Janela titulo={painel==='casos'?'Casos':painel==='atividade'?'Atividade':a?`${a.nome} · Detalhes`:'Detalhes'} fechar={painel==='casos'||painel==='atividade'?()=>setPainel('detalhes'):null}>
        {painel==='casos'?<Casos casos={dados.casos}/>:painel==='atividade'?<Feed sinais={dados.sinais}/>:<Detalhe agente={a} seguir={seguir} onSeguir={()=>setSeguir(x=>!x)} onPerfil={onPerfil} mostrarCusto={mostrarCusto} resumoAntigo={dados.erroResumo} amostra={dados.amostra}/>}
      </Janela></div>
    </div>
    <div className="ao-toolbar"><div>
      <button type="button" onClick={()=>{lista.current?.scrollIntoView({block:'nearest',behavior:'auto'});lista.current?.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true})}}><Users size={17}/><span>Agentes</span></button>
      {[['casos',FolderOpen,'Casos'],['atividade',Activity,'Atividade'],['detalhes',Crosshair,'Detalhes']].map(([id,Icon,label])=><button type="button" className={painel===id?'ao-toolbar-active':''} key={id} onClick={()=>setPainel(id)} aria-pressed={painel===id}><Icon size={17}/><span>{label}</span></button>)}
    </div><div><button type="button" onClick={()=>mover('zoom',-1)} title="Diminuir zoom" aria-label="Diminuir zoom"><Minus size={18}/></button><button type="button" onClick={()=>mover('zoom',1)} title="Aumentar zoom" aria-label="Aumentar zoom"><Plus size={18}/></button><button type="button" onClick={()=>mover('centrar')} title="Centralizar sala" aria-label="Centralizar sala"><Scan size={18}/><span>Centralizar</span></button></div></div>
    </div>
    <section className="ao-roster" ref={lista} aria-label="Seleção de agentes">
      <header><h3>Agentes</h3><p>Selecione um agente para acompanhar a tarefa e as últimas ações.</p></header>
      <Lista agentes={dados.agentes} selecionado={selecionado} onSelecionar={selecionar}/>
    </section>
  </section>
}
