"""Sistemas Internos da Batcaverna (Veículos, Meteorologia tática e Agenda)."""

import random
from mcp_servidor import mcp

# Lista de locais para simular dados
DISTRITOS_GOTHAM = ["The Bowery", "Crime Alley", "Diamond District", "Otisburg", "The Narrows", "Bristol", "Burnside"]

# Limites da agenda (a webapp pode ser pública: a memória não pode crescer sem fim)
MAX_TEXTO_COMPROMISSO = 200
MAX_COMPROMISSOS_DIA = 20
MAX_DIAS = 30

# Estado em memória para a agenda (reinicia quando o servidor MCP é reiniciado)
AGENDA_BRUCE = {
    "hoje": [
        "10:00 - Reunião do Conselho da Wayne Enterprises",
        "20:00 - Gala de Angariação de Fundos no Museu de Arte"
    ],
    "amanhã": [
        "12:30 - Almoço com o Mayor",
        "15:00 - Inspeção técnica aos laboratórios de I&D"
    ]
}

@mcp.tool()
def estado_batmovel(veiculo: str = "Batmóvel") -> dict:
    """
    Verifica o estado atual, nível de danos, energia e localização de um veículo (ex: Batmóvel, Batwing).
    """
    return {
        "veiculo": veiculo,
        "blindagem": f"{random.randint(40, 100)}%",
        "energia_combustivel": f"{random.randint(15, 100)}%",
        "estado": random.choice([
            "Em patrulha furtiva", 
            "Estacionado e oculto", 
            "Em perseguição a alta velocidade", 
            "Necessita de reparações menores",
            "Pronto a intervir na Batcaverna"
        ]),
        "localizacao": random.choice(DISTRITOS_GOTHAM)
    }

@mcp.tool()
def clima_gotham(distrito: str = "Gotham City") -> dict:
    """
    Verifica as condições meteorológicas e ambientais num distrito de Gotham.
    """
    if distrito.lower() in ["aleatorio", "qualquer", "gotham", "gotham city"]:
        distrito = random.choice(DISTRITOS_GOTHAM)

    return {
        "distrito": distrito,
        "temperatura": f"{random.randint(0, 12)}ºC",
        "condicao_atmosferica": random.choice(["Chuva intensa", "Nevoeiro denso", "Trovoada", "Chuva miúda", "Céu muito nublado"]),
        "visibilidade": random.choice(["Fraca", "Muito fraca", "Quase nula", "Moderada"]),
        "anomalias_quimicas_no_ar": random.choice([
            "Nenhuma detetada", 
            "Ligeiros vestígios de Smog industrial", 
            "Alerta: Níveis anómalos de toxinas detetados", 
            "Poluição padrão de Gotham"
        ])
    }

@mcp.tool()
def gerir_agenda_bruce(acao: str, data: str = "hoje", compromisso: str = "") -> dict:
    """
    Lê ou adiciona compromissos à agenda pública do Bruce Wayne.
    - acao: "ler" ou "escrever"
    - data: "hoje", "amanhã" (ou outra data qualquer)
    - compromisso: O texto do compromisso (obrigatório apenas se acao for "escrever")
    """
    data_key = data.lower().strip()
    
    if acao.lower() == "ler":
        return {
            "data": data_key, 
            "compromissos": AGENDA_BRUCE.get(data_key, ["Nenhum compromisso agendado para esta data."])
        }
        
    elif acao.lower() == "escrever":
        compromisso = compromisso.strip()[:MAX_TEXTO_COMPROMISSO]
        data_key = data_key[:40]
        if not compromisso:
            return {"erro": "Para escrever, tens de fornecer o argumento 'compromisso'."}

        if data_key not in AGENDA_BRUCE:
            if len(AGENDA_BRUCE) >= MAX_DIAS:
                return {"erro": "A agenda está cheia. Escolhe uma data que já exista."}
            AGENDA_BRUCE[data_key] = []

        if len(AGENDA_BRUCE[data_key]) >= MAX_COMPROMISSOS_DIA:
            return {"erro": f"Já há {MAX_COMPROMISSOS_DIA} compromissos para {data_key}."}

        AGENDA_BRUCE[data_key].append(compromisso)
        return {
            "sucesso": True, 
            "mensagem": f"Compromisso '{compromisso}' adicionado a {data_key}.", 
            "agenda_atualizada": AGENDA_BRUCE[data_key]
        }
        
    else:
        return {"erro": "Ação inválida. Usa 'ler' ou 'escrever'."}