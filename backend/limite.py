"""
Limite de requisições e de análises simultâneas.

Só o login tinha freio. Upload, backtest e as sondas de banco de dados não
tinham nenhum, e "esqueci minha senha" disparava e-mail para qualquer endereço
quantas vezes fosse chamado.

Duas coisas diferentes, porque são dois problemas:

  Taxa           quantas vezes por janela. Protege contra script e abuso.
  Simultâneas    quantas análises ao mesmo tempo. Protege a MEMÓRIA, e é o
                 risco maior: medido, uma carteira de 200 mil devedores leva o
                 processo a 542 MB. Duas análises ao mesmo tempo — ou um duplo
                 clique — estouram os 512 MB do plano gratuito, e nenhum limite
                 por minuto impede isso.

Quem é "o usuário": o `sub` do JWT; se o token não for um JWT (chave de API), o
hash do cabeçalho; se não houver credencial, a requisição passa e a rota a
recusa com 401. IP não serve de chave: atrás do proxy do Render,
`request.client.host` costuma ser o do proxy, igual para todos, e o limite
viraria um balde global que uns usuários esgotam para os outros.

Limite deste arquivo é por PROCESSO. Com duas instâncias o teto efetivo é o
dobro. É um freio contra abuso e acidente, não contabilidade exata; contar em
banco a cada requisição custaria uma ida ao Supabase em toda chamada.

É ASGI puro, instalado antes do CORS, por dois motivos. Rejeita antes de o
corpo ser lido — um upload de 100 MB recusado depois de recebido já gastou o
que se queria poupar. E fica por dentro do CORS, para o 429 sair com o
cabeçalho e o navegador poder mostrar a mensagem em vez de "Failed to fetch".
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

log = logging.getLogger("mizan.limite")

# Teto de chaves rastreadas. Um cliente que gera tokens inventados a cada
# chamada criaria um balde novo por requisição; sem teto, a memória cresceria.
MAX_CHAVES = 20_000


@dataclass(frozen=True)
class Regra:
    balde: str       # regras com o mesmo balde dividem a mesma cota
    maximo: int
    janela_s: int
    mensagem: str
    pesada: bool = False    # também passa pelo portão de análises simultâneas


REGRAS = {
    ("POST", "/analisar"):     Regra("analise", 10, 600,
        "Muitas análises em pouco tempo. Aguarde {espera} s e tente de novo.", pesada=True),
    ("POST", "/analisar/db"):  Regra("analise", 10, 600,
        "Muitas análises em pouco tempo. Aguarde {espera} s e tente de novo.", pesada=True),
    ("POST", "/backtest"):     Regra("analise", 10, 600,
        "Muitas análises em pouco tempo. Aguarde {espera} s e tente de novo.", pesada=True),
    # Sondar conexões: cada chamada abre uma conexão com um banco de terceiros e
    # devolve o motivo da falha. Sem freio, serve para testar credenciais.
    ("POST", "/listar-tabelas"): Regra("sonda_db", 20, 600,
        "Muitas tentativas de conexão. Aguarde {espera} s."),
    ("POST", "/testar-db"):      Regra("sonda_db", 20, 600,
        "Muitas tentativas de conexão. Aguarde {espera} s."),
}


class Limitador:
    """Janela deslizante em memória, segura entre threads."""

    def __init__(self, relogio=time.monotonic):
        self._agora = relogio
        self._marcas: "OrderedDict[str, deque]" = OrderedDict()
        self._trava = threading.Lock()

    def tentar(self, chave: str, maximo: int, janela_s: int) -> tuple:
        """Registra uma tentativa. Devolve (permitida, segundos_de_espera)."""
        agora = self._agora()
        limite = agora - janela_s
        with self._trava:
            marcas = self._marcas.get(chave)
            if marcas is None:
                marcas = deque()
                self._marcas[chave] = marcas
                # Estourou o teto: descarta as mais antigas em vez de deixar de
                # rastrear as novas — o contrário desligaria o limite justamente
                # sob a inundação que ele existe para segurar.
                while len(self._marcas) > MAX_CHAVES:
                    self._marcas.popitem(last=False)
            while marcas and marcas[0] <= limite:
                marcas.popleft()
            if len(marcas) >= maximo:
                espera = int(marcas[0] + janela_s - agora) + 1
                return False, max(espera, 1)
            marcas.append(agora)
            return True, 0

    def limpar(self) -> None:
        with self._trava:
            self._marcas.clear()


LIMITADOR = Limitador()


def identidade(scope: dict) -> "str | None":
    """Quem está chamando, sem tocar em IP. None se não houver credencial."""
    for nome, valor in scope.get("headers", []):
        if nome != b"authorization":
            continue
        bruto = valor.decode("latin-1")
        token = bruto.split(" ", 1)[-1]
        try:
            from auth import validar_token
            sub = validar_token(token).get("sub")
            if sub:
                return f"u:{sub}"
        except Exception:
            pass
        # Não é JWT válido: pode ser chave de API. O hash identifica a
        # credencial sem guardá-la.
        return "k:" + hashlib.sha256(bruto.encode()).hexdigest()[:16]
    return None


def _simultaneas() -> int:
    try:
        return max(1, int(os.getenv("MIZAN_ANALISES_SIMULTANEAS", "2")))
    except ValueError:
        return 2


class LimiteDeRequisicoes:
    """Aplica as regras antes de a rota (e o corpo) existirem."""

    def __init__(self, app, regras=None, simultaneas=None, limitador=None):
        self.app = app
        self.regras = REGRAS if regras is None else regras
        self.limitador = limitador or LIMITADOR
        self._portao = threading.BoundedSemaphore(simultaneas or _simultaneas())

    async def _recusar(self, scope, receive, send, mensagem, espera):
        from fastapi.responses import JSONResponse
        resposta = JSONResponse(
            status_code=429,
            content={"detail": mensagem, "espera_s": espera},
            headers={"Retry-After": str(espera)},
        )
        await resposta(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        regra = self.regras.get((scope["method"], scope["path"]))
        if regra is None:
            return await self.app(scope, receive, send)

        quem = identidade(scope)
        if quem is None:
            # Sem credencial não há o que limitar: a rota devolve 401.
            return await self.app(scope, receive, send)

        # O portão vem ANTES da taxa. Se fosse depois, quem esbarra num portão
        # cheio gastaria uma cota a cada nova tentativa e acabaria bloqueado por
        # taxa por ter insistido — punindo justamente quem só quer a vez.
        segurou = False
        if regra.pesada:
            segurou = self._portao.acquire(blocking=False)
            if not segurou:
                log.warning(json.dumps({"evento": "portao_cheio", "rota": scope["path"]}))
                return await self._recusar(
                    scope, receive, send,
                    "Já há análises em andamento. Aguarde alguns instantes e tente de novo.", 15)

        try:
            ok, espera = self.limitador.tentar(f"{regra.balde}:{quem}", regra.maximo, regra.janela_s)
            if not ok:
                log.warning(json.dumps({"evento": "limite_excedido", "balde": regra.balde,
                                        "rota": scope["path"], "usuario": quem}))
                return await self._recusar(
                    scope, receive, send, regra.mensagem.format(espera=espera), espera)
            await self.app(scope, receive, send)
        finally:
            if segurou:
                self._portao.release()


# Teto de corpo por rota, em bytes. O multipart acrescenta cabeçalhos às partes;
# a folga cobre isso sem deixar passar um arquivo de verdade maior que o limite.
MB = 1024 * 1024
FOLGA_MULTIPART = 64 * 1024
TETOS_CORPO = {
    ("POST", "/analisar"):        25 * MB,
    ("POST", "/backtest"):        25 * MB,
    ("POST", "/upload"):          25 * MB,
    ("POST", "/feedback/lote"):   25 * MB,
    ("POST", "/empresa/foto"):    5 * MB,
}
TETO_PADRAO = 2 * MB   # qualquer outra rota POST/PUT/PATCH: JSON pequeno


class LimiteDeTamanho:
    """Recusa corpo grande ANTES de ele virar memória.

    Antes, as rotas faziam `await file.read()` e só depois comparavam o tamanho:
    o teto de 25 MB não protegia nada, o arquivo inteiro já estava na RAM (e o
    /upload e o /feedback/lote nem tinham teto). Aqui:

      - Content-Length acima do teto: 413 sem ler nenhum byte.
      - Sem Content-Length (chunked) ou mentindo: conta os bytes que passam e,
        no estouro, entrega fim-de-corpo à rota (para de ler) e troca a resposta
        dela por 413. Trocar é necessário porque o FastAPI converte a falha de
        leitura do corpo em 400/422, e o cliente precisa ver "grande demais".
    """

    def __init__(self, app, tetos=None, padrao=None):
        self.app = app
        self.tetos = TETOS_CORPO if tetos is None else tetos
        self.padrao = TETO_PADRAO if padrao is None else padrao

    @staticmethod
    def _mensagem(teto):
        return f"Arquivo ou corpo muito grande. Limite: {teto // MB} MB." if teto >= MB \
            else "Corpo da requisição muito grande."

    async def _recusar(self, scope, receive, send, teto):
        from fastapi.responses import JSONResponse
        resposta = JSONResponse(status_code=413, content={"detail": self._mensagem(teto)},
                                headers={"Connection": "close"})
        await resposta(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)

        base = self.tetos.get((scope["method"], scope["path"]))
        teto = self.padrao if base is None else base
        maximo = teto + (FOLGA_MULTIPART if base is not None else 0)

        for nome, valor in scope.get("headers", []):
            if nome == b"content-length":
                try:
                    if int(valor) > maximo:
                        log.warning(json.dumps({"evento": "corpo_grande", "rota": scope["path"],
                                                "bytes": int(valor)}))
                        return await self._recusar(scope, receive, send, teto)
                except ValueError:
                    pass
                break

        estado = {"lidos": 0, "estourou": False, "respondeu": False}

        async def receber():
            if estado["estourou"]:
                return {"type": "http.request", "body": b"", "more_body": False}
            msg = await receive()
            if msg["type"] == "http.request":
                estado["lidos"] += len(msg.get("body", b""))
                if estado["lidos"] > maximo:
                    estado["estourou"] = True
                    log.warning(json.dumps({"evento": "corpo_grande", "rota": scope["path"],
                                            "bytes": ">" + str(maximo)}))
                    return {"type": "http.request", "body": b"", "more_body": False}
            return msg

        async def enviar(msg):
            if not estado["estourou"]:
                return await send(msg)
            # A resposta da rota é descartada; sai a 413 uma única vez.
            if not estado["respondeu"]:
                estado["respondeu"] = True
                await self._recusar(scope, receive, send, teto)

        await self.app(scope, receber, enviar)


def instalar(app) -> None:
    """Chamar ANTES de instalar a captura de erros e o CORS."""
    app.add_middleware(LimiteDeRequisicoes)
    # Por fora da taxa: um corpo grande demais não gasta cota nem ocupa o portão.
    app.add_middleware(LimiteDeTamanho)
