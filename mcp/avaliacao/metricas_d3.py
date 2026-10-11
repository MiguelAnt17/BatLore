"""Métricas da avaliação do D3 (agente MCP do Alfred).

Cada função recebe os dados de UMA pergunta e devolve números simples.
O avaliar_d3.ipynb chama-as pergunta a pergunta e faz as médias.

Cinco grupos:
    1. Ferramentas      o agente escolheu as ferramentas certas?
    2. Servidor         as chamadas MCP funcionaram e quanto demoraram?
    3. Argumentos       os argumentos enviados eram válidos e adequados?
    4. Testes diretos   cada ferramenta funciona sozinha, sem LLM?
    5. Resposta         juiz de correção (pass/fail) e nota 0-10

Uma "chamada" é um dicionário registado pelo notebook em cada chamada MCP:
    {"ferramenta": "pesquisar_web", "argumentos": {...}, "origem": "llm" ou "codigo",
     "ok": True/False, "segundos": 1.2, "saida": "texto devolvido"}
"""

import math
import re

# "relevancia" é sempre chamada pelo código (nunca é uma escolha do LLM): não conta como escolha.
FERRAMENTAS_IGNORADAS = {"relevancia"}


# ---------------------------------------------------------------------------
# 1. Ferramentas escolhidas
# ---------------------------------------------------------------------------
# Cada entrada de "ferramentas_esperadas" é um nome, ou alternativas separadas por "|"
# ("pesquisar_web|pesquisar_noticias": qualquer uma das duas serve).


def nomes_chamados(chamadas, so_llm=False):
    """Nomes distintos das ferramentas chamadas (sem as ignoradas).

    so_llm=True: só as que o LLM pediu, sem as que o código chama sempre.
    """
    nomes = []
    for c in chamadas:
        if so_llm and c["origem"] != "llm":
            continue
        if c["ferramenta"] in FERRAMENTAS_IGNORADAS or c["ferramenta"] in nomes:
            continue
        nomes.append(c["ferramenta"])
    return nomes


def metricas_ferramentas(chamadas, esperadas, permitidas=()):
    """ToolHit, ToolRecall, ToolPrecision e NumToolCalls de uma pergunta.

    ToolRecall    = entradas esperadas que foram chamadas / entradas esperadas
    ToolHit       = 1 se pelo menos uma entrada esperada foi chamada
    ToolPrecision = ferramentas pedidas pelo LLM que eram esperadas ou permitidas / pedidas pelo LLM
                    (NaN se o LLM não pediu nenhuma)
    NumToolCalls  = número de chamadas (sem as ignoradas)
    """
    usadas = nomes_chamados(chamadas)
    escolhidas = nomes_chamados(chamadas, so_llm=True)
    grupos = [set(e.split("|")) for e in esperadas]
    aceites = set(permitidas).union(*grupos)

    satisfeitas = [bool(g & set(usadas)) for g in grupos]
    certas = [f for f in escolhidas if f in aceites]
    return {
        "ToolHit": float(any(satisfeitas)) if grupos else math.nan,
        "ToolRecall": sum(satisfeitas) / len(grupos) if grupos else math.nan,
        "ToolPrecision": len(certas) / len(escolhidas) if escolhidas else math.nan,
        "NumToolCalls": sum(c["ferramenta"] not in FERRAMENTAS_IGNORADAS for c in chamadas),
    }


# ---------------------------------------------------------------------------
# 2. Servidor MCP: fiabilidade e latência (a partir das chamadas registadas)
# ---------------------------------------------------------------------------


def metricas_servidor(chamadas):
    """TaxaSucesso e LatenciaMedia das chamadas MCP de uma pergunta.

    TaxaSucesso   = chamadas sem erro / chamadas (conta todas, também as do código)
    LatenciaMedia = média dos segundos de cada chamada (NaN se não houver tempos)
    """
    tempos = [c["segundos"] for c in chamadas if c.get("segundos") is not None]
    return {
        "TaxaSucesso": sum(c["ok"] for c in chamadas) / len(chamadas) if chamadas else math.nan,
        "LatenciaMedia": sum(tempos) / len(tempos) if tempos else math.nan,
    }


