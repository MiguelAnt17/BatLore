"""Servidor web do agente híbrido (Batman + Alfred).

    python webapp/server.py            # http://localhost:8001

Variáveis de ambiente (ver .env.example):
    HOST / PORT            endereço e porta (defeito 127.0.0.1:8001; no Docker 0.0.0.0:7860)
    RATE_LIMIT_PER_MIN     mensagens por minuto e por IP (defeito 20; 0 = sem limite)
    TRUST_PROXY=1          usa o X-Forwarded-For para o IP (atrás de um proxy, ex.: HF Spaces)
    AGENTE_TIMEOUT         segundos máximos por resposta do Alfred (defeito 180)

API (JSON):
    GET  /api/health   -> {"ok": true}
    GET  /api/status   -> fornecedor/modelo do LLM, modo do Alfred, ...
    POST /api/start    -> nova conversa {"idioma"?: "pt"|"en"}: {"sessao_id", "saudacao", "modo_agente", "idioma"}
    POST /api/say      -> um turno: {"sessao_id", "texto", "modo_agente"?}
"""

import json
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETO = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(BASE_DIR, "static")

if PASTA_PROJETO not in sys.path:
    sys.path.insert(0, PASTA_PROJETO)
os.chdir(PASTA_PROJETO)

import agente_hibrido as agente  # noqa: E402
import modelos_llm  # noqa: E402

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8001))
MAX_TEXTO = 500
MAX_CORPO = 8 * 1024                 # bytes por pedido
MAX_SESSOES = 500
TTL_SESSAO = 2 * 60 * 60             # 2 h sem atividade
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
TIMEOUT_AGENTE = float(os.environ.get("AGENTE_TIMEOUT", "180"))
# Arranca o servidor MCP em inglês logo no início (numa thread), para a primeira
# pergunta em inglês não esperar pelo carregamento. PRELOAD_EN=0 só o arranca quando é preciso.
PRELOAD_EN = os.environ.get("PRELOAD_EN", "1") != "0"

# ---------------------------------------------------------------------------
# Estado partilhado
# ---------------------------------------------------------------------------

_sessoes = OrderedDict()             # id -> {"estado": ..., "visto": timestamp}
_lock_sessoes = threading.Lock()

_pedidos_ip = defaultdict(deque)     # ip -> timestamps dos últimos pedidos
_lock_ip = threading.Lock()

_router = None
_agente_rag = None
_lock_rag = threading.Lock()         # o LLM/RAG atende uma pergunta de cada vez


class AgenteRAGPartilhado:
    """AgenteRAG com lock: os passos de cada pergunta não se misturam (nem nos logs),
    e um Ollama local responde a um pedido de cada vez de qualquer forma."""

    def relevancia(self, texto):
        with _lock_rag:
            return _agente_rag.relevancia(texto)

    def responder(self, texto):
        with _lock_rag:
            return _agente_rag.responder(texto)

    def responder_sem_rag(self, texto):
        with _lock_rag:
            return _agente_rag.responder_sem_rag(texto)

    def responder_agente(self, texto, historico, modo=None, idioma="pt"):
        # Liga ao servidor do idioma FORA do lock: se ainda estiver a arrancar (ex.: o
        # inglês na primeira vez), as perguntas em português não ficam à espera.
        _agente_rag.agente_mcp(idioma)
        with _lock_rag:
            return _agente_rag.responder_agente(texto, historico, modo, timeout=TIMEOUT_AGENTE, idioma=idioma)


def _nova_sessao(idioma="pt"):
    sessao_id = uuid.uuid4().hex
    agora = time.time()
    with _lock_sessoes:
        # remove as expiradas e, se ainda houver demasiadas, as mais antigas
        for sid in [s for s, v in _sessoes.items() if agora - v["visto"] > TTL_SESSAO]:
            del _sessoes[sid]
        while len(_sessoes) >= MAX_SESSOES:
            _sessoes.popitem(last=False)
        _sessoes[sessao_id] = {"estado": agente.novo_estado(idioma), "visto": agora}
    return sessao_id


def _obter_sessao(sessao_id):
    with _lock_sessoes:
        sessao = _sessoes.get(sessao_id)
        if sessao is None or time.time() - sessao["visto"] > TTL_SESSAO:
            _sessoes.pop(sessao_id, None)
            return None
        sessao["visto"] = time.time()
        _sessoes.move_to_end(sessao_id)
        return sessao["estado"]


def _dentro_do_limite(ip):
    """Janela deslizante de 60 s por IP."""
    if RATE_LIMIT <= 0:
        return True
    agora = time.time()
    with _lock_ip:
        fila = _pedidos_ip[ip]
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= RATE_LIMIT:
            return False
        fila.append(agora)
        if len(_pedidos_ip) > 10_000:   # não deixa o dicionário crescer sem fim
            for chave in [k for k, v in _pedidos_ip.items() if not v]:
                del _pedidos_ip[chave]
        return True


