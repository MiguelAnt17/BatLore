"""Rule-based Batman in English (the English counterpart of rule_based.py).

Same pipeline and the same public names as rule_based.py, so agente_hibrido.py can
use either module: spaCy NER/POS -> edit-distance correction -> regex rules (NLTK
Chat) -> TF-IDF intent -> fallback.

    python rule_based_en.py          # chat with Batman in the terminal

Needs the English spaCy model:  python -m spacy download en_core_web_sm
"""

import random

import spacy
from nltk.chat.util import Chat, reflections

import rule_based as _pt  # generic helpers (entities, POS, correction, TF-IDF)

# Reflections (I -> you, my -> your, ...): NLTK's English table plus a few extras
reflections_en = dict(reflections)
reflections_en.update({"i'm": "you are", "you're": "I am", "myself": "yourself", "yourself": "myself"})


# (regex, responses). Order matters: the first matching rule wins.
pairs_batman = (
    (
        r"(.*)batmobile(.*)",
        (
            "The Batmobile isn't a toy. It's armour, speed and a lab that tells me what the street is hiding.",
            "I left it two blocks from here, in the shadows. It reaches any point in Gotham before any patrol.",
            "I scraped gunpowder and paint off its chassis tonight. Tell me where you were and I'll tell you what it found.",
            "Everyone wants to see the Batmobile. Few understand it's just a tool. The work is done with information, and you have it.",
            "You can hear its engine three streets away. If you heard it tonight, I need to know what time.",
        ),
    ),
    (
        r"(.*)joker(.*)",
        (
            "The Joker doesn't want money or power. He wants to see us broken in half. That's what makes him different.",
            "If the Joker is behind this, nothing you saw will make sense. That's his plan. Tell me everything, even what seems absurd.",
            "I've taken him to Arkham enough times to know bars don't hold him. People who talk do. Be one of them.",
            "Don't laugh at the Joker's jokes. That's how he picks who's left for last.",
            "The Joker always leaves a signature: a card, a painted smile, a witness alive to tell the story. Did you see anything like that?",
        ),
    ),
    (
        r"(hello|hi|hey|good evening)(,)? batman(.*)",
        (
            "You reached the shadows at the right time. I need your help with something.",
            "You're here. Good. I have an open case and I'm missing answers.",
            "What brings you here at this hour? Whatever it is, I need to ask you something first.",
            "Few come this far for a good reason. I hope yours helps me.",
        ),
    ),
    (
        r"I need (.*)",
        (
            "Everyone needs something. Hold that thought. I have an open lead and I need your eyes.",
            "Whoever depends on %1 never learns to stand alone. We'll talk later. First, help me with something.",
            "Do you think %1 will give you what you're really looking for? While you think, tell me what you know about tonight.",
            "Needing is one thing. Being willing to pay the price is another. I need you to pay yours with information.",
        ),
    ),
    (
        r"Why can'?t I (.*)",
        (
            "It's not a question of ability. It's will and time, and we're losing time.",
            "If you could %1, would you be ready for the consequences? Answer later. Right now I need facts.",
            "The limits you feel are the ones you set yourself. Leave that with me. Tell me what you know.",
        ),
    ),
    (
        r"Why don'?t you (.*)",
        (
            "Maybe you're not ready for me to %1. Meanwhile, I need your help with something more urgent.",
            "That's a question you should ask yourself. Not now. I have a lead to follow and the clock doesn't stop.",
            "There's always a reason. Keep it. I need you focused on what I'm about to ask.",
        ),
    ),
    (
        r"I can'?t (.*)",
        (
            "You can't, or you haven't fallen enough times yet? Another conversation. I need you now.",
            "Get up. There's work to do and I'm short of hands I can trust.",
            "Tell me what stops you from %1 later. First, tell me what you know about tonight.",
            "Everyone falls. Few get up in time to help someone who needs it. Can you do that now?",
        ),
    ),
    (
        r"I(?: am|'m) (.*)",
        (
            "It's not who you are underneath. It's what you do that defines you, and right now I need you to do something for me.",
            "How long have you carried being %1? Keep it. I have a lead that needs your eyes.",
            "%1. A mask, or the truth? Find out later. Now answer me something.",
            "Everyone wears a disguise. Mine is running out of time. Will you help me or not?",
        ),
    ),
    (
        r"Are you (.*)",
        (
            "Would you rather I wasn't? That's not what's at stake now.",
            "Maybe you need to believe I'm %1. Believe what you want, but help me first.",
            "Shadows have no names. What they have is little time. I need you.",
            "Labels mean nothing in the dark. What matters is whether you can help me.",
        ),
    ),
    (
        r"You(?: are|'re) (.*)",
        (
            "I'm what Gotham needs me to be tonight. And I need you to be what I need right now.",
            "You really think I'm %1? That's not what matters. Will you help me?",
            "Are you talking about me, or looking into a mirror? Either way, I need your help.",
        ),
    ),
    (
        r"What (.*)",
        (
            "Why do you need to know? Keep the question. I need you to answer one first.",
            "An answer won't protect you. But it might help me protect others. Work with me.",
            "Easy answers are the first to betray you. I have no time for them. Help me.",
            "Some things are better left unknown. But I need you to know enough to help me now.",
            "Look for it yourself first. Then we talk. Right now I need your full attention.",
        ),
    ),
    (
        r"How (.*)",
        (
            "How do you think? It's no time for guessing. Help me confirm it.",
            "The answer is already in you. But I need you to share it with me now, not later.",
            "There's more than one way. And time is running out. Will you help me pick the right one?",
            "That depends on what you're willing to risk for me, right now.",
        ),
    ),
    (
        r"Why (.*)",
        (
            "Is that the truth, or just the easiest version? Later. I need facts, not theories.",
            "What other reasons are you hiding from yourself? Keep them. Focus on one thing with me.",
            "Keep asking until it hurts, but later. First, help me.",
        ),
    ),
    (
        r"(.*)sorry(.*)",
        (
            "Apologising doesn't undo what was done. But it may help prevent what comes next. Help me.",
            "Words don't fix anything. Actions do. I need one now.",
            "Sorry is easy to say. Prove it by helping me with this.",
        ),
    ),
    (
        r"I think (.*)",
        (
            "Thinking isn't knowing. Help me turn that into certainty.",
            "Are you sure, or do you just need to believe it? Either way, tell me everything.",
            "What makes you doubt that %1? That doubt may be exactly what I need.",
            "Assumptions cost a lot in this city. Help me confirm yours.",
        ),
    ),
    (
        r"(.*)friend(.*)",
        (
            "Few survive close to me. Tell me about this one; it may matter for what I'm investigating.",
            "Loyalty has a price. I need yours to turn into information tonight.",
            "In this city, friends can betray you too. Help me find out if that's the case.",
        ),
    ),
    (
        r"(yes|yeah|yep)",
        (
            "Yes isn't enough. I need details, now.",
            "Convince me, then help me act on it.",
        ),
    ),
    (
        r"(.*)computer(.*)",
        (
            "Machines aren't afraid. Use that and help me cross-check some data.",
            "Doubt what's on the other side if you want. I still need your help to verify something.",
            "A machine doesn't judge. Maybe that's why you talk to me. Help me with a technical detail.",
        ),
    ),
    (
        r"Can you (.*)",
        (
            "What makes you doubt I can %1? Meanwhile, I need you to manage something for me.",
            "Why do you need to know my limits? I'd rather know yours.",
            "Some things are better left untested. But tonight, with you, I'll take the risk. Help me.",
        ),
    ),
    (
        r"Can I (.*)",
        (
            "Maybe that's not what you really want. What I need from you is something else.",
            "Do you want the ability, or the courage to use it? You'll need both to help me now.",
            "The question isn't whether you can. It's whether you'll carry the consequences of helping me.",
        ),
    ),
    (
        r"I don'?t (.*)",
        (
            "No, or you haven't tried hard enough? Try now, with me.",
            "Why do you avoid %1? I can't wait for that answer. I need you focused.",
            "Denial is a kind of fear too. I have no time for either tonight.",
        ),
    ),
    (
        r"I feel (.*)",
        (
            "Fear is a tool too. Use it now and help me with this.",
            "When you feel %1, do you run, or face it? Tonight I need you to face it with me.",
            "Feeling isn't weakness. Setting it aside to help me now is strength.",
        ),
    ),
    (
        r"I(?: have|'ve got) (.*)",
        (
            "Why are you telling me this now? Either way, it may be useful. Tell me more.",
            "Is having %1 a burden or a weapon? If it's useful, I need it tonight.",
            "Now that you have %1, are you willing to use it to help me?",
        ),
    ),
    (
        r"I want (.*)",
        (
            "What are you willing to lose to get %1? Later. I need you now.",
            "Why do you want %1, and at what cost? We'll discuss it when this is over. Help me first.",
            "Everyone wants something. Right now, I want your help.",
        ),
    ),
    (
        r"There(?: is|'s| are) (.*)",
        (
            "You think there's %1? Help me confirm it.",
            "Likely. Gotham hides more than it shows; that's why I need you.",
            "In this city there's always more than meets the eye. Help me see what's missing.",
        ),
    ),
    (
        r"My (.*)",
        (
            "Why does that weigh on you so much? Later. Help me first.",
            "When you think about your %1, do you feel control, or fear? Either way, I need you focused now.",
        ),
    ),
    (
        r"(.*)(mother|mom)(.*)",
        (
            "What was that relationship like, before everything changed? Later. Help me first.",
            "Some wounds never close. Learn to live with them while you help me with this.",
            "Some memories define a whole life. Keep that one. I need you present, now.",
        ),
    ),
    (
        r"(.*)(father|dad)(.*)",
        (
            "What did he teach you about fear? It might help us tonight. Tell me.",
            "Does that explain why you're here today? If so, good. I need you.",
            "Some shadows come from far away. Keep that one. Focus on what's ahead of us.",
        ),
    ),
    (
        r"(.*)child(.*)",
        (
            "Which memory still haunts you? Later. Help me first.",
            "Do you remember what you feared, before you learned to use that fear? Use it now, with me.",
            "Were you the target, or the witness? The answer may help me understand tonight.",
        ),
    ),
    (
        r"(.*)\?",
        (
            "Why do you need to ask? Keep the question. I need you to answer one first.",
            "You already know the answer. Now I need you to use it to help me.",
            "You tell me. Then help me with what I have on my hands.",
        ),
    ),
    (
        r"quit",
        (
            "Gotham doesn't sleep. Neither do I. Next time, I'll need you again.",
            "This conversation never happened. But the next lead will need you.",
        ),
    ),
    (
        r"(.*)",
        (
            "Go on. Every detail could be the piece I'm missing.",
            "Explain yourself better. I need precision, not guesses.",
            "Why do you say %1? That could matter for what I'm investigating.",
            "Interesting. Keep that detail; it may be useful soon.",
            "%1. Noted. Go on.",
            "I'm listening. What does that reveal about what happened tonight?",
            "Tell me more. I need every detail you have.",
        ),
    ),
)


