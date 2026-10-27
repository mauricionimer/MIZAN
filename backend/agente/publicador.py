"""Fila limitada e descartável de observabilidade, fora da resposta ao cliente.

Uma thread por processo; snapshots ainda aguardando gravação são substituídos
pelo mais recente do mesmo evento. Não serve para eventos de negócio.
"""
from queue import Queue, Full
from threading import Lock, Thread


class Publicador:
    def __init__(self, limite=128):
        self._fila = Queue(maxsize=limite)
        self._pendentes = {}
        self._lock = Lock()
        self._thread = None

    def publicar(self, chave, gravar, dados):
        with self._lock:
            if chave in self._pendentes:
                self._pendentes[chave] = (gravar, dados)
                return True
            self._pendentes[chave] = (gravar, dados)
            try:
                self._fila.put_nowait(chave)
            except Full:
                self._pendentes.pop(chave, None)
                return False
            if self._thread is None:
                self._thread = Thread(target=self._rodar, name="mizan-observabilidade", daemon=True)
                self._thread.start()
        return True

    def _rodar(self):
        while True:
            chave = self._fila.get()
            try:
                with self._lock:
                    gravar, dados = self._pendentes.pop(chave)
                gravar(dados)
            except Exception as e:
                # Nunca registra payload, texto do devedor ou credenciais.
                print(f"[Agente] observabilidade indisponível: {type(e).__name__}")
            finally:
                self._fila.task_done()


publicador = Publicador()
