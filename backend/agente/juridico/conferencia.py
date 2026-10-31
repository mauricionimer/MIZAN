"""Confere o texto do acervo com a fonte oficial (Planalto, Banco Central).

Para cada norma: baixa a página oficial, tira o texto tachado (redações antigas que o
Planalto mostra riscadas) e procura cada dispositivo vigente, normalizado, dentro do texto
oficial. Resultado:
- "conferida": todos os dispositivos encontrados, com a data da conferência;
- "divergente": lista dos dispositivos cuja redação não bate (desatualizados ou com erro
  de conversão). A decisão que depender deles vai para revisão humana;
- "nao_conferida": a fonte oficial não respondeu (sem internet, bloqueio, mudança de
  endereço). Fica a limitação registrada; nada é dado como conferido sem conferir.

Roda onde houver internet: na ingestão (--conferir) ou pelo servidor
(POST /agente/juridico/conferir, só administrador), que grava o resultado no banco.
"""
import hashlib
import html as _html
import re
import urllib.request
from datetime import datetime, timezone

from agente.juridico.texto import normalizar

TIMEOUT_S = 30
MIN_TEXTO = 25            # dispositivo curto demais ("(VETADO)") não prova nada


def _buscar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mizan-conferencia-juridica/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return r.read()


def _decodificar(bruto: bytes) -> str:
    cab = bruto[:4000].decode("ascii", "ignore").lower()
    m = re.search(r"charset=([\w-]+)", cab)
    for cod in ([m.group(1)] if m else []) + ["utf-8", "cp1252"]:
        try:
            return bruto.decode(cod)
        except (LookupError, UnicodeDecodeError):
            continue
    return bruto.decode("cp1252", "replace")


def html_para_texto(html: str) -> str:
    """Texto visível, sem o que está tachado (redação revogada) e sem scripts."""
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    t = re.sub(r"(?is)<(strike|s|del)\b.*?</\1>", " ", t)
    t = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</tr>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return _html.unescape(t)


def _comparavel(texto: str) -> str:
    t = normalizar(texto)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def conferir(norma: dict, registros: list, buscar=None, agora: datetime | None = None) -> dict:
    """Resultado da conferência de uma norma (`norma` é a entrada do manifesto)."""
    agora = agora or datetime.now(timezone.utc)
    url = norma.get("url_oficial")
    base = {"em": agora.isoformat(), "url": url}
    if not url:
        return {**base, "status": "nao_conferida", "detalhe": "sem endereço oficial cadastrado"}
    try:
        bruto = (buscar or _buscar)(url)
    except Exception as e:                          # sem internet, bloqueio, 404...
        return {**base, "status": "nao_conferida",
                "detalhe": f"fonte oficial inacessível a partir deste ambiente ({type(e).__name__})"}
    oficial = _comparavel(html_para_texto(_decodificar(bruto if isinstance(bruto, bytes) else bruto.encode())))
    if len(oficial) < 500:
        return {**base, "status": "nao_conferida", "detalhe": "a página oficial veio vazia ou incompleta"}
    vigentes = [r for r in registros if r.get("situacao") in ("vigente", "desatualizado")
                and len(r.get("texto") or "") >= MIN_TEXTO]
    divergentes = [r["id"] for r in vigentes if _comparavel(r["texto"]) not in oficial]
    return {**base, "status": "conferida" if not divergentes else "divergente",
            "verificados": len(vigentes), "divergentes": divergentes[:200],
            "sha256_fonte": hashlib.sha256(bruto if isinstance(bruto, bytes) else bruto.encode()).hexdigest(),
            "detalhe": ("todos os dispositivos conferem com a fonte oficial" if not divergentes
                        else f"{len(divergentes)} de {len(vigentes)} dispositivos com redação diferente da oficial")}
