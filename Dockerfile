# Batman & Alfred chatbot: ready for Docker and Hugging Face Spaces (Docker SDK).
#
#   docker build -t batman-chatbot .
#   docker run -p 7860:7860 -e LLM_PROVIDER=groq -e GROQ_API_KEY=... batman-chatbot
#   -> http://localhost:7860
#
# Models and the vector DB are prepared at build time, so the container starts ready.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hugging Face Spaces runs the container as user 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    NLTK_DATA=/home/user/nltk_data \
    PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

# CPU-only PyTorch first (the default wheel bundles CUDA and is several GB larger)
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt \
 && python -m spacy download pt_core_news_sm \
 && python -m spacy download en_core_web_sm

COPY --chown=user . .
USER user

# Download the embedding/router models and build the Chroma DBs (PT from the bundled PDFs, EN downloaded)
RUN python scripts/preparar.py

ENV HOST=0.0.0.0 \
    PORT=7860 \
    TRUST_PROXY=1 \
    LLM_PROVIDER=groq

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')" || exit 1

CMD ["python", "webapp/server.py"]
