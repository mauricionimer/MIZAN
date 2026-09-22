#!/usr/bin/env python3
"""Gera uma API key nova e o SQL para cadastrá-la.

    python gerar_api_key.py <empresa_id> [rotulo]

A chave em texto aparece UMA vez, aqui na tela. O banco recebe só o hash —
é isso que impede um dump ou um acesso de leitura de virar credencial
funcional. Se a chave se perder, gera-se outra; não há como recuperá-la a
partir do banco, e isso é intencional.

Sem acesso a um terminal (pelo celular, por exemplo), o mesmo pode ser feito
só com SQL, direto no editor do Supabase — e é até melhor, porque a chave
não passa por lugar nenhum além da própria tela:

    WITH nova AS (
      SELECT 'mizan_' || encode(gen_random_bytes(24), 'hex') AS chave
    ), gravada AS (
      INSERT INTO api_keys (empresa_nome, empresa_id, rotulo, api_key_hash, ativa)
      SELECT 'MIZAN', 'mizan', 'chave rotacionada',
             encode(digest(nova.chave, 'sha256'), 'hex'), true
      FROM nova
      RETURNING id
    )
    SELECT nova.chave AS copie_esta_chave FROM nova, gravada;
"""
import hashlib
import secrets
import sys

PREFIXO = "mizan_"


def gerar(empresa_id: str, rotulo: str = "") -> tuple[str, str]:
    chave = PREFIXO + secrets.token_urlsafe(32)
    return chave, hashlib.sha256(chave.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    empresa_id = sys.argv[1].strip().lower()
    rotulo = sys.argv[2] if len(sys.argv) > 2 else "chave de integração"
    chave, h = gerar(empresa_id, rotulo)

    print("=" * 66)
    print("CHAVE (copie agora — não aparece de novo, nem fica no banco):")
    print()
    print(f"    {chave}")
    print()
    print("=" * 66)
    print("SQL para rodar no Supabase (só o hash vai para o banco):")
    print()
    print("INSERT INTO api_keys (empresa_nome, empresa_id, rotulo, api_key_hash, ativa)")
    print(f"VALUES ('{empresa_id}', '{empresa_id}', '{rotulo}',")
    print(f"        '{h}', true);")
    print()
    print("Use no header:  Authorization: Bearer <chave>")
    print("            ou: X-API-Key: <chave>   (webhook de pagamento)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
