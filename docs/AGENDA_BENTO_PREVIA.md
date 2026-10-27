# Prévia dos cartões proporcionais da Agenda

Aplicação restrita à lista da equipe em Agenda. Todos os cartões usam a mesma largura e altura, com mínimo de 340 px de altura, área visual de 200 px e faixa de conteúdo sobreposta, seguindo a composição do componente enviado. A grade tem uma coluna no celular, duas a partir de 640 px e três a partir de 900 px. Nomes longos quebram sem truncamento. O botão inteiro abre a agenda existente; os dados vêm do mesmo endpoint.

## Organização aprovada

- **Operadores**: abre a lista de operadores humanos e, depois, a agenda individual.
- **Demandas de agenda para administração**: reúne tarefas administrativas manuais e solicitações de atendimento/reunião aguardando o ADM. Permite criar, concluir e reabrir tarefas, além de escolher o operador, aprovar/atribuir ou recusar uma solicitação.
- **Atendimentos virtuais**: mantém os compromissos do responsável virtual e as três faixas de prazo existentes.

Os cartões externos não exibem “Agenda da equipe” nem as contagens de prazo. As três entradas ficam disponíveis mesmo sem pendências. A seleção de empresas por Comando permanece somente leitura.

## Persistência e aprovação

As tarefas manuais usam a tabela `agenda` existente: são retornos internos com `cpf` vazio e referências de cliente/carteira nulas. Não geram CPFs fictícios nem exigem migração de banco. Rotas específicas exigem administrador para escrever, isolam a empresa e identificam somente esses registros, impedindo tratar compromissos de clientes como tarefas. A conclusão/reabertura compara a situação esperada para detectar alterações concorrentes. Há paginação e auditoria. A interface não usa localStorage para guardar tarefas.

Novas reuniões solicitadas pela ferramenta `marcar_atendimento_humano` ficam com `a-definir`, inclusive quando o devedor já tem responsável. O agente informa que aguarda aprovação, não confirma a reunião. A atribuição pelo administrador, já protegida no backend e contra clique duplo, efetiva a aprovação. A resposta posterior do agente consulta a situação/data/hora atuais do compromisso, reconhecendo aprovação, recusa e conclusão. Não há envio novo de mensagens nesta implementação.

Compromissos anteriores não são reatribuídos retroativamente. Retornos virtuais e promessas comuns mantêm suas regras atuais.

## Validação

- Build do frontend.
- Compilação sintática dos arquivos Python alterados.
- Cinco testes de tarefas administrativas: permissão, empresa, gravação, conclusão/reabertura, concorrência, separação de clientes, validação e paginação.
- Onze testes de agenda humana, incluindo aprovação obrigatória mesmo com responsável, recusa e confirmação após atribuição.
- Regressão de disponibilidade dos operadores: nenhuma falha.
- O teste completo de passagem que importa `main` não foi executado até o fim: o runtime local não tem `uvicorn`/FastAPI instalados. Os testes puros de passagem anteriores à importação passaram; isso não equivale a um teste HTTP completo.

Esta mudança inclui backend e frontend: a publicação deve atualizar ambos antes da verificação autenticada das novas rotas. A prévia local demonstra interações sem gravar dados reais.

O `bento.tsx` existente já serve o Início e foi preservado. A nova exportação `AgendaBentoCard` aponta para `frontend/src/components/ui/agenda-bento-card.tsx`, com estilos exclusivos em `agenda-bento-card.css`. Os tokens globais continuam em `frontend/src/index.css`.

React, clsx, framer-motion, Lucide e Tailwind já estão instalados. O Vite compila TSX e o Tailwind lê essa extensão. A área visual é feita em CSS e usa a quantidade real de pendências; não exige fotos ou gráficos fictícios. A animação respeita a preferência de movimento reduzido.

Este projeto Vite usa `frontend/src/components/ui`, não uma pasta na raiz do repositório. Manter a UI dentro de `src` garante a compilação e leitura pelo Tailwind. Para configurar futuramente o CLI shadcn e a checagem estática TypeScript, execute em `frontend`:

```sh
npm install -D typescript @types/react @types/react-dom
npx tsc --init --jsx react-jsx --module esnext --moduleResolution bundler --allowJs --noEmit
npx shadcn@latest init
```

Use `src/components/ui` para os componentes e `src/index.css` para estilos; configure o alias `@/*` para `src/*` tanto no TypeScript quanto no Vite. Essa inicialização global não faz parte desta mudança visual restrita à Agenda, que utiliza imports relativos.

Build local validado com uma URL de API fictícia apenas para compilação. Publicação autorizada após avaliação visual. Os cartões externos preservam os links de acesso e não exibem as frases explicativas. A tipografia usa os tokens do MIZAN, com Bricolage Grotesque também na prévia.
