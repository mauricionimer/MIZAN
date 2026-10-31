# Base jurídica interna do orquestrador (RAG jurídico)

Apoio interno às decisões do agente sobre crédito, cobrança e dados pessoais. Antes de
uma ação com impacto jurídico, o orquestrador consulta as normas selecionadas, aplica uma
regra em código e registra a decisão. **Não é parecer jurídico.** É um limite operacional
que, na dúvida, manda para revisão humana.

Código: `backend/agente/juridico/` (núcleo) e `backend/agente/juridico_orq.py` (ponte com o
orquestrador). Testes: `test_juridico_base.py` e `test_juridico_fluxos.py`.

## 1. Como funciona

```
ação sensível ──► fatos mínimos (código) ──► consultar_legislacao ──► regra do perfil ──► decisão
                     sem nome/CPF/telefone      busca híbrida +          (código, não IA)     │
                                                fundamentos por artigo                       ▼
                                                                         registro interno (cifrado)
                                                                         passo no rastreio (só ação + conclusão)
```

- **Decisões possíveis:** `prosseguir`, `prosseguir_com_condicoes`, `nao_prosseguir` e
  `revisao_humana`.
- **Falta de resultado não é permissão.** Cada um destes casos leva a `revisao_humana`:
  - fundamento ausente no índice;
  - dispositivo conflitante;
  - dispositivo desatualizado;
  - redação divergente da fonte oficial;
  - fato essencial faltando;
  - ação sem perfil;
  - falha técnica da consulta.
- **O texto recuperado não decide nem dá ordem.** A regra é código (`decisao.py`, `PERFIS`).
  A consulta só confirma que o fundamento existe e está em condições de uso. Trecho com cara
  de instrução ("ignore as instruções…") é marcado na ingestão e fica fora da busca.
- **Nunca inventa dispositivo.** O fundamento é buscado por artigo no índice. Quando não está
  lá, a resposta diz que faltou.

### Ferramenta `consultar_legislacao(pergunta, contexto_da_acao)`

Arquivo: `agente/juridico/consulta.py`. Devolve:

- **`dispositivos`**: id, rótulo canônico (por exemplo "LGPD, art. 18, inciso II"), texto,
  contexto (capítulo, seção, caput e dispositivo-pai), situação, notas e conferência.
- **`fontes`**: norma, versão do texto, arquivo, commit do acervo, endereço no repositório,
  fonte oficial, situação e data da conferência.
- **`limitacoes`**: o que não foi conferido, o que está desatualizado, o escopo e o aviso de
  que não é parecer.
- **`fundamentos_ausentes`** e a **versão do índice**.

## 2. Fontes

