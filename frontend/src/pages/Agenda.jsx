// F2 — Agenda: retornos e promessas, separados em Alto · Médio · Tranquilo.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Users, ClipboardList, Bot, CalendarClock, Check, Loader2, PhoneCall, RotateCcw } from 'lucide-react'
import AppShell from '../components/AppShell'
import CabecalhoPagina from '../components/CabecalhoPagina'
import { AgendaBentoCard } from '../components/ui/bento'
import DemandasAdministrativas from '../components/DemandasAdministrativas'
import ErroCarga from '../components/ErroCarga'
import AvisoDesfazer from '../components/AvisoDesfazer'
import FichaPassagem, { SeloPrioridade } from '../components/FichaPassagem'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { useAoMudarNoServidor } from '../components/useMudancasDoServidor'
import { classificarErro, listarAgenda, listarEquipeAgenda, mudarAgenda, buscarPaginaRanking, listarEmpresas, carregarCarteira, agenteAtribuir, listarTarefasAdministrativas } from '../api'
import { NIVEIS, TIPO_LABEL, quando, hojeISO, somarDias, avisarAgendaMudou } from '../utils/agenda'

const fmtBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)
const ID_ADMINISTRACAO = 'a-definir'
const ID_VIRTUAIS = 'agente-mizan'
const AREAS = ['operadores', 'administracao', 'virtuais']
const ehOperador = o =>![ID_ADMINISTRACAO, ID_VIRTUAIS].includes(o.id)

function AtribuirAtendimento({ item, operadores, onAtribuir }) {
  const [escolha, setEscolha] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState(null)
  async function atribuir() {
    if (!escolha || salvando) return
    setSalvando(true); setErro(null)
    try { await onAtribuir(item, escolha) } catch (e) { setErro(e) } finally { setSalvando(false) }
  }
  return <div className="mt-3 space-y-2 border-t border-line pt-3">
    <label className="block text-xs font-medium text-ink" htmlFor={`atribuir-${item.id}`}>Qual operador vai atender este cliente?</label>
    <div className="flex flex-wrap gap-2">
      <select id={`atribuir-${item.id}`} value={escolha} disabled={salvando} onChange={e => setEscolha(e.target.value)} className="min-h-[40px] min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-2 text-sm text-ink">
        <option value="">Escolha o operador</option>
        {operadores.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
      </select>
      <button type="button" disabled={!escolha || salvando} onClick={atribuir} className="btn-primary btn-sm disabled:opacity-50">{salvando ? 'Aprovando…' : 'Aprovar e atribuir'}</button>
    </div>
    {!operadores.length && <p className="text-xs text-ink-2">Cadastre um operador ativo em Configurações → Usuários para atribuir este atendimento.</p>}
    <ErroCarga erro={erro} compacto />
  </div>
}

function Remarcar({ item, onSalvar, onCancelar }) {
  const [data, setData] = useState(somarDias(hojeISO(), 1))
  const [hora, setHora] = useState(item.hora || '')
  return (
    <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-line bg-surface-2 p-2.5">
      <label className="text-xs text-ink-2">Nova data
        <input type="date" value={data} min={hojeISO()} onChange={e => setData(e.target.value)}
          className="mt-1 block rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink [color-scheme:dark]" />
      </label>
      <label className="text-xs text-ink-2">Hora
        <input type="time" value={hora} onChange={e => setHora(e.target.value)}
          className="mt-1 block rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink [color-scheme:dark]" />
      </label>
      <button onClick={() => onSalvar(data, hora || null)} disabled={!data} className="btn-primary btn-sm">Salvar</button>
      <button onClick={onCancelar} className="btn-ghost btn-sm">Cancelar</button>
    </div>
  )
}

const O_QUE = { cumprir: 'marcar como cumprida', quebrar: 'marcar como não paga', cancelar: 'cancelar', remarcar: 'remarcar' }

// A falha de uma ação aparece no cartão do próprio devedor: o que não
// aconteceu, o motivo e, quando faz sentido, refazer a mesma ação.
function FalhaNoCartao({ erro }) {
  const c = classificarErro(erro.e)
  return (
    <div role="alert" className="mt-3 rounded-lg px-3 py-2 text-xs"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', borderLeft: '3px solid var(--danger)' }}>
      <p className="font-semibold text-ink">Não foi possível {erro.oque}.</p>
      <p className="mt-0.5 leading-relaxed text-ink-2">{c.mensagem}</p>
      {c.podeTentar && (
        <button type="button" onClick={erro.refazer}
          className="mt-1 inline-flex min-h-[32px] items-center gap-1 font-semibold text-accent-text hover:opacity-80">
          <RotateCcw className="h-3 w-3" aria-hidden="true" /> Tentar novamente
        </button>
      )}
    </div>
  )
}

const SITUACAO_RESOLVIDA = { cumprida: 'Cumprida', quebrada: 'Não paga', cancelada: 'Cancelada' }
const hora = (iso) => iso ? new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date(iso)) : ''

