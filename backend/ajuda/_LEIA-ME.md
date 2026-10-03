# Como escrever ou mudar uma resposta da Central de Ajuda

Cada arquivo `NN-assunto.md` tem entradas começando em `## id-da-entrada`. O
formato está descrito no topo de `ajuda.py`. Regras que o teste
(`python test_ajuda_catalogo.py`) cobra:

1. **Fonte de verdade é o código.** Toda fórmula ou número citado vem de uma
   função ou constante, e ela entra em `fontes:` ou `constantes:`. Se o código
   mudar e o texto não, o teste quebra.
2. **Perfil.** `perfis:` nunca pode incluir quem não tem a tela de `telas:`.
   A tabela de telas por perfil (`TELAS` em `ajuda.py`) é conferida contra o
   `App.jsx` e os `isOperador` do `Dashboard.jsx`.
3. **Não prometa o que o sistema não faz.** Se o comportamento é uma decisão
   pendente, escreva o que o sistema faz hoje e marque `revisar:` citando o
   achado do `docs/MAPA_DO_SISTEMA.md`. Quando a decisão sair, a entrada muda.
4. **Linguagem do operador.** As `perguntas:` são jeitos reais de perguntar
   ("por que esse cara está no topo?"), não o nome técnico. Cinco ou mais, e
   nenhuma repetida em outra entrada.
5. **Honestidade.** Diga de onde o número vem: dado do cliente, modelo,
   premissa ou escolha de projeto. Se não tem fonte, diga que não tem.

Depois de mudar o código de uma métrica, rode o teste: ele aponta as entradas
que ficaram velhas.
