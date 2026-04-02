from fastapi import APIRouter, HTTPException
from app.deps import AuthDep, MemoryDep
from app.models.schemas import MemoryWriteRequest, ApplyUpdateRequest, MemoryFileResponse

router = APIRouter(prefix="/api/memory", tags=["memory"])

ALLOWED_FILES = [
    "L0_identity.md",
    "L1_campaign.md",
    "planner.md",
    "L2_knowledge.md",
    "stories_bank.md",
    "resume_versions.md",
    "interview_log.md",
]


@router.get("/files")
async def list_files(_: AuthDep, memory: MemoryDep):
    result = []
    for f in ALLOWED_FILES:
        result.append({
            "filename": f,
            "last_modified": memory.last_modified(f),
            "last_commit": memory.last_commit_message(f),
        })
    return {"files": result}


@router.get("/{filename}", response_model=MemoryFileResponse)
async def get_file(filename: str, _: AuthDep, memory: MemoryDep):
    if filename not in ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    return MemoryFileResponse(
        filename=filename,
        content=memory.read(filename),
        last_modified=memory.last_modified(filename),
        last_commit=memory.last_commit_message(filename),
    )


@router.put("/{filename}")
async def write_file(
    filename: str,
    body: MemoryWriteRequest,
    _: AuthDep,
    memory: MemoryDep,
):
    if filename not in ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    memory.write_full(filename, body.content, f"manual edit: {filename}")
    return {"ok": True, "committed": True}


@router.post("/{filename}/apply-update")
async def apply_update(
    filename: str,
    body: ApplyUpdateRequest,
    _: AuthDep,
    memory: MemoryDep,
):
    if filename not in ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    memory.apply_update(
        filename=filename,
        section=body.section,
        action=body.action,
        content=body.content,
        reason=body.reason,
    )
    return {"ok": True, "committed": True}


@router.get("/git/log")
async def git_log(_: AuthDep, memory: MemoryDep):
    return {"commits": memory.git_log(max_entries=30)}
