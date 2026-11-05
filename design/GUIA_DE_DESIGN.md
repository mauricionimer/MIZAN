# MIZAN — Guia de design para quem vai criar telas (pessoas e LLMs)

Leia este guia **antes** de criar ou mudar qualquer tela do MIZAN. Ele vale para
pessoas e para assistentes de código (Claude, Codex, Copilot etc.). O brief visual
original (paleta, fonte, logo, login) está em `design/MIZAN_REDESIGN.md`; este guia
cobre o resto: como uma tela do MIZAN pensa, se organiza, anima e se testa.

> Regra que resume tudo: **cada coisa na tela ajuda alguém a decidir o que fazer
> agora.** Se não ajuda, sai da tela, vira detalhe a um clique ou muda de forma.

---

## 1. O produto e quem usa

O MIZAN é uma plataforma de inteligência para carteiras de crédito em atraso.
Ela pontua cada devedor (score de recuperabilidade), monta a fila de cobrança,
precifica a carteira e opera agentes de IA que conversam com os devedores.

| Papel | O que vem fazer | Pergunta típica |
|---|---|---|
| **Operador** | cobrar os devedores da sua fila | "Quem eu chamo agora e o que ofereço?" |
| **Admin** (gestor da empresa) | acompanhar a operação e a equipe | "A carteira está rendendo? O que precisa de mim?" |
| **Comando** (equipe MIZAN) | cuidar de todas as empresas, modelo e agentes | "Qual empresa precisa de atenção? O modelo acerta?" |

