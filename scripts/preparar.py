"""Preparação única: descarrega os modelos e constrói a Vector DB.

    python scripts/preparar.py

Faz de uma vez o que, de outra forma, acontece na primeira pergunta:
  1. stopwords do NLTK (BM25);
  2. modelo de embeddings do RAG e encoder do router (Hugging Face);
  3. PDFs em falta (Wikipédia PT e EN) e as Vector DB Chroma em rag/iln_batman/
     e rag/iln_batman_en/.

    python scripts/preparar.py --so-pt     # só o português

Usado também no Dockerfile, para a imagem arrancar já pronta.
"""

import os
import sys

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA_PROJETO)
sys.path.insert(0, os.path.join(PASTA_PROJETO, "rag"))

import rag_system as rag  # noqa: E402


def main():
    idiomas = ["pt"] if "--so-pt" in sys.argv else ["pt", "en"]

    print("[1/4] Stopwords do NLTK...")
    for idioma in idiomas:
        rag.carregar_stopwords(idioma)

    print("[2/4] Modelos de embeddings (RAG e router)...")
    rag.obter_embeddings()
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(os.environ.get(
        "ROUTER_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"))

    print("[3/4] Modelos do spaCy...")
    import spacy
    modelos = {"pt": "pt_core_news_sm", "en": "en_core_web_sm"}
    for idioma in idiomas:
        try:
            spacy.load(modelos[idioma])
        except OSError:
            sys.exit(f"Falta o modelo do spaCy: python -m spacy download {modelos[idioma]}")

    print("[4/4] Documentos e Vector DB...")
    for idioma in idiomas:
        db = rag.obter_vector_db_idioma(idioma)
        print(f"  {idioma}: {db._collection.count()} excertos na Vector DB.")
    print("Pronto.")


if __name__ == "__main__":
    main()