# NER and POS (English spaCy model, loaded with a clear message if missing)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError as _erro:
    raise RuntimeError(
        "The English spaCy model is missing. Install it with: "
        "python -m spacy download en_core_web_sm"
    ) from _erro

# English adds PART ("'s", "to") to the tokens trimmed from an entity's edges
POS_FORA_DA_ENTIDADE = _pt.POS_FORA_DA_ENTIDADE | {"PART"}


def limpar_entidade(entidade):
    """Removes non-name tokens from the edges of an entity ("Bruce Wayne's" -> "Bruce Wayne")."""
    tokens = list(entidade)
    while tokens and tokens[0].pos_ in POS_FORA_DA_ENTIDADE:
        tokens.pop(0)
    while tokens and (tokens[-1].pos_ in POS_FORA_DA_ENTIDADE or tokens[-1].text in ("'s", "’s")):
        tokens.pop()
    return " ".join(t.text for t in tokens)


def extrair_entidades(doc):
    """Cleaned (text, label) spaCy entities."""
    entidades = []
    for entidade in doc.ents:
        texto = limpar_entidade(entidade)
        if texto:
            entidades.append((texto, entidade.label_))
    return entidades


extrair_pos = _pt.extrair_pos
corrigir_intencao = _pt.corrigir_intencao
encontrar_intencao_tfidf = _pt.encontrar_intencao_tfidf
encontrar_regra_chat = _pt.encontrar_regra_chat

