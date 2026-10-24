// Mesmos carregadores para React.lazy e intenção de navegação. Só baixa código.
export const paginas = {
  Home: () => import('../pages/Home'),
  Inicio: () => import('../pages/Inicio'),
  PastasDevedores: () => import('../pages/PastasDevedores'),
  DebtorDetail: () => import('../pages/DebtorDetail'),
  Feedback: () => import('../pages/Feedback'),
  BanditDashboard: () => import('../pages/BanditDashboard'),
  AprendizadoDashboard: () => import('../pages/AprendizadoDashboard'),
  ComandoDashboard: () => import('../pages/ComandoDashboard'),
  AdminUsuarios: () => import('../pages/AdminUsuarios'),
  Auditoria: () => import('../pages/Auditoria'),
  AlterarSenha: () => import('../pages/AlterarSenha'),
  EsqueciSenha: () => import('../pages/EsqueciSenha'),
  RedefinirSenha: () => import('../pages/RedefinirSenha'),
  Login: () => import('../pages/Login'),
  Privacidade: () => import('../pages/Privacidade'),
  Backtest: () => import('../pages/Backtest'),
  PerformanceIA: () => import('../pages/PerformanceIA'),
  Agenda: () => import('../pages/Agenda'),
  PainelOperador: () => import('../pages/PainelOperador'),
  Resultados: () => import('../pages/Resultados'),
  Acordos: () => import('../pages/Acordos'),
  Ofertas: () => import('../pages/Ofertas'),
  Retencao: () => import('../pages/Retencao'),
  TreinoModelo: () => import('../pages/TreinoModelo'),
  ChavesApi: () => import('../pages/ChavesApi'),
  Ajuda: () => import('../pages/Ajuda'),
  Premissas: () => import('../pages/Premissas'),
  DuvidasComando: () => import('../pages/DuvidasComando'),
  Agente: () => import('../pages/Agente'),
  AgentePerfil: () => import('../pages/AgentePerfil'),
  LaboratorioPagina: () => import('../pages/LaboratorioPagina'),
}

const rotas = {
  '/': paginas.Home,
  '/inicio': paginas.Inicio,
  '/pastas': paginas.PastasDevedores,
  '/feedback': paginas.Feedback,
  '/bandit': paginas.BanditDashboard,
  '/aprendizado': paginas.AprendizadoDashboard,
  '/comando': paginas.ComandoDashboard,
  '/admin/usuarios': paginas.AdminUsuarios,
  '/auditoria': paginas.Auditoria,
  '/alterar-senha': paginas.AlterarSenha,
  '/login': paginas.Login,
  '/backtest': paginas.Backtest,
  '/ia': paginas.PerformanceIA,
  '/agenda': paginas.Agenda,
  '/painel': paginas.PainelOperador,
  '/resultados': paginas.Resultados,
  '/acordos': paginas.Acordos,
  '/ofertas': paginas.Ofertas,
  '/retencao': paginas.Retencao,
  '/comando/treino': paginas.TreinoModelo,
  '/comando/chaves': paginas.ChavesApi,
  '/ajuda': paginas.Ajuda,
  '/premissas': paginas.Premissas,
  '/comando/duvidas': paginas.DuvidasComando,
  '/agente': paginas.Agente,
  '/laboratorio': paginas.LaboratorioPagina,
}

export function prepararPagina(rota) {
  const conexao = globalThis.navigator?.connection
  if (conexao?.saveData || /(^|-)2g$/.test(conexao?.effectiveType || '')) return
  const caminho = (rota || '/').split('?')[0]
  const carregar = rotas[caminho] || (caminho.startsWith('/agente/') ? paginas.AgentePerfil : null)
  // Uma falha de antecipação não bloqueia o clique: lazy pode tentar de novo.
  carregar?.().catch(() => {})
}
