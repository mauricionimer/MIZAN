"""Agentes, Parte 1 — cliente de IA falso, custo, teto e rastreio.

    python test_agente_llm.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_PRECOS", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE",
          "MIZAN_MODELO_TRIAGEM", "MIZAN_MODELO_NEGOCIADOR"):
    os.environ.pop(v, None)
from agente import llm                             # noqa: E402
from agente.rastreio import Rastreio               # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

def levanta(exc, f):
    try:
        f()
        return False
    except exc:
        return True

print("— cliente falso —")
cli = llm.cliente()
checar(isinstance(cli, llm.ClienteFalso), "sem configuração, o cliente é o falso")
cli = llm.ClienteFalso(["olá", llm.Resposta(texto="x", ferramentas=[{"nome": "simular", "args": {}}]),
                        TimeoutError("lento"), lambda s, m: "eco:" + m[-1]["conteudo"]])
r = cli.gerar(sistema="s", mensagens=[{"papel": "devedor", "conteudo": "oi"}])
checar(r.texto == "olá" and r.custo_usd == 0 and r.tokens_entrada > 0, "responde em ordem, custo zero")
checar(cli.gerar(sistema="s", mensagens=[]).ferramentas[0]["nome"] == "simular", "devolve pedido de ferramenta")
checar(levanta(TimeoutError, lambda: cli.gerar(sistema="s", mensagens=[])), "simula falha do fornecedor")
checar(cli.gerar(sistema="s", mensagens=[{"conteudo": "a"}]).texto == "eco:a", "aceita função")
checar(len(cli.chamadas) == 4, "guarda as chamadas")

print("— preço e teto —")
checar(levanta(llm.PrecoDesconhecido, lambda: llm.custo("modelo-x", 10, 10)), "modelo real sem preço não roda")
os.environ["MIZAN_AGENTE_PRECOS"] = '{"modelo-x": [2.0, 10.0]}'
checar(llm.custo("modelo-x", 1_000_000, 100_000) == 3.0, "preço por milhão de tokens, entrada e saída")
os.environ["MIZAN_AGENTE_PRECOS"] = "{quebrado"
checar(levanta(llm.PrecoDesconhecido, lambda: llm.custo("modelo-x", 1, 1)), "configuração inválida avisa")
os.environ.pop("MIZAN_AGENTE_PRECOS")
checar(llm.teto_dia_usd() == 1.0, "teto padrão US$ 1 por dia")
os.environ["MIZAN_AGENTE_TETO_DIA_USD"] = "0.5"
checar(levanta(llm.TetoExcedido, lambda: llm.conferir_teto(0.5)), "no teto, para")
llm.conferir_teto(0.49)
checar(True, "abaixo do teto, segue")
os.environ.pop("MIZAN_AGENTE_TETO_DIA_USD")

print("— roteamento de modelos —")
checar(llm.modelo_para("triagem") == "falso", "sem configuração, falso")
os.environ["MIZAN_MODELO_TRIAGEM"] = "barato"
checar(llm.modelo_para("triagem") == "barato" and llm.modelo_para("negociador") == "falso", "cada papel o seu")
os.environ.pop("MIZAN_MODELO_TRIAGEM")
os.environ["MIZAN_AGENTE_CLIENTE"] = "outro"
checar(levanta(NotImplementedError, llm.cliente), "cliente que não existe avisa, não finge")
os.environ.pop("MIZAN_AGENTE_CLIENTE")

print("— cliente da Anthropic (SDK simulado, sem rede) —")
from types import SimpleNamespace as NS
class Bloco(NS):
    def model_dump(self, exclude_none=False):
        return {k: v for k, v in vars(self).items() if not (exclude_none and v is None)}
class SDK:
    def __init__(s, msg): s.msg, s.pedidos = msg, []; s.messages = s
    def create(s, **k): s.pedidos.append(k); return s.msg
msg = NS(content=[Bloco(type="thinking", thinking="", signature="abc"), Bloco(type="text", text="Vou simular."),
                  Bloco(type="tool_use", id="toolu_1", name="simular_acordo", input={"n_parcelas": 1})],
         stop_reason="tool_use",
         usage=NS(input_tokens=1000, output_tokens=200, cache_creation_input_tokens=3000, cache_read_input_tokens=0))
sdk = SDK(msg)
os.environ["MIZAN_AGENTE_PRECOS"] = '{"modelo-y": [2.0, 10.0]}'
r = llm.ClienteAnthropic(sdk=sdk).gerar(sistema="regras", mensagens=[{"role": "user", "content": "oi"}],
                                        modelo="modelo-y", ferramentas=[{"name": "t"}], papel="negociador")
p = sdk.pedidos[0]
checar(p["system"][0]["cache_control"] == {"type": "ephemeral"} and p["tools"] == [{"name": "t"}]
       and "output_config" not in p, "instruções com cache; ferramentas; esforço padrão na conversa")
checar(r.parada == "ferramenta" and r.ferramentas == [{"id": "toolu_1", "nome": "simular_acordo", "args": {"n_parcelas": 1}}]
       and r.texto == "Vou simular.", "converte texto e pedido de ferramenta")
checar([b["type"] for b in r.bruto] == ["thinking", "text", "tool_use"], "guarda os blocos como vieram (inclui raciocínio)")
checar(r.tokens_entrada == 4000 and r.custo_usd == round((1000 * 2 + 3000 * 2 * 1.25 + 200 * 10) / 1e6, 6),
       "custo com cache: gravar custa 1,25x a entrada", str(r.custo_usd))
llm.ClienteAnthropic(sdk=sdk).gerar(sistema="s", mensagens=[], modelo="modelo-y", papel="triagem")
checar(sdk.pedidos[1]["output_config"] == {"effort": "low"} and "tools" not in sdk.pedidos[1], "triagem com esforço baixo")
msg.stop_reason = "refusal"
checar(llm.ClienteAnthropic(sdk=sdk).gerar(sistema="s", mensagens=[], modelo="modelo-y").parada == "recusa", "recusa do modelo")
checar(levanta(llm.PrecoDesconhecido, lambda: llm.ClienteAnthropic(sdk=sdk).gerar(sistema="s", mensagens=[], modelo="falso")),
       "cliente real sem modelo configurado não roda")
os.environ.pop("MIZAN_AGENTE_PRECOS")
checar(levanta(llm.PrecoDesconhecido, lambda: llm.ClienteAnthropic(sdk=sdk).gerar(sistema="s", mensagens=[], modelo="modelo-y")),
       "modelo real sem preço configurado não roda")

print("— rastreio —")
gravados = []
rt = Rastreio("emp", gravados.append, caso_id="c1", evento_id="e1")
with rt.span("triagem", "triagem") as p:
    rt.somar_ia(llm.Resposta(tokens_entrada=100, tokens_saida=20, custo_usd=0.001, modelo="m"))
    rt.somar_ia(llm.Resposta(tokens_entrada=50, tokens_saida=5, custo_usd=0.0005, modelo="m"))
    p["regra"] = "R1"
checar(gravados[0]["tokens_entrada"] == 150 and gravados[0]["custo_usd"] == 0.0015, "soma tokens e custo no passo")
checar(gravados[0]["trace_id"] == rt.trace_id and gravados[0]["regra"] == "R1", "passo com trace e regra")
try:
    with rt.span("negociador", "negociador"):
        raise ValueError("cpf 123")
except ValueError:
    pass
checar(gravados[1]["resultado"] == "erro" and gravados[1]["detalhe"] == {"erro": "ValueError"},
       "erro grava só o tipo, nunca a mensagem (pode ter dado pessoal)")
def quebra(_):
    raise IOError("banco fora")
rt2 = Rastreio("emp", quebra)
with rt2.span("x"):
    pass
checar(len(rt2.passos) == 1, "falha ao gravar o rastreio não derruba o atendimento")
checar(rt.custo_total == 0.0015, "custo total do trace")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
