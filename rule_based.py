"""Batman rule-based agent (script of D1_RuleAgent.ipynb).

    python3 rule_based.py [eliza | vs [turnos]]
"""

# Batman: reflexões e regras
import nltk
from nltk.chat.util import Chat, reflections
from nltk.metrics import edit_distance
import spacy


# Reflexões
reflexoes_pt = {
    # Pronomes
    "eu": "tu",
    "tu": "eu",
    "mim": "ti",
    "ti": "mim",
    "me": "te",
    "te": "me",
    "comigo": "contigo",
    "contigo": "comigo",
    "nós": "vocês",
    "nos": "vos",

    # Possessivos
    "meu": "teu",
    "teu": "meu",
    "minha": "tua",
    "tua": "minha",
    "meus": "teus",
    "teus": "meus",
    "minhas": "tuas",
    "tuas": "minhas",
    "nosso": "vosso",
    "nossa": "vossa",

    # Verbos Principais (Presente)
    "sou": "és",
    "és": "sou",
    "estou": "estás",
    "estás": "estou",
    "tenho": "tens",
    "tens": "tenho",
    "vou": "vais",
    "vais": "vou",
    "quero": "queres",
    "queres": "quero",
    "posso": "podes",
    "podes": "posso",
    "sei": "sabes",
    "sabes": "sei",
    "faço": "fazes",
    "fazes": "faço",
    "conheces": "conheço",

    # Verbos
    "sinto": "sentes",
    "sentes": "sinto",
    "acho": "achas",
    "achas": "acho",
    "consigo": "consegues",
    "consegues": "consigo",
    "preciso": "precisas",
    "precisas": "preciso",
    "gosto": "gostas",
    "gostas": "gosto",

    # Verbos no Passado
    "fui": "foste",
    "foste": "fui",
    "estive": "estiveste",
    "estiveste": "estive",
    "tive": "tiveste",
    "tiveste": "tive",
    "quis": "quiseste",
    "quiseste": "quis",
    "fiz": "fizeste",
    "fizeste": "fiz"
}


