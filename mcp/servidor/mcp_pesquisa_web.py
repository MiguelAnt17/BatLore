"""Web Search: ferramentas de pesquisa web simplificadas para servidor MCP."""

import ipaddress
import os
import socket
from urllib.parse import urlparse

import trafilatura
from ddgs import DDGS

from mcp_servidor import mcp

# Região da pesquisa: Portugal no servidor PT, EUA/inglês no servidor EN
REGIAO = "us-en" if os.environ.get("IDIOMA") == "en" else "pt-pt"
MAX_RESULTADOS = 10
MAX_CARACTERES = 8000



def _url_publico(url: str) -> bool:
    """True se o URL aponta para um endereço público.

    Proteção contra SSRF: numa versão pública da webapp, o LLM não pode ser levado
    a ler endereços internos (localhost, rede privada, metadados da cloud).
    """
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError):
        return False
    for endereco in enderecos:
        ip = ipaddress.ip_address(endereco.split("%", 1)[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return True


@mcp.tool()
def pesquisar_web(
    consulta: str, max_resultados: int = 5, periodo: str | None = None
) -> dict:
    """Pesquisa geral na web. Devolve lista de resultados com título, URL e excerto."""
    n = max(1, min(max_resultados, MAX_RESULTADOS))
    try:
        brutos = list(
            DDGS().text(consulta, region=REGIAO, timelimit=periodo, max_results=n)
        )
    except Exception as e:
        return {"erro": f"A pesquisa falhou: {e}"}

    resultados = [
        {
            "titulo": r.get("title", ""),
            "url": r.get("href", ""),
            "excerto": r.get("body", ""),
        }
        for r in brutos
    ]

    return {
        "consulta": consulta,
        "n_resultados": len(resultados),
        "resultados": resultados,
    }


@mcp.tool()
def pesquisar_noticias(
    consulta: str, max_resultados: int = 5, periodo: str | None = "m"
) -> dict:
    """Pesquisa notícias recentes. Cada resultado inclui data e fonte."""
    n = max(1, min(max_resultados, MAX_RESULTADOS))
    try:
        brutos = list(
            DDGS().news(consulta, region=REGIAO, timelimit=periodo, max_results=n)
        )
    except Exception as e:
        return {"erro": f"A pesquisa de notícias falhou: {e}"}

    resultados = [
        {
            "titulo": r.get("title", ""),
            "url": r.get("url", ""),
            "excerto": r.get("body", ""),
            "fonte": r.get("source", ""),
            "data": r.get("date", ""),
        }
        for r in brutos
    ]

    return {
        "consulta": consulta,
        "n_resultados": len(resultados),
        "resultados": resultados,
    }


@mcp.tool()
def ler_pagina(url: str, max_caracteres: int = 4000) -> dict:
    """Descarrega uma página web e devolve o texto limpo principal."""
    if urlparse(url).scheme not in ("http", "https"):
        return {"erro": "O URL tem de começar por http:// ou https://"}
    if not _url_publico(url):
        return {"erro": "Só é possível ler páginas públicas da internet."}

    html = trafilatura.fetch_url(url)
    if not html:
        return {"erro": f"Não foi possível descarregar a página: {url}"}

    texto = trafilatura.extract(html, include_comments=False, include_tables=False)
    if not texto:
        return {"erro": "A página não tem texto que se consiga extrair."}

    meta = trafilatura.extract_metadata(html)
    limite = max(500, min(max_caracteres, MAX_CARACTERES))

    return {
        "url": url,
        "titulo": meta.title if meta and meta.title else "",
        "data": meta.date if meta and meta.date else "",
        "texto": texto[:limite],
        "truncado": len(texto) > limite,
    }
