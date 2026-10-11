/* Batcomputador: cliente do agente híbrido (GET /api/status, POST /api/start, POST /api/say) */
"use strict";

// ---------------------------------------------------------------------------
// Textos da interface (PT / EN). Batman e Alfred respondem sempre em PT-PT.
// ---------------------------------------------------------------------------

const TEXTOS = {
  pt: {
    marca: "Batcomputador",
    subtitulo: "Batman (regras) · Alfred (RAG + MCP)",
    nova_conversa: "Nova conversa",
    debug_titulo: "Modo debug: mostra o router, NER, POS e TF-IDF",
    info_titulo: "Informação",
    fechar: "Fechar",
    enviar: "Enviar",
    a_tua_mensagem: "A tua mensagem",
    placeholder: "Escreve uma mensagem…",
    dica_teclas: "Enter para enviar · Shift+Enter para nova linha",
    aviso_idioma: "",
    na_linha: "Na linha",
    papel_batman: "Detetive · agente de regras",
    papel_alfred: "Mordomo · LLM com ferramentas",
    desc_batman: "Agente de regras (ELIZA + NER + TF-IDF). Diz “Quero falar com o Alfred” para mudar de linha.",
    desc_alfred: "LLM com RAG sobre 18 artigos da Wikipédia e ferramentas MCP (web, sistemas da Batcaverna). Diz “Obrigado, Alfred. É tudo.” para terminar a ligação.",
    modo_alfred: "Modo do Alfred",
    modo_rag: "RAG primeiro",
    modo_rag_desc: "Consulta sempre os arquivos; usa a web e os sistemas só se precisar.",
    modo_livre: "Livre (agêntico)",
    modo_livre_desc: "O LLM decide todas as ferramentas, incluindo os arquivos.",
    ferramentas_titulo: "Ferramentas MCP do Alfred",
    f_arquivos: "18 artigos da Wikipédia (RAG híbrido)",
    f_web: "Pesquisa na web (DuckDuckGo)",
    f_pagina: "Lê o texto de uma página",
    f_sistemas: "Sistemas da Batcaverna (simulados)",
    f_batman: "Pede a opinião ao Batman",
    sobre_titulo: "Sobre",
    sobre_texto: "Projeto académico de Interação em Linguagem Natural (Mestrado em IA, Universidade de Coimbra). Um <em>router</em> de embeddings decide quem responde: o Batman de regras ou o Alfred com LLM.",
    estado_ligar: "A ligar…",
    estado_pronto: "Online",
    estado_batman: "O Batman está a pensar…",
    estado_alfred: "O Alfred está a consultar o Batcomputador…",
    estado_erro: "Sem ligação",
    estado_fim: "Conversa terminada",
    voce: "Tu",
    via_regra: "regra",
    via_tfidf: "tf-idf",
    via_entidade: "entidade",
    via_fallback: "fallback",
    via_mcp: "batcomputador",
    via_rag: "arquivos",
    via_llm: "llm",
    via_alfred: "fim de ligação",
    troca_alfred: "Ligação estabelecida · Batcaverna / Alfred",
    troca_batman: "Ligação cortada · De volta ao Batman",
    fim_conversa: "Fim da conversa · carrega em “Nova conversa”",
    ferramentas_usadas: "Ferramentas",
    automatica: "auto",
    detalhes: "Detalhes técnicos",
    passos: (n, s) => `${n} chamada(s) MCP · ${s}s`,
    limite: "limite de chamadas atingido",
    corrigido: "interpretado como",
    tentar: "Tentar outra vez",
    erro_rede: "Não consegui falar com o servidor. Está a correr?",
    erro_sessao: "A conversa expirou. Começa uma nova.",
    erro_rate_limit: "Demasiadas mensagens seguidas. Espera um minuto.",
    erro_llm_offline: null, // usa a mensagem do servidor
    sem_ferramentas: "nenhuma",
    analise: "Análise",
  },
  en: {
    marca: "Batcomputer",
    subtitulo: "Batman (rules) · Alfred (RAG + MCP)",
    nova_conversa: "New chat",
    debug_titulo: "Debug mode: shows the router, NER, POS and TF-IDF",
    info_titulo: "Info",
    fechar: "Close",
    enviar: "Send",
    a_tua_mensagem: "Your message",
    placeholder: "Write a message…",
    dica_teclas: "Enter to send · Shift+Enter for a new line",
    aviso_idioma: "",
    aviso_so_pt: "English isn't available in this server mode: Batman and Alfred will answer in Portuguese.",
    na_linha: "On the line",
    papel_batman: "Detective · rule-based agent",
    papel_alfred: "Butler · LLM with tools",
    desc_batman: "Rule-based agent (ELIZA + NER + TF-IDF). Say “I want to talk to Alfred” to switch lines.",
    desc_alfred: "LLM with RAG over 18 English Wikipedia articles and MCP tools (web, Batcave systems). Say “Thanks, Alfred. That's all.” to end the call.",
    modo_alfred: "Alfred's mode",
    modo_rag: "RAG first",
    modo_rag_desc: "Always searches the archives; uses the web and systems only when needed.",
    modo_livre: "Free (agentic)",
    modo_livre_desc: "The LLM decides every tool call, archives included.",
    ferramentas_titulo: "Alfred's MCP tools",
    f_arquivos: "18 Wikipedia articles (hybrid RAG)",
    f_web: "Web search (DuckDuckGo)",
    f_pagina: "Reads the text of a web page",
    f_sistemas: "Batcave systems (simulated)",
    f_batman: "Asks Batman for his take",
    sobre_titulo: "About",
    sobre_texto: "Academic project for the Natural Language Interaction course (MSc in AI, University of Coimbra). An embedding <em>router</em> decides who answers: rule-based Batman or LLM-powered Alfred.",
    estado_ligar: "Connecting…",
    estado_pronto: "Online",
    estado_batman: "Batman is thinking…",
    estado_alfred: "Alfred is querying the Batcomputer…",
    estado_erro: "Offline",
    estado_fim: "Chat ended",
    voce: "You",
    via_regra: "rule",
    via_tfidf: "tf-idf",
    via_entidade: "entity",
    via_fallback: "fallback",
    via_mcp: "batcomputer",
    via_rag: "archives",
    via_llm: "llm",
    via_alfred: "call ended",
    troca_alfred: "Line open · Batcave / Alfred",
    troca_batman: "Line closed · Back to Batman",
    fim_conversa: "Chat ended · press “New chat”",
    ferramentas_usadas: "Tools",
    automatica: "auto",
    detalhes: "Technical details",
    passos: (n, s) => `${n} MCP call(s) · ${s}s`,
    limite: "call limit reached",
    corrigido: "read as",
    tentar: "Try again",
    erro_rede: "Could not reach the server. Is it running?",
    erro_sessao: "This chat expired. Start a new one.",
    erro_rate_limit: "Too many messages. Wait a minute.",
    erro_llm_offline: "Could not reach the LLM provider (is Ollama running? is the API reachable?).",
    erro_llm_config: "The LLM is not configured (missing or invalid API key). Check the .env file.",
    erro_llm_rate_limit: "The LLM provider is rate-limiting requests. Wait a bit and try again.",
    erro_timeout: "Alfred took too long to answer. Try again.",
    erro_interno: "Something went wrong in the Batcomputer. Try again.",
    erro_modelo_en: "The English spaCy model is missing on the server: python -m spacy download en_core_web_sm",
    sem_ferramentas: "none",
    analise: "Analysis",
  },
};