# (regex, respostas) do Batman
pairs_batman = (
    (
        r"(.*)batm[oó]vel(.*)",
        (
            "O Batmóvel não é um brinquedo. É blindagem, velocidade e um laboratório que me diz o que a rua esconde.",
            "Deixei-o a dois quarteirões daqui, nas sombras. Chega a qualquer ponto de Gotham antes de qualquer patrulha.",
            "Já lhe tirei pólvora e tinta do chassis esta noite. Diz-me onde estiveste e eu digo-te o que ele encontrou.",
            "Toda a gente quer ver o Batmóvel. Poucos percebem que é só uma ferramenta. O trabalho faz-se com informação, e essa tens tu.",
            "O motor dele ouve-se a três ruas de distância. Se o ouviste esta noite, preciso que me digas a que horas.",
        ),
    ),
    (
        r"(.*)joker(.*)",
        (
            "O Joker não quer dinheiro nem poder. Quer ver-nos partidos ao meio. É isso que o torna diferente de todos os outros.",
            "Se o Joker anda nisto, nada do que viste vai fazer sentido. É esse o plano dele. Conta-me tudo, mesmo o que te pareça absurdo.",
            "Já o levei a Arkham vezes suficientes para saber que as grades não o seguram. O que o segura são as pessoas que falam. Sê uma delas.",
            "Não rias das piadas do Joker. É assim que ele escolhe quem fica para o fim.",
            "O Joker deixa sempre assinatura: uma carta, um sorriso pintado, uma testemunha viva para contar a história. Viste alguma coisa assim?",
        ),
    ),
    (
        r"Eu preciso de (.*)",
        (
            "Todos precisam de alguma coisa. Guarda essa. Tenho uma pista em aberto e faltam-me os teus olhos.",
            "Quem depende de %1 nunca aprende a ficar de pé sozinho. Falamos disso depois. Primeiro, ajuda-me com uma coisa.",
            "Achas que %1 te vai dar aquilo que realmente procuras? Enquanto pensas nisso, diz-me o que sabes sobre o que se passou esta noite.",
            "Todos dizem que precisam de algo, até enfrentarem o que realmente temem. Tenho uma pergunta mais urgente para ti.",
            "Precisar é uma coisa. Estar disposto a pagar o preço é outra. Preciso que pagues o teu com informação.",
        ),
    ),
    (
        r"Porque é que não (.*)",
        (
            "Talvez ainda não estejas pronto para %1. Enquanto isso, preciso da tua ajuda com um assunto mais urgente.",
            "Essa é a pergunta que devias fazer a ti mesmo. Mas agora não é o momento. Tenho uma pista a seguir e o relógio não pára.",
            "Há sempre uma razão. Guarda-a. Preciso que te concentres no que te vou perguntar a seguir.",
            "Talvez não seja falta de capacidade. Isso pode esperar; algo mais grave não pode.",
            "Continua a perguntar-te isso mais tarde. Agora, diz-me o que viste.",
        ),
    ),
    (
        r"Porque é que não posso (.*)",
        (
            "Não é uma questão de poder. É uma questão de vontade e de tempo, que estamos a perder.",
            "Se pudesses %1, estarias preparado para as consequências? Responde depois. Agora preciso de factos.",
            "Os limites que sentes foram impostos por ti mesmo. Deixa isso comigo. Diz-me o que sabes.",
            "Já enfrentaste mesmo esse medo? Vamos falar disso. Mas primeiro, ajuda-me a confirmar uma coisa.",
            "Talvez a pergunta certa seja outra. Guarda-a para depois. Há algo mais urgente a resolver.",
        ),
    ),
    (
        r"Eu não consigo (.*)",
        (
            "Não consegues, ou ainda não caíste vezes suficientes? Isso fica para outra conversa. Preciso de ti agora.",
            "Levanta-te. Há trabalho a fazer e faltam-me mãos em que possa confiar.",
            "Diz-me o que te impede de %1 depois. Primeiro, preciso que me digas o que sabes sobre esta noite.",
            "Todos caem. Poucos se levantam a tempo de ajudar quem precisa. Consegues fazer isso agora?",
            "Não conseguir é temporário. O que se passa lá fora não pode esperar por essa certeza.",
        ),
    ),
    (
        r"Eu sou (.*)",
        (
            "Não é quem és por dentro. É o que fazes que te define; e agora preciso que faças algo por mim.",
            "Há quanto tempo carregas o peso de seres %1? Guarda isso. Tenho uma pista que precisa dos teus olhos.",
            "%1. Uma máscara, ou a verdade? Descobre depois. Agora responde-me a uma coisa.",
            "Ser %1 é uma escolha, ou algo que te foi imposto? Fica para mais tarde. Diz-me o que sabes.",
            "Todos usamos um disfarce. O meu está a ficar sem tempo. Ajudas-me, ou não?",
        ),
    ),
    (
        r"Eu estou (.*)",
        (
            "A noite tem esse efeito nas pessoas. Mesmo assim, preciso que te concentres um momento.",
            "Estar %1 não é fraqueza. É informação; e eu preciso de mais informação agora, não sobre ti.",
            "Porque é que me dizes isto, agora, aqui? Guarda. Há algo mais urgente a tratar.",
            "O que te levou a estares %1? Falamos disso depois. Primeiro, diz-me o que viste esta noite.",
            "Reconhecer isso já é mais do que a maioria consegue fazer. Agora usa essa clareza para me ajudares.",
            "O que fazes normalmente quando te sentes assim? Deixa para depois. Preciso de ti focado.",
        ),
    ),
    (
        r"Tu és (.*)",
        (
            "Sou o que Gotham precisa que eu seja esta noite. E preciso que sejas o que eu preciso agora.",
            "Achas mesmo que sou %1? Não é isso que importa. Ajudas-me com uma coisa?",
            "Estás a falar de mim, ou a olhar para um espelho? De qualquer forma, preciso da tua ajuda agora.",
            "Isso importa menos do que aquilo que decides fazer com o que vês. E preciso que vejas uma coisa por mim.",
        ),
    ),
    (
        r"És (.*)",
        (
            "Não sou uma resposta fácil, e não tenho tempo para dar uma agora. Preciso da tua ajuda.",
            "As etiquetas não significam nada nas sombras. O que significa é se me consegues ajudar com isto.",
            "Talvez sim, talvez não. Isso não muda o que preciso que faças agora.",
            "Cada um vê o que precisa de ver. Eu preciso que vejas isto comigo.",
        ),
    ),
    (
        r"És tu (.*)",
        (
            "Preferias que não fosse? Não é isso que está em jogo agora.",
            "Talvez precises de acreditar que sou %1. Acredita no que quiseres, mas ajuda-me primeiro.",
            "As sombras não têm nome. O que têm é pouco tempo. Preciso de ti.",
            "Se fosse, isso mudava o que vieste aqui fazer? Espero que não.",
        ),
    ),
    (
        r"O que (.*)",
        (
            "Porque é que precisas de saber? Guarda a pergunta. Preciso que me respondas a uma primeiro.",
            "Uma resposta não te vai proteger. Mas talvez me ajude a proteger outros. Colabora comigo.",
            "As respostas fáceis são as primeiras a trair-te. Não tenho tempo para elas. Ajuda-me.",
            "Há coisas que é melhor não saberes. Mas preciso que saibas o suficiente para me ajudares agora.",
            "Isso muda alguma coisa? Talvez. Primeiro, preciso que me ajudes com um detalhe.",
            "Procura tu primeiro. Depois falamos. Agora preciso da tua atenção total.",
            "Nem tudo o que se descobre traz paz. Mas preciso de descobrir isto comigo, agora.",
        ),
    ),
    (
        r"Como (.*)",
        (
            "Como achas? Não é altura para adivinhar. Ajuda-me a confirmar.",
            "A resposta já está dentro de ti. Mas preciso que a partilhes comigo agora, não depois.",
            "O que estás realmente a tentar perguntar? Fica para depois. Preciso de ti concentrado nisto.",
            "Há mais do que uma forma. E o tempo está a esgotar-se. Ajudas-me a escolher a certa?",
            "Descobre-o sozinho, quando isto acabar. Agora, preciso da tua ajuda.",
            "Isso depende do que estás disposto a arriscar por mim, agora mesmo.",
        ),
    ),
    (
        r"Porque (.*)",
        (
            "Essa é a verdade, ou só a versão mais fácil? Fica para depois. Preciso de factos, não de teorias.",
            "Que outras razões escondes de ti mesmo? Guarda-as. Preciso que te concentres numa coisa comigo.",
            "Isso aplica-se a mais alguma coisa na tua vida? Talvez. Mas agora preciso de ti aqui, comigo.",
            "Se %1, o que mais terias de enfrentar? Enfrenta depois. Ajuda-me primeiro.",
        ),
    ),
    (
        r"(.*) desculpa (.*)",
        (
            "Pedir desculpa não desfaz o que foi feito. Mas pode ajudar a evitar o que vem a seguir. Ajuda-me.",
            "O que sentes quando pedes desculpa? Guarda isso. Preciso da tua cabeça no que se segue.",
            "As palavras não reparam nada. As ações, sim. Preciso de uma agora.",
            "Desculpa é fácil de dizer. Prova-o ajudando-me com isto.",
        ),
    ),
    (
        r"Olá Batman(.*)",
        (
            "Chegaste às sombras na hora certa. Preciso da tua ajuda com algo.",
            "Estás aqui. Bom. Tenho um assunto em aberto e faltam-me respostas.",
            "O que te traz a esta hora? Seja o que for, tenho de te pedir algo primeiro.",
            "Poucos vêm até aqui por bom motivo. Espero que o teu sirva para me ajudares.",
        ),
    ),
    (
        r"Eu acho que (.*)",
        (
            "Achar não é o mesmo que saber. Ajuda-me a transformar isso em certeza.",
            "Tens a certeza, ou só precisas de acreditar nisso? De qualquer forma, preciso que me contes tudo.",
            "O que te faz duvidar de %1? Essa dúvida pode ser exatamente o que preciso agora.",
            "As suposições custam caro nesta cidade. Ajuda-me a confirmar a tua.",
            "E se estiveres errado? Vamos descobrir juntos. Preciso da tua ajuda para isso.",
        ),
    ),
    (
        r"(.*) amigo (.*)",
        (
            "Poucos sobrevivem perto de mim. Fala-me desse; pode ser relevante para o que estou a investigar.",
            "A lealdade tem um preço. Preciso que a tua se traduza em informação, esta noite.",
            "Nesta cidade, os amigos também podem trair-te. Ajuda-me a perceber se é esse o caso.",
        ),
    ),
    (
        r"Sim",
        (
            "Sim não basta. Preciso de detalhes, agora.",
            "Convence-me e depois ajuda-me a agir sobre isso.",
        ),
    ),
    (
        r"(.*) computador(.*)",
        (
            "As máquinas não têm medo. Preciso que uses isso a teu favor e me ajudes a cruzar uns dados.",
            "Sente-te à vontade para duvidar do que está do outro lado. Mesmo assim, preciso da tua ajuda a verificar algo.",
            "O que a tecnologia te faz sentir? Fica para depois. Agora, ajuda-me a decifrar isto.",
            "Uma máquina não julga. Talvez seja por isso que falas comigo. Aproveita e ajuda-me com um detalhe técnico.",
        ),
    ),
    (
        r"É (.*)",
        (
            "Achas que é %1? Preciso que confirmes isso comigo, agora.",
            "Se fosse %1, estarias preparado para agir a meu lado?",
            "É possível. A verdade raramente é simples. Ajuda-me a encontrá-la.",
            "Nem tudo o que se parece. Preciso que olhes de novo, comigo.",
            "Podia ser. Mas isso muda o que vais fazer a seguir? Espero que sim.",
        ),
    ),
    (
        r"Isso é (.*)",
        (
            "Pareces convicto. Preciso dessa convicção para me ajudares a confirmar isto.",
            "E se te dissesse que provavelmente não é %1? Ajudas-me a descobrir o que é, então?",
            "A certeza é o primeiro erro que se comete nesta cidade. Ajuda-me a evitá-lo.",
            "Talvez. Ou talvez seja só aquilo que precisas de acreditar. De qualquer forma, preciso da tua ajuda a apurar.",
        ),
    ),
    (
        r"Consegues (.*)",
        (
            "O que te faz duvidar que eu consiga %1? Enquanto isso, preciso que consigas outra coisa por mim.",
            "Se conseguisses %1, o preço valeria a pena? Discutimos isso depois. Preciso de ação agora.",
            "Porque é que precisas de saber os meus limites? Preciso antes de saber os teus.",
            "Há coisas que é melhor não testar. Mas hoje, contigo, vou arriscar. Ajuda-me.",
        ),
    ),
    (
        r"Posso (.*)",
        (
            "Talvez não seja isso que realmente queres. O que preciso que faças é outra coisa.",
            "Queres a capacidade, ou a coragem para a usar? Vais precisar de ambas para me ajudares agora.",
            "A pergunta não é se podes. É se estás disposto a arcar com as consequências de me ajudares.",
        ),
    ),
    (
        r"Tu (.*)",
        (
            "Não estamos aqui para falar de mim. Estamos aqui porque preciso da tua ajuda.",
            "Porque é que precisas de projetar isso em mim? Guarda isso. Ajuda-me primeiro.",
            "Porque é que te interessa tanto o que eu %1? Interessa-te mais o que eu preciso agora de ti.",
            "Muda de assunto. Fala de ti e de como me podes ajudar esta noite.",
        ),
    ),
    (
        r"Eu não (.*)",
        (
            "Não, ou ainda não tentaste o suficiente? Tenta agora, comigo.",
            "Porque é que evitas %1? Não posso esperar por essa resposta. Preciso de ti concentrado.",
            "É isso que queres, no fundo? Fica para depois. Primeiro, ajuda-me.",
            "A negação também é uma forma de medo. Não tenho tempo para nenhum dos dois esta noite.",
        ),
    ),
    (
        r"Eu sinto (.*)",
        (
            "O medo também é uma ferramenta. Usa-o agora e ajuda-me com isto.",
            "Costumas sentir-te %1? Guarda isso. Preciso que te concentres no que se segue.",
            "Quando te sentes %1, foges, ou enfrentas? Hoje, preciso que enfrentes a meu lado.",
            "Sentir não é fraqueza. Ignorar o que sentes para me ajudares agora, é força.",
            "Guarda esse sentimento. Vais precisar dele mais tarde; mas primeiro, preciso de ti aqui.",
        ),
    ),
    (
        r"Eu tenho (.*)",
        (
            "Porque é que me revelas isso agora? Seja como for, pode ser útil. Conta-me mais.",
            "Ter %1 é um fardo, ou uma arma? Se for útil, preciso dela esta noite.",
            "Agora que tens %1, estás disposto a usá-lo para me ajudares?",
            "Tudo o que se tem, pode perder-se numa noite. Usa isso comigo antes que seja tarde.",
        ),
    ),
    (
        r"Eu faria (.*)",
        (
            "As intenções não salvam ninguém. As ações, sim. Preciso de uma agora.",
            "Explica porque farias %1; enquanto isso, ajuda-me com o que tenho em mãos.",
            "Quem mais precisa de saber que farias %1? Eu preciso de saber se o fazes agora.",
        ),
    ),
    (
        r"Há (.*)",
        (
            "Achas que há %1? Preciso que me ajudes a confirmar.",
            "É provável. Gotham esconde mais do que mostra; por isso preciso de ti.",
            "Se houvesse %1, estarias preparado para agir comigo?",
            "Nesta cidade, há sempre mais do que se vê. Ajuda-me a ver o que falta.",
        ),
    ),
    (
        r"O meu (.*)",
        (
            "Porque é que isso pesa tanto sobre ti? Fica para depois. Ajuda-me primeiro.",
            "Quando pensas no teu %1, sentes controlo, ou medo? De qualquer forma, preciso de ti focado agora.",
            "Isso define-te, ou é apenas o que carregas contigo? Não tenho tempo para decidir isso por ti, só para te pedir ajuda.",
        ),
    ),
    (
        r"Porque é que (.*)",
        (
            "Diz-me tu a razão pela qual %1 depois. Agora, preciso que me ajudes com algo mais urgente.",
            "Porque é que achas que %1? Guarda essa reflexão. Preciso de ti aqui, comigo.",
            "Continua a perguntar até doer, mas depois. Primeiro, ajuda-me.",
        ),
    ),
    (
        r"Eu quero (.*)",
        (
            "O que estás disposto a perder para conseguir %1? Fica para depois. Preciso de ti agora.",
            "Porque é que queres %1, e a que custo? Discutimos isso quando isto acabar. Ajuda-me primeiro.",
            "O que farias depois de conseguires %1? Primeiro, ajuda-me a resolver isto.",
            "Se conseguisses %1, isso mudaria quem és? Talvez. Mas agora preciso de quem és hoje.",
            "Todos querem algo. Eu, agora, quero a tua ajuda.",
        ),
    ),
    (
        r"(.*) mãe(.*)",
        (
            "Como era essa relação, antes de tudo mudar? Falamos disso depois. Ajuda-me primeiro.",
            "O que sentes quando pensas nela? Usa isso como força, agora, comigo.",
            "Isso ainda molda as decisões que tomas hoje? Pode ser exatamente o que preciso que me contes.",
            "Algumas feridas nunca fecham. Aprende a viver com elas enquanto me ajudas com isto.",
            "Há memórias que definem uma vida inteira. Guarda essa. Preciso de ti presente, agora.",
        ),
    ),
    (
        r"(.*) pai(.*)",
        (
            "O que é que ele te ensinou sobre o medo? Pode ajudar-nos esta noite. Conta-me.",
            "O que sentes quando pensas nele? Usa isso, agora, comigo.",
            "Isso explica a razão pela qual estás aqui hoje? Se sim, ainda bem. Preciso de ti.",
            "Tens dificuldade em mostrar isso a alguém? Não precisas de mostrar tudo. Só de me ajudares.",
            "Algumas sombras vêm de longe. Guarda essa. Preciso que te concentres no que temos pela frente.",
        ),
    ),
    (
        r"(.*) criança(.*)",
        (
            "Qual é a memória que ainda te assombra? Fica para depois. Ajuda-me primeiro.",
            "Lembras-te do que temias, antes de aprenderes a usar esse medo? Usa-o agora, comigo.",
            "Foste alvo, ou testemunha? A resposta pode ajudar-me a perceber o que se passa esta noite.",
            "O que ficou por resolver desde então? Isso fica para depois. Primeiro, preciso de ti focado.",
        ),
    ),
    (
        r"(.*)\?",
        (
            "Porque é que precisas de perguntar? Guarda a pergunta. Preciso que me respondas a uma primeiro.",
            "A resposta já a sabes. Mas agora preciso que a uses para me ajudares.",
            "Procura dentro de ti depois. Agora, preciso de ti aqui, comigo.",
            "Diz-me tu. E depois ajuda-me com o que tenho em mãos.",
            "Se soubesses a resposta, ajudavas-me a agir sobre ela?",
        ),
    ),
    (
        r"quit",
        (
            "Gotham não dorme. Nem eu. Da próxima vez, vou precisar de ti outra vez.",
            "Vai. Mas o caso continua em aberto, e o medo há de te encontrar outra vez.",
            "Esta conversa nunca aconteceu. Mas a próxima pista vai precisar de ti.",
            "As sombras vão estar aqui quando voltares; e eu também, à espera da tua ajuda.",
        ),
    ),
    (
        r"(.*)",
        (
            "Continua. Cada detalhe pode ser a peça que me falta.",
            "Vamos mudar de assunto por um momento; mas preciso que voltes a isto depois.",
            "Explica-te melhor. Preciso de precisão, não de suposições.",
            "Porque é que dizes que %1? Isso pode ser importante para o que estou a investigar.",
            "Interessante. Guarda esse detalhe, pode ser útil daqui a pouco.",
            "%1. Anotado. Continua.",
            "Estou a ouvir. E o que é que isso revela sobre o que se passou esta noite?",
            "Sentes o peso disso agora? Guarda-o para depois. Primeiro, ajuda-me a terminar isto.",
            "Diz mais. Preciso de todos os detalhes que tiveres.",
        ),
    ),
)


