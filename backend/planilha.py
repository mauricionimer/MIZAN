"""
Trava contra planilha "bomba de descompactação".

O limite de 25 MB do upload vale para o arquivo COMPACTADO. Um .xlsx de
~120 KB pode virar centenas de MB de XML, e o openpyxl carrega as células na
memória: a instância tem 512 MB, e um usuário derrubava o serviço de todos.

A conferência lê só o índice do zip, ANTES de qualquer leitor de Excel. O
tamanho declarado no índice é confiável aqui: o zipfile do Python não entrega
mais bytes do que o declarado.
"""

import io
import zipfile

XLSX_MAX_DESCOMPACTADO = 80 * 1024 * 1024
XLSX_MAX_ARQUIVOS = 500


class PlanilhaRecusada(ValueError):
    """Planilha que não pode ir ao leitor de Excel; a mensagem diz o que fazer."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status


def conferir(conteudo: bytes, nome: str) -> None:
    """Recusa .xls e .xlsx que descompactam demais. Levanta PlanilhaRecusada."""
    if (nome or "").lower().endswith(".xls"):
        raise PlanilhaRecusada(400, "Formato .xls antigo não é aceito. Salve como .xlsx ou CSV.")
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            infos = z.infolist()
    except zipfile.BadZipFile:
        raise PlanilhaRecusada(422, "Arquivo Excel inválido ou corrompido.")
    if len(infos) > XLSX_MAX_ARQUIVOS or sum(i.file_size for i in infos) > XLSX_MAX_DESCOMPACTADO:
        raise PlanilhaRecusada(413, "Planilha grande demais depois de aberta (limite de 80 MB). Exporte como CSV.")
