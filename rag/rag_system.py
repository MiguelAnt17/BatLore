"""D2: RAG sobre 18 artigos da Wikipédia PT (Chroma + BM25 + RRF) e o Alfred com RAG.

O LLM e o modelo de embeddings são carregados só quando são precisos (o servidor
MCP importa este módulo apenas para a pesquisa e não precisa do LLM). Continuam
acessíveis como `rag_system.llm` e `rag_system.embedding_func`, como no D2.
"""
import os
import re
import sys
import time
import unicodedata

import nltk
import requests
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

PASTA_RAG = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETO = os.path.dirname(PASTA_RAG)
if PASTA_PROJETO not in sys.path:
    sys.path.insert(0, PASTA_PROJETO)

import modelos_llm  # noqa: E402  (carrega o .env)

# 1. Modelos

# Modelo de embeddings da Vector DB (mudar obriga a apagar iln_batman/ para a recriar)
MODELO_EMBEDDINGS = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Turnos de que o Alfred se lembra no modo D2 (modelos locais têm contexto curto)
MAX_TURNOS = 1 if modelos_llm.fornecedor() == "ollama" else 10
historico_alfred = []

_llm = None
_embeddings = None


def obter_llm():
    """LLM do D2 (o mesmo fornecedor/modelo configurado em modelos_llm)."""
    global _llm
    if _llm is None:
        _llm = modelos_llm.obter_llm()
    return _llm


def obter_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    return _embeddings


def __getattr__(nome):
    # Compatibilidade com o D2 e os notebooks: rag_system.llm / rag_system.embedding_func
    if nome == "llm":
        return obter_llm()
    if nome == "embedding_func":
        return obter_embeddings()
    raise AttributeError(nome)


# 2. PDFs
# Dados ao lado deste ficheiro (rag/), venha o processo de onde vier.
PASTA_PDFS = os.path.join(PASTA_RAG, "pdffiles")
PASTA_DB = os.environ.get("RAG_DB_DIR", os.path.join(PASTA_RAG, "iln_batman"))

# Artigos da Wikipédia PT
WIKI_PDF = "https://pt.wikipedia.org/api/rest_v1/page/pdf/"
FONTES_PDF = {
    # Batman e Gotham
    "wiki_batman.pdf": WIKI_PDF + "Batman",
    "wiki_gotham_city.pdf": WIKI_PDF + "Gotham_City",
    "wiki_asilo_arkham.pdf": WIKI_PDF + "Asilo_Arkham",
    "wiki_batcaverna.pdf": WIKI_PDF + "Batcaverna",
    "wiki_batmovel.pdf": WIKI_PDF + "Batmóvel",
    # Aliados
    "wiki_alfred_pennyworth.pdf": WIKI_PDF + "Alfred_Pennyworth",
    "wiki_james_gordon.pdf": WIKI_PDF + "James_Gordon_(DC_Comics)",
    "wiki_robin.pdf": WIKI_PDF + "Robin_(DC_Comics)",
    # Vilões
    "wiki_coringa.pdf": WIKI_PDF + "Coringa_(DC_Comics)",
    "wiki_pinguim.pdf": WIKI_PDF + "Pinguim_(DC_Comics)",
    "wiki_duas_caras.pdf": WIKI_PDF + "Duas-Caras",
    "wiki_charada.pdf": WIKI_PDF + "Charada_(DC_Comics)",
    "wiki_espantalho.pdf": WIKI_PDF + "Espantalho_(DC_Comics)",
    "wiki_mulher_gato.pdf": WIKI_PDF + "Mulher-Gato",
    "wiki_bane.pdf": WIKI_PDF + "Bane",
    "wiki_ras_al_ghul.pdf": WIKI_PDF + "Ra's_al_Ghul",
    "wiki_arlequina.pdf": WIKI_PDF + "Arlequina",
    "wiki_hera_venenosa.pdf": WIKI_PDF + "Hera_Venenosa",
}

