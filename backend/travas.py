"""
Trava com prazo, para o que não pode rodar em duas instâncias ao mesmo tempo.

O agendador de retreino roda dentro do processo do app (APScheduler, sem Redis
nem Celery). Isso funciona enquanto há uma instância. Na segunda, os dois
agendadores acordam no mesmo intervalo, contam os mesmos feedbacks novos e
disparam o mesmo retreino — disputando o estado das versões e o bucket de
modelos, e gastando CPU dobrada para produzir o mesmo resultado, ou pior, dois
resultados diferentes promovidos em ordem imprevisível.

Aqui um ganha. Quem consegue gravar a trava roda; os outros pulam o ciclo e
tentam no próximo.

Por que com prazo: um processo pode morrer segurando a trava — deploy no meio
do retreino, contêiner reciclado, falta de memória. Sem prazo, o retreino
ficaria bloqueado para sempre e ninguém perceberia, porque a ausência de
retreino não gera erro nenhum. O prazo é o que faz o sistema se recuperar
sozinho.

Não é exclusão mútua perfeita: entre conferir o vencimento e gravar existe uma
janela, e dois processos podem passar se o relógio deles divergir muito. Para
um retreino que roda de hora em hora isso é aceitável — o custo de rodar duas
vezes num caso raro é CPU, não corrupção. Garantia forte exigiria transação, e
o PostgREST não expõe uma.
"""

import os
import socket
from datetime import datetime, timedelta, timezone

# Identifica quem segurou a trava. Serve para depurar "por que o retreino não
# roda": o dono aparece na tabela.
DONO = f"{socket.gethostname()}:{os.getpid()}"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def adquirir(nome: str, duracao_min: int = 30) -> bool:
    """Tenta ficar com a trava. Devolve se conseguiu.

    Na dúvida, devolve False: deixar de rodar um ciclo é barato, rodar dois
    retreinos concorrentes não é.
    """
    from db import get_db

    expira = (_agora() + timedelta(minutes=duracao_min)).isoformat()
    try:
        db = get_db()
        try:
            db.table("travas").insert(
                {"nome": nome, "dono": DONO, "expira_em": expira}
            ).execute()
            return True
        except Exception:
            # Já existe: só toma se a anterior venceu. O filtro pelo vencimento
            # vai na própria cláusula do UPDATE, então dois processos tentando
            # ao mesmo tempo não levam os dois — o segundo não encontra mais
            # linha vencida para atualizar.
            res = (db.table("travas")
                   .update({"dono": DONO, "expira_em": expira})
                   .eq("nome", nome)
                   .lt("expira_em", _agora().isoformat())
                   .execute())
            return bool(res.data)
    except Exception as e:
        print(f"[Trava] Não foi possível adquirir '{nome}': {e}")
        return False


def liberar(nome: str) -> None:
    """Devolve a trava ao terminar, para o próximo ciclo não esperar o prazo."""
    from db import get_db
    try:
        get_db().table("travas").delete().eq("nome", nome).eq("dono", DONO).execute()
    except Exception as e:
        print(f"[Trava] Não foi possível liberar '{nome}': {e}")
