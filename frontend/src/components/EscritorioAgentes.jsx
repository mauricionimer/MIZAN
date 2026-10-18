// Escritório dos agentes: a Central em pixel art isométrica (estilo "estação de
// agentes"). Cada agente tem mesa e boneco; o envelope anda na ordem real dos
// passos. Desenho próprio, em SVG: nada de arte de terceiros.
// Mostra só o que já está gravado nos passos (nunca o texto do devedor).
import { useEffect, useMemo, useRef, useState } from 'react'
import { Play, Maximize2, Radio, Square } from 'lucide-react'
import { agenteEstacao } from '../api'

const TW = 64, TH = 32, I = 11, J = 8, OX = 24 + J * TW / 2, OY = 112, PAREDE = 92
const iso = (i, j) => [OX + (i - j) * TW / 2, OY + (i + j) * TH / 2]
const sobe = ([x, y], h) => [x, y - h]
const pts = l => l.map(([x, y]) => `${x},${y}`).join(' ')
const ATIVO_MS = 30000

// Onde fica cada um (coordenadas do piso). Mesa: i, j, largura, fundo.
const MESAS = {
  Estrategista: { i: 1.2, j: 1.0, ia: 'estrategista', pele: '#e8b48a', cabelo: '#3b2414' },
  Triagem: { i: 3.6, j: 1.0, ia: 'triagem', pele: '#c98e62', cabelo: '#111827' },
  Negociador: { i: 6.0, j: 1.0, ia: 'negociador', pele: '#f1c9a5', cabelo: '#a16207' },
  Acompanhamento: { i: 1.2, j: 4.2, ia: 'acompanhamento', pele: '#8d5a3b', cabelo: '#111827' },
  Supervisor: { i: 3.6, j: 4.2, ia: 'supervisor', pele: '#f1c9a5', cabelo: '#6b7280' },
  Cientista: { i: 6.0, j: 4.2, ia: 'cientista', pele: '#c98e62', cabelo: '#7c2d12' },
  Auditor: { i: 9.0, j: 2.0, w: 1.3, d: 1.2, balcao: true, pele: '#e8b48a', cabelo: '#1f2937' },
  Orquestrador: { i: 3.4, j: 6.7, w: 2.4, d: 0.9, balcao: true, pele: '#8d5a3b', cabelo: '#374151' },
}
const W = 1.6, D = 0.9, ALTURA_MESA = 15
const PORTA = { a: 7.75, b: 8.65 }
const CATRACA = { i: 9.3, j: 4.6 }
const ARQUIVO = { i: 9.5, j: 6.3 }

function lugar(nome) {
  const m = MESAS[nome]
  if (m) return iso(m.i + (m.w || W) * 0.62, m.j - 0.3)
  if (nome === 'Travas') return iso(CATRACA.i + 0.3, CATRACA.j + 0.3)
  if (nome === 'Ferramenta') return iso(ARQUIVO.i + 0.3, ARQUIVO.j + 0.2)
  if (nome === 'Equipe') return iso((PORTA.a + PORTA.b) / 2, 0.15)
  return lugar('Orquestrador')
}

function paraEquipe(p) {
  return p && (p.quem === 'Equipe' || ['transferir', 'avisar_equipe'].includes(p.no)
    || p.no === 'ferramenta:transferir_para_humano' || p.no === 'ferramenta:marcar_atendimento_humano')
}

function Caixa({ i, j, w, d, h, z = 0, topo, esq, dir, extra }) {
  const a = sobe(iso(i, j), z), b = sobe(iso(i + w, j), z), c = sobe(iso(i + w, j + d), z), e = sobe(iso(i, j + d), z)
  return (
    <g {...extra}>
      <polygon points={pts([sobe(e, h), sobe(c, h), c, e])} fill={esq} />
      <polygon points={pts([sobe(c, h), sobe(b, h), b, c])} fill={dir} />
      <polygon points={pts([sobe(a, h), sobe(b, h), sobe(c, h), sobe(e, h)])} fill={topo} />
    </g>
  )
}