# NER e POS
try:
    nlp = spacy.load("pt_core_news_sm")
except OSError as _erro:
    raise SystemExit(
        "Falta o modelo do spaCy para português. Instala-o com:\n"
        "    python -m spacy download pt_core_news_sm"
    ) from _erro


# POS que não fazem parte de um nome próprio
POS_FORA_DA_ENTIDADE = {
    "VERB", "AUX", "DET", "ADP", "PRON", "SCONJ", "CCONJ", "ADV", "PUNCT",
}


def limpar_entidade(entidade):
    """Removes non-name tokens from the edges of an entity."""
    tokens = list(entidade)

    while tokens and tokens[0].pos_ in POS_FORA_DA_ENTIDADE:
        tokens.pop(0)
    while tokens and tokens[-1].pos_ in POS_FORA_DA_ENTIDADE:
        tokens.pop()

    palavras = []
    for token in tokens:
      palavras.append(token.text)
    return " ".join(palavras)


def extrair_entidades(doc):
    """Cleaned (text, label) spaCy entities."""
    entidades = []
    for entidade in doc.ents:
      texto = limpar_entidade(entidade)
      if not texto:
        continue
      entidades.append((texto, entidade.label_))
    return entidades


def extrair_pos(doc):
    """(text, POS) per token, without punctuation."""
    tokens = []
    for token in doc:
      if not token.is_punct:
        tokens.append((token.text, token.pos_))
    return tokens




