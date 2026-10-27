"""Mede a API sem registrar URLs, parâmetros, tokens ou dados de clientes."""
import json
import logging
import time
import uuid

log = logging.getLogger("uvicorn.error")


class MedirDesempenho:
    def __init__(self, app, limite_ms=1000):
        self.app, self.limite_ms = app, limite_ms

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        inicio = time.perf_counter()
        codigo = uuid.uuid4().hex[:16]
        status = 500

        async def enviar(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                ms = (time.perf_counter() - inicio) * 1000
                message = {**message, "headers": [*message.get("headers", []),
                           (b"server-timing", f"app;dur={ms:.1f}".encode()),
                           (b"x-request-id", codigo.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ms = (time.perf_counter() - inicio) * 1000
            if ms >= self.limite_ms or status >= 500:
                # Somente o template da rota. Nem mesmo a URL de um 404 é registrada.
                rota = getattr(scope.get("route"), "path", "sem_rota")
                log.info(json.dumps({"evento": "api_desempenho", "request_id": codigo,
                                     "rota": rota, "status": status, "duracao_ms": round(ms, 1)}))