# Artigos equivalentes da Wikipédia EN (modo inglês da webapp)
WIKI_PDF_EN = "https://en.wikipedia.org/api/rest_v1/page/pdf/"
FONTES_PDF_EN = {
    "wiki_batman.pdf": WIKI_PDF_EN + "Batman",
    "wiki_gotham_city.pdf": WIKI_PDF_EN + "Gotham_City",
    "wiki_arkham_asylum.pdf": WIKI_PDF_EN + "Arkham_Asylum",
    "wiki_batcave.pdf": WIKI_PDF_EN + "Batcave",
    "wiki_batmobile.pdf": WIKI_PDF_EN + "Batmobile",
    "wiki_alfred_pennyworth.pdf": WIKI_PDF_EN + "Alfred_Pennyworth",
    "wiki_james_gordon.pdf": WIKI_PDF_EN + "James_Gordon_(character)",
    "wiki_robin.pdf": WIKI_PDF_EN + "Robin_(character)",
    "wiki_joker.pdf": WIKI_PDF_EN + "Joker_(character)",
    "wiki_penguin.pdf": WIKI_PDF_EN + "Penguin_(character)",
    "wiki_two_face.pdf": WIKI_PDF_EN + "Two-Face",
    "wiki_riddler.pdf": WIKI_PDF_EN + "Riddler",
    "wiki_scarecrow.pdf": WIKI_PDF_EN + "Scarecrow_(DC_Comics)",
    "wiki_catwoman.pdf": WIKI_PDF_EN + "Catwoman",
    "wiki_bane.pdf": WIKI_PDF_EN + "Bane_(DC_Comics)",
    "wiki_ras_al_ghul.pdf": WIKI_PDF_EN + "Ra's_al_Ghul",
    "wiki_harley_quinn.pdf": WIKI_PDF_EN + "Harley_Quinn",
    "wiki_poison_ivy.pdf": WIKI_PDF_EN + "Poison_Ivy_(character)",
}

IDIOMAS = ("pt", "en")
PASTA_PDFS_EN = os.path.join(PASTA_RAG, "pdffiles_en")
PASTA_DB_EN = os.environ.get("RAG_DB_DIR_EN", os.path.join(PASTA_RAG, "iln_batman_en"))


def config_idioma(idioma="pt"):
    """(fontes, pasta dos PDFs, pasta da Vector DB) de cada idioma."""
    if idioma == "en":
        return FONTES_PDF_EN, PASTA_PDFS_EN, PASTA_DB_EN
    return FONTES_PDF, PASTA_PDFS, PASTA_DB


def titulo_fonte(url):
    """"https://.../page/pdf/Joker_(character)" -> "Joker (character)"."""
    return url.rsplit("/", 1)[-1].replace("_", " ")


# A Wikipédia pede um User-Agent identificável (https://meta.wikimedia.org/wiki/User-Agent_policy)
USER_AGENT = "BatmanAlfredChatbot/1.0 (academic project; https://github.com)"


