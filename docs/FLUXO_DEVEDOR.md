# Fluxo do devedor

Composição adaptada do `BuildPipeline` fornecido: cinco blocos isométricos conectados. A seleção de um bloco explica a fase, sem editar o caso. Tipografia e cores usam os tokens do MIZAN.

Entradas:

- Pastas: documento “Fluxo do devedor” e botão direto “Ver fluxo do devedor”. Os documentos anteriores continuam abrindo as conversas.
- Recuperabilidade: dentro da ficha aberta pela tabela, sem acrescentar uma coluna à fila.

## Regras confirmadas

1. Não iniciado.
2. Contactado.
3. Negociando.
4. Acordo.
5. Pagamento em andamento: exige pagamento positivo no registro `dados.pagamentos` do Acompanhamento, feedback com baixa confirmada ou parcela marcada paga. `pagamento_informado`, contato com resultado “pagou” e `pagamento_em_conferencia` não confirmam pagamento.

Quitação, atraso e quebra são avisos, mantendo as cinco fases. Contestação, suspensão, atendimento pela equipe e conferência também preservam a situação real como aviso, sem virar uma sexta fase.

`agente/fluxo.py` reúne o caso dos agentes com contatos, ofertas, feedbacks e parcelas da operação. Contatos são isolados por empresa e CPF; informações financeiras, por empresa e predição. Tentativa sem resposta não avança. Promessa sem aceite mantém negociação. Oferta aceita ou acordo registrado indica acordo. A situação de parcelas usa a regra existente em `acordos.py`, sem criar outro prazo de atraso ou quebra.

Na leitura, não há gravações nem execução de agentes. Sem atendimento registrado nas fontes disponíveis, o fluxo começa em não iniciado. Planejamento de lembrete sem mensagem não prova contato. Quando faltam registros ou fontes para identificar a fase, a interface informa que ela não está identificada. Divergências sem uma progressão cronológica coerente pedem decisão do operador. Não há datas históricas ou etapas concluídas fabricadas.

“Definir fase” grava a escolha explícita da operação em `agente_casos.dados.fluxo_manual`, preservando os outros dados e a situação usada pelos agentes. Se necessário, cria somente o registro do caso, sem mandar mensagens ou iniciar trabalho remoto. Há trava concorrente e auditoria. Somente operador/admin da própria empresa pode escrever; Comando consulta. A quinta fase exige comprovação também no servidor. A escolha prevalece sobre atualizações automáticas até a operação selecionar “Automático”. Os avisos financeiros continuam visíveis. Não há migração de banco.

A API consulta o caso dentro da empresa da carteira, após verificar a autorização sobre a carteira. A consulta não depende da carteira mais recente nem usa apenas CPF. A ficha em memória sem id resolve a linha no ranking salvo e confere posição e CPF antes de consultar o caso.

Atualização ao abrir, ao voltar o foco, após registros locais de atendimento/agenda e a cada 30 segundos com a página visível. Erros mantêm a última consulta identificada como desatualizada; nunca são apresentados como ausência de atendimento. Requisições antigas não substituem o devedor atual.

## Componentes e dependências

O projeto já tem React, Tailwind, Lucide e compilação TSX com Vite. O caminho utilizado é `frontend/src/components/ui/build-pipeline.tsx`, dentro de `src`, com CSS próprio ao lado; os estilos globais ficam em `frontend/src/index.css`. Não há dependência nova nem necessidade de fotos. O componente foi adaptado à cobrança: não inclui comandos de deploy, simulação de progresso, tempos ou logs fictícios do exemplo técnico.

Para configurar o CLI shadcn futuramente, execute `npx shadcn@latest init` em `frontend`, selecionando `src/components/ui` e `src/index.css`. O alias `@/*` deve apontar para `src/*` tanto no Vite quanto no TypeScript caso seja adotado. A integração usa imports relativos e preserva a estrutura existente.

## Verificação

Vinte testes de projeção, fontes manuais, isolamento, permissão, trava concorrente, persistência da escolha e integração com o grafo real de pagamento; regressão de Acompanhamento; compilação Python; build Vite; teste local no navegador com dados fictícios cobrindo abertura pela pasta, teclado, ficha sem id, atualização, decisão manual, retorno ao automático, erro de consulta, tema claro e largura de 320 px. Nenhum dado real foi alterado pelos testes.
