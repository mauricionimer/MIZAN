# Escritório dos agentes — plano aprovado e implementação

Referências: `prompt-escritorio-agentes.md` enviado pelo usuário e a imagem da sala. O HTML `sala-dos-agentes.html`, citado no MD, não foi fornecido nem localizado com esse nome em Downloads. Plano aprovado pelo usuário em 21/10/2026: “sendo tudo na mesma página tá tudo certo pode fazer”.

## Composição proposta

Interpretar “escritório separado dos cards” como três áreas independentes: lista de agentes à esquerda, quadro da sala no centro e detalhes do agente selecionado à direita. Lista e detalhes são HTML separado do Canvas e ficam fora da área desenhada da sala. Não ficam pintados no cenário nem cobrem as mesas.

A sala segue o estilo isométrico do MD: Canvas 2D, pixels ampliados por fator inteiro, paredes laranja, piso de madeira, divisórias de vidro com portas, mesas, cadeiras, plantas, janelas e identificação da empresa. Cabeçalho, navegação, outras abas e estilos globais do MIZAN permanecem como estão. Os painéis preservam a tipografia do MIZAN; os rótulos do cenário podem usar fonte pixel.

O layout responde à largura real do container. Quando não couberem três áreas, sala acima e painéis abaixo; abaixo de 760 px, painéis em gaveta local. Controles de câmera só capturam ponteiro/roda sobre a sala. Casos e Atividade abrem a partir da barra local. Não haverá captura global de teclado/scroll, `position:fixed` no escritório nem CSS global.

Essa separação adapta as janelas sobrepostas do MD ao pedido explícito de manter o escritório separado dos dois cards. A posição final dos três painéis faz parte desta aprovação.

## Inventário real

O frontend e `agente/api.py:AGENTES_TELA` apresentam dez categorias. São oito atores do escritório e dois serviços de código. “Equipe” representa pessoas da empresa; não é um agente artificial extra.

| Id/identificação no código | Nome | Função | Recebe | Entrega |
|---|---|---|---|---|
| Nós `receber`, `enviar`, `resposta_fixa`, `avisar_equipe`, `transferir`; categoria `Orquestrador` | Orquestrador | Organiza eventos e executa o grafo; único orquestrador. | Mensagens, relógio, pagamentos e fila. | Triagem, Estrategista, Acompanhamento ou equipe conforme o grafo. |
| `triagem` | Triagem | Classifica intenção e sinais de risco. | Mensagem recebida pelo Orquestrador. | Negociador ou ramificações de segurança e equipe. |
| `negociador` / nó `negociar` | Negociador | Conduz conversa, simulação, oferta e aceite. | Triagem, estratégia e resposta do devedor. | Ferramentas, Auditor, Supervisor, Travas e resposta via Orquestrador. |
| `estrategista` | Estrategista | Propõe abordagem, tom e oferta inicial; orienta o plano do dia. | Predições, política, dados e orientação aprovada do laboratório. | Abordagem e orientação usada pelo Negociador. |
| `acompanhamento` | Acompanhamento | Trata datas, pagamentos, lembretes e atraso. | Eventos de vencimento, pagamento e relógio. | Atualização do caso, mensagem ou passagem para a equipe. |
| `supervisor` | Supervisor | Revisa tom em casos delicados e prepara passagem para pessoas. | Resposta do Negociador ou necessidade de atendimento humano. | Revisão ao Negociador ou resumo para a equipe. Não substitui o Auditor. |
| `cientista` | Cientista | Analisa evidências e propõe melhorias. | Métricas estatísticas, resultados e sinais da equipe. | Recomendação proposta, cuja adoção depende de decisão humana. |
| `auditor` | Auditor | Autoriza ou bloqueia ações segundo a política. | Ações propostas, argumentos e contexto. | Permissão ou bloqueio à etapa que o chamou. |
| Nó `guardrails`; categoria `Travas` | Travas | Confere texto, números e segurança antes da saída. | Resposta preparada. | Liberação, correção ou bloqueio. |
| Prefixo `ferramenta:`; categoria `Ferramenta` | Ferramenta | Executa operações permitidas e registra resultados. | Solicitação validada do agente. | Resultado para o chamador e registros reais de acordo, agenda ou passagem. |