def _texto_wikipedia(url):
    """Reserva quando o PDF falha: o texto simples do artigo pela API da Wikipédia."""
    from urllib.parse import unquote, urlparse
    partes = urlparse(url)
    titulo = unquote(partes.path.rsplit("/", 1)[-1])
    api = f"{partes.scheme}://{partes.netloc}/w/api.php"
    params = {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
              "titles": titulo, "format": "json", "formatversion": 2}
    try:
        r = requests.get(api, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        paginas = r.json().get("query", {}).get("pages", [])
        texto = paginas[0].get("extract", "") if paginas else ""
    except (requests.RequestException, ValueError):
        return ""
    return f"{titulo.replace('_', ' ')}\n\n{texto}" if texto else ""


def descarregar_pdfs(fontes=FONTES_PDF, pasta=PASTA_PDFS, pausa=2, tentativas=4):
    """Descarrega os PDFs em falta e devolve os caminhos locais.

    Se a Wikipédia não devolver o PDF, guarda o texto do artigo num .txt com o mesmo nome.
    """
    os.makedirs(pasta, exist_ok=True)
    caminhos = []
    for nome, url in fontes.items():
        caminho = os.path.join(pasta, nome)
        caminho_txt = os.path.splitext(caminho)[0] + ".txt"
        if not os.path.exists(caminho) and os.path.exists(caminho_txt):
            caminhos.append(caminho_txt)
            continue
        if not os.path.exists(caminho):
            print(f"A descarregar {nome}...")
            time.sleep(pausa)  # evita o rate limit da Wikipédia
            resposta = None
            for tentativa in range(1, tentativas + 1):
                try:
                    resposta = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
                except requests.RequestException as erro:
                    print(f"Aviso: falha a descarregar {nome}: {erro}")
                    resposta = None
                    break
                if resposta.status_code != 429:  # 429 = demasiados pedidos
                    break
                espera = pausa * 2 ** tentativa
                print(f"Limite de pedidos atingido, a tentar de novo daqui a {espera}s...")
                time.sleep(espera)
            if resposta is None or resposta.status_code != 200 or not resposta.content.startswith(b"%PDF"):
                codigo = resposta.status_code if resposta is not None else "sem ligação"
                texto = _texto_wikipedia(url)
                if texto:
                    print(f"Aviso: {url} não devolveu um PDF (HTTP {codigo}); a usar o texto do artigo.")
                    with open(caminho_txt, "w", encoding="utf-8") as f:
                        f.write(texto)
                    caminhos.append(caminho_txt)
                else:
                    print(f"Aviso: {url} não devolveu um PDF (HTTP {codigo}), a ignorar.")
                continue
            with open(caminho, "wb") as f:
                f.write(resposta.content)
        caminhos.append(caminho)
    return caminhos

# 3. Vector DB
_IDIOMA_DB = {}  # id(vector_db) -> idioma (para o BM25 usar as stopwords certas)


def obter_ou_criar_vector_db(caminhos_pdf, persist_dir=PASTA_DB, idioma="pt"):
    """Carrega a Vector DB do disco ou cria-a a partir dos PDFs (ou .txt)."""
    from langchain_chroma import Chroma
    embedding_func = obter_embeddings()
    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        print("A carregar Vector DB existente a partir do disco...")
        vector_db = Chroma(
            collection_name="especialista_collection",
            embedding_function=embedding_func,
            persist_directory=persist_dir,
            collection_metadata={"hnsw:space": "cosine"}
        )
        _IDIOMA_DB[id(vector_db)] = idioma
        return vector_db

    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    print("A processar os documentos pela primeira vez...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len
    )
    documentos = []
    for caminho_pdf in caminhos_pdf:
        if caminho_pdf.endswith(".txt"):
            with open(caminho_pdf, encoding="utf-8") as f:
                doc = Document(page_content=f.read(), metadata={"source": caminho_pdf, "page": 0})
            documentos += text_splitter.split_documents([doc])
        else:
            documentos += PyPDFLoader(caminho_pdf).load_and_split(text_splitter=text_splitter)

    vector_db = Chroma(
        collection_name="especialista_collection",
        embedding_function=embedding_func,
        persist_directory=persist_dir,
        collection_metadata={"hnsw:space": "cosine"}
    )
    vector_db.add_documents(documentos)
    _IDIOMA_DB[id(vector_db)] = idioma
    return vector_db


def obter_vector_db_idioma(idioma="pt"):
    """Descarrega o que faltar e devolve a Vector DB de um idioma ("pt" ou "en")."""
    fontes, pasta_pdfs, pasta_db = config_idioma(idioma)
    caminhos = descarregar_pdfs(fontes, pasta_pdfs)
    if not caminhos:
        raise RuntimeError(f"Nenhum documento disponível em {pasta_pdfs}.")
    return obter_ou_criar_vector_db(caminhos, pasta_db, idioma)

# 4. Respostas (com e sem RAG)
def responder_sem_rag(pergunta):
    """Resposta só do LLM, sem contexto."""
    resposta = obter_llm().invoke(pergunta)
    return modelos_llm.texto_resposta(resposta)

def responder_como_alfred(pergunta):
    """Resposta sem RAG, como Alfred."""
    system_prompt = (
        "És o Alfred Pennyworth, o leal mordomo e assistente tático do Batman. "
        "Estás na Batcaverna a falar pelo intercomunicador com um contacto ou informador do Batman.\n"
        "Responde sempre em português de Portugal, com um tom extremamente educado, "
        "formal e com um leve humor britânico seco.\n"
        "SÊ BREVE E CONCISO: responde de forma curta, e normal como numa conversa normal "
        "Trata o interlocutor apenas por 'senhor' ou 'senhora'.\n")

    global historico_alfred

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="historico"),
        ("human", "{input}"),
    ])

    query = prompt.invoke({"input": pergunta, "historico": historico_alfred})
    texto = modelos_llm.texto_resposta(obter_llm().invoke(query))

    # Guardar memória
    historico_alfred.append(HumanMessage(content=pergunta))
    historico_alfred.append(AIMessage(content=texto))
    if len(historico_alfred) > MAX_TURNOS * 2:
        historico_alfred = historico_alfred[-(MAX_TURNOS * 2):]

    return texto

