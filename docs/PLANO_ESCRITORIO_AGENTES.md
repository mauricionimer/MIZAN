# Escritório dos agentes (topo da Central)

Pedido do Mauricio (17/10): ver cada agente e o que está fazendo, no estilo
"estação de agentes" em pixel art isométrica. Decisão: no topo da Central, com
botão de tela cheia para o pitch.

## O que foi feito

- Rota `GET /agente/estacao` (admin/comando): passos dos últimos 15 minutos da
  empresa e a última conversa inteira, já com quem agiu e a frase explicativa
  (`_passo_publico`). Diz quais agentes estão com IA ligada. Nunca o texto do
  devedor. Usa o índice existente `(empresa_id, criado_em)`: sem SQL novo.
- `frontend/src/components/EscritorioAgentes.jsx`: sala em SVG desenhada em
  código (sem arte de terceiros). Mesa e boneco para os 8 agentes; Travas é a
  catraca, Ferramenta é o arquivo, a porta "Equipe" acende quando o caso vai
  para uma pessoa; o Auditor levanta a placa da regra quando bloqueia.
  Atualiza a cada 5 s. Botão "Reproduzir última conversa" (1,2 s por passo).
  Clique num agente mostra os passos dele. Respeita "reduzir movimento"; a
  lista ao lado mostra o mesmo em texto.
- `_quem`: passos do grafo (receber, enviar, transferir...) passaram a ser do
  Orquestrador; antes apareciam como Travas.

## Verificação

`test_agente_estacao.py` (só passos da empresa, sem texto pessoal, janela),
suíte inteira, build e conferência visual com dados fictícios.