# ---------------------------------------------------------------------------
# 3. Argumentos das chamadas
# ---------------------------------------------------------------------------
# 3a. ArgsValidos (sem LLM): confere os argumentos com o esquema da ferramenta.
# O esquema vem do servidor (list_tools), por exemplo:
#   {"properties": {"consulta": {"type": "string"}, "max_resultados": {"type": "integer"}},
#    "required": ["consulta"]}

TIPOS_PYTHON = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def tipos_aceites(propriedade):
    """Tipos Python que um parâmetro aceita ('str | None' vem como anyOf)."""
    tipos = ()
    for opcao in propriedade.get("anyOf", [propriedade]):
        tipos += TIPOS_PYTHON.get(opcao.get("type"), ())
    return tipos


def tipo_certo(valor, tipos):
    if not tipos:
        return True   # o esquema não diz o tipo: aceita tudo
    if isinstance(valor, bool) and bool not in tipos:
        return False  # em Python True é um int: aqui não conta como número
    return isinstance(valor, tipos)


def argumentos_validos(args, esquema):
    """1.0 se tem todos os argumentos obrigatórios, nenhum desconhecido e os tipos certos; senão 0.0."""
    propriedades = esquema.get("properties", {})
    for nome in esquema.get("required", []):
        if nome not in args:
            return 0.0
    for nome, valor in args.items():
        if nome not in propriedades or not tipo_certo(valor, tipos_aceites(propriedades[nome])):
            return 0.0
    return 1.0


# 3b. ArgsAdequados (juiz Gemma): os valores fazem sentido para a pergunta?
# Só se avaliam as chamadas pedidas pelo LLM: as do código usam sempre a pergunta tal e qual.

PROMPT_ARGUMENTOS = """You will be given a user question and a tool call made by an assistant. Decide if the arguments of the call are adequate to answer the question: the right values, nothing important missing, nothing made up.

Return 'pass' if the arguments are adequate, 'fail' if they are not.

Question: {question}
Tool: {tool} - {description}
Arguments: {arguments}

Evaluation:"""


def extrair_pass_fail(texto):
    """1.0 para 'pass', 0.0 para 'fail' (a primeira palavra que aparecer); NaN se não houver."""
    m = re.search(r"\b(pass|fail)\b", (texto or "").lower())
    if not m:
        return math.nan
    return 1.0 if m.group(1) == "pass" else 0.0


async def argumentos_adequados(cliente_openai, modelo, pergunta, ferramenta, descricao, args):
    """Pede ao juiz pass/fail para os argumentos de uma chamada. Devolve (nota, texto do juiz)."""
    prompt = PROMPT_ARGUMENTOS.format(question=pergunta, tool=ferramenta, description=descricao, arguments=args)
    r = await cliente_openai.chat.completions.create(
        model=modelo, temperature=0, messages=[{"role": "user", "content": prompt}])
    texto = r.choices[0].message.content or ""
    return extrair_pass_fail(texto), texto.strip()


# ---------------------------------------------------------------------------
# 4. Testes diretos: cada ferramenta sozinha, sem LLM
# ---------------------------------------------------------------------------
# Cada teste chama UMA ferramenta com argumentos fixos e confere o resultado.
# "verifica" recebe o resultado (um dicionário) e devolve True se estiver certo.
# espera_erro=True: a entrada é inválida de propósito e a ferramenta tem de responder com "erro".


def criar_teste(ferramenta, argumentos, verifica=None, espera_erro=False):
    return {"ferramenta": ferramenta, "argumentos": argumentos, "verifica": verifica, "espera_erro": espera_erro}


