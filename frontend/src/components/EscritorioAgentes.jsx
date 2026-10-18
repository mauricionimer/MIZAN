// Escritório dos agentes: sala isométrica em pixel art com baias de vidro por
// time. Desenho próprio, em SVG. Mostra só o que está gravado nos passos
// (nunca o texto do devedor).
import { useEffect, useMemo, useRef, useState } from 'react'
import { Play, Maximize2, Radio, Square, ArrowRight } from 'lucide-react'
import { agenteEstacao } from '../api'

const I = 14, J = 10, OX = 40 + J * 28, OY = 160, PAREDE = 118
const iso = (i, j) => [OX + (i - j) * 28, OY + (i + j) * 14]
const sobe = ([x, y], h) => [x, y - h]
const pts = l => l.map(([x, y]) => `${x},${y}`).join(' ')
const ATIVO_MS = 30000
const FONTE = 'ui-monospace, SFMono-Regular, Menlo, monospace'

export const TIMES = {
  atendimento: { nome: 'Atendimento', cor: '#3b82f6', i0: 0.4, i1: 6.6, j0: 0.4, j1: 3.8 },
  estrategia: { nome: 'Estratégia', cor: '#06b6d4', i0: 7.4, i1: 13.6, j0: 0.4, j1: 3.8 },
  acompanhamento: { nome: 'Acompanhamento', cor: '#f97316', i0: 0.4, i1: 4.8, j0: 5.4, j1: 9.6 },
  controle: { nome: 'Controle', cor: '#f59e0b', i0: 9.2, i1: 13.6, j0: 5.4, j1: 9.6 },
  recepcao: { nome: 'Recepção' },
}

// Mesa (i, j, largura, fundo), time, papel de IA e o visual do boneco.
export const MESAS = {
  Triagem: { i: 1.0, j: 1.4, time: 'atendimento', ia: 'triagem', pele: '#c98e62', cabelo: '#111827', acc: 'headset' },
  Negociador: { i: 3.0, j: 1.4, time: 'atendimento', ia: 'negociador', pele: '#f1c9a5', cabelo: '#a16207', acc: 'gravata' },
  Supervisor: { i: 5.0, j: 1.4, time: 'atendimento', ia: 'supervisor', pele: '#e8b48a', cabelo: '#9ca3af', acc: 'oculos' },
  Estrategista: { i: 8.4, j: 1.4, time: 'estrategia', ia: 'estrategista', pele: '#8d5a3b', cabelo: '#111827', acc: null },
  Cientista: { i: 11.0, j: 1.4, time: 'estrategia', ia: 'cientista', pele: '#f1c9a5', cabelo: '#7c2d12', acc: 'jaleco' },
  Acompanhamento: { i: 1.6, j: 6.6, time: 'acompanhamento', ia: 'acompanhamento', pele: '#8d5a3b', cabelo: '#3b2414', acc: null },
  Orquestrador: { i: 5.8, j: 7.4, w: 2.4, d: 0.9, balcao: true, time: 'recepcao', pele: '#c98e62', cabelo: '#374151', acc: 'headset' },
  Auditor: { i: 10.0, j: 6.6, w: 1.6, d: 1.0, balcao: true, time: 'controle', pele: '#e8b48a', cabelo: '#1f2937', acc: 'bone' },
}
const W = 1.5, D = 0.85, ALTURA_MESA = 14
const CATRACA = { i: 12.0, j: 8.2 }
const ARQUIVO = { i: 12.7, j: 5.8 }
const PORTA = { a: 4.15, b: 5.05 }               // na parede da esquerda (corredor do meio)

function lugar(nome) {
  const m = MESAS[nome]
  if (m) return iso(m.i + (m.w || W) * 0.6, m.j - 0.35)
  if (nome === 'Travas') return iso(CATRACA.i + 0.4, CATRACA.j + 0.2)
  if (nome === 'Ferramenta') return iso(ARQUIVO.i + 0.3, ARQUIVO.j + 0.3)
  if (nome === 'Equipe') return iso(0.5, (PORTA.a + PORTA.b) / 2)
  return lugar('Orquestrador')
}

