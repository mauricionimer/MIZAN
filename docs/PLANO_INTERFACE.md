# Interface mais simples e agentes exploráveis

Pedido do Mauricio (17/10): interface bem mais simples, organizada, com menos
texto e o essencial "na cara"; e poder explorar melhor os agentes.
Regra do plano: nenhuma tela é apagada nem perde função; muda o lugar, o nome
e a quantidade de texto. Rotas antigas continuam funcionando (redirecionam).

## Diagnóstico (levantamento do código, 17/10)

- Menu do admin com 13 itens em 3 grupos; nomes técnicos (Backtest, Premissas);
  sobreposição (Painel da equipe, Resultados, Acordos, Performance da IA);
  Agenda no menu e como aba do Agente.
- Agente.jsx: 6 abas + legenda + escritório + cartões; 18 parágrafos de
  explicação (as outras telas têm de 0 a 4).
- Agentes explicados em 3 lugares (legenda, rodapé do escritório, Ajuda).
- Dado técnico para o gestor: "US$ 0.0000", nome do modelo, "Versão 1".
- Cartões e títulos com o mesmo peso: nada mostra o que importa agora.

## Princípios

1. Uma pergunta por tela; a resposta em número; um botão para agir.
2. No máximo uma linha de subtítulo por tela. Explicação vai para um ícone
   "i" (dica ao passar o mouse) ou para a Ajuda.
3. Número formatado para gente: "R$ 1.234,56", "US$ 0,12 de 1,00 hoje".
   Nome de modelo e versão de prompt só no perfil do agente.
4. Um cartão = um número grande + um rótulo curto + (opcional) um detalhe.
5. Telas vazias: uma frase e um botão.

## Etapa A — Menu e agrupamento (1 PR)

Admin:
| Menu | Abre | Abas no topo da tela |
|---|---|---|
| Hoje | Agenda (renomeada), com 4 números em cima | — |
| Carteira | Análise de carteira (início atual) | Análise · Pagamentos |
| Agentes | Nova área (Etapa B) | Ao vivo · Conversas · Regras |
| Resultados | Resultados | Resultados · Acordos · Performance da IA · Laboratório |
| Configurações | Ofertas | Ofertas · Política de cobrança (Premissas) · Usuários · Auditoria · Simulação histórica (Backtest) |

Rodapé do menu: Ajuda, Alterar senha, Sair.
Operador: Hoje, Carteira (com Pagamentos), Meus acordos, Meu painel.
Comando: mantém o grupo "Comando" como está, abaixo dos 5 itens.

Como: um componente `AbasDaArea` no topo das telas de cada área, que marca o
item do menu certo. As páginas existentes continuam as mesmas.

## Etapa B — Área Agentes (1 PR)

- **Ao vivo** (`/agente`): 4 números (conversas hoje, acordos hoje, bloqueios
  hoje, gasto de IA do dia com barra do teto) + o Escritório grande + uma grade
  com os 8 agentes (cartão: nome, cor, IA ligada/código, ações hoje). Sai a
  legenda; o cartão e o boneco levam ao perfil.
- **Perfil do agente** (`/agente/<nome>`, novo): o que faz em uma linha; IA
  ligada, desligada ou código; modelo e versão do prompt; números das últimas
  24 h (decisões, bloqueios/reescritas, custo, tempo médio); últimas 20
  decisões com o motivo e o caso; "como ele é controlado" (o que o código
  confere nele, em 3 itens). Rota nova `GET /agente/agentes/{nome}` a partir
  dos passos (sem texto do devedor), com teste.
- **Conversas**: lista de casos à esquerda; conversa, caderno e passos à
  direita (o que hoje é a aba Conversa, sem os textos de ajuda).
- **Regras**: Política + Plano do dia + Rodar o relógio.
- Agenda sai do Agente (está em Hoje). Laboratório vai para Resultados.

## Etapa C — Texto e números (1 PR)

- Corta os parágrafos explicativos das telas de gestor para no máximo uma
  linha; o que for útil vira dica "i" (`Dica`, componente novo) ou vai para a
  Ajuda.
- Formatação: dinheiro, custo de IA (2 casas), datas relativas ("há 3 min").

## Etapa D — Acabamento visual (1 PR)

- Componentes únicos: `Numero` (cartão de número), `Etiqueta` (situação),
  `Vazio` (tela vazia). Aplicar nas telas das áreas acima.
- Um destaque de cor só (royal do Mizan); cores dos agentes só nos agentes.

## Verificação

Cada etapa: suíte inteira, build, conferência visual de cada tela mexida com
dados fictícios (mock local) e prévia da Vercel. Rotas antigas testadas
(redirecionam para o lugar novo). Nada de backend muda além da rota do perfil.

## Prazo

A e B: 18–19/10. C e D: 20–21/10. 22–23/10: congelar e ensaiar.