PALAVRAS_COMUNS = {"Batman", "sim", "não", "nao"}
PALAVRAS_COMUNS.update(reflexoes_pt, reflexoes_pt.values())

# Palavras com regra própria em pairs_batman
PALAVRAS_COM_REGRA = {"batman", "batmóvel", "batmovel", "joker"}

def reagir_a_entidades(entidades, contexto):
    """Reacts to a person/place mentioned for the first time, else None."""

    for texto, tipo in entidades:
        chave = texto.lower()
        # Skip common words (verbs mislabeled as PROPN)
        palavras = chave.split()

        if palavras:
            primeira_palavra = palavras[0]
        else:
            primeira_palavra = chave

        if chave in PALAVRAS_COMUNS or primeira_palavra in PALAVRAS_COMUNS:
            continue
        # Leave these to the rules
        if any(palavra in PALAVRAS_COM_REGRA for palavra in palavras):
            continue
        if tipo == "PER" and chave not in contexto["nomes"]:
            contexto["nomes"].add(chave)
            return f"{texto}. Guarda esse nome pode ser uma peça no que estou a investigar. O que sabes sobre essa pessoa?"
        if tipo in ("LOC", "GPE") and chave not in contexto["locais"]:
            contexto["locais"].add(chave)
            return f"{texto}... conheço esse lugar. O que aconteceu lá?"
    return None