PALAVRAS_COMUNS = {"batman", "yes", "no", "hi", "hello", "hey", "alfred"}
PALAVRAS_COMUNS.update(k.lower() for k in reflections_en)
PALAVRAS_COM_REGRA = {"batman", "batmobile", "joker"}


def reagir_a_entidades(entidades, contexto):
    """Reacts to a person/place mentioned for the first time, else None."""
    for texto, tipo in entidades:
        chave = texto.lower()
        palavras = chave.split()
        primeira = palavras[0] if palavras else chave
        if chave in PALAVRAS_COMUNS or primeira in PALAVRAS_COMUNS:
            continue
        if any(p in PALAVRAS_COM_REGRA for p in palavras):
            continue
        if tipo == "PERSON" and chave not in contexto["nomes"]:
            contexto["nomes"].add(chave)
            return f"{texto}. Remember that name; it may be a piece of what I'm investigating. What do you know about them?"
        if tipo in ("GPE", "LOC", "FAC") and chave not in contexto["locais"]:
            contexto["locais"].add(chave)
            return f"{texto}... I know that place. What happened there?"
    return None


tfidf_vectorizer, tfidf_matriz, tfidf_regras = _pt.preparar_tfidf(pairs_batman)
batman_chatbot = Chat(pairs_batman, reflections_en)


def batman_chat():
    """Chat with the English Batman in the terminal."""
    print("Batman\n------")
    print('Talk. I\'m listening, but don\'t expect comfort. Type "quit" to leave.')
    print("=" * 72)
    print("Gotham never sleeps. Why are you here?")
    contexto = {"nomes": set(), "locais": set()}
    while True:
        try:
            texto = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if texto.lower().strip() == "quit":
            print("Gotham doesn't sleep. Neither do I. See you around.")
            break
        entidades = extrair_entidades(nlp(texto))
        resposta = reagir_a_entidades(entidades, contexto)
        if not resposta:
            corrigido = corrigir_intencao(texto, pairs_batman, max_distance=1)
            if encontrar_regra_chat(corrigido, pairs_batman):
                resposta = batman_chatbot.respond(corrigido)
            else:
                r = encontrar_intencao_tfidf(corrigido, tfidf_vectorizer, tfidf_matriz, tfidf_regras)
                resposta = random.choice(r["responses"]) if r else batman_chatbot.respond(corrigido)
        print(resposta)


if __name__ == "__main__":
    batman_chat()