O Comando escolhe a empresa antes de ver dados dela (um `<select>` "Escolha a
empresa…" no cabeçalho). Tela de operador nunca mostra números de outra fila.

---

## 2. Stack e onde as coisas moram

- **Frontend:** React 18 + Vite 6 + Tailwind, `framer-motion`, `lucide-react`,
  `recharts` (só onde ainda não foi trocado pelas peças de `graficos.jsx`).
- **Rotas:** `frontend/src/App.jsx`; páginas carregadas sob demanda via
  `frontend/src/lib/paginas.js`. Toda página logada usa `<AppShell>`.
- **API:** sempre por `frontend/src/api.js` (`pedir(caminho, {query, metodo, corpo})`).
  Nunca use `fetch` solto numa página nova.
- **Backend:** FastAPI em `backend/main.py` (Supabase). Agentes em `backend/agente/`.

---

## 3. Cor, tipo e forma: só tokens

Os tokens estão em `frontend/src/index.css` (claro em `:root`, escuro em
`[data-theme="dark"]` e no `prefers-color-scheme`). **Nunca escreva hex solto em
componente.** Use as classes do Tailwind ligadas aos tokens ou `var(--token)`.

| Uso | Tailwind | CSS |
|---|---|---|
| Fundo da página / cartão | `bg-surface`, `bg-raise-1/2/3` | `var(--canvas)`, `var(--card)`, `var(--raised)` |
| Texto principal / apoio / fraco | `text-ink`, `text-ink-2`, `text-ink-3` | `var(--text)`, `var(--text-2)`, `var(--text-muted)` |
| Borda | `border-line` | `var(--border)` |
| Marca / ação | `bg-royal`, `text-accent-text` | `var(--royal)`, `var(--accent-text)` |
| Estado | — | `var(--success)`, `var(--warning)`, `var(--danger)` |
| Com opacidade | — | `rgb(var(--c-royal) / 0.12)` (também `--c-success`, `--c-warning`, `--c-danger`) |
| Séries de gráfico | — | `var(--chart-1)` … `var(--chart-5)` |

- **Cor tem dois trabalhos só:** identidade (qual série é qual) e estado
  (verde = bom/pago, âmbar = atenção, vermelho = problema). Nunca decoração.
  Estado sempre vem com texto ao lado, nunca só a cor.
- **Fonte:** Bricolage Grotesque, uma família só. Números com `tabular-nums`.
- **Texto mínimo:** 11 px (rótulos curtos em caixa alta); corpo 13–14 px.
- **Botões:** `btn-primary` (um por tela), `btn-secondary`, `btn-ghost`,
  `btn-danger`, tamanho menor com `btn-sm`. Alvo mínimo de 40 px de altura.
- **Exceção conhecida:** a "Sala dos Agentes" (`components/escritorio/`) tem
  paleta própria de pixel-art em hex. Não espalhe esse estilo para fora dela.

### Logo

- Arquivos oficiais em `design/logo/`:
  - `mizan-logo-escuro.svg`: palavra em `#f4f2fa`, para fundo escuro;
  - `mizan-logo-claro.svg`: palavra em `#1a0033`, para fundo claro;
  - `mizan-simbolo.svg`: só as barras.
- As duas versões da logo só mudam a cor da palavra. As barras são sempre `#b8c0ee`, `#8f9be9` e `#5966d9`.
- No app, use `components/Logo.jsx`:
  - `<LogoCompleto />`: barras + palavra desenhada, com a cor da palavra vinda de `currentColor` (por exemplo `text-ink`);
  - `<LogoMark />`: só as barras, para ícone ao lado de um nome.
- **Nunca escreva "Mizan" em texto para fazer de logo.**
- Onde a marca aparece hoje:
  - login;
  - "Esqueci a senha" e "Redefinir senha";
  - topo e menu (logo completa quando não há empresa cliente; com empresa cliente, o símbolo e o nome dela);
  - favicon;
  - cabeçalho do PDF (barras desenhadas);
  - e-mails (barras em tabela HTML, porque cliente de e-mail não mostra SVG).

---

## 4. Moldura da tela: o cabeçalho padrão

Toda tela usa `components/CabecalhoPagina.jsx`, e **nenhuma página tem `<h1>`
próprio** (o teste-guarda em `frontend/tests/ux-auditoria.test.mjs` falha).

```jsx
<CabecalhoPagina rotulo="Cobrança" icone={Handshake} titulo="Acordos" ajuda="acordos-em-andamento"
  subtitulo="Acordos parcelados: o que vence nos próximos dias e quem parou de pagar.">
  {/* ações à direita: seletor de empresa, exportar, atualizar */}
</CabecalhoPagina>
```

- `voltar` padrão é `← Início`. Em telas de detalhe, passe para onde a pessoa
  veio: `voltar={{ to: '/pastas', rotulo: 'Pastas' }}` (ou `location.state.de`).
  **A pessoa nunca fica sem saída.**
- `titulo` = o mesmo nome do item do menu.
- `subtitulo` = uma frase dizendo para que a tela serve, do lado de quem usa.
- `ajuda` = id de uma entrada da Central de Ajuda (`backend/ajuda/*.md`, `## id`).
  O "?" só aparece se o perfil logado puder ver aquela entrada.
- Dentro de um pai com `space-y-*`, passe `className="!mb-0"`.

Cada tela que carrega dados tem os **5 estados**: carregando (skeleton no
formato do conteúdo, nunca zeros falsos), vazio (por que está vazio + o próximo
passo), erro (`components/ErroCarga.jsx`, com "Tentar de novo"), sem permissão,
e o conteúdo.

---

## 5. Texto (pt-BR)

- Fale do lado da pessoa: "Quem pagou", não "Métricas de conversão".
- Botão diz o que acontece: "Abrir pasta", "Registrar pagamento", "Manter minha conta".
- Toda frase de apoio responde "e daí?": "trazem R$ 7,3 milhões", "compare com o custo de cobrar um caso".
- Sem jargão de sistema no texto principal (nomes de tabela, códigos como
  `oferta_desfeita`, `sofrimento_grave`). Se o conceito é necessário, explique numa linha.
- Moeda, número e data sempre em `pt-BR` (`Intl.NumberFormat('pt-BR', …)`).
- Número zerado nunca fica mudo: diga por quê.

---

## 6. Movimento

As animações moram em `frontend/src/components/graficos.jsx`. **Use estas peças;
não invente animação nova numa página.**

| Peça | O que faz | Use para |
|---|---|---|
| `BarraH` | barra fina que cresce até o valor (`listrada` = amostra pequena) | proporções, progresso, partes de um todo |
| `Contador` | número que conta até o valor | o número herói de um cartão |
| `Regua` | ponto que desliza de "antes" (○) para "agora" (●) | traços do perfil do cliente, antes × depois |
| `Medidor` | segmentos que acendem até o nível | saúde de um serviço (Ajuda › Estado da plataforma) |
| `LinhaDesenhada` | linha de SVG que se desenha na ordem do tempo | curvas e séries (fila de cobrança) |
| `Ponto` | "pop" de uma bolinha | uma bolinha por resultado (Quem pagou) |
| `Aparece` | bloco que sobe e aparece ao entrar na tela | seções e cartões |

Regras:
1. **O movimento explica.** A barra cresce até o valor; a linha se desenha da
   esquerda (passado) para a direita (agora). Nada gira, pisca ou pulsa sem motivo.
2. **Roda uma vez**, quando a peça entra na tela (`useInView` com `once`).
3. **Movimento reduzido:** com `prefers-reduced-motion`, tudo nasce pronto.
   As peças já fazem isso; CSS próprio precisa de `@media (prefers-reduced-motion: reduce)`.
4. Duração de 0,5 a 1,4 s, saída suave (`[0.22, 1, 0.36, 1]`). Em série, atraso de 0,1 a 0,25 s entre itens.
5. Anime `transform`/`opacity` (ou `pathLength`), nunca `width/height/top` em loop.

---

## 7. Gráficos

1. **O título é a resposta, não o nome do gráfico.**
   - Errado: "Aging da carteira".
   - Certo: "96% do que dá para recuperar está nos primeiros 90 dias".
   - A frase é calculada dos mesmos dados do gráfico, numa função pura. Exemplos: `parteAte90`, `fraseQuemPagou` em `components/PainelCarteira.jsx`.
2. Um gráfico por pergunta. Repertório usado no MIZAN:
   - quanto de um total → barra com trilho (trilho = face, cheio = esperado);
   - até onde vale → curva acumulada com cortes clicáveis (10/20/30/50%);
   - partes de um todo → barras empilhadas com legenda; **sem pizza**;
   - resultados contáveis → uma bolinha por resultado (cheia = pagou, vazada = não pagou);
   - conta em etapas → cascata (esperado − custo − retorno = preço máximo);
   - saúde → medidor em segmentos.
3. Uma escala por gráfico, sem eixo duplo, grade tracejada fraca e rótulo só no que importa.
4. Duas ou mais séries: a identidade nunca depende só da cor, use legenda ou rótulo direto.
5. `role="img"` + `aria-label` com os números em todo gráfico.
6. **Número exato vem do servidor.** O desenho pode ser amostrado (a curva tem 40 pontos), mas o valor de um corte vem da rota que soma de verdade (`/alcance`).

---

## 8. Honestidade dos dados

- **Não afirme o que não mediu.** Serviço sem dado aparece como "sem medição", em
  cinza, nunca como verde. Veja `backend/plataforma.py` e `components/EstadoPlataforma.jsx`.
- Amostra pequena se anuncia ("Cada bolinha são 3 resultados", barra `listrada`).
- Dado de análise antiga sem um campo novo: mostre o que dá e diga como completar
  ("reenvie a carteira para ver quanto volta em cada faixa").
- Quando uma medição falha, diga isso ("Não consegui medir agora"), sem fingir zero.

---

## 9. Ações sensíveis

| Ação | Como |
|---|---|
| Reversível (apagar um filtro, desfazer baixa) | faz na hora e oferece **Desfazer** (`components/AvisoDesfazer.jsx`) |
| Irreversível (excluir conta, apagar carteira) | **duas travas**: marcar "Entendo que não dá para desfazer" + segundo clique ("Excluir definitivamente", expira em 5 s). O botão seguro é o `btn-primary`; o destrutivo fica afastado |
| Cria compromisso (acordo, pagamento) | mostre o impacto **antes** de confirmar ("Confirmar R$ 1.200,00") |

Botão em execução: desabilitado + texto de estado ("Salvando…"), sem clique duplo.

---

## 10. LGPD e dados do devedor

- Mostre o mínimo: CPF mascarado (`***.567.060-**`), sem texto de conversa em
  listas, resumos ou telas de métricas.
- **Perfil do cliente** (aba Resumo da pasta): é orientação de conversa, não
  diagnóstico. Vem de regras auditáveis (`backend/agente/perfil.py`), não usa
  dado sensível, mostra as fontes de cada traço e o aviso "não decide nada sozinha".
- Nada de dado pessoal em URL (`?cpf=` não). Use ids.
- Logs e métricas guardam contagens e tempos, não destinatários nem mensagens
  (ex.: `email_utils.ENVIOS` guarda só hora e ok).

---

## 11. Backend: como dar suporte a uma tela nova

- **Prefira rota nova a mudar o contrato de uma existente.** Se precisar mudar
  uma resposta, só **acrescente** campos (a tela antiga ignora o que não conhece).
- Conta nova = **função pura testada** (ex.: `pontos_da_curva`, `plataforma.agentes`,
  `agente.api.por_hora`). A rota só busca as linhas e chama a função.
- Toda rota confere quem chama (`_usuario_autenticado`, `_exige_carteira_da_empresa`,
  `_empresa_do_agente`). Ação de escrita grava auditoria (`_registrar_auditoria`).
- Rota de leitura pesada usa cache curto (`_cache_get`/`_cache_set`, 60–600 s).
- Mudança de backend é sensível no repositório compartilhado: **sempre destaque
  no PR** o que mudou e se é só acréscimo.

---

## 12. Como testar antes de entregar

1. `cd frontend && npx vite build` (precisa de `VITE_API_URL`) sem erro.
2. `node --test tests/<arquivo>.test.mjs` para cada arquivo de `frontend/tests/`.
   O `ux-auditoria.test.mjs` tem os testes-guarda da moldura e das ações sensíveis.
3. Backend: os testes são scripts (`python test_x.py`), não pytest. Rode os da
   área que você tocou e escreva um novo para cada conta nova.
4. **Todo bug corrigido vem com um teste que falha sem a correção.** Prove:
   guarde a correção (`git stash push <arquivos>`), rode e veja falhar, devolva.
5. Olhe a tela de verdade em 390 px e 1280–1440 px, nos temas claro e escuro,
   e com movimento reduzido. Nada pode rolar na horizontal.
6. Teste o vazio, um item só, muitos itens e nomes/valores longos.

---

## 13. Checklist rápido

- [ ] `CabecalhoPagina` com voltar, título igual ao menu, frase de propósito
- [ ] Cada gráfico com título-resposta calculado dos dados
- [ ] Só tokens; estado com cor **e** texto
- [ ] Animação vinda de `graficos.jsx`, uma vez, respeitando movimento reduzido
- [ ] Carregando / vazio / erro / sem permissão tratados
- [ ] Ação irreversível com duas travas; reversível com desfazer
- [ ] Nada de dado pessoal sobrando; perfil com fontes e aviso
- [ ] Backend só por acréscimo, conta em função pura testada, destacado no PR
- [ ] Build, testes e olhar em 390 px e desktop, claro e escuro