function paraEquipe(p) {
  return p && (p.quem === 'Equipe' || ['transferir', 'avisar_equipe'].includes(p.no)
    || p.no === 'ferramenta:transferir_para_humano' || p.no === 'ferramenta:marcar_atendimento_humano')
}

function Caixa({ i, j, w, d, h, z = 0, topo, esq, dir, borda }) {
  const a = sobe(iso(i, j), z), b = sobe(iso(i + w, j), z), c = sobe(iso(i + w, j + d), z), e = sobe(iso(i, j + d), z)
  const s = borda ? { stroke: borda, strokeWidth: 1 } : {}
  return (
    <g>
      <polygon points={pts([sobe(e, h), sobe(c, h), c, e])} fill={esq} {...s} />
      <polygon points={pts([sobe(c, h), sobe(b, h), b, c])} fill={dir} {...s} />
      <polygon points={pts([sobe(a, h), sobe(b, h), sobe(c, h), sobe(e, h)])} fill={topo} {...s} />
    </g>
  )
}

// Parede de vidro entre dois pontos do piso, com montantes a cada metro.
function Vidro({ de, ate, h = 38 }) {
  const a = iso(...de), b = iso(...ate)
  const n = Math.max(1, Math.round(Math.hypot(ate[0] - de[0], ate[1] - de[1])))
  const mont = []
  for (let k = 0; k <= n; k++) {
    const x = a[0] + (b[0] - a[0]) * k / n, y = a[1] + (b[1] - a[1]) * k / n
    mont.push(<line key={k} x1={x} y1={y} x2={x} y2={y - h} stroke="#94a3b8" strokeWidth="1.5" />)
  }
  return (
    <g>
      <polygon points={pts([a, b, sobe(b, h), sobe(a, h)])} fill="#bae6fd" opacity="0.38" />
      <line x1={a[0]} y1={a[1] - h} x2={b[0]} y2={b[1] - h} stroke="#64748b" strokeWidth="2.5" />
      <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#94a3b8" strokeWidth="2" />
      {mont}
    </g>
  )
}

function Planta({ i, j }) {
  const [x, y] = iso(i + 0.25, j + 0.25)
  return (
    <g>
      <Caixa i={i} j={j} w={0.5} d={0.5} h={10} topo="#a16207" esq="#92400e" dir="#78350f" />
      {[[-9, -24, 10], [0, -30, 10], [4, -22, 9], [-4, -36, 8], [-12, -16, 8], [6, -14, 7]].map(([dx, dy, s], k) => (
        <rect key={k} x={x + dx} y={y + dy} width={s} height={s} fill={k % 2 ? '#16a34a' : '#22c55e'} />
      ))}
    </g>
  )
}

// Boneco de pixels (origem nos pés). Antena acesa = agente com IA.
function Boneco({ x, y, cor, pele, cabelo, acc, trabalhando, dormindo, ia }) {
  const p = 3
  const r = (cx, cy, w, h, f) => <rect x={cx * p} y={cy * p} width={w * p} height={h * p} fill={f} />
  const camisa = acc === 'jaleco' ? '#f8fafc' : cor
  return (
    <g transform={`translate(${Math.round(x)},${Math.round(y)})`}>
      <ellipse cx="0" cy="0" rx="12" ry="4" fill="#0f172a" opacity="0.18" />
      <g className={trabalhando ? 'esc-digita' : ''}>
        {r(-2, -6, 2, 5, '#1e293b')}{r(0, -6, 2, 5, '#334155')}
        {r(-2, -1, 2, 1, '#0f172a')}{r(0, -1, 2, 1, '#0f172a')}
        {r(-3, -13, 6, 7, camisa)}{r(-3, -13, 6, 1, '#ffffff40')}
        {acc === 'jaleco' && r(-1, -13, 2, 7, cor)}
        {acc === 'gravata' && <>{r(-1, -13, 2, 1, '#f8fafc')}{r(0, -12, 1, 4, '#991b1b')}</>}
        {r(-4, -12, 1, 5, camisa)}{r(3, -12, 1, 5, camisa)}
        {r(-4, -7, 1, 1, pele)}{r(3, -7, 1, 1, pele)}
        {r(-1, -14, 2, 1, pele)}
        {r(-2, -18, 4, 4, pele)}
        {r(-2, -19, 4, 1, cabelo)}{r(-3, -18, 1, 2, cabelo)}{r(2, -18, 1, 2, cabelo)}
        {dormindo
          ? <>{r(-1, -16, 1, 0.34, '#111827')}{r(1, -16, 1, 0.34, '#111827')}</>
          : <>{r(-1, -16, 1, 1, '#111827')}{r(1, -16, 1, 1, '#111827')}</>}
        {acc === 'oculos' && <>{r(-2, -16.3, 4, 0.5, '#0f172a')}{r(-1.6, -16.6, 1.3, 1.2, '#93c5fd80')}{r(0.4, -16.6, 1.3, 1.2, '#93c5fd80')}</>}
        {acc === 'headset' && <>{r(-3, -19, 1, 4, '#374151')}{r(-3, -15, 2, 1, '#374151')}{r(-2, -20, 4, 1, '#374151')}</>}
        {acc === 'bone' && <>{r(-2, -20, 4, 1, '#b45309')}{r(-2, -19, 5, 1, '#b45309')}</>}
        {ia && <>{r(0, -21, 1, 2, '#94a3b8')}<g className="esc-pisca-lento">{r(-0.5, -22.5, 2, 1.5, cor)}</g></>}
      </g>
    </g>
  )
}