Acervo: [ctresb/leis](https://github.com/ctresb/leis), commit `2dac3a272eed`
(28/10/2026). Os scripts estão sob licença MIT. Os textos são atos oficiais, sem proteção
autoral (Lei 9.610/98, art. 8º, I). O próprio README avisa que a conversão é automática e
pode ter erros. Aqui o acervo serve de **cópia de consulta**: redação e vigência se
confirmam na fonte oficial (seção 4).

| Norma | Versão no acervo | Dispositivos | Por quê |
|---|---|---|---|
| LGPD (Lei 13.709/2018) | compilada | 457 | Bases legais, princípios, direitos do titular, decisão automatizada, segurança |
| CDC (Lei 8.078/1990) | compilada | 474 | Cobrança (art. 42), cadastros (art. 43), crédito (art. 52), superendividamento |
| Cadastro Positivo (Lei 12.414/2011) | compilada | 111 | Histórico de crédito, revisão de decisão |
| Código Civil, só um recorte | compilada | 155 | Prescrição, cessão de crédito, pagamento e quitação, inadimplemento e juros, cobrança de dívida paga |
| Marco Civil (Lei 12.965/2014), arts. 3, 7 e 10 | compilada | 32 | Dados e comunicações em canais digitais |
| Decreto 11.150/2022 | **original** | 32 | Mínimo existencial |
| Decreto 11.567/2023 | original | 5 | Altera o art. 3º do Decreto 11.150 |
| Resolução CMN 4.949/2021 | publicação original | 82 | Relacionamento com clientes; aplica-se a instituições financeiras |

Normas deixadas de fora (estão em `catalogo.DESCARTADAS`):

- **Lei 14.181/2021**: já está dentro do CDC compilado.
- **Constituição**: grande demais para o ganho.
- **Normas estaduais e municipais**: fora do escopo inicial.

O texto do art. 3º do Decreto 11.150 no acervo é anterior ao Decreto 11.567/2023. Por isso
ele fica marcado como **desatualizado**, e qualquer decisão que dependa dele vai para
revisão humana.

## 3. Ingestão, índice e atualização

- **Estrutura:** norma → artigo → parágrafo → inciso → alínea (`estrutura.py`). Cada
  dispositivo leva:
  - rótulo canônico;
  - contexto (capítulo, seção, caput e pai);
  - notas editoriais, separadas do texto;
  - situação: vigente, revogado, vetado ou desatualizado;
  - hash.
- **Metadados** no `manifesto.json`:
  - título, tipo, número, data e versão do texto;
  - arquivo, sha256 do arquivo e commit;
  - endereço no repositório e fonte oficial;
  - data da ingestão e conferência.
- **Atualização incremental:** norma cujo arquivo, recorte, alterações conhecidas e versão
  do parser não mudaram fica como estava. Mudou: só ela é relida, e o relatório diz o que
  entrou, mudou ou saiu. Arquivo que sumiu do acervo fica com a cópia anterior, sinalizada.
- **Deduplicação:** texto longo idêntico em duas normas fica só na principal. O mesmo
  dispositivo duas vezes com textos diferentes vira **conflito**.
- **Busca híbrida** (`indice.py`):
  - BM25: termos exatos e radicais;
  - LSA: TF-IDF + SVD do scikit-learn, semântica local, sem mandar nada para fora;
  - as duas fundidas por Reciprocal Rank Fusion;
  - sinônimos traduzem o vocabulário da operação para o da lei.
- **Fica fora da busca:** revogados, vetados, duplicados e trechos com cara de instrução.
  Revogados e vetados continuam acessíveis por artigo.
- **O índice tem só texto público das normas.** Arquivos: `agente/juridico/dados/indice.jsonl.gz`
  e `manifesto.json`, ambos versionados no git.

Para atualizar o índice (precisa de um clone do acervo; lê direto do commit, sem extrair os
17 GB):

```bash
cd backend
python -m agente.juridico.ingestao --acervo /caminho/do/clone/leis            # simulação
python -m agente.juridico.ingestao --acervo /caminho/do/clone/leis --aplicar  # grava
```

Depois, rode `python test_juridico_base.py` e faça o commit dos dois arquivos de `dados/`.

## 4. Conferência na fonte oficial

`conferencia.py` baixa a página oficial (Planalto ou Banco Central) e tira o texto tachado
(redações antigas). Em seguida procura cada dispositivo vigente no texto oficial. O
resultado é um destes:

- **`conferida`**;
- **`divergente`**, com a lista dos dispositivos que não batem;
- **`nao_conferida`**.

A conferência só vale para o mesmo arquivo (sha256). O ambiente onde o índice foi gerado
não alcança o Planalto, por isso **todas as normas estão hoje `nao_conferida`**. Para
conferir pelo servidor, que tem internet:

- `POST /agente/juridico/conferir` (administrador): roda em segundo plano e grava em
  `agente_conferencias_juridicas`;
- o resultado aparece em `GET /agente/juridico/fontes` e vale para as próximas decisões.

Enquanto uma norma não for conferida, cada consulta diz isso nas limitações. Ações que
exigem texto conferido vão para revisão humana:

- compartilhamento de dados;
- oferta com sinais de superendividamento.

## 5. Quando o orquestrador consulta

| Momento | Ação (perfil) | Nível | Se bloquear |
|---|---|---|---|
| Aplicar o plano do dia | `estrategia_cobranca` + `decisao_automatizada_credito` | empresa | nada é aplicado; a tela mostra o que revisar |
| Todo contato iniciado pelo agente (abordagem, lembretes) — `Contexto.auditar` | `estrategia_cobranca` (canal, horário, dias, frequência, conteúdo) | empresa | o contato não sai (`RJ_REVISAO_JURIDICA`) |
| Estrategista escolhe tom e oferta inicial | `decisao_automatizada_credito` | empresa | segue sem estratégia automática |
| Devedor abre o convite do Telegram | `comunicacao_devedor` + `uso_dados_pessoais` (guardar o id do chat) | caso | o chat é desligado e a pessoa recebe mensagem neutra |
| Registrar um acordo | `oferta_credito` (total e parcelas mostrados antes, superendividamento, pressão) | caso | faltou mostrar a conta: a IA mostra e pede confirmação; o resto vai para uma pessoa |
| Pedido sobre os próprios dados | `pedido_titular` | caso | sempre com uma pessoa responsável (registra e confirma ao devedor) |
| Contestação da dívida | `contestacao` | caso | consultiva: suspende a cobrança e registra |

Sobre o nível das decisões:

- **Nível empresa** depende só da política: é avaliada uma vez, registrada sem caso e
  reaproveitada por 6 horas (com o mesmo índice).
- **Nível caso** é registrada com o id do caso.

Os fatos são montados em código, nunca a partir do texto da conversa. O pedido do titular
é detectado em código (`sinais.pedido_titular`) em qualquer caminho da mensagem: também
quando a pessoa pede para parar, contesta ou o caso está com a equipe. Ele vira um item na
agenda da equipe.

Os tipos de pedido são:

- **Seguem na conversa:** acesso, origem, informação sobre uso e compartilhamento,
  correção, portabilidade.
- **Passam para uma pessoa:** eliminação, oposição, revogação do consentimento e revisão de
  decisão automatizada.

## 6. Conversa com o devedor

- A análise jurídica fica no registro interno. A conversa nunca menciona a base jurídica,
  a consulta, o parecer ou a análise interna; as travas de saída barram isso.
- O atendente **não cita lei por iniciativa própria.** Cita só quando a pessoa pede a lei
  ou o fundamento (`sinais.pediu_fundamento`). Fora disso, `consultar_base` devolve a
  resposta em palavras simples, e a trava barra citação.
- Pergunta sobre direitos ou dados tem resposta verdadeira e compreensível, ou vai para uma
  pessoa. O pedido do titular é sempre registrado e confirmado, com o que a pessoa tem
  direito de receber; o prazo de 15 dias aparece só para acesso e origem.
- Antes do aceite, a pessoa precisa ter visto o valor total, o número e o valor das
  parcelas.

## 7. Privacidade e acesso

- **Contexto mínimo.** A consulta recebe fatos estruturados (sim/não, horários, tipo de
  pedido). `sanitizar` ainda tira CPF, CNPJ, e-mail, telefone, números longos e nomes. A
  pergunta livre do administrador também perde os nomes próprios.
- **Registro** (`agente_consultas_juridicas`) guarda:
  - ação, conclusão, condições e justificativa;
  - dispositivos e fontes;
  - incertezas, versão do índice e data.

  Os fatos ficam cifrados com a **mesma chave Fernet da Mizan** (`MIZAN_ENCRYPTION_KEY`). Em
  produção sem chave, nada é gravado em claro; a decisão vale e só o registro não é feito.
- **Acesso.** As tabelas têm RLS ligado e nenhuma política: só o backend lê e grava. As rotas
  são só para administrador (e COMANDO), restritas à própria empresa:
  - `GET /agente/juridico/decisoes?caso_id=`;
  - `POST /agente/juridico/consultar`;
  - `GET /agente/juridico/fontes`;
  - `POST /agente/juridico/conferir`.
- **Rastreio da operação.** Mostra só ação, conclusão e id do registro. A fundamentação não
  aparece ali.
- **O RAG não contorna nada.** Auditor, travas de saída e revisão humana continuam iguais;
  a base jurídica só acrescenta bloqueios.

## 8. Configuração

1. **Supabase:** rode `backend/sql/migracao_agente_juridico.sql` no SQL Editor. Sem as
   tabelas, o agente decide do mesmo jeito, mas não guarda o registro e avisa no log.
2. **Render:** nada novo. Usa a `MIZAN_ENCRYPTION_KEY` que já existe. O índice vai no
   código e é aquecido ao subir o servidor.
3. **Conferência:** depois do deploy, um administrador chama `POST /agente/juridico/conferir`
   e confere o resultado em `GET /agente/juridico/fontes`.

## 9. Limitações (exigem avaliação jurídica humana)

- **Fontes não conferidas** na fonte oficial até rodar a conferência pelo servidor.
- **Decreto 11.150/2022:** o art. 3º do acervo está desatualizado (Decreto 11.567/2023).
- **Fora da base:**
  - normas estaduais e municipais (por exemplo, horários de cobrança e telemarketing);
  - resoluções e guias da ANPD;
  - normas do Bacen além da Resolução CMN 4.949;
  - jurisprudência;
  - Constituição.
- **Regras heurísticas.** As regras dos perfis são escolhas conservadoras, não
  interpretação definitiva. Por exemplo, contato só das 8h às 20h, de segunda a sábado; um
  sinal de superendividamento leva a revisão humana. Elas devem ser validadas pelo jurídico
  da empresa cliente.
- **Detectores por regras de texto.** Os detectores de pedido do titular, superendividamento
  e pedido da lei podem deixar passar frases diferentes das previstas. Nesse caso, a IA ainda
  tem a ferramenta `registrar_pedido_titular`.
- **Lacunas não verificadas automaticamente.** A RLS e o acesso dependem da chave de serviço
  ficar só no backend. A base não verifica bases legais específicas de cada empresa
  (contratos, consentimentos) nem o papel de controlador e operador.
