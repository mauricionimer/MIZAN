"""Quais normas entram na base jurídica, por quê, com qual recorte e qual fonte oficial.

Acervo inicial: https://github.com/ctresb/leis (textos convertidos de normas.leg.br e do
DOU; licença MIT para os scripts; os textos são atos oficiais, sem proteção autoral pelo
art. 8º, I, da Lei nº 9.610/98). O próprio acervo avisa que é conversão automática e não
substitui a publicação oficial: aqui ele é cópia de consulta. A redação e a vigência se
confirmam na fonte oficial (conferencia.py); enquanto não confirmadas, cada consulta
sinaliza a limitação ao orquestrador.

Seleção pela operação da Mizan (recuperação de crédito com agente que conversa com o
devedor): proteção de dados, crédito, consumidor e cobrança. Não se ingere o acervo
inteiro (17 GB): custo, ruído na busca e textos sem relação com a operação.
"""
from dataclasses import dataclass, field

ACERVO_URL = "https://github.com/ctresb/leis"


@dataclass(frozen=True)
class Norma:
    id: str
    sigla: str                  # como o dispositivo é nomeado no registro interno: "LGPD, art. 20"
    caminho: str                # arquivo no acervo
    url_oficial: str            # onde conferir a redação vigente
    motivo: str                 # por que entra
    recorte: tuple = ()         # faixas de artigos ((de, até), ...); vazio = norma inteira
    prioridade: int = 1         # 1 = principal; em texto repetido, fica o de menor prioridade
    aplica_se: str = ""         # alcance, quando não é geral
    observacoes: tuple = ()     # limitações conhecidas desta cópia
    # Alterações posteriores conhecidas que o texto do acervo NÃO incorpora:
    # (artigo, descrição). O dispositivo fica marcado como desatualizado.
    alteracoes: tuple = ()
    temas: tuple = field(default=())


CATALOGO = (
    Norma("lgpd", "LGPD", "federal/leis-ordinarias/2018/lei-13709-2018-08-14.md",
          "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm",
          "Tratamento de dados pessoais de devedores: bases legais, princípios, direitos do titular, "
          "decisão automatizada, encarregado e segurança.",
          temas=("dados_pessoais", "direitos_titular", "decisao_automatizada")),
    Norma("cdc", "CDC", "federal/leis-ordinarias/1990/lei-8078-1990-09-11.md",
          "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
          "Cobrança de dívidas (arts. 42, 42-A e 71), cadastros de consumidores (art. 43), crédito e "
          "superendividamento (arts. 52 e 54-A a 54-G; já inclui as alterações da Lei nº 14.181/2021).",
          temas=("cobranca", "credito", "consumidor", "superendividamento")),
    Norma("cadastro_positivo", "Lei do Cadastro Positivo", "federal/leis-ordinarias/2011/lei-12414-2011-06-09.md",
          "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12414.htm",
          "Histórico de crédito e direitos do cadastrado, inclusive revisão de decisão automatizada.",
          temas=("credito", "decisao_automatizada", "dados_pessoais")),
    Norma("codigo_civil", "Código Civil", "federal/leis-ordinarias/2002/lei-10406-2002-01-10.md",
          "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
          "Só o que a cobrança usa: prescrição, cessão de crédito, pagamento e quitação, inadimplemento "
          "e juros, e cobrança de dívida já paga. O resto do código (680 KB) não entra.",
          recorte=((189, 211), (286, 298), (304, 333), (389, 407), (939, 941)),
          temas=("cobranca", "credito")),
    Norma("marco_civil", "Marco Civil da Internet", "federal/leis-ordinarias/2014/lei-12965-2014-04-23.md",
          "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm",
          "Direitos do usuário de internet sobre dados e comunicações (canais digitais da cobrança).",
          recorte=((3, 3), (7, 7), (10, 10)), temas=("dados_pessoais", "comunicacao")),
    Norma("decreto_11150", "Decreto nº 11.150/2022", "federal/decretos/2022/dec-11150-2022-07-26.md",
          "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/d11150.htm",
          "Mínimo existencial no superendividamento: limita o que um acordo pode comprometer.",
          observacoes=("O acervo traz a redação ORIGINAL deste decreto, sem as alterações posteriores.",),
          alteracoes=(("3", "Redação alterada pelo Decreto nº 11.567/2023 (art. 1º), que mudou o valor do "
                            "mínimo existencial e revogou o § 2º. O texto deste dispositivo no acervo está "
                            "desatualizado: use a redação vigente da fonte oficial."),),
          temas=("superendividamento", "credito")),
    Norma("decreto_11567", "Decreto nº 11.567/2023", "federal/decretos/2023/dec-11567-2023-06-19.md",
          "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/d11567.htm",
          "Altera o Decreto nº 11.150/2022 (valor do mínimo existencial). Entra para a redação nova "
          "ficar na busca ao lado da antiga, marcada como desatualizada.",
          prioridade=2, temas=("superendividamento",)),
    Norma("cmn_4949", "Resolução CMN nº 4.949/2021",
          "reguladores/bcb/resolucoes/2021/resolucao-cmn-n-4.949-de-30-de-setembro-de-2021-350015767.md",
          "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=4949",
          "Relacionamento de instituições financeiras com clientes, inclusive tratamento de dados e "
          "sistemática de cobrança no inadimplemento (art. 7º).",
          aplica_se="instituições financeiras e demais autorizadas pelo Banco Central (clientes da Mizan)",
          observacoes=("Publicação original no DOU; alterações posteriores não verificadas no acervo.",),
          temas=("cobranca", "dados_pessoais")),
)

# Avaliadas e deixadas de fora (fica registrado no manifesto).
DESCARTADAS = (
    ("federal/leis-ordinarias/2021/lei-14181-2021-07-01.md",
     "Lei que altera o CDC: o texto dela já está no CDC compilado; ingerir duplicaria os dispositivos."),
    ("constituicao.md", "Arquivo muito grande para o ganho; os direitos de privacidade e proteção de dados "
                        "aplicáveis à operação estão detalhados na LGPD e no CDC."),
    ("estaduais/ e municipais/", "Fora do escopo inicial. Leis estaduais e municipais sobre cobrança e "
                                 "telemarketing podem impor regras locais: avaliar por estado de atuação."),
)

POR_ID = {n.id: n for n in CATALOGO}