TESTES = [
    # Lista os artigos do RAG: tem de haver artigos e o total tem de bater com a lista
    criar_teste("listar_arquivos", {},
                lambda r: r["n_artigos"] > 0 and r["n_artigos"] == len(r["artigos"])),
    # Relevância da pergunta face aos arquivos: valor entre 0 e 1 e artigo mais próximo indicado
    criar_teste("relevancia", {"pergunta": "Quem é o Batman?"},
                lambda r: 0 <= r["relevancia"] <= 1 and r["artigo"] != ""),
    # Pesquisa no RAG com k=3: devolve entre 1 e 3 excertos, todos com texto
    criar_teste("pesquisar_arquivos", {"pergunta": "Quem é o Batman?", "k": 3},
                lambda r: 0 < r["n_excertos"] <= 3 and all(e["texto"] for e in r["excertos"])),
    # Web
    # Pesquisa web limitada a 3 resultados, cada um com um URL http(s)
    criar_teste("pesquisar_web", {"consulta": "Batman filme 2022", "max_resultados": 3},
                lambda r: 0 < r["n_resultados"] <= 3 and all(x["url"].startswith("http") for x in r["resultados"])),
    # Pesquisa de notícias: no máximo 3 resultados e o total bate com a lista
    criar_teste("pesquisar_noticias", {"consulta": "Batman", "max_resultados": 3},
                lambda r: r["n_resultados"] == len(r["resultados"]) <= 3),
    # Lê uma página real: devolve texto não vazio, truncado a 1000 caracteres
    criar_teste("ler_pagina", {"url": "https://pt.wikipedia.org/wiki/Batman", "max_caracteres": 1000},
                lambda r: 0 < len(r["texto"]) <= 1000),
    # Entrada inválida (esquema ftp): a ferramenta tem de responder com erro
    criar_teste("ler_pagina", {"url": "ftp://exemplo.com"}, espera_erro=True),
    # Batcaverna
    # Estado de um veículo: devolve o veículo pedido e a blindagem entre 0% e 100%
    criar_teste("estado_batmovel", {"veiculo": "Batwing"},
                lambda r: r["veiculo"] == "Batwing" and 0 <= int(r["blindagem"].rstrip("%")) <= 100),
    # Clima de um distrito: devolve o distrito pedido e a temperatura em ºC
    criar_teste("clima_gotham", {"distrito": "The Narrows"},
                lambda r: r["distrito"] == "The Narrows" and "ºC" in r["temperatura"]),
    # Agenda (ler): devolve pelo menos um compromisso
    criar_teste("gerir_agenda_bruce", {"acao": "ler", "data": "hoje"},
                lambda r: len(r["compromissos"]) > 0),
    # Agenda (escrever): sucesso e o novo compromisso aparece na agenda atualizada
    criar_teste("gerir_agenda_bruce", {"acao": "escrever", "data": "teste", "compromisso": "Teste"},
                lambda r: r["sucesso"] and "Teste" in r["agenda_atualizada"]),
    # Entrada inválida (ação inexistente): a ferramenta tem de responder com erro
    criar_teste("gerir_agenda_bruce", {"acao": "voar"}, espera_erro=True),
    # Batman (D1)
    # Conversa com o Batman do D1: a resposta não pode vir vazia
    criar_teste("perguntar_ao_batman", {"mensagem": "Olá, Batman"},
                lambda r: r["resposta_batman"] != ""),
]


def verificar(teste, resultado):
    """True se o resultado de uma ferramenta passa no teste."""
    tem_erro = "erro" in resultado
    if teste["espera_erro"]:
        return tem_erro
    if tem_erro:
        return False
    if teste["verifica"] is None:
        return True
    try:
        return bool(teste["verifica"](resultado))
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return False   # faltam campos ou têm o formato errado


# ---------------------------------------------------------------------------
# 5. Resposta: LLM-as-Judge (prompt dos slides, do cookbook da Hugging Face)
# ---------------------------------------------------------------------------