// Resolvido hoje: fica à mão para desfazer um clique errado, mesmo depois de recarregar.
function ItemResolvido({ item, mostrarOperador, podeDesfazer, onDesfazer }) {
  const [ocupado, setOcupado] = useState(false)
  // Promessa cumprida por pagamento confirmado só volta pelo próprio Pagamentos.
  const reabre = podeDesfazer && item.resolvido_por !== 'pagamento confirmado'
  async function desfazer() { setOcupado(true); try { await onDesfazer(item) } finally { setOcupado(false) } }
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-line bg-surface p-4">
      <div className="min-w-0 flex-1 basis-48">
        <p className="truncate text-sm font-semibold text-ink">{item.nome || item.cpf}</p>
        <p className="text-xs text-ink-2">
          {TIPO_LABEL[item.tipo]} de {quando(item.data, item.hora).toLowerCase()}
          {mostrarOperador && item.operador_nome ? ` · ${item.operador_nome}` : ''}
        </p>
      </div>
      <span className="text-sm font-medium text-ink">{SITUACAO_RESOLVIDA[item.situacao] ?? item.situacao}
        <span className="font-normal text-ink-2"> às {hora(item.resolvido_em)}</span></span>
      {reabre
        ? <button type="button" disabled={ocupado} onClick={desfazer} className="btn-secondary btn-sm min-h-[40px] disabled:opacity-60">
            {ocupado ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Desfazer
          </button>
        : item.resolvido_por === 'pagamento confirmado' && <span className="text-xs text-ink-2">Paga por pagamento confirmado</span>}
    </li>
  )
}

/* ── Fila + atendimento (canvas "Agenda · Atendimentos virtuais") ──────────
   À esquerda, a fila agrupada por prazo (Atrasados · Hoje e amanhã · Próximos);
   à direita, um atendimento por vez: por que está com você, o que fazer, a
   oferta que pode usar e "Como terminou?". Resolver passa para o próximo. */
const GRUPO_FILA = {
  alto: { nome: 'Atrasados', cor: 'var(--danger)' },
  medio: { nome: 'Hoje e amanhã', cor: 'var(--warning)' },
  safe: { nome: 'Próximos', cor: 'var(--text-muted)' },
}
const iniciais = (nome) => String(nome || '?').split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase()
const umaHora = () => { const d = new Date(Date.now() + 3600000); return { data: hojeISO(), hora: `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}` } }

function FilaAgenda({ grupos, selecionado, onSelecionar }) {
  return (
    <aside aria-label="Fila de atendimentos" className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-2.5">
      {NIVEIS.map(n => (
        <div key={n} className="flex flex-col gap-1">
          <div className="flex items-center justify-between px-3 pb-1.5 pt-3">
            <span className="text-xs font-bold uppercase tracking-[0.14em]" style={{ color: n === 'alto' ? 'var(--danger)' : 'var(--text-muted)' }}>{GRUPO_FILA[n].nome}</span>
            <span className="text-xs tabular-nums text-ink-3">{grupos[n].length}</span>
          </div>
          {!grupos[n].length && <p className="px-3 pb-2 text-xs text-ink-3">Nada aqui.</p>}
          {grupos[n].map(i => {
            const atual = i.id === selecionado
            return (
              <button key={i.id} type="button" onClick={() => onSelecionar(i.id)} aria-current={atual || undefined}
                className={`flex w-full items-start gap-3 rounded-[14px] border p-3 text-left transition-colors ${atual ? 'border-[var(--border-strong)] bg-[var(--raised)]' : 'border-transparent hover:bg-raise-1'}`}>
                <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: GRUPO_FILA[n].cor }} aria-hidden="true" />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex justify-between gap-2">
                    <b className="truncate text-[15px] font-semibold text-ink">{i.nome || i.cpf}</b>
                    <span className="shrink-0 whitespace-nowrap text-xs text-ink-3">{quando(i.data, i.hora)}</span>
                  </span>
                  <span className="truncate text-[13px] text-ink-2">{i.passagem?.o_que_quer || i.observacao || TIPO_LABEL[i.tipo]}</span>
                </span>
              </button>
            )
          })}
        </div>
      ))}
    </aside>
  )
}