// Retrato do agente (o mesmo boneco da sala), para cartões e perfil.
export function Retrato({ nome, cor, tamanho = 64 }) {
  const m = MESAS[nome] || { pele: '#e8b48a', cabelo: '#374151' }
  return (
    <svg viewBox="-22 -72 44 76" width={tamanho} height={tamanho * 76 / 44} shapeRendering="crispEdges" aria-hidden="true">
      <Boneco x={0} y={0} cor={cor} pele={m.pele} cabelo={m.cabelo} acc={m.acc} ia={!!m.ia} />
    </svg>
  )
}

function Balao({ x, y, texto, cor }) {
  const t = texto.length > 46 ? texto.slice(0, 45) + '…' : texto
  const w = Math.round(t.length * 5.7 + 16), h = 21
  const bx = Math.max(4, Math.min(756 - w, x - w / 2)), by = y - h
  return (
    <g className="esc-balao">
      <rect x={bx + 2} y={by + 2} width={w} height={h} fill="#0f172a" opacity="0.25" />
      <rect x={bx} y={by} width={w} height={h} fill="#ffffff" stroke="#0f172a" strokeWidth="2" />
      <rect x={bx} y={by} width="4" height={h} fill={cor} />
      <polygon points={pts([[x - 5, by + h], [x + 5, by + h], [x, by + h + 7]])} fill="#ffffff" stroke="#0f172a" strokeWidth="2" />
      <rect x={x - 4} y={by + h - 2} width="8" height="3" fill="#ffffff" />
      <text x={bx + 10} y={by + 14} fontSize="10.5" fontFamily={FONTE} fill="#0f172a">{t}</text>
    </g>
  )
}

function Plaquinha({ x, y, nome, cor, apagada }) {
  const w = Math.round(nome.length * 6.2 + 14)
  return (
    <g opacity={apagada ? 0.55 : 1}>
      <rect x={x - w / 2 + 1.5} y={y + 1.5} width={w} height="15" fill="#0f172a" opacity="0.25" />
      <rect x={x - w / 2} y={y} width={w} height="15" fill="#ffffff" stroke={cor} strokeWidth="2" />
      <rect x={x - w / 2} y={y} width="4" height="15" fill={cor} />
      <text x={x + 2} y={y + 11} fontSize="9.5" fontWeight="700" textAnchor="middle" fontFamily={FONTE} fill="#0f172a">{nome}</text>
    </g>
  )
}

