# Servidor sempre ligado (sem pagar)

## O problema

- O Render grátis **dorme depois de 15 minutos sem visita**. A primeira visita depois disso
  espera cerca de 1 minuto para o servidor acordar.
- O despertador do GitHub (`.github/workflows/keepalive.yml`) pede uma chamada a cada 8 minutos,
  mas o GitHub atrasa tarefas agendadas. Entre 27/10 e 05/11/2026 ele rodou, na prática, a cada
  3 a 10 horas (média de 5 h 30). Por isso não segurava o servidor acordado.
- O site (Vercel) e o banco (Supabase) não dormem. Quem dorme é só o servidor do Render.

## A solução grátis

Um serviço externo chama `https://mizan-backend-4zg8.onrender.com/health` a cada 5 minutos.
A rota é leve: não consulta o banco nem a IA e não grava nada.

### 1. Despertador principal: cron-job.org (grátis)

1. Crie uma conta em https://cron-job.org.
2. Clique em **Create cronjob** e preencha:
   - **Title:** Mizan acordado
   - **URL:** `https://mizan-backend-4zg8.onrender.com/health`
   - **Execution schedule:** every 5 minutes
3. Salve.

Se o servidor estiver dormindo, a primeira chamada pode dar erro de tempo esgotado. Mesmo
assim ela acorda o servidor, e as seguintes dão "Success".

### 2. Reserva (opcional): UptimeRobot (grátis)

1. Crie uma conta em https://uptimerobot.com.
2. **New monitor:** tipo HTTP(s), mesma URL, intervalo de 5 minutos.
3. Ele também manda e-mail quando o servidor cai, o que é útil no dia de uma apresentação.

A rota `/health` aceita GET e HEAD, então funciona com qualquer um dos dois monitores.

### 3. Render: caminho de saúde (recomendado)

Em **Render → serviço → Settings → Health Check Path**, coloque `/health`. Assim, num deploy, o
Render só troca para a versão nova quando ela já responde.

## Cuidado com as horas do Render

- O plano grátis dá **750 horas por mês para a conta inteira**, somando todos os serviços
  grátis.
- Ligado 24 horas, o Mizan gasta 720 horas em 30 dias e cabe.
- Se houver **outro serviço grátis na mesma conta** que também fique ligado, as horas acabam no
  meio do mês e o Render desliga todos até o dia 1º.
- Para conferir: **Render → Billing / Usage**. Deixe só o Mizan com despertador.

## O que muda com o servidor sempre ligado

As tarefas automáticas passam a rodar o tempo todo, como foram planejadas:

| Tarefa | Frequência |
|---|---|
| Ciclo dos agentes (fila, relógio, lembretes) | A cada minuto, só com `MIZAN_AGENTE_ATIVO=1` |
| Sincronizar as conexões de banco | A cada 15 minutos |
| Conferir o retreino do modelo | A cada 24 horas |

O gasto com IA continua limitado pelo teto diário (`MIZAN_AGENTE_TETO_DIA_USD`).

## Lista para o dia de uma apresentação

1. **Na véspera:** configure o despertador e confira no Render (Logs) que o servidor não
   dorme mais.
2. **De 2 horas antes até o fim:** ninguém faz merge ou push na `master`. Cada envio faz um
   deploy novo e reinicia o servidor.
3. **30 minutos antes:** abra o Mizan e entre com o celular do app autenticador na mão
   (o 2FA é obrigatório para administradores). Faça a demonstração uma vez, incluindo o
   Telegram.
4. **IA no plano grátis do Gemini:** a cota é por minuto. Evite disparar muitas mensagens
   seguidas. Se o agente demorar, é a cota, e ele responde quando ela libera.
5. **Plano B:** grave um vídeo curto da demonstração funcionando, para o caso de a internet
   do local falhar.

## Para depois

Para tirar o risco de vez, o plano pago mais barato do Render não dorme (conferir o preço em
render.com/pricing). Hospedagem grátis que nunca dorme existe, por exemplo uma máquina
"Always Free" da Oracle Cloud, mas exige configurar um servidor do zero. Não vale a troca às
vésperas de uma apresentação.
