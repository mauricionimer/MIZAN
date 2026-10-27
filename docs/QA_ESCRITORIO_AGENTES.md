# Escritório: reorganização e regressões de UI/UX

Atualização solicitada em 21/10/2026. Substitui a composição inicial de três colunas: a sala agora ocupa a esquerda, os detalhes ficam à direita quando há espaço, e a seleção de agentes fica em um painel horizontal separado abaixo da moldura. Em telas menores os detalhes passam para baixo da sala; no celular a lista horizontal tem rolagem própria. Tudo permanece em `/agente`.

Paredes no azul MIZAN `#5966d9`, com a outra face mais clara. Nomes canônicos preservados, conforme confirmação do usuário, com etiquetas completas, selecionáveis e sem colisões. A câmera usa os limites do cenário desenhado para ampliar a sala em pixels inteiros. O nome da empresa usa medição real da fonte, ajuste de tamanho e quebra de linhas; nomes excepcionalmente extensos recebem reticências na placa, com a identificação completa preservada no cabeçalho. A imagem da empresa mantém sua proporção.

## Regressões persistentes

| ID | Problema protegido | Verificação |
|---|---|---|
| REG-LAYOUT-001 | Lista ocupar a esquerda ou permanecer dentro da moldura | Posição abaixo de sala/detalhes, ancestral fora de `.ao-frame`, primeiros cartões na mesma linha. Reproduziu falha na composição anterior. |
| REG-SIZE-002 | Aumentar o quadro sem aumentar o cenário por causa das margens vazias | Câmera com zoom 2 em áreas de 930–1190 px e limites desenhados contidos no quadro; largura real da sala ampliada no navegador. |
| REG-NAMES-003 | Nome incompleto ou sobreposto a outro nome | Identidades canônicas, texto sem corte, detecção geométrica de colisões e caso sintético de nomes longos próximos. |
| REG-BRAND-004 | Goiás Bank sair da placa ou perder caracteres | Nome completo com acento/K; marcas extensas e palavras sem espaços; largura medida e altura dentro da placa; comparação de pixels confirma que alterações de nome não modificam a área fora da placa. |
| REG-RESP-005 | Transbordamento horizontal e seleção inacessível | 1920, 1440, 1280, 1024, 760, 390 e 320 px; seleção por Enter e permanência na mesma página. |
| REG-COLOR-006 | Paredes voltarem à cor antiga | Cor da configuração e amostra de pixels da parede renderizada. |
| REG-NAMES-007 | Etiquetas existirem no DOM, mas ficarem invisíveis abaixo do canvas | Todos os retângulos das etiquetas ficam dentro do cenário. A inspeção da captura revelou falta de `left:0; top:0`, corrigida e coberta por esta asserção. |
| REG-MURAL-008 | Folhas decorativas ultrapassarem o mural | Seis folhas em posições explícitas, com largura/altura contidas na moldura e margem em todos os lados; o desenho também recorta o conteúdo ao mural. |
| REG-BRAND-009 | Letras pequenas e pixeladas tornarem o nome da empresa ilegível | Goiás Bank em duas linhas, fonte maior e nome preservado; texto desenhado diretamente na resolução da tela, sem reduzir uma textura ao buffer pixelado. |

Também verificados: Casos/Atividade/Detalhes, seguir e centralizar, preservação de dados na perda de conexão, recuperação automática, feed sem duplicação e ausência de erros de JavaScript.

## Execução

Na pasta `frontend`:

```powershell
npm run test:escritorio
npm run test:escritorio:ui
npm run build
```

Os testes de modelo usam somente Node. O teste de navegador precisa de Playwright disponível no ambiente de QA (instalação local ou `MIZAN_PLAYWRIGHT_MODULE` apontando para uma instalação existente). `MIZAN_BROWSER_CHANNEL=msedge` permite usar o Edge instalado; sem essa opção, usa o Chromium do Playwright. `MIZAN_QA_OUTPUT` define a pasta das capturas, cujo padrão fica na pasta temporária do sistema.

As APIs e a autenticação são substituídas por fixtures locais no navegador isolado. Não são usadas credenciais nem sessões reais. A suite sobe e encerra seu próprio Vite. Nenhuma dependência de produção foi adicionada.

Resultado atual: sete testes de modelo passaram, suite de navegador passou e build de produção passou. As capturas de desktop e celular mostram dados de teste. A validação cobre os cenários descritos, sem afirmar ausência de qualquer possível problema em dispositivos não testados.

Na limpeza visual posterior, o relógio da parede e os nomes dos departamentos desenhados no piso foram removidos. A comparação de pixels da placa continua verificando que o texto, agora renderizado em resolução de tela, não ultrapassa sua área. O QA visual conferiu a placa legível e as seis folhas dentro do mural.