Não usar Atlas, Bia, Dante, Íris, Caio, Nina ou Theo. Travas e Ferramenta permanecem identificadas como serviços em código; podem aparecer como posto de controle e balcão de operações na sala, com seleção e métricas próprias, sem inventar dois novos agentes de IA.

## Fluxos encontrados

1. Mensagem: Orquestrador recebe → Triagem → Negociador → resposta pelo Orquestrador. Durante a negociação, Auditor e ferramentas podem ser chamados várias vezes. Supervisor revisa o tom quando há indicação; Travas conferem a saída.
2. Segurança: pedido para parar, pessoa errada, contestação, pedido de pessoa ou risco seguem ramificações próprias. O caso pode ser suspenso/contestado e transferido. Não há uma passagem obrigatória por todos os agentes.
3. Estratégia: plano do dia → Estrategista/abordagem → conversa quando houver resposta. As decisões orientam o Negociador; esse fluxo não é uma fase obrigatória entre Triagem e Negociador.
4. Acompanhamento: relógio/vencimento → conferência → lembrete, cobrança do atraso ou passagem para pessoa. Pagamento confirmado tem grafo próprio de registro. Depois, o devedor pode retornar ao fluxo de conversa.
5. Laboratório: dados e estatística → Cientista → recomendação → decisão humana → orientação ao Estrategista quando aprovada.

Há concorrência entre casos e eventos, mas o mesmo caso tem trava de processamento. Não existe na API atual uma identificação de instância que permita representar com honestidade “Negociador 1” e “Negociador 2”. Nenhuma mesa extra deve ser criada só porque houve várias ações recentes.

Aprovações humanas: reuniões solicitadas pelos agentes são aprovadas/atribuídas pelo ADM na Agenda; recomendações do Cientista são propostas até decisão humana; casos transferidos ficam com a equipe. O Supervisor não aprova políticas nem substitui essas decisões.

## Fontes atuais e lacunas

| Fonte | Dados disponíveis | Limite para a sala |
|---|---|---|
| `GET /agente/estacao` | Passos dos últimos 15 minutos, última conversa concluída, estado do interruptor e papéis de IA. Hoje consultado a cada 5 s. | Passos são registrados ao terminar; não há evento de início em execução. |
| `GET /agente/agentes` | Ações, erros, bloqueios, tempo médio e custo por categoria nas últimas 24 h. Hoje consultado a cada 15 s. | Não fornece tarefa em curso, fila por agente ou porcentagem de progresso. |
| `GET /agente/agentes/{nome}` | Perfil e últimas 20 decisões, com duração, tokens, custo e identificação do trace/caso. | Últimas 20 ações não equivalem ao total de tokens de 24 h. |
| `GET /agente/central` | Eventos pendentes/processando/feitos/falhos, falhas e casos por situação. | Evento feito não significa dívida quitada. A fila é global, não uma fila atribuída por agente. |
| `agente/rastreio.py` | Nó, agente, resultado, duração, tokens de entrada/saída, custo, regra e versão. | `Rastreio.span` grava no final do bloco; atividade recente não prova execução atual. |

Não há WebSocket ou SSE nesta área. A integração inicial continua por polling, com uma camada única de dados compartilhada entre sala, lista, perfil, casos e atividade; sem um pedido por bonequinho. Erros mantêm o último estado com horário da última atualização.

O destaque atual considera “trabalhando” quem teve um passo nos últimos 30 segundos. Isso é uma aproximação que deve ser retirada do status ao vivo. A atividade histórica continua disponível como “Última ação”.

Para representar tarefa atual, pensando e handoff ao vivo, será necessária instrumentação observacional no backend: registrar início/fim da etapa e passagem efetiva para a etapa seguinte, com empresa, caso, trace, agente e horário. Esses sinais não devem alterar roteamento, decisões, prompts ou permissões. A implementação dessa instrumentação precisa estar incluída na confirmação do plano; sem ela, os estados ausentes ficam omitidos e a sala mostra somente atividade registrada.