PROMPT_JUIZ = """You will be given a user_question and system_answer couple. Your task is to provide a 'total rating' scoring how well the system_answer answers the user concerns expressed in the user_question. Give your answer as a float on a scale of 0 to 10, where 0 means that the system_answer is not helpful at all, and 10 means that the answer completely and helpfully addresses the question.

Provide your feedback as follows:

Feedback:::
Total rating: (your rating, as a float between 0 and 10)

Now here are the question and answer.

Question: {question}
Answer: {answer}

Feedback:::
Total rating: """


def extrair_nota(texto):
    """Lê a nota 0-10 da resposta do juiz (a que vem depois de 'Total rating:'); NaN se não houver número."""
    m = re.search(r"Total rating:\s*([0-9]+(?:[.,][0-9]+)?)", texto or "", re.IGNORECASE) \
        or re.search(r"([0-9]+(?:[.,][0-9]+)?)", texto or "")
    if not m:
        return math.nan
    return min(10.0, max(0.0, float(m.group(1).replace(",", "."))))


async def nota_llm_judge(cliente_openai, modelo, pergunta, resposta):
    """Pede ao juiz a 'total rating' (0-10). Devolve (nota, texto do juiz)."""
    r = await cliente_openai.chat.completions.create(
        model=modelo, temperature=0,
        messages=[{"role": "user", "content": PROMPT_JUIZ.format(question=pergunta, answer=resposta)}])
    texto = r.choices[0].message.content or ""
    return extrair_nota(texto), texto.strip()


# ---------------------------------------------------------------------------
# 5. Resposta: correção pass/fail (Ragas DiscreteMetric, como no guia "evaluate and improve RAG")
# ---------------------------------------------------------------------------
# Diferença para o guia: o prompt do guia pede "factually accurate based on the provided
# context" mas não passa o contexto. Aqui o contexto são as saídas das ferramentas MCP.

PROMPT_CORRECAO = """Compare the model response to the expected answer and determine if it's correct.

Consider the response correct if it:
1. Contains the key information from the expected answer
2. Is factually accurate based on the provided context
3. Adequately addresses the question asked

When the expected answer describes what a correct response must contain (instead of a fixed fact), judge the response against that description and the context.

Return 'pass' if the response is correct, 'fail' if it's incorrect.

Question: {question}
Expected Answer: {expected_answer}
Context (tool outputs): {context}
Model Response: {response}

Evaluation:"""


def criar_metrica_correcao():
    """DiscreteMetric 'correctness' (pass/fail). Import tardio: o ragas é pesado."""
    from ragas.metrics import DiscreteMetric

    return DiscreteMetric(name="correctness", prompt=PROMPT_CORRECAO, allowed_values=["pass", "fail"])


# ---------------------------------------------------------------------------
# Análise de falhas: porque é que uma resposta saiu errada (correctness = fail)?
# ---------------------------------------------------------------------------
# Vê-se a causa por ordem: a primeira regra que se aplica ganha.

CAUSAS = {
    "selecao_ferramenta": "o LLM não chamou a ferramenta esperada",
    "argumentos": "o LLM chamou uma ferramenta com argumentos inválidos ou inadequados",
    "ferramenta_falhou": "uma chamada MCP devolveu erro (com argumentos bons)",
    "limite_chamadas": "o agente atingiu MAX_CHAMADAS e respondeu sem terminar",
    "geracao": "chamou as ferramentas certas, sem erros, mas a resposta saiu errada",
}


def classificar_falha(linha):
    """Causa provável de uma resposta errada (chave de CAUSAS). linha = métricas da pergunta.

    Um valor em falta (NaN) nunca é menor que 1, por isso não dispara a regra.
    """
    if linha.get("ToolRecall", 1.0) < 1.0:
        return "selecao_ferramenta"
    if linha.get("ArgsValidos", 1.0) < 1.0 or linha.get("ArgsAdequados", 1.0) < 1.0:
        return "argumentos"
    if linha.get("TaxaSucesso", 1.0) < 1.0:
        return "ferramenta_falhou"
    if linha.get("limite_atingido"):
        return "limite_chamadas"
    return "geracao"
