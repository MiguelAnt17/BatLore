"""Escolha do LLM (um único sítio para todo o projeto).

O fornecedor e o modelo escolhem-se com variáveis de ambiente (ou no ficheiro .env):

    LLM_PROVIDER = ollama | groq | openrouter | huggingface      (defeito: ollama)
    LLM_MODEL    = nome do modelo (opcional; cada fornecedor tem um defeito)
    LLM_TEMPERATURE = 0.1

    ollama      -> OLLAMA_BASE_URL (defeito http://localhost:11434)
    groq        -> GROQ_API_KEY
    openrouter  -> OPENROUTER_API_KEY
    huggingface -> HUGGINGFACEHUB_API_TOKEN (ou HF_TOKEN)

Os imports de cada fornecedor são tardios: só é preciso instalar o pacote do
fornecedor que se usa (langchain-ollama, langchain-groq, langchain-openai ou
langchain-huggingface).

Compatibilidade: AGENTE_MODELO, MODELO_GROQ e MODELO_HF (nomes antigos) ainda funcionam.
"""

import os
import re

from dotenv import load_dotenv

PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PASTA_PROJETO, ".env"))

FORNECEDORES = ("ollama", "groq", "openrouter", "huggingface")

# Modelos por defeito: todos suportam tool calling (necessário para o agente MCP).
MODELOS_DEFEITO = {
    "ollama": "qwen2.5:7b",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
}

# Variáveis antigas, por fornecedor (o código do D2/D3 usava estas)
_VARIAVEIS_ANTIGAS = {
    "ollama": "AGENTE_MODELO",
    "groq": "MODELO_GROQ",
    "huggingface": "MODELO_HF",
}

_ALIASES = {"hf": "huggingface", "local": "ollama"}


def fornecedor() -> str:
    nome = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
    nome = _ALIASES.get(nome, nome)
    if nome not in FORNECEDORES:
        raise ValueError(f"LLM_PROVIDER desconhecido: {nome!r} (usa um de {', '.join(FORNECEDORES)})")
    return nome


def nome_modelo(prov: str | None = None) -> str:
    prov = prov or fornecedor()
    return (os.environ.get("LLM_MODEL")
            or os.environ.get(_VARIAVEIS_ANTIGAS.get(prov, ""), "")
            or MODELOS_DEFEITO[prov])


def descricao() -> dict:
    """Fornecedor e modelo em uso (para os logs e para a webapp)."""
    prov = fornecedor()
    return {"fornecedor": prov, "modelo": nome_modelo(prov)}


def obter_llm(max_tokens: int = 800, temperature: float | None = None):
    """Devolve um chat model do LangChain para o fornecedor configurado."""
    prov = fornecedor()
    modelo = nome_modelo(prov)
    if temperature is None:
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.1"))

    if prov == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=modelo,
            temperature=temperature,
            num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "16384")),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    if prov == "groq":
        _exigir_chave("GROQ_API_KEY")
        from langchain_groq import ChatGroq
        return ChatGroq(model=modelo, temperature=temperature, max_tokens=max_tokens)

    if prov == "openrouter":
        chave = _exigir_chave("OPENROUTER_API_KEY")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=modelo,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=chave,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers={"X-Title": "Batman & Alfred chatbot"},
        )

    # huggingface
    token = os.environ.get("HUGGINGFACEHUB_API_TOKEN") or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("LLM_PROVIDER=huggingface precisa de HUGGINGFACEHUB_API_TOKEN (ou HF_TOKEN).")
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    ep = HuggingFaceEndpoint(repo_id=modelo, max_new_tokens=max_tokens,
                             temperature=max(temperature, 0.01), huggingfacehub_api_token=token)
    return ChatHuggingFace(llm=ep)


def _exigir_chave(variavel: str) -> str:
    valor = os.environ.get(variavel, "").strip()
    if not valor:
        raise RuntimeError(f"Falta a variável {variavel} (define-a no ficheiro .env).")
    return valor


_PENSAMENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def texto_resposta(mensagem) -> str:
    """Texto final de uma resposta do LLM.

    - content pode ser uma lista de blocos (alguns fornecedores) -> junta o texto;
    - modelos de raciocínio (qwen3, deepseek-r1) incluem <think>...</think> -> remove.
    """
    conteudo = getattr(mensagem, "content", mensagem)
    if isinstance(conteudo, list):
        partes = []
        for bloco in conteudo:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict) and bloco.get("type") == "text":
                partes.append(bloco.get("text", ""))
        conteudo = "".join(partes)
    conteudo = _PENSAMENTO.sub("", str(conteudo or ""))
    # <think> sem fecho (resposta cortada): fica só o que vem antes
    conteudo = conteudo.split("<think>")[0]
    return conteudo.strip()
