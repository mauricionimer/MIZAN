"""Semáforo do devedor: a cor da pasta (branco, amarelo, vermelho)."""
import json
from datetime import datetime, timedelta, timezone

from agente import semaforo, triagem

AGORA = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def caso(situacao="novo", **dados):
    return {"id": "c1", "situacao": situacao, "dados": dados}


def leitura(**k):
    return {"leitura": {"quando": AGORA.isoformat(), "sinais": [], "intencao": "outro", **k}}


def test_piso_pela_situacao():
    cor = lambda s: semaforo.calcular(caso(s), AGORA)["cor"]
    assert cor("novo") == "branco" and cor("quitado") == "branco"
    assert cor("negociando") == "amarelo" and cor("acordo_ativo") == "amarelo" and cor("suspenso") == "amarelo"
    assert cor("atrasado") == "vermelho" and cor("quebrado") == "vermelho" and cor("contestado") == "vermelho"


def test_sem_caso_e_branco():
    assert semaforo.para_tela(None)["cor"] == "branco"


def test_leitura_da_triagem_sobe_a_cor():
    s = semaforo.calcular(caso("em_contato", **leitura(emocao="irritado")), AGORA)
    assert s["cor"] == "vermelho" and "irritado" in s["motivo"] and s["origem"] == "regra"
    s = semaforo.calcular(caso("novo", **leitura(urgencia="alta")), AGORA)
    assert s["cor"] == "vermelho"
    s = semaforo.calcular(caso("novo", **leitura(emocao="ansioso")), AGORA)
    assert s["cor"] == "amarelo"


def test_a_ia_sobe_mas_nunca_baixa_o_piso():
    # IA diz vermelho num caso que as regras veem amarelo: vale a IA, com o motivo dela
    s = semaforo.calcular(caso("negociando", **leitura(semaforo="vermelho", semaforo_motivo="ameaçou acionar o Procon")), AGORA)
    assert (s["cor"], s["origem"], s["motivo"]) == ("vermelho", "agente", "ameaçou acionar o Procon")
    # IA diz branco num caso atrasado: o piso das regras vence
    s = semaforo.calcular(caso("atrasado", **leitura(semaforo="branco")), AGORA)
    assert s["cor"] == "vermelho" and s["origem"] == "regra"


def test_leitura_velha_nao_vale():
    velha = {"leitura": {"quando": (AGORA - timedelta(days=30)).isoformat(), "semaforo": "vermelho", "emocao": "irritado"}}
    assert semaforo.calcular(caso("novo", **velha), AGORA)["cor"] == "branco"


def test_quitado_e_sempre_branco():
    assert semaforo.calcular(caso("quitado", **leitura(semaforo="vermelho", emocao="irritado")), AGORA)["cor"] == "branco"


def test_passagem_urgente_com_a_equipe():
    ficha = {"emocao": "desesperado", "urgencia": "alta", "quando": AGORA.isoformat()}
    assert semaforo.calcular(caso("com_pessoa", passagem=ficha), AGORA)["cor"] == "vermelho"
    assert semaforo.calcular(caso("com_pessoa", passagem={"quando": AGORA.isoformat()}), AGORA)["cor"] == "amarelo"


def test_validacao_da_triagem_traz_o_semaforo():
    base = {"intencao": "outro", "confianca": 0.8}
    v = triagem._validar(json.dumps(base))
    assert v["semaforo"] is None and v["semaforo_motivo"] == ""                 # sem o campo: não derruba
    v = triagem._validar(json.dumps({**base, "semaforo": "ROXO"}))
    assert v["semaforo"] is None
    v = triagem._validar(json.dumps({**base, "semaforo": "Vermelho", "semaforo_motivo": "CPF 123.456.789-00 pede pressa"}))
    assert v["semaforo"] == "vermelho" and "123.456" not in v["semaforo_motivo"]


def test_regra_de_seguranca_define_a_cor_sem_ia():
    class Rastreio:
        atual = None
    class Ctx:
        saida, rastreio, caso, agora = {}, Rastreio(), {"dados": {}}, AGORA
        def ia(self, *a, **k):
            raise AssertionError("regra de segurança não chama a IA")
        def anotar(self, *a):
            pass
    ctx = Ctx()
    out = triagem.classificar(ctx, "quero falar com um atendente")
    assert out["semaforo"] == "vermelho"
    assert ctx.caso["dados"]["leitura"]["semaforo"] == "vermelho"
    out = triagem.classificar(ctx, "me deixa em paz")
    assert out["semaforo"] == "amarelo"
    assert semaforo.atualizar(ctx.caso, AGORA)["cor"] == "amarelo"


def test_arquivos_da_pasta():
    assert semaforo.arquivos(None)[0]["name"] == "Sem atendimento"
    c = caso("negociando", caderno=[{"agente": "triagem"}], **leitura(emocao="ansioso", urgencia="media"))
    nomes = [a["name"] for a in semaforo.arquivos(c)]
    assert nomes[0] == "Situação" and "Última leitura" in nomes and "Caderno do caso" in nomes


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
