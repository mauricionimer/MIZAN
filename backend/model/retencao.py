"""
Retenção: por quanto tempo o Mizan guarda o CPF de quem nunca foi seu usuário.

O sistema guarda CPF, nome, dívida e renda estimada de pessoas que não têm
conta aqui e não consentiram nada — elas existem na base porque o banco
cliente mandou a carteira. O usuário do Mizan pode apagar a própria conta;
o devedor não tem esse botão, e até aqui não havia nenhum prazo: o dado
ficava para sempre, inclusive depois do contrato com o cliente terminar.

A LGPD trata os dois lados disso. O Art. 15 encerra o tratamento quando a
finalidade se cumpre, e o Art. 16 manda eliminar o dado depois disso, com
exceções (obrigação legal, estudo por órgão de pesquisa, uso exclusivo do
controlador desde que ANONIMIZADO). O Art. 18 dá ao titular o direito de
pedir eliminação. E o Art. 12 é o que abre a saída: dado anonimizado não é
dado pessoal, e sai do alcance da lei — desde que a anonimização seja
irreversível.

A tensão real está aí. O modelo aprende do resultado: `feedbacks` diz quem
pagou e `predicoes` guarda as variáveis que levaram à previsão. Apagar as
predições antigas destrói a base de treino inteira — é o retrain lendo
feedbacks e buscando as features por `predicao_id`. Mas o aprendizado nunca
precisou saber QUEM era: precisa de (variáveis → resultado). Identidade e
aprendizado são coisas separáveis, e é essa separação que este módulo faz.

Por isso o padrão é anonimizar, não apagar: passado o prazo, `cpf` e `nome`
saem da linha e o resto fica. O modelo continua aprendendo e ninguém fica
identificado. Apagar de verdade acontece em dois casos, e só a pedido: fim
de contrato (expurgo da empresa) e pedido do titular.

Sobre honestidade do termo "anonimizado": tirar CPF e nome de uma linha que
ainda tem UF, valor da dívida e dias de atraso é despersonalização forte,
não uma prova matemática de irreversibilidade. Quem cruzar essa linha com
uma base externa que já tenha esses três campos pode reidentificar. Este
módulo não finge o contrário — quem precisar de garantia formal deve usar o
expurgo, que apaga a linha.

NADA roda por padrão. Sem a empresa configurar um prazo, nenhuma linha é
tocada: apagar dado de cliente por conta própria seria pior do que não ter
a função. O que existe sem configuração é a prévia, que mostra o que
aconteceria se um prazo fosse escolhido.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Colunas que identificam a pessoa em cada tabela. Anonimizar é zerar estas
# e não tocar em mais nada — o resto da linha é o que o modelo aprende.
IDENTIFICADORES = {
    "predicoes":    ("cpf", "nome"),
    "feedbacks":    ("cpf",),
    "contatos":     ("cpf", "observacao"),
    "recomendacoes": ("cpf",),
}

# A observação do contato é campo livre: o operador escreve "falei com a
# esposa no 9 9999-9999". Não dá para anonimizar por partes, então some junto.

MINIMO_DIAS = 30      # abaixo disso o dado sai antes de a cobrança terminar
MAXIMO_DIAS = 3650    # dez anos; acima disso não é retenção, é "para sempre"


@dataclass(frozen=True)
class PoliticaRetencao:
    """Quanto tempo o identificador fica. Sem configuração, nada acontece."""
    ativa: bool = False
    dias: int = 0

    def valida(self) -> "str | None":
        """Devolve o motivo da recusa, ou None se a política puder rodar."""
        if not self.ativa:
            return None
        if self.dias < MINIMO_DIAS:
            return (f"Prazo de {self.dias} dias é curto demais: o mínimo é "
                    f"{MINIMO_DIAS}, senão o dado sai antes de a cobrança acabar.")
        if self.dias > MAXIMO_DIAS:
            return (f"Prazo de {self.dias} dias passa do teto de {MAXIMO_DIAS} "
                    f"(dez anos) — acima disso não é retenção, é guardar para sempre.")
        return None


def de_config(extra: dict) -> PoliticaRetencao:
    """Lê a política de `empresa_config.extra`.

    Formato esperado:

        {"retencao": {"ativa": true, "dias": 365}}

    Qualquer coisa fora disso vira a política inerte — na dúvida sobre o que
    o cliente quis dizer, não apagar nada é a única resposta segura.
    """
    bloco = (extra or {}).get("retencao")
    if not isinstance(bloco, dict):
        return PoliticaRetencao()
    try:
        dias = int(bloco.get("dias", 0))
    except (TypeError, ValueError):
        return PoliticaRetencao()
    return PoliticaRetencao(ativa=bool(bloco.get("ativa")) and dias > 0, dias=dias)


def corte(politica: PoliticaRetencao, agora: "datetime | None" = None) -> "datetime | None":
    """A data-limite: linha mais antiga que isso perde o identificador."""
    if not politica.ativa or politica.valida():
        return None
    agora = agora or datetime.now(timezone.utc)
    return agora - timedelta(days=politica.dias)


def _quando(linha: dict) -> "datetime | None":
    bruto = linha.get("created_at")
    if not bruto:
        return None
    if isinstance(bruto, datetime):
        return bruto if bruto.tzinfo else bruto.replace(tzinfo=timezone.utc)
    try:
        # o PostgREST devolve ISO 8601; o Z é aceito só a partir do 3.11
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    except ValueError:
        return None


def selecionar(linhas: list, politica: PoliticaRetencao,
               agora: "datetime | None" = None) -> list:
    """Ids das linhas que já passaram do prazo e ainda têm identificador.

    Linha sem data não entra: sem saber quando chegou, não dá para dizer que
    o prazo venceu, e o risco de apagar cedo demais é pior que o de tarde.
    """
    limite = corte(politica, agora)
    if limite is None:
        return []
    alvos = []
    for linha in linhas:
        if linha.get("anonimizado_em"):
            continue
        quando = _quando(linha)
        if quando is not None and quando < limite:
            alvos.append(linha.get("id"))
    return [i for i in alvos if i is not None]


def patch_anonimo(tabela: str, agora: "datetime | None" = None) -> dict:
    """O UPDATE que tira a identificação da linha, sem tocar no resto."""
    colunas = IDENTIFICADORES.get(tabela, ("cpf",))
    agora = agora or datetime.now(timezone.utc)
    patch = {c: None for c in colunas}
    patch["anonimizado_em"] = agora.isoformat()
    return patch
