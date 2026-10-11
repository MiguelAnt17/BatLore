# Deploying a public demo on Hugging Face Spaces

Hugging Face Spaces can run the Docker image for free (CPU basic: 2 vCPU, 16 GB RAM). The free CPU tier can't run Ollama at a usable speed, so the demo uses a hosted LLM (Groq has a free tier).

1. Create a Space at <https://huggingface.co/new-space>, SDK **Docker**, template **Blank**.
2. Push this repository to the Space (it is a git repo):

   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space-name>
   git push space main
   ```

3. Spaces reads its settings from YAML at the top of `README.md`. Add this block **as the first lines of the README in the Space** (you can keep it out of the GitHub README):

   ```yaml
   ---
   title: Batcomputer
   emoji: 🦇
   colorFrom: gray
   colorTo: yellow
   sdk: docker
   app_port: 7860
   pinned: false
   ---
   ```

4. In the Space **Settings → Variables and secrets**, add:
   - secret `GROQ_API_KEY` (or `OPENROUTER_API_KEY` / `HUGGINGFACEHUB_API_TOKEN`)
   - variable `LLM_PROVIDER` = `groq` (the Dockerfile default) or `openrouter` / `huggingface`
   - optional: `LLM_MODEL`, `RATE_LIMIT_PER_MIN` (default 20)

The first build takes a while (PyTorch, models and the vector DB are prepared during the build). After that the Space starts in under a minute.

## Notes for public deployments

- **Cost/abuse:** every Alfred answer is one or more LLM calls on your key. Keep `RATE_LIMIT_PER_MIN` low and set a spending limit with your provider.
- **One question at a time:** answers are serialised by a lock. That's fine for a demo; for many users, run several replicas.
- **`ler_pagina`** only reads public internet addresses (private, loopback and cloud-metadata IPs are refused).
- **Bruce's agenda** is shared memory in the MCP server process: everyone sees the same agenda until the server restarts.
- Conversations live in memory and expire after 2 hours of inactivity.
