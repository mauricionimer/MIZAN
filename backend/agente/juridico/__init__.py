"""Base jurídica interna do orquestrador (RAG jurídico). Ver docs/RAG_JURIDICO.md.

O orquestrador consulta a legislação antes de ações e estratégias com impacto
jurídico (dados pessoais, decisão automatizada de crédito, estratégia e canal de
cobrança, oferta de acordo, pedidos do titular). A consulta orienta e limita o
que o sistema faz; a fundamentação fica nos bastidores e nunca vai, por
iniciativa do sistema, para a conversa com o devedor.

- catalogo.py    quais normas entram, por quê, com qual recorte e fonte oficial
- estrutura.py   texto da norma em artigo, parágrafo, inciso e alínea, com contexto
- ingestao.py    monta o índice a partir do acervo (incremental, com deduplicação)
- conferencia.py compara o texto com a fonte oficial e registra o resultado
- indice.py      busca híbrida: termos exatos (BM25) + semântica local (LSA)
- consulta.py    consultar_legislacao(pergunta, contexto_da_acao)
- decisao.py     decisão interna: prosseguir, com condições, não prosseguir, revisão humana
- registro.py    registro auditável da decisão (sem dado pessoal; contexto cifrado)
"""
