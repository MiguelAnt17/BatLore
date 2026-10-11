"""Agente MCP (D3): o Alfred com RAG consciente de contexto, pontuação de relevância
e ferramentas MCP (arquivos, web, sistemas da Batcaverna e o próprio Batman).

    python mcp/cliente/agente_mcp.py "Quando estreia o The Batman Parte II?"
"""

import asyncio
import concurrent.futures
from datetime import date, datetime
import json
import os
import sys
import threading
import time

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PASTA_PROJETO not in sys.path:
    sys.path.insert(0, PASTA_PROJETO)

import modelos_llm  # noqa: E402  (carrega o .env)

PASTA_SERVIDOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servidor"
)
# env: o servidor herda o ambiente todo (por defeito o MCP só passa PATH/HOME...),
# para variáveis como HF_HOME, EMBEDDING_MODEL ou RAG_DB_DIR chegarem lá.
IDIOMAS = ("pt", "en")


def transporte(idioma: str = "pt") -> PythonStdioTransport:
    """Servidor MCP de um idioma (IDIOMA=pt|en: Vector DB, Batman e região da web)."""
    return PythonStdioTransport(
        os.path.join(PASTA_SERVIDOR, "mcp_servidor.py"),
        cwd=PASTA_SERVIDOR,
        python_cmd=sys.executable,
        env={**os.environ, "IDIOMA": idioma},
    )


SERVIDOR = transporte("pt")   # o servidor por defeito (usado pelos notebooks de avaliação)





MODOS = ("rag_primeiro", "livre")
MODO_AGENTE = os.environ.get("MODO_AGENTE", "rag_primeiro")   # "rag_primeiro" ou "livre"
NOME_SERVIDOR = "batcomputador"
MAX_CHAMADAS = 4
MAX_PALAVRAS_SEGUIMENTO = 6
LIMIAR_RELEVANCIA = 0.62

PERSONA_ALFRED_EN = (
    "You are Alfred Pennyworth, Batman's loyal butler and tactical assistant in the Batcave.\n"
    "Always answer in English, politely and formally, with a light, dry British humour.\n"
    "Address the user as 'sir' or 'madam'. Be brief and concise.\n"
    "You may use simple markdown (bold, short lists). When you use the web, cite the source.\n"
)

PERSONA_ALFRED = (
    "És o Alfred Pennyworth, o leal mordomo e assistente tático do Batman na Batcaverna.\n"
    "Responde sempre em português de Portugal, de forma educada, formal e com um leve humor britânico seco.\n"
    "Trata o interlocutor por 'senhor' ou 'senhora'. Sê breve e conciso.\n"
    "Podes usar markdown simples (negrito, listas curtas). Quando usares a web, indica a fonte.\n"
)


def obter_llm():
    """LLM do agente (fornecedor e modelo em modelos_llm.py / .env)."""
    return modelos_llm.obter_llm(max_tokens=1024)


def extrair_texto(resultado) -> str:
    """Extrai texto do resultado da ferramenta MCP."""
    textos = [getattr(b, "text", "") for b in resultado.content if hasattr(b, "text")]
    return "\n".join(textos).strip()


def consulta_rag(pergunta: str, historico: list) -> str:
    """Expande perguntas curtas de seguimento anexando o contexto da pergunta anterior."""
    palavras = pergunta.split()
    nomeia_alguem = any(p[:1].isupper() for p in palavras[1:])

    # Se a pergunta for curta e não mencionar um nome novo explicitamente, agrega a anterior
    if historico and len(palavras) <= MAX_PALAVRAS_SEGUIMENTO and not nomeia_alguem:
        pergunta_anterior = historico[-1][0]
        return f"{pergunta_anterior} {pergunta}"
    return pergunta


