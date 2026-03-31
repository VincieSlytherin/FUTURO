# Ollama + Qwen 2.5 Setup Guide

Futuro supports running entirely on local models via Ollama. This means no API costs, full privacy — your conversations never leave your machine — and offline operation.

---

## Why Qwen 2.5

Qwen 2.5 (千问 2.5) by Alibaba is the best open-weight model family for a bilingual Chinese/English assistant at the sizes that run on consumer hardware. It outperforms Llama 3 and Mistral on reasoning benchmarks at equivalent sizes, has strong instruction following, and handles both languages natively without switching modes.

| Model         | RAM required | Speed (M2 Pro) | Best for |
|---------------|-------------|-----------------|---------|
| qwen2.5:7b    | 4 GB        | ~50 tok/s       | Daily use, fast replies, classification |
| qwen2.5:14b   | 9 GB        | ~25 tok/s       | Coaching, story building, BQ practice |
| qwen2.5:32b   | 20 GB       | ~10 tok/s       | Complex reasoning, job scoring, strategy review |
| qwen2.5:72b   | 45 GB       | ~3 tok/s        | Maximum quality (requires A100-class GPU) |

For most users with a modern MacBook: **qwen2.5:14b** is the sweet spot.

---

## Step 1 — Install Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Verify
ollama --version
```

Ollama runs as a background service and exposes a REST API at `http://localhost:11434`.

---

## Step 2 — Pull models

### Chat model (pick one)

```bash
# Recommended for most machines
ollama pull qwen2.5:14b

# Faster / less RAM
ollama pull qwen2.5:7b

# Maximum quality (needs 20 GB RAM)
ollama pull qwen2.5:32b
```

### Embedding model (pick one)

```bash
# Recommended — small, fast, excellent quality
ollama pull nomic-embed-text

# Better retrieval quality, 2.5x larger
ollama pull mxbai-embed-large

# Reuse the chat model (no extra pull, lower quality)
# Just set OLLAMA_EMBED_MODEL=qwen2.5:14b
```

---

## Step 3 — Configure Futuro

Edit your `.env`:

```bash
# Provider routing
LLM_PROVIDER=auto          # auto-detects Ollama; falls back to Claude if unavailable
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=180.0       # 32b needs more time on CPU; reduce for 7b
OLLAMA_KEEP_ALIVE=10m      # keep model in VRAM between requests
```

Then restart:

```bash
make dev
```

---

## Step 4 — Verify

The `/api/health` endpoint now shows active providers:

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "ok",
  "providers": {
    "chat":     { "provider": "ollama", "model": "qwen2.5:14b" },
    "classify": { "provider": "ollama", "model": "qwen2.5:14b" },
    "score":    { "provider": "ollama", "model": "qwen2.5:14b" },
    "embed":    { "provider": "ollama", "model": "nomic-embed-text" }
  }
}
```

Or visit **Settings** in the Futuro UI — the provider status panel shows live health for each provider.

---

## Provider routing in depth

Futuro routes different workloads to different providers independently. The full config:

```bash
# Master switch: "claude" | "ollama" | "auto"
# auto = use Ollama if reachable, else Claude
LLM_PROVIDER=auto

