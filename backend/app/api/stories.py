from fastapi import APIRouter, HTTPException
from app.deps import AuthDep, MemoryDep
from app.config import settings
from app.memory.vector_store import StoryVectorStore
from app.models.schemas import StorySearchRequest

router = APIRouter(prefix="/api/stories", tags=["stories"])


def _get_store(memory) -> StoryVectorStore:
    return StoryVectorStore(chroma_dir=settings.chroma_dir)


@router.post("/search")
async def search_stories(body: StorySearchRequest, _: AuthDep, memory: MemoryDep):
    store = _get_store(memory)
    results = store.search(body.query, n_results=body.n_results)
    return {"results": [
        {
            "story_id": r.story_id,
            "title": r.title,
            "one_liner": r.one_liner,
            "themes": r.themes,
            "distance": round(r.distance, 4),
            "result_metric": r.result_metric,
        }
        for r in results
    ]}


@router.post("/rebuild-index")
async def rebuild_index(_: AuthDep, memory: MemoryDep):
    import time
    store = _get_store(memory)
    stories_md = memory.read("stories_bank.md")
    start = time.time()
    count = store.rebuild_from_markdown(stories_md)
    duration_ms = int((time.time() - start) * 1000)
    return {"stories_indexed": count, "duration_ms": duration_ms}


@router.get("")
async def list_stories(_: AuthDep, memory: MemoryDep, theme: str | None = None):
    """Return raw stories_bank.md content — frontend parses for display."""
    content = memory.read("stories_bank.md")
    return {"content": content, "theme_filter": theme}


@router.get("/raw")
async def raw_stories(_: AuthDep, memory: MemoryDep):
    return {"content": memory.read("stories_bank.md")}
