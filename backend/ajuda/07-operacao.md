# Operação: arquivos, conexões, pessoas e privacidade

## enviar-carteira
titulo: Como enviar uma carteira (arquivo)
perfis: operador, admin, comando
telas: Análise
perguntas:
- como enviar a carteira
- quais colunas o arquivo precisa ter
- quais formatos de arquivo aceita
- qual o tamanho máximo do arquivo
- por que o arquivo foi recusado
- o sistema reconhece o nome da minha coluna
- o que acontece quando falta uma coluna opcional
- quais colunas o arquivo da carteira precisa ter
- qual o formato e o tamanho máximo do arquivo
- o sistema reconhece os nomes das minhas colunas
curta: Envie CSV ou Excel com pelo menos CPF, valor da dívida e dias em atraso. O sistema reconhece vários nomes de coluna e preenche o que faltar com valores padrão.
calculo: Obrigatórias: cpf, valor_divida e dias_em_atraso. Opcionais reconhecidas: nome, produto, status, uf, renda_estimada e despesas_mensais; uma coluna pagou (com valor_recuperado) registra os pagamentos junto. Sem a coluna, o padrão é: nome "Desconhecido", produto "pessoal", status "inadimplente", UF "SP" e renda 0. O limite é de 25 MB por arquivo.
fazer: Revise o mapeamento e as colunas reconhecidas antes de analisar. Quanto mais completas as colunas, mais fiel o score.
cuidado: Os padrões não são dados do devedor: UF "SP" e produto "pessoal" entram no modelo como se fossem verdade. Renda ausente vira 0. Informe essas colunas sempre que puder.
fontes:
- backend/main.py::COLUNAS_OBRIGATORIAS
- backend/main.py::COLUNAS_COM_DEFAULT
- backend/main.py::CAMPO_ALIASES
- backend/limite.py::TETOS_CORPO
constantes:
- backend/limite.py::MB = 1048576

## conexao-com-banco
titulo: Conexão com banco de dados e Google Sheets
perfis: operador, admin, comando
telas: Análise
perguntas:
- como conectar meu banco de dados
- quais bancos são aceitos
- a conexão altera meus dados
- por que o operador não vê minha senha
- como liberar uma conexão para um operador
- o que é sincronização automática
- por que a conexão sqlite não funciona
- como ligo o sistema ao banco de dados da empresa
- quais bancos de dados são aceitos
- como libero uma conexão para um operador
curta: O administrador cadastra a conexão (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle ou Google Sheets) e libera para os operadores. A senha fica criptografada e nunca volta para a tela.
calculo: Só consultas SELECT são aceitas. A análise direta de um banco lê no máximo 50.000 linhas. A conexão salva pode ser sincronizada a cada 1, 4 ou 24 horas. O operador só usa conexões salvas e liberadas para ele, e sempre contra o servidor cadastrado.
fazer: O administrador cria a conexão em Análise > banco de dados e libera operadores na tela de Usuários. Se precisar de mais de 50.000 linhas, exporte para arquivo.
cuidado: A conexão é somente leitura, a menos que o administrador ative a escrita de volta. SQLite só funciona em instalação local, não no serviço hospedado. Endereços internos da rede são recusados. Conexões Google Sheets salvas não guardam as credenciais da conta de serviço, então a sincronização (manual e automática) não as atende: para Sheets, cole as credenciais na própria análise ou envie um arquivo.
revisar: achado D12 do mapa do sistema (Sheets salvo não sincroniza).
fontes:
- backend/main.py::_conexao_usavel
- backend/main.py::ConexaoDB
- backend/main.py::_validar_destino_externo

## usuarios-e-papeis
titulo: Usuários e papéis (operador, administrador, COMANDO)
perfis: admin, comando
telas: Usuários
perguntas:
- quais são os papéis do sistema
- quem pode criar usuários
- o que o administrador pode fazer
- o que o operador não pode fazer
- como desativar um usuário
- como promover um operador
- o que é o perfil comando
- por que não consigo criar um usuário
- o que cada papel pode fazer no sistema
- quem pode criar e desativar usuários
- qual a diferença entre operador administrador e comando
curta: Operador trabalha a fila; administrador gerencia a equipe e os dados da empresa; COMANDO é da plataforma e vê todas as empresas.
calculo: Operador: analisa, vê a fila, registra contatos. Administrador: tudo isso mais precificação, ciclo, resultados, pagamentos, conexões, retenção, auditoria e ativar ou desativar usuários da própria empresa. COMANDO: todas as empresas, mais criar usuários, mudar papéis, treinar modelos e ver as telas de aprendizado. Só o COMANDO cria usuários e altera papéis, e o último COMANDO ativo não pode ser rebaixado nem desativado.
fazer: Para incluir alguém na sua equipe, peça ao COMANDO. O administrador pode desativar quem sair.
cuidado: O papel e a empresa de cada pessoa vêm do cadastro a cada chamada, não do token de login: mudar o papel vale na hora.
fontes:
- backend/main.py::auth_registrar
- backend/main.py::auth_alterar_role
- backend/auth.py::_ultimo_comando_ativo