// Sugestões por idioma. "troca" = muda de linha (estilo tracejado).
const SUGESTOES = {
  pt: {
    batman: [
      { texto: "Quero falar com o Alfred", troca: true },
      { texto: "O que sabes sobre o Joker?" },
      { texto: "Onde está o Batmóvel?" },
      { texto: "Eu preciso de ajuda" },
    ],
    alfred: [
      { texto: "Quem matou os pais do Bruce Wayne?" },
      { texto: "Quando estreia o próximo filme do Batman?" },
      { texto: "Qual é o estado do Batmóvel?" },
      { texto: "O que tem o Bruce na agenda hoje?" },
      { texto: "Quem é a Hera Venenosa?" },
      { texto: "Obrigado, Alfred. É tudo.", troca: true },
    ],
  },
  en: {
    batman: [
      { texto: "I want to talk to Alfred", troca: true },
      { texto: "What do you know about the Joker?" },
      { texto: "Where is the Batmobile?" },
      { texto: "I need help" },
    ],
    alfred: [
      { texto: "Who killed Bruce Wayne's parents?" },
      { texto: "When does the next Batman movie come out?" },
      { texto: "What's the status of the Batmobile?" },
      { texto: "What's on Bruce's schedule today?" },
      { texto: "Who is Poison Ivy?" },
      { texto: "Thanks, Alfred. That's all.", troca: true },
    ],
  },
};

