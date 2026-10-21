# Bento da Agenda da equipe

Aplicado somente à lista de agendas de **Agenda → Equipe**. A agenda individual, Minha agenda, as outras abas e os componentes KPI existentes mantêm seu comportamento.

O exemplo foi adaptado para os dados existentes: resumo de compromissos pendentes à esquerda e cartões clicáveis de cada agenda à direita. Os números, os prazos e as proporções das barras vêm de `equipe.operadores`, sem métricas ou imagens fictícias. O clique reutiliza a seleção de operador existente. Carregamento, erro e equipe vazia continuam controlados pela página.

## Arquivos e dependências

- Entrada compatível com o prompt: `frontend/src/components/ui/stats-bento.tsx`, exportação `StatsBento` e default.
- Implementação isolada: `frontend/src/components/ui/agenda-equipe-bento.tsx`.
- Demonstração com props reais: `frontend/src/components/ui/agenda-equipe-bento.demo.tsx`.
- Estilos exclusivos: `frontend/src/components/ui/agenda-equipe-bento.css`, todos com prefixo `agenda-equipe-bento`.
- Estilos e tokens globais existentes: `frontend/src/index.css`.
- React e Lucide já instalados. Nenhuma dependência nova, provider ou estado de dados adicional é necessário. Não há imagens nesse componente.

O caminho de UI deste projeto Vite é **`frontend/src/components/ui`**. Usar a pasta dentro de `src` evita duplicação na raiz do repositório e mantém os componentes no escopo do Tailwind. O Tailwind já está instalado e lê TSX; o Vite já compila TypeScript/TSX.

O projeto ainda usa páginas JSX, sem configuração completa do CLI shadcn nem checagem estática de TypeScript. A integração não altera a configuração global para respeitar o escopo de uma única aba. Para configurar esse fluxo posteriormente, execute na pasta `frontend`:

```sh
npm install -D typescript @types/react @types/react-dom
npx tsc --init --jsx react-jsx --module esnext --moduleResolution bundler --allowJs --noEmit
npx shadcn@latest init
```

Na inicialização do shadcn, mantenha os caminhos de componentes em `src/components` e `src/components/ui`, CSS em `src/index.css` e configure o mesmo alias `@/* → src/*` no TypeScript e no Vite. Essa inicialização deve ser revisada antes de aplicar, pois pode mudar estilos globais. O novo componente usa importações relativas, sem depender desse alias.

Em telas a partir de 768 px a composição tem seis colunas, seguindo a proporção do exemplo; no celular fica em uma coluna. Textos longos quebram sem truncar o nome. As cores usam os tokens existentes dos temas claro/escuro e da empresa. Todas as agendas são botões acessíveis por teclado, com descrição e foco visível.
