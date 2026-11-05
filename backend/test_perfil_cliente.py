"""Perfil do cliente: orientação de conversa, honesta com pouco dado e sem dado sensível."""
import json

from agente import api, perfil, semaforo
from agente.bateria.motor import DIA, devedor, em
from agente.fonte import FonteMemoria
from agente.repositorio import RepoMemoria


def msg(texto, direcao="entrada"):
    return {"direcao": direcao, "texto": texto, "criado_em": "2026-11-01T12:00:00+00:00"}


def test_sem_dados_nao_inventa():
    r = perfil.calcular({"dados": {}}, [msg("oi")])
    assert r["pronto"] is False and "1 resposta" in r["falta"]
    assert perfil.calcular(None, [])["pronto"] is False


def test_tracos_antes_e_agora_com_fontes():
    caso = {"dados": {"identidade_ok": True}}
    semaforo.guardar_leitura(caso, {"intencao": "contestar", "emocao": "irritado", "urgencia": "alta"}, em(DIA))
    semaforo.guardar_leitura(caso, {"intencao": "pagar_negociar", "emocao": "calmo", "urgencia": "alta"}, em(DIA, 18))
    msgs = [msg("isso não é meu"), msg("tô desempregado, não tenho como pagar tudo"),
            msg("dá pra parcelar?"), msg("ok, entendi, quero resolver isso logo")]
    r = perfil.calcular(caso, msgs)
    assert r["pronto"] is True
    t = {x["id"]: x for x in r["tracos"]}
    assert t["humor"]["antes"] == 85 and t["humor"]["agora"] == 15          # irritado → calmo
    assert t["vontade"]["antes"] < t["vontade"]["agora"]                     # contestou → quer pagar
    assert t["aperto"]["agora"] >= 60 and any("dinheiro curto" in f for f in t["aperto"]["fontes"])
    assert all(x["fontes"] for x in r["tracos"]), "todo traço diz de onde veio"
    assert any("parcelas" in f.lower() for f in r["funciona"])
    assert r["frase"].endswith(".") and "Não é diagnóstico" in r["aviso"]


def test_nao_guarda_nem_mostra_texto_ou_sinal_sensivel():
    caso = {"dados": {}}
    semaforo.guardar_leitura(caso, {"intencao": "outro", "emocao": "triste", "urgencia": "baixa",
                                    "sinais_de_risco": ["sofrimento_grave"]}, em(DIA))
    assert "sinais" not in caso["dados"]["leituras"][-1]
    r = perfil.calcular(caso, [msg("meu salário 3200 acabou"), msg("estou mal")])
    texto = json.dumps(r, ensure_ascii=False)
    assert "3200" not in texto and "sofrimento" not in texto and "estou mal" not in texto


def test_historico_de_leituras_e_curto():
    caso = {"dados": {}}
    for i in range(20):
        semaforo.guardar_leitura(caso, {"intencao": "duvida", "emocao": "calmo"}, em(DIA))
    assert len(caso["dados"]["leituras"]) == semaforo.MAX_LEITURAS


def test_equipe_anota_no_caderno():
    repo, fonte = RepoMemoria(), FonteMemoria([devedor()])
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {}})
    api.fabrica_repo, api.fabrica_fonte = (lambda: repo), (lambda: fonte)
    try:
        r = api.anotar_pela_equipe("emp", "p1", "  Prefere   falar depois das 18h  ", "u1", agora=em(DIA))
        assert r["caderno"][0]["agente"] == "equipe" and r["caderno"][0]["motivo"] == "Prefere falar depois das 18h"
        for ruim in ["", "x" * 201]:
            try:
                api.anotar_pela_equipe("emp", "p1", ruim, "u1", agora=em(DIA))
                raise AssertionError("devia recusar")
            except ValueError:
                pass
        try:
            api.anotar_pela_equipe("emp", "p9", "oi", "u1")
            raise AssertionError("sem caso")
        except LookupError:
            pass
        assert api.perfil_do_cliente("emp", "p1")["pronto"] is False
    finally:
        from agente.fonte import FonteSupabase
        from agente.repositorio import RepoSupabase
        api.fabrica_repo, api.fabrica_fonte = RepoSupabase, FonteSupabase


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
