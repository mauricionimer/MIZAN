# Revisão completa do MIZAN (18/10/2026)

Objetivo: sistema liso, coerente, didático e profissional para o regional de 24/10.
Escopo: os 8 agentes (qualidade e uso), todo o backend (~25 mil linhas) e todo o
frontend (~17 mil linhas).

## Método

1. **Leitura em paralelo, sem editar.** Dez revisores independentes, cada um com uma
   área e o mesmo formato de achado: gravidade, arquivo:linha, o que acontece,
   evidência (código lido ou comando rodado) e correção sugerida. Quem revisa não
   corrige: as correções são feitas num lugar só, para não haver conflito.
2. **Verificar antes de aceitar.** Cada achado é conferido no código (ou reproduzido)
   antes de virar correção. Achado sem evidência é descartado.
3. **Corrigir por lotes**, do mais grave ao mais leve, cada lote com teste novo
   quando for comportamento, suíte inteira, bateria e build.
4. **Qualidade dos agentes com IA real** (Gemini grátis, com pausa por causa da
   cota): uma bateria de conversas difíceis por agente, notas por critério.
5. **Conferência visual** das telas com o servidor falso (dogfood).
6. **Revisão independente do diff final** antes do PR (skill requesting-code-review).

## Áreas

| # | Área | Arquivos |
|---|---|---|
| 1 | Núcleo dos agentes | orquestrador, grafos, estado, rastreio, repositorio, fonte, llm |
| 2 | Conversa e segurança | triagem, negociador, guardrails, auditor, ferramentas, conhecimento + base |
| 3 | Agentes analíticos | estrategista(_ia), acompanhamento, supervisor, passagem, ciencia, cientista, agente/api |
| 4 | API, parte 1 | main.py 1–4300, auth.py |
| 5 | API, parte 2 e modelos | main.py 4300–fim, limite, ajuda, backtest, model/ |
| 6 | Front: base | api.js, App.jsx, AppShell, contextos, utils, Login, AlterarSenha, AdminUsuarios, Upload |
| 7 | Front: operação | Dashboard, DebtorDetail, FazerOferta, Feedback, Acordos, Agenda, PainelOperador, Resultados |
| 8 | Front: agentes e análises | Agente, AgentePerfil, Escritório, FichaPassagem, Comando, Aprendizado, Bandit, Backtest, Ofertas, Roteiros, Retenção, PerformanceIA, Treino, Ajuda, Auditoria |
| 9 | Coerência entre partes | cada chamada do api.js contra a rota do backend; textos e números da tela contra o código; docs públicos (AGENTESMIZAN) contra o código |
| 10 | Testes e análise estática | ruff/pyflakes (venv descartável), avisos do build, lacunas de teste |

## Gravidade

- **Crítico**: vaza dado, quebra segurança/multiempresa, perde dinheiro ou dado, derruba tela/rota.
- **Alto**: resultado errado ao usuário, agente faz o que não devia, fluxo principal quebra em caso comum.
- **Médio**: caso de borda, incoerência visível, texto confuso, erro sem mensagem.
- **Baixo**: estilo, código morto, melhoria.

## Regras mantidas

Nada de escrita no Supabase de produção (SQL novo vai em backend/sql/ para o Mauricio
rodar); testes com ClienteFalso; dados fictícios; suíte verde antes de subir; PR por
lote.
