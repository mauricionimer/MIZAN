"""Treino por empresa: modelo próprio, dados descartados, nada vaza para outras empresas.

    python test_treino_empresa.py
"""
import hashlib, io, os, sys, tempfile
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
TMP = tempfile.mkdtemp(prefix="mizan_treino_")
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_DATA_DIR=TMP)
# O modelo global do repositório é copiado para o diretório de teste, que é onde o código vai procurar.
import shutil
(Path(TMP) / "model").mkdir(parents=True)
for n in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl"):
    shutil.copy(AQUI / "model" / n, Path(TMP) / "model" / n)

from model import modelos_empresa as me, treino_empresa as te, score as sc   # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

# storage_ml tenta o Supabase real: aqui não há rede, e o código precisa seguir sem ele
rng = np.random.default_rng(7)
N = 3000
def carteira(n=N, com_data=True, extra=None):
    dias = rng.integers(10, 900, n)
    valor = rng.lognormal(8.0, 0.8, n).round(2)
    renda = rng.lognormal(7.9, 0.5, n).round(2)
    logit = -0.004 * dias + 0.0 * valor + 0.0004 * renda - 0.6 * (valor / renda > 1.5) + 0.8
    pagou = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    df = pd.DataFrame({
        "cpf": [f"{(i * 7919) % 10**11:011d}" for i in range(n)],
        "nome": [f"Fulano Silva {i}" for i in range(n)],
        "valor_divida": valor, "renda_estimada": renda, "dias_em_atraso": dias,
        "produto": rng.choice(["cartao", "consignado", "pessoal"], n),
        "uf": rng.choice(["GO", "DF"], n),
        "pagou": np.where(pagou == 1, "sim", "não"),
    })
    if com_data:
        df["data_referencia"] = pd.date_range("2024-01-01", periods=n, freq="6h").strftime("%d/%m/%Y")
    if extra:
        for k, v in extra(df, pagou).items():
            df[k] = v
    return df, pagou

def csv_bytes(df): return df.to_csv(index=False).encode()

df, y = carteira()
raw = csv_bytes(df)
_vistas = []
_aj = te._ajustar
def _espia(d_, y_):
    _vistas.append(list(d_.columns))
    return _aj(d_, y_)
te._ajustar = _espia
cpfs = set(df["cpf"]); nomes = set(df["nome"][:50])

# ── treino ───────────────────────────────────────────────────────────────
reg = te.treinar(raw, "goias.csv", "Goias Bank", "mauricio@x.com")
checar(reg["promovido"] is False and me.versao_ativa("goias bank") is None,
       "treinar NÃO ativa o modelo")
checar(reg["tipo_alvo"] == "real" and reg["validacao"] == "temporal", "alvo real e validação temporal", reg["validacao"])
checar(reg["arquivo"]["sha256"] == hashlib.sha256(raw).hexdigest(), "impressão digital do arquivo registrada")
checar(reg["n_amostras"] == N and reg["periodo"] and reg["periodo"]["inicio"] == "2024-01-01", "contagem e período", str(reg["periodo"]))
m = reg["metricas"]
checar(0.5 < m["novo"]["auc"] < 1 and m["novo"]["n_teste"] == int(N * 0.2), "métricas do teste calculadas", str(m["novo"]))
checar(m["atual"].get("origem") == "global", "modelo atual medido na mesma fatia", str(m["atual"]))
checar(set(reg["identificadores_removidos"]) == {"cpf", "nome"}, "CPF e nome removidos na entrada")
checar(not any(c in reg["colunas_do_modelo"] for c in ("cpf", "nome", "pagou")), "e não viraram variáveis")

te._ajustar = _aj
checar(_vistas and all("cpf" not in c and "nome" not in c and "pagou" not in c for c in _vistas),
       "identificadores e resultado nem chegam ao ajuste do modelo", str(_vistas[0]) if _vistas else "")

# ── nada do arquivo ficou em lugar nenhum ────────────────────────────────
achou = []
for arq in Path(TMP).rglob("*"):
    if not arq.is_file(): continue
    if arq.suffix in (".csv", ".xlsx", ".xls"): achou.append(f"arquivo de dados: {arq.name}")
    if arq.suffix == ".json":
        txt = arq.read_text()
        achou += [f"{arq.name}: cpf" for c in list(cpfs)[:200] if c in txt][:1]
        achou += [f"{arq.name}: nome" for nm in nomes if nm in txt][:1]
    if arq.suffix == ".pkl" and "empresas" in str(arq):
        bin_ = arq.read_bytes()
        achou += [f"{arq.name}: contém cpf" for c in list(cpfs)[:200] if c.encode() in bin_][:1]
        achou += [f"{arq.name}: contém nome" for nm in list(nomes)[:50] if nm.encode() in bin_][:1]