## Estados visuais

| Estado | Uso proposto |
|---|---|
| Trabalhando | Somente início real sem término/erro, com sinal válido de execução. Nunca por ação concluída há menos de 30 s. |
| Pensando | Somente sinal real de chamada ao modelo em andamento. Hoje não está exposto. |
| Entregando | Passagem registrada no mesmo caso/trace, com origem e destino conhecidos. A caminhada ilustra esse registro, sem atrasar o processamento. Sem sinal de passagem, não fabricar handoff. |
| Aguardando | Sem tarefa em execução confirmada. Não exibir “fila 0” quando só há uma fila global desconhecida por agente. |
| Erro | Erro registrado da tarefa ou falha vigente, com horário e tentativa quando disponíveis. Não transformar todo erro antigo em estado atual. |
| Ocioso/café | Animação decorativa identificada como tal, sem indicar pausa da operação. Só quando houver confirmação de que não está executando. |
| Reunião | Omitir: não existe estado equivalente de reunião entre agentes. |
| Pausado | Omitir controle individual: o backend não oferece pausa/retomada por agente. IA desligada pode usar reserva em código e não significa agente pausado. |

Não mostrar porcentagem de progresso, fila individual, economia estimada, quantidade de dívidas ou casos concluídos hoje sem uma fonte correspondente. Mostrar etapas registradas, última ação, duração em ms, tokens reais, modelo/versão e custo conforme as permissões já adotadas no produto. Custos respeitam o escopo de visibilidade atual. Tokens agregados de 24 h precisam ser somados no backend sobre a mesma janela das demais métricas.

Não haverá campo para mandar instruções ao Orquestrador: o sistema tem simulação de mensagem de devedor, mas isso não é um canal de comando ao Orquestrador. Reproduzir conversa, se mantido, fica explicitamente identificado como reprodução de registros, separado da operação ao vivo.

## Setores e aparência proposta

| Setor | Atores/postos | Aparência dos bonecos |
|---|---|---|
| Atendimento | Triagem e Negociador | Triagem: camisa lilás, cabelo curto escuro, headset. Negociador: azul, cabelo castanho curto, gravata. |
| Estratégia | Estrategista e Cientista | Estrategista: ciano, cabelo curto escuro, sem acessório. Cientista: amarelo com jaleco, cabelo castanho, óculos. |
| Acompanhamento | Acompanhamento | Camisa laranja, cabelo castanho, headset; mesa perto do calendário e arquivo. |
| Coordenação | Orquestrador, Supervisor e Auditor; postos Travas/Ferramenta | Orquestrador: cinza azulado, cabelo escuro, headset. Supervisor: magenta, cabelo grisalho, óculos. Auditor: âmbar, cabelo escuro, prancheta. Travas: catraca rosa. Ferramenta: balcão verde com arquivo. |

São propostas visuais, não características ou identidades de pessoas reais. Cores usam as categorias já existentes em `COR_AGENTE`. Logo/nome da empresa vêm da configuração real, com fallback MIZAN.

## Arquivos envolvidos depois da aprovação

- `frontend/src/components/EscritorioAgentes.jsx`: hoje contém sala SVG, consulta, reprodução e cartão de seleção; separar responsabilidades e substituir o desenho por Canvas 2D.
- `frontend/src/pages/Agente.jsx`, função `AoVivo`: hoje monta escritório e uma segunda grade de agentes; ajustar somente a composição local para evitar duplicidade de lista/cards.
- `frontend/src/pages/AgentePerfil.jsx`: fonte de conteúdo e métricas do perfil existente; preservar sua rota e comportamento, compartilhando apresentação onde for adequado.
- Novos módulos locais de configuração visual, renderer Canvas, hook de dados e painéis HTML com prefixo exclusivo; nenhuma biblioteca de jogo.
- Se confirmada a telemetria ao vivo: pontos de observação em `backend/agente/rastreio.py`/`orquestrador.py` e a resposta da estação em `api.py`, com testes para demonstrar que a execução do caso continua igual.

