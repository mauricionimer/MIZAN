// Identidades visuais únicas, compartilhadas pela sala e pelos painéis.
export const TIMES = {
  atendimento: { nome: 'Atendimento' }, estrategia: { nome: 'Estratégia' },
  acompanhamento: { nome: 'Acompanhamento' }, coordenacao: { nome: 'Coordenação' },
}
export const AGENTES = [
  ['Triagem', 'Leitura da intenção', 'Identifica intenção, urgência e sinais de risco.', '#a78bfa', 'atendimento', 1, 2, '#c98e62', '#202737', 'headset'],
  ['Negociador', 'Conversa e acordos', 'Conversa com o devedor e conduz propostas e acordos.', '#60a5fa', 'atendimento', 4, 2, '#f1c9a5', '#80502a', 'gravata'],
  ['Estrategista', 'Plano de abordagem', 'Define abordagem, tom e oferta conforme a política.', '#22d3ee', 'estrategia', 9, 2, '#8d5a3b', '#202737'],
  ['Cientista', 'Análise de evidências', 'Analisa resultados e propõe melhorias para decisão humana.', '#facc15', 'estrategia', 12, 2, '#f1c9a5', '#7c432b', 'jaleco'],
  ['Acompanhamento', 'Datas e pagamentos', 'Acompanha pagamentos, retornos, lembretes e atrasos.', '#fb923c', 'acompanhamento', 1, 8, '#8d5a3b', '#3b2414', 'headset'],
  ['Orquestrador', 'Coordenação do fluxo', 'Recebe eventos e aciona a próxima etapa do caso.', '#94a3b8', 'coordenacao', 5, 9, '#c98e62', '#374151', 'headset'],
  ['Supervisor', 'Revisão e passagem', 'Revisa o tom e prepara a passagem do caso para a equipe.', '#e879f9', 'coordenacao', 9, 8, '#e8b48a', '#b5b5bc', 'oculos'],
  ['Auditor', 'Política e segurança', 'Autoriza ou bloqueia ações conforme a política de cobrança.', '#f59e0b', 'coordenacao', 12, 8, '#e8b48a', '#272732', 'oculos'],
  ['Travas', 'Conferência da saída', 'Confere texto, números e segurança antes do envio.', '#f472b6', 'coordenacao', 14, 11, '#e8b48a', '#374151', 'servico'],
  ['Ferramenta', 'Operações em código', 'Registra acordos, compromissos e operações autorizadas.', '#34d399', 'acompanhamento', 2.5, 11, '#e8b48a', '#374151', 'servico'],
].map(([nome, papel, desc, cor, time, i, j, pele, cabelo, acc]) => ({
  id: nome, nome, papel, desc, cor, time, i, j, pele, cabelo, acc,
  ia: !['Orquestrador', 'Auditor', 'Travas', 'Ferramenta'].includes(nome),
}))
export const MESAS = Object.fromEntries(AGENTES.map(a => [a.nome, a]))
export const ESTADOS = {
  trabalhando: { nome: 'Trabalhando', cor: '#2e9e44' },
  pensando: { nome: 'Pensando', cor: '#3b7dd8' },
  aguardando: { nome: 'Aguardando', cor: '#ad7410' },
  desconhecido: { nome: 'Sem sinal', cor: '#6c7582' },
}
export const hora = t => t ? new Date(t).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'
export const curto = id => String(id || '').slice(0, 6)
export const tarefa = no => ({ receber: 'Recebendo mensagem', triagem: 'Identificando a intenção', negociar: 'Conduzindo a negociação',
  auditor: 'Conferindo a política', guardrails: 'Conferindo a resposta', enviar: 'Enviando resposta', conferir: 'Conferindo vencimento',
  lembrar: 'Preparando lembrete', registrar: 'Registrando pagamento', abordagem: 'Definindo abordagem',
  avisar_equipe: 'Avisando a equipe', transferir: 'Passando para a equipe', cobrar_atraso: 'Acompanhando atraso',
  encerrar: 'Encerrando acompanhamento', resposta_fixa: 'Preparando resposta',
}[no] || String(no || 'Etapa registrada').replace('ferramenta:', '').replaceAll('_', ' '))
export function mensagem(e) {
  if (e.tipo === 'handoff') return `${e.de} → ${e.para} · #${curto(e.caso_id)}`
  return `${e.quem}: ${e.tipo === 'erro' ? 'erro na etapa' : e.resultado === 'bloqueado' ? 'etapa bloqueada' : e.tipo === 'fim' ? 'etapa concluída' : tarefa(e.no)} · #${curto(e.caso_id)}`
}