const AGENTES = {
  batman: { nome: "Batman", img: "/static/img/batman.webp" },
  alfred: { nome: "Alfred", img: "/static/img/alfred.webp" },
};

// ---------------------------------------------------------------------------
// Elementos e estado
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);
const el = {
  mensagens: $("mensagens"),
  sugestoes: $("sugestoes"),
  avisoIdioma: $("aviso-idioma"),
  form: $("composer"),
  input: $("mensagem"),
  contador: $("contador"),
  enviar: $("btn-enviar"),
  nova: $("btn-nova"),
  debug: $("btn-debug"),
  info: $("btn-info"),
  fecharPainel: $("btn-fechar-painel"),
  painel: $("painel"),
  veu: $("veu"),
  estado: $("estado"),
  estadoTexto: $("estado-texto"),
  llmInfo: $("llm-info"),
  linhaAtiva: document.querySelector(".linha-ativa"),
  miniImg: $("mini-img"),
  miniNome: $("mini-nome"),
  miniPapel: $("mini-papel"),
  retratoImg: $("retrato-img"),
  retratoNome: $("retrato-nome"),
  retratoDesc: $("retrato-desc"),
  cartaoModo: $("cartao-modo"),
};

const estado = {
  sessaoId: null,
  ocupado: false,
  terminada: false,
  agente: "batman",
  idioma: "pt",
  debug: false,
  limite: 500,
  ultimoTexto: null,
  idiomasBot: ["pt", "en"],  // idiomas da conversa que o servidor suporta (/api/status)
  temporizador: null,
};

const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// localStorage pode não existir (modo privado, iframes): falha em silêncio.
const guardado = {
  ler(chave) { try { return localStorage.getItem(chave); } catch (_) { return null; } },
  escrever(chave, valor) { try { localStorage.setItem(chave, valor); } catch (_) { /* ignora */ } },
};

const t = (chave) => {
  const valor = TEXTOS[estado.idioma][chave];
  return valor === undefined ? TEXTOS.pt[chave] : valor;
};

// ---------------------------------------------------------------------------
// Idioma
// ---------------------------------------------------------------------------

// O idioma muda a interface E a conversa (Batman de regras, Alfred, arquivos do RAG),
// por isso mudar de idioma começa uma conversa nova.
function mudarIdioma(idioma) {
  if (idioma === estado.idioma || estado.ocupado) return;
  aplicarIdioma(idioma);
  novaConversa();
}