# Correção (edit distance)
def corrigir_intencao(texto, pairs_batman, max_distance=1):
    """Corrects the start of the text to the closest rule (edit distance)."""
    palavras = texto.split()

    melhor_regra = None
    melhor_distancia = float("inf")
    melhor_num_palavras = 0

    for pattern, responses in pairs_batman:
        if pattern == r"(.*)":
            continue

        if pattern.startswith("(.*)"):
            continue

        padrao = pattern.replace("(.*)", "").strip()

        if not padrao:
            continue

        palavras_padrao = padrao.split()
        numero_palavras = len(palavras_padrao)

        if len(palavras) < numero_palavras:
            continue

        inicio = " ".join(palavras[:numero_palavras])

        distancia = edit_distance(
            inicio.lower(),
            padrao.lower()
        )

        if distancia <= max_distance:

            if (
                distancia < melhor_distancia
                or (
                    distancia == melhor_distancia
                    and numero_palavras > melhor_num_palavras
                )
            ):

                # Skip short prefixes
                if distancia > 0 and len(inicio) <= 2:
                    continue

                melhor_regra = padrao
                melhor_distancia = distancia
                melhor_num_palavras = numero_palavras

    if melhor_regra is None:
        return texto

    resto = " ".join(palavras[melhor_num_palavras:])

    if resto:
        return melhor_regra + " " + resto

    return melhor_regra


