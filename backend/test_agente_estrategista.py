"""Agentes — Estrategista: quatro grupos com motivo, grupo sorteado e a
primeira mensagem do grupo 'contato'. Sem IA, sem banco.

    python test_agente_estrategista.py
"""
import os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import api, auditor, estrategista as est, orquestrador as orq   # noqa: E402
from agente.fonte import FonteMemoria                                       # noqa: E402
from agente.llm import ClienteFalso                                         # noqa: E402
from agente.repositorio import RepoMemoria                                  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEX_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
def dev(i, p=None, score=None):
    return {"id": f"p{i}", "empresa_id": "emp", "cpf": f"{i:011d}", "nome": f"Pessoa {i} Silva",
            "valor_divida": 1000.0 + i, "probabilidade_pagamento": p, "score_recuperabilidade": score}

print("— classificar —")
checar(est.classificar(dev(1, 0.85), None)[0] == "so_lembrete", "chance alta: só lembrete")
checar(est.classificar(dev(1, 0.30), None) == ("contato", "chance de 30%: paga se for procurado"), "chance média: contato, com motivo")
checar(est.classificar(dev(1, 0.02), None)[0] == "nao_adianta", "chance muito baixa: não adianta agora")
checar(est.classificar(dev(1, None, 75), None)[0] == "so_lembrete", "sem probabilidade, usa o score")
checar(est.classificar(dev(1), None)[0] == "contato", "sem nada: procurar para entender")
for s, g in (("contestado", "pessoa"), ("com_pessoa", "pessoa"), ("suspenso", "pessoa"), ("quebrado", "nao_adianta"),
             ("acordo_ativo", "so_lembrete"), ("atrasado", "so_lembrete")):
    checar(est.classificar(dev(1, 0.3), {"situacao": s})[0] == g, f"caso {s}: {g}")

print("— sorteio —")
n = sum(est.sorteado("emp", f"p{i}", 10) for i in range(10_000))
checar(900 <= n <= 1100, "10% sorteados, em média", str(n))
checar(all(est.sorteado("emp", f"p{i}", 10) == est.sorteado("emp", f"p{i}", 10) for i in range(200)), "sorteio fixo por devedor")
checar(not any(est.sorteado("emp", f"p{i}", 0) for i in range(500)), "0% não sorteia ninguém")

print("— plano —")
devs = [dev(i, p) for i, p in enumerate([0.9, 0.8, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.01, 0.03] * 6)]
for i, d in enumerate(devs):
    d["id"] = f"p{i}"
repo, fonte = RepoMemoria(), FonteMemoria(devs)
repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
api.fabrica_repo, api.fabrica_fonte, api.fabrica_cliente = (lambda: repo), (lambda: fonte), (lambda: ClienteFalso())
p = api.plano_do_dia("emp")
total = sum(p["contagem"].values())
checar(total == 60 and p["percentual_controle"] == 10 and repo.casos == {}, "prévia: todos classificados, nada gravado", str(p["contagem"]))
checar(all(it["motivo"] for g in p["grupos"].values() for it in g), "todo devedor tem motivo")

os.environ["MIZAN_AGENTE_ATIVO"] = "1"
r = api.aplicar_plano("emp", agora=SEX_14H)
casos = list(repo.casos.values())
ctrl = [c for c in casos if c["grupo_controle"]]
checar(len(ctrl) == r["contagem"]["controle"] and all(c["situacao"] == "novo" for c in ctrl), "sorteados gravados e intocados")
contato = [c for c in casos if c["grupo"] == "contato" and not c["grupo_controle"]]
saidas = [m for m in repo.mensagens if m["direcao"] == "saida"]
checar(len(saidas) == len(contato) and all(c["situacao"] == "em_contato" for c in contato),
       "grupo contato: primeira mensagem pronta e caso em contato", f"{len(saidas)} x {len(contato)}")
checar(saidas and "assistente virtual de Banco Demonstração" in saidas[0]["texto"], "a abordagem se apresenta como assistente virtual")
checar(saidas and "posso confirmar se estou falando com você" in saidas[0]["texto"], "a abordagem começa pela identidade e privacidade")
checar(saidas and not any(t in saidas[0]["texto"].lower() for t in ("pendência", "regularizar", "condições", "r$")),
       "a primeira abordagem não começa cobrando")
ids_ctrl = {c["id"] for c in ctrl}
checar(not any(m["caso_id"] in ids_ctrl for m in repo.mensagens), "nenhuma mensagem para quem foi sorteado")
checar(all(c["situacao"] == "so_lembrete" for c in casos if c["grupo"] == "so_lembrete" and not c["grupo_controle"]),
       "grupo só lembrete fica com o Acompanhamento")
api.aplicar_plano("emp", agora=SEX_14H)
checar(len([m for m in repo.mensagens if m["direcao"] == "saida"]) == len(saidas), "aplicar de novo não repete a abordagem")
checar({c["id"]: c["grupo_controle"] for c in repo.casos.values()} == {c["id"]: c["grupo_controle"] for c in casos},
       "nem muda o sorteio")

repo2, fonte2 = RepoMemoria(), FonteMemoria([dev(1, 0.3)])
repo2.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "percentual_controle": 0})
api.fabrica_repo, api.fabrica_fonte = (lambda: repo2), (lambda: fonte2)
api.aplicar_plano("emp", agora=datetime(2026, 10, 16, 2, 0, tzinfo=timezone.utc))   # 23h em Brasília
c = list(repo2.casos.values())[0]
ev = list(repo2.eventos.values())[0]
checar(c["situacao"] == "novo" and repo2.mensagens == [] and ev["situacao"] == "pendente",
       "fora do horário: a abordagem espera a janela de contato")
orq.processar_fila(repo2, api.grafos(fonte2), ClienteFalso(), agora=datetime(2026, 10, 16, 11, 0, tzinfo=timezone.utc))
checar(repo2.obter_caso(c["id"])["situacao"] == "em_contato" and len(repo2.mensagens) == 1, "às 8h ela sai")
os.environ.pop("MIZAN_AGENTE_ATIVO")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
