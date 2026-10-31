"""Sinais na mensagem do devedor que importam para a análise jurídica interna.

Regras em código, sem IA e sem guardar o texto: cada função lê a mensagem e devolve só
um rótulo (ou sim/não). O rótulo vai para os fatos da decisão; o texto não vai.
"""
import re

from agente.juridico.texto import sem_acento


def _t(texto: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(str(texto or "")).lower())


# A pessoa pede a lei ou o fundamento. Só então o atendente cita norma.
_PEDIU_FUNDAMENTO = re.compile(
    r"\b(qual|que|quais|em que|segundo qual|onde) (e a |e o |sao as |sao os )?(lei|leis|artigo|artigos|norma|normas"
    r"|regra|regras|sumula|base legal|fundamento|legislacao)\b"
    r"|\b(lei|artigo|norma|legislacao|base legal|fundamento legal|sumula)\b.{0,30}\?"
    r"|\bonde (diz|fala|esta escrito|esta isso|consta)\b|\b(me )?(mostra|passa|cita|manda|diz|informa)\w* (a |o |qual )?"
    r"(lei|artigo|norma|fundamento|base legal)\b|\b(lgpd|cdc|codigo de defesa|codigo civil|stj)\b"
    r"|\bqual (e )?o (numero|n) da lei\b|\bpor lei\?|\bisso e lei\b|\btem lei\b|\bexiste (uma )?lei\b")


def pediu_fundamento(texto: str) -> bool:
    return bool(_PEDIU_FUNDAMENTO.search(_t(texto)))


# Pedido do titular sobre os próprios dados. A ordem importa: o primeiro que bate vale.
_DADOS = r"(meus dados|meus dados pessoais|minhas informac\w*|meu cadastro|minha ficha|meu numero|meu telefone|meu contato" \
         r"|meu e-?mail|meu endereco|meu cpf|os dados|esses dados|dados pessoais)"
_PEDIDOS = [
    ("revisao_decisao", r"\b(revis\w*|reanalis\w*|reavali\w*) (d[ae] |dessa |desta |essa |esta |a |o )?(decisao|analise|avaliacao)"
                        r"|\bdecisao automati\w*|\bdecidid[oa] (so )?(por|pelo) (robo|sistema|maquina|computador|algoritmo)"
                        r"|\b(quero|pec\w*|gostaria) (que )?(uma pessoa|um humano|alguem) (revis|reanalis|reavali)\w*"
                        r"|\bquais (foram )?os criterios\b|\bque criterios (voces|vcs|foram)"),
    ("revogacao", r"\b(revog\w*|retir\w*|cancel\w*) (o |meu |a minha |minha )?(consentimento|autorizac\w*)"
                  r"|\bnao (dou|autorizo mais|consinto)( mais)? (o )?(meu )?consentimento"),
    ("oposicao", r"\bnao (autorizo|permito|aceito|quero) (que )?(voces |vcs |a empresa )?(o uso|usar|usem|utilizem|tratem|tratar"
                 r"|guardem|compartilhem|compartilhar) (d?os )?" + _DADOS +
                 r"|\b(me oponho|oposicao) (a|ao) (uso|tratamento) (d?os )?" + _DADOS +
                 r"|\b(proibo|nao autorizo) (o uso|o tratamento) (d?os )?" + _DADOS),
    ("eliminacao", r"\b(apag|exclu|delet|remov|elimin|destru)\w* (todos |todas )?(os |as )?" + _DADOS +
                   r"|\b" + _DADOS + r" (sejam |seja )?(apagad|excluid|deletad|removid|eliminad)\w*"
                   r"|\b(direito ao esquecimento|esquecam (os )?meus dados)"),
    ("correcao", r"\b(corrig|atualiz|retific|alter|mud)\w* (os |o |a |as )?" + _DADOS +
                 r"|\b" + _DADOS + r" (esta|estao|ta|tao) (errad|incorret|desatualizad|incomplet)\w*"
                 r"|\b(dado|dados|informac\w*|cadastro|endereco|nome) (errad|incorret|desatualizad)\w* no (meu )?cadastro"),
    ("portabilidade", r"\bportabilidade (d?os )?(meus )?dados\b"),
    ("informacao", r"\bcom quem (voces |vcs |a empresa )?(compartilh|pass|repass|vend|envi)\w* " + _DADOS +
                   r"|\b(voces|vcs|a empresa) (compartilh|vend|repass|pass)\w* " + _DADOS + r" (para|pra|com)"
                   r"|\b(voces|vcs|a empresa) (compartilh|vend|repass)\w* " + _DADOS +
                   r"|\b(o que|que) (voces|vcs|a empresa) (fazem|faz|fizeram|vao fazer) com " + _DADOS +
                   r"|\b(para que|pra que|por que) (voces |vcs )?(usam|guardam|tem|precisam d)\w* " + _DADOS +
                   r"|\b(quem e o )?encarregado (de|dos|pelo tratamento de) dados\b|\bdpo\b"),
    ("origem", r"\b(onde|como|de onde) (voces |vcs |a empresa |o senhor |a senhora )?(conseguiu|conseguiram|pegou|pegaram"
               r"|obteve|obtiveram|achou|acharam|arrumou|arrumaram|tiraram|tirou) (o |os )?" + _DADOS +
               r"|\bde onde (vieram|veio|saiu|sairam) (o |os )?" + _DADOS),
    ("acesso", r"\b(quais|que) (dados|informac\w*) (voces |vcs |a empresa )?(tem|possuem|possui|guardam|guarda|tem guardad\w*)"
               r" (sobre|de|a respeito de) mim\b"
               r"|\b(acesso|copia|relatorio|lista) (a |aos |dos |de )?(todos )?(os )?" + _DADOS +
               r"|\b(quero|gostaria de|preciso) (saber|ver|receber) (quais|que|todos os) (dados|informac\w*)"),
]
_PEDIDOS = [(nome, re.compile(rx)) for nome, rx in _PEDIDOS]

