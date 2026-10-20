# Indicadores bento no MIZAN

O componente enviado foi integrado aos dados da aplicação, sem os números e o gráfico decorativo da demonstração. A base já tinha `KpiBento`; esta alteração completa a adoção nos resumos que ainda tinham implementações próprias.

## Estrutura

- Componente TypeScript: `frontend/src/components/ui/stats-bento.tsx`.
- Adaptador das páginas: `frontend/src/components/StatCard.jsx`.
- Exemplo com dados recebidos por props: `frontend/src/components/ui/stats-bento.demo.tsx`.
- Estilos e cores: `frontend/src/index.css`.
- Tailwind 3 já instalado, com leitura de arquivos TS/TSX.
- TypeScript configurado em `frontend/tsconfig.json`, mantendo compatibilidade com as páginas JSX existentes.
- Alias `@/` configurado no Vite e TypeScript.
- Estrutura shadcn declarada em `frontend/components.json`, com utilitário `cn` em `frontend/src/lib/utils.ts`.

`src/components/ui` é a pasta de componentes visuais compartilhados dentro do frontend Vite. Não deve ser criada outra pasta `components/ui` na raiz do repositório: isso duplicaria a estrutura fora de `src` e do escopo do Tailwind. O alias permite usar `@/components/ui/stats-bento`.

Não é necessário executar a inicialização do shadcn nem reinstalar Tailwind. Para instalar o ambiente em outra máquina, execute `npm ci` na pasta `frontend`. Novos componentes do catálogo podem ser adicionados com `npx shadcn@latest add <componente>` nessa pasta; devem usar os tokens de tema já existentes no MIZAN.

## Uso

```tsx
import StatsBento, { BentoStat } from '@/components/ui/stats-bento'

<StatsBento aria-label="Resumo da carteira">
  <BentoStat label="Valor de face" value={valorFormatado} />
  <BentoStat label="Devedores" value={quantidade} />
  <BentoStat label="Score médio" value={score} />
</StatsBento>
```

`StatsBento` e `KpiBento` são nomes para o mesmo layout. Com três ou mais cartões, o primeiro ganha destaque, o segundo ocupa a faixa superior e os demais compõem a faixa inferior. Um ou dois cartões usam uma grade simples. No celular os indicadores empilham em uma coluna. Os valores permitem quebra para evitar transbordamento de quantias extensas.

`StatCard` preserva as props das páginas: rótulo, valor, ícone Lucide, nota, barra e link. Os dados continuam vindo dos hooks e APIs existentes; não há novo provider de dados nem alteração de cálculo. As variantes de layout usam um contexto React interno. A cor principal e a tinta de contraste vêm de `--royal` e `--on-brand`, respeitando temas e personalização da empresa.

## Cobertura

| Área | Integração |
| --- | --- |
| Carteira | Resumo e precificação |
| Ficha do devedor | Resumo antes do atendimento |
| Acordos / Meus acordos | Resumo com filtros por clique e estado selecionado |
| Pagamentos | Resultado da importação de feedbacks; acordos embutidos usam o mesmo componente |
| Ofertas | Valores calculados da simulação |
| Performance da IA | Modelo em uso e acerto nos pagamentos |
| Simulação histórica | Indicadores de separação, quantidade e recuperação |
| Agentes e perfis | Indicadores já integrados passam pelo mesmo componente |
| Laboratório | Usa os indicadores da área de agentes |
| Meu painel / Equipe | Mantém os resumos existentes na grade compartilhada |
| Resultados | Mantém os resumos existentes na grade compartilhada |
| Comando / Bandit | Resumos da plataforma e abordagens |
| Aprendizado | Acurácia, precisão, revocação, F1, precificação e sincronização |
| Retenção | Contagens de registros e vencimentos |

Agenda, pastas, auditoria, usuários, permissões e política mantêm suas listas, tabelas, formulários e fluxos específicos. Gráficos e matrizes de comparação continuam com suas escalas e legendas: o componente organiza indicadores, sem transformar cada célula ou campo em um KPI. Login e recuperação são formulários, sem indicadores de análise.

## Verificação

Na pasta `frontend`:

```sh
npm run typecheck
npm run test:bento
npm run build
```

O build exige `VITE_API_URL` do ambiente de destino. Para apenas validar a compilação local, pode ser usado um endereço fictício; o resultado dessa compilação não deve ser publicado como ambiente funcional.

Os testes renderizam o componente e verificam hierarquia, exclusão de cartões condicionais, valores zerados, quantia longa, links e limites de progresso. Não substituem inspeção visual das telas autenticadas; esta entrega foi conferida pelo código, conforme solicitado.
