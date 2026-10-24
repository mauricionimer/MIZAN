# Análise de desempenho do MIZAN

Revisão realizada em 22–23/10/2026. Escopo: estrutura das rotas, carregamento do frontend, consultas principais, animação compartilhada, servidor e hospedagem.

## Conclusão

A lentidão tem causas diferentes: espera pelo servidor/banco, volume de dados desnecessário e trabalho contínuo do navegador. As páginas já eram divididas em arquivos carregados sob demanda; baixar o aplicativo inteiro não era o principal problema da entrada. A revisão corrigiu seis pontos reproduzíveis e identificou os próximos trabalhos de maior impacto.

Não foi feita uma sessão autenticada de medição em produção nem um teste de carga sobre dados reais. A análise combina inspeção do código, medições públicas, build e testes locais com dados fictícios. Os números abaixo não são percentuais de aceleração do site em produção.

## Evidências medidas

| Medição | Resultado | Interpretação |
|---|---|---|
| HTML público `/inicio`, três chamadas consecutivas | 1.830 ms, 247 ms, 208 ms; 1.325 bytes | Tempo HTTP completo observado desta máquina, incluindo a primeira conexão. Não mede a página pronta nem suas consultas autenticadas. |
| Backend `/health`, três chamadas consecutivas | 715 ms, 314 ms, 285 ms | Servidor estava respondendo. O endpoint não consulta o banco nem representa o tempo das telas. Não houve medição de retomada após hibernação. |
| Carteira sintética com 1.203 devedores e campos extensos | 2.789.105 → 309.767 bytes lidos no banco falso | Aproximadamente 89% menos volume nessa massa. Resumo, filtros, distribuições e dez destaques comparados integralmente. A referência usa a leitura completa, sem incluir a segunda leitura redundante antiga. |
| Carteira antiga, sem rank gravado, mesma massa | 2.790.212 → 311.007 bytes | Mesmo resultado, preservando a política que recompõe a ordem. |
| Início + aviso da Agenda no menu | 1 pedido simultâneo ao endpoint de resumo | Antes havia consumidores independentes sem compartilhamento da requisição em andamento. |
| Fundo animado no navegador de teste | 44 desenhos em dois segundos | Limite de 24 fps; antes desenhava a cada quadro do monitor. Aba oculta e movimento reduzido ficam sem animação contínua. |
| JavaScript principal, build | Aproximadamente 128 KB gzip | A antecipação de rotas acrescentou aproximadamente 1 KB gzip. Ela reduz espera no clique, não o tamanho total do aplicativo. |

As massas de carteira são artificiais, incluindo um campo longo por devedor. O ganho depende do tamanho real dos registros. O resultado medido é redução de dados lidos, não uma promessa de páginas 89% mais rápidas.

## Correções implementadas

1. **Resumo da carteira:** lê somente os campos necessários aos cálculos e busca os detalhes completos de até dez destaques. Produtos e UFs vêm dessa leitura, eliminando a segunda varredura da carteira. A leitura completa continua disponível no contrato existente da API. A autenticação e a verificação da empresa acontecem antes das consultas.
2. **Resumos da Agenda:** os contadores leem datas; o resumo da equipe lê operador e data. Observações e demais detalhes deixam de trafegar para montar apenas números.
3. **Requisições simultâneas repetidas:** o cliente central compartilha GETs iguais enquanto estão em andamento. A chave inclui token e parâmetros. Escritas e logout invalidam o compartilhamento. Não há cache persistente de resultados; uma consulta posterior continua buscando dados novos. Requisições com cancelamento próprio ficam independentes.
4. **Navegação:** passar o ponteiro ou focar um item do menu, uma aba ou um cartão do Início antecipa o código da página. A ação não consulta dados nem navega. Conexões com economia de dados/2G não antecipam. React.lazy e a antecipação usam os mesmos carregadores.
5. **Fundo e fonte:** desenho limitado a 24 fps, sem medir layout em cada quadro, com pausa na aba oculta e respeito a movimento reduzido. Redimensionamento e troca de tema ainda atualizam o desenho estático. Removida a importação duplicada da fonte no CSS; a fonte da marca permanece declarada no HTML.
6. **Transporte:** respostas do backend a partir de 1.000 bytes usam gzip quando o cliente aceita, com nível 4. Conteúdo JSON, autorização e CORS foram conferidos. Respostas pequenas, como health, não são comprimidas.

## Mapa da aplicação

Esta tabela resume a revisão de código das áreas e componentes compartilhados. Não representa uma medição autenticada individual de cada rota.

