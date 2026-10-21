# Teste glass — Agenda da equipe

O componente `LiquidGlassCard` foi adaptado do código enviado para envolver somente os cartões da equipe em `Agenda.jsx`. A linha, os dados e a ação de abrir cada agenda continuam iguais. Nenhuma mudança foi aplicada a Meu painel, às demais abas ou à agenda individual.

Implementação TypeScript: `frontend/src/components/ui/liquid-weather-glass.tsx`. Estilos exclusivos: `frontend/src/components/ui/liquid-weather-glass.css`; os tokens de tema continuam em `frontend/src/index.css`. O filtro SVG tem identificador único por cartão, não recebe cliques e atua apenas atrás do conteúdo. Arrastar e expandir não entram neste teste para preservar o botão de navegação. Não há dados fictícios nem imagens.

React, clsx e Tailwind já estão instalados; o Vite já aceita TSX. Não é preciso adicionar `motion`, pois esta aplicação do efeito não usa animações de arraste ou expansão. O caminho correto neste projeto Vite é `frontend/src/components/ui`, dentro do diretório `src` lido pelo Tailwind, em vez de criar outra pasta na raiz.

Para configurar posteriormente checagem TypeScript e o CLI shadcn, execute em `frontend`:

```sh
npm install -D typescript @types/react @types/react-dom
npx tsc --init --jsx react-jsx --module esnext --moduleResolution bundler --allowJs --noEmit
npx shadcn@latest init
```

Mantenha os componentes em `src/components/ui`, estilos em `src/index.css` e o alias `@/*` apontando para `src/*` no TypeScript e no Vite. Essa configuração global não foi aplicada durante este teste restrito à Agenda; o componente usa imports relativos e as dependências existentes.
