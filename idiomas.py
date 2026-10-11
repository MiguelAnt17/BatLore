"""Textos de cada idioma da conversa: frases do router, frases para terminar a
conversa com o Alfred e as frases fixas do Batman e do Alfred.

Módulo leve (sem modelos), usado pelo agente_hibrido.py e pelos testes.
"""

import re
import unicodedata

# Frases que ativam o Alfred
FRASES_ALFRED = [
    "Alfred, acede ao Batcomputador e pesquisa sobre isto.",
    "Alfred, o que dizem os registos do GCPD e de Arkham?",
    "Preciso de informações detalhadas da base de dados, Alfred.",
    "Procura nos ficheiros de criminosos.",
    "Não percebi.",
    "Não respondeste ao que eu te perguntei.",
    "Quero falar com o Alfred.",
    "Olá alfred"
]

FRASES_ALFRED_EN = [
    "Alfred, access the Batcomputer and look this up.",
    "Alfred, what do the GCPD and Arkham records say?",
    "I need detailed information from the database, Alfred.",
    "Search the criminal files.",
    "I didn't understand.",
    "You didn't answer my question.",
    "I want to talk to Alfred.",
    "Hello Alfred",
]

# Frases que voltam ao Batman
FRASES_BATMAN = [
    "Desliga o canal. Volto à patrulha.",
    "Chega de computador. Vou interrogar os suspeitos.",
    "Desliga o terminal, vou resolver isto à minha maneira.",
    "Silêncio na escuta.",
    "Quero falar com o Batman.",
    "Olá Batman"
]

FRASES_BATMAN_EN = [
    "Close the channel. Back to patrol.",
    "Enough with the computer. I'll interrogate the suspects.",
    "Shut down the terminal, I'll handle this my way.",
    "Radio silence.",
    "I want to talk to Batman.",
    "Hello Batman",
]

# Frases para terminar a conversa com o Alfred (voltar ao Batman). Ao contrário do
# router (por similaridade), estas são reconhecidas de forma exata, depois de
# normalizar: o Alfred despede-se e a linha volta ao Batman.
FRASES_SAIR_ALFRED = {
    "pt": ["obrigado alfred e tudo", "obrigada alfred e tudo", "e tudo alfred", "adeus alfred",
           "tchau alfred", "ate logo alfred", "termina a ligacao", "terminar ligacao",
           "desliga alfred", "parar de falar com o alfred", "sair do alfred", "fim da ligacao"],
    "en": ["thanks alfred thats all", "thank you alfred thats all", "thats all alfred",
           "goodbye alfred", "bye alfred", "end call", "end the call", "hang up",
           "stop talking to alfred", "thats all for now alfred", "over and out alfred"],
}


def _normalizar(texto):
    """minúsculas, sem acentos nem pontuação: "Obrigado, Alfred. É tudo!" -> "obrigado alfred e tudo"."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("'", "").replace("’", "")
    return " ".join(re.findall(r"\w+", texto))


def quer_sair_do_alfred(texto, idioma="pt"):
    """True se a mensagem é um pedido explícito para terminar a conversa com o Alfred."""
    normal = _normalizar(texto)
    return any(normal == f or normal.startswith(f + " ") or normal.endswith(" " + f)
               for f in FRASES_SAIR_ALFRED.get(idioma, []) + FRASES_SAIR_ALFRED["pt"])


TEXTOS = {
    "pt": {
        "saudacao": "Gotham nunca dorme. Porque é que estás aqui?",
        "despedida": "Gotham não dorme. Nem eu. Vejo-te por aí.",
        "regresso_batman": "De volta às sombras. Onde é que íamos?",
        "saudacao_alfred": "Ao seu dispor, senhor. O Batcomputador está ligado e pronto. Em que posso ser útil?",
        "despedida_alfred": "Muito bem, senhor. Termino a ligação ao Batcomputador. O Batman fica consigo.",
    },
    "en": {
        "saudacao": "Gotham never sleeps. Why are you here?",
        "despedida": "Gotham doesn't sleep. Neither do I. See you around.",
        "regresso_batman": "Back to the shadows. Where were we?",
        "saudacao_alfred": "At your service, sir. The Batcomputer is online and ready. How may I help?",
        "despedida_alfred": "Very good, sir. I'll close the line to the Batcomputer. Batman is with you now.",
    },
}