# TF-IDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import random
import re

def preparar_tfidf(pairs):
    """Fits TF-IDF on the rule patterns (without (.*))."""
    textos = []
    regras = []

    for pattern, responses in pairs:
        # Skip fallback
        if pattern == r"(.*)":
            continue

        # Skip rules starting with (.*)
        if pattern.startswith("(.*)"):
            continue

        padrao = pattern.replace("(.*)", "").strip()

        if not padrao:
            continue

        textos.append(padrao)
        regras.append((padrao, responses))

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2)
    )

    matriz = vectorizer.fit_transform(textos)

    return vectorizer, matriz, regras

def encontrar_intencao_tfidf(texto, vectorizer, matriz, regras, threshold=0.35):
    """Most similar rule, or None below the threshold."""
    vetor = vectorizer.transform([texto])

    similaridades = cosine_similarity(vetor, matriz)[0]

    indice = similaridades.argmax()

    melhor_similaridade = similaridades[indice]

    if melhor_similaridade < threshold:
        return None

    padrao, responses = regras[indice]

    return {
        "padrao": padrao,
        "responses": responses,
        "similaridade": melhor_similaridade
    }


tfidf_vectorizer, tfidf_matriz, tfidf_regras = preparar_tfidf(pairs_batman)


def encontrar_regra_chat(texto, pairs):
    """True if a rule other than (.*) matches."""

    for pattern, responses in pairs:

        if pattern == r"(.*)":
            continue

        try:
            if re.match(pattern, texto, re.IGNORECASE):
                return True
        except re.error:
            continue

    return False


# Batman Chatbot
batman_chatbot = Chat(pairs_batman, reflexoes_pt)

def batman_chat(verbose=False):
    """Chat with Batman in the terminal."""
    print("Batman")
    print("------")
    print("Fala. Estou a ouvir, mas não esperes conforto.")
    print('Escreve "quit" quando quiseres sair.')
    print("=" * 72)
    print("Gotham nunca dorme. Porque é que estás aqui?")

    contexto = {"nomes": set(), "locais": set()}

    while True:
        texto = input("> ")

        if texto.lower().strip() == "quit":
            print("Gotham não dorme. Nem eu. Vejo-te por aí.")
            break

        if texto.lower().strip() == "debug":
            verbose = not verbose
            if verbose:
              estado = "ligado"
            else:
              estado = "desligado"
            print(f"[Modo debug (NER/POS): {estado}]")
            continue

        # NER + POS
        doc = nlp(texto)
        entidades = extrair_entidades(doc)
        pos_tags = extrair_pos(doc)

        if verbose:
            if entidades:
                print(f"[NER: {entidades}]")
            print(f"[POS: {pos_tags}]")

        # Entities
        resposta_especial = reagir_a_entidades(entidades, contexto)
        if resposta_especial:
            print(resposta_especial)
            continue

        # Edit Distance Correction
        texto_corrigido = corrigir_intencao(texto, pairs_batman, max_distance=1)

        if texto != texto_corrigido:
            print("[Correção:", texto_corrigido + "]")

        # 1. Rules
        if encontrar_regra_chat(texto_corrigido, pairs_batman):
            resposta = batman_chatbot.respond(texto_corrigido)
            print(resposta)
            continue
        # 2. TF-IDF
        resultado_tfidf = encontrar_intencao_tfidf(
            texto_corrigido, tfidf_vectorizer, tfidf_matriz, tfidf_regras, threshold=0.35
        )
        if resultado_tfidf:
            if verbose:
                print(f"[TF-IDF: {resultado_tfidf['padrao']} | similaridade: {resultado_tfidf['similaridade']:.2f}]")

            resposta = random.choice(resultado_tfidf["responses"])
            print(resposta)
            continue
        # 3. Fallback
        resposta = batman_chatbot.respond(texto_corrigido)
        print(resposta)

def demo_batman():
    batman_chat()


# ELIZA Chatbot
# Natural Language Toolkit: Eliza
#
# Copyright (C) 2001-2026 NLTK Project
# Authors: Steven Bird <stevenbird1@gmail.com>
#          Edward Loper <edloper@gmail.com>
# URL: <https://www.nltk.org/>
# For license information, see LICENSE.TXT

# Baseado numa implementação do Eliza por Joe Strout <joe@strout.net>,
# Jeff Epler <jepler@inetnebr.com> e Jez Higgins <mailto:jez@jezuk.co.uk>.
# Traduzido para Português Europeu.

from nltk.chat.util import Chat, reflections

# (regex, respostas); %1, %2 = grupos capturados