// Letreiro da parede: o nome da empresa contratante, do tamanho que couber.
function Letreiro({ empresa }) {
  const nome = (empresa || 'Mizan').toUpperCase()
  const fs = Math.max(13, Math.min(30, 250 / (0.62 * nome.length)))
  const [x, y] = iso(7, 0)
  return (
    <g>
      <polygon points={pts([sobe(iso(2, 0), 62), sobe(iso(12, 0), 62), sobe(iso(12, 0), 112), sobe(iso(2, 0), 112)])}
        fill="#0f172a" stroke="#1e293b" strokeWidth="3" />
      <polygon points={pts([sobe(iso(2, 0), 62), sobe(iso(12, 0), 62), sobe(iso(12, 0), 66), sobe(iso(2, 0), 66)])} fill="#6b77e3" />
      <text transform={`translate(${x},${y - 84 + fs / 3}) skewY(26.565)`} textAnchor="middle" fontSize={fs} fontWeight="800"
        fontFamily={FONTE} fill="#f8fafc" letterSpacing="1">{nome}</text>
      <text transform={`translate(${x},${y - 101}) skewY(26.565)`} textAnchor="middle" fontSize="8.5" fontWeight="700"
        fontFamily={FONTE} fill="#a5b4fc" letterSpacing="2">CENTRAL DE AGENTES</text>
    </g>
  )
}

function NomeDoTime({ t }) {
  const [x, y] = iso(t.i0 + 0.35, t.j1 - 0.3)
  return (
    <text transform={`matrix(0.894,0.447,-0.894,0.447,${x},${y})`} fontSize="12" fontWeight="800" fontFamily={FONTE}
      fill={t.cor} opacity="0.85" letterSpacing="1.5">{t.nome.toUpperCase()}</text>
  )
}

