import os
import re
from supabase import create_client, Client

# A biblioteca supabase<=2.10 valida chaves usando regex JWT e rejeita o novo
# formato sb_secret_... / sb_publishable_... do Supabase. Este patch substitui
# o módulo `re` dentro do namespace do client para aceitar ambos os formatos.
import supabase._sync.client as _sc

class _PatchedRe:
    _JWT_PATTERN = r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"

    def match(self, pattern, string, *args, **kwargs):
        if (pattern == self._JWT_PATTERN
                and isinstance(string, str)
                and (string.startswith("sb_secret_") or string.startswith("sb_publishable_"))):
            return re.match(r".+", string)
        return re.match(pattern, string, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(re, name)

_sc.re = _PatchedRe()

import threading

# Um cliente POR THREAD, não um para o processo inteiro.
#
# O cliente do PostgREST fala HTTP/2 (http2=True dentro da biblioteca), e uma
# conexão HTTP/2 do httpx não é segura para várias threads ao mesmo tempo. As
# rotas síncronas do FastAPI rodam num pool de threads, e o Dashboard dispara
# umas seis buscas juntas: com um cliente só, elas disputavam a mesma conexão e
# falhavam de forma intermitente — 503 "Não foi possível validar o acesso à
# carteira" e 500 em pagamentos, alcance e status, voltando a cada troca de aba.
# O pool tem poucas dezenas de threads, então são poucas dezenas de clientes.
_local = threading.local()


def get_db() -> Client:
    cliente = getattr(_local, "cliente", None)
    if cliente is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL e SUPABASE_KEY ausentes no .env")
        cliente = create_client(url, key)
        _local.cliente = cliente
    return cliente
