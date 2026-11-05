# Instruções para assistentes de código (MIZAN)

Antes de criar ou mudar qualquer tela, leia **`design/GUIA_DE_DESIGN.md`**:
cabeçalho padrão, tokens, animações (`frontend/src/components/graficos.jsx`),
regras de gráfico, ações sensíveis, LGPD e como testar.

O visual base (paleta, fonte, logo) está em `design/MIZAN_REDESIGN.md`.

Repositório compartilhado:
- Trabalhe numa branch e entregue por PR. Nunca faça push direto na `master`.
- Mudança no backend é sensível. Prefira rota nova ou só acrescentar campos, e destaque a mudança no PR.
- Os testes do backend são scripts (`python test_x.py`). Os do frontend rodam com `node --test frontend/tests/<arquivo>`.
