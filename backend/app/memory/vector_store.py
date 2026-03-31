"""
Story vector store
------------------
ChromaDB-backed semantic search over stories_bank.md.
Embedding function is resolved from the provider router:
  - If EMBED_PROVIDER=ollama → OllamaEmbeddingFunction (calls /api/embed)
  - Otherwise → ChromaDB's built-in default (sentence-transformers, local)

The index is always rebuildable from the markdown source file.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings


@dataclass
class StoryMatch:
    story_id: str
    title: str
    one_liner: str
    themes: list[str]
    distance: float
    result_metric: str | None


# ── Embedding function adapters ───────────────────────────────────────────────

class OllamaEmbeddingFunction(EmbeddingFunction):
    """Wraps OllamaProvider.embed() for ChromaDB."""

    def __init__(self, base_url: str, model: str):
        import httpx
        self._base_url = base_url.rstrip("/")
        self._model    = model
        self._client   = httpx.Client(timeout=60.0)

    def __call__(self, input: Documents) -> Embeddings:  # type: ignore[override]
        texts = list(input)
        try:
            resp = self._client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except Exception:
            # Fallback: legacy single-string endpoint
            results = []
            for text in texts:
                r = self._client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                r.raise_for_status()
                results.append(r.json()["embedding"])
            return results


def _build_ef(settings=None):
    """Pick embedding function based on provider config."""
    try:
        from app.config import settings as _settings
        cfg = settings or _settings

        if (cfg.ollama_enabled and
                (cfg.embed_provider == "ollama" or
                 (cfg.embed_provider is None and cfg.llm_provider in ("ollama", "auto")))):
            return OllamaEmbeddingFunction(
                base_url=cfg.ollama_base_url,
                model=cfg.ollama_embed_model,
            )
    except Exception:
        pass

    from chromadb.utils import embedding_functions
    return embedding_functions.DefaultEmbeddingFunction()


# ── Vector store ──────────────────────────────────────────────────────────────

class StoryVectorStore:
    COLLECTION = "futuro_stories"

    def __init__(self, chroma_dir: Path, settings=None):
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.ef = _build_ef(settings)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

    def search(self, query: str, n_results: int = 3) -> list[StoryMatch]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        matches = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i]
            matches.append(StoryMatch(
                story_id=doc_id,
                title=meta.get("title", ""),
                one_liner=meta.get("one_liner", ""),
                themes=meta.get("themes", "").split(",") if meta.get("themes") else [],
                distance=dist,
                result_metric=meta.get("result_metric") or None,
            ))
        return matches

    def rebuild_from_markdown(self, stories_md: str) -> int:
        stories = self._parse_stories(stories_md)
        if not stories:
            return 0
        self.client.delete_collection(self.COLLECTION)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )
        self._upsert_many(stories)
        return len(stories)

    def upsert_story(self, story_id: str, parsed: dict) -> None:
        self._upsert_many([parsed])

    def _upsert_many(self, stories: list[dict]) -> None:
        ids, docs, metas = [], [], []
        for s in stories:
            ids.append(s["story_id"])
            docs.append(self._to_document(s))
            metas.append({
                "title":         s.get("title", ""),
                "one_liner":     s.get("one_liner", ""),
                "themes":        ",".join(s.get("themes", [])),
                "result_metric": s.get("result_metric", ""),
                "archived":      str(s.get("archived", False)),
            })
        self.collection.upsert(ids=ids, documents=docs, metadatas=metas)

    @staticmethod
    def _to_document(s: dict) -> str:
        parts = [
            s.get("one_liner", ""),
            s.get("situation", ""),
            s.get("action", ""),
            s.get("result", ""),
            "Themes: " + ", ".join(s.get("themes", [])),
        ]
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _parse_stories(content: str) -> list[dict]:
        stories = []
        blocks = re.split(r"^## STORY-", content, flags=re.MULTILINE)
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            if not lines:
                continue
            m = re.match(r"(\d+)\s*·\s*(.+)", lines[0])
            if not m:
                continue
            story_id = f"STORY-{m.group(1).zfill(3)}"
            title    = m.group(2).strip()
            text     = "\n".join(lines[1:])

            def extract(label):
                p = rf"\*\*{label}:\*\*\s*(.+?)(?=\n\*\*|\Z)"
                hit = re.search(p, text, re.DOTALL)
                return hit.group(1).strip() if hit else ""

            themes_raw = extract("Themes")
            themes = [t.strip() for t in themes_raw.split(",") if t.strip()]
            sit = re.search(r"\*\*Situation:\*\*\s*(.+?)(?=\*\*Task|\Z)",  text, re.DOTALL)
            act = re.search(r"\*\*Action:\*\*\s*(.+?)(?=\*\*Result|\Z)",  text, re.DOTALL)
            res = re.search(r"\*\*Result:\*\*\s*(.+?)(?=---|\*\*Short|\Z)", text, re.DOTALL)

            stories.append({
                "story_id": story_id,
                "title":    title,
                "one_liner": extract("The one-liner").strip("> "),
                "themes":   themes,
                "situation": sit.group(1).strip() if sit else "",
                "action":    act.group(1).strip() if act else "",
                "result":    res.group(1).strip() if res else "",
                "result_metric": "",
                "archived":  "[ARCHIVED]" in block,
            })
        return stories
