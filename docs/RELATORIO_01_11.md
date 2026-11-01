# Entrega quinzenal Mizan — 1 de novembro

**Período:** 18/10 a 01/11/2026  
**Repositório:** [github.com/mauricionimer/MIZAN](https://github.com/mauricionimer/MIZAN)

## 1. Metas

1. Evolução da cibersegurança
2. Conexão do Cientista com o ML
3. Integração com o Telegram e funcionamento do fluxo de conversa
4. Legislação

## 2. Cumprimento

As quatro metas foram cumpridas.

- **Cibersegurança:** fizemos 17 correções do plano de segurança, todas conferidas por uma
  prova automática que foi aprovada:
    - limite de tentativas de login;
    - senhas e chaves guardadas só em forma cifrada (hash);
    - sessão com prazo de validade;
    - servidor que só sobe com senhas fortes configuradas;
    - bibliotecas atualizadas, sem vulnerabilidades conhecidas.
- **Cientista e ML:** o agente Cientista passou a trabalhar junto com os modelos de machine
  learning, com cada passo registrado para auditoria:
    - todo dia, avalia se há dados reais suficientes;
    - propõe o retreino do modelo de score ou testes de ofertas;
    - só executa depois da aprovação de um administrador;
    - o modelo novo nasce desligado até alguém ativá-lo.
- **Telegram:** o devedor recebe um link pessoal, abre a conversa no Telegram e negocia com
  o agente no mesmo fluxo do chat do Mizan (triagem, negociação e travas de segurança).
  Quando preciso, um atendente assume a conversa pelo Mizan. Também:
    - as respostas ficaram mais rápidas (de 7 a 10 s para 5 a 6 s);
    - os agendamentos não se duplicam mais;
    - as telas passaram a se atualizar sozinhas.
- **Legislação:** criamos um RAG jurídico, uma base com LGPD, CDC, Cadastro Positivo e
  normas de crédito (1.348 artigos, parágrafos e incisos). O agente consulta essa base para
  conferir o que diz a lei antes de agir. Na dúvida, o caso vai para revisão humana, e cada
  consulta fica registrada com as leis usadas. Ele consulta, por exemplo:
    - antes de fechar um acordo;
    - antes de iniciar um contato;
    - quando a pessoa pede algo sobre os próprios dados.

## 3. O que impediu

Nada impediu as metas. Fica pendente conferir o texto das leis no site oficial do Planalto.

## 5. O que foi atualizado e feito

- **Segurança:** [PR #28](https://github.com/mauricionimer/MIZAN/pull/28) (29/10).
- **Cientista e aprendizado:** [PR #29](https://github.com/mauricionimer/MIZAN/pull/29) (31/10).
- **Canal Telegram e melhorias da conversa:** 27/10 a 31/10.
- **RAG jurídico do agente:** 31/10.
- **Outras melhorias:** novo visual (login, pastas e agenda), escritório dos agentes,
  desempenho e documentação.
