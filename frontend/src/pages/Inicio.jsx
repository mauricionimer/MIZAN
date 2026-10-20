import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { listarCarteiras, carregarCarteira } from '../api'
import useAvisoAgenda from '../components/useAvisoAgenda'
import AppShell from '../components/AppShell'
import { BentoCard, BentoGrid } from '../components/ui/bento'
import { lista, item, SEM_MOVIMENTO } from '../lib/motion'

/**
 * Hub de entrada: o primeiro lugar em que a pessoa cai depois do login.
 * Cada bloco leva a uma área da plataforma, as mesmas do menu (☰), que continua
 * disponível no canto superior esquerdo. As artes são desenhadas em SVG com as
 * cores da marca: não dependem de imagens externas.
 */

const BARRAS = 'var(--royal, #5966d9)'

// Pequenas ilustrações, uma por área. Usam currentColor para acompanhar o tema.
function Arte({ tipo }) {
  const traco = { stroke: 'currentColor', strokeWidth: 2, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' }
  return (
    <svg viewBox="0 0 320 160" className="hub-arte-svg" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      {tipo === 'hoje' && (
        <g>
          {[0, 1, 2].map(i => (
            <g key={i} transform={`translate(70 ${28 + i * 38})`}>
              <rect width="180" height="28" rx="8" fill="currentColor" opacity={0.14 - i * 0.03} />
              <circle cx="16" cy="14" r="5" fill={BARRAS} />
              <rect x="30" y="9" width={110 - i * 22} height="10" rx="5" fill="currentColor" opacity="0.35" />
            </g>
          ))}
        </g>
      )}
      {tipo === 'carteira' && (
        <g>
          <polygon points="86,100 118,100 106,140 74,140" fill="#b8c0ee" />
          <polygon points="130,70 162,70 150,140 118,140" fill="#8f9be9" />
          <polygon points="174,36 206,36 194,140 162,140" fill={BARRAS} />
          <polyline points="214,92 238,70 262,80 290,42" {...traco} opacity="0.5" />
        </g>
      )}
      {tipo === 'agentes' && (
        <g {...traco} opacity="0.9">
          <line x1="160" y1="80" x2="96" y2="42" /><line x1="160" y1="80" x2="226" y2="40" />
          <line x1="160" y1="80" x2="100" y2="124" /><line x1="160" y1="80" x2="228" y2="122" />
          <circle cx="160" cy="80" r="16" fill={BARRAS} stroke="none" />
          {[[96, 42], [226, 40], [100, 124], [228, 122]].map(([x, y]) => <circle key={x} cx={x} cy={y} r="9" fill="currentColor" opacity="0.35" stroke="none" />)}
        </g>
      )}
      {tipo === 'resultados' && (
        <g>
          <polyline points="40,124 100,96 150,108 210,60 280,32" {...traco} strokeWidth="3" style={{ color: BARRAS }} />
          <polyline points="40,124 100,96 150,108 210,60 280,32 280,140 40,140" fill="currentColor" opacity="0.08" stroke="none" />
          {[[100, 96], [210, 60], [280, 32]].map(([x, y]) => <circle key={x} cx={x} cy={y} r="5" fill={BARRAS} />)}
        </g>
      )}
      {tipo === 'config' && (
        <g {...traco}>
          {[[50, 0.35], [80, 0.7], [110, 0.5]].map(([y, p]) => (
            <g key={y}><line x1="70" y1={y} x2="250" y2={y} opacity="0.3" /><circle cx={70 + 180 * p} cy={y} r="8" fill={BARRAS} stroke="none" /></g>
          ))}
        </g>
      )}
      {tipo === 'acordos' && (
        <g {...traco}>
          <rect x="96" y="30" width="128" height="100" rx="12" opacity="0.35" />
          <path d="M122 82l16 16 34-36" stroke={BARRAS} strokeWidth="5" />
        </g>
      )}
      {tipo === 'painel' && (
        <g {...traco}>
          <path d="M80 118a80 80 0 0 1 160 0" opacity="0.3" strokeWidth="10" />
          <path d="M80 118a80 80 0 0 1 112-72" stroke={BARRAS} strokeWidth="10" />
          <line x1="160" y1="118" x2="196" y2="80" strokeWidth="4" />
        </g>
      )}
      {tipo === 'ia' && (
        <g {...traco}>
          <path d="M160 28l-34 56h30l-10 48 46-64h-30l8-40z" fill={BARRAS} stroke="none" opacity="0.9" />
          <circle cx="160" cy="80" r="58" opacity="0.18" />
        </g>
      )}
      {tipo === 'comando' && (
        <g {...traco}>
          <rect x="80" y="36" width="160" height="88" rx="12" opacity="0.3" />
          <path d="M108 70l22 18-22 18" stroke={BARRAS} strokeWidth="5" /><line x1="146" y1="108" x2="190" y2="108" />
        </g>
      )}
    </svg>
  )
}

function blocosDoPerfil({ gestor, comando, agenda }) {
  const aviso = agenda.alto > 0 ? `${agenda.alto} ${agenda.alto === 1 ? 'vencido' : 'vencidos'}`
              : agenda.medio > 0 ? `${agenda.medio} para hoje` : null
  const hoje = { id: 'hoje', to: '/agenda', eyebrow: 'Hoje', title: 'Agenda', arte: 'hoje', badge: comando ? null : aviso,
    description: 'Compromissos, retornos e atendimentos do dia, com o que está vencido em destaque.', className: 'lg:col-span-3' }
  const carteira = { id: 'carteira', to: '/', eyebrow: 'Carteira', title: 'Análise e painel da carteira', arte: 'carteira',
    description: 'Suba ou conecte a carteira, veja quem cobrar primeiro e acompanhe os pagamentos.', className: 'lg:col-span-3' }
  const lista = gestor ? [
    hoje, carteira,
    { id: 'agente', to: '/agente', eyebrow: 'Agentes', title: 'Equipe de agentes de IA', arte: 'agentes',
      description: 'Veja os agentes trabalhando, as conversas e as regras do Auditor.', className: 'lg:col-span-2' },
    { id: 'resultados', to: '/resultados', eyebrow: 'Resultados', title: 'O que a cobrança recuperou', arte: 'resultados',
      description: 'Resultados, equipe, acordos e o laboratório de comparação.', className: 'lg:col-span-2' },
    { id: 'config', to: '/ofertas', eyebrow: 'Configurações', title: 'Ofertas e política de cobrança', arte: 'config',
      description: 'Ofertas, política, usuários, auditoria e simulação histórica.', className: 'lg:col-span-2' },
  ] : [
    hoje, carteira,
    { id: 'acordos', to: '/acordos', eyebrow: 'Acordos', title: 'Meus acordos', arte: 'acordos',
      description: 'Acordos firmados e o que já foi pago.', className: 'lg:col-span-2' },
    { id: 'painel', to: '/painel', eyebrow: 'Painel', title: 'Meu painel', arte: 'painel',
      description: 'Seu desempenho e suas metas.', className: 'lg:col-span-2' },
    { id: 'ia', to: '/ia', eyebrow: 'IA', title: 'Performance da IA', arte: 'ia',
      description: 'Como as recomendações da IA estão se saindo.', className: 'lg:col-span-2' },
  ]
  if (comando) lista.push({ id: 'comando', to: '/comando', eyebrow: 'Plataforma', title: 'Comando', arte: 'comando',
    description: 'Empresas, aprendizado do modelo, chaves de API e dúvidas.', className: 'lg:col-span-6' })
  return lista
}

export default function Inicio() {
  const { usuario, isAdmin, isComando } = useAuth()
  const agenda = useAvisoAgenda()
  const reduzir = useReducedMotion()
  const blocos = blocosDoPerfil({ gestor: isAdmin || isComando, comando: isComando, agenda })
  const nome = (usuario?.nome || '').split(' ')[0]
  const navigate = useNavigate()
  const { result, setResult, setVista } = useAnalysis()
  const [abrindo, setAbrindo] = useState(false)

  // "Carteira" abre direto a última análise da própria pessoa (no painel da
  // carteira); de lá ela troca de análise se quiser. Sem nenhuma análise ainda,
  // cai na tela de análise para subir a primeira.
  async function abrirCarteira(e) {
    e.preventDefault()
    if (abrindo) return
    if (result) { setVista('dashboard'); navigate('/'); return }
    setAbrindo(true)
    try {
      const [ultima] = await listarCarteiras({ meus: true, limite: 1 })
      if (ultima?.id) {
        setResult(await carregarCarteira(ultima.id))
        setVista('dashboard')
      } else setVista('analise')
    } catch {
      setVista('analise')          // servidor fora ou acesso negado: a tela de análise segue disponível
    } finally {
      setAbrindo(false)
      navigate('/')
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="hub-titulo">{nome ? `Olá, ${nome}` : 'Olá'}</h1>
        <p className="hub-sub">Para onde você quer ir?</p>
        <motion.div className="mt-8" variants={reduzir ? SEM_MOVIMENTO : lista} initial="inicial" animate="entra">
          <BentoGrid>
            {blocos.map(b => (
              <motion.div key={b.id} variants={reduzir ? SEM_MOVIMENTO : item} className={b.className}>
                <BentoCard to={b.to} eyebrow={b.eyebrow} title={b.title} description={b.description}
                  badge={b.badge} loading={b.id === 'carteira' && abrindo}
                  onNavigate={b.id === 'carteira' ? abrirCarteira : undefined} graphic={<Arte tipo={b.arte} />} className="h-full" />
              </motion.div>
            ))}
          </BentoGrid>
        </motion.div>
      </div>
    </AppShell>
  )
}
