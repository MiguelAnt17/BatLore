"""Testes unitários das peças sem modelos: LLM config, RRF, fontes, SSRF e agenda."""

import json

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

import modelos_llm


# ---------- modelos_llm ----------

def test_fornecedor_e_modelo_por_defeito(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Groq")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("MODELO_GROQ", raising=False)
    assert modelos_llm.descricao() == {"fornecedor": "groq", "modelo": "llama-3.3-70b-versatile"}


def test_alias_e_modelo_explicito(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "hf")
    monkeypatch.setenv("LLM_MODEL", "org/modelo")
    assert modelos_llm.descricao() == {"fornecedor": "huggingface", "modelo": "org/modelo"}


def test_fornecedor_invalido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nada")
    with pytest.raises(ValueError):
        modelos_llm.fornecedor()


def test_chave_em_falta(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        modelos_llm.obter_llm()


@pytest.mark.parametrize("conteudo, esperado", [
    ("<think>a pensar...</think>\nOlá, senhor.", "Olá, senhor."),
    ([{"type": "text", "text": "Boa "}, {"type": "tool_use"}, {"type": "text", "text": "noite."}], "Boa noite."),
    ("  Resposta  ", "Resposta"),
    ("<think>cortado a meio", ""),
])
def test_texto_resposta(conteudo, esperado):
    assert modelos_llm.texto_resposta(AIMessage(content=conteudo)) == esperado


# ---------- RAG: fusão RRF ----------

def test_fusao_rrf_privilegia_documentos_nas_duas_listas():
    import rag_system as rag
    a, b, c = (Document(page_content=x) for x in "abc")
    resultado = rag.fusao_rrf([a, b], [c, b], k=2)
    assert resultado[0].page_content == "b"
    assert len(resultado) == 2


def test_remover_acentos():
    import rag_system as rag
    assert rag.remover_acentos("Batmóvel Ração") == "Batmovel Racao"


# ---------- agente MCP ----------

def test_consulta_rag_expande_seguimentos():
    import agente_mcp
    historico = [("Quem é o Joker?", "...")]
    assert agente_mcp.consulta_rag("e a origem?", historico) == "Quem é o Joker? e a origem?"
    # nome novo -> pergunta independente
    assert agente_mcp.consulta_rag("e o Bane?", historico) == "e o Bane?"
    assert agente_mcp.consulta_rag("e a origem?", []) == "e a origem?"


def test_extrair_fontes():
    import agente_mcp
    web = json.dumps({"resultados": [
        {"titulo": "A", "url": "https://a.pt"}, {"titulo": "A2", "url": "https://a.pt"}, {"titulo": "sem url"}]})
    assert agente_mcp.extrair_fontes("pesquisar_web", web) == [{"titulo": "A", "url": "https://a.pt", "tipo": "web"}]
    arq = json.dumps({"excertos": [{"artigo": "Batman"}, {"artigo": "Batman"}, {"artigo": "Bane"}]})
    assert [f["titulo"] for f in agente_mcp.extrair_fontes("pesquisar_arquivos", arq)] == ["Batman", "Bane"]
    assert agente_mcp.extrair_fontes("pesquisar_web", "não é json") == []


# ---------- ferramentas MCP ----------

@pytest.mark.parametrize("url", [
    "http://localhost:8001/", "http://127.0.0.1/", "http://10.0.0.5/admin",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http:///sem-host",
])
def test_ler_pagina_bloqueia_enderecos_internos(url):
    import mcp_pesquisa_web
    assert mcp_pesquisa_web._url_publico(url) is False


def test_ler_pagina_recusa_esquemas_estranhos():
    import mcp_pesquisa_web
    fn = getattr(mcp_pesquisa_web.ler_pagina, "fn", mcp_pesquisa_web.ler_pagina)
    assert "erro" in fn("file:///etc/passwd")
    assert "erro" in fn("http://127.0.0.1:8001/")


def test_agenda_limites():
    import mcp_batinfo
    fn = getattr(mcp_batinfo.gerir_agenda_bruce, "fn", mcp_batinfo.gerir_agenda_bruce)
    assert "erro" in fn("escrever", "hoje", "")
    r = fn("escrever", "dia-teste", "x" * 1000)
    assert r["sucesso"] and len(r["agenda_atualizada"][-1]) == mcp_batinfo.MAX_TEXTO_COMPROMISSO
    for _ in range(mcp_batinfo.MAX_COMPROMISSOS_DIA):
        fn("escrever", "dia-teste", "reunião")
    assert "erro" in fn("escrever", "dia-teste", "mais uma")
    assert fn("ler", "dia-teste")["compromissos"]


# ---------- idiomas (PT / EN) ----------

@pytest.mark.parametrize("texto, idioma", [
    ("Obrigado, Alfred. É tudo.", "pt"),
    ("adeus Alfred!", "pt"),
    ("Thanks, Alfred. That's all.", "en"),
    ("ok, bye Alfred", "en"),
    ("Hang up", "en"),
])
def test_frases_para_sair_do_alfred(texto, idioma):
    import idiomas
    assert idiomas.quer_sair_do_alfred(texto, idioma)


@pytest.mark.parametrize("texto", ["Obrigado, Alfred", "Quem é o Bane?", "Thanks Alfred, who is Bane?"])
def test_frases_normais_nao_terminam_a_ligacao(texto):
    import idiomas
    assert not idiomas.quer_sair_do_alfred(texto, "en")


def test_textos_existem_nos_dois_idiomas():
    import idiomas
    assert set(idiomas.TEXTOS["pt"]) == set(idiomas.TEXTOS["en"])
    assert len(idiomas.FRASES_ALFRED_EN) == len(idiomas.FRASES_ALFRED)


def test_prompt_do_alfred_em_ingles():
    import agente_mcp
    prompt = agente_mcp.prompt_sistema({"excertos": [{"artigo": "Joker (character)", "texto": "..."}]}, 0.9, "en")
    assert "Always answer in English" in prompt and "[Joker (character)]" in prompt
    assert "português" in agente_mcp.prompt_sistema(None, None, "pt")


def test_rag_configura_cada_idioma():
    import rag_system as rag
    fontes_en, pasta_en, db_en = rag.config_idioma("en")
    fontes_pt, pasta_pt, db_pt = rag.config_idioma("pt")
    assert len(fontes_en) == len(fontes_pt) == 18
    assert pasta_en != pasta_pt and db_en != db_pt
    assert all("en.wikipedia.org" in u for u in fontes_en.values())
    assert rag.titulo_fonte(fontes_en["wiki_joker.pdf"]) == "Joker (character)"