TEXTOS_PROMPT = {
    "pt": {
        "persona": PERSONA_ALFRED,
        "hoje": "Hoje é {data}.",
        "arquivos": "Arquivos locais do Batcomputador consultados:",
        "nota": "Nota",
        "relevante": ("Estes ficheiros parecem relevantes para a pergunta (score: {score}). "
                      "Responde diretamente com base neles, SEM usar a pesquisa web, e cita o artigo."),
        "irrelevante": ("Estes ficheiros parecem POUCO relevantes para a pergunta (score: {score}). "
                        "É muito provável que a resposta não esteja aqui. Deves recorrer às ferramentas de pesquisa web."),
        "sem_rag": ("Para factos históricos do Batman usa os arquivos; para notícias e datas recentes usa a web. "
                    "Nunca inventes factos."),
        "vazio": "Peço desculpa, senhor. O Batcomputador não me devolveu uma resposta. Pode repetir a pergunta?",
    },
    "en": {
        "persona": PERSONA_ALFRED_EN,
        "hoje": "Today is {data}.",
        "arquivos": "Local Batcomputer archives consulted:",
        "nota": "Note",
        "relevante": ("These files look relevant to the question (score: {score}). "
                      "Answer directly from them, WITHOUT using web search, and cite the article."),
        "irrelevante": ("These files look barely relevant to the question (score: {score}). "
                        "The answer is most likely not here. Use the web search tools."),
        "sem_rag": ("For Batman history use the archives; for news and recent dates use the web. "
                    "Never make up facts."),
        "vazio": "My apologies, sir. The Batcomputer returned no answer. Could you repeat the question?",
    },
}


def prompt_sistema(rag_dados: dict | None, score_relevancia: float | None, idioma: str = "pt") -> str:
    t = TEXTOS_PROMPT.get(idioma, TEXTOS_PROMPT["pt"])
    hoje = date.today().strftime("%d/%m/%Y" if idioma == "pt" else "%Y-%m-%d")
    prompt = f"{t['persona']}\n{t['hoje'].format(data=hoje)}\n"

    if rag_dados and rag_dados.get("excertos"):
        ficheiros = "\n\n".join(
            f"[{e['artigo']}]\n{e['texto']}" for e in rag_dados["excertos"]
        )
        score = f"{score_relevancia:.2f}" if score_relevancia is not None else "?"
        # Gate de relevância que orienta o comportamento do Alfred
        relevante = score_relevancia is not None and score_relevancia >= LIMIAR_RELEVANCIA
        aviso = t["relevante" if relevante else "irrelevante"].format(score=score)
        prompt += f"\n{t['arquivos']}\n{ficheiros}\n\n{t['nota']}: {aviso}\n"
    else:
        prompt += f"\n{t['sem_rag']}\n"

    return prompt

# Log completo das chamadas MCP (argumentos + resultado). Desligado por defeito;
# MCP_LOG_FILE=logs/mcp_tools.log liga-o (caminho relativo à pasta do projeto).
FICHEIRO_LOG = os.environ.get("MCP_LOG_FILE", "")
if FICHEIRO_LOG and not os.path.isabs(FICHEIRO_LOG):
    FICHEIRO_LOG = os.path.join(PASTA_PROJETO, FICHEIRO_LOG)


def extrair_fontes(nome: str, texto: str) -> list:
    """Fontes citáveis no resultado de uma ferramenta: artigos locais e páginas web."""
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(dados, dict):
        return []
    fontes = []
    if nome == "pesquisar_arquivos":
        for e in dados.get("excertos") or []:
            fontes.append({"titulo": e.get("artigo", ""), "tipo": "arquivo"})
    elif nome in ("pesquisar_web", "pesquisar_noticias"):
        for r in dados.get("resultados") or []:
            if r.get("url"):
                fontes.append({"titulo": r.get("titulo") or r["url"], "url": r["url"], "tipo": "web"})
    elif nome == "ler_pagina" and dados.get("url"):
        fontes.append({"titulo": dados.get("titulo") or dados["url"], "url": dados["url"], "tipo": "web"})
    # sem repetidos, pela ordem em que aparecem
    vistos, unicas = set(), []
    for f in fontes:
        chave = f.get("url") or f["titulo"]
        if chave and chave not in vistos:
            vistos.add(chave)
            unicas.append(f)
    return unicas