function Sala({ cores, ia, foco, ativos, sel, onSel, ligado, empresa }) {
  const quemFoco = foco?.quem
  const bloqueio = foco && foco.quem === 'Auditor' && foco.resultado === 'bloqueado'
  const travou = foco && foco.quem === 'Travas' && foco.resultado === 'bloqueado'
  const equipe = paraEquipe(foco)
  const env = foco ? (equipe ? lugar('Equipe') : lugar(quemFoco)) : null
  const apagado = n => !ligado || !!(MESAS[n]?.ia && ia && ia[MESAS[n].ia] === false)

  const piso = []
  for (let i = 0; i < I; i++) for (let j = 0; j < J; j++) {
    piso.push(<polygon key={`${i}-${j}`} points={pts([iso(i, j), iso(i + 1, j), iso(i + 1, j + 1), iso(i, j + 1)])}
      fill={(i + j) % 2 ? '#eef1f6' : '#e5e9f1'} stroke="#d6dce7" strokeWidth="0.6" />)
  }

  function mesa(nome) {
    const m = MESAS[nome], w = m.w || W, d = m.d || D, cor = cores[nome] || '#94a3b8'
    const off = apagado(nome)
    const trab = !off && (ativos.has(nome) || quemFoco === nome)
    const [bx, by] = lugar(nome)
    return (
      <g key={nome} onClick={() => onSel(sel === nome ? null : nome)} style={{ cursor: 'pointer' }} opacity={off ? 0.6 : 1}>
        {sel === nome && <ellipse cx={bx} cy={by} rx="20" ry="8" fill="none" stroke={cor} strokeWidth="2.5" strokeDasharray="4 3" />}
        <Boneco x={bx} y={by} cor={cor} pele={m.pele} cabelo={m.cabelo} acc={m.acc} ia={!!m.ia && !off}
          trabalhando={trab} dormindo={!trab} />
        {!trab && <text x={bx + 12} y={by - 50} className="esc-zz" fontSize="10" fontWeight="700" fill="#64748b" fontFamily={FONTE}>z z</text>}
        <Caixa i={m.i} j={m.j} w={w} d={d} h={ALTURA_MESA}
          topo={m.balcao ? '#e2e8f0' : '#ffffff'} esq={m.balcao ? '#94a3b8' : '#cbd5e1'} dir={m.balcao ? '#64748b' : '#94a3b8'} borda="#94a3b833" />
        {m.balcao && <Caixa i={m.i} j={m.j + d - 0.08} w={w} d={0.08} h={3} z={ALTURA_MESA} topo={cor} esq={cor} dir={cor} />}
        {!m.balcao && <Caixa i={m.i + 0.15} j={m.j + 0.08} w={0.55} d={0.14} h={16} z={ALTURA_MESA}
          topo="#334155" esq={trab ? cor : '#1e293b'} dir="#0f172a" />}
      </g>
    )
  }

  const t = TIMES
  const [pa1, pa2] = [iso(0, PORTA.a), iso(0, PORTA.b)]
  return (
    <svg viewBox="28 26 704 478" className="w-full" shapeRendering="crispEdges" role="img" aria-label="Escritório dos agentes">
      <style>{`
        .esc-digita { animation: escDigita .45s steps(2) infinite; }
        .esc-zz { animation: escZz 2.4s steps(4) infinite; }
        .esc-balao { animation: escSurge .25s steps(3); }
        .esc-env { transition: transform .7s steps(7); }
        .esc-pisca { animation: escPisca .5s steps(2) infinite; }
        .esc-pisca-lento { animation: escPisca 1.6s steps(2) infinite; }
        @keyframes escDigita { 50% { transform: translateY(-2px); } }
        @keyframes escZz { 0% { transform: translateY(0); opacity: .2 } 100% { transform: translateY(-8px); opacity: 1 } }
        @keyframes escSurge { from { transform: translateY(4px); opacity: 0 } }
        @keyframes escPisca { 50% { opacity: .35 } }
        @media (prefers-reduced-motion: reduce) { .esc-digita, .esc-zz, .esc-balao, .esc-pisca, .esc-pisca-lento { animation: none } .esc-env { transition: none } }
      `}</style>
      {/* paredes */}
      <polygon points={pts([iso(0, J), iso(0, 0), sobe(iso(0, 0), PAREDE), sobe(iso(0, J), PAREDE)])} fill="#f1f5f9" />
      <polygon points={pts([iso(0, 0), iso(I, 0), sobe(iso(I, 0), PAREDE), sobe(iso(0, 0), PAREDE)])} fill="#e2e8f0" />
      <polygon points={pts([sobe(iso(0, J), PAREDE), sobe(iso(0, 0), PAREDE), sobe(iso(0, 0), PAREDE + 8), sobe(iso(0, J), PAREDE + 8)])} fill="#94a3b8" />
      <polygon points={pts([sobe(iso(0, 0), PAREDE), sobe(iso(I, 0), PAREDE), sobe(iso(I, 0), PAREDE + 8), sobe(iso(0, 0), PAREDE + 8)])} fill="#cbd5e1" />
      <polygon points={pts([iso(0, J), iso(0, 0), sobe(iso(0, 0), 6), sobe(iso(0, J), 6)])} fill="#cbd5e1" />
      <polygon points={pts([iso(0, 0), iso(I, 0), sobe(iso(I, 0), 6), sobe(iso(0, 0), 6)])} fill="#94a3b8" />
      {[[1.0, 3.2], [6.0, 8.6]].map(([a, b]) => (
        <polygon key={a} points={pts([sobe(iso(0, a), 40), sobe(iso(0, b), 40), sobe(iso(0, b), 96), sobe(iso(0, a), 96)])}
          fill="#bae6fd" stroke="#94a3b8" strokeWidth="3" />
      ))}
      <Letreiro empresa={empresa} />
      {/* porta da equipe (parede da esquerda) */}
      <polygon points={pts([pa1, pa2, sobe(pa2, 70), sobe(pa1, 70)])} fill={equipe ? '#facc15' : '#64748b'} stroke="#334155" strokeWidth="2.5"
        className={equipe ? 'esc-pisca' : ''} />
      <text transform={`translate(${(pa1[0] + pa2[0]) / 2},${(pa1[1] + pa2[1]) / 2 - 76}) skewY(-26.565)`} textAnchor="middle"
        fontSize="9" fontWeight="800" fill="#334155" fontFamily={FONTE}>EQUIPE</text>
      {piso}
      {['atendimento', 'estrategia', 'acompanhamento', 'controle'].map(k => (
        <polygon key={k} points={pts([iso(t[k].i0, t[k].j0), iso(t[k].i1, t[k].j0), iso(t[k].i1, t[k].j1), iso(t[k].i0, t[k].j1)])}
          fill={t[k].cor} opacity="0.09" />
      ))}
      {['atendimento', 'estrategia', 'acompanhamento', 'controle'].map(k => <NomeDoTime key={k} t={t[k]} />)}

      {/* Atendimento */}
      {['Triagem', 'Negociador', 'Supervisor'].map(mesa)}
      <Vidro de={[6.6, 0.4]} ate={[6.6, 3.8]} />
      <Vidro de={[0.4, 3.8]} ate={[2.6, 3.8]} /><Vidro de={[3.6, 3.8]} ate={[6.6, 3.8]} />
      {/* Estratégia */}
      <Vidro de={[7.4, 0.4]} ate={[7.4, 3.8]} />
      {['Estrategista', 'Cientista'].map(mesa)}
      <Vidro de={[7.4, 3.8]} ate={[10.0, 3.8]} /><Vidro de={[11.0, 3.8]} ate={[13.6, 3.8]} />
      <Planta i={13.2} j={4.3} />
      {/* Acompanhamento */}
      <Vidro de={[0.4, 5.4]} ate={[2.2, 5.4]} /><Vidro de={[3.0, 5.4]} ate={[4.8, 5.4]} />
      {mesa('Acompanhamento')}
      <Caixa i={0.5} j={8.6} w={1.0} d={0.5} h={22} topo="#fed7aa" esq="#fdba74" dir="#fb923c" />
      <Vidro de={[4.8, 5.4]} ate={[4.8, 9.6]} />
      {/* Recepção */}
      {mesa('Orquestrador')}
      {/* Controle */}
      <Vidro de={[9.2, 5.4]} ate={[10.8, 5.4]} /><Vidro de={[11.6, 5.4]} ate={[13.6, 5.4]} />
      <Vidro de={[9.2, 5.4]} ate={[9.2, 9.6]} />
      <g onClick={() => onSel(sel === 'Ferramenta' ? null : 'Ferramenta')} style={{ cursor: 'pointer' }}>
        <Caixa i={ARQUIVO.i} j={ARQUIVO.j} w={0.7} d={0.6} h={36} topo="#6ee7b7" esq={quemFoco === 'Ferramenta' ? '#34d399' : '#10b981'} dir="#059669" />
        {[10, 20, 30].map(h => {
          const [x1, y1] = sobe(iso(ARQUIVO.i, ARQUIVO.j + 0.6), h), [x2, y2] = sobe(iso(ARQUIVO.i + 0.7, ARQUIVO.j + 0.6), h)
          return <line key={h} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#047857" strokeWidth="1.5" />
        })}
      </g>
      {mesa('Auditor')}
      <g onClick={() => onSel(sel === 'Travas' ? null : 'Travas')} style={{ cursor: 'pointer' }}>
        <Caixa i={CATRACA.i} j={CATRACA.j} w={0.25} d={0.8} h={28} topo="#cbd5e1" esq="#94a3b8" dir="#64748b" />
        <Caixa i={CATRACA.i + 0.75} j={CATRACA.j} w={0.25} d={0.8} h={28} topo="#cbd5e1" esq="#94a3b8" dir="#64748b" />
        <Caixa i={CATRACA.i + 0.05} j={CATRACA.j + 0.35} w={0.9} d={0.1} h={4} z={16}
          topo={travou ? '#ef4444' : quemFoco === 'Travas' ? '#22c55e' : cores.Travas || '#f472b6'} esq="#be185d" dir="#9d174d" />
      </g>
      <Planta i={8.3} j={9.1} />
      <Planta i={0.6} j={4.3} />

      {/* plaquinhas (somem quando o balão é do agente) */}
      {[...Object.keys(MESAS), 'Travas', 'Ferramenta'].filter(n => !(foco?.explicacao && !equipe && n === quemFoco)).map(n => {
        const [x, y] = lugar(n)
        const alto = MESAS[n] ? 82 : n === 'Ferramenta' ? 56 : 48
        return (
          <g key={`pl-${n}`} onClick={() => onSel(sel === n ? null : n)} style={{ cursor: 'pointer' }}>
            <Plaquinha x={x} y={y - alto} nome={n} cor={cores[n] || '#94a3b8'} apagada={apagado(n)} />
          </g>
        )
      })}
      {bloqueio && (() => {
        const [x, y] = lugar('Auditor')
        return (
          <g className="esc-pisca">
            <rect x={x + 14} y={y - 70} width="3" height="40" fill="#64748b" />
            <rect x={x - 4} y={y - 92} width="58" height="22" fill="#dc2626" stroke="#0f172a" strokeWidth="2" />
            <text x={x + 25} y={y - 77} fontSize="11" fontWeight="800" textAnchor="middle" fill="#fff" fontFamily={FONTE}>{(foco.regra || 'BLOQUEADO').split('_')[0]}</text>
          </g>
        )
      })()}
      {env && (
        <g className="esc-env" style={{ transform: `translate(${Math.round(env[0])}px, ${Math.round(env[1] - 70)}px)` }}>
          <rect x="-9" y="-6" width="18" height="12" fill="#fef3c7" stroke="#0f172a" strokeWidth="1.5" />
          <polyline points="-9,-6 0,1 9,-6" fill="none" stroke="#0f172a" strokeWidth="1.5" />
        </g>
      )}
      {foco?.explicacao && (() => {
        const [x, y] = lugar(equipe ? 'Equipe' : quemFoco)
        return <Balao x={x} y={y - (equipe ? 82 : 84)} texto={`${foco.quem}: ${foco.explicacao}`} cor={cores[foco.quem] || '#94a3b8'} />
      })()}
      {!ligado && (
        <g><rect x="270" y="16" width="220" height="24" fill="#7f1d1d" /><text x="380" y="32" textAnchor="middle" fontSize="11" fontWeight="800" fill="#fff" fontFamily={FONTE}>AGENTE DESLIGADO</text></g>
      )}
    </svg>
  )
}