function Atendimento({ item, onAcao, onAbrir, soLeitura, meuId, operadores, onAtribuir }) {
  const navigate = useNavigate()
  const [abrindo, setAbrindo] = useState(false)
  const [erro, setErro] = useState(null)             // { e, oque, refazer }
  const [remarcando, setRemarcando] = useState(false)
  const [ocupado, setOcupado] = useState(null)
  useEffect(() => { setErro(null); setRemarcando(false); setOcupado(null) }, [item.id])
  const promessa = item.tipo === 'promessa'
  const aguardandoAprovacao = item.operador_id === ID_ADMINISTRACAO
  const ligar = !!meuId && item.operador_id === meuId
  const atrasado = item.nivel === 'alto'
  const p = item.passagem
  async function abrir() {
    if (abrindo) return
    setAbrindo(true); setErro(null)
    try { await onAbrir(item) } catch (e) { setErro({ e, oque: 'abrir o devedor', refazer: abrir }) } finally { setAbrindo(false) }
  }
  async function agir(acao, extra) {
    if (ocupado) return
    setOcupado(acao); setErro(null)
    try { await onAcao(item, acao, extra); setRemarcando(false) }
    catch (e) { setErro({ e, oque: O_QUE[acao] ?? 'concluir', refazer: () => agir(acao, extra) }) }
    finally { setOcupado(null) }
  }
  const porque = p?.situacao || item.observacao || (promessa
    ? `Prometeu pagar${item.valor > 0 ? ` ${fmtBRL(item.valor)}` : ''} nesta data.`
    : 'Retorno combinado com o cliente.')
  const oQueFazer = p?.proximo_passo || p?.sugestao?.resumo || (promessa ? 'Conferir se o pagamento entrou' : 'Fazer o retorno combinado')
  const detalheFazer = p?.proximo_passo && p?.sugestao ? `${p.sugestao.resumo}. ${p.sugestao.motivo || ''}` : p?.sugestao?.motivo
    || (promessa ? 'Se não entrou, ligue e pergunte o que aconteceu antes de marcar como não paga.' : 'Ligue no horário combinado e registre como terminou.')
  const oferta = p?.sugestao?.resumo || (p?.tentado?.length ? `Já oferecido: ${p.tentado.slice(-2).map(t => t.resumo).join(' · ')}` : null)
  const resultados = aguardandoAprovacao ? [] : promessa
    ? [['cumprir', 'Pagou'], ['quebrar', 'Não pagou']]
    : [['cumprir', 'Feito'], ['cancelar', 'Cancelar retorno']]
  const chip = 'inline-flex h-9 items-center rounded-full border border-line px-3.5 text-[13px] text-ink-2 hover:border-[var(--border-strong)] hover:text-ink disabled:opacity-40'

  return (
    <section aria-label="Atendimento selecionado" className="overflow-hidden rounded-2xl border border-line bg-surface">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-6 py-6 sm:px-7"
        style={{ background: 'linear-gradient(160deg, color-mix(in srgb, var(--royal) 10%, transparent), transparent 60%)' }}>
        <div className="flex min-w-0 items-center gap-3.5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[var(--royal-soft)] text-base font-bold text-accent-text" aria-hidden="true">{iniciais(item.nome)}</span>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="break-words text-[22px] font-bold leading-tight text-ink">{item.nome || item.cpf}</span>
            <span className="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
              CPF {item.cpf} · {TIPO_LABEL[item.tipo]}{item.operador_nome && item.operador_id !== meuId ? ` · ${item.operador_nome}` : ''}
              <SeloPrioridade passagem={p} />
            </span>
          </div>
        </div>
        <div className="flex gap-6">
          {promessa && item.valor > 0 && <div className="flex flex-col items-end"><span className="text-xs text-ink-3">Prometido</span><b className="text-lg tabular-nums text-ink">{fmtBRL(item.valor)}</b></div>}
          {p?.valor_dito > 0 && <div className="flex flex-col items-end"><span className="text-xs text-ink-3">Consegue por mês</span><b className="text-lg tabular-nums text-ink">{fmtBRL(p.valor_dito)}</b></div>}
          <div className="flex flex-col sm:items-end"><span className="text-xs text-ink-3">Combinado para</span>
            <b className="text-lg" style={{ color: atrasado ? 'var(--danger)' : 'var(--text)' }}>{quando(item.data, item.hora)}</b></div>
        </div>
      </div>

      <div className="grid gap-[18px] px-6 py-6 sm:px-7 md:grid-cols-2">
        <div className="flex flex-col gap-2.5">
          <span className="section-label">Por que está com você</span>
          <p className="text-[15px] leading-relaxed text-ink">{porque}</p>
          {p?.o_que_quer && <>
            <span className="section-label mt-2">O que o cliente quer</span>
            <div className="max-w-full self-start rounded-[18px_18px_18px_6px] border border-[var(--border)] bg-[var(--raised)] px-3.5 py-3 text-[15px] leading-relaxed text-ink">“{p.o_que_quer}”</div>
          </>}
        </div>
        <div className="flex flex-col gap-2.5">
          <span className="section-label">O que fazer</span>
          <div className="flex flex-col gap-1.5 rounded-[18px] border border-[var(--border-strong)] bg-[var(--royal-soft)] px-[18px] py-4">
            <b className="text-[17px] text-ink">{oQueFazer}</b>
            {detalheFazer && <span className="text-sm leading-relaxed text-ink-2">{detalheFazer}</span>}
          </div>
          {oferta && (
            <div className="flex flex-col gap-1.5 rounded-[18px] border border-line bg-canvas px-4 py-3.5">
              <span className="text-[13px] text-ink-3">Oferta que pode usar</span>
              <span className="text-[15px] text-ink">{oferta}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3.5 border-t border-line px-6 pb-[26px] pt-5 sm:px-7">
        {!soLeitura && onAtribuir && aguardandoAprovacao && <AtribuirAtendimento item={item} operadores={operadores} onAtribuir={onAtribuir} />}
        {!soLeitura && (remarcando
          ? <Remarcar item={item} onCancelar={() => setRemarcando(false)} onSalvar={(data, hora) => agir('remarcar', { data, hora })} />
          : <>
              {!!resultados.length && <>
                <span className="text-sm text-ink-2">Como terminou?</span>
                <div className="flex flex-wrap gap-2">
                  {resultados.map(([acao, rotulo]) => (
                    <button key={acao} type="button" disabled={!!ocupado} aria-busy={ocupado === acao} onClick={() => agir(acao)}
                      className="inline-flex h-11 items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--raised)] px-4 text-sm font-semibold text-ink hover:border-[var(--border-strong)] disabled:opacity-40">
                      {ocupado === acao ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}{rotulo}
                    </button>
                  ))}
                </div>
              </>}
              {aguardandoAprovacao && (
                <button type="button" disabled={!!ocupado} onClick={() => agir('cancelar')} className="btn-ghost-danger btn-sm self-start">Recusar solicitação</button>
              )}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="mr-1 text-sm text-ink-2">Remarcar:</span>
                <button type="button" disabled={!!ocupado} className={chip} onClick={() => agir('remarcar', umaHora())}>Em 1 hora</button>
                <button type="button" disabled={!!ocupado} className={chip} onClick={() => agir('remarcar', { data: somarDias(hojeISO(), 1), hora: '09:00' })}>Amanhã, 9h</button>
                <button type="button" disabled={!!ocupado} className={chip} onClick={() => setRemarcando(true)}>Escolher dia…</button>
              </div>
            </>)}
        {erro && <FalhaNoCartao erro={erro} />}
        {p && <FichaPassagemRetorno passagem={p} predicaoId={item.predicao_id} />}
        <div className="flex flex-wrap gap-4 text-sm font-semibold">
          {item.predicao_id && <button type="button" onClick={() => navigate(`/pasta/${item.predicao_id}`, { state: { devedor: { nome: item.nome }, de: '/agenda' } })} className="text-accent-text hover:underline">Abrir pasta do cliente ↗</button>}
          {item.predicao_id && <button type="button" onClick={() => navigate(`/pasta/${item.predicao_id}?aba=conversa`, { state: { devedor: { nome: item.nome }, de: '/agenda' } })} className="text-accent-text hover:underline">Ver conversa inteira ↗</button>}
          {item.carteira_id
            ? <button type="button" onClick={abrir} disabled={abrindo} className={ligar ? 'btn-primary btn-sm ml-auto' : 'text-accent-text hover:underline disabled:opacity-60'}>
                {abrindo ? 'Abrindo…' : ligar ? <><PhoneCall className="h-3.5 w-3.5" aria-hidden="true" /> Ligar agora</> : 'Ficha do devedor ↗'}
              </button>
            : <span className="text-xs font-normal text-ink-3">Sem carteira ligada</span>}
        </div>
      </div>
    </section>
  )
}

/* Só a pergunta "o resumo ajudou?" da ficha de passagem: o resto já está no atendimento. */
function FichaPassagemRetorno({ passagem, predicaoId }) {
  if (!predicaoId) return null
  return <details className="text-xs text-ink-3"><summary className="cursor-pointer">Resumo completo do agente</summary><FichaPassagem passagem={passagem} predicaoId={predicaoId} /></details>
}

export default function Agenda() {
  const { token, usuario, isAdmin, isComando } = useAuth()
  // COMANDO consulta a agenda de uma empresa, sem alterar (quem resolve é a operação).
  const [empresas, setEmpresas] = useState([])
  const [alvo, setAlvo] = useState('')
  useEffect(() => {
    if (!isComando) return
    listarEmpresas(token).then(d => setEmpresas(d.empresas || [])).catch(() => {})
  }, [isComando, token])
  const navigate = useNavigate()
  const { result, setResult } = useAnalysis()
  const carteiraAberta = result?.resumo?.carteira_id ?? result?.carteira_id ?? null
  const location = useLocation()
  const gestor = isAdmin || isComando
  // Escopo, área e operador moram na URL (/agenda?area=operadores&op=…): o voltar do
  // navegador sobe um nível, recarregar mantém a tela e o link pode ser enviado.
  const [params, setParams] = useSearchParams()
  const escopo = isAdmin && params.get('escopo') === 'minha' ? 'minha' : (gestor ? 'equipe' : 'minha')
  const areaEquipe = gestor && escopo === 'equipe' && AREAS.includes(params.get('area')) ? params.get('area') : null
  const operadorId = areaEquipe === 'operadores' ? params.get('op') : null
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)          // falha ao carregar a lista
  const [erroAcao, setErroAcao] = useState(null)  // falha numa ação (resolver, remarcar, abrir)
  const [aviso, setAviso] = useState('')
  const [desfazer, setDesfazer] = useState(null)  // aviso com "Desfazer" no rodapé
  const [selecionado, setSelecionado] = useState(null)
  const [resolvidosHoje, setResolvidosHoje] = useState(null)
  const [vista, setVista] = useState('pendentes')  // pendentes | resolvidos (hoje)
  // Administração: 'Equipe' mostra primeiro os operadores; só ao escolher um abre a agenda dele.
  const [equipe, setEquipe] = useState(null)
  const [tarefasPendentes, setTarefasPendentes] = useState(0)
  const requisicao = useRef(0)
  const operador = useMemo(() => {
    if (areaEquipe === 'administracao') return { id: ID_ADMINISTRACAO, nome: 'Demandas de agenda para administração' }
    if (areaEquipe === 'virtuais') return { id: ID_VIRTUAIS, nome: 'Atendimentos virtuais' }
    if (!operadorId) return null
    return { id: operadorId, nome: equipe?.operadores?.find(o => o.id === operadorId)?.nome ?? '' }
  }, [areaEquipe, operadorId, equipe])
  // Muda o nível da Agenda empilhando no histórico. `null` apaga a chave.
  const irPara = useCallback((mudancas, { substituir = false } = {}) => {
    setParams(atual => {
      const novo = new URLSearchParams(atual)
      for (const [k, v] of Object.entries(mudancas)) v == null ? novo.delete(k) : novo.set(k, v)
      return novo
    }, { replace: substituir })
  }, [setParams])
  // Trocou de nível (por clique ou pelo voltar do navegador): a lista anterior não vale mais.
  useEffect(() => { setDados(null); setVista('pendentes') }, [escopo, areaEquipe, operadorId])
  const naLista = gestor && escopo === 'equipe' && !operador
  const naEntrada = naLista && !areaEquipe
  const listaOperadores = (equipe?.operadores ?? []).filter(ehOperador)
  const resumoAdmin = equipe?.operadores?.find(o => o.id === ID_ADMINISTRACAO)
  const resumoVirtuais = equipe?.operadores?.find(o => o.id === ID_VIRTUAIS)
  const resolvidos = vista === 'resolvidos'

  const carregar = useCallback(() => {
    const pedido = ++requisicao.current
    if (isComando && !alvo) { setDados(null); setEquipe(null); setCarregando(false); return }
    setCarregando(true); setErro(null); setErroAcao(null)
    const empresa_id = isComando ? alvo : undefined
    const busca = naLista
      ? Promise.all([
          listarEquipeAgenda({ empresa_id }).then(r => { if (pedido === requisicao.current) setEquipe(r) }),
          listarTarefasAdministrativas({ empresa_id, limite: 1 }).then(r => { if (pedido === requisicao.current) setTarefasPendentes(r.total) }),
        ])
      : Promise.all([
          listarAgenda({ escopo, empresa_id, operador_id: operador?.id, situacao: resolvidos ? 'resolvidos_hoje' : undefined }).then(r => { if (pedido === requisicao.current) setDados(r) }),
          // "N de M resolvidos hoje" no topo: só a contagem dos resolvidos de hoje.
          resolvidos ? null : listarAgenda({ escopo, empresa_id, operador_id: operador?.id, situacao: 'resolvidos_hoje' })
            .then(r => { if (pedido === requisicao.current) setResolvidosHoje((r.itens || []).length) }).catch(() => {}),
          // Entrou direto pelo link (ou voltou pelo navegador) na agenda de um operador:
          // a equipe ainda não veio e é ela que dá o nome e a lista do seletor.
          operadorId && !equipe ? listarEquipeAgenda({ empresa_id }).then(r => { if (pedido === requisicao.current) setEquipe(r) }) : null,
        ])
    return busca.catch(e => { if (pedido === requisicao.current) setErro(e) }).finally(() => { if (pedido === requisicao.current) setCarregando(false) })
  }, [escopo, isComando, alvo, resolvidos, operador?.id, naLista]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { carregar(); return () => { requisicao.current++ } }, [carregar])

  // Ao vivo: o agente (ou outra pessoa) mudou a agenda. Recarrega em silêncio, sem
  // spinner e sem mexer no que a pessoa está fazendo; só troca a lista se ela mudou.
  const carregandoRef = useRef(false)
  carregandoRef.current = carregando
  const recarregarQuieto = useCallback(() => {
    if (carregandoRef.current || (isComando && !alvo)) return
    const base = requisicao.current
    const empresa_id = isComando ? alvo : undefined
    const trocar = (set) => (r) => {
      if (base !== requisicao.current) return           // a pessoa mudou de tela nesse meio-tempo
      set(atual => (JSON.stringify(atual) === JSON.stringify(r) ? atual : r))
    }
    if (naLista) {
      listarEquipeAgenda({ empresa_id }).then(trocar(setEquipe)).catch(() => {})
      listarTarefasAdministrativas({ empresa_id, limite: 1 })
        .then(r => { if (base === requisicao.current) setTarefasPendentes(r.total) }).catch(() => {})
    } else {
      listarAgenda({ escopo, empresa_id, operador_id: operador?.id, situacao: resolvidos ? 'resolvidos_hoje' : undefined })
        .then(trocar(setDados)).catch(() => {})
    }
  }, [escopo, isComando, alvo, resolvidos, operador?.id, naLista])
  useAoMudarNoServidor('agenda', recarregarQuieto)

  const grupos = useMemo(() => {
    const g = { alto: [], medio: [], safe: [] }
    for (const i of dados?.itens ?? []) (g[i.nivel] ?? g.safe).push(i)
    for (const k in g) g[k].sort((a, b) => String(a.data).localeCompare(String(b.data)) || String(a.hora || '99:99').localeCompare(String(b.hora || '99:99')))
    return g
  }, [dados])

  const ordenar = (lista) => [...lista].sort((a, b) =>
    String(a.data).localeCompare(String(b.data)) || String(a.hora || '99:99').localeCompare(String(b.hora || '99:99')))

  async function atribuirAtendimento(item, operadorId) {
    const r = await agenteAtribuir(item.id, operadorId, isComando ? alvo : undefined)
    setDados(d => d ? ({ ...d, itens: d.itens.filter(i => i.id !== item.id) }) : d)
    setEquipe(await listarEquipeAgenda({ empresa_id: isComando ? alvo : undefined }))
    setAviso(`${item.nome || 'Cliente'}: reunião aprovada e atribuída a ${r.operador.nome}.`)
    avisarAgendaMudou()
  }

  function abrirArea(area) {
    irPara({ area, op: null })
  }

  async function acao(item, acao, extra) {
    setAviso(''); setErroAcao(null)
    // Uma falha sobe para o cartão do devedor, que mostra o erro no lugar certo.
    const r = await mudarAgenda(item.id, acao, extra)
    setDados(d => ({
      ...d,
      itens: r.item.situacao === 'pendente'
        ? d.itens.map(i => i.id === item.id ? { ...i, ...r.item } : i)
        : d.itens.filter(i => i.id !== item.id),
    }))
    avisarAgendaMudou()
    if (r.item.situacao !== 'pendente') setResolvidosHoje(n => (n ?? 0) + 1)
    const nome = (item.nome || 'devedor').split(' ')[0]
    if (acao === 'remarcar') {
      // Remarcar não some da lista e pode ser refeito: basta a confirmação.
      setAviso(`${nome}: remarcado para ${quando(r.item.data, r.item.hora).toLowerCase()}.`)
      return
    }
    // Quem pode registrar o pagamento ganha o atalho já preenchido no aviso.
    const registrar = acao === 'cumprir' && item.tipo === 'promessa' && gestor
    const texto = {
      cumprir: item.tipo === 'promessa'
        ? (registrar ? `${nome}: promessa cumprida.` : `${nome}: promessa cumprida. Registre o pagamento em Pagamentos.`)
        : `${nome}: retorno feito.`,
      quebrar: `${nome}: promessa marcada como não paga.`,
      cancelar: item.operador_id === ID_ADMINISTRACAO ? `${nome}: solicitação recusada.` : `${nome}: retorno cancelado.`,
    }[acao]
    // Desfazer de verdade: reabre no servidor, só se ninguém mexeu depois.
    setDesfazer({
      id: `${item.id}-${Date.now()}`, texto, desfeito: 'Desfeito. O compromisso voltou para a Agenda.',
      acao: registrar ? { rotulo: 'Registrar pagamento', onClick: () => navigate('/feedback', {
        state: { registrar: { devedor: { id: item.predicao_id, cpf: item.cpf, nome: item.nome }, valor: item.valor } } }) } : undefined,
      desfazer: async () => {
        const v = await mudarAgenda(item.id, 'reabrir', { situacao_esperada: r.item.situacao })
        setDados(d => ({ ...d, itens: ordenar([...d.itens.filter(i => i.id !== item.id), { ...item, ...v.item }]) }))
        setResolvidosHoje(n => Math.max(0, (n ?? 1) - 1))
        setSelecionado(item.id)
        avisarAgendaMudou()
      },
    })
  }

  async function desfazerResolvido(item) {
    setAviso(''); setErroAcao(null)
    try {
      await mudarAgenda(item.id, 'reabrir', { situacao_esperada: item.situacao })
      setDados(d => ({ ...d, itens: d.itens.filter(i => i.id !== item.id) }))
      avisarAgendaMudou()
      setAviso(`${(item.nome || 'devedor').split(' ')[0]}: voltou para a Agenda.`)
    } catch (e) { setErroAcao(e) }
  }

  // Falhas sobem para o cartão do devedor (Item), que mostra o erro no lugar certo.
  async function abrir(item) {
    setErroAcao(null)
    // Devedor de outra carteira: abre a carteira dele antes (o servidor só
    // entrega carteiras da empresa de quem pede).
    if (item.carteira_id !== carteiraAberta) {
      const carteira = await carregarCarteira(item.carteira_id)
      setResult(carteira)
    }
    const p = await buscarPaginaRanking(item.carteira_id, { busca: item.cpf, limit: 1 })
    const rank = p.itens?.[0]?.rank
    // O compromisso vai junto: a ficha mostra o que foi combinado e a oferta.
    if (rank) navigate(`/devedor/${rank}`, { state: { deAgenda: item, voltar: { para: location.pathname + location.search, rotulo: 'Voltar à agenda' } } })
    else throw new Error('Este devedor não está mais nessa carteira (ela pode ter sido analisada de novo).')
  }

  const total = (dados?.itens ?? []).length
  // O atendimento aberto: o escolhido, ou o primeiro da fila (do mais atrasado ao mais tarde).
  const naOrdem = [...grupos.alto, ...grupos.medio, ...grupos.safe]
  const atual = naOrdem.find(i => i.id === selecionado) || naOrdem[0] || null

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <CabecalhoPagina
          voltar={areaEquipe === 'operadores' && operador ? { to: '/agenda?area=operadores', rotulo: 'Operadores' }
            : areaEquipe ? { to: '/agenda', rotulo: 'Agenda' } : undefined}
          rotulo={areaEquipe ? 'Agenda · Hoje' : 'Hoje'}
          icone={areaEquipe === 'virtuais' ? Bot : areaEquipe === 'administracao' ? ClipboardList : areaEquipe === 'operadores' ? Users : CalendarClock}
          titulo={areaEquipe === 'virtuais' ? 'Atendimentos virtuais' : areaEquipe === 'administracao' ? 'Demandas para administração'
            : areaEquipe === 'operadores' ? (operador?.nome ? `Agenda de ${operador.nome}` : 'Operadores') : 'Agenda'}
          ajuda="agenda-de-retorno" className="!mb-0"
          subtitulo={naEntrada ? 'Escolha uma área da agenda.'
                : naLista ? 'Escolha um operador para ver a agenda dele.'
                : areaEquipe === 'administracao' ? 'Aprovação de reuniões e demandas administrativas.'
                : areaEquipe === 'virtuais' ? 'Clientes que o agente passou para uma pessoa. Um por vez, do mais atrasado ao mais tarde.'
                : operador ? (operador.nome ? `Agenda de ${operador.nome}.` : 'Agenda do operador.')
                : 'Seus compromissos, um por vez, do mais atrasado ao mais tarde.'}>
          <div className="flex min-w-0 flex-wrap items-center gap-2.5">
            {!naLista && !resolvidos && dados?.ativo && resolvidosHoje != null && (
              <div className="flex min-w-[200px] flex-col items-start gap-2 sm:items-end">
                <span className="text-sm text-ink-2"><b className="text-lg tabular-nums text-ink">{resolvidosHoje}</b> de {resolvidosHoje + total} resolvidos hoje</span>
                <div className="h-2 w-[200px] overflow-hidden rounded-full bg-[var(--raised)]" aria-hidden="true">
                  <div className="h-full rounded-full bg-[var(--success)] transition-[width] duration-500" style={{ width: `${resolvidosHoje + total ? Math.round(resolvidosHoje / (resolvidosHoje + total) * 100) : 0}%` }} />
                </div>
              </div>
            )}
            {isComando && (
              <select value={alvo} onChange={e => { setAlvo(e.target.value); setEquipe(null); irPara({ area: null, op: null }, { substituir: true }) }} aria-label="Empresa"
                className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink focus:outline-none [color-scheme:dark]">
                <option value="">Escolha a empresa…</option>
                {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.nome_exibicao || e.empresa_id}</option>)}
              </select>
            )}
            {gestor && escopo === 'equipe' && areaEquipe === 'operadores' && (
              <div className="flex min-w-0 items-center gap-2 text-xs font-medium text-ink-2">
                <label htmlFor="agenda-operador">Operador</label>
                <select id="agenda-operador" value={operador?.id ?? ''} disabled={!listaOperadores.length}
                  onChange={e => irPara({ op: e.target.value || null }, { substituir: true })}
                  className="min-h-[40px] min-w-0 max-w-[240px] rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink disabled:opacity-50">
                  <option value="">{listaOperadores.length ? 'Selecione um operador' : 'Nenhum operador ativo'}</option>
                  {listaOperadores.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
                </select>
              </div>
            )}
            {isAdmin && (
              <div role="group" aria-label="De quem é a agenda" className="flex rounded-[14px] border border-line bg-surface p-1">
                {[['minha', 'Minha agenda'], ['equipe', 'Equipe']].map(([k, l]) => (
                  <button key={k} aria-pressed={escopo === k} onClick={() => irPara({ escopo: k === 'minha' ? 'minha' : null, area: null, op: null })}
                    className={`h-9 rounded-[10px] px-4 text-sm transition-colors ${escopo === k ? 'bg-[var(--raised)] font-semibold text-ink' : 'font-medium text-ink-2 hover:text-ink'}`}>
                    {l}
                  </button>
                ))}
              </div>
            )}
            <button onClick={carregar} aria-label="Atualizar"
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-line bg-surface text-ink-2 hover:text-ink">
              <RotateCcw className={`h-3.5 w-3.5 ${carregando ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </CabecalhoPagina>

        {aviso && <p className="flex items-center gap-1.5 text-sm text-emerald-400"><Check className="h-4 w-4" /> {aviso}</p>}
        <ErroCarga erro={erro} onTentar={carregar} />
        <ErroCarga erro={erroAcao} onTentar={carregar} compacto />

        {naLista && equipe?.ativo === false && (
          <div className="rounded-2xl border border-line bg-surface p-6 text-sm text-ink-2">{equipe.mensagem}</div>
        )}
        {naEntrada && equipe?.ativo && (
          <ul className="agenda-equipe-bento-grid" aria-label="Áreas da agenda">
            <li><AgendaBentoCard nome="Operadores" total={listaOperadores.reduce((s, o) => s + o.total, 0)} icone={Users}
              acao="Ver operadores" onAbrir={() => abrirArea('operadores')} /></li>
            <li><AgendaBentoCard nome="Demandas de agenda para administração" total={(resumoAdmin?.total ?? 0) + tarefasPendentes} icone={ClipboardList}
              legenda="demandas pendentes" acao="Ver demandas" onAbrir={() => abrirArea('administracao')} /></li>
            <li><AgendaBentoCard nome="Atendimentos virtuais" total={resumoVirtuais?.total ?? 0} icone={Bot}
              acao="Ver atendimentos" onAbrir={() => abrirArea('virtuais')} /></li>
          </ul>
        )}
        {naLista && areaEquipe === 'operadores' && equipe?.ativo && (
          listaOperadores.length === 0
            ? <div className="rounded-2xl border border-line bg-surface px-6 py-10 text-center text-sm text-ink-2">Nenhum operador ativo nesta empresa.</div>
            : (
              <ul className="agenda-equipe-bento-grid" aria-label="Minha equipe">
                {listaOperadores.map(o => (
                  <li key={o.id}>
                    <AgendaBentoCard nome={o.nome} total={o.total} descricao="Acompanhe os compromissos e retornos deste operador."
                      onAbrir={() => irPara({ op: o.id })} />
                  </li>
                ))}
              </ul>
            )
        )}

        {isComando && !alvo && (
          <div className="rounded-2xl border border-line bg-surface p-6 text-sm text-ink-2">Escolha a empresa para ver a agenda da equipe dela.</div>
        )}
        {areaEquipe === 'administracao' && operador && <>
          <DemandasAdministrativas empresaId={isComando ? alvo : undefined} soLeitura={isComando} onTotal={setTarefasPendentes} />
          <div><h2 className="text-base font-semibold text-ink">Atendimentos e reuniões aguardando aprovação</h2><p className="mt-1 text-sm text-ink-2">Confira a data e o horário solicitados pelo agente, escolha quem atende e aprove a reunião.</p></div>
        </>}

        {!naLista && dados && dados.ativo === false && (
          <div className="rounded-2xl border border-line bg-surface p-6 text-sm text-ink-2">{dados.mensagem}</div>
        )}

        {carregando && !dados && !naLista && (
          <div className="flex items-center gap-2 py-10 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> Carregando a agenda…</div>
        )}

        {!naLista && dados?.ativo && resolvidos && (
          total === 0
            ? <div className="rounded-2xl border border-line bg-surface px-6 py-10 text-center text-sm text-ink-2">Nada foi resolvido hoje ainda.</div>
            : <ul className="space-y-2.5">
                {dados.itens.map(i => (
                  <ItemResolvido key={i.id} item={i} mostrarOperador={false} podeDesfazer={!isComando} onDesfazer={desfazerResolvido} />
                ))}
              </ul>
        )}

        {!naLista && dados?.ativo && !resolvidos && total === 0 && (
          <div className="rounded-2xl border border-line bg-surface px-6 py-12 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-ink-2 opacity-50" />
            <p className="mt-3 text-sm font-medium text-ink">Nada pendente</p>
            <p className="mt-1 text-xs text-ink-2">
              Ao registrar um contato na ficha do devedor, marque a data prometida ou o retorno: ele aparece aqui.
            </p>
          </div>
        )}

        {!naLista && dados?.ativo && !resolvidos && total > 0 && atual && (
          <div className="grid items-start gap-5 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
            <FilaAgenda grupos={grupos} selecionado={atual.id} onSelecionar={setSelecionado} />
            <Atendimento key={atual.id} item={atual} onAcao={acao} onAbrir={abrir} soLeitura={isComando} meuId={usuario?.id}
              operadores={listaOperadores} onAtribuir={areaEquipe === 'administracao' && isAdmin ? atribuirAtendimento : undefined} />
          </div>
        )}
      </div>
      <AvisoDesfazer aviso={desfazer} onFechar={() => setDesfazer(null)} />
    </AppShell>
  )
}
