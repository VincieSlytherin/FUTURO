import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.deps import AuthDep, MemoryDep
from app.agents.base import get_agent

router = APIRouter(prefix="/api/intake", tags=["intake"])


class UrlIntakeRequest(BaseModel):
    url: str
    intent: str = "STRATEGY_INTEL"


class TextIntakeRequest(BaseModel):
    text: str
    source: str = "Unknown"
    intent: str = "STRATEGY_INTEL"


def _fetch_url(url: str) -> str:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_links=False)
            return text or ""
    except Exception:
        pass
    try:
        import httpx
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        return resp.text[:8000]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")


def _extract_file_text(file_bytes: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF read failed: {e}")
    if name.endswith(".docx"):
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"DOCX read failed: {e}")
    return file_bytes.decode("utf-8", errors="replace")


async def _intake_stream(text: str, source: str, memory):
    agent = get_agent("INTAKE", memory)
    ctx = memory.load_context("INTAKE")
    message = f"Please process this content from '{source}':\n\n{text[:6000]}"
    async for token in agent.stream(message, [], ctx):
        yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
    yield f"event: complete\ndata: {json.dumps({'source': source})}\n\n"


@router.post("/url")
async def intake_url(body: UrlIntakeRequest, _: AuthDep, memory: MemoryDep):
    text = _fetch_url(body.url)
    if not text:
        raise HTTPException(status_code=422, detail="No readable content found at URL")
    return StreamingResponse(
        _intake_stream(text, body.url, memory),
        media_type="text/event-stream",
    )


@router.post("/file")
async def intake_file(
    _: AuthDep,
    memory: MemoryDep,
    file: UploadFile = File(...),
    intent: str = "STRATEGY_INTEL",
):
    content = await file.read()
    text = _extract_file_text(content, file.filename or "upload")
    return StreamingResponse(
        _intake_stream(text, file.filename or "uploaded file", memory),
        media_type="text/event-stream",
    )


@router.post("/text")
async def intake_text(body: TextIntakeRequest, _: AuthDep, memory: MemoryDep):
    return StreamingResponse(
        _intake_stream(body.text, body.source, memory),
        media_type="text/event-stream",
    )
