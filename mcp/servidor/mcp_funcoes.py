"""Custom Function (D3): o RAG do D2 como ferramentas simplificadas do servidor MCP."""

import contextlib
import os
import sys

from mcp_servidor import mcp

# ---------------------------------------------------------------------------
# Arranque: carregar o RAG do D2 sem poluir stdout
# ---------------------------------------------------------------------------
PASTA_RAG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "rag",
)
if PASTA_RAG not in sys.path:
    sys.path.insert(0, PASTA_RAG)

# Idioma deste servidor: o cliente lança um servidor por idioma (IDIOMA=pt|en),
# cada um com a sua Vector DB (Wikipédia PT ou EN).
IDIOMA = os.environ.get("IDIOMA", "pt") if os.environ.get("IDIOMA") in ("pt", "en") else "pt"

with contextlib.redirect_stdout(sys.stderr):
    import rag_system as rag

    _db = rag.obter_vector_db_idioma(IDIOMA)

_FONTES, _, _ = rag.config_idioma(IDIOMA)
TITULOS = {}
for _ficheiro, _url in _FONTES.items():
    _titulo = rag.titulo_fonte(_url)
    TITULOS[_ficheiro] = _titulo
    TITULOS[os.path.splitext(_ficheiro)[0] + ".txt"] = _titulo  # reserva em texto

K_MAXIMO = 8


def _obter_titulo(metadata: dict) -> str:
    """Extrai o título limpo do documento a partir do caminho do ficheiro."""
    ficheiro = os.path.basename(metadata.get("source", ""))
    return TITULOS.get(ficheiro, ficheiro or "desconhecido")


# ---------------------------------------------------------------------------
# Ferramentas MCP
# ---------------------------------------------------------------------------


@mcp.tool()
def pesquisar_arquivos(pergunta: str, k: int = 3, modo: str = "hibrido") -> dict:
    """Pesquisa nos arquivos do Batcomputador (artigos sobre o universo Batman)."""
    k = max(1, min(k, K_MAXIMO))
    try:
        with contextlib.redirect_stdout(sys.stderr):
            docs = rag.recuperar_chunks(pergunta, _db, k=k, modo=modo)
    except Exception as e:
        return {"erro": f"Falha na pesquisa dos arquivos: {e}"}

    excertos = [
        {
            "texto": d.page_content.strip(),
            "artigo": _obter_titulo(d.metadata),
            "pagina": d.metadata.get("page"),
        }
        for d in docs
    ]

    return {
        "pergunta": pergunta,
        "modo": modo,
        "n_excertos": len(excertos),
        "excertos": excertos,
    }


@mcp.tool()
def relevancia(pergunta: str) -> dict:
    """Mede (0 a 1) quão bem os arquivos locais cobrem uma pergunta."""
    resultados = _db.similarity_search_with_relevance_scores(pergunta, k=1)
    if not resultados:
        return {"pergunta": pergunta, "relevancia": 0.0, "artigo": ""}

    doc, score = resultados[0]
    return {
        "pergunta": pergunta,
        "relevancia": float(score),
        "artigo": _obter_titulo(doc.metadata),
    }


@mcp.tool()
def listar_arquivos() -> dict:
    """Lista todos os artigos disponíveis na base local do Batcomputador."""
    artigos = sorted(set(TITULOS.values()))
    return {
        "n_artigos": len(artigos),
        "artigos": artigos,
    }
