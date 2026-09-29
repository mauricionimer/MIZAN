"""Regressão: retenção de dados de quem nunca foi usuário do Mizan.

    python test_retencao.py

O sistema guardava CPF, nome, dívida e renda de devedores para sempre — sem
prazo e sem caminho de eliminação depois do fim do contrato. Estes testes
fixam as três decisões que o módulo tomou:

  1. Sem configuração, nada é tocado. Apagar dado de cliente por conta
     própria é pior do que não ter a função.
  2. O padrão é anonimizar, não apagar: o modelo aprende de (variáveis →
     resultado) e nunca precisou do CPF. Apagar a predição destruiria a base
     de treino junto com a identidade.
  3. Linha sem data não entra. Sem saber quando chegou, não dá para afirmar
     que o prazo venceu.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from model import retencao as R                    # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


AGORA = datetime(2026, 9, 29, tzinfo=timezone.utc)


def linha(id_, dias_atras, anonimizado=False):
    return {
        "id": id_,
        "created_at": (AGORA - timedelta(days=dias_atras)).isoformat(),
        "anonimizado_em": AGORA.isoformat() if anonimizado else None,
    }


# ── 1. o padrão é não fazer nada ─────────────────────────────────────────
print("— sem configuração, nada acontece —")

inerte = R.de_config({})
checar(not inerte.ativa, "empresa sem bloco de retenção fica inerte")
checar(R.corte(inerte, AGORA) is None, "política inerte não tem data de corte")
checar(R.selecionar([linha("a", 9999)], inerte, AGORA) == [],
       "dado de 27 anos atrás não é tocado sem configuração",
       "o prazo é escolha do cliente, não padrão do Mizan")

for ruim in ({"retencao": "365"}, {"retencao": {"dias": "ano que vem"}},
             {"retencao": {"ativa": True}}, {"retencao": {"ativa": True, "dias": 0}}):
    checar(not R.de_config(ruim).ativa,
           f"config malformada vira política inerte: {ruim}")


# ── 2. os limites do prazo ───────────────────────────────────────────────
print("\n— o prazo tem piso e teto —")

checar(R.PoliticaRetencao(True, 10).valida() is not None,
       "10 dias é recusado", "sairia antes de a cobrança terminar")
checar(R.PoliticaRetencao(True, R.MINIMO_DIAS).valida() is None,
       f"{R.MINIMO_DIAS} dias (o mínimo) é aceito")
checar(R.PoliticaRetencao(True, 20000).valida() is not None,
       "55 anos é recusado", "isso não é retenção, é guardar para sempre")
checar(R.corte(R.PoliticaRetencao(True, 10), AGORA) is None,
       "política inválida não produz corte, mesmo marcada como ativa")

politica = R.PoliticaRetencao(ativa=True, dias=365)
checar(R.corte(politica, AGORA) == AGORA - timedelta(days=365),
       "o corte é exatamente o prazo para trás")


# ── 3. quem entra e quem fica ────────────────────────────────────────────
print("\n— a seleção —")

base = [linha("velha", 400), linha("nova", 10), linha("limite_fora", 366),
        linha("limite_dentro", 364), linha("ja_anonima", 400, anonimizado=True)]
alvos = R.selecionar(base, politica, AGORA)

checar("velha" in alvos, "linha de 400 dias entra")
checar("nova" not in alvos, "linha de 10 dias fica")
checar("limite_fora" in alvos, "366 dias entra (passou de 365)")
checar("limite_dentro" not in alvos, "364 dias fica (ainda não venceu)")
checar("ja_anonima" not in alvos, "linha já anonimizada não volta à fila",
       "senão cada execução reescreveria a base inteira")

sem_data = [{"id": "x", "created_at": None}, {"id": "y"}, {"id": "z", "created_at": "ontem"}]
checar(R.selecionar(sem_data, politica, AGORA) == [],
       "linha sem data utilizável não é tocada",
       "não dá para afirmar que o prazo venceu")

naive = [{"id": "n", "created_at": datetime(2020, 1, 1)}]
checar(R.selecionar(naive, politica, AGORA) == ["n"],
       "data sem fuso é lida como UTC, não quebra")


# ── 4. o que a anonimização escreve ──────────────────────────────────────
print("\n— o patch —")

patch = R.patch_anonimo("predicoes", AGORA)
checar(patch["cpf"] is None and patch["nome"] is None,
       "predições perdem CPF e nome")
checar("valor_divida" not in patch and "score_recuperabilidade" not in patch,
       "e mais nada: as variáveis do modelo ficam",
       "é isto que separa identidade de aprendizado")
checar(patch["anonimizado_em"] == AGORA.isoformat(),
       "a linha registra quando foi anonimizada")

checar(R.patch_anonimo("contatos")["observacao"] is None,
       "a observação do contato some junto",
       "campo livre: o operador escreve telefone e nome de parente ali")
checar("observacao" not in R.patch_anonimo("feedbacks"),
       "feedback não tem observação para limpar")

checar(set(R.IDENTIFICADORES) == {"predicoes", "feedbacks", "contatos", "recomendacoes"},
       "as quatro tabelas com CPF de terceiro estão cobertas")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
