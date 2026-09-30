"""
Erros internos: o que o cliente vê, e o que fica registrado para você.

Até aqui não havia nada disso. Nenhum handler global, nenhum `logging`, 37
`print` soltos — e, pior, o texto bruto da exceção ia para o cliente. Numa
simulação de banco recusando conexão, a resposta trazia o host interno e a
senha:

    {"detail": "RuntimeError: connection to db.internal:5432 refused, password=..."}

Eram 39 lugares com `detail=f"...{e}"`, e qualquer exceção não tratada caía no
mesmo caminho. Este módulo troca isso por duas coisas separadas:

  para o cliente   uma frase genérica e um código curto. O código é o que ele
                   lê para o suporte e o que você procura no log.
  para o log       uma linha JSON com o código, a rota, o tipo do erro, quem
                   chamou e o traceback completo — mascarado.

Por que um middleware próprio em vez de só `exception_handler(Exception)`: o
handler de Exception roda no ServerErrorMiddleware, que fica FORA do CORS. A
resposta 500 sai sem cabeçalho CORS e o navegador esconde o corpo, mostrando
"Failed to fetch" — o cliente nunca chegaria a ver o código. Aqui a captura
fica por dentro do CORS, então o corpo é legível.

O que NÃO muda: erros 4xx são mensagens feitas para o usuário ("senha fraca")
e seguem como estão, e o 503 de "erro ao conectar no banco" vem do banco do
próprio cliente — o assistente de conexão existe justamente para mostrar por
que falhou, e trocá-lo por uma frase genérica o inutilizaria.

Mascaramento é o que se consegue com padrões, não uma garantia: pega CPF, senha
em `chave=valor`, credencial em URL e token Bearer. Um segredo escrito de outra
forma passa. Por isso o traceback vai para o LOG e nunca para a resposta.
"""

import json
import logging
import re
import sys
import traceback
import uuid

from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("mizan.erros")

MSG_GENERICA = "Erro interno. Se persistir, informe o código ao suporte: {codigo}"

# CPF formatado, ou onze dígitos seguidos.
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
# credencial dentro de URL: esquema://usuario:senha@host
_URL_CRED = re.compile(r"(://)[^/\s:@]+:[^/\s@]+@")
# chave=valor ou chave: valor para nomes que costumam carregar segredo
_SEGREDO = re.compile(
    r"(?i)\b(password|passwd|pwd|senha|secret|token|api[_-]?key|apikey|authorization)"
    r"(\s*[=:]\s*)(?:bearer\s+)?[^\s,;&\"')]+")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def mascarar(texto) -> str:
    """Tira CPF, senha, credencial de URL e token de um texto.

    Melhor esforço por padrões. Serve para o que vai ao log; nunca é a única
    barreira do que vai à resposta — essa é não mandar a mensagem.
    """
    t = str(texto)
    t = _URL_CRED.sub(r"\1***:***@", t)
    t = _SEGREDO.sub(r"\1\2***", t)
    t = _BEARER.sub("Bearer ***", t)
    t = _CPF.sub("***CPF***", t)
    return t


def novo_codigo() -> str:
    """Oito caracteres: cabe num print de tela e não colide na prática."""
    return uuid.uuid4().hex[:8]


def configurar_log() -> None:
    """Manda os eventos deste módulo para a saída padrão, uma linha por evento.

    O Render captura stdout. Uma linha JSON por erro dá para buscar pelo código
    na tela de logs. Idempotente: chamar duas vezes não duplica as linhas.
    """
    if log.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    # Sem isto o uvicorn, que também configura o logger raiz, repetiria a linha.
    log.propagate = False


def _rota(scope: dict) -> str:
    """O modelo da rota, não o caminho real.

    `/predicoes/{cpf}/propostas` em vez de `/predicoes/12345678900/propostas`:
    o caminho real carrega CPF e não pode ir para o log.
    """
    rota = scope.get("route")
    modelo = getattr(rota, "path", None)
    return modelo if modelo else mascarar(scope.get("path", ""))


def _quem(scope: dict) -> tuple:
    """(usuario_id, empresa_id) do token, ou (None, None). Nunca levanta."""
    try:
        from auth import validar_token
        for nome, valor in scope.get("headers", []):
            if nome == b"authorization":
                token = valor.decode("latin-1").split(" ", 1)[-1]
                p = validar_token(token)
                return p.get("sub"), p.get("empresa_id")
    except Exception:
        pass
    return None, None


def registrar(scope: dict, exc: BaseException, status: int) -> str:
    """Grava o evento no log e devolve o código que vai para o cliente."""
    codigo = novo_codigo()
    usuario, empresa = _quem(scope)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    evento = {
        "evento": "erro_interno",
        "codigo": codigo,
        "status": status,
        "metodo": scope.get("method"),
        "rota": _rota(scope),
        "tipo": type(exc).__name__,
        "mensagem": mascarar(getattr(exc, "detail", None) or exc),
        "usuario": usuario,
        "empresa_id": empresa,
        "traceback": mascarar(tb),
    }
    try:
        log.error(json.dumps(evento, ensure_ascii=False))
    except Exception:
        # Registrar não pode ser o que derruba a resposta de erro.
        pass
    return codigo


def _resposta(codigo: str, status: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"detail": MSG_GENERICA.format(codigo=codigo), "codigo_erro": codigo},
    )


class CapturaErros:
    """ASGI puro que converte exceção não tratada em 500 com código.

    Precisa ser instalado ANTES do CORS: no Starlette, o último middleware
    adicionado é o mais externo, e este tem de ficar por dentro dele para a
    resposta sair com os cabeçalhos CORS.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        respondeu = False

        async def enviar(msg):
            nonlocal respondeu
            if msg["type"] == "http.response.start":
                respondeu = True
            await send(msg)

        try:
            await self.app(scope, receive, enviar)
        except Exception as exc:
            # Se a resposta já começou não dá para trocar o corpo: deixa subir.
            if respondeu:
                raise
            codigo = registrar(scope, exc, 500)
            await _resposta(codigo)(scope, receive, send)


async def _handler_http(request, exc: StarletteHTTPException):
    """HTTPException 500 vira genérica; o resto segue o comportamento padrão.

    São os `raise HTTPException(500, detail=f"...{e}")` espalhados pelo código.
    O texto original é registrado no log e não sai na resposta. Qualquer outro
    status — 4xx de validação, 503 de banco do cliente — passa intacto.
    """
    if exc.status_code == 500:
        codigo = registrar(request.scope, exc, 500)
        return _resposta(codigo)
    return await http_exception_handler(request, exc)


def instalar_captura(app) -> None:
    """Chamar ANTES de adicionar o CORS."""
    configurar_log()
    app.add_middleware(CapturaErros)


def instalar_handlers(app) -> None:
    app.add_exception_handler(StarletteHTTPException, _handler_http)