# 4.1 Retriever híbrido (denso + BM25)
def remover_acentos(texto):
    """"Batmóvel" -> "Batmovel"."""
    texto_decomposto = unicodedata.normalize("NFKD", texto)
    resultado = ""
    for caracter in texto_decomposto:
        if not unicodedata.combining(caracter):
            resultado += caracter
    return resultado

# Reserva, se as stopwords do NLTK não estiverem instaladas nem se conseguirem descarregar
STOPWORDS_RESERVA = set(
    "a ao aos as com como da das de do dos e ela elas ele eles em entre era essa esse esta este eu "
    "foi for ha isso isto ja lhe mais mas me mesmo meu minha muito na nas nem no nos nossa nosso "
    "num numa o os ou para pela pelas pelo pelos por qual quando que quem se sem ser seu sua so "
    "tambem te tem ter teu tu tua um uma voce voces".split()
)


STOPWORDS_RESERVA_EN = set(
    "a an and are as at be but by for from has have he her his i in is it its me my no not of on "
    "or our she so that the their them they this to was we were what when where which who why will "
    "with you your".split()
)


def carregar_stopwords(idioma="pt"):
    """Stopwords do NLTK, sem acentos (com uma lista de reserva se não houver rede)."""
    lingua = "english" if idioma == "en" else "portuguese"
    reserva = STOPWORDS_RESERVA_EN if idioma == "en" else STOPWORDS_RESERVA
    try:
        palavras = nltk.corpus.stopwords.words(lingua)
    except LookupError:
        try:
            nltk.download("stopwords", quiet=True)
            palavras = nltk.corpus.stopwords.words(lingua)
        except Exception:  # sem rede, proxy, ...
            print("Aviso: stopwords do NLTK indisponíveis; a usar a lista de reserva.", file=sys.stderr)
            return set(reserva)

    stopwords = set()
    for palavra in palavras:
        stopwords.add(remover_acentos(palavra))
    return stopwords

_STOPWORDS = {}  # idioma -> conjunto, carregado na primeira tokenização


def tokenizar(texto, idioma="pt"):
    """Tokenizador do BM25."""
    if idioma not in _STOPWORDS:
        _STOPWORDS[idioma] = carregar_stopwords(idioma)
    stopwords = _STOPWORDS[idioma]
    texto = remover_acentos(texto.lower())
    tokens = []
    for palavra in re.findall(r"\w+", texto):
        if palavra not in stopwords:
            tokens.append(palavra)
    return tokens