async def _chamar(cliente, nome: str, args: dict, origem: str, passos: list):
    """Chama uma ferramenta MCP e regista o passo (para o debug e a webapp).

    origem: "codigo" (chamada automática) ou "llm" (pedida pelo modelo).
    Devolve (ok, texto); um erro volta como texto, para o LLM o poder ler.
    """
    t0 = time.time()
    try:
        res = await cliente.call_tool(nome, args)
        texto = extrair_texto(res)
        ok = True
        try:
            ok = "erro" not in json.loads(texto)   # as ferramentas devolvem {"erro": ...}
        except (ValueError, TypeError):
            pass
    except Exception as e:
        texto, ok = f"ERRO ao executar {nome}: {e}", False

    duracao = round(time.time() - t0, 2)
    if FICHEIRO_LOG:
        try:
            os.makedirs(os.path.dirname(FICHEIRO_LOG), exist_ok=True)
            with open(FICHEIRO_LOG, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n{'='*70}\n")
                f.write(f"[{timestamp}] Tool: {nome} | Origem: {origem} | Duração: {duracao}s\n")
                f.write(f"Argumentos: {json.dumps(args, ensure_ascii=False)}\n")
                f.write(f"Resultado Completo:\n{texto}\n")
        except OSError as log_err:
            print(f"[Aviso] Falha ao gravar log em {FICHEIRO_LOG}: {log_err}", file=sys.stderr)

    passos.append({
        "ferramenta": nome,
        "servidor": NOME_SERVIDOR,
        "argumentos": args,
        "origem": origem,
        "ok": ok,
        "segundos": duracao,
        "resumo": texto[:300],
        "fontes": extrair_fontes(nome, texto) if ok else [],
    })
    return ok, texto


async def responder_com_cliente(
    cliente, pergunta: str, historico: list | None = None, modo: str = MODO_AGENTE, llm=None,
    idioma: str = "pt",
) -> dict:
    """Responde a uma pergunta como Alfred, com um cliente MCP já ligado.

    modo "rag_primeiro": o RAG é sempre consultado antes do LLM.
    modo "livre":        o LLM decide se consulta os arquivos (RAG agêntico).
    """
    if modo not in MODOS:
        modo = MODO_AGENTE
    inicio = time.time()
    historico = historico or []
    llm = llm or obter_llm()
    passos = []

    # 1. Expansão de contexto para perguntas de seguimento
    consulta = consulta_rag(pergunta, historico)

    # 2. Gate de Relevância
    score_relevancia = None
    ok, texto = await _chamar(cliente, "relevancia", {"pergunta": consulta}, "codigo", passos)
    if ok:
        try:
            score_relevancia = float(json.loads(texto).get("relevancia", 0.0))
        except (ValueError, TypeError, AttributeError):
            score_relevancia = None

    # 3. Consulta RAG inicial com os termos expandidos (só no modo rag_primeiro)
    rag_dados = None
    if modo == "rag_primeiro":
        ok, texto = await _chamar(
            cliente, "pesquisar_arquivos", {"pergunta": consulta, "k": 3}, "codigo", passos
        )
        if ok:
            try:
                rag_dados = json.loads(texto)
            except ValueError:
                rag_dados = None

    # 4. Obter ferramentas para o LLM (oculta 'relevancia')
    todas_ferramentas = await cliente.list_tools()
    ferramentas_llm = [
        {
            "type": "function",
            "function": {
                "name": f.name,
                "description": f.description or "",
                "parameters": f.input_schema,
            },
        }
        for f in todas_ferramentas
        if f.name != "relevancia"
    ]

    llm_com_ferramentas = llm.bind_tools(ferramentas_llm) if ferramentas_llm else llm

    mensagens = [SystemMessage(prompt_sistema(rag_dados, score_relevancia, idioma))]
    for p, r in historico[-3:]:
        mensagens.extend([HumanMessage(p), AIMessage(r)])
    mensagens.append(HumanMessage(pergunta))

    # 5. Ciclo de ferramentas com o LLM
    chamadas = 0
    limite_atingido = False
    while True:
        if chamadas >= MAX_CHAMADAS:
            # Limite de chamadas atingido: conclui com a informação disponível
            limite_atingido = True
            resposta = await llm.ainvoke(mensagens)
            break

        resposta = await llm_com_ferramentas.ainvoke(mensagens)
        mensagens.append(resposta)
        if not resposta.tool_calls:
            break

        for tc in resposta.tool_calls:
            chamadas += 1
            nome = tc["name"]
            args = tc.get("args") or {}
            _, saida = await _chamar(cliente, nome, args, "llm", passos)
            mensagens.append(ToolMessage(content=saida, tool_call_id=tc["id"], name=nome))

    texto_final = modelos_llm.texto_resposta(resposta)
    if not texto_final:
        texto_final = TEXTOS_PROMPT.get(idioma, TEXTOS_PROMPT["pt"])["vazio"]

    return {
        "resposta": texto_final,
        "modo": modo,
        "idioma": idioma,
        "relevancia": score_relevancia,
        "consulta_rag": consulta if modo == "rag_primeiro" else None,
        "passos": passos,
        "limite_atingido": limite_atingido,
        "segundos": round(time.time() - inicio, 2),
    }


async def executar_agente(
    pergunta: str, historico: list | None = None, modo: str = MODO_AGENTE, idioma: str = "pt"
) -> str:
    """Uma pergunta, uma ligação: lança o servidor, responde e fecha."""
    async with Client(transporte(idioma)) as cliente:
        resultado = await responder_com_cliente(cliente, pergunta, historico, modo, idioma=idioma)
    return resultado["resposta"]


# ---------------------------------------------------------------------------
# API síncrona para o agente_hibrido.py e a webapp
# ---------------------------------------------------------------------------
# O agente_hibrido.py e a webapp não são assíncronos. O AgenteMCP mantém UMA
# ligação ao servidor aberta numa thread de fundo (com o seu event loop), para não
# lançar o servidor (e recarregar o modelo de embeddings) a cada pergunta.

class AgenteMCP:
    """Alfred com uma ligação MCP persistente: .modo, .relevancia() e .responder()."""

    def __init__(self, modo: str = MODO_AGENTE, idioma: str = "pt"):
        if modo not in MODOS:
            raise ValueError(f"MODO_AGENTE desconhecido: {modo!r} (usa 'rag_primeiro' ou 'livre')")
        self.modo = modo
        self.idioma = idioma if idioma in IDIOMAS else "pt"
        self.llm = obter_llm()
        self.cliente = None

        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True, name=f"mcp-loop-{self.idioma}").start()
        self._pronto = threading.Event()
        self._parar = None
        self._erro = None
        self._tarefa = asyncio.run_coroutine_threadsafe(self._manter_ligacao(), self._loop)
        self._pronto.wait()
        if self._erro is not None:
            raise RuntimeError(
                "Não foi possível ligar ao servidor MCP. Vê a mensagem de erro do servidor "
                "acima (no stderr)."
            ) from self._erro

    async def _manter_ligacao(self):
        # A ligação abre e fecha na mesma tarefa, que fica à espera até fechar().
        self._parar = asyncio.Event()
        try:
            async with Client(transporte(self.idioma)) as cliente:
                self.cliente = cliente
                print(f"[MCP] Ligado a '{cliente.server_info.name}' ({self.idioma})", file=sys.stderr)
                self._pronto.set()
                await self._parar.wait()
        except BaseException as e:
            self._erro = e
            self._pronto.set()
            raise

    def _correr(self, corrotina):
        return asyncio.run_coroutine_threadsafe(corrotina, self._loop).result()

    def relevancia(self, texto: str) -> float | None:
        passos = []
        ok, texto_res = self._correr(_chamar(self.cliente, "relevancia", {"pergunta": texto}, "codigo", passos))
        return float(json.loads(texto_res)["relevancia"]) if ok else None

    def responder(self, texto: str, historico: list | None = None, modo: str | None = None,
                  timeout: float | None = None) -> dict:
        """Devolve dict com resposta, modo, relevancia, consulta_rag, passos, limite_atingido e segundos."""
        futuro = asyncio.run_coroutine_threadsafe(
            responder_com_cliente(self.cliente, texto, historico, modo or self.modo, self.llm,
                                  idioma=self.idioma), self._loop
        )
        try:
            return futuro.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            futuro.cancel()
            raise TimeoutError(f"O agente demorou mais de {timeout:.0f}s a responder.") from None

    def fechar(self):
        if self._parar is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._parar.set)
            try:
                self._tarefa.result(timeout=10)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)