## senha-e-sessao
titulo: Senha, sessão e esqueci a senha
perfis: operador, admin, comando
telas: Conta
perguntas:
- como trocar a senha
- esqueci a senha
- quantos caracteres tem a senha
- quanto tempo dura a sessão
- por que o login foi bloqueado
- o link de redefinição expirou
- como troco ou recupero minha senha
- quanto tempo fico logado
- por que o link de redefinição de senha não funciona
curta: A senha tem no mínimo 8 caracteres. A sessão dura 7 dias. O link de redefinição vale 1 hora.
calculo: Troca em "Alterar senha". Esqueci a senha envia um link ao e-mail, com limite de 3 pedidos por hora por endereço, e a resposta é sempre a mesma exista ou não a conta. Após 5 tentativas erradas de login, há bloqueio de 15 minutos.
fazer: Se o link expirou, peça outro. Se não chegar, confira o spam e se o e-mail é o cadastrado.
cuidado: A mensagem é igual para e-mails que não existem: é proposital, para não revelar quem tem conta.
fontes:
- backend/auth.py::TOKEN_EXPIRE
- backend/main.py::auth_esqueci_senha
constantes:
- backend/auth.py::TOKEN_EXPIRE = 604800
- backend/main.py::_RATE_MAX = 5

## retencao-de-dados
titulo: Retenção de dados (LGPD)
perfis: admin, comando
telas: Retenção
perguntas:
- por quanto tempo o sistema guarda o cpf
- o que é anonimizar
- como definir o prazo de retenção
- o que é executar agora
- o modelo continua aprendendo depois da anonimização
- anonimizar apaga a linha
- o que é a prévia da retenção
- por quanto tempo o sistema guarda cpf e nome
- o que quer dizer anonimizar os dados
- como configuro o prazo de retenção
curta: Você escolhe por quanto tempo guardar o CPF e o nome dos devedores. Passado o prazo, eles são retirados da linha e o resto fica para o modelo continuar aprendendo.
calculo: Prazo de 30 a 3.650 dias. Anonimizar zera cpf e nome (e, nos contatos, a observação) e marca a data; as variáveis e o resultado ficam. Nada roda sem prazo configurado: a prévia mostra o que aconteceria. "Executar agora" aplica o prazo escolhido.
fazer: Escolha um prazo compatível com o fim da cobrança (ciclo encerrado) e com as obrigações do banco; rode a prévia antes.
cuidado: Tirar CPF e nome de uma linha que mantém UF, valor e dias de atraso é despersonalização forte, não prova matemática de irreversibilidade. Quem precisa de garantia formal deve pedir o expurgo, que apaga a linha.
fontes:
- backend/model/retencao.py::patch_anonimo
- backend/model/retencao.py::de_config
constantes:
- backend/model/retencao.py::MINIMO_DIAS = 30
- backend/model/retencao.py::MAXIMO_DIAS = 3650

## pedido-do-titular
titulo: Pedido de um titular (direito de eliminação)
perfis: admin, comando
telas: Retenção
perguntas:
- um devedor pediu para apagar os dados dele
- como atender o pedido do titular
- lgpd artigo 18
- como eliminar o cpf de uma pessoa
- o que acontece quando elimino um cpf
- como atender quando o devedor pede a eliminação dos dados dele
- o que a lgpd pede num pedido de titular
- como eliminar um cpf do sistema
curta: Informe o CPF do titular: o sistema retira a identificação de todas as linhas dele na sua empresa, em qualquer formato de CPF.
calculo: Procura o CPF formatado, só dígitos, com zeros à esquerda e sem zeros, em predições, feedbacks, contatos e recomendações da empresa, e anonimiza o que achar.
fazer: Guarde o registro do pedido (a ação fica na auditoria) e responda ao titular.
cuidado: Atua só na empresa de quem faz o pedido. O CPF pode existir em outras empresas clientes, que são controladoras do próprio dado.
fontes:
- backend/main.py::rota /retencao/titular

