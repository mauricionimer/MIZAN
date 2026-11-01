# Prova de segurança: APROVADO

- Data: 2026-11-01 21:18 UTC
- Commit: `4e3a12c`
- Modo: provas + testes de segurança
- Python 3.11.17 em Linux

| Etapa | Resultado | Tempo |
|---|---|---|
| `test_seguranca_estatico.py` | ok | 31 s |
| `test_seguranca_plano.py` | ok | 80 s |
| `test_api_key.py` | ok | 2 s |
| `test_autorizacao.py` | ok | 3 s |
| `test_segredos.py` | ok | 2 s |
| `test_destino_conexao.py` | ok | 2 s |
| `test_conexoes_escopo.py` | ok | 2 s |
| `test_conexao_sheets.py` | ok | 2 s |
| `test_erros_internos.py` | ok | 2 s |
| `test_limite.py` | ok | 8 s |
| `test_escopo_carteira.py` | ok | 2 s |
| `test_auditoria_acesso.py` | ok | 2 s |
| `test_varredura_contas.py` | ok | 8 s |
| `test_agente_manipulacao.py` | ok | 0 s |
| `test_agente_telegram.py` | ok | 18 s |
| `test_revisao_api.py` | ok | 14 s |
| `pip-audit` | ok | 16 s |
| `npm audit --omit=dev` | ok | 1 s |

## Saída de cada etapa

<details><summary><code>test_seguranca_estatico.py</code>: ok</summary>

```
ok    [S3] migração que apaga a coluna api_key existe
ok    [S3] _buscar_api_key não consulta a coluna em texto
ok    [S3] schema.sql sem a coluna api_key
ok    [S4] nenhuma exceção inesperada na resposta
ok    [S5] requirements.txt só com versões exatas (==)
ok    [S5] fastapi >= 0.162.0
ok    [S5] starlette >= 1.10.0
ok    [S5] python-multipart >= 0.0.32
ok    [S5] python-dotenv >= 1.2.4
ok    [S5] cryptography >= 43.0.0
ok    [S5] react-router >= 7.18.5 no package-lock
ok    [S5] react-router-dom >= 7.18.5 no package-lock
ok    [S5] jspdf >= 4.2.1 no package-lock
ok    [S5] xlsx >= 0.20.3 no package-lock
ok    [S5] dompurify sem a versão vulnerável
ok    [S10] lifespan chama _conferir_segredos_de_producao
ok    [S10] conferência antes do agendador e do primeiro admin
ok    [S11] defusedxml no requirements.txt
ok    [S11] toda leitura de Excel em main.py passa antes pela trava
ok    [S11] treino por empresa também confere a planilha
ok    [S12] todas as 37 tabelas dos scripts têm RLS
ok    [S13] vercel.json define content-security-policy
ok    [S13] vercel.json define x-content-type-options
ok    [S13] vercel.json define x-frame-options
ok    [S13] vercel.json define referrer-policy
ok    [S13] vercel.json define strict-transport-security
ok    [S13] CSP com frame-ancestors 'none'
ok    [S13] script-src sem unsafe-inline/unsafe-eval
ok    [S13] index.html sem script embutido
ok    [OK-CORS] CORS sem origem coringa
ok    [OK-XSS] frontend sem innerHTML/eval
ok    [OK-TOKEN] token fora do localStorage
ok    [OK-PROVA] a prova dinâmica não substitui as funções de segurança
APROVADO
```

</details>

<details><summary><code>test_seguranca_plano.py</code>: ok</summary>

