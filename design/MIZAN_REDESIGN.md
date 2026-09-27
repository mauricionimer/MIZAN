# Mizan — Brief de redesign (handoff para Claude Code)

Este documento descreve o novo visual do Mizan (plataforma de inteligência de
carteira de crédito) para ser aplicado no código real. **Objetivo:** trocar a
interface atual pela nova identidade — paleta azul, tema claro/escuro, fonte
Bricolage Grotesque, cantos levemente arredondados, nova logo (gráfico
ascendente) e a tela de login em fundo azul cheio.

## Como usar
1. Coloque estes arquivos na raiz do repositório (ou em `/design`):
   `MIZAN_REDESIGN.md`, `mizan-tokens.css`, `MizanLogo.tsx`, `mizan-mark.svg`.
2. No Claude Code, rode algo como:
   > "Leia `MIZAN_REDESIGN.md` e aplique o redesign neste projeto. Primeiro
   > detecte a stack (Next.js? Tailwind? CSS Modules? shadcn/ui?), me diga o
   > plano de mudanças por arquivo e então implemente, mantendo a lógica e as
   > rotas intactas — mude só estilo, tokens, a logo e o layout do login."
3. Não altere lógica de negócio, chamadas de API, autenticação ou dados — **é
   um redesign visual.**

> Referência visual (protótipo aprovado, navegável, com todos os estados):
> abra o artifact "Mizan Protótipo" na sua conta claude.ai/code/artifacts.

---

## 1. Tokens de cor e base
Use **`mizan-tokens.css`** (incluído). Cole o conteúdo em `globals.css`.
Ele define, via CSS variables, a paleta em **3 estados de tema**:

- `:root` = tema claro (padrão)
- `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` = escuro do SO
- `:root[data-theme="dark"]` = escuro forçado pelo toggle

O toggle de tema deve setar/remover `data-theme="dark"` / `data-theme="light"`
no elemento `<html>` (e pode persistir em `localStorage`).

**Regra de ouro:** todo componente pega cor **dos tokens**, nunca hex fixo, pra
funcionar nos dois temas. Ex.: `background: var(--card); color: var(--text);
border: 1px solid var(--border-subtle);`

### Se o projeto usa Tailwind
Mapeie os tokens no `tailwind.config`:
```js
// tailwind.config.js -> theme.extend.colors
colors: {
  canvas: 'var(--canvas)', card: 'var(--card)', raised: 'var(--raised)', sunken: 'var(--sunken)',
  'border-subtle': 'var(--border-subtle)', 'border-strong': 'var(--border-strong)',
  ink: 'var(--text)', 'ink-2': 'var(--text-2)', 'ink-muted': 'var(--text-muted)',
  royal: 'var(--royal)', 'royal-hover': 'var(--royal-hover)', 'royal-soft': 'var(--royal-soft)',
  deep: 'var(--deep)', 'panel-ink': 'var(--panel-ink)', 'panel-2': 'var(--panel-2)',
  success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)',
  'on-brand': 'var(--on-brand)', 'accent-text': 'var(--accent-text)',
},
borderRadius: { DEFAULT: 'var(--radius)', lg: 'var(--radius-lg)' },
fontFamily: { sans: 'var(--font-sans)', display: 'var(--font-display)' },
```
Se usa **shadcn/ui**, sobrescreva as variáveis dele (`--background`,
`--foreground`, `--primary`, `--muted`, `--border`, `--ring`…) com estes valores
equivalentes, mantendo a convenção do shadcn.

---

## 2. Tipografia — Bricolage Grotesque (fonte única)
Uma família só em toda a interface: **Bricolage Grotesque** (Google Fonts).
Títulos, textos, botões, labels e **números** usam ela. Números usam
`font-variant-numeric: tabular-nums` (classe utilitária `.tnum`) pra alinhar
colunas de valores.

**Next.js (app router) — recomendado:**
```ts
// app/layout.tsx
import { Bricolage_Grotesque } from "next/font/google";
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", display: "swap" });
// no <html className={bricolage.variable}> …
```
E no CSS: `--font-display` e `--font-sans` já apontam para
`"Bricolage Grotesque", …`. Se usar `next/font`, troque para
`var(--font-bricolage), "Segoe UI", system-ui, sans-serif`.