// Boneco de pixels. Origem nos pés. Agente com IA tem antena acesa na cor dele.
function Boneco({ x, y, cor, pele, cabelo, trabalhando, dormindo, ia }) {
  const p = 3
  const r = (cx, cy, w, h, f) => <rect x={cx * p} y={cy * p} width={w * p} height={h * p} fill={f} />
  return (
    <g transform={`translate(${Math.round(x)},${Math.round(y)})`}>
      <ellipse cx="0" cy="0" rx="11" ry="4" fill="#000" opacity="0.25" />
      <g className={trabalhando ? 'esc-digita' : ''}>
        {ia && <>{r(0, -20, 1, 2, '#9ca3af')}{r(0, -21, 1, 1, cor)}</>}
        {r(-2, -18, 4, 1, cabelo)}{r(-3, -17, 1, 2, cabelo)}{r(2, -17, 1, 2, cabelo)}
        {r(-2, -17, 4, 4, pele)}
        {dormindo ? <>{r(-1, -15, 1, 0.34, '#111')}{r(1, -15, 1, 0.34, '#111')}</>
          : <>{r(-1, -16, 1, 1, '#111')}{r(1, -16, 1, 1, '#111')}</>}
        {r(-3, -13, 6, 6, cor)}{r(-3, -13, 6, 1, '#ffffff33')}
        {r(-4, -12, 1, 4, cor)}{r(3, -12, 1, 4, cor)}
        {r(-4, -8, 1, 1, pele)}{r(3, -8, 1, 1, pele)}
        {r(-2, -7, 2, 6, '#1e2340')}{r(0, -7, 2, 6, '#262c52')}
      </g>
    </g>
  )
}

function Balao({ x, y, texto, cor }) {
  const t = texto.length > 42 ? texto.slice(0, 41) + '…' : texto
  const w = Math.round(t.length * 5.6 + 16), h = 20
  const bx = Math.max(4, Math.min(676 - w, x - w / 2)), by = y - h
  return (
    <g className="esc-balao">
      <rect x={bx} y={by} width={w} height={h} fill="#f8fafc" stroke="#0b1020" strokeWidth="2" />
      <rect x={bx} y={by + h - 3} width={w} height="3" fill={cor} />
      <polygon points={pts([[x - 4, by + h], [x + 4, by + h], [x, by + h + 6]])} fill="#f8fafc" stroke="#0b1020" strokeWidth="2" />
      <text x={bx + 8} y={by + 13} fontSize="10" fontFamily="ui-monospace, monospace" fill="#0b1020">{t}</text>
    </g>
  )
}

function Plaquinha({ x, y, nome, cor }) {
  const w = Math.round(nome.length * 6 + 10)
  return (
    <g>
      <rect x={x - w / 2} y={y} width={w} height="13" fill="#0b1020" stroke={cor} strokeWidth="1.5" />
      <text x={x} y={y + 9.5} fontSize="9" fontWeight="700" textAnchor="middle" fontFamily="ui-monospace, monospace" fill={cor}>{nome}</text>
    </g>
  )
}

