import { useCallback, useMemo, useRef, useState } from 'react'
import { Users, Activity, FolderOpen, Minus, Plus, Scan, Crosshair, ArrowUpRight, Radio, X } from 'lucide-react'
import SalaCanvas from './SalaCanvas'
import Retrato from './Retrato'
import { ESTADOS, TIMES, LIMITES, hora, curto, mensagem } from './config'
import './escritorio.css'

// Layout da prancha "Agentes · Ao vivo": a sala à esquerda com a barra de ferramentas embaixo,
// a lista dos agentes à direita e, ao escolher um, uma janela larga com o que ajuda a decidir.

function Estado({ valor }) {
  const e = ESTADOS[valor] || ESTADOS.desconhecido
  return <span className="ao-status" style={{ '--ao-state': e.cor }}>{e.nome}</span>
}

function Janela({ titulo, extra, children, fechar, className = '' }) {
  return <section className={`ao-window ${className}`} aria-label={titulo}>
    <div className="ao-window-title"><h3 tabIndex={-1}>{titulo}</h3>{extra}{fechar && <button type="button" className="ao-close" onClick={fechar} aria-label={`Fechar ${titulo}`}><X size={13} /></button>}</div>
    <div className="ao-window-body">{children}</div>
  </section>
}

const agoraDe = a => a.atual ? a.tarefa : a.metricas?.ultimo_em ? `Última ação às ${hora(a.metricas.ultimo_em)}` : 'Sem atividade registrada'

function Lista({ agentes, selecionado, onSelecionar }) {
  const [filtro, setFiltro] = useState('todos')
  const vis = agentes.filter(a => filtro === 'todos' || (filtro === 'ia' ? a.ia : !a.ia))
  return <>
    <div className="ao-filtros" role="group" aria-label="Filtrar agentes">
      {[['todos', 'Todos'], ['ia', 'Agentes de IA'], ['codigo', 'Em código']].map(([id, nome]) =>
        <button type="button" key={id} aria-pressed={filtro === id} onClick={() => setFiltro(id)}>{nome}</button>)}
    </div>
    <div className="ao-agent-list">{vis.map(a => <button type="button" key={a.id} className={`ao-agent-row ${selecionado === a.id ? 'ao-selected' : ''}`} onClick={() => onSelecionar(a.id)} aria-pressed={selecionado === a.id}>
      <span className="ao-portrait-small" style={{ '--ao-agent': a.cor + '55' }}><Retrato nome={a.nome} cor={a.cor} tamanho={26} /></span>
      <span className="ao-agent-copy">
        <span className="ao-agent-head"><strong>{a.nome}</strong><Estado valor={a.status} /></span>
        <span>{a.papel}</span>
        <span className="ao-row-task" title={agoraDe(a)}>{agoraDe(a)}</span>
      </span>
    </button>)}</div>
  </>
}

// Precisa de você? Erros e bloqueios das últimas 24 h são o que pode pedir uma pessoa.
function Precisa({ m }) {
  if (!m) return null
  const n = (m.erros || 0) + (m.bloqueios || 0)
  return <div className={`ao-precisa ${n ? 'ao-precisa-sim' : ''}`} role="status">
    <strong>{n ? 'Precisa de você' : 'Nada pede você agora'}</strong>
    <span>{n ? `${n} ${n === 1 ? 'erro ou bloqueio' : 'erros ou bloqueios'} nas últimas 24 h. Veja as últimas ações.` : 'Ele segue sozinho dentro dos limites da política.'}</span>
  </div>
}

// Hora do relógio da barra i (0 = há 23 h, 23 = agora).
const horaDaBarra = i => `${new Date(Date.now() - (23 - i) * 3600e3).getHours()}h`