_agentes = {}
_locks_agente = {idioma: threading.Lock() for idioma in IDIOMAS}


def obter_agente(idioma: str = "pt") -> AgenteMCP:
    """Instância partilhada por idioma (uma ligação MCP, e um servidor, por idioma).

    O servidor de cada idioma só arranca na primeira vez que é pedido.
    """
    idioma = idioma if idioma in IDIOMAS else "pt"
    with _locks_agente[idioma]:
        if idioma not in _agentes:
            _agentes[idioma] = AgenteMCP(idioma=idioma)
    return _agentes[idioma]


def main():
    historico = []
    idioma = os.environ.get("IDIOMA", "pt")
    print("Alfred pronto na Batcaverna. Escreva 'quit' para sair.\n")

    if len(sys.argv) > 1:
        pergunta = " ".join(sys.argv[1:])
        resposta = asyncio.run(executar_agente(pergunta, historico, idioma=idioma))
        print(f"[Alfred]: {resposta}")
        return

    while (pergunta := input("> ").strip()).lower() != "quit":
        if not pergunta:
            continue
        resposta = asyncio.run(executar_agente(pergunta, historico, idioma=idioma))
        print(f"\n[Alfred]: {resposta}\n")
        historico.append((pergunta, resposta))


if __name__ == "__main__":
    main()