def _mensagem_erro(erro):
    """Erro técnico -> mensagem curta para a página (o detalhe fica no terminal)."""
    texto = f"{type(erro).__name__}: {erro}"
    baixo = texto.lower()
    if "en_core_web_sm" in texto:
        return "modelo_en", "Falta o modelo do spaCy em inglês: python -m spacy download en_core_web_sm"
    if isinstance(erro, TimeoutError) or "timeout" in baixo or "timed out" in baixo:
        return "timeout", "O Alfred demorou demasiado a responder. Tenta outra vez."
    if "api_key" in baixo or "falta a variável" in baixo or "401" in baixo or "unauthorized" in baixo:
        return "llm_config", "O LLM não está configurado (chave de API em falta ou inválida). Vê o ficheiro .env."
    if "connection" in baixo or "connect" in baixo or "refused" in baixo:
        if modelos_llm.fornecedor() == "ollama":
            return "llm_offline", "Não consegui falar com o Ollama. Está a correr? (ollama serve)"
        return "llm_offline", "Não consegui falar com o fornecedor do LLM. Verifica a ligação."
    if "429" in baixo or "rate limit" in baixo:
        return "llm_rate_limit", "O fornecedor do LLM está a limitar pedidos. Espera um pouco e tenta outra vez."
    return "interno", "Algo correu mal no Batcomputador. Tenta outra vez."


def _fontes(passos):
    """Fontes (artigos e páginas web) usadas pelo Alfred, sem repetidos."""
    vistas, fontes = set(), []
    for passo in passos or []:
        for fonte in passo.get("fontes") or []:
            chave = fonte.get("url") or fonte.get("titulo")
            if chave and chave not in vistas:
                vistas.add(chave)
                fontes.append(fonte)
    return fontes[:8]


TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

CSP = ("default-src 'self'; img-src 'self' data:; "
       "style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
       "script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors *")


