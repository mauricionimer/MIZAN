# Business Model Canvas - Mizan

**Versão:** outubro de 2026

**Status:** hipótese de modelo de negócio para validação comercial. O Mizan ainda não possui cliente pagante nem piloto concluído.

**Leitura por IA:** os blocos abaixo usam nomes estáveis, premissas explícitas, unidades e critérios de validação. Não trate hipóteses ou cenários como resultado comprovado.

## Resumo semântico

| Campo | Valor |
| --- | --- |
| Produto | Plataforma SaaS para inteligência e operação de recuperação de crédito. |
| Cliente que paga | Instituição credora ou operação de recuperação contratante. |
| Usuários | Gestor de recuperação, operador, administrador, risco, jurídico e segurança. |
| Unidade de valor | Dinheiro recuperado, custo operacional evitado, qualidade da decisão e controle de risco. |
| Unidade de cobrança | Assinatura mensal, uso por carteira/casos/interações de IA e serviços de implantação. |
| Limite de escopo | O Mizan é software. Não é credor, assessoria de cobrança nem decide ações fora da política aprovada. |
| Evidência atual | Protótipo funcional e testes internos. Sem piloto concluído ou receita comprovada. |

## 1. Segmentos de clientes

- Bancos pequenos e médios.
- Cooperativas de crédito.
- Financeiras e empresas de crédito.
- Gestoras de carteiras e operações de recuperação que atendem essas instituições.

**Comprador econômico:** gestor de recuperação de crédito.

**Influenciadores e aprovadores:** tecnologia, risco, jurídico, segurança, dados e compras.

**Usuários operacionais:** administradores, operadores e analistas de carteira.

## 2. Proposta de valor

O Mizan ajuda instituições financeiras a recuperar crédito com mais foco, controle e evidência. A plataforma analisa a carteira, prioriza casos, recomenda a próxima ação e oferta, organiza o trabalho de operadores e acompanha promessas, acordos e pagamentos.

Os agentes de IA executam atividades dentro das políticas da instituição. O sistema registra decisão, custo, latência, exceção e encaminhamento para humano.

**Resultado esperado, ainda sujeito a piloto:**

- aumentar dinheiro efetivamente recebido com a mesma equipe;
- reduzir contatos improdutivos;
- reduzir tempo operacional para priorização e registro;
- reduzir acordos quebrados por meio de acompanhamento;
- aumentar controle, auditoria e aderência à política de cobrança.

## 3. Canais

- Venda consultiva direta para gestores de recuperação e operações de crédito.
- Backtest ou prova de valor com carteira histórica e dados controlados.
- Piloto com grupo de comparação para medir resultado incremental.
- Parcerias de integração e indicação com provedores usados pelo cliente.

## 4. Relacionamento com clientes

- Diagnóstico inicial da carteira e configuração das políticas de cobrança.
- Implantação assistida para importação ou integração de dados.
- Painel para gestores, fila e agenda para operadores e trilha de auditoria.
- Suporte operacional e governança dos agentes com autonomia escolhida pela instituição.
- Revisões periódicas de resultado, custo por negociação, falhas e qualidade.

## 5. Fontes de receita

- Assinatura mensal da plataforma, por instituição ou operação.
- Uso variável conforme volume contratado: carteira ativa, casos acompanhados ou interações de IA.
- Serviços de implantação e integrações específicas, quando necessários.
- Bônus vinculado a ganho comprovado em piloto, apenas se o contrato preservar o posicionamento de software.

**Regra de posicionamento:** o modelo evita comissão sobre valor recuperado como padrão. O Mizan é ferramenta da instituição, não assessoria de cobrança.

## 6. Recursos-chave

- Plataforma web de carteira, agenda, acordos, resultados e configurações.
- Modelos de predição, recuperabilidade, recomendação e regras de política.
- Orquestração de agentes, trilhas de auditoria, logs de custo e latência.
- Integrações com dados e canais da instituição.
- Equipe de produto, engenharia, dados, segurança, implantação e sucesso do cliente.

## 7. Atividades-chave

- Conectar e organizar dados de carteira, pagamentos, acordos e agenda.
- Gerar prioridades, recomendações e simulações de oferta.
- Operar o fluxo de agentes: triagem, estratégia, negociação, auditoria e acompanhamento.
- Medir acordos cumpridos, dinheiro recebido, custo e qualidade de cada decisão.
- Garantir segurança, LGPD, políticas versionadas e rastreabilidade.

## 8. Parceiros-chave