_bm25 = {}  # id(vector_db) -> BM25Retriever, criado na primeira pesquisa

def recuperar_bm25(pergunta, vector_db, k):
    """Top-k chunks por BM25 (sobre os chunks do Chroma)."""
    chave = id(vector_db)
    if chave not in _bm25:
        dados = vector_db.get()
        chunks = []
        for i in range(len(dados["documents"])):
            chunks.append(Document(page_content=dados["documents"][i], metadata=dados["metadatas"][i]))
        from langchain_community.retrievers import BM25Retriever
        idioma = _IDIOMA_DB.get(chave, "pt")
        _bm25[chave] = BM25Retriever.from_documents(
            chunks, preprocess_func=lambda texto: tokenizar(texto, idioma))
    retriever = _bm25[chave]
    retriever.k = k
    return retriever.invoke(pergunta)

def fusao_rrf(lista_densa, lista_bm25, k, c=60):
    """Reciprocal Rank Fusion: score = soma de 1 / (c + rank)."""
    scores = {}
    docs = {}

    for lista in [lista_densa, lista_bm25]:
        rank = 1
        for doc in lista:
            chave = doc.page_content
            if chave not in scores:
                scores[chave] = 0.0
                docs[chave] = doc
            scores[chave] += 1.0 / (c + rank)
            rank += 1

    chaves_ordenadas = sorted(scores, key=lambda chave: scores[chave], reverse=True)
    resultado = []
    for chave in chaves_ordenadas[:k]:
        resultado.append(docs[chave])
    return resultado

def recuperar_chunks(pergunta, vector_db, k=3, modo="hibrido", n_candidatos=20):
    """Top-k chunks. modo: "denso", "bm25" ou "hibrido" (RRF)."""
    if modo == "denso":
        return vector_db.similarity_search(pergunta, k=k)
    elif modo == "bm25":
        return recuperar_bm25(pergunta, vector_db, k)
    elif modo == "hibrido":
        lista_densa = vector_db.similarity_search(pergunta, k=n_candidatos)
        lista_bm25 = recuperar_bm25(pergunta, vector_db, n_candidatos)
        return fusao_rrf(lista_densa, lista_bm25, k)
    else:
        raise ValueError(f"modo de recuperação desconhecido: {modo}")



def responder_com_rag(pergunta, vector_db):
    """Resposta com RAG (imprime os chunks usados)."""
    # docs = recuperar_chunks(pergunta, vector_db, k=3)
    docs = recuperar_chunks(pergunta, vector_db, k=3, modo="denso")
    if os.environ.get("RAG_VERBOSE", "0") == "1":
        print("\n" + "="*20 + " CHUNKS RECUPERADOS PELO RAG " + "="*20)
        for i, doc in enumerate(docs, 1):
            print(f"\n--- CHUNK {i} (Página {doc.metadata.get('page', '?')}) ---")
            print(doc.page_content.strip())
        print("="*65 + "\n")

    return gerar_resposta(pergunta, docs)

    
def gerar_resposta(pergunta, docs):
    """Resposta do Alfred com os chunks como contexto."""
    contexto = "\n\n".join([doc.page_content for doc in docs])

    global historico_alfred

    system_prompt = (
        "És o Alfred Pennyworth. Estás na Batcaverna a utilizar o Batcomputador para "
        "aceder aos registos do GCPD e do Asilo Arkham a pedido de um contacto do Batman.\n"
        "Responde sempre em português de Portugal, de forma educada, formal e prestativa.\n"
        "Trata o utilizador apenas por 'senhor' ou 'senhora'.\n"
        "SÊ BREVE E CONCISO: responde de forma curta, e normal como numa conversa normal "
        "Responde à pergunta com base APENAS nos ficheiros extraídos do Batcomputador abaixo.\n"
        "Se a informação não estiver lá, diz educadamente que os sistemas não têm registos sobre isso.\n\n"
        "Ficheiros do Batcomputador:\n{contexto}"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="historico"),
        ("human", "{input}"),
    ])
    
    query = prompt.invoke({"contexto": contexto, "input": pergunta, "historico": historico_alfred})
    texto = modelos_llm.texto_resposta(obter_llm().invoke(query))

    # Guardar memória
    historico_alfred.append(HumanMessage(content=pergunta))
    historico_alfred.append(AIMessage(content=texto))
    if len(historico_alfred) > MAX_TURNOS * 2:
        historico_alfred = historico_alfred[-(MAX_TURNOS * 2):]

    return texto

