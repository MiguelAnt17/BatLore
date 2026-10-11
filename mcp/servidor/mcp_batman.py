"""Custom Function (D3): Ferramenta que permite ao Alfred consultar o agente de regras (Batman)."""

import os
import sys
import random

from mcp_servidor import mcp

# ---------------------------------------------------------------------------
# Arranque: carregar o agente de regras (D1)
# ---------------------------------------------------------------------------
# Ajusta o caminho se o teu rule_based.py estiver noutra diretoria
PASTA_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PASTA_RAIZ not in sys.path:
    sys.path.insert(0, PASTA_RAIZ)

# O servidor em inglês (IDIOMA=en) consulta o Batman de regras em inglês
if os.environ.get("IDIOMA") == "en":
    import rule_based_en as ruleBasedAgent
else:
    import rule_based as ruleBasedAgent

# Contexto partilhado para o Batman "lembrar-se" dos nomes e locais durante a sessão
CONTEXTO_BATMAN = {"nomes": set(), "locais": set()}

# ---------------------------------------------------------------------------
# Ferramenta MCP
# ---------------------------------------------------------------------------

@mcp.tool()
def perguntar_ao_batman(mensagem: str) -> dict:
    """
    Usa esta ferramenta para fazer uma pergunta direta ao Batman ou pedir a sua opinião/dedução sobre uma pista.
    Útil quando precisas da perspetiva fria e calculista do Bruce Wayne sobre suspeitos, locais, ou regras de Gotham.
    """
    
    # 1. Processar NER e POS do texto
    doc = ruleBasedAgent.nlp(mensagem)
    entidades = ruleBasedAgent.extrair_entidades(doc)

    # 2. Verificar se o Batman tem uma reação específica a uma nova entidade (Pessoa/Local)
    resposta_especial = ruleBasedAgent.reagir_a_entidades(entidades, CONTEXTO_BATMAN)
    if resposta_especial:
        return {
            "pergunta_alfred": mensagem,
            "resposta_batman": resposta_especial,
            "via": "entidade"
        }

    # 3. Corrigir intenção (Edit distance)
    texto_corrigido = ruleBasedAgent.corrigir_intencao(mensagem, ruleBasedAgent.pairs_batman, max_distance=1)

    # 4. Procura por correspondência direta nas Regras RegEx
    if ruleBasedAgent.encontrar_regra_chat(texto_corrigido, ruleBasedAgent.pairs_batman):
        resposta = ruleBasedAgent.batman_chatbot.respond(texto_corrigido)
        return {
            "pergunta_alfred": mensagem,
            "resposta_batman": resposta,
            "via": "regra_regex"
        }

    # 5. Procura de intenção via TF-IDF
    resultado_tfidf = ruleBasedAgent.encontrar_intencao_tfidf(
        texto_corrigido, 
        ruleBasedAgent.tfidf_vectorizer, 
        ruleBasedAgent.tfidf_matriz, 
        ruleBasedAgent.tfidf_regras, 
        threshold=0.35
    )
    
    if resultado_tfidf:
        resposta = random.choice(resultado_tfidf["responses"])
        return {
            "pergunta_alfred": mensagem,
            "resposta_batman": resposta,
            "via": "tfidf"
        }

    # 6. Fallback final
    resposta = ruleBasedAgent.batman_chatbot.respond(texto_corrigido)
    return {
        "pergunta_alfred": mensagem,
        "resposta_batman": resposta,
        "via": "fallback"
    }