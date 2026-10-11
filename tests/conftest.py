"""Testes rápidos e offline: não precisam de Ollama, chaves de API, rede nem modelos."""

import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for pasta in ("", "rag", os.path.join("mcp", "cliente"), os.path.join("mcp", "servidor")):
    caminho = os.path.join(RAIZ, pasta)
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

# O servidor MCP real (mcp_servidor.py) importa todas as ferramentas, incluindo o RAG
# (que carrega a Vector DB). Para testar uma ferramenta isolada, os testes usam uma
# instância FastMCP vazia no lugar do módulo mcp_servidor.
if "mcp_servidor" not in sys.modules:
    from fastmcp import FastMCP

    falso = types.ModuleType("mcp_servidor")
    falso.mcp = FastMCP("teste")
    sys.modules["mcp_servidor"] = falso

os.environ.setdefault("LLM_PROVIDER", "ollama")
