"""
Marca da empresa na tela de login, pelo DOMÍNIO do e-mail.

Quem digita "joao@goiasbank.com.br" vê "Mizan & Goiás Bank", com o logo do
banco, antes de entrar. A resposta depende só do domínio, nunca da pessoa: o
mesmo para quem tem conta e para quem não tem. Antes o login aceitava o e-mail
inteiro e respondia com a empresa dona da conta — um oráculo que dizia quem é
cliente e quem tem acesso. Por domínio, o que se revela é só que aquele domínio
é de uma empresa cliente, e é o COMANDO quem cadastra isso.

Domínios de e-mail público nunca entram: "gmail.com" mapeado para uma empresa
mostraria a marca dela para metade do país.
"""

import re

DOMINIOS_PUBLICOS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.br", "outlook.com", "outlook.com.br",
    "live.com", "msn.com", "yahoo.com", "yahoo.com.br", "ymail.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "gmx.com", "zoho.com", "mail.com", "bol.com.br", "uol.com.br",
    "terra.com.br", "ig.com.br", "globo.com", "globomail.com", "r7.com", "zipmail.com.br", "oi.com.br",
}
_FORMATO = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


def dominio_do_email(email: str) -> "str | None":
    """Domínio normalizado de um e-mail, ou None se não der para ler."""
    texto = (email or "").strip().lower()
    if texto.count("@") != 1:
        return None
    dominio = texto.split("@", 1)[1].strip(".")
    return dominio if _FORMATO.match(dominio) else None


def validar_dominios(lista) -> "tuple[list, str | None]":
    """Lista limpa (sem repetição, minúscula) ou o motivo da recusa."""
    if not isinstance(lista, list):
        return [], "Envie uma lista de domínios."
    limpos = []
    for bruto in lista:
        d = str(bruto or "").strip().lower().lstrip("@").strip(".")
        if not d:
            continue
        if not _FORMATO.match(d):
            return [], f"Domínio inválido: {bruto!r}. Use só o que vem depois do @, como goiasbank.com.br."
        if d in DOMINIOS_PUBLICOS:
            return [], f"{d} é um e-mail público e não pode ser de uma empresa."
        if d not in limpos:
            limpos.append(d)
    if len(limpos) > 20:
        return [], "No máximo 20 domínios por empresa."
    return limpos, None