**Alternativa (link):**
```html
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&display=swap">
```

> Removemos a fonte monoespaçada anterior. Não use Space Mono / Space Grotesk.

---

## 3. Cantos (raio)
Tudo **levemente arredondado**: use `--radius` (4px) em botões, inputs, cards,
chips, badges; `--radius-lg` (6px) em containers maiores/modais. Nada de pílulas
totalmente redondas nem cantos vivos. (Avatares/toggles podem ser 4px também.)

---

## 4. Logo
Nova marca: **gráfico ascendente** — três barras inclinadas subindo, em degradê
de azul (`#b8c0ee` → `#8f9be9` → `#5966d9`). Use **`MizanLogo.tsx`**
(`<MizanMark />` e `<MizanLogo />`) e **`mizan-mark.svg`**. Substitua o
logo/ícone atual em: login, top nav, sidebar do dashboard, favicon e qualquer
splash. SVG do símbolo (viewBox 30×30):
```html
<polygon points="6.5,15 11.5,15 9,27 4,27" fill="#b8c0ee"/>
<polygon points="13.5,9 18.5,9 16,27 11,27" fill="#8f9be9"/>
<polygon points="20.5,3 25.5,3 23,27 18,27" fill="#5966d9"/>
```
O wordmark "Mizan" é só a fonte Bricolage, peso 700, `letter-spacing:-.03em`.
Para o **favicon**, exporte o `mizan-mark.svg` (ou um PNG 512px do símbolo).

---

## 5. Componentes (specs em tokens)

**Botões** (`--radius`, fonte display peso 600):
- Primário: `background:var(--royal); color:var(--on-brand);` hover
  `var(--royal-hover)`, active `var(--royal-pressed)`.
- Secundário: `background:var(--card); color:var(--text); border:1px solid var(--border);`
  hover `border-color:var(--border-strong)`.
- Ghost: `background:transparent; color:var(--accent-text);` hover
  `background:var(--royal-soft)`.
- Destrutivo: `background:var(--danger); color:#fff` (no escuro, texto
  `var(--text)`/ink). Sempre confirmar antes de ação destrutiva.
- **Todo botão precisa de `color` explícito** (ver Nota importante no fim) e de
  foco visível (`box-shadow:var(--focus-ring)`).

**Inputs / selects**: `background:var(--sunken); color:var(--text);
border:1px solid var(--border-strong); border-radius:var(--radius); padding:12px 14px;`
foco → `border-color:var(--focus); box-shadow:var(--focus-ring);
background:var(--card);`. Erro → borda e texto de ajuda em `var(--danger)`.
Label em `var(--text-2)`, peso 600. Placeholder/ajuda em `var(--text-muted)`.

**Cards / painéis**: `background:var(--card); border:1px solid var(--border-subtle);
border-radius:var(--radius-lg); box-shadow:var(--shadow-sm|md); padding:20-24px.`

**Badges de status** (mapeamento fixo — não trocar os significados):
- Saudável/aprovado → `success` sobre `success-soft`
- Atenção/pendente → `warning` sobre `warning-soft` (**texto escuro se preenchido**)
- Risco/vencido → `danger` sobre `danger-soft`
- Em análise/info → `accent-text` sobre `royal-soft`
Sempre cor **+ texto** (nunca só cor).

**KPI tiles**: card + rótulo em maiúsculas pequeno (`var(--text-muted)`), número
grande com `.tnum`, ícone tingido no canto. Sem legendas descritivas embaixo do
número (foram removidas).

**Top nav e Sidebar**: fundo `var(--deep)` (azul-meia-noite no escuro,
azul-clarinho no claro — o token já é tema-aware). Texto em `var(--panel-ink)`,
secundário `var(--panel-2)`, hover `var(--panel-hover)`, item ativo com leve
tinta royal (`rgba(89,102,217,.24)`).

**Tabelas**: cabeçalho em maiúsculas pequeno `var(--text-muted)`; linhas com
divisor `var(--border-subtle)`; hover `var(--raised)`; números com `.tnum`;
valores monetários positivos podem usar `var(--success)`.