function aplicarIdioma(idioma) {
  estado.idioma = TEXTOS[idioma] ? idioma : "pt";
  document.documentElement.lang = estado.idioma;
  document.title = t("marca");
  guardado.escrever("idioma", estado.idioma);

  document.querySelectorAll("[data-lang]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.lang === estado.idioma)));
  document.querySelectorAll("[data-i18n]").forEach((n) => {
    const v = t(n.dataset.i18n);
    if (typeof v === "string") n.textContent = v;
  });
  // só textos fixos da tabela acima (nunca conteúdo do servidor)
  document.querySelectorAll("[data-i18n-html]").forEach((n) => { n.innerHTML = t(n.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });

  const soPt = estado.idioma !== "pt" && !estado.idiomasBot.includes(estado.idioma);
  el.avisoIdioma.textContent = soPt ? t("aviso_so_pt") : "";
  el.avisoIdioma.hidden = !soPt;
  atualizarAgente(estado.agente, false);
  if (!estado.ocupado) definirEstado(estado.sessaoId ? (estado.terminada ? "fim" : "pronto") : "ligar");
}

// ---------------------------------------------------------------------------
// Utilitários de interface
// ---------------------------------------------------------------------------

function criar(tag, classe, texto) {
  const n = document.createElement(tag);
  if (classe) n.className = classe;
  if (texto !== undefined && texto !== null) n.textContent = texto;
  return n;
}

function horaAgora() {
  return new Date().toLocaleTimeString(estado.idioma === "en" ? "en-GB" : "pt-PT", { hour: "2-digit", minute: "2-digit" });
}

function paraOFundo() {
  el.mensagens.scrollTop = el.mensagens.scrollHeight;
}

function definirEstado(tipo) {
  const mapa = {
    ligar: ["", "estado_ligar"],
    pronto: ["ativo", "estado_pronto"],
    pensar: ["ocupado", estado.agente === "alfred" ? "estado_alfred" : "estado_batman"],
    erro: ["erro", "estado_erro"],
    fim: ["", "estado_fim"],
  };
  const [classe, chave] = mapa[tipo] || mapa.pronto;
  el.estado.className = "estado " + classe;
  el.estadoTexto.textContent = t(chave);
  el.estado.dataset.tipo = tipo;
}

function bloquear(sim) {
  estado.ocupado = sim;
  el.input.disabled = sim || estado.terminada;
  el.enviar.disabled = sim || estado.terminada || !el.input.value.trim();
  el.nova.disabled = sim;
  el.sugestoes.querySelectorAll("button").forEach((b) => { b.disabled = sim || estado.terminada; });
}

function atualizarContador() {
  const n = el.input.value.length;
  el.contador.textContent = n > estado.limite * 0.7 ? `${n}/${estado.limite}` : "";
  el.contador.classList.toggle("perto", n > estado.limite * 0.9);
  el.enviar.disabled = estado.ocupado || estado.terminada || !el.input.value.trim();
}

function ajustarAltura() {
  el.input.style.height = "auto";
  el.input.style.height = Math.min(el.input.scrollHeight, 160) + "px";
}

// ---------------------------------------------------------------------------
// Markdown mínimo e seguro: escapa TUDO e só depois cria as etiquetas permitidas.
// ---------------------------------------------------------------------------

function escapar(texto) {
  return texto.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function markdownLinha(texto) {
  let s = escapar(texto);
  const codigos = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codigos.push(c); return `\u0000${codigos.length - 1}\u0000`; });
  // [texto](https://...)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, txt, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${txt}</a>`);
  // URLs soltos (fora de atributos já criados)
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,;:!?])/g,
    (_, antes, url) => `${antes}<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  s = s.replace(/(^|[\s(])_([^_\s][^_]*)_(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
  s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codigos[Number(i)]}</code>`);
  return s;
}

function markdown(texto) {
  const linhas = texto.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let lista = null;
  let paragrafo = [];

  const fecharParagrafo = () => {
    if (paragrafo.length) html.push(`<p>${paragrafo.map(markdownLinha).join("<br>")}</p>`);
    paragrafo = [];
  };
  const fecharLista = () => {
    if (lista) html.push(`</${lista}>`);
    lista = null;
  };

  for (const linha of linhas) {
    const item = linha.match(/^\s*([-*•]|\d+[.)])\s+(.*)$/);
    const titulo = linha.match(/^\s*#{1,6}\s+(.*)$/);
    if (item) {
      fecharParagrafo();
      const tipo = /\d/.test(item[1]) ? "ol" : "ul";
      if (lista !== tipo) { fecharLista(); html.push(`<${tipo}>`); lista = tipo; }
      html.push(`<li>${markdownLinha(item[2])}</li>`);
    } else if (titulo) {
      fecharParagrafo(); fecharLista();
      html.push(`<p><strong>${markdownLinha(titulo[1])}</strong></p>`);
    } else if (!linha.trim()) {
      fecharParagrafo(); fecharLista();
    } else {
      fecharLista();
      paragrafo.push(linha);
    }
  }
  fecharParagrafo(); fecharLista();
  return html.join("");
}

// ---------------------------------------------------------------------------
// Mensagens
// ---------------------------------------------------------------------------