// Atividade por hora nas últimas 24 h: a barra mais alta ganha a cor do agente; a parte âmbar são erros e bloqueios.
function Horas({ h, cor }) {
  const max = Math.max(1, ...h.acoes), total = h.acoes.reduce((a, b) => a + b, 0)
  const pico = h.acoes.indexOf(Math.max(...h.acoes))
  const ultima = 23 - [...h.acoes].reverse().findIndex(v => v > 0)
  const resumo = total ? `${total} ${total === 1 ? 'etapa' : 'etapas'}; pico às ${horaDaBarra(pico)}, última atividade às ${horaDaBarra(ultima)}` : 'Nenhuma etapa nas últimas 24 h'
  return <div className="ao-caixa">
    <div className="ao-horas" role="img" aria-label={resumo}>
      {h.acoes.map((v, i) => <span key={i} className={v ? '' : 'ao-vazio'} style={{ '--h': v ? `${Math.max(12, (v / max) * 100)}%` : '6%', '--a': v ? `${(h.atencao[i] / v) * 100}%` : '0%', '--c': i === pico && v ? cor : '#7d8f93', '--d': `${i * 18}ms` }}
        title={`${horaDaBarra(i)}: ${v} etapas${h.atencao[i] ? `, ${h.atencao[i]} com erro ou bloqueio` : ''}`} />)}
    </div>
    <div className="ao-horas-eixo"><span>{horaDaBarra(0)}</span><span>agora</span></div>
    <span className="ao-horas-resumo">{resumo}</span>
  </div>
}

