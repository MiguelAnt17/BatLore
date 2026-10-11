"""Agente híbrido: Batman (regras, D1) + RAG (D2) + agente MCP (D3). Comandos: "debug", "quit".

D3: no modo Alfred, as perguntas vão para o agente MCP (agente_mcp.py). O RAG do D2
continua lá, agora servido pelo servidor MCP (mcp_servidor.py, ferramentas em
mcp_funcoes.py), e a pesquisa web (mcp_pesquisa_web.py) complementa-o. O router e o Batman de regras não mudam.

Dois modos para o Alfred (comando "modo" no terminal, seletor na webapp, ou a
variável de ambiente MODO_AGENTE):
    rag_primeiro (defeito) -> o RAG corre sempre; o LLM usa a web se precisar
    livre                  -> o LLM decide tudo, incluindo se consulta os arquivos

Para correr o comportamento do D2 (útil para a avaliação D2 vs D3):
    USAR_MCP=0 python agente_hibrido.py
"""
print("[1/4] A carregar bibliotecas e dependências pesadas...")
import os
import random
import sys

from sentence_transformers import SentenceTransformer, util

# Código do D2 em rag/ e do D3 em mcp/cliente/.
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
for _pasta in ("rag", os.path.join("mcp", "cliente")):
    _caminho = os.path.join(PASTA_PROJETO, _pasta)
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import modelos_llm  # noqa: E402  (carrega o .env antes de tudo)
import rule_based as ruleBasedAgent  # noqa: E402
import rag_system as rag  # noqa: E402  (ainda usado no modo D2, USAR_MCP=0)

# D3: liga/desliga o agente MCP sem mexer no código.
# DECISÃO: ligado por defeito (é o sistema do D3); USAR_MCP=0 repõe o D2 tal e qual,
#   para os dois poderem ser comparados com as mesmas perguntas.
USAR_MCP = os.environ.get("USAR_MCP", "1") != "0"

# Idiomas da conversa. O inglês usa o Batman de regras em inglês (rule_based_en.py),
# frases do router em inglês, a Wikipédia EN no RAG e o Alfred a responder em inglês.
# DECISÃO: o inglês só existe com o agente MCP (D3); o modo D2 fica só em português.
IDIOMAS = ("pt", "en") if USAR_MCP else ("pt",)
IDIOMA_DEFEITO = os.environ.get("IDIOMA", "pt") if os.environ.get("IDIOMA") in IDIOMAS else "pt"


def idioma_valido(idioma):
    return idioma if idioma in IDIOMAS else "pt"


_REGRAS = {"pt": ruleBasedAgent}


def regras(idioma="pt"):
    """Módulo do Batman de regras do idioma (o inglês é importado só quando é preciso)."""
    if idioma not in _REGRAS:
        import rule_based_en
        _REGRAS[idioma] = rule_based_en
    return _REGRAS[idioma]

# 1. Router