**Gráficos**: use `--chart-1..5`. Texto/eixos com `var(--text-muted)`; grade
`var(--border-subtle)`. Garanta legibilidade nos dois temas.

---

## 6. Tela de LOGIN (mudança de layout)
- Fundo **azul cobrindo a tela inteira**: `min-height:100dvh; background:var(--deep);`
  (deep = azul-meia-noite no escuro, azul-clarinho no claro). **Sem** o split
  metade-metade antigo e **sem** linhas/textura no fundo.
- **Desktop:** logo **grande à esquerda** (símbolo + "Mizan", ~clamp(56–96px)),
  card de login **à direita**, ambos centralizados verticalmente, largura máx.
  ~1060px. **Mobile (≤820px):** empilha — logo em cima (centralizada), card
  embaixo.
- Card: `background:var(--card)`, borda `var(--border-subtle)`, `--radius-lg`,
  `box-shadow:var(--shadow-lg)`, largura ~440px.
- Conteúdo do card: título "Entrar", campo E-mail, campo Senha (com botão
  mostrar/ocultar), link "Esqueci minha senha", botão primário "Entrar", link
  "Política de privacidade". **Removido:** subtítulo "Acesso restrito…" e todos
  os textos de marketing (headline + bullets) — esses vão pra slides, não pro
  app.
- Toggle de tema (sol/lua) no canto superior direito.

---

## 7. Limpeza de textos (aplicar em todo o app)
Remover as "frasinhas" descritivas de apoio que poluem: descrições embaixo dos
cards do Hub, legendas embaixo dos números dos KPIs, subtítulos de seção
redundantes e a nota "Cluster #… identificado por machine learning". Manter
dados funcionais (host de banco, "Sync há X min", datas, etc.).

---

## 8. Nota importante (bug real de tema)
`<button>` **não herda `color`** por padrão. Com o SO em modo escuro e a página
em tema claro, o texto de botões sem cor explícita sai **branco/invisível**.
Garanta `color: inherit` (ou `var(--text)`) em todo botão/elemento clicável
estilizado. Já incluí `button{ color:inherit }` no `mizan-tokens.css`, mas
verifique botões que resetam cor.

---

## 9. Checklist de aceite

Conferido contra o código em 27/09/2026; a coluna diz onde cada item está.

- [x] Tokens colados; toggle claro/escuro funcionando (via `data-theme` no `<html>`).
      → `src/context/ThemeContext.jsx` (sistema/claro/escuro), `src/components/ThemeToggle.jsx`.
- [x] Bricolage Grotesque em toda a UI; números com `tabular-nums`.
      → fonte em `index.html` e `--font-display`; utilitário `.tnum` em `index.css`.
- [x] Raio ~4px em botões/inputs/cards/badges.
      → `--radius:4px` / `--radius-lg:6px`, ligados a todo `borderRadius` do Tailwind.
- [x] Nova logo (gráfico ascendente) em login, nav, sidebar e favicon.
      → `src/components/Logo.jsx` e `public/favicon.svg`.
- [x] Login em fundo azul cheio, logo grande à esquerda, card à direita,
      empilhando no mobile; sem textos de marketing.
      → `.login-shell` usa `var(--deep)`; `.login-stack` é `space-between` e
      vira coluna abaixo de 820px.
- [x] Nav e sidebar em `--deep` com texto claro nos dois temas.
      → `.navbar-glass` / `.panel-surface` redeclaram `--text`/`--ink` para os
      tokens de painel no próprio escopo, então os descendentes invertem sem
      classe extra. Aplicado em 11 telas. O app não tem sidebar: o layout
      ficou em barra superior.
- [x] Botões com cor explícita (sem texto some no modo escuro do SO).
      → `.btn-primary` / `.btn-secondary` em `index.css`, com estados
      hover/active/focus-visible/disabled.
- [x] Nada de lógica/rotas/API alteradas — só visual.
      → o commit do redesign não toca `backend/` nem `src/services/api.js`.
- [x] Contraste AA de texto nos dois temas.

Ponta solta conhecida: `--bg-auth` (em `index.css`) ficou definido e sem uso —
o login passou a ler `--deep` direto.