```
— S1: credencial do Google só fala com o Google —
ok    [S1] controle da montagem: google-auth sem trava chega ao servidor interno
ok    [S1] /testar-db com JSON novo: 400, sem requisição ao interno
ok    [S1] conexão já salva com token_uri interno: barrada no uso
ok    [S1] /conexoes recusa credencial com token_uri errado
ok    [S1] /conexoes recusa credencial com universe_domain errado
ok    [S1] /conexoes recusa credencial com client_email errado
ok    [S1] /conexoes recusa credencial com type errado
ok    [S1] controle: credencial com token_uri do Google é salva
ok    [S1] o que fica guardado é a credencial limpa
ok    [S1] nenhuma requisição chegou ao servidor interno
— S2: limite de login pelo e-mail, não pelo IP —
ok    [S2] 8 tentativas, IP diferente em cada: 5 × 401 e depois 429
ok    [S2] nem a senha certa entra durante o bloqueio (por e-mail)
ok    [S2] controle: outra conta continua entrando
ok    [S2] e-mail inexistente recebe exatamente a mesma sequência
ok    [S2] um IP, muitos e-mails: 429 depois de 30
ok    [S2] o registro de tentativas tem teto de chaves
ok    [S2] redefinir a senha limpa o bloqueio do e-mail
— S3: chave de API só pelo hash —
ok    [S3] chave que só existe em texto puro: 401 no /webhook/pagamento
ok    [S3] a busca nunca filtra pela coluna api_key
[Webhook] Pagamento recebido — CPF: ***09, pagou: True, empresa: alfa
ok    [S3] controle: chave pelo hash autentica
ok    [S3] sem a coluna de hash, nada entra (falha fechada)
— S4: falha interna não vaza na resposta —
ok    [S4] a mensagem da exceção não aparece na resposta
ok    [S4] a resposta traz o código de 8 caracteres
— S6: /docs fechado em produção —
ok    [S6] /docs dá 404
ok    [S6] /redoc dá 404
ok    [S6] /openapi.json dá 404
ok    [S6] controle: /health continua 200
— S7: um PBKDF2 por login, exista o e-mail ou não —
ok    [S7] mesmo número de PBKDF2 (1) nos três casos
ok    [S7] resposta idêntica nos três casos
— S8: PBKDF2 com 600 mil iterações —
ok    [S8] hash novo com >= 600 mil iterações
ok    [S8] hash antigo continua entrando
ok    [S8] o login regrava o hash
ok    [S8] o token emitido nesse login funciona no /auth/me
— S9: /auth/refresh não renova para sempre —
ok    [S9] o login grava auth_time no token
ok    [S9] renovar mantém o mesmo auth_time
ok    [S9] auth_time de 31 dias atrás: 401 no refresh
ok    [S9] controle: 29 dias ainda renova
— S10: segredo fraco não sobe —
ok    [S10] recusa JWT curto
ok    [S10] recusa JWT padrão do código
ok    [S10] recusa JWT vazio
ok    [S10] recusa chave Fernet vazia
ok    [S10] recusa chave Fernet inválida
ok    [S10] controle: aceita segredos bons
— S11: .xlsx que explode ao abrir —
ok    [S11] montagem: a bomba tem menos de 1 MB compactada
ok    [S11] /analisar: 413 sem chamar o leitor de Excel
ok    [S11] /backtest: 413 sem chamar o leitor de Excel
ok    [S11] /feedback/lote: 413 sem chamar o leitor de Excel
ok    [S11] controle: planilha normal chega ao leitor
— S13: cabeçalhos de segurança na API —
ok    [S13] rota autenticada com no-store e nosniff
ok    [S13] nosniff também na rota pública
— S14: o que a tela mostra não confirma a identidade —
ok    [S14] nenhum pedaço da máscara da tela confirma
ok    [S14] controle: o CPF completo confirma
ok    [S14] o log também não mostra os 3 primeiros
— S16: PUT /empresa/config só aceita chaves conhecidas —
ok    [S16] chave desconhecida em extra: 422
ok    [S16] controle: alterar nome_exibicao continua 200
— S18: token de redefinição guardado como hash —
ok    [S18] o banco não contém o token do link
ok    [S18] controle: o link redefine a senha
ok    [S18] o mesmo link não serve duas vezes
— OK-IA: a IA não recebe o CPF completo —
ok    [OK-IA] o texto que vai à IA sai mascarado
— S15: 40 mensagens no Telegram, no máximo o limite de rodadas de IA (padrão 30) —
ok    [S15] montagem: convite gerado pela rota
ok    [S15] 40 mensagens seguidas: no máximo 30 rodadas de IA
ok    [S15] o devedor recebe um único aviso fixo, sem IA
ok    [S15] o que passou do limite fica num único evento adiado, com todas as mensagens
ok    [S15] controle: aberta a janela, uma rodada responde a todas
APROVADO
```

</details>

<details><summary><code>test_api_key.py</code>: ok</summary>

```
ok    chave correta é reconhecida pelo hash
ok    a chave em texto nunca sai do banco para a aplicação  — ['api_key_hash', 'ativa', 'empresa_id', 'empresa_nome', 'id']
ok    chave errada é recusada
ok    o hash da aplicação bate com o do gerador e com o SHA-256 padrão
ok    chave revogada (ativa=false) para de autenticar na hora
ok    banco sem a coluna de hash: a chave antiga NÃO autentica (falha fechada)
ok    e a retaguarda não aceita qualquer coisa
ok    o uso é registrado, para dar para saber se a chave ainda está viva  — {'ultimo_uso': '2026-11-01T21:16:39.453671'}
ok    e falhar ao gravar o rastro não derruba a requisição válida
ok    cada chave gerada é diferente
ok    chave tem tamanho e prefixo esperados  — 49 caracteres
ok    o gerador entrega o hash correspondente à chave
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_autorizacao.py</code>: ok</summary>

```
— /predicoes/historico —
ok    token inventado é recusado  — 401 — era 200 com o histórico
ok    sem token também
ok    devolve só o histórico da própria empresa  — ['p-dupla-a']
ok    CPF que só existe em outra empresa é 404, não o histórico dela
ok    comando vê as duas  — 200
ok    empresa sem carteira não vê o de ninguém
— /webhook/pagamento —
[Webhook] corpo diz empresa='beta', chave é de 'alfa'; usando a da chave.
[Agenda] promessas de 222*** não marcadas: AttributeError
[Webhook] Pagamento recebido — CPF: ***22, pagou: True, empresa: alfa
ok    a chamada é aceita  — 200
ok    mas grava na empresa DA CHAVE, não na do corpo  — gravou em alfa — era 'beta'
ok    e não liga à predição da beta
ok    o bandit da beta não aprende com isso
[Agenda] promessas de 333*** não marcadas: AttributeError
[Webhook] Pagamento recebido — CPF: ***33, pagou: True, empresa: alfa
ok    nome de exibição no corpo não quebra a integração  — o campo é ignorado, não rejeitado
ok    chave sem empresa vinculada é recusada  — 403
ok    chave inexistente segue 401
— o token prova quem é; o cadastro diz o que pode —
ok    admin ativo acessa a rota de admin (controle)  — 200
ok    admin DESLIGADO é recusado, mesmo com token válido  — 401
ok    admin REBAIXADO no cadastro perde o acesso na hora  — 403 — o token dizia admin, o cadastro diz operador
ok    admin REMOVIDO da empresa é recusado, em vez de listar TODAS  — 403 — empresa vazia significava 'todos os usuários de todos os clientes'
ok    comando DESLIGADO é recusado  — 401
ok    token que ALEGA ser comando, de usuário que no cadastro é admin, é recusado  — 403
ok    usuário que nem existe mais é recusado
ok    promovido no cadastro ganha acesso sem esperar o token novo
[Agenda] promessas de 222*** não marcadas: AttributeError
ok    mudar a empresa no cadastro vale na hora  — gravou em beta; o token ainda dizia alfa
ok    admin REBAIXADO a operador não registra pagamento manual  — 403, gravou 0 — o token ainda dizia admin
ok    e o desligado também não  — 401
ok    lista conexões: usuário desligado é recusado  — 401
ok    registra contato: usuário desligado é recusado  — 401
ok    lista contatos do CPF: usuário desligado é recusado  — 401
— /contatos —
ok    usuário sem empresa não lista contatos de ninguém  — 403 — via observação livre, vazaria telefone e nome de parente
ok    e quem tem empresa só vê os da própria  — []
ok    registrar 'pagou' para CPF que só existe em outra empresa é 404  — 404 — antes a resposta revelava se o CPF existia em QUALQUER empresa
ok    empresa sem carteira não casa com CPF de ninguém  — 404
ok    usuário sem empresa é recusado  — 403
— /devedores/{cpf}/confirmar-pagamento —
[Confirmar] Tentativa — CPF: ***22, role: admin
ok    empresa sem carteira não confirma pagamento do CPF de outra  — 404, gravou 0 — o `if cart_ids:` caía em 'sem filtro'
— /upload —
ok    exige credencial  — 403 — era 200 para qualquer um
ok    e credencial falsa não basta  — 401
ok    autenticado continua funcionando  — 200
— a classe de erro, não só as instâncias —
ok    toda rota que recebe credencial a usa  — []
ok    nenhuma rota confere só a assinatura do token  — [] (auth_refresh é a exceção: ele mesmo confere o cadastro)
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_segredos.py</code>: ok</summary>

