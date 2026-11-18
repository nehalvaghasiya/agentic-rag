"""Submit/read/update/delete real document revisions via multipart upload."""

from dataclasses import asdict
from mimetypes import guess_type
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from agentic_rag.api.contracts import DocumentPreviewResponse, DocumentResponse
from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal
from agentic_rag.models.upload import Upload

router = APIRouter(tags=["Documents"])


@router.get("/kb/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_docs(
    kb_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, object]]:
    return await runtime.knowledge.list_docs(kb_id, principal)


@router.post("/kb/{kb_id}/documents", status_code=202)
async def upload(
    kb_id: str,
    files: list[UploadFile] = File(...),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, object]]:
    if not 1 <= len(files) <= 10:
        raise ValueError("Upload count must be between 1 and 10")
    uploads = [
        Upload(file.filename or "", await file.read(8 * 1024 * 1024 + 1), file.content_type)
        for file in files
    ]
    jobs = await runtime.knowledge.submit(uploads, kb_id, principal)
    if runtime.settings.environment == "demo":
        for _ in jobs:
            await runtime.worker.once(principal)
    return [asdict(job) for job in jobs]


@router.put("/documents/{doc_id}", status_code=202)
async def update_doc(
    doc_id: str,
    file: UploadFile = File(...),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    job = await runtime.knowledge.update(
        doc_id, Upload(file.filename or "", await file.read(8 * 1024 * 1024 + 1)), principal
    )
    if runtime.settings.environment == "demo":
        await runtime.worker.once(principal)
    return asdict(job)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_doc(
    doc_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> None:
    await runtime.knowledge.delete(doc_id, principal)


@router.get("/documents/{doc_id}/preview", response_model=DocumentPreviewResponse)
async def preview_doc(
    doc_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20_000, ge=1, le=50_000),
    version: int | None = Query(default=None, ge=1),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "private, no-store"
    return await runtime.knowledge.preview(doc_id, principal, offset, limit, version)


@router.get(
    "/documents/{doc_id}/download",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            }
        }
    },
)
async def download_doc(
    doc_id: str,
    version: int | None = Query(default=None, ge=1),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> Response:
    doc, content = await runtime.knowledge.original(doc_id, principal, version)
    return Response(
        content,
        media_type=guess_type(doc.title)[0] or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"document\"; filename*=UTF-8''{quote(doc.title, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
