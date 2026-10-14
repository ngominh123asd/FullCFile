"""
FileForge Backend - Document Conversion Endpoints - No auth required
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.endpoints.files import ensure_guest_user
from app.models.database import File, Job
from app.schemas.schemas import ConvertRequest, JobResponse
from app.services.document_service import document_service

router = APIRouter()


@router.post("", response_model=JobResponse)
async def convert_document(
    request: ConvertRequest,
    db: AsyncSession = Depends(get_db),
):
    """Convert document to target format"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(File).where(
            File.id == request.input_file_id,
            File.user_id == user_id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    document_types = ["markdown", "html", "pdf", "text", "docx", "doc", "rtf"]
    if file_record.file_type not in document_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_record.file_type}' is not a document",
        )

    # Create job
    job = Job(
        user_id=user_id,
        input_file_id=file_record.id,
        job_type="convert",
        output_format=request.output_format,
        config=request.options.model_dump() if request.options else {},
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    try:
        result = await document_service.convert(
            input_path=file_record.storage_path,
            output_format=request.output_format,
            options=request.options.model_dump() if request.options else None,
        )

        job.status = "completed"
        job.progress = 100
        job.stage = "completed"
        job.result = result
        await db.flush()

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        await db.flush()

    return job