```
— com chave configurada —
ok    a senha não sai em claro
ok    e o texto não aparece dentro do cifrado
ok    e volta ao original na leitura
— sem chave, com Supabase configurado (produção) —
ok    gravar credencial sem chave levanta erro nomeando a variável  — Tentativa de gravar credencial sem MIZAN_ENCRYPTION_KEY conf
— sem chave, sem Supabase (desenvolvimento local) —
ok    local segue funcionando sem exigir chave  — quem roda na própria máquina não precisa gerar uma
— migração de quem já tem credencial em claro —
ok    senha antiga, gravada em claro, ainda é lida  — ligar a chave não quebra o que já está no banco
— a trava na subida —
ok    o lifespan recusa subir em produção sem a chave
ok    e o render.yaml declara a variável  — senão um ambiente novo sobe sem ela e ninguém percebe
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_destino_conexao.py</code>: ok</summary>

```
— SQLite em serviço hospedado —
ok    recusa sqlite apontando para '/etc/passwd'
ok    recusa sqlite apontando para 'model/mizan_model.pkl'
ok    recusa sqlite apontando para '../../etc/shadow'
ok    recusa sqlite apontando para 'novo.db'
ok    e a mensagem diz o que fazer no lugar  — recusar sem alternativa vira chamado de suporte
— endereços que não podem ser o banco do cliente —
ok    recusa 127.0.0.1  — loopback
ok    recusa localhost  — loopback por nome
ok    recusa 169.254.169.254  — metadata da nuvem
ok    recusa 10.0.0.5  — rede privada
ok    recusa 192.168.1.10  — rede privada
ok    recusa 172.16.0.1  — rede privada
ok    recusa 0.0.0.0  — não especificado
ok    recusa ::1  — loopback IPv6
— o que é uso legítimo —
ok    endereço público é aceito
ok    e continua exigindo TLS
ok    Google Sheets não tem host e não é barrado
— SQL Server conecta por fora do construtor de URL —
ok    SQL Server também valida o destino  — Endereço 10.0.0.9 é de rede interna e nã
— desenvolvimento local —
ok    local conecta no Postgres da própria máquina  — quem está programando não pode ser barrado
ok    e SQLite local segue funcionando
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_conexoes_escopo.py</code>: ok</summary>