function Sala({ cores, ia, foco, ativos, sel, onSel, ligado }) {
  const quemFoco = foco?.quem
  const bloqueio = foco && foco.quem === 'Auditor' && foco.resultado === 'bloqueado'
  const travou = foco && foco.quem === 'Travas' && foco.resultado === 'bloqueado'
  const equipe = paraEquipe(foco)
  const env = foco ? (equipe ? lugar('Equipe') : lugar(quemFoco)) : null

  const piso = []
  for (let i = 0; i < I; i++) for (let j = 0; j < J; j++) {
    piso.push(<polygon key={`${i}-${j}`} points={pts([iso(i, j), iso(i + 1, j), iso(i + 1, j + 1), iso(i, j + 1)])}
      fill={(i + j) % 2 ? '#1c2452' : '#202a5c'} stroke="#2a3672" strokeWidth="0.6" />)
  }

  function mesa(nome) {
    const m = MESAS[nome], w = m.w || W, d = m.d || D, cor = cores[nome] || '#94a3b8'
    const desligada = m.ia && ia && ia[m.ia] === false
    const trab = ativos.has(nome) || quemFoco === nome
    const [bx, by] = lugar(nome)
    return (
      <g key={nome} onClick={() => onSel(sel === nome ? null : nome)} style={{ cursor: 'pointer' }}
        opacity={desligada || !ligado ? 0.45 : 1}>
        <Boneco x={bx} y={by} cor={cor} pele={m.pele} cabelo={m.cabelo} ia={!!m.ia && !desligada}
          trabalhando={trab && !desligada} dormindo={!trab} />
        {!trab && <text x={bx + 12} y={by - 50} className="esc-zz" fontSize="10" fontWeight="700" fill="#94a3b8" fontFamily="ui-monospace, monospace">z z</text>}
        <Caixa i={m.i} j={m.j} w={w} d={d} h={ALTURA_MESA}
          topo={m.balcao ? '#5b6bbf' : '#c08a4e'} esq={m.balcao ? '#3c4890' : '#8f5f2f'} dir={m.balcao ? '#323d7c' : '#7a4f26'} />
        {!m.balcao && <Caixa i={m.i + 0.18} j={m.j + 0.08} w={0.5} d={0.14} h={17} z={ALTURA_MESA}
          topo="#374151" esq={trab && !desligada ? cor : '#0b1020'} dir="#1f2937" />}
        {sel === nome && <polygon points={pts([iso(m.i - 0.1, m.j - 0.6), iso(m.i + w + 0.1, m.j - 0.6), iso(m.i + w + 0.1, m.j + d + 0.1), iso(m.i - 0.1, m.j + d + 0.1)])}
          fill="none" stroke="#f8fafc" strokeWidth="1.5" strokeDasharray="4 3" />}
      </g>
    )
  }

  const [px1, py1] = iso(PORTA.a, 0), [px2, py2] = iso(PORTA.b, 0)
  const [tx, ty] = iso(3.4, 0)
  return (
    <svg viewBox="0 0 680 440" className="w-full" style={{ imageRendering: 'pixelated' }} shapeRendering="crispEdges"
      role="img" aria-label="Escritório dos agentes">
      <style>{`
        .esc-digita { animation: escDigita .45s steps(2) infinite; }
        .esc-zz { animation: escZz 2.4s steps(4) infinite; }
        .esc-balao { animation: escSurge .25s steps(3); }
        .esc-env { transition: transform .7s steps(7); }
        .esc-pisca { animation: escPisca .5s steps(2) infinite; }
        @keyframes escDigita { 50% { transform: translateY(-2px); } }
        @keyframes escZz { 0% { transform: translateY(0); opacity: .2 } 100% { transform: translateY(-8px); opacity: 1 } }
        @keyframes escSurge { from { transform: translateY(4px); opacity: 0 } }
        @keyframes escPisca { 50% { opacity: .35 } }
        @media (prefers-reduced-motion: reduce) { .esc-digita, .esc-zz, .esc-balao, .esc-pisca { animation: none } .esc-env { transition: none } }
      `}</style>
      {/* paredes */}
      <polygon points={pts([iso(0, J), iso(0, 0), sobe(iso(0, 0), PAREDE), sobe(iso(0, J), PAREDE)])} fill="#252f66" />
      <polygon points={pts([iso(0, 0), iso(I, 0), sobe(iso(I, 0), PAREDE), sobe(iso(0, 0), PAREDE)])} fill="#2c3878" />
      <polygon points={pts([sobe(iso(0, J), PAREDE), sobe(iso(0, 0), PAREDE), sobe(iso(0, 0), PAREDE + 6), sobe(iso(0, J), PAREDE + 6)])} fill="#4c5bb0" />
      <polygon points={pts([sobe(iso(0, 0), PAREDE), sobe(iso(I, 0), PAREDE), sobe(iso(I, 0), PAREDE + 6), sobe(iso(0, 0), PAREDE + 6)])} fill="#5a69c2" />
      {[1.2, 3.4, 5.6].map(j => (
        <polygon key={j} points={pts([sobe(iso(0, j), 30), sobe(iso(0, j + 1.4), 30), sobe(iso(0, j + 1.4), 70), sobe(iso(0, j), 70)])} fill="#7dd3fc" opacity="0.35" stroke="#93c5fd" strokeWidth="1" />
      ))}
      <text transform={`translate(${tx},${ty - 84}) skewY(26.565)`} fontSize="12" fontWeight="800" fill="#c7d2fe" fontFamily="ui-monospace, monospace">MIZAN · AGENTES</text>
      {/* porta da equipe */}
      <polygon points={pts([[px1, py1], [px2, py2], [px2, py2 - 64], [px1, py1 - 64]])} fill={equipe ? '#facc15' : '#6b4220'} stroke="#0b1020" strokeWidth="2"
        className={equipe ? 'esc-pisca' : ''} />
      <text transform={`translate(${px1 + 2},${py1 - 72}) skewY(26.565)`} fontSize="9" fontWeight="700" fill="#e5e7eb" fontFamily="ui-monospace, monospace">EQUIPE</text>
      {piso}
      {['Estrategista', 'Triagem', 'Negociador', 'Auditor'].map(mesa)}
      {['Acompanhamento', 'Supervisor', 'Cientista'].map(mesa)}
      {/* catraca = travas de saída */}
      <g onClick={() => onSel(sel === 'Travas' ? null : 'Travas')} style={{ cursor: 'pointer' }}>
        <Caixa i={CATRACA.i} j={CATRACA.j} w={0.25} d={0.8} h={26} topo="#9ca3af" esq="#6b7280" dir="#4b5563" />
        <Caixa i={CATRACA.i + 0.75} j={CATRACA.j} w={0.25} d={0.8} h={26} topo="#9ca3af" esq="#6b7280" dir="#4b5563" />
        <Caixa i={CATRACA.i + 0.05} j={CATRACA.j + 0.35} w={0.9} d={0.1} h={4} z={14}
          topo={travou ? '#ef4444' : quemFoco === 'Travas' ? '#22c55e' : cores.Travas || '#f472b6'} esq="#9d174d" dir="#831843" />
        <Plaquinha x={iso(CATRACA.i + 0.5, CATRACA.j + 0.8)[0]} y={iso(CATRACA.i + 0.5, CATRACA.j + 0.8)[1] + 4} nome="Travas" cor={cores.Travas || '#f472b6'} />
      </g>
      {/* arquivo = o que foi gravado de verdade */}
      <g onClick={() => onSel(sel === 'Ferramenta' ? null : 'Ferramenta')} style={{ cursor: 'pointer' }}>
        <Caixa i={ARQUIVO.i} j={ARQUIVO.j} w={0.7} d={0.6} h={34} topo="#6ee7b7" esq={quemFoco === 'Ferramenta' ? '#34d399' : '#059669'} dir="#047857" />
        <Plaquinha x={iso(ARQUIVO.i + 0.35, ARQUIVO.j + 0.6)[0]} y={iso(ARQUIVO.i + 0.35, ARQUIVO.j + 0.6)[1] + 4} nome="Ferramenta" cor={cores.Ferramenta || '#34d399'} />
      </g>
      {mesa('Orquestrador')}
      {/* placa do Auditor quando bloqueia */}
      {bloqueio && (() => {
        const [x, y] = lugar('Auditor')
        const regra = foco.regra || 'bloqueado'
        return (
          <g className="esc-pisca">
            <rect x={x - 4} y={y - 92} width="3" height="34" fill="#9ca3af" />
            <rect x={x - 34} y={y - 108} width="64" height="20" fill="#dc2626" stroke="#0b1020" strokeWidth="2" />
            <text x={x - 2} y={y - 94} fontSize="10" fontWeight="800" textAnchor="middle" fill="#fff" fontFamily="ui-monospace, monospace">{regra.split('_')[0]}</text>
          </g>
        )
      })()}
      {/* envelope */}
      {env && (
        <g className="esc-env" style={{ transform: `translate(${Math.round(env[0])}px, ${Math.round(env[1] - 66)}px)` }}>
          <rect x="-8" y="-6" width="16" height="11" fill="#fef3c7" stroke="#0b1020" strokeWidth="1.5" />
          <polyline points="-8,-6 0,1 8,-6" fill="none" stroke="#0b1020" strokeWidth="1.5" />
        </g>
      )}
      {Object.keys(MESAS).filter(n => !(foco?.explicacao && !equipe && n === quemFoco)).map(n => {
        const [x, y] = lugar(n)
        const off = (MESAS[n].ia && ia && ia[MESAS[n].ia] === false) || !ligado
        return (
          <g key={`pl-${n}`} onClick={() => onSel(sel === n ? null : n)} style={{ cursor: 'pointer' }} opacity={off ? 0.5 : 1}>
            <Plaquinha x={x} y={y - 78} nome={n} cor={cores[n] || '#94a3b8'} />
          </g>
        )
      })}
      {foco?.explicacao && <Balao x={lugar(equipe ? 'Equipe' : quemFoco)[0]} y={lugar(equipe ? 'Equipe' : quemFoco)[1] - (equipe ? 76 : 80)}
        texto={`${foco.quem}: ${foco.explicacao}`} cor={cores[foco.quem] || '#94a3b8'} />}
      {!ligado && <text x="340" y="30" textAnchor="middle" fontSize="12" fontWeight="700" fill="#fca5a5" fontFamily="ui-monospace, monospace">AGENTE DESLIGADO</text>}
    </svg>
  )
}

