"""O ciclo do agente MCP com um cliente MCP e um LLM falsos (sem rede nem modelos)."""

import asyncio
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage

import agente_mcp


class ClienteFalso:
    """Imita o fastmcp.Client: list_tools() e call_tool()."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    async def list_tools(self):
        return [SimpleNamespace(name=n, description=n, input_schema={"type": "object", "properties": {}})
                for n in ("relevancia", "pesquisar_arquivos", "pesquisar_web")]

    async def call_tool(self, nome, args):
        self.chamadas.append(nome)
        texto = json.dumps(self.respostas[nome], ensure_ascii=False)
        return SimpleNamespace(content=[SimpleNamespace(text=texto)])


class LLMFalso:
    """Primeiro pede uma pesquisa web; depois responde com texto."""

    def __init__(self, guiao):
        self.guiao = list(guiao)
        self.mensagens_vistas = []

    def bind_tools(self, ferramentas):
        self.ferramentas = ferramentas
        return self

    async def ainvoke(self, mensagens):
        self.mensagens_vistas.append(list(mensagens))
        return self.guiao.pop(0)


RESPOSTAS = {
    "relevancia": {"relevancia": 0.3, "artigo": "Batman"},
    "pesquisar_arquivos": {"excertos": [{"artigo": "Batman", "texto": "O Batman protege Gotham."}]},
    "pesquisar_web": {"resultados": [{"titulo": "Notícia", "url": "https://exemplo.pt/n", "excerto": "..."}]},
}


def test_modo_rag_primeiro_com_pesquisa_web():
    cliente = ClienteFalso(RESPOSTAS)
    llm = LLMFalso([
        AIMessage(content="", tool_calls=[{"name": "pesquisar_web", "args": {"consulta": "filme"}, "id": "1"}]),
        AIMessage(content="<think>hmm</think>Estreia em 2027, senhor."),
    ])
    r = asyncio.run(agente_mcp.responder_com_cliente(cliente, "Quando estreia o filme?", [], "rag_primeiro", llm))

    assert r["resposta"] == "Estreia em 2027, senhor."
    assert cliente.chamadas == ["relevancia", "pesquisar_arquivos", "pesquisar_web"]
    assert [p["origem"] for p in r["passos"]] == ["codigo", "codigo", "llm"]
    assert r["passos"][-1]["fontes"][0]["url"] == "https://exemplo.pt/n"
    # a ferramenta interna "relevancia" não é oferecida ao LLM
    assert "relevancia" not in [f["function"]["name"] for f in llm.ferramentas]
    assert r["relevancia"] == 0.3 and not r["limite_atingido"]


def test_modo_livre_nao_chama_o_rag_automaticamente():
    cliente = ClienteFalso(RESPOSTAS)
    llm = LLMFalso([AIMessage(content="Boa noite, senhor.")])
    r = asyncio.run(agente_mcp.responder_com_cliente(cliente, "Olá", [], "livre", llm))
    assert cliente.chamadas == ["relevancia"]
    assert r["modo"] == "livre"


def test_limite_de_chamadas():
    cliente = ClienteFalso(RESPOSTAS)
    pedido = AIMessage(content="", tool_calls=[{"name": "pesquisar_web", "args": {}, "id": "x"}])
    llm = LLMFalso([pedido] * agente_mcp.MAX_CHAMADAS + [AIMessage(content="Fico por aqui, senhor.")])
    r = asyncio.run(agente_mcp.responder_com_cliente(cliente, "?", [], "livre", llm))
    assert r["limite_atingido"]
    assert r["resposta"] == "Fico por aqui, senhor."


def test_modo_invalido_usa_o_defeito():
    cliente = ClienteFalso(RESPOSTAS)
    llm = LLMFalso([AIMessage(content="Certo.")])
    r = asyncio.run(agente_mcp.responder_com_cliente(cliente, "?", [], "qualquer", llm))
    assert r["modo"] == agente_mcp.MODO_AGENTE
