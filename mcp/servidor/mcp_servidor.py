"""Servidor MCP do D3: uma instância FastMCP com todas as ferramentas do Alfred.

Organização (como nos slides: MCP Server / Web Search / Custom Function / MCP Client):
    mcp_servidor.py      -> MCP Server: cria a instância e arranca-a
    mcp_pesquisa_web.py  -> Web Search: pesquisar_web, pesquisar_noticias, ler_pagina
    mcp_funcoes.py       -> Custom Function: o RAG do D2 (pesquisar_arquivos,
                            relevancia, listar_arquivos)
    mcp_batman.py        -> Custom Function: perguntar_ao_batman (o agente de regras do D1)
    mcp_batinfo.py       -> Sistemas da Batcaverna (simulados): estado_batmovel,
                            clima_gotham, gerir_agenda_bruce
    ../cliente/agente_mcp.py -> MCP Client: o Alfred (LLM + ferramentas)

As ferramentas registam-se na instância `mcp` deste ficheiro com @mcp.tool.
Usa a biblioteca FastMCP (https://gofastmcp.com), construída sobre o SDK oficial do MCP.

Execução:
    python mcp/servidor/mcp_servidor.py          # stdio (o cliente lança o processo)
    python mcp/servidor/mcp_servidor.py --http   # Streamable HTTP em http://localhost:8002/mcp
    fastmcp dev inspector mcp/servidor/mcp_servidor.py   # MCP Inspector, para testar à mão

Dependências:
    pip install fastmcp ddgs trafilatura
"""

import sys

from fastmcp import FastMCP

# "python mcp_servidor.py" carrega este ficheiro como __main__. Sem esta linha, o
# "from mcp_servidor import mcp" dos ficheiros de ferramentas voltava a carregá-lo
# com outro nome e criava um segundo servidor, sem ferramentas.
sys.modules.setdefault("mcp_servidor", sys.modules[__name__])

PORTA_HTTP = 8002   # 8001 = webapp; 8002 = este servidor (modo --http)

mcp = FastMCP(
    "batcomputador",
    instructions=(
        "Batcomputador do Alfred. Os arquivos locais (pesquisar_arquivos) têm 18 artigos "
        "da Wikipédia em português sobre Batman, Gotham, os seus aliados e vilões: são a "
        "fonte principal para personagens, locais e história. Para filmes, séries, BD e "
        "notícias recentes usa pesquisar_web ou pesquisar_noticias, e ler_pagina para ler "
        "um resultado em detalhe. Para o estado dos veículos, o clima de Gotham ou a agenda "
        "do Bruce Wayne usa estado_batmovel, clima_gotham e gerir_agenda_bruce. "
        "Se precisares de falar com o batman, ou quiseres reportar-lhe algo, podes usar a ferramenta 'perguntar_ao_batman'.\n" 
    ),
)

# Registo das ferramentas: importar os módulos corre os @mcp.tool de cada um.
import mcp_pesquisa_web  # noqa: E402,F401
import mcp_funcoes  # noqa: E402,F401
import mcp_batman  # noqa: E402,F401
import mcp_batinfo  # noqa: E402,F401

if __name__ == "__main__":
    # Em stdio, o stdout é o canal do protocolo: as mensagens vão para o stderr.
    # show_banner=False: o FastMCP mostra por defeito um banner grande no arranque.
    if "--http" in sys.argv:
        print(f"Servidor MCP em http://localhost:{PORTA_HTTP}/mcp", file=sys.stderr)
        mcp.run(transport="http", port=PORTA_HTTP, show_banner=False)
    else:
        print("Servidor MCP em stdio (o cliente lança o processo)", file=sys.stderr)
        mcp.run(show_banner=False)