const hora = s => (s ? new Date(s).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')
const NOME_TIME = n => TIMES[MESAS[n]?.time]?.nome || (n === 'Travas' || n === 'Ferramenta' ? 'Controle' : '')

function CartaoDoAgente({ nome, cor, resumo, passos, ia, trabalhando, onPerfil, onFechar }) {
  const papel = MESAS[nome]?.ia
  const estadoIa = papel ? (ia?.[papel] === false ? 'IA desligada (em código)' : 'IA ligada') : 'Código'
  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-base font-bold" style={{ color: cor }}>{nome}</p>
          <p className="text-[11px] text-ink-3">{NOME_TIME(nome)}</p>
        </div>
        <button onClick={onFechar} className="text-xs text-ink-3 hover:text-ink" aria-label="Fechar">✕</button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
        <span className={`rounded px-1.5 py-0.5 ${trabalhando ? 'bg-emerald-500/15 text-emerald-300' : 'bg-raise-2 text-ink-2'}`}>{trabalhando ? 'trabalhando' : 'parado'}</span>
        <span className="rounded bg-raise-2 px-1.5 py-0.5 text-ink-2">{estadoIa}</span>
      </div>
      {resumo && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[['ações 24 h', resumo.acoes], ['bloqueios', resumo.bloqueios], ['tempo', resumo.tempo_medio_ms != null ? `${(resumo.tempo_medio_ms / 1000).toFixed(1)} s` : '—']].map(([r, v]) => (
            <div key={r} className="rounded-md bg-raise-2 px-1 py-1.5"><p className="text-sm font-bold text-ink">{v}</p><p className="text-[10px] text-ink-3">{r}</p></div>
          ))}
        </div>
      )}
      <p className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-ink-3">Últimas ações</p>
      <ol className="mt-1 space-y-1">
        {passos.slice(-4).reverse().map((p, k) => (
          <li key={k} className="text-xs text-ink-2">{p.explicacao}{p.resultado === 'bloqueado' && <span className="text-red-300"> · {p.regra || 'bloqueado'}</span>}
            <span className="text-ink-3"> · {hora(p.criado_em)}</span></li>
        ))}
        {!passos.length && <li className="text-xs text-ink-3">Nada nos últimos minutos.</li>}
      </ol>
      {onPerfil && MESAS[nome] && (
        <button onClick={() => onPerfil(nome)} className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/15 px-3 py-1.5 text-sm font-medium text-blue-300">
          Abrir perfil <ArrowRight className="h-4 w-4" /></button>
      )}
    </div>
  )
}