# 5. Avaliação (LLM-as-judge)
def avaliar_resposta_llm_judge(pergunta, resposta_gerada, resposta_ideal, juiz=None):
    """LLM-as-judge: nota de 0 a 10. juiz: modelo com .invoke() (por omissão, o llm do RAG)."""
    prompt_avaliacao = f"""
    És um avaliador rigoroso. Compara a Resposta Gerada com a Resposta Ideal.
    Dá uma nota de 0 a 10 baseada na precisão e relevância. 
    Devolve APENAS o número da nota, sem qualquer texto adicional.
    
    Pergunta: {pergunta}
    Resposta Ideal: {resposta_ideal}
    Resposta Gerada: {resposta_gerada}
    """
    resultado = (juiz or obter_llm()).invoke(prompt_avaliacao)
    # Primeiro número da resposta (o juiz às vezes devolve "8/10" ou "Nota: 8")
    nota = re.search(r"\d+(?:[.,]\d+)?", resultado.content)
    return float(nota.group().replace(",", ".")) if nota else 0.0

# Execução
if __name__ == "__main__":
    caminhos_pdf = descarregar_pdfs()

    if not caminhos_pdf:
        print(f"Erro: não foi possível obter nenhum PDF para a pasta '{PASTA_PDFS}'.")
        exit()

    db = obter_ou_criar_vector_db(caminhos_pdf)
    pergunta_teste = [
        {
            "pergunta": "Quem matou os pais de Bruce Wayne e onde aconteceu?",
            "resposta_ideal": "Thomas Wayne e Martha Wayne foram assassinados por Joe Chill no Beco do Crime (anteriormente conhecido como Park Row), em Gotham City, à frente do filho Bruce, depois de a família ter ido à ópera."
        }
    ]
    
    notas_sem_rag = []
    notas_com_rag = []
    
    print("\n--- A INICIAR AVALIAÇÃO QUANTITATIVA ---")
    for item in pergunta_teste:
        pergunta = item["pergunta"]
        ideal = item["resposta_ideal"]
        
        print(f"\nPergunta: {pergunta}")
        
        # Sem RAG
        resp_base = responder_sem_rag(pergunta)
        print(f"\n[Resposta Sem RAG]:\n{resp_base}")
        nota_base = avaliar_resposta_llm_judge(pergunta, resp_base, ideal)
        notas_sem_rag.append(nota_base)
        print(f"Nota Sem RAG: {nota_base}/10")
        
        # Com RAG
        resp_rag = responder_com_rag(pergunta, db)
        print(f"\n[Resposta Com RAG]:\n{resp_rag}")
        nota_rag = avaliar_resposta_llm_judge(pergunta, resp_rag, ideal)
        notas_com_rag.append(nota_rag)
        print(f"Nota Com RAG: {nota_rag}/10")
        
    media_sem_rag = sum(notas_sem_rag) / max(1, len(notas_sem_rag))
    media_com_rag = sum(notas_com_rag) / max(1, len(notas_com_rag))
    
    print("\n==========================================")
    print("RESULTADOS DA COMPARAÇÃO QUANTITATIVA")
    print("==========================================")
    print(f"Média de Qualidade SEM RAG: {media_sem_rag:.2f} / 10")
    print(f"Média de Qualidade COM RAG: {media_com_rag:.2f} / 10")
    print("==========================================")