## auditoria-de-acoes
titulo: Auditoria (quem fez o quê)
perfis: admin, comando
telas: Auditoria
perguntas:
- como ver quem fez uma ação
- o que a auditoria registra
- como filtrar a auditoria
- quem alterou o papel de um usuário
- quem confirmou um pagamento
- onde vejo quem fez cada ação no sistema
- o que fica registrado na auditoria
- como filtrar o histórico de ações
curta: Registra as ações sensíveis (criar usuário, mudar papel, confirmar pagamento, treinar ou ativar modelo etc.), com quem fez e quando.
calculo: Cada ação grava quem, quando, em qual empresa, qual entidade e detalhes sem dado pessoal. O administrador vê a da própria empresa; o COMANDO vê todas. Filtros por entidade, usuário, ação e período.
fazer: Use para conferir mudanças de papel, pagamentos confirmados e ativações de modelo.
cuidado: Só ações que o sistema audita aparecem; consultas e leituras não são registradas.
fontes:
- backend/main.py::_registrar_auditoria
- backend/main.py::listar_auditoria

## perfil-da-empresa
titulo: Perfil da empresa (nome, cor e logo)
perfis: admin, comando
telas: Usuários
perguntas:
- como mudar o logo da empresa
- como mudar a cor do sistema
- como mudar o nome de exibição
- qual o tamanho da foto
- link de login com a marca da empresa
- como mudo o logo e a cor da empresa
- qual o tamanho da imagem do logo
- como fazer o login mostrar a marca da empresa
curta: O administrador define nome, cor principal e logo da empresa, que aparecem no sistema e na tela de login pelo link da empresa.
calculo: A foto aceita jpg, png, webp ou gif, até 5 MB. O link de login com a marca usa o endereço do sistema com o parâmetro ?empresa=identificador.
fazer: Compartilhe com a equipe o link com ?empresa= para que a marca apareça antes do login.
cuidado: A marca só aparece pelo link: digitar o e-mail não mostra a empresa, de propósito, para não revelar quem tem conta.
fontes:
- backend/main.py::rota /empresa/foto
- backend/main.py::get_empresa_config_publica

## como-configurar-premissas
titulo: Como configurar as premissas da empresa
perfis: admin, comando
telas: Premissas
perguntas:
- onde configuro a comissão
- onde configuro a cessão
- como mudar o critério da fila
- como mudar a recuperação se pagar
- onde mudo o buffer da margem
- onde ficam as premissas da empresa
- o que são premissas
- onde ajusto a comissão e a cessão
- onde configuro comissão cessão e critério da fila
- como ajusto a margem e o teto de parcela
- como volto uma premissa ao padrão
- as premissas mudam as carteiras que já analisei
curta: Em Premissas (menu lateral) o administrador define comissão do escritório, valor de cessão, quanto entra quando o devedor paga, critério da fila, folga da margem e teto da parcela.
calculo: Cada campo vazio vale o padrão: recuperação se pagar 100%, critério por valor esperado, folga 30% e teto de parcela 100%; comissão e cessão não têm padrão e, sem elas, o sistema avisa em vez de escolher um número. Os valores são validados (por exemplo, percentuais entre 0 e 100) e cada mudança fica na auditoria, com o valor antes e depois. Folga e teto da parcela valem na hora, nas propostas; as demais valem para as próximas análises, e as carteiras já analisadas não mudam. O COMANDO escolhe a empresa no alto da tela.
fazer: Preencha só o que o contrato do banco define. Para voltar ao padrão, apague o campo e salve.
cuidado: Um valor inválido em qualquer campo impede salvar todos, para não gravar só uma parte. Cada campo tem um "O que é isto?" que abre a explicação.
fontes:
- backend/model/premissas.py::PREMISSAS
- backend/main.py::rota /empresa/premissas
- frontend/src/pages/Premissas.jsx::texto "Premissas"

