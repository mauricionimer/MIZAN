# Cientista integrado ao aprendizado

Implementação em `backend/aprendizado/`, com as rotas `/agente/aprendizado` e painel no Laboratório. O Cientista tem um ciclo determinístico de dados, propostas, aprovação, execução e acompanhamento. A IA pode escrever o relatório, mas seu texto não produz rótulos de treinamento nem altera parâmetros por conta própria.

## Fluxo operacional

1. O agendador avalia cada empresa diariamente, conforme `SCHEDULER_INTERVALO_HORAS`. O botão **Avaliar dados para retreino** executa a mesma avaliação. Gerar a análise textual do Cientista também tenta criar uma proposta vinculada à recomendação.
2. A avaliação gera `coleta_dados` ou `retreino_score`, com justificativa, critérios, período, contagens, exclusões, hash da base e modelo de referência. Não há treino sem aprovação.
3. Admin da própria empresa ou COMANDO aprova/recusa. **Executar ação aprovada** inicia uma tarefa em segundo plano. Aprovar uma recomendação textual antiga continua tendo seu significado original: orientar o Estrategista, sem autorizar treinamento.
4. Antes de executar, o servidor refaz os critérios e o hash e confere o modelo ativo. Mudança de base, critérios, modelo ou vencimento de sete dias expira a proposta.
5. O treino reutiliza `treino_feedbacks.treinar` e `treino_empresa.treinar`: modelo de score e modelo de preço por empresa. O candidato nasce inativo, com métricas do teste temporal, comparação com o ativo e vínculo à ação.
6. Somente COMANDO ativa uma versão nas telas/rotas existentes. A ativação e a volta a uma versão anterior registram intenção e confirmação no histórico do Cientista. O monitor acompanha scores realmente emitidos pela versão, ligados a pagamentos confirmados após a ativação.

## Quando há dados suficientes

Os valores padrão são travas de engenharia; não representam garantia de poder estatístico:

- 300 pessoas distintas com resultado confirmado e vínculo predição–carteira–empresa.
- Pelo menos 30 pagamentos e 30 não pagamentos confirmados.
- 30 resultados novos desde o último treino com feedbacks (`SCHEDULER_MIN_FEEDBACKS` no agendador).
- Predição com pelo menos 30 dias. Não pagamento só é elegível se confirmado após essa janela (`CIENTISTA_MATURIDADE_DIAS`). Ausência de feedback nunca vira classe zero.
- Pelo menos 80% das observações recebidas elegíveis (`CIENTISTA_QUALIDADE_MINIMA`). O relatório informa exclusões por vínculo, identidade, data, maturidade, repetição ou variáveis inválidas.
- Uma predição por pessoa, escolhida pela data antes de olhar o alvo. Uma pessoa não aparece nos dois lados da validação.
- Teste nos 20% mais recentes, com fronteira ajustada para não dividir o mesmo dia. Ambas as classes precisam estar presentes.

A base inclui somente feedback explícito ligado a predições. A fração elegível mede a qualidade desse conjunto, não a cobertura de todos os devedores. Há risco de viés de resposta. Feedbacks anteriores à predição atual, inclusive após substituição de uma carteira, são excluídos.

AUC e Brier são comparados na mesma fatia quando possível. Se o ativo já viu o teste, a comparação é marcada como indisponível e o Cientista pede revisão. A proposta registra mínimos e tolerâncias; suspeitas de vazamento também exigem revisão. Nenhuma métrica ou selo autoriza promoção automática.

## Experimentos do bandit

O botão **Propor experimento do bandit** cria uma proposta separada, que também precisa de aprovação e execução. O experimento implementado compara o LinUCB atual com exploração 10% maior:

- Sorteio estável por empresa, experimento e pessoa, com dois grupos aproximadamente iguais. A recomendação inicial de cada pessoa fica registrada e é mantida durante o experimento.
- Não altera os parâmetros salvos do LinUCB nem os limites de negociação; atua apenas na seleção da recomendação. A aplicação continua sujeita às travas normais do produto.
- No máximo um experimento ativo por empresa, garantido por índice único no banco.
- Duração de 60 dias, permitindo observar os primeiros desfechos maduros antes do fim; o prazo é conferido em cada recomendação. Encerramento manual restaura imediatamente a seleção original. Os resultados reais já aprendidos não são apagados.
- Registro da recomendação, grupo, ação efetiva, aderência e resultado confirmado. Sem contato posterior à exposição, o pagamento não é atribuído ao experimento.
- O monitor exige maturidade de 30 dias e resultado explícito. Mostra pagamentos, recuperação/dívida, composição dos grupos, pendências, não aderência e intervalo de confiança.
- Com ao menos 30 resultados por grupo, um IC95% inteiramente abaixo de −5 pontos percentuais na taxa de pagamento interrompe o experimento. O monitor roda no agendador ou pelo botão **Atualizar acompanhamento**; não é monitoramento em tempo real.
- Após o encerramento, novos desfechos maduros continuam atualizando o relatório e sua auditoria. Não há expansão automática: resultados pedem nova revisão humana. O relatório não apresenta a amostra observada como prova causal.

