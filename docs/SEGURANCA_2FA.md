# Verificação em duas etapas (2FA) e limite de login

## O que muda para quem usa

- **Administrador e COMANDO:** no próximo acesso depois da migração, entram com a senha e,
  antes de qualquer outra tela, configuram o 2FA:
  1. instalar um app autenticador (Google Authenticator, Microsoft Authenticator ou Authy);
  2. ler o QR code no app;
  3. digitar o código de 6 dígitos;
  4. guardar os 10 códigos de recuperação.

  Daí em diante, todo login pede a senha e o código do app.
- **Operador:** o 2FA é opcional. Ele liga no menu **Conta → Verificação em duas etapas**.
- **Perdeu o celular:** na tela do código, use "Perdi o celular: usar código de
  recuperação". Cada código vale uma vez. Para trocar de aparelho, use **Conta → Verificação
  em duas etapas → Trocar de celular**.
- **Perdeu o celular e os códigos:** o COMANDO redefine em **Usuários → botão 2FA** da
  pessoa, e ela configura de novo no próximo acesso.

## Como funciona (backend)

| Peça | Onde |
|---|---|
| Código TOTP (RFC 6238, 6 dígitos, 30 s), códigos de recuperação, regra de quem é obrigado | `backend/dois_fatores.py` |
| Rotas `/auth/login/2fa` e `/auth/2fa/*`, verificação central em `_usuario_autenticado` | `backend/main.py` |
| Limite de tentativas no banco (sobrevive a reinício) | `backend/limite_login.py` |
| Migração (colunas do 2FA e tabela `login_tentativas`) | `backend/sql/migracao_seguranca_2fa.sql` |
| Testes (vetores do RFC, fluxo completo e limite) | `backend/test_dois_fatores.py`, também na prova de segurança |

**Segredo e códigos**
- O segredo fica cifrado com a `MIZAN_ENCRYPTION_KEY`.
- Os códigos de recuperação ficam só como hash com sal.
- O cadastro que vai para a tela nunca leva esses campos (`auth.publico`).

**Login em duas etapas**
- Senha certa com 2FA ligado devolve um **desafio**: um token de uso restrito, que vale
  5 minutos e não abre nenhuma outra rota.
- Com o código, sai a sessão marcada como "com 2FA".

**Sessões e códigos**
- Com o 2FA ligado, sessão sem a marca de 2FA cai (401). Isso vale para sessões abertas antes
  de ligar e para outros aparelhos.
- Renovar a sessão e trocar a senha mantêm a marca.
- Cada código vale uma vez: o último passo usado fica gravado, e dois pedidos com o mesmo
  código não passam juntos.

**Administrador sem 2FA**
- As rotas respondem 403 com um aviso, e a tela abre a configuração.
- Configurar exige login nos últimos 15 minutos ou a senha. Assim, uma sessão antiga ou
  roubada não cadastra o celular de outra pessoa.

**Limite de tentativas**
- Por pessoa: 5 por 15 minutos e 15 por dia.
- Login: 5 erros por e-mail e 30 por IP em 15 minutos, como antes. Agora cada erro vai na
  hora para `login_tentativas`, com a chave em HMAC (sem e-mail nem IP em texto). Banco fora:
  vale a contagem em memória.

**Auditoria:** ativação, desativação, novos códigos, uso de código de recuperação e
redefinição pelo COMANDO.

## Configuração

1. **Supabase:** rode `backend/sql/migracao_seguranca_2fa.sql`. Antes disso, ninguém é
   obrigado ao 2FA, e o código novo pode ir ao ar sem trancar ninguém.
2. **Render:** nada obrigatório. A biblioteca do QR code (`segno`) entra pelo
   `requirements.txt`.
3. **Interruptor de emergência:** `MIZAN_2FA_OBRIGATORIO` no Render.
   - Padrão: `admin,comando`.
   - `0` desliga a obrigação (quem já ligou o 2FA continua usando).
4. **Último recurso, se o único COMANDO perder celular e códigos:** no SQL Editor do
   Supabase,
   `update usuarios set totp_ativo = false, totp_segredo = null, totp_recuperacao = null where email = '...';`
5. **Depois de conferir que o login funciona:** a tabela antiga `rate_limit_login` pode ser
   apagada (comando no fim da migração).
