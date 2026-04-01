import mimetypes
import re
import shutil
from datetime import datetime
from pathlib import Path
from posixpath import normpath

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.deps import AuthDep
from app.models.schemas import PortfolioFileResponse, PortfolioFolderResponse, PortfolioListResponse

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _ensure_portfolio_dir() -> Path:
    settings.portfolio_dir.mkdir(parents=True, exist_ok=True)
    return settings.portfolio_dir


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Filename is required")
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    safe = safe.replace("..", ".")
    stem = Path(safe).stem.strip(" .") or "document"
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")
    return f"{stem}{suffix}"


def _sanitize_relative_path(relative_path: str, fallback_filename: str) -> str:
    raw = (relative_path or fallback_filename).replace("\\", "/").strip("/")
    if not raw:
        raw = fallback_filename
    normalized = normpath(raw)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise HTTPException(status_code=400, detail="Invalid folder path")

    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        raise HTTPException(status_code=400, detail="Invalid folder path")

    safe_parts = [re.sub(r"[^A-Za-z0-9._ -]", "_", part).strip(" .") or "folder" for part in parts[:-1]]
    safe_filename = _sanitize_filename(parts[-1])
    return "/".join([*safe_parts, safe_filename]) if safe_parts else safe_filename


def _unique_destination(relative_path: str) -> Path:
    directory = _ensure_portfolio_dir()
    candidate = directory / Path(relative_path)
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        retry = candidate.parent / f"{stem}-{index}{suffix}"
        if not retry.exists():
            return retry
        index += 1


def _resolve_existing_entry(entry_path: str) -> Path:
    raw = entry_path.replace("\\", "/").strip("/")
    candidate = (_ensure_portfolio_dir() / Path(raw)).resolve()
    directory = _ensure_portfolio_dir().resolve()
    if candidate != directory and directory not in candidate.parents:
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    return candidate


def _serialize_file(path: Path) -> PortfolioFileResponse:
    stat = path.stat()
    content_type, _ = mimetypes.guess_type(path.name)
    relative_path = path.relative_to(_ensure_portfolio_dir()).as_posix()
    return PortfolioFileResponse(
        filename=path.name,
        relative_path=relative_path,
        size_bytes=stat.st_size,
        content_type=content_type,
        uploaded_at=datetime.fromtimestamp(stat.st_mtime),
    )


@router.get("/files", response_model=PortfolioListResponse)
async def list_portfolio_files(_: AuthDep):
    directory = _ensure_portfolio_dir()
    files = [
        _serialize_file(path)
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    files.sort(key=lambda item: item.uploaded_at, reverse=True)

    folder_map: dict[str, PortfolioFolderResponse] = {}
    for file in files:
        parent = Path(file.relative_path).parent
        if str(parent) == ".":
            continue
        current = []
        for segment in parent.parts:
            current.append(segment)
            folder_path = "/".join(current)
            existing = folder_map.get(folder_path)
            if existing is None:
                folder_map[folder_path] = PortfolioFolderResponse(
                    path=folder_path,
                    file_count=1,
                    uploaded_at=file.uploaded_at,
                )
            else:
                existing.file_count += 1
                if file.uploaded_at > existing.uploaded_at:
                    existing.uploaded_at = file.uploaded_at

    folders = sorted(folder_map.values(), key=lambda item: item.path.lower())
    return PortfolioListResponse(files=files, folders=folders)


@router.post("/upload", response_model=PortfolioListResponse, status_code=201)
async def upload_portfolio_files(
    _: AuthDep,
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(default=[]),
):
    if not files:
        raise HTTPException(status_code=400, detail="Please choose at least one file")
    if paths and len(paths) != len(files):
        raise HTTPException(status_code=400, detail="Upload paths did not match uploaded files")

    saved_files: list[PortfolioFileResponse] = []
    for index, upload in enumerate(files):
        relative_path = _sanitize_relative_path(
            paths[index] if paths else "",
            upload.filename or "",
        )
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"{Path(relative_path).name} is empty")
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail=f"{Path(relative_path).name} exceeds the 20MB limit")

        destination = _unique_destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        saved_files.append(_serialize_file(destination))

    saved_files.sort(key=lambda item: item.uploaded_at, reverse=True)
    folder_map: dict[str, PortfolioFolderResponse] = {}
    for file in saved_files:
        parent = Path(file.relative_path).parent
        if str(parent) == ".":
            continue
        folder_key = parent.as_posix()
        current = folder_map.get(folder_key)
        if current is None:
            folder_map[folder_key] = PortfolioFolderResponse(
                path=folder_key,
                file_count=1,
                uploaded_at=file.uploaded_at,
            )
        else:
            current.file_count += 1
            if file.uploaded_at > current.uploaded_at:
                current.uploaded_at = file.uploaded_at
    return PortfolioListResponse(files=saved_files, folders=sorted(folder_map.values(), key=lambda item: item.path.lower()))


@router.get("/download/{entry_path:path}")
async def download_portfolio_file(entry_path: str, _: AuthDep):
    path = _resolve_existing_entry(entry_path)
    if path.is_dir():
        raise HTTPException(status_code=400, detail="Folders cannot be opened directly")
    content_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(path, media_type=content_type or "application/octet-stream", filename=path.name)


@router.delete("/entry/{entry_path:path}", status_code=204)
async def delete_portfolio_entry(entry_path: str, _: AuthDep):
    path = _resolve_existing_entry(entry_path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