ROTULO_PEDIDO = {"acesso": "acesso aos dados", "informacao": "informação sobre o uso e o compartilhamento dos dados",
                 "origem": "origem dos dados", "correcao": "correção de dados", "eliminacao": "eliminação de dados",
                 "oposicao": "oposição ao uso dos dados", "revogacao": "revogação do consentimento",
                 "revisao_decisao": "revisão de decisão automatizada", "portabilidade": "portabilidade dos dados"}


def pedido_titular(texto: str) -> str | None:
    """O tipo de pedido sobre os próprios dados, se a mensagem traz um."""
    t = _t(texto)
    return next((nome for nome, rx in _PEDIDOS if rx.search(t)), None)


# Sinais de superendividamento: a pessoa diz que as dívidas comprometem o básico.
_SUPERENDIVIDAMENTO = re.compile(
    r"superendivid|\b(muitas|varias|um monte de|tantas|monte de) dividas\b|\bendividad[oa] (ate|demais|em tudo)"
    r"|\bdevo (pra|para|a) (todo mundo|tudo quanto e|varios|muitos)\b|\bnome sujo em (tudo|todo lugar|varios)"
    r"|\bnao (me )?sobra (nada|dinheiro|nem)\b|\b(minha )?renda (toda|inteira|ja) (esta |ta |fica )?comprometid"
    r"|\bnao (tenho|sobra|consigo|da) (dinheiro )?(nem )?(pra|para) (comer|o basico|aluguel|a luz|luz|agua|remedio|comida|o mercado)"
    r"|\b(passando|passo|estou passando) fome\b|\bsem (dinheiro|renda) (nenhum|nenhuma|alguma) (pra|para) (comer|viver)"
    r"|\bmais (dividas|parcelas) do que (eu )?(ganho|recebo)\b|\bganho menos do que devo\b")


def superendividamento(texto: str) -> bool:
    return bool(_SUPERENDIVIDAMENTO.search(_t(texto)))


# Pressão para aceitar, no texto do próprio agente (as travas já barram ameaça).
_PRESSAO = re.compile(r"\b(so (ate )?hoje|ultima (chance|oportunidade)|agora ou nunca|e pegar ou largar"
                      r"|nao (vai|vou) (ter|conseguir) (de novo|outra (vez|chance|oferta))|corra|aproveite (ja|logo|agora))\b")


def pressao(texto: str) -> bool:
    return bool(_PRESSAO.search(_t(texto)))