O fechamento do aprendizado do bandit exige contato efetivamente registrado. Uma recomendação exibida isoladamente não é uma ação executada. Feedbacks têm identificador persistido no estado do bandit e são aplicados no máximo uma vez por ID, usando a mesma gravação com controle de versão. A rotina de reconciliação recupera observações experimentais a partir dos registros operacionais sem reaplicar recompensas.

## Auditoria e recuperação

`migracao_cientista_aprendizado.sql` cria:

- `cientista_acoes`: estado atual e relatórios por ação.
- `cientista_eventos`: histórico de cada transição, ator, motivo e fotografia do estado.
- `cientista_bases`: fotografia cifrada e imutável dos dados elegíveis, identificada por empresa e SHA-256.
- `cientista_exposicoes` e `cientista_resultados`: atribuições e observações imutáveis.

A criação da base, proposta e evento é transacional. Mudanças de estado e seus eventos também são transacionais. UPDATE/DELETE de eventos, bases, exposições e resultados são bloqueados por gatilhos. RLS e privilégios restringem as tabelas e RPCs ao backend; as rotas validam papel e empresa antes de acessar os dados.

O manifesto da base contém features, desfechos e identificadores pseudonimizados por HMAC, sem nomes, CPF ou contatos em claro. Os dados financeiros do manifesto são cifrados com `MIZAN_ENCRYPTION_KEY`. **Exportar base auditável** decifra apenas a base da empresa autorizada e verifica seu hash. O histórico de eventos guarda o hash e as contagens, sem repetir a base inteira a cada ação. A chave deve ser estável, protegida e incluída na estratégia de backup; sua perda impede ler as bases antigas.

Se a auditoria falha antes da execução, a ação não começa. Se o processo termina após gravar o modelo e antes de concluir o relatório, o vínculo `cientista_acao_id` permite concluir a auditoria sem retreinar. Uma execução interrompida sem artefato passa para erro na recuperação e exige nova tentativa explícita. A trava de treinamento vence após 120 minutos; uma execução ainda com a trava não pode ser retomada concorrente.

Falhas ficam no estado e histórico. A rotina pode ser tentada novamente sem duplicar a proposta do mesmo dia/base, o feedback ou a observação experimental. Uma falha de confirmação após ativação não significa que a versão deixou de ser ativada: verificar o estado atual e a intenção registrada antes de repetir.

O monitor do score compara resultados pós-ativação com as métricas de validação e recomenda revisão/rollback se AUC cair mais de 0,05 ou Brier subir mais de 0,05. Períodos e composições diferentes limitam essa comparação. Ele não troca o modelo automaticamente. Para rollback, COMANDO ativa a versão anterior ou desativa o próprio modelo para voltar ao global.

## Correções jurídicas incluídas

- Conferência por dispositivo: divergência em outro artigo não contamina os dispositivos explicitamente conferidos. Relatórios antigos sem lista completa não são presumidos corretos.
- Aceite: total, quantidade e valor das parcelas, além da entrada quando existir, precisam aparecer na mesma oferta posterior à simulação. Números espalhados em mensagens antigas não satisfazem o requisito. Simulações antigas sem data precisam ser refeitas.
- Falha ao gravar/cifrar a auditoria suspende autorizações e não fica no cache de seis horas. Nova consulta tenta registrar novamente. Contestação continua suspendendo a cobrança pelo fluxo de proteção existente.

## Habilitação em produção

1. Aplicar `backend/sql/migracao_cientista_aprendizado.sql` e depois `backend/sql/migracao_cientista_busca_segura.sql` no banco de produção por seu administrador, após backup. As migrações anteriores de agente, recomendações, modelos e travas devem existir.
2. Configurar uma chave Fernet válida em `MIZAN_ENCRYPTION_KEY` e preservar `MIZAN_DATA_DIR`/Storage dos modelos.
3. Publicar backend e frontend juntos. O agendador passa a propor, sem o retreino automático antigo. A migração ausente aparece como indisponibilidade; não autoriza intervenção experimental.
4. No Laboratório, conferir a empresa, gerar avaliação e verificar exclusões. Aprovar e executar uma proposta elegível; revisar o candidato no COMANDO antes de ativá-lo.
5. Verificar o histórico e o manifesto exportado, depois acompanhar os resultados no agendador ou pelo botão de atualização.

A implementação e os testes locais não aplicam migrações nem ativam modelos em produção.

## Testes

Backend: `python -m pytest test_cientista_aprendizado.py test_cientista_api.py test_correcoes_juridicas.py` a partir de `backend/`. Inclui treinamento real de candidato, erros, recuperação, isolamento, aprovação, sorteio, maturidade e idempotência.

SQL: executar a migração e `backend/test_cientista_sql.sql` em banco PostgreSQL descartável com os papéis `anon`, `authenticated`, `service_role` e tabela `recomendacoes`. Não rodar o teste em produção.

Interface: `node tests/cientista.ui.mjs` em `frontend/`, com Playwright instalado (`MIZAN_PLAYWRIGHT_MODULE` permite indicar uma instalação externa). O teste usa dados simulados e não acessa serviços externos.