export default function EscritorioAgentes({ empresa, cores, nomeEmpresa, resumos, onPerfil }) {
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  const [sel, setSel] = useState(null)
  const [replay, setReplay] = useState(null)
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
    const fim = replay + 1 >= conversa.length
    const t = setTimeout(() => setReplay(fim ? null : replay + 1), fim ? 2500 : 1200)
    return () => clearTimeout(t)
  }, [replay, conversa.length])

  const { ativos, focoVivo, porQuem } = useMemo(() => {
    const agora = d ? Date.parse(d.agora) : 0
    const porQuem = {}, ativos = new Set()
    let focoVivo = null
    for (const p of d?.passos || []) {
      (porQuem[p.quem] ||= []).push(p)
      if (agora - Date.parse(p.criado_em) < ATIVO_MS) { ativos.add(p.quem); focoVivo = p }
    }
    return { ativos, focoVivo, porQuem }
  }, [d])

  const foco = replay !== null ? conversa[replay] : focoVivo
  const feed = (d?.passos || []).slice(-8).reverse()
  const resumoSel = sel && (resumos || []).find(r => r.nome === sel)

  return (
    <section ref={caixa} className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Radio className="h-4 w-4 text-emerald-400" /> Escritório
          <span className="text-xs font-normal text-ink-3">{replay !== null ? `reproduzindo · passo ${replay + 1} de ${conversa.length}` : 'ao vivo'}</span>
        </h2>
        <div className="flex gap-2">
          {replay === null
            ? <button onClick={() => { setSel(null); setReplay(0) }} disabled={!conversa.length}
                className="flex items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/15 px-3 py-1.5 text-sm font-medium text-blue-300 disabled:opacity-40">
                <Play className="h-4 w-4" /> Reproduzir última conversa</button>
            : <button onClick={() => setReplay(null)} className="flex items-center gap-1.5 rounded-md border border-line bg-raise-1 px-3 py-1.5 text-sm font-medium text-ink-2">
                <Square className="h-4 w-4" /> Parar</button>}
          <button onClick={() => (document.fullscreenElement ? document.exitFullscreen() : caixa.current?.requestFullscreen?.())}
            className="rounded-md border border-line bg-raise-1 p-2 text-ink-2" title="Tela cheia" aria-label="Tela cheia">
            <Maximize2 className="h-4 w-4" /></button>
        </div>
      </div>
      {erro && !d && <p className="mt-3 text-xs text-red-300">Não foi possível carregar o escritório.</p>}
      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_270px]">
        <div className="overflow-hidden rounded-lg border border-line" style={{ background: '#cfd8e6' }}>
          <Sala cores={cores} ia={d?.ia} foco={foco} ativos={replay !== null ? new Set() : ativos} sel={sel} onSel={setSel}
            ligado={d ? d.ligado : true} empresa={nomeEmpresa} />
        </div>
        <div className="rounded-lg border border-line bg-raise-1 p-3">
          {sel ? (
            <CartaoDoAgente nome={sel} cor={cores[sel] || '#94a3b8'} resumo={resumoSel} passos={porQuem[sel] || []} ia={d?.ia}
              trabalhando={ativos.has(sel)} onPerfil={onPerfil} onFechar={() => setSel(null)} />
          ) : (
            <>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">{replay !== null ? 'Última conversa' : 'Agora'}</p>
              <ol className="mt-2 space-y-1.5" aria-live="polite">
                {(replay !== null ? conversa : feed).map((p, k) => (
                  <li key={`${p.trace_id}-${p.criado_em}-${k}`}
                    className={`text-xs ${replay !== null && k === replay ? 'rounded bg-blue-500/15 px-1 text-ink' : replay !== null && k > replay ? 'text-ink-3 opacity-50' : 'text-ink-2'}`}>
                    <span className="font-semibold" style={{ color: cores[p.quem] || '#94a3b8' }}>{p.quem}</span> {p.explicacao}
                    {p.resultado === 'bloqueado' && <span className="ml-1 text-red-300">· {p.regra || 'bloqueado'}</span>}
                  </li>
                ))}
                {!(replay !== null ? conversa : feed).length && <li className="text-xs text-ink-3">Ninguém trabalhando agora.</li>}
              </ol>
              <p className="mt-3 border-t border-line pt-2 text-[11px] text-ink-3">Clique num agente para ver o que ele faz.</p>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