pairs_elisa = (
    (
        r"Preciso de (.*)",
        (
            "Porque precisas de %1?",
            "Seria realmente uma ajuda conseguires %1?",
            "Tens a certeza de que precisas de %1?",
        ),
    ),
    (
        r"Porque não (.*)",
        (
            "Achas mesmo que eu não %1?",
            "Talvez um dia eu venha a %1.",
            "Queres mesmo que eu %1?",
        ),
    ),
    (
        r"Porque não consigo (.*)",
        (
            "Achas que deverias ser capaz de %1?",
            "Se pudesses %1, o que farias?",
            "Não sei -- porque é que não consegues %1?",
            "Já tentaste a sério?",
        ),
    ),
    (
        r"Não consigo (.*)",
        (
            "Como sabes que não consegues %1?",
            "Talvez conseguisses %1 se tentasses.",
            "O que seria preciso para conseguires %1?",
        ),
    ),
    (
        r"Eu sou (.*)",
        (
            "Vieste ter comigo por seres %1?",
            "Há quanto tempo és %1?",
            "Como te sentes por ser %1?",
        ),
    ),
    (
        r"Eu estou (.*)",
        (
            "Como é que estar %1 te faz sentir?",
            "Gostas de estar %1?",
            "Porque me dizes que estás %1?",
            "Porque achas que estás %1?",
        ),
    ),
    (
        r"És (.*)",
        (
            "Porque importa se sou %1?",
            "Preferias que eu não fosse %1?",
            "Talvez acredites que sou %1.",
            "Posso ser %1 -- o que achas?",
        ),
    ),
    (
        r"O que (.*)",
        (
            "Porque perguntas?",
            "Como é que a resposta a isso te ajudaria?",
            "O que achas?",
        ),
    ),
    (
        r"Como (.*)",
        (
            "O que supões?",
            "Talvez possas responder à tua própria pergunta.",
            "O que estás realmente a perguntar?",
        ),
    ),
    (
        r"Porque (.*)",
        (
            "É essa a verdadeira razão?",
            "Que outras razões te vêm à cabeça?",
            "Essa razão aplica-se a mais alguma coisa?",
            "Se %1, o que mais tem de ser verdade?",
        ),
    ),
    (
        r"(.*) desculpa (.*)",
        (
            "Muitas vezes não é preciso pedir desculpa.",
            "Que sentimentos tens quando pedes desculpa?",
        ),
    ),
    (
        r"Olá Batman(.*)",
        (
            "Olá... Ainda bem que vieste hoje.",
            "Olá... como estás hoje?",
            "Olá, como te sentes hoje?",
        ),
    ),
    (
        r"Eu acho que (.*)",
        (
            "Duvidas que %1?",
            "Achas mesmo que sim?",
            "Mas não tens a certeza que %1?",
        ),
    ),
    (
        r"(.*) amig[oa](.*)",
        (
            "Fala-me mais dos teus amigos.",
            "Quando pensas num amigo, o que te vem à cabeça?",
            "Porque não me falas de um amigo de infância?",
        ),
    ),
    (r"Sim", ("Pareces ter muita certeza.", "OK, mas podes elaborar um pouco?")),
    (
        r"(.*) computador(.*)",
        (
            "Estás mesmo a falar de mim?",
            "Parece-te estranho falar com um computador?",
            "Como é que os computadores te fazem sentir?",
            "Sentes-te ameaçado por computadores?",
        ),
    ),
    (
        r"Será que (.*)",
        (
            "Achas que %1?",
            "Talvez %1 -- o que achas?",
            "Se %1, o que farias?",
            "Pode muito bem ser que %1.",
        ),
    ),
    (
        r"Isso é (.*)",
        (
            "Pareces ter muita certeza.",
            "Se eu te dissesse que provavelmente não é %1, como te sentirias?",
        ),
    ),
    (
        r"Consegues (.*)",
        (
            "O que te faz pensar que não consigo %1?",
            "Se eu conseguisse %1, e depois?",
            "Porque perguntas se consigo %1?",
        ),
    ),
    (
        r"Posso (.*)",
        (
            "Talvez não queiras %1.",
            "Queres ser capaz de %1?",
            "Se pudesses %1, fá-lo-ias?",
        ),
    ),
    (
        r"Tu és (.*)",
        (
            "Porque achas que sou %1?",
            "Agrada-te pensar que sou %1?",
            "Talvez gostasses que eu fosse %1.",
            "Talvez estejas na verdade a falar de ti próprio?",
        ),
    ),
    (
        r"Estás (.*)",
        (
            "Porque dizes que estou %1?",
            "Porque achas que estou %1?",
            "Estamos a falar de ti ou de mim?",
        ),
    ),
    (
        r"Eu não (.*)",
        ("Não %1 mesmo?", "Porque não %1?", "Queres %1?"),
    ),
    (
        r"Sinto-me (.*)",
        (
            "Bem, fala-me mais sobre esses sentimentos.",
            "Costumas sentir-te %1 muitas vezes?",
            "Quando te costumas sentir %1?",
            "Quando te sentes %1, o que fazes?",
        ),
    ),
    (
        r"Eu tenho (.*)",
        (
            "Porque me dizes que tens %1?",
            "Tens mesmo %1?",
            "Agora que tens %1, o que vais fazer a seguir?",
        ),
    ),
    (
        r"Gostaria de (.*)",
        (
            "Podes explicar porque gostarias de %1?",
            "Porque gostarias de %1?",
            "Quem mais sabe que gostarias de %1?",
        ),
    ),
    (
        r"Existe (.*)",
        (
            "Achas que existe %1?",
            "É provável que exista %1.",
            "Gostavas que existisse %1?",
        ),
    ),
    (
        r"O meu (.*)|A minha (.*)",
        (
            "Estou a ver, o teu %1%2.",
            "Porque dizes isso sobre o teu %1%2?",
            "Quando pensas no teu %1%2, como te sentes?",
        ),
    ),
    (
        r"Tu (.*)",
        (
            "Devíamos estar a discutir sobre ti, não sobre mim.",
            "Porque dizes isso sobre mim?",
            "Porque te importas se eu %1?",
        ),
    ),
    (
        r"Por que (.*)",
        ("Porque não me dizes a razão pela qual %1?", "Porque achas que %1?"),
    ),
    (
        r"Quero (.*)",
        (
            "O que significaria para ti se conseguisses %1?",
            "Porque queres %1?",
            "O que farias se conseguisses %1?",
            "Se conseguisses %1, o que farias depois?",
        ),
    ),
    (
        r"(.*) mãe(.*)",
        (
            "Fala-me mais sobre a tua mãe.",
            "Como era a tua relação com a tua mãe?",
            "Como te sentes em relação à tua mãe?",
            "Como é que isso se relaciona com o que sentes hoje?",
            "As boas relações familiares são importantes.",
        ),
    ),
    (
        r"(.*) pai(.*)",
        (
            "Fala-me mais sobre o teu pai.",
            "Como é que o teu pai te fazia sentir?",
            "Como te sentes em relação ao teu pai?",
            "A tua relação com o teu pai relaciona-se com os sentimentos que tens hoje?",
            "Tens dificuldade em demonstrar afeto à tua família?",
        ),
    ),
    (
        r"(.*) criança(.*)",
        (
            "Tinhas amigos próximos quando eras criança?",
            "Qual é a tua memória favorita de infância?",
            "Lembras-te de algum sonho ou pesadelo da infância?",
            "As outras crianças costumavam meter-se contigo?",
            "Como achas que as tuas experiências de infância se relacionam com o que sentes hoje?",
        ),
    ),
    (
        r"(.*)\?",
        (
            "Porque perguntas isso?",
            "Por favor, considera se consegues responder à tua própria pergunta.",
            "Talvez a resposta esteja dentro de ti próprio?",
            "Porque não me dizes tu?",
        ),
    ),
    (
        r"sair",
        (
            "Obrigado por teres falado comigo.",
            "Adeus.",
            "Obrigado, são 150€. Tem um bom dia!",
        ),
    ),
    (
        r"(.*)",
        (
            "Por favor, conta-me mais.",
            "Vamos mudar de assunto um pouco... Fala-me sobre a tua família.",
            "Podes elaborar um pouco mais sobre isso?",
            "Porque dizes que %1?",
            "Estou a ver.",
            "Muito interessante.",
            "%1.",
            "Estou a ver. E o que é que isso te diz?",
            "Como é que isso te faz sentir?",
            "Como te sentes quando dizes isso?",
        ),
    ),
)