function mensagemUtilizador(texto) {
  const msg = criar("div", "msg msg-utilizador");
  const corpo = criar("div", "corpo-msg");
  corpo.appendChild(criar("div", "bolha", texto));
  msg.appendChild(corpo);
  el.mensagens.appendChild(msg);
  paraOFundo();
  return corpo;
}

function mensagemAgente(quem, via) {
  const a = AGENTES[quem];
  const msg = criar("div", `msg msg-${quem}`);
  const avatar = criar("div", "avatar");
  const img = criar("img");
  img.src = a.img;
  img.alt = "";
  avatar.appendChild(img);

  const corpo = criar("div", "corpo-msg");
  const cab = criar("div", "cabecalho-msg");
  cab.appendChild(criar("strong", null, a.nome));
  if (via) cab.appendChild(criar("span", "via", via));
  const hora = criar("time", null, horaAgora());
  cab.appendChild(hora);

  const bolha = criar("div", "bolha");
  corpo.append(cab, bolha);
  msg.append(avatar, corpo);
  el.mensagens.appendChild(msg);
  paraOFundo();
  return { msg, corpo, bolha };
}

/* Mostra a resposta palavra a palavra (rápido) e no fim aplica o markdown. */
async function escrever(bolha, texto) {
  if (reduzirMovimento || !texto) {
    bolha.innerHTML = markdown(texto || "");
    return;
  }
  const palavras = texto.split(/(\s+)/);
  const passo = Math.max(1, Math.ceil(palavras.length / 90)); // ~1,5 s no máximo
  let saltar = false;
  const aoClicar = () => { saltar = true; };
  bolha.addEventListener("click", aoClicar, { once: true });
  bolha.classList.add("a-escrever");
  for (let i = 0; i < palavras.length && !saltar; i += passo) {
    bolha.textContent = palavras.slice(0, i + passo).join("");
    paraOFundo();
    await new Promise((r) => setTimeout(r, 16));
  }
  bolha.removeEventListener("click", aoClicar);
  bolha.classList.remove("a-escrever");
  bolha.innerHTML = markdown(texto);
  paraOFundo();
}

function divisor(texto, classe) {
  el.mensagens.appendChild(criar("div", "sistema " + (classe || ""), texto));
  paraOFundo();
}

function indicador(quem) {
  const { msg, bolha } = mensagemAgente(quem);
  msg.classList.add("indicador");
  msg.querySelector("time").remove();
  const pontos = criar("span", "pontos");
  pontos.append(criar("i"), criar("i"), criar("i"));
  const texto = criar("span", null, t(quem === "alfred" ? "estado_alfred" : "estado_batman"));
  const tempo = criar("span", "tempo");
  bolha.append(pontos, texto, tempo);

  const inicio = Date.now();
  estado.temporizador = setInterval(() => {
    const s = Math.floor((Date.now() - inicio) / 1000);
    tempo.textContent = s >= 3 ? `${s}s` : "";
  }, 500);
  return {
    remover() {
      clearInterval(estado.temporizador);
      msg.remove();
    },
  };
}

function mensagemErro(texto, repetir) {
  const { msg, corpo, bolha } = mensagemAgente(estado.agente);
  msg.classList.add("msg-erro");
  bolha.textContent = texto;
  if (repetir) {
    const b = criar("button", "botao tentar", t("tentar"));
    b.type = "button";
    b.addEventListener("click", () => {
      msg.remove();
      repetir();
    });
    corpo.appendChild(b);
  }
  paraOFundo();
}

// ---------- extras: ferramentas, fontes e detalhes ----------

const ICONE_LINK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const ICONE_ARQUIVO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6zM14 3v4h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>';