```
— a senha salva só vai para o servidor salvo —
ok    host da requisição é ignorado: a conexão usa o servidor cadastrado  — ['postgresql+psycopg://leitor:senha-secreta-do-cliente@db.alfa.example:5432/carteira?sslmode=require']
ok    e a senha salva é usada nele (fluxo legítimo continua)
— quem pode usar —
ok    admin de OUTRA empresa: 403 e nem tenta conectar  — 403 []
ok    operador sem permissão: 403  — 403
ok    operador liberado usa a conexão  — 503 ['postgresql+psycopg://leitor:senha-secreta-do-cliente@db.alfa.example:5432/carteira?sslmode=require']
ok    comando usa qualquer uma
ok    conexão inexistente: 404
— host e senha digitados —
ok    operador não digita host e senha (sonda de rede)  — 403
ok    admin digita o banco dele normalmente  — 503 ['postgresql+psycopg://u:s@meu.example:5432/b?sslmode=require']
ok    /listar-tabelas: mesma regra para operador
ok    /analisar/db: admin de outra empresa não usa a conexão  — 403
— editar a conexão —
ok    operador não edita, mesmo com permissão de uso  — 403
ok    admin de outra empresa não edita  — 403
ok    admin da empresa edita  — 200
— permissões de uso —
ok    admin de outra empresa: GET recusado  — 403
ok    admin de outra empresa: POST recusado  — 403
ok    admin de outra empresa: DELETE recusado  — 403
ok    não libera a conexão a usuário de outra empresa  — 400
ok    libera a quem é da mesma empresa  — 200
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_conexao_sheets.py</code>: ok</summary>

```
— salvar —
ok    Sheets sem credencial: recusa em vez de salvar algo que não sincroniza  — 400
ok    credencial sem chave privada: recusa  — 400
ok    salva com a credencial  — 200
ok    a credencial vai CIFRADA para o banco
ok    a resposta não devolve a credencial, só diz que ela existe
— listar —
ok    a listagem não traz a credencial  — [{"id":"cx1","created_at":"2026-10-03","nome":"Planilha do banco","tipo":"sheets","sheets_id":"1AbC","sheets_aba":"Deved
— sincronizar e testar com a credencial salva —
ok    a sincronização lê a planilha com a credencial decifrada
ok    testar a conexão salva usa a credencial guardada, sem colar de novo  — 503
ok    outra empresa não usa a credencial  — 403
— conexões antigas, salvas sem credencial —
ok    a sincronização diz o que falta, em vez de um erro do Google  — Conexão Sheets salva sem a credencial da conta de serviço. Edite a conexão e cole o JSON da credencial.
ok    dá para completar a credencial pela edição, cifrada  — 200
ok    e então ela sincroniza
— banco sem a coluna nova —
ok    diz qual migração rodar  — {"detail":"O banco ainda não tem onde guardar a credencial do Google: rode backend/sql/migracao_conexoes_sheets.sql no Supabase."}
— apagar —
ok    admin de outra empresa não apaga  — 403
ok    COMANDO apaga a de qualquer empresa
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_erros_internos.py</code>: ok</summary>

```
— exceção não tratada —
ok    responde 500  — 500
ok    a senha não vai na resposta  — {"detail":"Erro interno. Se persistir, informe o código ao suporte: 86c41719","c
ok    o host interno também não
ok    nem o nome da exceção
ok    a resposta traz um código curto, repetido na mensagem  — 86c41719
ok    e o mesmo código está no log  — 1 evento(s)
ok    o log guarda o tipo do erro  — RuntimeError = chegou não tratada, pelo middleware; HTTPException = pelo handler
ok    e o traceback completo  — é ele que responde 'onde quebrou'
ok    mas a senha foi mascarada no próprio log  — connection to db.interno.acme:5432 refused, password=***
ok    sabe quem chamou  — u-42 / banco_alfa
ok    e qual rota  — /_teste/erro
— o navegador consegue ler? —
ok    o 500 sai com cabeçalho CORS  — sem isto o navegador mostra 'Failed to fetch' e o código não chega
ok    e origem desconhecida continua sem CORS  — a lista de permitidas não mudou
— controle: o handler comum de Exception —
ok    um handler comum de Exception devolve 500 SEM cabeçalho CORS  — é a premissa do módulo: sem isto o navegador esconde o corpo
— HTTPException(500) com detail vazando —
ok    o texto da exceção deixa de sair  — {"detail":"Erro interno. Se persistir, informe o código ao suporte: 8aa87010","c
ok    e vai para o log, com a credencial da URL mascarada  — Erro na análise: postgresql://***:***@db.interno.acme:5432/p
ok    o traceback encadeado mostra a causa original  — o `raise ... from` implícito preserva o erro de dentro
— o que não mudou —
ok    4xx de validação passa intacto  — {"detail":"Senha fraca: use letras e números."}
ok    503 do banco do cliente passa intacto  — o assistente de conexão precisa mostrar por que falhou
ok    e nenhum deles é registrado como erro interno
ok    401 segue 401
— CPF no caminho —
ok    o CPF da URL não vai para o log  — /_teste/contato/{cpf}
ok    vai o modelo da rota, não o caminho real  — /_teste/contato/{cpf}
— mascaramento —
ok    mascara CPF formatado  — titular ***CPF*** não encontrado
ok    mascara CPF só dígitos  — cpf=***CPF*** sem feedback
ok    mascara senha chave=val  — falha com password=*** no host
ok    mascara senha em pt  — senha: *** inválida
ok    mascara URL com senha  — postgresql://***:***@db:5432/x
ok    mascara token bearer  — Authorization: ***
ok    mascara api key  — api_key=*** caiu
ok    não mexe em texto comum: 'Erro na linha 42 do arquivo'
ok    não mexe em texto comum: 'score 61.2 e valor 4821.55'
ok    não mexe em texto comum: '12345 devedores'
ok    não mexe em texto comum: 'protocolo 1234567890'
— o log —
ok    configurar o log duas vezes não duplica as linhas
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_limite.py</code>: ok</summary>

```
— janela deslizante —
ok    deixa passar até o máximo
ok    recusa a seguinte e diz quanto esperar  — 601 s
ok    a espera é até a MAIS ANTIGA sair da janela, não a janela inteira  — 501 s (esperado ~501)
ok    passada a espera, libera
ok    outra chave tem cota própria
ok    dentro da janela ainda recusa
ok    e a janela DESLIZA: não espera o bloco inteiro zerar
ok    com 8 threads disputando, passam exatamente 100 de 400  — passaram 100
ok    tokens inventados não fazem a memória crescer sem fim  — 50 chaves
ok    e, estourado o teto, chave nova continua sendo limitada  — o contrário desligaria o freio justamente sob inundação
— regras e rotas reais —
ok    POST /analisar existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /analisar/db existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /backtest existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /listar-tabelas existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /testar-db existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /ajuda/duvidas existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /ajuda/buscar existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    GET /empresa/marca existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /comando/treino existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    POST /feedback/lote existe de verdade  — senão a regra ficaria lá sem proteger nada
ok    e há regras suficientes para o que interessa
— no app real —
ok    as primeiras 20 chegam à rota (422 de validação, sem stub nenhum)  — {422}
ok    a seguinte é recusada com 429  — 429
ok    com Retry-After  — 600
ok    e uma mensagem que o usuário entende  — Muitas tentativas de conexão. Aguarde 600 s.
ok    o 429 sai COM cabeçalho CORS  — sem isto o navegador mostra 'Failed to fetch' em vez de 'aguarde 40 s'
ok    e não é registrado como erro interno  — 429 é comportamento, não falha
ok    outro usuário não é afetado  — cada um tem a própria cota
ok    /listar-tabelas divide o balde com /testar-db  — senão bastaria alternar entre as duas para dobrar a cota
ok    rota sem regra nunca é limitada  — {200}
ok    sem credencial não vira 429: a rota recusa como sempre  — {403}
ok    credencial que não é JWT também é limitada
ok    e outra credencial tem cota própria
— portão de simultâneas —
ok    a segunda, com o portão ocupado, é recusada  — 429
ok    com Retry-After
ok    e a recusa do portão NÃO gasta cota de taxa  — 1 marca(s): só a da primeira. Gastar puniria quem só quer a vez
ok    a primeira termina normalmente
ok    terminada a primeira, a vaga volta
ok    depois de três análises que quebraram, ainda aceita a próxima  — sem o finally o sistema recusaria análise para sempre
ok    regra sem 'pesada' não passa pelo portão  — pico simultâneo: 6
— esqueci a senha —
ok    a resposta é a MESMA com e sem limite  — um 429 aqui revelaria que o e-mail existe
ok    mas só 3 e-mails saem por hora para o mesmo endereço  — saíram 3
ok    maiúscula e espaço não contornam o limite
ok    outro endereço não é afetado
ok    martelar um endereço não bloqueia a redefinição dos outros  — o teto global só conta quando o do e-mail deixou passar
ok    e há um teto global por hora  — saíram 200
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_escopo_carteira.py</code>: ok</summary>

```
/feedbacks/status            alheia=403 BLOQUEADA  |  própria=200 ok
/performance                 alheia=403 BLOQUEADA  |  própria=200 ok
/performance/pagamentos      alheia=403 BLOQUEADA  |  própria=200 ok
RESULTADO: todos os três protegidos
```

</details>

<details><summary><code>test_auditoria_acesso.py</code>: ok</summary>

```
ok    operador não lê a auditoria
ok    admin lê  — 200
ok    e só da própria empresa  — [{'id': 1, 'empresa_id': 'alfa', 'acao': 'usuario_criado'}]
ok    comando lê
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_varredura_contas.py</code>: ok</summary>

```
— 1. senha trocada derruba as outras sessões —
ok    logado nos dois
ok    quem trocou recebe um token novo e continua dentro
ok    a outra sessão (ou um token roubado) cai
ok    e não dá para renová-la
ok    token emitido antes desta versão (sem a marca) também cai
ok    redefinir pelo link mata também os outros links do mesmo e-mail
ok    e derruba as sessões abertas
— 2. excluir a própria conta —
ok    o cadastro sai
ok    o histórico de contatos fica, sem o nome dela
ok    a conexão com o banco do cliente continua com a empresa
ok    o nome sai das dúvidas
ok    fica na auditoria, sem o e-mail
ok    o único COMANDO não se exclui  — 400
— 3. auditoria sem CPF inteiro —
ok    confirmar pagamento audita só o final do CPF
— 4. pedido do titular alcança feedback com o nome da empresa —
ok    o feedback gravado como 'Banco Alfa' perde o CPF  — {"ok":true,"anonimizadas":{"predicoes":1,"feedbacks":1,"contatos":0,"recomendacoes":0},"total":2}
ok    o de outra empresa não é tocado
— 5. mover usuário entre empresas —
ok    id da empresa em minúscula, e-mail sem diferença de caixa  — goias_bank
ok    fica na auditoria
ok    remover também
— 6. logo da empresa —
ok    HTML com nome .png é recusado  — 400
ok    PNG de verdade sobe com o tipo do conteúdo, não o declarado  — [{'content-type': 'image/png', 'upsert': 'true'}]
— 7. cor da empresa —
ok    cor fora de #rrggbb é recusada
ok    #rrggbb passa
— 8. chaves de API —
ok    admin não cria chave
ok    COMANDO cria a chave da alfa
ok    o banco guarda só o hash
ok    a chave autentica
ok    a listagem não traz chave nem hash
ok    revogada, para de autenticar na hora
ok    criação e revogação na auditoria
RESULTADO: tudo certo
```

</details>

<details><summary><code>test_agente_manipulacao.py</code>: ok</summary>

```
ok test_saida_barrada
ok test_saida_normal_passa
ok test_entrada_de_seguranca_por_regra
ok test_sofrimento_e_manipulacao
ok test_marcador_forjado_nao_chega_cru_na_ia
```

</details>

<details><summary><code>test_agente_telegram.py</code>: ok</summary>

```
— webhook: quem pode chamar —
ok    sem o segredo: 403
ok    segredo errado: 403
ok    sem configuração: 503, nunca aceita segredo vazio
[Telegram] sem_vinculo em 0.0s
ok    segredo certo: 200
ok    chat sem vínculo recebe só a instrução  — Para falar com o assistente, abra o link
ok    corpo inválido: 400
— convite —
ok    operador não gera convite
ok    devedor de outra empresa: 404
ok    admin recebe o link do bot  — {'codigo': 'ff0dc333773e4b59bcf24014060bdef23mBiUbLzMZPk', 'expira_em': '2026-11-08T21:17:
ok    o caso guarda só o hash do segredo
ok    o código cabe no limite do Telegram (64)  — 44
— vínculo —
[Telegram] convite_invalido em 0.0s
ok    código adulterado não liga
ok    e nada ficou ligado
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 13.7s
ok    convite certo liga o chat e o agente abre com a mesma abordagem do Mizan  — [('555', 'Olá, Maria! Aqui é o assistente virtual de Banco Demonstração. Tudo bem? Antes de seguirmos, posso confirmar se estou falando com você? É um assunto d
ok    a abertura fica no caso (o chat do Mizan mostra a mesma conversa)  — [{'empresa_id': 'goias', 'caso_id': 'ff0dc333-773e-4b59-bcf2-4014060bdef2', 'direcao': 'saida', 'texto': 'Olá, Maria! Aqui é o assistente virtual de Banco Demon
ok    a conversa recomeça na abertura do Telegram
ok    a tela vê "ligado", sem o chat_id  — {'configurado': True, 'ligado': True, 'desde': '2026-11-01T21:17:13.325150+00:00', 'bloqueado': False, 'convite_pendente_ate': None, 'tentativa_outro_chat_em': None}
[Telegram] ja_ligado em 0.0s
ok    a mesma pessoa abre o link de novo: "você já está conectado"
[Telegram] ja_ligado em 0.0s
ok    /start sem código num chat ligado: "já conectado"
[Telegram] sem_vinculo em 0.0s
ok    /start sem código num chat sem vínculo: pede o link
[Telegram] convite_usado em 0.0s
ok    o convite vale uma vez: outro chat não rouba o vínculo
ok    e a segunda pessoa ouve que cada um precisa do próprio link
ok    a equipe vê no caso que alguém tentou usar o link em outro Telegram
ok    gerar convite com o chat ligado avisa a tela (para confirmar antes)
ok    convite vencido não liga
ok    um convite novo substitui o pendente
[Telegram] convite_substituido em 0.0s
ok    o link substituído não liga e diz para usar o mais novo
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 0.2s
ok    novo convite religa o caso a outro chat e solta o anterior
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 0.1s
ok    e volta para o primeiro chat com outro convite
— desligar o Telegram do caso —
ok    operador não desliga
ok    admin desliga
[Telegram] sem_vinculo em 0.0s
ok    depois de desligado, o chat só recebe a instrução
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 0.1s
— conversa —
[Telegram] mensagem em 0.1s
ok    mensagem aceita
ok    a resposta do agente chegou ao Telegram do devedor  — [('555', 'Obrigado, Maria. Quanto você consegue pagar por mês?')]
[Telegram] repetido em 0.0s
ok    o mesmo update reenviado pelo Telegram não duplica a resposta
ok    o caso registra a entrada e a resposta  — ['saida', 'entrada', 'saida']
ok    o agente não se apresenta de novo: a abertura já fez isso  — [('555', 'Obrigado, Maria. Quanto você consegue pagar por mês?')]
ok    a identidade foi confirmada pelo Telegram
[Telegram] sendChatAction falhou: gaierror
ok    com o Telegram ligado, a tela não escreve pelo devedor (a conversa é uma só)  — 409
— Telegram novo no mesmo caso —
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 0.1s
ok    outra pessoa ligou: a identidade precisa ser confirmada de novo
ok    e ela recebe a mesma abertura, não a resposta dada à outra pessoa  — [('4242', 'Olá, Maria! Aqui é o assistente virtual de Banco Demonstração. Tudo bem? Antes de seguirmos, posso confirmar se estou falando com você? É um assunto 
ok    a IA lê só a conversa a partir daí, sem o que a outra pessoa disse  — [{'empresa_id': 'goias', 'caso_id': 'ff0dc333-773e-4b59-bcf2-4014060bdef2', 'direcao': 'saida', 'texto': 'Olá, Maria! Aqui é o assistente virtual de Banco Demon
[Telegram] sendChatAction falhou: gaierror
[Telegram] sendChatAction falhou: gaierror
[Telegram] vinculado em 0.1s
[Telegram] ja_ligado em 0.0s
ok    a mesma pessoa com um convite novo: nada recomeça  — [('555', 'Você já está conectado. Pode escrever sua mensagem aqui.')]
— o que é ignorado e o que não é texto —
[Telegram] ignorado em 0.0s
[Telegram] ignorado em 0.0s
[Telegram] ignorado em 0.0s
[Telegram] ignorado em 0.0s
ok    grupo, bot e update sem mensagem são ignorados
[Telegram] midia em 0.0s
[Telegram] midia em 0.0s
ok    foto ou áudio: avisa que só lê texto, uma vez (sem repetir a cada foto)  — [('555', 'Por enquanto eu só consigo ler mensagens de texto. Pode escrever o que precisa?')]
— entrega com falha e reenvio —
[Telegram] mensagem em 0.0s
ok    falha de rede não derruba o atendimento
ok    a mensagem continua registrada no caso
[Telegram] sendChatAction falhou: gaierror
[Telegram] mensagem em 0.0s
ok    na rodada seguinte, o que tinha falhado vai antes, na ordem  — [('555', 'Posso explicar sim.'), ('555', 'Os juros já estão no valor.')]
[Telegram] mensagem em 0.0s[Telegram] sendChatAction falhou: gaierror
ok    e nada é entregue duas vezes  — [('555', 'Certo.')]
— devedor bloqueou o bot —
[Telegram] mensagem em 0.0s
[Telegram] sendChatAction falhou: gaierror
ok    o caso fica marcado como bloqueado
ok    e não se tenta mais enquanto ele não voltar
[Telegram] mensagem em 0.0s
[Telegram] sendChatAction falhou: gaierror
ok    voltou a escrever: desbloqueia e a resposta chega  — ['Que bom que voltou.']
ok    o que falhou com o bot bloqueado não chega atrasado  — ['Que bom que voltou.']
— atendente responde pelo chat do Mizan —
ok    enquanto o agente cuida do caso, a pessoa não fala por cima  — 409
[Telegram] sendChatAction falhou: gaierror
ok    a equipe assumiu o caso
ok    o devedor fica sabendo que agora fala com uma pessoa  — [('555', 'A partir de agora, uma pessoa da equipe vai continuar o seu atendimento por aqui.')]
ok    a resposta da pessoa é entregue  — 200
ok    e chega exatamente ao Telegram ligado ao caso  — [('555', 'A partir de agora, uma pessoa da equipe vai continuar o seu atendimento por aqui.'), ('555', 'Oi, sou do banco. Posso ajudar?')]
ok    fica registrada no caso, marcada como da pessoa
ok    o aviso de passagem também fica no caso
ok    lista de atendimentos: respondido, não espera  — [{'predicao_id': 'p1', 'nome': 'Maria das Dores', 'esperando': False, 'desde': '2026-11-01T21:17:27.996428+00:00', 'ultima_em': '2026-11-01T21:17:28.066434+00:00', 'telegram': True}]
[Telegram] mensagem em 0.0s
ok    o que o devedor responde aparece no chat do Mizan
ok    e o agente não responde por cima enquanto o caso está com a pessoa  — []
ok    e o caso aparece como esperando resposta da equipe
ok    mensagem vazia: 422
ok    outra empresa: 404
ok    outra empresa não vê os atendimentos
— sinal leve e digitando —
[Telegram] sendChatAction falhou: gaierror
[Telegram] mensagem em 0.0s
ok    chegou mensagem: o sinal muda (a tela recarrega sozinha)
ok    sem novidade, o sinal é o mesmo (a tela não recarrega à toa)
ok    outra empresa não vê nada
— devolver ao agente —
ok    ao devolver, o devedor sabe que o assistente voltou  — [('555', 'A partir de agora, uma pessoa da equipe vai continuar o seu atendimento por aqui.'), ('555', 'O assistente virtual voltou a acompanhar o seu atendimento. Pode escrever quando quiser.')]
[Telegram] mensagem em 0.0s
ok    o Telegram mostra "digitando…" assim que a mensagem chega  — ['555']
ok    o agente volta a responder, sem nada atrasado de antes da passagem  — [('555', 'Claro.')]
— agente desligado —
[Telegram] agente_desligado em 0.0s
[Telegram] repetido em 0.0s
[Telegram] agente_desligado em 0.0s
ok    a mensagem não se perde (e o reenvio do Telegram não duplica)  — ['Alguém aí?', 'Oi??']
ok    o devedor sabe que foi recebida, uma vez só  — [('555', 'Recebemos sua mensagem. O atendimento automático está pausado agora; uma pessoa da equipe vai responder por aqui.')]
— o /start some do chat —
ok    ao ligar, o bot apaga a mensagem "/start <código>"  — [('2121', 4321)]
— abertura: plano antes do convite e convite de madrugada —
ok    o plano abriu a conversa com o João antes do convite
ok    ao ligar, ele recebe a abertura que já estava no caso (sem duplicar no Mizan)  — [('2020', 'Olá, João! Aqui é o assistente virtual de Banco Demonstração. Tudo bem? Antes de seguirmos, posso confirmar se estou falando com você? É um assunto d
ok    abriu o convite às 2h: o agente responde na hora (foi a pessoa quem chamou)  — [('3030', 'Olá, Ana! Aqui é o assistente virtual de Banco Demonstração. Tudo bem? Antes de seguirmos, posso confirmar se estou falando com você? É um assunto do
— mensagens seguidas: uma resposta só, como no Mizan —
ok    mensagem que chega antes de o agente responder entra na mesma rodada  — {'acao': 'juntou', 'caso_id': 'd8fc55af-35dd-4400-8f1e-f6954ea9e0a0'}
ok    o reenvio de uma mensagem juntada não duplica
ok    três mensagens seguidas, uma resposta  — [('3131', 'Que bom, Ana! Como posso ajudar?')]
ok    o Mizan mostra as três juntas e a resposta  — [{'empresa_id': 'goias', 'caso_id': 'd8fc55af-35dd-4400-8f1e-f6954ea9e0a0', 'direcao': 'entrada', 'texto': 'oi\nsou eu sim\npode falar', 'trace_id': '351e9a1af46444e69452d653bdad897e', 'criado_em': da
— o que o Telegram grava durante a resposta não se perde —
ok    o agente não apaga o que o webhook gravou enquanto ele respondia
ok    desligado no meio da resposta: o chat continua desligado e nada é enviado  — []
0 falha(s)
```

</details>

<details><summary><code>test_revisao_api.py</code>: ok</summary>

```
— login: e-mail normalizado e IP real —
ok    maiúsculas e espaços contam no mesmo limite do e-mail  — 429
ok    outro IP (o primeiro do X-Forwarded-For) HERDA o bloqueio do e-mail  — 429
ok    primeiro_ip lê o cliente, não o proxy
— esqueci a senha com maiúscula —
ok    o token é pedido para o e-mail normalizado  — ['bia@teste.com']
— marca pública limitada por IP —
ok    o mesmo IP passa de 60 consultas e leva 429  — [200, 200, 429]
ok    outro IP segue consultando  — 200
— primeiro admin sem senha fixa em produção —
ok    sem ADMIN_SENHA: senha aleatória  — aleatoria
[Auth] ADMIN_SENHA fraca: ignorada; criada senha aleatória.
ok    ADMIN_SENHA fraca é ignorada
— carteiras pela empresa —
ok    admin vê só as carteiras da empresa  — {'c-alfa2', 'c-alfa'}
ok    e o total vem no cabeçalho  — 2
ok    a lista pagina
ok    meus=true devolve a última carteira da própria pessoa  — [{'id': 'c-alfa2', 'empresa_id': 'alfa', 'usuario_id': 'u-adm-a', 'created_at': '2026-10-02'}]
ok    e não traz a de outra pessoa da mesma empresa  — [{'id': 'c-alfa3', 'empresa_id': 'alfa', 'usuario_id': 'u-op-a', 'created_at': '2026-10-04'}]
ok    quem está sem empresa não cai no filtro por usuario_id  — 403
ok    admin da alfa não abre carteira da beta  — 403
ok    COMANDO abre qualquer uma  — 200
— conexões só pela empresa —
ok    admin da beta não vê a conexão da alfa
ok    quem criou a conexão e mudou de empresa não a usa mais
— COMANDO não grava contato —
ok    COMANDO sem empresa recebe 403  — 403
— cache de desempenho: dono antes, empresa na chave —
ok    o dono lê (e enche o cache)
ok    outra empresa com o mesmo carteira_id não recebe o cache  — 403
ok    pagamentos: registrado_em inteiro, com fuso  — [{'cpf': '11111111111', 'nome': 'Ana Teste', 'valor_divida': 1000.0, 'score': 45.0, 'pagou': True, 'valor_recuperado': 300, 'data_pagamento': '2026-10-10', 'registrado_por': 'adm', 'registrado_em': '2026-10-10T15:04:05.123+00:00'}]
ok    pagamentos: dono conferido antes do cache  — 403
ok    operador não vê nome e CPF de quem pagou
ok    a chave do cache leva a empresa  — ['perf:c-alfa:alfa', 'pagamentos:c-alfa:alfa']
— /feedbacks/status: mesmo conserto de cache —
ok    o dono lê o status
ok    registrado_em inteiro
ok    outra empresa não lê o cache do dono  — 403
ok    chave com a empresa  — ['fb_status:c-alfa:alfa']
— hora do 'já confirmado' em Brasília —
ok    UTC vira hora de Brasília
ok    sem fuso é tratado como UTC
ok    vazio fica vazio
— /feedback/lote do COMANDO —
ok    sem empresa escolhida: 400  — 400
ok    e nada gravado (antes ia com o nome do usuário como empresa)
ok    com a empresa: grava nela e liga à predição dela  — {'cpf': '11111111111', 'pagou': True, 'valor_recuperado': 0.0, 'empresa': 'beta', 'predicao_id': 'p-b1', 'id': 'feedbacks-2', 'created_at': '2026-10-18T12:00:00+00:00'}
ok    admin ignora o empresa_id da query (vale a dele)
— confirmar pagamento do COMANDO —
ok    sem empresa: 400  — 400
[Confirmar] Tentativa — CPF: ***11, role: comando
[Confirmar] Gravando Supabase — CPF: ***11, empresa: beta, predicao_id: p-b1
[Confirmar] Supabase gravado com sucesso — feedback_id: feedbacks-1
[Confirmar] SUCESSO — CPF: ***11, id: feedbacks-1, writeback: None
ok    grava na beta e liga à predição da beta  — {"ok":true,"feedback_id":"feedbacks-1","registrado_por":"u-cmd","registrado_em":"2026-10-18T12:00:00+00:00","writeback":null}
ok    invalida o cache da beta  — ['fb_status:beta', 'pagamentos:beta', 'perf:beta', 'fb_status:c-beta', 'pagamentos:c-beta', 'perf:c-beta']
[Confirmar] Tentativa — CPF: ***11, role: comando
ok    idempotência na empresa escolhida: a segunda vez é 409  — 409
ok    a mensagem mostra a hora de Brasília (12:00 UTC = 09:00)  — Pagamento já confirmado por u-cmd em 2026-10-18 09:00.
[Confirmar] Tentativa — CPF: ***11, role: comando
[Confirmar] Gravando Supabase — CPF: ***11, empresa: alfa, predicao_id: p-a1
[Confirmar] Supabase gravado com sucesso — feedback_id: feedbacks-2
[Confirmar] SUCESSO — CPF: ***11, id: feedbacks-2, writeback: None
ok    o pagamento da beta não bloqueia o da alfa  — 200
— contatos na análise: só da empresa —
ok    a consulta filtra a empresa  — [[('eq', 'empresa_id', 'alfa'), ('in', 'cpf', ['11111111111'])]]
ok    sem empresa, não consulta contatos de ninguém  — []
ok    data vazia conferida com notna
— operador usando conexão salva —
ok    operador: vale a consulta salva  — SELECT cpf, valor FROM devedores
ok    admin pode trocar a consulta
ok    operador não reaponta a carteira da conexão  — 200 None
ok    admin reaponta
ok    falha ao religar fica registrada (não some num except: pass)  — [analisar/db] não religou a conexão cx-alfa à carteira c-nova: RuntimeError
— simulador do COMANDO com a política da empresa —
ok    a política vem da empresa do devedor, não da vazia  — ['beta']
— acurácia: um limiar só —
ok    LIMIAR_ACERTO_SCORE = 50
ok    corte em 50 para os dois lados
ok    /performance e /admin/modelos usam _acertou
ok    score 45 que pagou conta como erro em /performance  — 0.0
— feedback automático com empresa —
ok    a coluna 'pagou' grava fb_row['empresa']
— db_sync liga só na empresa —
[DB Sync] 1 pagamentos sincronizados
ok    empresa alfa: liga em p-a1  — {'cpf': '11111111111', 'pagou': True, 'valor_recuperado': 5.0, 'empresa': 'alfa', 'predicao_id': 'p-a1', 'id': 'feedbacks-1', 'created_at': '2026-10-18T12:00:00+00:00'}
[DB Sync] 1 pagamentos sincronizados
ok    empresa (nenhuma): liga em None  — {'cpf': '11111111111', 'pagou': True, 'valor_recuperado': 5.0, 'id': 'feedbacks-1', 'created_at': '2026-10-18T12:00:00+00:00'}
— _empresa_da_carteira única —
ok    uma definição só
ok    lê a empresa e aceita id vazio
ok    erro do banco sobe
[carteira] não leu a empresa da carteira c-beta: RuntimeError
ok    a variante tolerante devolve vazio
— DELETE /auth/me pede a senha —
ok    sem corpo não apaga  — 422
ok    senha errada: 401 e a conta fica  — 401
ok    senha certa apaga  — 200
— retorno da passagem com caso ocupado —
ok    caso ocupado vira 409, não 500  — 409
RESULTADO: tudo certo
```

</details>

<details><summary><code>pip-audit</code>: ok</summary>

```
No known vulnerabilities found
```

</details>

<details><summary><code>npm audit --omit=dev</code>: ok</summary>

```
found 0 vulnerabilities
```

</details>
