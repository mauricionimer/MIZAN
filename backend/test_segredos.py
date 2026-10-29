"""Regressão: segredo ausente derruba o app, não degrada em silêncio.

    python test_segredos.py

O JWT_SECRET já tinha trava: com o valor padrão, o app se recusa a subir em
produção. A chave de criptografia não tinha. Sem ela, _encrypt devolvia o
texto puro e o app subia normalmente — gravando usuário e senha do banco de
produção do cliente em claro, enquanto a política de privacidade afirmava
"criptografia de credenciais (AES via Fernet)".

Falhar alto é o comportamento certo aqui: um deploy sem a chave deve quebrar
na subida, onde alguém vê, e não meses depois num vazamento.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from cryptography.fernet import Fernet             # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


SENHA = "senha-do-banco-do-cliente"


def com_chave(chave):
    """Reinstala a chave e limpa o Fernet memoizado."""
    main._FERNET_KEY = chave
    main._fernet = None


# ── 1. com chave: cifra de verdade ───────────────────────────────────────
print("— com chave configurada —")
chave = Fernet.generate_key().decode()
com_chave(chave)

cifrado = main._encrypt(SENHA)
checar(cifrado != SENHA, "a senha não sai em claro")
checar(SENHA not in cifrado, "e o texto não aparece dentro do cifrado")
checar(main._decrypt(cifrado) == SENHA, "e volta ao original na leitura")


# ── 2. sem chave, em produção: falha alto ────────────────────────────────
print("\n— sem chave, com Supabase configurado (produção) —")
com_chave("")
try:
    main._encrypt(SENHA)
    checar(False, "gravar credencial sem chave levanta erro",
           "devolveu texto puro em silêncio — é a falha original")
except RuntimeError as e:
    checar("MIZAN_ENCRYPTION_KEY" in str(e),
           "gravar credencial sem chave levanta erro nomeando a variável",
           str(e)[:60])


# ── 3. sem chave, em desenvolvimento: segue ──────────────────────────────
print("\n— sem chave, sem Supabase (desenvolvimento local) —")
supabase = os.environ.pop("SUPABASE_URL")
try:
    checar(main._encrypt(SENHA) == SENHA,
           "local segue funcionando sem exigir chave",
           "quem roda na própria máquina não precisa gerar uma")
finally:
    os.environ["SUPABASE_URL"] = supabase


# ── 4. dado já gravado em claro continua legível ─────────────────────────
print("\n— migração de quem já tem credencial em claro —")
com_chave(chave)
checar(main._decrypt(SENHA) == SENHA,
       "senha antiga, gravada em claro, ainda é lida",
       "ligar a chave não quebra o que já está no banco")


# ── 5. a trava do startup ────────────────────────────────────────────────
print("\n— a trava na subida —")
fonte = (AQUI / "main.py").read_text()
# A trava foi para _conferir_segredos_de_producao (S10), chamada pelo lifespan.
try:
    main._conferir_segredos_de_producao("x" * 48, "")
    _recusou = False
except RuntimeError:
    _recusou = True
checar("_conferir_segredos_de_producao(_JWT_SECRET, _FERNET_KEY)" in fonte and _recusou,
       "o lifespan recusa subir em produção sem a chave")
checar("MIZAN_ENCRYPTION_KEY" in (AQUI / "render.yaml").read_text(),
       "e o render.yaml declara a variável",
       "senão um ambiente novo sobe sem ela e ninguém percebe")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