checar(not achou, "nenhum CPF, nome ou arquivo de dados em disco (json e pkl varridos)", str(achou))

# ── ativação, isolamento, volta ao global ────────────────────────────────
glob = sc._carregar_modelos()
checar(sc._carregar_modelos("goias bank")[2] is glob[2], "antes de ativar, a empresa usa o global")
me.ativar("goias bank", reg["versao"])
meta_g = sc._carregar_modelos("goias bank")[2]
checar(meta_g.get("versao") == reg["versao"], "depois de ativar, usa o modelo próprio")
checar(sc._carregar_modelos("outro banco")[2] is glob[2], "outra empresa continua no global")
checar(sc._carregar_modelos()[2] is glob[2], "e sem empresa também")
res = sc.score_carteira(df.head(50).copy(), "goias bank")
checar("score_recuperabilidade" in res and res["score_recuperabilidade"].between(0, 100).all(), "pontua com o modelo próprio")
me.desativar("goias bank")
checar(sc._carregar_modelos("goias bank")[2] is glob[2], "desativar devolve ao global")
checar(me.carregar_versoes("goias bank")["versoes"], "e os arquivos da versão ficam guardados")

# ── caminho seguro ───────────────────────────────────────────────────────
p = me.pasta("../../etc/passwd")
checar(me.EMPRESAS_DIR.resolve() in p.parents, "empresa_id malicioso não escapa da pasta", str(p))
checar(me.slug("Banco A") != me.slug("banco-a"), "ids que colidiriam ganham sufixos diferentes")

# ── recusas ──────────────────────────────────────────────────────────────
def recusa(df_, rotulo, trecho):
    try:
        te.treinar(csv_bytes(df_), "x.csv", "emp-r", "")
        checar(False, rotulo)
    except te.DadosInvalidos as e:
        checar(trecho.lower() in str(e).lower(), rotulo, str(e)[:90])
    checar(not (me.EMPRESAS_DIR / me.slug("emp-r")).exists(), "  e nada ficou gravado")

recusa(df.drop(columns=["pagou"]), "sem coluna de resultado é recusado", "resultado")
d2 = df.copy(); d2.loc[0, "pagou"] = "talvez"
recusa(d2, "resultado ilegível é recusado, não adivinhado", "talvez")
recusa(df.head(100), "poucas linhas é recusado", "mínimo")
d3 = df.copy(); d3["pagou"] = "não"
recusa(d3, "resultado uniforme é recusado", "mínimo")
recusa(df.drop(columns=["valor_divida"]), "sem valor da dívida é recusado", "obrigat")

# ── vazamento ────────────────────────────────────────────────────────────
dv, yv = carteira(extra=lambda d, p: {"valor_recuperado": p * 1000.0, "indicador_x": p * 5 + np.random.default_rng(1).normal(0, 0.01, len(p))})
rv = te.treinar(csv_bytes(dv), "v.csv", "emp-v", "")
checar("valor_recuperado" not in rv["colunas_do_modelo"], "coluna de desfecho (valor recuperado) fica fora")
checar(any("indicador_x" in a for a in rv["avisos"]), "variável que copia a resposta gera aviso", str(rv["avisos"])[:120])

# ── sem data: avisa que a validação é mais branda ────────────────────────
dn, _ = carteira(com_data=False)
rn = te.treinar(csv_bytes(dn), "n.csv", "emp-n", "")
checar(rn["validacao"] == "aleatoria" and any("aleatória" in a for a in rn["avisos"]), "sem data: validação aleatória e aviso")

# ── falha no meio não deixa casca ────────────────────────────────────────
orig = te._ajustar
te._ajustar = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("memória"))
try:
    te.treinar(raw, "g.csv", "emp-f", "")
except RuntimeError:
    pass
te._ajustar = orig
checar(not (me.EMPRESAS_DIR / me.slug("emp-f")).exists(), "falha no treino não deixa pasta nem arquivo")

# ── teto de linhas: amostra e avisa ─────────────────────────────────────
te.MAX_LINHAS = 600
rc = te.treinar(raw, "g.csv", "emp-c", "")
checar(rc["n_amostras"] == 600 and rc["linhas_com_resultado"] == N, "acima do teto de memória: treina com amostra", f"{rc['n_amostras']} de {rc['linhas_com_resultado']}")
checar(any("amostra" in a for a in rc["avisos"]), "e avisa que usou amostra")
te.MAX_LINHAS = 100_000

# ── ';' e Latin-1 ────────────────────────────────────────────────────────
dl = df.head(400).copy(); dl["produto"] = "cartão"
lido = te.ler_tabela(dl.to_csv(index=False, sep=";").encode("latin-1"), "a.csv")
checar(len(lido) == 400 and "valor_divida" in lido.columns, "lê CSV com ';' e Latin-1")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if falhas else 0)
