# Plano de evolução do harness de qualidade dos agentes

**Status:** backlog estratégico. Não iniciar sem priorização explícita após validação do fluxo atual.

## Objetivo

Garantir que cada mudança nos agentes do Mizan preserve ou melhore a qualidade da negociação, a segurança, a aderência à política e a experiência de atendimento. Uma integração de modelo de IA só pode avançar quando o harness demonstra que a mudança é segura e traz benefício mensurável.

## Base que já existe

- Bateria de cenários simulados para conversas e fluxos.
- Auditor e guardrails para impedir ações fora da política.
- Logs com trace ID, duração, custo, tokens, erro e motivo de transferência.
- Checkpoints, retentativas, controle de duplicidade e encaminhamento para humano.
- Testes de regressão para agentes e fluxos críticos.

## Lacunas prioritárias

1. **Base de avaliação anonimizável**
   - Conversas reais ou representativas, sem dados pessoais.
   - Rótulos: aprovado, aceitável, reprovado e motivo da avaliação.
   - Cobertura de negociação, contestação, promessa de pagamento, recusa, vulnerabilidade e pedido de atendimento humano.

2. **Avaliação automática por versão**
   - Toda alteração de prompt, ferramenta, política ou modelo executa a mesma base de cenários.
   - Comparar versão candidata contra versão de referência.
   - Bloquear publicação se piorar critérios mínimos definidos.

3. **Aprovação humana configurável**
   - Aprovação obrigatória para descontos, acordos, exceções de política e ações sensíveis.
   - Registro de quem aprovou, contexto, decisão e motivo.
   - Fila de revisão para casos de baixa confiança.

4. **Painel de qualidade**
   - Qualidade da resposta por versão do agente.
   - Tempo de resposta, custo, falha, transferência humana e acordo cumprido.
   - Recuperação incremental e custo por negociação quando houver piloto com dados reais.

5. **Portões de qualidade**
   - Não publicar versão que aumente transferências indevidas, violações de política, falhas ou latência além do limite.
   - Não aumentar autonomia sem evidência de qualidade e aprovação de risco, jurídico e operação.

## Métricas iniciais

| Métrica | Como calcular | Direção desejada |
| --- | --- | --- |
| Taxa de resposta aprovada | respostas aprovadas / respostas avaliadas | aumentar |
| Transferência indevida | transferências classificadas como evitáveis / transferências | reduzir |
| Violação de política | violações detectadas / interações | reduzir para zero |
| Latência por resposta | tempo entre evento e resposta final | reduzir |
| Custo por negociação | custo de IA e infraestrutura / negociações | controlar |
| Taxa de acordo cumprido | acordos pagos / acordos firmados | aumentar |
| Recuperação incremental | resultado do grupo tratado - linha de base | validar em piloto |

## Ordem recomendada

1. Construir a base de cenários e os rótulos de qualidade.
2. Criar comparação automática entre versão candidata e referência.
3. Definir portões de publicação e aprovação humana.
4. Exibir o painel de qualidade para operação e administração.
5. Calibrar métricas com piloto e dados reais anonimizados.

## Regra de decisão

O Mizan não deve chamar uma nova versão de agente de “melhor” apenas porque responde mais rápido ou parece mais natural. Ela precisa manter a política, reduzir erro, preservar a experiência do devedor e gerar resultado operacional mensurável.