function Detalhe({ agente: a, mostrarCusto, resumoAntigo, amostra }) {
  const m = a.metricas
  const limites = LIMITES[a.nome] || []
  return <div className="ao-detail-grid">
    <div className="ao-col">
      <div className="ao-detail-top">
        <div className="ao-portrait" style={{ '--ao-agent': a.cor }}><Retrato nome={a.nome} cor={a.cor} tamanho={50} /></div>
        <div><h4>{a.nome}</h4><p>{a.papel}</p><Estado valor={a.status} /></div>
      </div>
      <p className="ao-description">{a.desc}</p>
      <span className="ao-sector">{TIMES[a.time]?.nome} · {a.ia ? 'Agente de IA' : 'Código'}</span>
    </div>

    <div className="ao-col">
      <div className="ao-section-label">Agora</div>
      <div className="ao-task"><strong>{a.tarefa}</strong>{a.atual
        ? <span>Caso #{curto(a.atual.caso_id)} · {a.ativos.length > 1 ? `${a.ativos.length} eventos em execução` : 'execução confirmada'}</span>
        : <span>{a.status === 'desconhecido' ? 'Aguardando um sinal atualizado.' : 'Esperando o próximo evento (resposta, pagamento ou horário).'}</span>}</div>
      {a.ativos.length > 1 && <div className="ao-parallel">{a.ativos.slice(1).map(x => <span key={x.id}>Também: #{curto(x.caso_id)} · {x.no}</span>)}</div>}
      <Precisa m={m} />
    </div>

    <div className="ao-col">
      <div className="ao-section-label">Últimas 24 h, hora a hora{resumoAntigo ? ' · desatualizadas' : ''}</div>
      {m?.por_hora ? <Horas h={m.por_hora} cor={a.cor} /> : <div className="ao-caixa"><span className="ao-horas-resumo">Sem medição nesta janela.</span></div>}
      <div className="ao-metrics">
        <div><strong>{m?.acoes ?? '—'}</strong><span>etapas</span></div>
        <div><strong>{m?.bloqueios ?? '—'}</strong><span>bloqueios</span></div>
        <div><strong>{m?.tempo_medio_ms != null ? (m.tempo_medio_ms >= 1000 ? `${(m.tempo_medio_ms / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s` : `${m.tempo_medio_ms} ms`) : '—'}</strong><span>tempo médio</span></div>
      </div>
      {amostra && <p className="ao-panel-note">Amostra das últimas 5.000 etapas da empresa nesta janela.</p>}
      {(m?.modelo || (mostrarCusto && m)) && <p className="ao-model" title={m?.modelo}>
        {[m?.modelo && `Modelo ${m.modelo}${m.versao_prompt ? ` · prompt ${m.versao_prompt}` : ''}`, m?.tokens != null && `${m.tokens.toLocaleString('pt-BR')} tokens`, mostrarCusto && `US$ ${Number(m.custo_usd || 0).toFixed(4)}`].filter(Boolean).join(' · ')}
      </p>}
    </div>

    <div className="ao-col">
      {limites.length > 0 && <>
        <div className="ao-section-label">Limites que ele segue</div>
        <div className="ao-limites">{limites.map(l => <span key={l}>{l}</span>)}</div>
      </>}
      <div className="ao-section-label">Últimas ações</div>
      <div className="ao-actions">{a.ultimas.length ? a.ultimas.slice(0, 4).map((p, i) => <div key={`${p.trace_id}-${p.no}-${p.criado_em}-${i}`}>
        <time>{hora(p.criado_em)}</time>
        <i style={{ background: p.resultado === 'erro' ? '#cf453c' : p.resultado === 'bloqueado' || p.resultado === 'aguardando' ? '#c98c28' : '#47986b' }} />
        <span>{p.explicacao || p.expli || p.no}</span>
      </div>) : <p className="ao-empty">Nenhuma etapa nas últimas 15 min.</p>}</div>
    </div>
  </div>
}

function Casos({ casos }) {
  const unicos = useMemo(() => [...new Map([...casos].reverse().map(c => [c.caso_id, c])).values()].reverse(), [casos])
  const sit = { pendente: 'Na fila', processando: 'Em execução', falhou: 'Falha no evento' }
  return <><p className="ao-panel-note">Casos com eventos na amostra recente. Um evento concluído não significa dívida quitada.</p>{unicos.length ? unicos.map(c => <article className="ao-case" key={c.caso_id}><header><strong>Caso #{curto(c.caso_id)}</strong><span>{sit[c.situacao] || c.situacao}</span></header><p>{c.tipo?.replaceAll('_', ' ')}</p><div className="ao-case-stages">{c.etapas?.map(n => <span key={n}>✓ {n}</span>)}{c.quem && <b>● {c.quem}</b>}</div>{c.situacao === 'processando' && !c.quem && <small>Sem sinal recente da etapa atual.</small>}</article>) : <p className="ao-empty">Nenhum evento pendente nesta amostra.</p>}</>
}

function Feed({ sinais }) {
  return sinais.length ? <ol className="ao-feed">{sinais.map(e => <li key={e.id}><time>{hora(e.t)}</time><i style={{ background: e.tipo === 'erro' ? '#c8463b' : e.resultado === 'bloqueado' ? '#c98c28' : e.tipo === 'fim' ? '#47986b' : e.tipo === 'handoff' ? '#7972bc' : '#5185b5' }} /><div>{mensagem(e)}<small>{e.tipo === 'handoff' ? 'Passagem registrada' : e.tipo === 'inicio' ? 'Início de etapa' : e.tipo === 'fim' ? 'Fim de etapa' : 'Falha registrada'}</small></div></li>)}</ol> : <p className="ao-empty">Os próximos eventos registrados aparecerão aqui.</p>
}

export default function EscritorioAgentes({ dados, nomeEmpresa, logoUrl, onPerfil, mostrarCusto }) {
  const [selecionado, setSelecionado] = useState('Orquestrador'), [painel, setPainel] = useState('agentes'), [seguir, setSeguir] = useState(false), [controle, setControle] = useState(null)
  const detalhe = useRef(null)
  // No celular a janela de detalhes fica longe da sala: ao escolher, ela vem para a vista.
  const selecionar = useCallback(nome => {
    setSelecionado(nome)
    const el = detalhe.current
    if (el && el.closest('.ao-office').getBoundingClientRect().width < 1000) requestAnimationFrame(() => el.scrollIntoView({ block: 'nearest', behavior: 'auto' }))
  }, [])
  const a = dados.agentes.find(x => x.nome === selecionado)
  const contagem = dados.agentes.reduce((acc, a) => ({ ...acc, [a.status]: (acc[a.status] || 0) + 1 }), {})
  const mover = (tipo, delta) => { setSeguir(false); setControle({ tipo, delta, id: Date.now() }) }
  const irDetalhes = () => { detalhe.current?.scrollIntoView({ block: 'nearest', behavior: 'auto' }); detalhe.current?.querySelector('h3')?.focus({ preventScroll: true }) }
  const ferramentas = [['agentes', Users, 'Agentes'], ['casos', FolderOpen, 'Casos'], ['atividade', Activity, 'Atividade']]
  return <section className="ao-office" aria-label="Sala dos agentes">
    <div className="ao-frame">
      <div className="ao-office-top">
        <div className="ao-office-brand"><span className="ao-brand-icon">M</span><div><h2>Sala dos Agentes</h2><p>{nomeEmpresa || 'MIZAN'} · Operação de cobrança</p></div></div>
        <div className="ao-counts">{Object.entries(ESTADOS).filter(([k]) => contagem[k]).map(([k, e]) => <span key={k}><i style={{ background: e.cor }} />{contagem[k]} {e.nome.toLowerCase()}</span>)}</div>
        <span className={`ao-connection ${dados.erro ? 'ao-disconnected' : ''}`} role="status"><Radio size={12} />{dados.erro ? 'Conexão interrompida' : !dados.estacao ? 'Conectando…' : dados.estacao.ligado === false ? 'Automação desligada' : `Atualizado ${hora(dados.atualizado)}`}</span>
      </div>
      {(dados.erro || dados.erroResumo) && <div className="ao-warning" role="status">{dados.estacao ? 'Mantendo os últimos dados disponíveis. Tentando reconectar…' : 'Não foi possível carregar a operação. Tentando novamente…'}</div>}

      <div className="ao-layout">
        <div className="ao-room">
          <SalaCanvas agentes={dados.agentes} sinais={dados.sinais} selecionado={selecionado} onSelecionar={selecionar} controle={controle} seguir={seguir} onManual={() => setSeguir(false)} nomeEmpresa={nomeEmpresa} logoUrl={logoUrl} obsoleto={dados.erro} />
          <div className="ao-toolbar">
            <div>
              {ferramentas.map(([id, Icon, label]) => <button type="button" className={painel === id ? 'ao-toolbar-active' : ''} key={id} onClick={() => setPainel(id)} aria-pressed={painel === id}><Icon size={17} /><span>{label}</span></button>)}
              <button type="button" onClick={irDetalhes}><Crosshair size={17} /><span>Detalhes</span></button>
            </div>
            <div>
              <button type="button" onClick={() => mover('zoom', -1)} title="Diminuir zoom" aria-label="Diminuir zoom"><Minus size={18} /></button>
              <button type="button" onClick={() => mover('zoom', 1)} title="Aumentar zoom" aria-label="Aumentar zoom"><Plus size={18} /></button>
              <button type="button" onClick={() => mover('centrar')} title="Centralizar sala" aria-label="Centralizar sala"><Scan size={18} /><span>Centralizar</span></button>
            </div>
          </div>
        </div>

        <div className="ao-right">
          {painel === 'agentes'
            ? <Janela titulo={`Agentes · ${dados.agentes.length}`} extra={<span className="ao-window-hint">role para ver todos</span>}>
                <Lista agentes={dados.agentes} selecionado={selecionado} onSelecionar={selecionar} />
              </Janela>
            : <Janela titulo={painel === 'casos' ? 'Casos' : 'Atividade'} fechar={() => setPainel('agentes')}>
                {painel === 'casos' ? <Casos casos={dados.casos} /> : <Feed sinais={dados.sinais} />}
              </Janela>}
        </div>
      </div>

      <div className="ao-detail" ref={detalhe}>
        <Janela titulo={a ? `${a.nome} · Detalhes` : 'Detalhes'} className="ao-window-wide"
          extra={a && <span className="ao-title-actions">
            <button type="button" className={seguir ? 'ao-follow-active' : ''} onClick={() => setSeguir(x => !x)} aria-pressed={seguir}><Crosshair size={12} />{seguir ? 'Seguindo' : 'Seguir na sala'}</button>
            <button type="button" onClick={() => onPerfil(a.nome)}><ArrowUpRight size={12} />Perfil completo</button>
          </span>}>
          {a ? <Detalhe agente={a} mostrarCusto={mostrarCusto} resumoAntigo={dados.erroResumo} amostra={dados.amostra} /> : <p className="ao-empty">Selecione um agente na sala ou na lista.</p>}
        </Janela>
      </div>
    </div>
  </section>
}