## enviar-duvida
titulo: Enviar uma dúvida ao COMANDO
perfis: operador, admin, comando
telas: Ajuda
perguntas:
- como mando uma pergunta para o comando
- não achei a resposta na ajuda, e agora
- como falo com o suporte do sistema
- onde vejo a resposta da minha dúvida
- por que o menu ajuda tem um número
- posso colocar o cpf do devedor na dúvida
- quanto tempo demora a resposta do comando
- o administrador vê as dúvidas da equipe
curta: Na página Ajuda, se a busca não resolver, use "Pergunte ao COMANDO". A resposta aparece em "Minhas dúvidas", e o menu Ajuda mostra um número quando chegar.
calculo: A dúvida aceita até 2.000 caracteres e cada pessoa pode enviar até 10 por hora. O servidor retira CPF, CNPJ, telefone, e-mail e números longos antes de gravar. O COMANDO vê todas as dúvidas; o administrador vê, só para leitura, as da sua equipe; cada pessoa vê as suas. O número no menu some quando você abre a página Ajuda.
fazer: Diga o que você não entendeu e em que tela estava. A dúvida leva junto a tela de onde você veio.
cuidado: Nomes de pessoas não podem ser reconhecidos por regra e passam: não escreva nome de devedor. A busca só é guardada quando não achou resposta (sem seu nome nem empresa; veja "Buscas sem resposta"), e o que você ENVIA como dúvida é guardado com o seu nome e lido por pessoas. Não há prazo garantido para a resposta.
fontes:
- backend/main.py::rota /ajuda/duvidas
- backend/ajuda_duvidas.py::mascarar_pii
- backend/main.py::ajuda_duvidas_da_equipe

## responder-duvidas
titulo: Responder as dúvidas dos usuários (COMANDO)
perfis: comando
telas: Dúvidas
perguntas:
- como respondo uma dúvida de usuário
- onde ficam as dúvidas enviadas ao comando
- como corrijo uma resposta que já dei
- como transformo uma dúvida em resposta da ajuda
- o que significa sugerir para a central
- o que acontece quando aprovo uma sugestão
- por que o menu dúvidas tem um número
curta: Em Dúvidas, o COMANDO responde às perguntas dos usuários e, quando a resposta serve para todos, sugere que ela vire uma entrada da Central.
calculo: A fila mostra as abertas, da mais antiga para a mais nova; o número no menu é a quantidade de abertas. Corrigir uma resposta avisa de novo quem perguntou. "Sugerir para a Central" marca a resposta para revisão; "Aprovar" registra quem revisou, mas não publica nada: a entrada só passa a existir quando alguém a escreve em backend/ajuda e os testes do catálogo passam.
fazer: Responda em linguagem de operador e, se a mesma pergunta aparecer duas vezes, sugira para a Central: é assim que a busca melhora.
cuidado: A pergunta já vem sem CPF, CNPJ, telefone e e-mail, mas nomes podem ter passado: não copie dúvidas para fora do sistema. Respostas, sugestões e revisões ficam na auditoria, sem o texto.
fontes:
- backend/main.py::rota /comando/duvidas
- backend/main.py::comando_responder_duvida
- backend/main.py::comando_revisar_sugestao

## buscas-sem-resposta
titulo: Buscas sem resposta (COMANDO)
perfis: comando
telas: Dúvidas
perguntas:
- como sei o que as pessoas procuram e a ajuda não responde
- onde vejo as buscas sem resposta da ajuda
- o que significa isto não resolveu a minha dúvida
- o que quer dizer reapareceu depois de tratada
- como marco uma busca como tratada
- as buscas da ajuda ficam guardadas com meu nome
- por quanto tempo ficam guardadas as buscas sem resposta
curta: Na aba "Buscas sem resposta" de Dúvidas, o COMANDO vê as perguntas que a Central não soube responder, agrupadas e da mais repetida para a menos.
calculo: Entra no registro a busca em que a Central não teve certeza da resposta e a busca em que a pessoa clicou em "Isto não resolveu a minha dúvida". Perguntas que só diferem em acento, maiúscula, plural, ordem ou palavras de ligação formam um grupo. Cada pessoa gera no máximo um registro por pergunta por hora. Marcar como tratada vale para os registros que existem agora; se a pergunta voltar, o grupo reaparece com o aviso "reapareceu depois de tratada", sinal de que a resposta escrita não bastou. "Resposta mais próxima hoje" é a entrada do catálogo de maior similaridade, ponto de partida para escrever ou corrigir.
fazer: Comece pelas mais repetidas, escreva ou ajuste a entrada em backend/ajuda, rode os testes do catálogo e marque como tratada. Registros com mais de 180 dias podem ser apagados na própria aba.
cuidado: O registro guarda só o texto buscado (sem CPF, CNPJ, telefone e e-mail) e o perfil de quem buscou, sem nome, e-mail ou empresa. Nomes digitados no texto não podem ser reconhecidos por regra. Não há apagamento automático: a limpeza é feita por quem é do COMANDO.
fontes:
- backend/main.py::comando_lacunas_da_ajuda
- backend/ajuda_lacunas.py::agrupar