class Handler(BaseHTTPRequestHandler):
    server_version = "BatmanHibrido/2.0"
    sys_version = ""

    # ---------- utilitários ----------

    def _cabecalhos_seguranca(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)

    def _responder_json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self._cabecalhos_seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, codigo, tipo, mensagem):
        self._responder_json({"erro": mensagem, "tipo": tipo}, codigo)

    def _ler_json(self):
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if tamanho <= 0:
            return {}
        if tamanho > MAX_CORPO:
            return None
        try:
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return dados if isinstance(dados, dict) else None

    def _ip(self):
        if TRUST_PROXY:
            encaminhado = self.headers.get("X-Forwarded-For", "")
            if encaminhado:
                return encaminhado.split(",")[0].strip()
        return self.client_address[0]

    def _servir_ficheiro(self, caminho_url):
        if caminho_url in ("", "/"):
            caminho_url = "/index.html"
        relativo = caminho_url.lstrip("/")
        if relativo.startswith("static/"):
            relativo = relativo[len("static/"):]

        caminho = os.path.realpath(os.path.join(STATIC_DIR, relativo))
        if not caminho.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(caminho):
            self.send_error(404, "Not found")
            return

        extensao = os.path.splitext(caminho)[1].lower()
        tipo = TIPOS.get(extensao, "application/octet-stream")
        with open(caminho, "rb") as f:
            corpo = f.read()

        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        # imagens podem ficar em cache; HTML/CSS/JS revalidam sempre (mudam com o código)
        self.send_header("Cache-Control", "public, max-age=86400" if tipo.startswith("image/") else "no-cache")
        self._cabecalhos_seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    # ---------- rotas ----------

    def do_GET(self):
        caminho = self.path.split("?", 1)[0]
        if caminho == "/api/health":
            self._responder_json({"ok": True})
        elif caminho == "/api/status":
            self._estado()
        else:
            self._servir_ficheiro(caminho)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        caminho = self.path.split("?", 1)[0]
        if caminho == "/api/start":
            self._iniciar()
        elif caminho == "/api/say":
            self._falar()
        else:
            self.send_error(404, "Not found")

    def _estado(self):
        try:
            llm = modelos_llm.descricao()
        except ValueError:
            llm = None
        self._responder_json({
            "ok": True,
            "mcp": agente.USAR_MCP,
            "modo_agente": _agente_rag.mcp.modo if agente.USAR_MCP else None,
            "llm": llm,
            "idiomas": list(agente.IDIOMAS),
            "limite_texto": MAX_TEXTO,
        })

    def _iniciar(self):
        """Nova conversa + saudação do Batman, no idioma pedido."""
        dados = self._ler_json() or {}
        idioma = agente.idioma_valido(dados.get("idioma"))
        sessao_id = _nova_sessao(idioma)
        self._responder_json({
            "sessao_id": sessao_id,
            "idioma": idioma,
            "saudacao": agente.frase("saudacao", idioma),
            # Modo por defeito do Alfred (para o seletor da página). None sem MCP (modo D2).
            "modo_agente": _agente_rag.mcp.modo if agente.USAR_MCP else None,
            "limite_texto": MAX_TEXTO,
        })

    def _falar(self):
        """Um turno do agente híbrido."""
        dados = self._ler_json()
        if dados is None:
            self._erro(400, "pedido_invalido", "Pedido inválido.")
            return

        estado = _obter_sessao(dados.get("sessao_id"))
        if estado is None:
            self._erro(404, "sessao", "A conversa expirou. Começa uma nova.")
            return

        texto = str(dados.get("texto") or "").strip()[:MAX_TEXTO]
        if not texto:
            self._erro(400, "texto_vazio", "Escreve uma mensagem.")
            return

        if not _dentro_do_limite(self._ip()):
            self._erro(429, "rate_limit", "Demasiadas mensagens seguidas. Espera um minuto.")
            return

        # Modo escolhido no seletor: só os dois valores válidos são aceites.
        modo = dados.get("modo_agente")
        if modo in ("rag_primeiro", "livre"):
            estado["modo_agente"] = modo

        if texto.lower() == "quit":
            with _lock_sessoes:
                _sessoes.pop(dados.get("sessao_id"), None)
            despedida = agente.frase("despedida", estado.get("idioma", "pt"))
            self._responder_json({"fim": True, "agente": "batman", "modo": "batman",
                                  "resposta": despedida, "batman": despedida})
            return

        try:
            resultado = agente.turno_hibrido(texto, estado, _router, AgenteRAGPartilhado())
        except Exception as erro:  # ex.: Ollama desligado, chave em falta, timeout
            tipo, mensagem = _mensagem_erro(erro)
            print(f"[Erro no turno] {type(erro).__name__}: {erro}", file=sys.stderr)
            self._erro(503 if tipo != "interno" else 500, tipo, mensagem)
            return

        self._responder_json({
            "fim": False,
            "resposta": resultado["resposta"],
            "batman": resultado["resposta"],          # nome antigo, mantido por compatibilidade
            "agente": resultado["agente"],
            "troca": resultado["troca"],
            "limiar": resultado["limiar"],
            "sim_rag": resultado["sim_rag"],
            "sim_batman": resultado["sim_batman"],
            "relevancia": resultado["relevancia"],
            "limiar_relevancia": agente.LIMIAR_RELEVANCIA,
            "modo": resultado["modo"],
            "correcao": resultado.get("correcao"),
            "entidades": resultado.get("entidades"),
            "pos": resultado.get("pos"),
            "especial": resultado.get("via") == "entidade",
            "via": resultado.get("via"),
            "similaridade": resultado.get("similaridade"),
            # D3: chamadas MCP do Alfred neste turno e as fontes que trouxeram
            "ferramentas": resultado.get("ferramentas"),
            "fontes": _fontes(resultado.get("ferramentas")),
            "limite_atingido": resultado.get("limite_atingido"),
            "segundos": resultado.get("segundos"),
            "modo_agente": resultado.get("modo_agente"),
        })

    def log_message(self, formato, *args):  # só regista a API
        if self.path.startswith("/api/") and not self.path.startswith("/api/health"):
            super().log_message(formato, *args)


def main():
    global _router, _agente_rag
    llm = modelos_llm.descricao()
    print(f"LLM: {llm['fornecedor']} / {llm['modelo']}")
    _router = agente.RouterAgentes()
    _agente_rag = agente.AgenteRAG()
    if PRELOAD_EN and "en" in agente.IDIOMAS:
        def _preparar_en():
            try:
                _agente_rag.preparar_idioma("en")
                print("[EN] Servidor MCP em inglês pronto.", flush=True)
            except BaseException as erro:  # ex.: falta o modelo en_core_web_sm
                print(f"[EN] Não foi possível preparar o inglês: {erro}", file=sys.stderr, flush=True)
        threading.Thread(target=_preparar_en, daemon=True, name="preparar-en").start()

    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    servidor.daemon_threads = True
    endereco = "localhost" if HOST in ("127.0.0.1", "0.0.0.0") else HOST
    print("=" * 60)
    modo = "regras + agente MCP" if agente.USAR_MCP else "regras + RAG"
    print(f" Batman ({modo})  --  http://{endereco}:{PORT}")
    print(" Ctrl+C para parar")
    print("=" * 60, flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAté à próxima.")
    finally:
        servidor.server_close()
        if _agente_rag is not None and _agente_rag.mcp is not None:
            _agente_rag.mcp.fechar()


if __name__ == "__main__":
    main()