| Área | Situação encontrada | Ação / prioridade restante |
|---|---|---|
| Login, recuperação, troca de senha e privacidade | Rotas divididas; login e renovação dependem do servidor. Fonte externa declarada duas vezes. | Fonte corrigida. Confirmar plano real da hospedagem e medir login após inatividade. |
| Início | Artes em SVG local; menu e cartões solicitam o mesmo resumo. Carteira abre após listar a última análise e carregar seu resumo. | Compartilhamento de leitura e antecipação de código implementados. A dependência entre listar e abrir é real. |
| Navegação e layout de todas as páginas | Layout permanece montado; páginas já usam lazy loading. Fundo WebGL contínuo. | Antecipação por intenção e limite/pausa do fundo implementados. |
| Carteira / painel | Tabela paginada; abertura ainda buscava todas as colunas e relia produtos/UFs. | Corrigido o excesso de dados. Agregações ainda percorrem a carteira: próximo ganho é resumo calculado no banco ou persistido com invalidação confiável. |
| Importação / conexões | Processamento pesado já usa threads; importação e sincronização dependem de bancos externos. | Medir separadamente leitura externa, pontuação e gravação. Algumas validações síncronas ainda são chamadas diretamente em rotas async. |
| Detalhe / recuperabilidade | Carregamento dedicado do devedor, explicações, propostas e fluxo. | Medir a sequência real de chamadas antes de agrupar respostas; preservar atualização de ações. |
| Pastas | Página visual de 24 itens, busca com debounce; servidor cruza casos da empresa e destaques para ordenar as cores. | Principal risco de escala restante: muito trabalho para poucas pastas. Levar filtro/ordenação ao banco após verificar planos reais, sem perder contagens ou cores. |
| Agenda / operadores / administração | Contadores usavam linhas completas. Listas e tarefas são buscadas em paralelo onde possível. | Projeção de campos corrigida; regressões de acesso e ações aprovadas. |
| Agentes / perfis | Escritório consulta estação a cada 5 s e resumo a cada 15 s, sem sobreposição e pausando em aba oculta. Resumo pode ler até 5.000 passos. | Priorizar agregações de métricas no banco se a telemetria real mostrar custo alto. Estação pode consultar vários traces até encontrar conversa completa. |
| Resultados / equipe / acordos / performance | Resultados cruzam pagamentos, predições e contatos em lotes. Gráficos estão em chunks separados. Painel da carteira consulta status/pagamentos a cada 15 s. | Próxima rodada: tornar polling do painel sensível à visibilidade e sem sobreposição, e medir agregações por período. |
| Ofertas / política / usuários / auditoria | Formulários e listas em rotas próprias; alterações exigem dados atuais. | Compartilhamento de GETs beneficia o cliente central sem introduzir cache de permissões. Confirmar paginação e latência com volumes reais. |
| Simulação / laboratório / aprendizado / treino | Relatórios e cálculos custosos; Aprendizado dispara nove leituras paralelas. | Separar dados essenciais de abas sob demanda; avaliar trabalhador separado para treino/sincronização conforme utilização de CPU/RAM. |
| Comando / chaves / retenção / ajuda | Rotas separadas por papel; índices de consultas comuns já aparecem nas migrações. | Verificar migrações instaladas e planos de consulta antes de criar novos índices. |
| Exportações | Excel, PDF e captura de gráficos já usam importação dinâmica. | Preservar carregamento somente quando solicitado. XLSX ≈143 KB gzip, PDF ≈121 KB gzip e html2canvas ≈48 KB gzip não entram todos na entrada. |

## Hospedagem e próximos passos, em ordem

**1. Confirmar a infraestrutura em uso.** `backend/render.yaml` declara `plan: free`, região Oregon e um processo de servidor. Isso é evidência da configuração versionada, não confirmação da configuração atual no painel. O Render documenta que serviços gratuitos suspendem após 15 minutos sem tráfego e podem levar cerca de um minuto para retomar. O projeto possui pings periódicos, mas eles não equivalem a capacidade reservada ou garantia de disponibilidade. Para operação contínua, confirmar um serviço que permaneça ativo. Não houve alteração de plano nem contratação. [Documentação do Render](https://render.com/docs/free).

**2. Medir backend e banco na mesma operação.** Registrar duração por rota e por consulta, identificador da requisição e contagem de linhas, sem conteúdo de clientes. Comparar primeira abertura, retorno à página, p50/p95 e tempos de erro. Confirmar a região real do banco antes de planejar aproximação entre API e banco. Mudar a região no Render exige criar outro serviço; não é um ajuste instantâneo. [Regiões do Render](https://render.com/docs/regions).

**3. Tirar agregações grandes da abertura das páginas.** Priorizar resumo da carteira, resultados e métricas de agentes. Implementar agregação no banco ou resumo persistido atualizado nas escritas. Um cache genérico sem invalidação poderia mostrar pagamentos e permissões antigos; não foi usado.

**4. Escalar pastas e atualização periódica.** Investigar consulta paginada já ordenada por semáforo, com contagem no banco. Revisar polling do painel da carteira. Separar treino e integrações pesadas da API quando as medições demonstrarem disputa de recursos.

**5. Definir orçamento de desempenho.** Como objetivos de trabalho, medir conteúdo útil nas navegações em até 1 segundo com servidor acordado e rede de referência, e ausência de chamadas duplicadas. Esses valores são metas a validar, não resultados obtidos nesta revisão.

## QA e regressões

- `backend/test_otimizacao_paginas.py`: quatro testes; igualdade de respostas atuais/legadas, limite de hidratação completa, volume, autorização, projeção da Agenda, gzip e CORS.
- `frontend/tests/performance-api.test.mjs`: quatro testes; fonte, compartilhamento, falhas, invalidação, token e parâmetros.
- `frontend/tests/performance.ui.mjs`: navegador real com API fictícia; uma consulta do resumo, pré-carregamento por intenção sem dados, navegação, quadros por segundo, aba oculta, movimento reduzido e resize.
- Regressões existentes: Agenda, desfazer, ranking paginado, escopo de carteira, pastas, Agenda humana, ordem da fila e cliente HTTP.
- Build de produção aprovado. QA não alterou dados reais nem dependências de produção; bibliotecas necessárias ao servidor de teste foram instaladas em diretório temporário.

Execução: `python test_otimizacao_paginas.py` em `backend`; `npm run test:performance`, `npm run test:performance:ui` e `node test_api.mjs` em `frontend`. O teste de navegador segue as variáveis `MIZAN_PLAYWRIGHT_MODULE` / `MIZAN_BROWSER_CHANNEL` usadas pelas outras regressões de UI.