function adicionarExtras(corpo, dados) {
  const extras = criar("div", "extras");
  const passos = (dados.ferramentas || []).filter((p) => p.ferramenta !== "relevancia");

  if (passos.length) {
    const chips = criar("div", "chips");
    chips.setAttribute("aria-label", t("ferramentas_usadas"));
    passos.forEach((p) => {
      const chip = criar("span", "chip-ferramenta" + (p.ok ? "" : " falhou"), p.ferramenta);
      if (p.origem === "codigo") chip.appendChild(criar("span", "auto", "· " + t("automatica")));
      chip.title = `${p.segundos}s`;
      chips.appendChild(chip);
    });
    extras.appendChild(chips);
  }

  if (dados.fontes && dados.fontes.length) {
    const fontes = criar("div", "fontes");
    dados.fontes.forEach((f) => {
      let n;
      if (f.url && /^https?:\/\//i.test(f.url)) {
        n = criar("a", "fonte");
        n.href = f.url;
        n.target = "_blank";
        n.rel = "noopener noreferrer";
        n.innerHTML = ICONE_LINK;
        let host = "";
        try { host = new URL(f.url).hostname.replace(/^www\./, ""); } catch (_) { /* ignora */ }
        n.appendChild(document.createTextNode(host || f.titulo));
        n.title = f.titulo || f.url;
      } else {
        n = criar("span", "fonte");
        n.innerHTML = ICONE_ARQUIVO;
        n.appendChild(document.createTextNode(f.titulo));
      }
      fontes.appendChild(n);
    });
    extras.appendChild(fontes);
  }

  const detalhes = construirDetalhes(dados);
  if (detalhes) extras.appendChild(detalhes);
  if (extras.childNodes.length) corpo.appendChild(extras);
}

function construirDetalhes(dados) {
  const linhas = [];
  const fmt = (v) => (typeof v === "number" ? v.toFixed(2) : v);

  if (estado.debug) {
    if (dados.sim_rag != null) linhas.push(["router", `sim(Alfred) = ${fmt(dados.sim_rag)} · limiar ${dados.limiar}`]);
    if (dados.sim_batman != null) linhas.push(["router", `sim(Batman) = ${fmt(dados.sim_batman)} · limiar ${dados.limiar}`]);
    if (dados.relevancia != null) linhas.push(["rag", `relevância = ${fmt(dados.relevancia)} · limiar ${dados.limiar_relevancia}`]);
    if (dados.via) linhas.push(["via", dados.via + (dados.via === "tfidf" && dados.similaridade != null ? ` (${fmt(dados.similaridade)})` : "")]);
    if (dados.entidades && dados.entidades.length) linhas.push(["ner", dados.entidades.map((e) => `${e[0]} (${e[1]})`).join(", ")]);
    if (dados.pos && dados.pos.length) linhas.push(["pos", dados.pos.map((p) => `${p[0]}/${p[1]}`).join(" ")]);
  }

  const passos = dados.ferramentas || [];
  if (!linhas.length && !passos.length) return null;

  const det = criar("details", "detalhes");
  const resumo = passos.length
    ? `${t("detalhes")} · ${t("passos")(passos.length, dados.segundos)}${dados.limite_atingido ? " · " + t("limite") : ""}${dados.modo_agente ? " · " + dados.modo_agente : ""}`
    : t("analise");
  det.appendChild(criar("summary", null, resumo));

  const lista = criar("ul", "traco");
  linhas.forEach(([rotulo, valor]) => {
    const li = criar("li");
    li.append(criar("span", "meta", rotulo.toUpperCase() + "  "), criar("span", null, valor));
    lista.appendChild(li);
  });
  passos.forEach((p, i) => {
    const li = criar("li");
    li.append(
      criar("span", "meta", `${i + 1}. ${p.origem === "codigo" ? "auto" : "LLM"} · `),
      criar("span", "nome-f", p.ferramenta),
      criar("span", p.ok ? "ok" : "falha", p.ok ? "  ok" : "  erro"),
      criar("span", "meta", `  ${p.segundos}s`),
    );
    li.appendChild(criar("div", "args", JSON.stringify(p.argumentos)));
    if (p.resumo) li.appendChild(criar("div", "resumo", "→ " + p.resumo.slice(0, 220) + (p.resumo.length > 220 ? "…" : "")));
    lista.appendChild(li);
  });
  det.appendChild(lista);
  return det;
}

// ---------------------------------------------------------------------------
// Agente ativo e sugestões
// ---------------------------------------------------------------------------

