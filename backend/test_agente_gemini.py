"""Conector do Gemini, sem rede: o formato que vai ao Google e o que volta ao agente."""
import json
import os

os.environ["MIZAN_AGENTE_PRECOS"] = json.dumps({"gemini-teste": [0.5, 3.0]})

from agente import llm  # noqa: E402

pedidos = []


def google(respostas):
    fila = list(respostas)

    def enviar(url, corpo, chave, timeout):
        pedidos.append({"url": url, "corpo": json.loads(json.dumps(corpo)), "chave": chave})
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return enviar


USO = {"promptTokenCount": 1000, "candidatesTokenCount": 50, "thoughtsTokenCount": 150, "cachedContentTokenCount": 400}
CHAMADA = {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
    {"text": "pensando", "thought": True},
    {"functionCall": {"name": "simular_acordo", "args": {"n_parcelas": 3}}, "thoughtSignature": "ASSINATURA"}]}}],
    "usageMetadata": USO}
TEXTO = {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "Fica R$ 900,00."}]}}],
         "usageMetadata": USO}
FERRAMENTAS = [{"name": "simular_acordo", "description": "simula",
                "input_schema": {"type": "object", "properties": {"n_parcelas": {"type": "integer"}},
                                 "required": ["n_parcelas"], "additionalProperties": False}}]


def test_chamada_de_ferramenta_e_volta_com_assinatura():
    pedidos.clear()
    cli = llm.ClienteGemini(chave="k", enviar=google([CHAMADA, TEXTO]))
    msgs = [{"role": "user", "content": [{"type": "text", "text": "<briefing>{}</briefing>"},
                                         {"type": "text", "text": "quero parcelar"}]}]
    r = cli.gerar(sistema="S", mensagens=msgs, modelo="gemini-teste", ferramentas=FERRAMENTAS, papel="negociador")
    assert r.parada == "ferramenta" and r.texto == ""                 # raciocínio não vira texto
    assert r.ferramentas[0]["nome"] == "simular_acordo" and r.ferramentas[0]["args"] == {"n_parcelas": 3}
    assert r.tokens_entrada == 1000 and r.tokens_saida == 200 and r.tokens_cache_leitura == 400
    assert abs(r.custo_usd - (600 * 0.5 + 400 * 0.5 * 0.1 + 200 * 3.0) / 1e6) < 1e-9
    c = pedidos[0]["corpo"]
    assert c["systemInstruction"]["parts"][0]["text"] == "S"
    assert c["contents"] == [{"role": "user", "parts": [{"text": "<briefing>{}</briefing>"}, {"text": "quero parcelar"}]}]
    decl = c["tools"][0]["functionDeclarations"][0]
    assert decl["name"] == "simular_acordo" and decl["parametersJsonSchema"]["required"] == ["n_parcelas"]
    assert c["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}

    # O agente devolve o bruto e o resultado da ferramenta, como faz com a Anthropic.
    msgs += [{"role": "assistant", "content": r.bruto},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": r.ferramentas[0]["id"],
                                           "content": json.dumps({"ok": True, "valor": 900}), "is_error": False}]}]
    r2 = cli.gerar(sistema="S", mensagens=msgs, modelo="gemini-teste", ferramentas=FERRAMENTAS, papel="negociador")
    assert r2.parada == "fim" and r2.texto == "Fica R$ 900,00."
    modelo, resultado = pedidos[1]["corpo"]["contents"][1:]
    assert modelo["role"] == "model" and modelo["parts"][1]["thoughtSignature"] == "ASSINATURA"
    assert resultado == {"role": "user", "parts": [{"functionResponse": {
        "name": "simular_acordo", "response": {"resultado": {"ok": True, "valor": 900}}}}]}


def test_id_do_google_volta_no_resultado():
    pedidos.clear()
    com_id = json.loads(json.dumps(CHAMADA))
    com_id["candidates"][0]["content"]["parts"][1]["functionCall"]["id"] = "abc"
    cli = llm.ClienteGemini(chave="k", enviar=google([com_id, TEXTO]))
    msgs = [{"role": "user", "content": "oi"}]
    r = cli.gerar(sistema="S", mensagens=msgs, modelo="gemini-teste", ferramentas=FERRAMENTAS)
    msgs += [{"role": "assistant", "content": r.bruto},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": r.ferramentas[0]["id"], "content": "{}"}]}]
    cli.gerar(sistema="S", mensagens=msgs, modelo="gemini-teste", ferramentas=FERRAMENTAS)
    fr = pedidos[1]["corpo"]["contents"][-1]["parts"][0]["functionResponse"]
    assert fr["id"] == "abc" and fr["name"] == "simular_acordo"


def test_bloqueio_corte_e_seguranca():
    casos = [({"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": USO}, "recusa"),
             ({"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}], "usageMetadata": USO}, "recusa"),
             ({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Fica"}]}}],
               "usageMetadata": USO}, "limite"),
             ({"candidates": [{"finishReason": "MALFORMED_FUNCTION_CALL"}], "usageMetadata": USO}, "limite")]
    for resposta, esperado in casos:
        r = llm.ClienteGemini(chave="k", enviar=google([resposta])).gerar(
            sistema="S", mensagens=[{"role": "user", "content": "oi"}], modelo="gemini-teste")
        assert r.parada == esperado, (resposta, r.parada)


def test_sem_chave_sem_modelo_sem_preco_nao_chama():
    pedidos.clear()
    for chave, modelo, erro in [("", "gemini-teste", llm.ErroGemini), ("k", llm.MODELO_FALSO, llm.PrecoDesconhecido),
                                ("k", "gemini-sem-preco", llm.PrecoDesconhecido)]:
        try:
            llm.ClienteGemini(chave=chave, enviar=google([TEXTO])).gerar(
                sistema="S", mensagens=[{"role": "user", "content": "oi"}], modelo=modelo)
            raise AssertionError(f"deveria falhar: {modelo}")
        except erro:
            pass
    assert not pedidos


def test_cliente_escolhido_pela_variavel():
    os.environ["MIZAN_AGENTE_CLIENTE"] = "gemini"
    try:
        assert isinstance(llm.cliente(), llm.ClienteGemini)
    finally:
        os.environ.pop("MIZAN_AGENTE_CLIENTE")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