# Per-task overrides (optional)
CHAT_PROVIDER=ollama        # main conversation
CLASSIFY_PROVIDER=ollama    # intent classification (very cheap — any model)
SCORE_PROVIDER=claude       # job scoring (structured JSON — Claude is more reliable)
EMBED_PROVIDER=ollama       # embeddings (local always preferred)
```

**Recommended hybrid config** — best quality for job scoring with privacy for conversations:

```bash
LLM_PROVIDER=auto
SCORE_PROVIDER=claude       # job scoring needs structured JSON; Claude is more reliable
EMBED_PROVIDER=ollama       # embeddings should always be local
# everything else: auto (Ollama if available)
```

This means:
- Your conversations, BQ coaching, story building → Qwen 2.5 (local)
- Job listing scoring → Claude (more reliable structured JSON parsing)
- Story semantic search embeddings → nomic-embed-text (local)

---

## Changing the chat model mid-session

1. Pull the new model: `ollama pull qwen2.5:32b`
2. Update `.env`: `OLLAMA_CHAT_MODEL=qwen2.5:32b`
3. Restart: `make dev`

Or pull from the Futuro Settings page (starts the download with a progress stream).

---

## Performance tuning

### Keep-alive

Ollama unloads models from VRAM when idle. `OLLAMA_KEEP_ALIVE=10m` keeps Qwen loaded for 10 minutes after the last request. Good for interactive sessions. Set to `0` to unload immediately and free VRAM.

### Concurrency

Ollama handles one request at a time by default. If you trigger a job scout scan while chatting, the scoring requests will queue. This is fine — the UI doesn't block.

### GPU acceleration

Ollama uses Metal on Apple Silicon automatically. On Linux with NVIDIA:

```bash
# Verify GPU is being used
ollama run qwen2.5:7b "say hello"
# Look for "gpu layers" in the Ollama server logs
```

### Context window

Qwen 2.5 supports 128K context. Futuro's memory prompts are ~6,000–15,000 tokens — well within limits. If you have a very large `stories_bank.md` or `L2_knowledge.md`, the model will still handle it gracefully.

---

## Troubleshooting

**"Cannot reach Ollama at http://localhost:11434"**
→ Ollama isn't running. Start it: `ollama serve`

**"chat model 'qwen2.5:14b' not pulled"**
→ `ollama pull qwen2.5:14b`

**Responses are slow**
→ You're running on CPU. Check if Metal/CUDA is active:
```bash
ollama run qwen2.5:7b "hi"
# Check server output for: "llm_load_tensors: offloaded N/N layers to GPU"
```
→ Try a smaller model: `OLLAMA_CHAT_MODEL=qwen2.5:7b`

**Intent classification is unreliable**
→ Small models (7B) occasionally return "BQ." instead of "BQ". Futuro handles this by stripping punctuation. If it's still wrong, set `CLASSIFY_PROVIDER=claude` to use Claude for classification only (very cheap — 5 tokens per call).

**Job scoring JSON is malformed**
→ Smaller models occasionally break out of JSON format. Set `SCORE_PROVIDER=claude` for reliable structured output.

**Embeddings are poor quality**
→ Switch from the default to a dedicated embed model:
```bash
ollama pull nomic-embed-text
OLLAMA_EMBED_MODEL=nomic-embed-text
make rebuild-index
```

---

## Completely offline usage

With Ollama running and models pulled, Futuro works without internet:

```bash
ANTHROPIC_API_KEY=sk-ant-not-set   # dummy value — not called
LLM_PROVIDER=ollama                # force all tasks to Ollama
SCOUT_ENABLED=false                # scout uses jobspy which needs internet
```

Memory files, the SQLite DB, and ChromaDB are all local. The only network call in normal operation is to Ollama's local HTTP server.

---

## Model recommendations by task

| Task | Best local model | Notes |
|---|---|---|
| Daily chat | qwen2.5:7b | Fast enough for back-and-forth |
| BQ coaching | qwen2.5:14b | Better nuance, longer structured output |
| Story building | qwen2.5:14b | Needs sustained reasoning |
| Resume editing | qwen2.5:14b | Benefits from instruction following |
| Job scoring | qwen2.5:32b or Claude | Structured JSON output |
| Intent classification | qwen2.5:7b | Simple task, 7b is plenty |
| Embeddings | nomic-embed-text | Dedicated model, not a chat model |

---

## Using Futuro in Chinese

Qwen 2.5 is natively bilingual. The base persona prompt is in English, but you can chat in Chinese and Futuro will respond in Chinese:

> 你好，我今天需要练习行为面试题目，帮我准备一下

Qwen handles this naturally. The memory files remain in whichever language you write them in — markdown is markdown regardless of language.

If you want Futuro to always respond in Chinese, add this to your `L0_identity.md`:

```markdown
## Communication preference
Please always respond in Chinese (Simplified). 请用中文（简体）回复。
```

Futuro reads this file at every session and will adjust accordingly.