function atualizarAgente(quem, animar = true) {
  const mudou = quem !== estado.agente;
  estado.agente = quem;
  document.body.dataset.agente = quem;
  const a = AGENTES[quem];

  el.miniImg.src = a.img;
  el.retratoImg.src = a.img;
  el.retratoImg.alt = a.nome;
  el.miniNome.textContent = a.nome;
  el.retratoNome.textContent = a.nome;
  el.miniPapel.textContent = t(quem === "alfred" ? "papel_alfred" : "papel_batman");
  el.retratoDesc.textContent = t(quem === "alfred" ? "desc_alfred" : "desc_batman");

  if (mudou && animar && !reduzirMovimento) {
    el.linhaAtiva.classList.remove("trocar");
    void el.linhaAtiva.offsetWidth;
    el.linhaAtiva.classList.add("trocar");
  }
  mostrarSugestoes();
}

function mostrarSugestoes() {
  el.sugestoes.replaceChildren();
  if (estado.terminada) return;
  const idiomaBot = estado.idiomasBot.includes(estado.idioma) ? estado.idioma : "pt";
  SUGESTOES[idiomaBot][estado.agente].forEach((s) => {
    const b = criar("button", "sugestao" + (s.troca ? " troca" : ""), s.texto);
    b.type = "button";
    b.disabled = estado.ocupado;
    b.addEventListener("click", () => enviar(s.texto));
    el.sugestoes.appendChild(b);
  });
}

// ---------------------------------------------------------------------------
// Rede
// ---------------------------------------------------------------------------

class ErroApi extends Error {
  constructor(mensagem, tipo, codigo) {
    super(mensagem);
    this.tipo = tipo;
    this.codigo = codigo;
  }
}

async function pedir(caminho, corpo) {
  let resposta;
  try {
    resposta = await fetch(caminho, {
      method: corpo === undefined ? "GET" : "POST",
      headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch (_) {
    throw new ErroApi(t("erro_rede"), "rede", 0);
  }
  let dados = null;
  try { dados = await resposta.json(); } catch (_) { /* sem JSON */ }
  if (!resposta.ok) {
    const tipo = (dados && dados.tipo) || "http";
    const traduzido = t("erro_" + tipo);
    throw new ErroApi(traduzido || (dados && dados.erro) || `HTTP ${resposta.status}`, tipo, resposta.status);
  }
  return dados;
}

async function carregarEstado() {
  try {
    const s = await pedir("/api/status");
    if (s.llm) {
      el.llmInfo.textContent = `${s.llm.fornecedor} · ${s.llm.modelo}`;
      el.llmInfo.title = "LLM";
      el.llmInfo.hidden = false;
    }
    el.cartaoModo.hidden = !s.mcp;
    if (Array.isArray(s.idiomas)) {
      estado.idiomasBot = s.idiomas;
      aplicarIdioma(estado.idioma);
    }
  } catch (_) { /* o /api/start mostra o erro */ }
}

// ---------------------------------------------------------------------------
// Conversa
// ---------------------------------------------------------------------------

function modoEscolhido() {
  const r = document.querySelector('input[name="modo"]:checked');
  return r ? r.value : undefined;
}

async function novaConversa() {
  el.mensagens.replaceChildren();
  estado.terminada = false;
  estado.sessaoId = null;
  atualizarAgente("batman", false);
  definirEstado("ligar");
  bloquear(true);

  try {
    const inicio = await pedir("/api/start", { idioma: estado.idioma });
    estado.sessaoId = inicio.sessao_id;
    if (inicio.limite_texto) {
      estado.limite = inicio.limite_texto;
      el.input.maxLength = inicio.limite_texto;
    }
    el.cartaoModo.hidden = !inicio.modo_agente;
    if (inicio.modo_agente) {
      const r = document.querySelector(`input[name="modo"][value="${inicio.modo_agente}"]`);
      if (r && !guardado.ler("modo")) r.checked = true;
    }
    const { bolha } = mensagemAgente("batman");
    await escrever(bolha, inicio.saudacao);
    definirEstado("pronto");
    bloquear(false);
    el.input.focus();
  } catch (erro) {
    definirEstado("erro");
    mensagemErro(erro.message, novaConversa);
    el.nova.disabled = false;
  }
}

async function enviar(textoForcado) {
  const texto = (textoForcado !== undefined ? textoForcado : el.input.value).trim();
  if (!texto || estado.ocupado || estado.terminada || !estado.sessaoId) return;

  if (textoForcado === undefined) {
    el.input.value = "";
    ajustarAltura();
    atualizarContador();
  }
  estado.ultimoTexto = texto;
  const corpoUtilizador = mensagemUtilizador(texto);
  await turno(texto, corpoUtilizador);
}

async function turno(texto, corpoUtilizador) {
  bloquear(true);
  definirEstado("pensar");
  const espera = indicador(estado.agente);

  let dados;
  try {
    dados = await pedir("/api/say", { sessao_id: estado.sessaoId, texto, modo_agente: modoEscolhido() });
  } catch (erro) {
    espera.remover();
    if (erro.tipo === "sessao") {
      estado.terminada = true;
      mensagemErro(erro.message, null);
      definirEstado("fim");
      bloquear(false);
      return;
    }
    definirEstado("erro");
    mensagemErro(erro.message, () => turno(texto, corpoUtilizador));
    bloquear(false);
    el.input.disabled = false;
    return;
  }
  espera.remover();

  if (dados.correcao && corpoUtilizador) {
    corpoUtilizador.appendChild(criar("div", "correcao", `${t("corrigido")}: “${dados.correcao}”`));
  }

  if (dados.troca === "rag") divisor(t("troca_alfred"), "para-alfred");
  if (dados.troca === "batman") divisor(t("troca_batman"), "para-batman");

  // O painel segue a linha ativa (modo); a mensagem segue quem respondeu.
  atualizarAgente(dados.modo === "rag" ? "alfred" : "batman");
  const quem = ["rag", "llm", "mcp", "alfred"].includes(dados.agente) ? "alfred" : "batman";
  const viaChave = quem === "alfred" ? "via_" + dados.agente : (dados.via ? "via_" + dados.via : null);
  const { corpo, bolha } = mensagemAgente(quem, viaChave ? t(viaChave) : null);
  await escrever(bolha, dados.resposta || dados.batman || "");
  adicionarExtras(corpo, dados);
  paraOFundo();

  if (dados.fim) {
    estado.terminada = true;
    divisor(t("fim_conversa"));
    definirEstado("fim");
    bloquear(false);
    mostrarSugestoes();
    return;
  }

  definirEstado("pronto");
  bloquear(false);
  if (window.matchMedia("(pointer: fine)").matches) el.input.focus();
}

// ---------------------------------------------------------------------------
// Painel (móvel) e eventos
// ---------------------------------------------------------------------------

function abrirPainel(abrir) {
  el.painel.classList.toggle("aberto", abrir);
  el.veu.hidden = !abrir;
  el.info.setAttribute("aria-expanded", String(abrir));
}

el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  enviar();
});

el.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    enviar();
  }
});

