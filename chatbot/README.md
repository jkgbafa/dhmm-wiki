# Ministry Wiki Chatbot

Chat with all three wikis — Bishop Dag's 6,730 messages + 133 books, and the Marriage Wiki (Adelaide, Joshua, First Love Conversations). Answers cite their sources with links (timestamped where available). UI built with [prompt-kit](https://www.prompt-kit.com/).

## Run it

```bash
cd chatbot
npm install
python3 ../pipeline/build_corpus.py   # builds corpus.db if missing (~2 min)
npm run build && npm start            # http://localhost:3000
```

## Choose the AI (set in `.env.local`, see `.env.local.example`)

| Option | Cost | Setup |
|---|---|---|
| **Ollama (local)** | Free, offline | `ollama pull llama3.2`, then `OPENAI_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=llama3.2` |
| **Groq free tier** | Free (rate-limited) | Key from console.groq.com → `OPENAI_API_KEY=gsk_...` (default base URL/model already point at Groq) |
| **Anthropic (paid)** | ~cents/chat | `OPENAI_BASE_URL=https://api.anthropic.com/v1`, `OPENAI_API_KEY=sk-ant-...`, `LLM_MODEL=claude-sonnet-5` |

Any OpenAI-compatible endpoint works — it's just those three env vars.

## Share it as one link

On the machine running it (Mac or NAS):

```bash
brew install cloudflared        # or the NAS package
cloudflared tunnel --url http://localhost:3000
```

That prints a free public `https://…trycloudflare.com` URL anyone can open and chat with. For a permanent address on your own domain, create a named tunnel in the Cloudflare dashboard (still free).

## How answers stay honest

The system prompt enforces the Marriage Wiki SCHEMA rules: evidence-only answers, per-speaker attribution (never merging Dag/Adelaide/Joshua into one voice), source links on every claim, and "the corpus doesn't cover this" instead of invented positions.

## Updating knowledge

After new transcripts or wiki pages land: `python3 ../pipeline/build_corpus.py` and restart. 215k+ chunks, SQLite FTS5 (free, no embedding service); swap in vectors later without touching the UI.
