"""Etapa 2: Triagem enriquecida (emoção, urgência, ironia, resumo)."""
import json

from agente import auditor, triagem


def test_validacao_tolerante():
    base = {"intencao": "outro", "confianca": 0.8}
    v = triagem._validar(json.dumps(base))                                  # sem os campos novos
    assert (v["emocao"], v["urgencia"], v["ironia"], v["resumo"]) == ("calmo", "baixa", False, "")
    v = triagem._validar(json.dumps({**base, "emocao": "furioso", "urgencia": "urgentíssima", "ironia": "sim",
                                     "resumo": 123}))
    assert (v["emocao"], v["urgencia"], v["ironia"], v["resumo"]) == ("calmo", "baixa", False, "")
    v = triagem._validar(json.dumps({**base, "emocao": "irritado", "urgencia": "alta", "ironia": True,
                                     "resumo": "quer pagar mas o CPF 123.456.789-00 não confere"}))
    assert (v["emocao"], v["urgencia"], v["ironia"]) == ("irritado", "alta", True)
    assert "123.456" not in v["resumo"] and "[removido]" in v["resumo"]


def test_regra_continua_antes_da_ia():
    class Rastreio:
        atual = None
    class Ctx:
        saida, rastreio = {}, Rastreio()
        notas = []
        resposta = None
        def ia(self, *a, **k):
            if self.resposta is None:
                raise AssertionError("regra de segurança não chama a IA")
            class R:
                texto = self.resposta
            return R()
        def anotar(self, *a):
            self.notas.append(a)
    ctx = Ctx()
    out = triagem.classificar(ctx, "me deixa em paz")                         # regra: nem chama a IA
    assert out["intencao"] == "parar_contato" and out["origem"] == "regra"
    ctx.resposta = json.dumps({"intencao": "outro", "confianca": 0.9, "emocao": "calmo"})
    out = triagem.classificar(ctx, "penso em tirar minha vida")             # IA diz calmo; a regra vence
    assert "sofrimento_grave" in out["sinais_de_risco"] and out["emocao"] == "desesperado"
    assert [n[1] for n in ctx.notas] == ["parar_contato", "outro"]


def test_ironia_bloqueia_aceite():
    caso = {"id": "c1", "situacao": "negociando", "dados": {"identidade_ok": True, "divida": 3000.0}}
    from datetime import datetime, timezone
    agora = datetime(2026, 10, 16, 15, tzinfo=timezone.utc)
    d = auditor.auditar({"tipo": "registrar_aceite", "params": {"n_parcelas": 1, "desconto_pct": 10}},
                        caso, auditor.POLITICA_DEMONSTRACAO, 1, agora, ironia=True)
    assert not d["permitida"] and d["regra"] == "R13_IRONIA"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
