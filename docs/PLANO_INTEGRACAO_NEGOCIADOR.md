# Integração do Negociador — plano de execução

## 1. Cumprir retornos combinados

O relógio gera um evento `retorno_combinado` para compromissos que o assistente marcou. O evento conserva o ID, a data e a hora do compromisso. Antes de enviar, o Acompanhamento confirma que ele ainda está pendente e não foi remarcado, que o caso pode receber contato e que o Auditor autoriza a mensagem. Horário fora da janela é adiado. O texto retoma a conversa sem revelar a dívida.

**Aceite:** retorno devido gera uma mensagem; rodar o relógio de novo não duplica; remarcação e cancelamento impedem o envio antigo; atendimento humano e tarefas internas não viram retorno automático.

## 2. Ligar decisão a resultado

Uma decisão de abordagem recebe `decisao_id`. As simulações carregam esse ID, e a proposta só conta como apresentada quando a resposta correspondente foi gravada. O acordo preserva a simulação, a decisão e o compromisso de pagamento. O evento de baixa confirmado pelo banco liga o valor recebido ao compromisso. A trilha compacta fica em `agente_casos.dados.negociacao`; os passos completos continuam no rastreio existente.

**Aceite:** uma proposta apenas simulada não conta como apresentada; o pagamento informado pelo devedor não conta como recebido; o aceite e a baixa conservam o vínculo com a decisão original.

## 3. Persistir a etapa da negociação

O caso guarda uma etapa explícita (`identidade`, `entendimento`, `capacidade`, `oferta`, `aceite`, `retorno`). A etapa avança por ações verificadas e pelo envio de uma oferta, entra no briefing do Negociador e não depende de classificar livremente o texto do devedor. A política, o Auditor e a base jurídica continuam sendo as travas de negociação.

**Aceite:** o briefing mostra a etapa após reiniciar a conversa; a etapa não avança por uma ferramenta reprovada.

## 4. Medir desfechos reais

O Laboratório recebe um funil descritivo separado do experimento com grupo sorteado: decisões, propostas apresentadas, acordos aceitos, primeiro pagamento confirmado, quebras, retornos cumpridos e passagens para uma pessoa. O funil usa casos da mesma empresa, IDs únicos e pagamentos confirmados; não chama aceite de recuperação nem usa essas contagens como prova causal.

As contagens começam com os eventos registrados por esta implementação. Casos antigos permanecem disponíveis no fluxo anterior e não recebem vínculos retrospectivos inventados. O armazenamento usa o JSON do caso e as tabelas de rastreio já existentes, sem migração de banco.

**Aceite:** cada métrica é reproduzível a partir dos casos e das baixas, sem misturar empresas ou contar simulações nunca apresentadas.