## Validação prevista

Screenshot real da aplicação rodando após a implementação. Testar container de 1024 a 1920 px e gaveta abaixo de 760 px; teclado; foco; redimensionamento; zoom inteiro; câmera; reconexão; dados ausentes; deduplicação de eventos; mesmo trace/caso no handoff; atualização sem simulação; nenhuma interferência no scroll da página ou em outras telas.

## Confirmação recebida

A separação em três áreas e a instrumentação mínima de execução foram aprovadas. O levantamento respeitou a Fase 0 do MD: “Pare aqui, apresente o plano e espere confirmação antes de implementar.”

## Entrega e limites dos dados

- `/agente`, aba Ao vivo: lista, sala e detalhe na mesma página. Selecionar não navega; o botão Perfil continua disponível como acesso opcional à rota já existente.
- Painéis em áreas reservadas, sem sobrepor as mesas e sem arrastá-los sobre a sala, conforme a composição aprovada. Casos/Atividade substituem o painel esquerdo. Abaixo de 760 px, uma gaveta local alterna lista, detalhes, casos e atividade.
- Canvas 2D com rasterização por scanline/Bresenham, fundo em cache, zoom inteiro, pan, seleção, teclado local e preferência de movimento reduzido. Em celulares, o zoom mínimo 1 mantém os pixels e a sala é explorável por arraste.
- O fluxo real emite início, fim, erro, passagem e chamada ao modelo. Os sinais ficam no JSON do evento já reservado, em `_escritorio`, sem migration, texto do devedor, prompts ou documentos. Histórico de até 80 sinais por evento; API entrega até 100 sinais e 100 casos da amostra dos últimos 500 eventos, priorizando os que estão em execução.
- A execução só aparece ativa enquanto o evento está processando e o sinal tem menos de 5 minutos. Falhas observacionais são isoladas do grafo. Eventos em execução sem sinal tornam os estados não identificáveis “Sem sinal”.
- Cientista executa análises avulsas fora da fila de casos: mostra histórico e métricas, com “Sem sinal” para a tarefa ao vivo. Não há suposição de execução pela recência de uma ação.
- Polling da estação a cada 5 s e métricas a cada 15 s, interrompido em aba oculta, sem sobreposição e sem consulta por boneco. Handoffs novos do mesmo caso/trace animam uma rota BFS; registros antigos ficam no feed. A animação nunca bloqueia o processamento.
- Tokens são somados no backend sobre a mesma janela de 24 h das métricas existentes, limitada a 5.000 etapas por empresa. A interface sinaliza quando esse limite é alcançado. Ações individuais mostram os últimos 15 minutos, no máximo 20 por categoria.
- Fila individual, progresso percentual, economia, pausa individual, reunião e comando por chat não têm fonte correspondente e permanecem omitidos. Erros e bloqueios aparecem no histórico/atividade e falhas vigentes também em Casos, sem converter um erro antigo em estado atual.
- Custos continuam restritos na apresentação ao perfil Comando, como antes. Isolamento de empresa e permissões das rotas existentes foram preservados.

## Verificação realizada

Build de produção do frontend. Testes de rastreio/estação, orquestração, acompanhamento, conversa, base de IA, Supervisor, Cientista e fluxo do devedor. Novos testes verificam início real, espera de modelo, retorno de spans aninhados, isolamento entre empresas, exclusão de texto sensível, descarte de sinal vencido, limite do histórico e execução preservada quando a telemetria falha.

Navegador Edge isolado com respostas de teste: clique no boneco e na lista, seleção sem troca de página, zoom, centralização, seguir, teclado, Casos, Atividade, deduplicação, perda e recuperação de conexão, BFS entre todas as mesas e larguras de 320, 390, 760, 1024, 1280 e 1920 px. Nenhum erro de JavaScript nem transbordamento horizontal nos tamanhos verificados.

As capturas `escritorio-desktop.png`, `escritorio-1280.png` e `escritorio-mobile.png` são da aplicação local rodando com dados de teste; não representam uma execução em produção. Nenhuma sessão real do usuário foi utilizada nesses testes.