el.input.addEventListener("input", () => {
  ajustarAltura();
  atualizarContador();
});

el.nova.addEventListener("click", novaConversa);

el.debug.addEventListener("click", () => {
  estado.debug = !estado.debug;
  el.debug.setAttribute("aria-pressed", String(estado.debug));
  guardado.escrever("debug", estado.debug ? "1" : "0");
});

document.querySelectorAll("[data-lang]").forEach((b) =>
  b.addEventListener("click", () => mudarIdioma(b.dataset.lang)));

document.querySelectorAll('input[name="modo"]').forEach((r) =>
  r.addEventListener("change", () => guardado.escrever("modo", r.value)));

el.info.addEventListener("click", () => abrirPainel(!el.painel.classList.contains("aberto")));
el.fecharPainel.addEventListener("click", () => abrirPainel(false));
el.veu.addEventListener("click", () => abrirPainel(false));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") abrirPainel(false); });

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

(function arrancar() {
  const idioma = guardado.ler("idioma") || ((navigator.language || "pt").toLowerCase().startsWith("pt") ? "pt" : "en");
  estado.debug = guardado.ler("debug") === "1";
  el.debug.setAttribute("aria-pressed", String(estado.debug));
  const modo = guardado.ler("modo");
  if (modo) {
    const r = document.querySelector(`input[name="modo"][value="${modo}"]`);
    if (r) r.checked = true;
  }
  aplicarIdioma(idioma);
  carregarEstado();
  novaConversa();
})();