const hora = s => (s ? new Date(s).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')

export default function EscritorioAgentes({ empresa, cores }) {
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [sel, setSel] = useState(null)
  const [replay, setReplay] = useState(null)        // índice do passo da última conversa
  const caixa = useRef(null)

  useEffect(() => {
    let vivo = true
    const carregar = () => agenteEstacao(empresa).then(r => { if (vivo) { setD(r); setErro(null) } }).catch(e => vivo && setErro(e))
    carregar()
    const t = setInterval(() => { if (!document.hidden) carregar() }, 5000)
    return () => { vivo = false; clearInterval(t) }
  }, [empresa])

  const conversa = d?.ultima_conversa || []
  useEffect(() => {
    if (replay === null) return undefined
    const t = setTimeout(() => setReplay(replay + 1 < conversa.length ? replay + 1 : null), replay + 1 < conversa.length ? 1200 : 2500)
    return () => clearTimeout(t)
  }, [replay, conversa.length])

  const { ativos, focoVivo, porQuem } = useMemo(() => {
    const agora = d ? Date.parse(d.agora) : 0
    const porQuem = {}
    const ativos = new Set()
    let focoVivo = null
    for (const p of d?.passos || []) {
      (porQuem[p.quem] ||= []).push(p)
      if (agora - Date.parse(p.criado_em) < ATIVO_MS) { ativos.add(p.quem); focoVivo = p }
    }
    return { ativos, focoVivo, porQuem }
  }, [d])

  const foco = replay !== null ? conversa[replay] : focoVivo
  const lista = sel ? (porQuem[sel] || []).slice(-5).reverse() : (d?.passos || []).slice(-8).reverse()

  return (
    <section ref={caixa} className="rounded-xl border border-line bg-surface p-4" style={{ background: 'var(--surface, #0f1535)' }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><Radio className="h-4 w-4 text-emerald-400" /> Escritório dos agentes</h2>
          <p className="mt-0.5 text-xs text-ink-2">
            {replay !== null ? `Reproduzindo a última conversa: passo ${replay + 1} de ${conversa.length}.`
              : `Ao vivo: o que cada agente fez nos últimos ${d?.janela_min || 15} minutos (atualiza a cada 5 s). Clique num agente para ver os passos dele.`}
          </p>
        </div>
        <div className="flex gap-2">
          {replay === null
            ? <button onClick={() => { setSel(null); setReplay(0) }} disabled={!conversa.length}
                className="flex items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/15 px-3 py-1.5 text-sm font-medium text-blue-300 disabled:opacity-40">
                <Play className="h-4 w-4" /> Reproduzir última conversa</button>
            : <button onClick={() => setReplay(null)} className="flex items-center gap-1.5 rounded-md border border-line bg-raise-1 px-3 py-1.5 text-sm font-medium text-ink-2">
                <Square className="h-4 w-4" /> Parar</button>}
          <button onClick={() => (document.fullscreenElement ? document.exitFullscreen() : caixa.current?.requestFullscreen?.())}
            className="flex items-center gap-1.5 rounded-md border border-line bg-raise-1 px-3 py-1.5 text-sm font-medium text-ink-2" title="Tela cheia">
            <Maximize2 className="h-4 w-4" /> Tela cheia</button>
        </div>
      </div>
      {erro && !d && <p className="mt-3 text-xs text-red-300">Não foi possível carregar o escritório.</p>}
      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="overflow-hidden rounded-lg border border-line" style={{ background: '#0b1029' }}>
          <Sala cores={cores} ia={d?.ia} foco={foco} ativos={replay !== null ? new Set() : ativos} sel={sel} onSel={setSel} ligado={d ? d.ligado : true} />
        </div>
        <div className="rounded-lg border border-line bg-raise-1 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">
            {replay !== null ? 'Última conversa' : sel ? `Últimos passos: ${sel}` : 'Agora'}</p>
          <ol className="mt-2 space-y-1.5" aria-live="polite">
            {(replay !== null ? conversa : lista).map((p, k) => (
              <li key={`${p.trace_id}-${p.criado_em}-${k}`}
                className={`text-xs ${replay !== null && k === replay ? 'rounded bg-blue-500/15 px-1 text-ink' : replay !== null && k > replay ? 'text-ink-3 opacity-50' : 'text-ink-2'}`}>
                <span className="font-semibold" style={{ color: cores[p.quem] || '#94a3b8' }}>{p.quem}</span> {p.explicacao}
                {p.resultado === 'bloqueado' && <span className="ml-1 text-red-300">· bloqueado{p.regra ? ` (${p.regra})` : ''}</span>}
                {replay === null && <span className="ml-1 text-ink-3">· {hora(p.criado_em)}</span>}
              </li>
            ))}
            {!(replay !== null ? conversa : lista).length && <li className="text-xs text-ink-3">{sel ? 'Nada deste agente nos últimos minutos.' : 'Ninguém trabalhando agora. Use "Reproduzir última conversa".'}</li>}
          </ol>
          <p className="mt-3 border-t border-line pt-2 text-[11px] text-ink-3">Antena acesa = agente com IA. Mesa apagada = IA desligada (o agente segue em código). Placa vermelha = o Auditor bloqueou. Porta amarela = caso indo para a equipe.</p>
        </div>
      </div>
    </section>
  )
}