# Encoder multilingue (alternativa PT: "PORTULAN/serafim-900m-portuguese-pt-sentence-encoder")
MODELO_ENCODER = os.environ.get(
    "ROUTER_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

# Similaridade mínima para trocar de agente
LIMIAR = 0.6

# Relevância mínima dos PDFs para usar o RAG (lore: 0.64-0.79, conversa: < 0.50)
LIMIAR_RELEVANCIA = 0.62

# Frases do router, frases para sair do Alfred e textos fixos: em idiomas.py
from idiomas import (  # noqa: E402,F401
    FRASES_ALFRED, FRASES_ALFRED_EN, FRASES_BATMAN, FRASES_BATMAN_EN, FRASES_SAIR_ALFRED,
    TEXTOS, quer_sair_do_alfred,
)

# Regras catch-all
REGRAS_GENERICAS = {r"(.*)", r"(.*)\?"}


class RouterAgentes:
    """Escolhe o agente por similaridade."""

    def __init__(self, modelo=MODELO_ENCODER, limiar=LIMIAR):
        print(f"[2/4] A inicializar o Router (modelo: {modelo})...")
        self.encoder = SentenceTransformer(modelo)
        self.limiar = limiar
        cod = lambda frases: self.encoder.encode(frases, normalize_embeddings=True)  # noqa: E731
        self.emb = {
            "pt": {"rag": cod(FRASES_ALFRED), "batman": cod(FRASES_BATMAN)},
            "en": {"rag": cod(FRASES_ALFRED_EN), "batman": cod(FRASES_BATMAN_EN)},
        }
        # nomes antigos (PT)
        self.emb_rag = self.emb["pt"]["rag"]
        self.emb_batman = self.emb["pt"]["batman"]

    def _similaridade(self, texto, embeddings):
        """Similaridade de cosseno máxima."""
        vetor = self.encoder.encode([texto], normalize_embeddings=True)
        return float(util.cos_sim(vetor, embeddings).max())

    def similaridade_rag(self, texto, idioma="pt"):
        return self._similaridade(texto, self.emb[idioma_valido(idioma)]["rag"])

    def similaridade_batman(self, texto, idioma="pt"):
        return self._similaridade(texto, self.emb[idioma_valido(idioma)]["batman"])


def tem_regra_especifica(texto, pairs):
    """True se alguma regra específica corresponde."""
    import re
    for pattern, responses in pairs:
        if pattern in REGRAS_GENERICAS:
            continue
        try:
            if re.match(pattern, texto, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


# 2. Agentes

def frase(chave, idioma="pt"):
    """Frase fixa de um idioma (saudação, despedida, ...)."""
    return TEXTOS[idioma_valido(idioma)][chave]


# Nomes antigos (PT)
SAUDACAO = TEXTOS["pt"]["saudacao"]
DESPEDIDA = TEXTOS["pt"]["despedida"]
REGRESSO_BATMAN = TEXTOS["pt"]["regresso_batman"]
SAUDACAO_ALFRED = TEXTOS["pt"]["saudacao_alfred"]

# Pedido de troca curto ("Quero falar com o Alfred"): o Alfred cumprimenta sem gastar
# uma chamada ao LLM. Mensagens mais longas ("Alfred, pesquisa quem é o Bane") seguem
# para o agente, porque trazem uma pergunta.
MAX_PALAVRAS_SAUDACAO = 6


def novo_estado(idioma="pt"):
    """Estado inicial de uma conversa."""
    # historico_mcp (D3): pares (pergunta, resposta) do Alfred nesta conversa, para o
    # agente MCP perceber perguntas de seguimento ("e quando estreia?").
    # DECISÃO: a memória fica no estado de cada conversa (e não numa variável
    #   global como o historico_alfred do D2), para duas pessoas na webapp não
    #   partilharem memória.
    # modo_agente (D3): "rag_primeiro" ou "livre" nesta conversa. None = o modo por
    #   defeito do agente_mcp.py (variável MODO_AGENTE). Fica no estado, e não numa
    #   variável global, para cada conversa da webapp poder ter o seu modo.
    # idioma: "pt" ou "en", escolhido no início da conversa (o seletor da webapp
    #   começa uma conversa nova quando muda).
    return {"contexto": {"nomes": set(), "locais": set()}, "agente": "batman",
            "historico_mcp": [], "modo_agente": None, "idioma": idioma_valido(idioma)}


def responder_batman(texto, contexto, idioma="pt"):
    """Turno do agente de regras: NER -> correção -> regras -> TF-IDF -> fallback."""
    ruleBasedAgent = regras(idioma)  # noqa: N806 (o módulo do idioma, com a mesma interface)
    doc = ruleBasedAgent.nlp(texto)
    entidades = ruleBasedAgent.extrair_entidades(doc)
    resultado = {
        "entidades": entidades,
        "pos": ruleBasedAgent.extrair_pos(doc),
        "correcao": None,
        "via": "entidade",
        "similaridade": None,
    }

    resposta_especial = ruleBasedAgent.reagir_a_entidades(entidades, contexto)
    if resposta_especial:
        resultado["resposta"] = resposta_especial
        return resultado

    texto_corrigido = ruleBasedAgent.corrigir_intencao(texto, ruleBasedAgent.pairs_batman, max_distance=1)
    if texto != texto_corrigido:
        resultado["correcao"] = texto_corrigido

    if ruleBasedAgent.encontrar_regra_chat(texto_corrigido, ruleBasedAgent.pairs_batman):
        resultado["via"] = "regra"
        resultado["resposta"] = ruleBasedAgent.batman_chatbot.respond(texto_corrigido)
        return resultado

    resultado_tfidf = ruleBasedAgent.encontrar_intencao_tfidf(
        texto_corrigido, ruleBasedAgent.tfidf_vectorizer, ruleBasedAgent.tfidf_matriz, ruleBasedAgent.tfidf_regras, threshold=0.35
    )
    if resultado_tfidf:
        resultado["via"] = "tfidf"
        resultado["similaridade"] = float(resultado_tfidf["similaridade"])
        resultado["resposta"] = random.choice(resultado_tfidf["responses"])
        return resultado

    resultado["via"] = "fallback"
    resultado["resposta"] = ruleBasedAgent.batman_chatbot.respond(texto_corrigido)
    return resultado

class AgenteRAG:
    """Modo Alfred: RAG do D2 ou agente MCP do D3 (conforme USAR_MCP)."""

    def __init__(self):
        self.rag = rag
        self.db = None
        self.mcp = None
        if USAR_MCP:
            # D3: a base vetorial é carregada pelo servidor batcomputador (outro
            # processo), por isso aqui NÃO a carregamos: evita ter o mesmo índice
            # em memória duas vezes. Os servidores MCP arrancam agora.
            print("[3/4] A ligar aos servidores MCP (batcomputador + pesquisa web)...")
            import agente_mcp  # import tardio: só é preciso em modo MCP
            self._agente_mcp = agente_mcp
            self.mcp = agente_mcp.obter_agente(IDIOMA_DEFEITO)
        else:
            print("[3/4] A inicializar o módulo RAG (modo D2)...")
            caminhos_pdf = rag.descarregar_pdfs()
            self.db = rag.obter_ou_criar_vector_db(caminhos_pdf)

    def relevancia(self, texto):
        """Relevância (0-1) do melhor excerto."""
        if self.mcp is not None:
            # D3: o mesmo cálculo, mas feito pelo servidor batcomputador via MCP.
            # É uma chamada decidida pelo CÓDIGO, não pelo LLM.
            return self.mcp.relevancia(texto)
        resultados = self.db.similarity_search_with_relevance_scores(texto, k=1)
        return float(resultados[0][1]) if resultados else 0.0

    def agente_mcp(self, idioma="pt"):
        """Ligação MCP do idioma (o servidor em inglês só arranca quando é preciso)."""
        return self._agente_mcp.obter_agente(idioma_valido(idioma))

    def preparar_idioma(self, idioma):
        """Arranca já o servidor MCP de um idioma (ex.: numa thread, no arranque da webapp)."""
        if self.mcp is not None:
            self.agente_mcp(idioma)
            regras(idioma)

    def responder_agente(self, texto, historico, modo=None, timeout=None, idioma="pt"):
        """D3: o agente MCP responde. modo: "rag_primeiro", "livre" ou None (defeito).
        Devolve um dict com resposta, relevancia, passos (chamadas MCP), contextos, etc."""
        return self.agente_mcp(idioma).responder(texto, historico, modo=modo, timeout=timeout)

    def responder(self, texto):
        """Resposta com RAG."""
        return self.rag.responder_com_rag(texto, self.db)

    def responder_sem_rag(self, texto):
        """LLM sem contexto, como Alfred."""
        return self.rag.responder_como_alfred(texto)


# 3. Conversa
def turno_hibrido(texto, estado, router, agente_rag):
    """Um turno: escolhe o agente ("batman", "rag", "llm" ou, no D3, "mcp") e responde."""
    idioma = idioma_valido(estado.get("idioma", "pt"))
    rb = regras(idioma)
    resultado = {"troca": None, "limiar": router.limiar, "idioma": idioma,
                 "sim_rag": None, "sim_batman": None, "relevancia": None, "ferramentas": None}

    # Pedido explícito para terminar com o Alfred: despede-se e a linha volta ao Batman.
    if estado["agente"] != "batman" and quer_sair_do_alfred(texto, idioma):
        estado["agente"] = "batman"
        resultado.update({"troca": "batman", "modo": "batman", "agente": "alfred",
                          "via": "despedida", "resposta": TEXTOS[idioma]["despedida_alfred"]})
        return resultado

    texto_corrigido = rb.corrigir_intencao(texto, rb.pairs_batman, max_distance=1)
    tem_regra = tem_regra_especifica(texto_corrigido, rb.pairs_batman)

    if estado["agente"] == "batman":
        # Só sem regra específica, ou quando a mensagem chama o Alfred pelo nome
        # (em inglês, "I want to talk to Alfred" também casa com a regra "I want (.*)").
        if not tem_regra or "alfred" in texto.lower():
            resultado["sim_rag"] = router.similaridade_rag(texto, idioma)
            if resultado["sim_rag"] >= router.limiar:
                estado["agente"] = "rag"
                resultado["troca"] = "rag"
    else:
        resultado["sim_batman"] = router.similaridade_batman(texto, idioma)
        if resultado["sim_batman"] >= router.limiar:
            estado["agente"] = "batman"
            resultado["troca"] = "batman"

    resultado["modo"] = estado["agente"]
    agente_turno = estado["agente"]
    # Modo RAG: regra -> Batman; PDFs irrelevantes -> só LLM
    if agente_turno == "rag" and resultado["troca"] is None:
        if not USAR_MCP:
            # D2: relevância baixa -> LLM sem RAG.
            resultado["relevancia"] = agente_rag.relevancia(texto)
            if resultado["relevancia"] < LIMIAR_RELEVANCIA:
                agente_turno = "llm"
        # D3: este corte deixa de existir. O RAG é sempre consultado (modo
        # rag_primeiro) e, se os arquivos não servirem, o agente pode ir à web em
        # vez de responder só de memória. A relevância é calculada pelo próprio
        # agente (no servidor batcomputador) e devolvida no resultado.

    # D3: tudo o que no D2 iria para o RAG vai para o agente MCP.
    if agente_turno == "rag" and USAR_MCP:
        agente_turno = "mcp"

    resultado["agente"] = agente_turno
    if resultado["troca"] == "rag" and len(texto.split()) <= MAX_PALAVRAS_SAUDACAO:
        resultado["resposta"] = TEXTOS[idioma]["saudacao_alfred"]
        resultado["via"] = "saudacao"
    elif agente_turno == "mcp":
        historico = estado.setdefault("historico_mcp", [])
        r = agente_rag.responder_agente(texto, historico, estado.get("modo_agente"), idioma=idioma)
        resultado["resposta"] = r["resposta"]
        resultado["relevancia"] = r["relevancia"]
        resultado["modo_agente"] = r["modo"]
        resultado["ferramentas"] = r["passos"]         # para o debug e a webapp
        resultado["limite_atingido"] = r["limite_atingido"]
        resultado["segundos"] = r["segundos"]
        historico.append((texto, r["resposta"]))
        del historico[:-5]  # só os últimos turnos (o agente usa no máximo 3)
    elif agente_turno == "rag":
        resultado["resposta"] = agente_rag.responder(texto)
    elif agente_turno == "llm":
        resultado["resposta"] = agente_rag.responder_sem_rag(texto)
    else:
        resultado.update(responder_batman(texto, estado["contexto"], idioma))

    # Regresso ao Batman: prefixa a frase de transição
    if resultado.get("troca") == "batman":
        resultado["resposta"] = f"{TEXTOS[idioma]['regresso_batman']} {resultado.get('resposta', '')}"

    return resultado

def conversa_hibrida(verbose=False):
    """Conversa no terminal."""
    # Carrega tudo antes da saudação
    llm = modelos_llm.descricao()
    print(f"[LLM] {llm['fornecedor']} / {llm['modelo']}")
    router = RouterAgentes()
    agente_rag = AgenteRAG()
    estado = novo_estado(IDIOMA_DEFEITO)
    print("[4/4] Sistemas operacionais. A iniciar patrulha.\n")
    print("Batman")
    print("------")
    print("Fala. Estou a ouvir, mas não esperes conforto.")
    print('Escreve "quit" quando quiseres sair.')
    if USAR_MCP:
        print(f'[D3] Alfred em modo "{agente_rag.mcp.modo}". Escreve "modo" para alternar, "debug" para ver as ferramentas.')
    print("=" * 72)
    print(frase("saudacao", IDIOMA_DEFEITO))

    while True:
        try:
            texto = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\n" + frase("despedida", IDIOMA_DEFEITO))
            break

        if texto.lower().strip() == "quit":
            print(frase("despedida", IDIOMA_DEFEITO))
            break

        if texto.lower().strip() == "modo":
            # D3: alterna o modo do Alfred nesta conversa.
            if not USAR_MCP:
                print("[Modo D2 (USAR_MCP=0): não há agente MCP]")
                continue
            atual = estado["modo_agente"] or agente_rag.mcp.modo
            estado["modo_agente"] = "livre" if atual == "rag_primeiro" else "rag_primeiro"
            descricao = {"rag_primeiro": "RAG sempre primeiro, MCP como complemento",
                         "livre": "o LLM decide todas as ferramentas"}
            print(f"[Modo do Alfred: {estado['modo_agente']} ({descricao[estado['modo_agente']]})]")
            continue

        if texto.lower().strip() == "debug":
            verbose = not verbose
            estado_debug = "ligado" if verbose else "desligado"
            print(f"[Modo debug: {estado_debug}]")
            continue

        resultado = turno_hibrido(texto, estado, router, agente_rag)

        if verbose:
            if resultado["sim_rag"] is not None:
                print(f"[Sem regra | similaridade RAG: {resultado['sim_rag']:.2f} | limiar: {router.limiar}]")
            if resultado["sim_batman"] is not None:
                print(f"[Similaridade Batman: {resultado['sim_batman']:.2f} | limiar: {router.limiar}]")
            if resultado["relevancia"] is not None:
                print(f"[Relevância PDFs: {resultado['relevancia']:.2f} | limiar: {LIMIAR_RELEVANCIA}]")
            if resultado.get("ferramentas") is not None:
                print(f"[Agente MCP, modo {resultado['modo_agente']}: {len(resultado['ferramentas'])} "
                      f"chamada(s) | {resultado['segundos']}s"
                      + (" | limite de chamadas atingido" if resultado.get("limite_atingido") else "") + "]")
            for i, p in enumerate(resultado.get("ferramentas") or [], 1):
                estado_p = "ok" if p["ok"] else "ERRO"
                origem = "auto" if p.get("origem") == "codigo" else "LLM"
                print(f"  {i}. ({origem}) [{p['servidor']}] {p['ferramenta']}({p['argumentos']}) "
                    f"-> {estado_p} ({p['segundos']}s)")
                
                # Imprime o output/retorno da ferramenta:
                if p.get("resumo"):
                    print(f"     └─ Resposta: {p['resumo']}\n")
            if resultado["modo"] == "rag" and resultado["agente"] == "batman":
                print("[Modo RAG, mas esta mensagem tem regra própria: responde o Batman]")
            if resultado["agente"] == "llm":
                print("[Modo RAG, mas sem excertos relevantes: responde só o LLM]")
        if resultado["troca"] == "rag":
            print("[Ligação Estabelecida: Batcaverna / Alfred]")
        elif resultado["troca"] == "batman":
            print("[Ligação Cortada: Modo Batman]")

        if verbose and resultado.get("pos") is not None:
            if resultado["entidades"]:
                print(f"[NER: {resultado['entidades']}]")
            print(f"[POS: {resultado['pos']}]")
        if resultado.get("correcao"):
            print("[Correção:", resultado["correcao"] + "]")
        if verbose and resultado.get("via") == "tfidf":
            print(f"[TF-IDF: similaridade: {resultado['similaridade']:.2f}]")

        # D3: mesmo sem debug, mostra que ferramentas o Alfred usou (é a novidade do D3).
        if not verbose and resultado.get("ferramentas"):
            # A relevancia é uma medição interna; mostramos só o que trouxe informação.
            nomes = " -> ".join(p["ferramenta"] + ("*" if p.get("origem") == "codigo" else "")
                                for p in resultado["ferramentas"] if p["ferramenta"] != "relevancia")
            print(f"[Ferramentas: {nomes or 'nenhuma'}]  (* = automática)")

        if resultado["agente"] == "batman":
            print(f"\n[Batman]: {resultado['resposta']}\n")
        else:
            print(f"\n[Alfred]: {resultado['resposta']}\n")

if __name__ == "__main__":
    conversa_hibrida()