- Provedores de nuvem, banco de dados e observabilidade.
- Provedores de modelos de IA e infraestrutura de inferência.
- Sistemas e canais usados pelo banco, como mensageria, discadores e pagamentos.
- Consultorias, integradores e assessoria jurídica especializada, quando necessários.

## 9. Estrutura de custos

- Desenvolvimento, produto, dados, segurança e suporte.
- Infraestrutura de nuvem, armazenamento e observabilidade.
- Uso de IA por negociação, com limites e medição de custo.
- Implantação, integrações, treinamento e sucesso do cliente.
- Vendas consultivas, conformidade e jurídico.

## Modelo de valor financeiro em reais

O Mizan só poderá afirmar valor realizado depois de um piloto com linha de base e grupo de comparação. Antes disso, use as fórmulas abaixo para apresentar **valor potencial mensurável**.

| Métrica | Fórmula | Unidade | Interpretação |
| --- | --- | --- | --- |
| Valor recuperado incremental | `carteira_em_atraso_brl * (taxa_recuperacao_tratamento - taxa_recuperacao_base)` | R$ | Dinheiro adicional recebido pelo grupo tratado em comparação com a linha de base. |
| Economia operacional | `horas_evitadas * custo_hora_operacao` | R$ | Custo evitado por priorização, registro e acompanhamento mais eficientes. |
| Benefício bruto | `valor_recuperado_incremental + economia_operacional` | R$ | Valor financeiro antes dos custos da solução. |
| Investimento total | `mensalidade + uso_ia + canais + implantacao_rateada` | R$ | Custo do Mizan e dos serviços necessários à operação. |
| Benefício líquido | `beneficio_bruto - investimento_total` | R$ | Valor econômico após custos. |
| ROI | `beneficio_liquido / investimento_total * 100` | % | Retorno sobre o investimento. |

### Cenário ilustrativo

Se uma carteira em atraso é de **R$ 2.000.000** e um piloto demonstra ganho de **1 ponto percentual** na taxa de recuperação em relação à linha de base:

`R$ 2.000.000 * 0,01 = R$ 20.000`

O resultado seria **R$ 20.000 de recuperação incremental** no período medido, antes de custos. Este número é exemplo de cálculo, não promessa comercial nem resultado já obtido pelo Mizan.

## Dados mínimos por piloto

| Campo | Tipo / unidade | Uso |
| --- | --- | --- |
| `carteira_em_atraso_brl` | R$ | Base do potencial recuperável. |
| `taxa_recuperacao_base` | % | Linha de base do grupo de comparação. |
| `taxa_recuperacao_tratamento` | % | Resultado do grupo apoiado pelo Mizan. |
| `valor_recebido_brl` | R$ | Medição de recuperação efetiva. |
| `horas_operacionais` | horas | Cálculo de produtividade e economia. |
| `custo_hora_operacao` | R$/hora | Conversão da economia em reais. |
| `custo_ia_brl` | R$ | Custo por uso de IA. |
| `custo_canais_brl` | R$ | Mensageria, telefonia e outros canais. |
| `acordos_cumpridos` | quantidade e % | Qualidade do resultado, não apenas acordo firmado. |
| `transferencias_humanas` | quantidade e % | Carga residual e motivo de escalonamento. |

## Plano de validação

1. **Backtest controlado:** importar carteira histórica, revisar qualidade dos dados e estabelecer linha de base.
2. **Piloto com política aprovada:** configurar usuários, alçadas, autonomia e canais.
3. **Grupo de comparação:** comparar casos tratados e não tratados em condições equivalentes.
4. **Revisão financeira e operacional:** medir valor recebido, benefício líquido, ROI, custo por negociação, acordos cumpridos, produtividade, falhas e repasses para humano.
5. **Decisão de escala:** só ampliar autonomia, preço e volume após resultado mensurável e aceite de risco, jurídico e segurança.

## Hipóteses e critérios de validação

| Hipótese | Evidência necessária | Critério de decisão |
| --- | --- | --- |
| O cliente aceita assinatura e uso. | Entrevistas, proposta comercial e piloto. | Custo por negociação transparente e aceitável ao comprador. |
| Há ganho financeiro. | Grupo de comparação e recebimento efetivo. | Benefício líquido positivo após todos os custos. |
| A autonomia pode aumentar. | Histórico de decisões, auditoria e incidentes. | Política atendida e exceções sob controle. |
| A integração é viável. | Importação, mapeamento e testes de segurança. | Dados, LGPD e canais aprovados pela instituição. |
| O fluxo é sustentável. | Latência, custo de IA, qualidade e satisfação operacional. | SLA e custo operacional compatíveis com o contrato. |