eliza_chatbot = Chat(pairs_elisa, reflexoes_pt)


def eliza_chat():
    print("Terapeuta\n---------")
    print("Fala com o programa escrevendo em Português simples, usando letras")
    print('maiúsculas e minúsculas normais e pontuação. Escreve "sair" quando terminares.')
    print("=" * 72)
    print("Olá. Como te sentes hoje?")

    eliza_chatbot.converse()


def demo_eliza():
    eliza_chat()


# Conversation between ELIZA and Batman
import time


def batman_vs_elisa(turnos=20, mensagem_inicial="Olá"):
    """Batman and ELIZA talk to each other."""
    print(30 * "=")
    print("A inciar conversa entre Batman e Eliza")
    print(30 * "=")

    mensagem_atual = mensagem_inicial
    print(f"User (Mensagem Inicial): {mensagem_atual}\n")

    for i in range(turnos):
        print(f"--- Turno {i+1} ---")
        msg_corrigida = corrigir_intencao(mensagem_atual, pairs_batman, max_distance=1)

        resposta_batman = batman_chatbot.respond(msg_corrigida)
        if not resposta_batman:
            resposta_batman = "Não sei o que dizer."

        print(f"Batman: {resposta_batman}")
        time.sleep(1.5)

        resposta_elisa = eliza_chatbot.respond(resposta_batman)
        if not resposta_elisa:
            resposta_elisa = "Please, tell me more."

        print(f"ELIZA: {resposta_elisa}\n")
        time.sleep(1.5)

        mensagem_atual = resposta_elisa


if __name__ == "__main__":
    import sys

    modo = sys.argv[1] if len(sys.argv) > 1 else "batman"

    if modo == "eliza":
        demo_eliza()
    elif modo == "vs":
        turnos = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        batman_vs_elisa(turnos=turnos, mensagem_inicial="Olá, como estás?")
    else:
        demo_batman()
