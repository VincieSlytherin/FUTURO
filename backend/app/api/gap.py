from fastapi import APIRouter, HTTPException

from app.config import settings
from app.deps import AuthDep, MemoryDep
from app.gap_analysis import analyze_gap
from app.memory.vector_store import StoryVectorStore
from app.models.schemas import GapAnalysisRequest, GapAnalysisResult

router = APIRouter(prefix="/api/gap", tags=["gap"])


@router.post("/analyze", response_model=GapAnalysisResult)
async def analyze(body: GapAnalysisRequest, _: AuthDep, memory: MemoryDep):
    if not (body.jd_text or "").strip() and not (body.jd_url or "").strip():
        raise HTTPException(status_code=422, detail="Provide jd_text or jd_url.")

    store = StoryVectorStore(chroma_dir=settings.chroma_dir)
    if body.rebuild_index:
        store.rebuild_from_markdown(memory.read("stories_bank.md"))

    try:
        result = await analyze_gap(
            jd_text=body.jd_text,
            jd_url=body.jd_url,
            identity=memory.read("L0_identity.md"),
            resume=memory.read("resume_versions.md"),
            store=store,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return GapAnalysisResult(**result)
